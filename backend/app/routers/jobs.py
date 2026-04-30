"""
/api/jobs — create, list, and inspect counting jobs.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.models import CVModel, Job, JobImage, Label, Tile, UploadedImage, User
from app.schemas import JobCreate, JobOut, TileOut
from app.services import detector as detector_service
from app.services import storage as storage_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Create job ────────────────────────────────────────────────────────────────

@router.post("", response_model=JobOut)
async def create_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a job, attach images, then launch the detector as a background task.
    """
    # Validate model belongs to this user
    model_result = await db.execute(
        select(CVModel).where(CVModel.id == body.model_id, CVModel.user_id == current_user.id)
    )
    if model_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Model not found")

    # Validate images belong to this user
    for img_id in body.image_ids:
        img_result = await db.execute(
            select(UploadedImage).where(
                UploadedImage.id == img_id,
                UploadedImage.user_id == current_user.id,
            )
        )
        if img_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Image {img_id} not found")

    job = Job(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        model_id=body.model_id,
        epsilon=body.epsilon,
        num_tiles=max(1, body.num_tiles),
        status="processing",
    )
    db.add(job)
    await db.flush()

    for img_id in body.image_ids:
        db.add(JobImage(job_id=job.id, image_id=img_id))

    await db.commit()
    await db.refresh(job)

    # Launch detector in the background (won't block the HTTP response)
    background_tasks.add_task(_run_detector_background, job.id)

    return _job_out(job, total_tiles=0, labeled_tiles=0)


# ── List / get jobs ───────────────────────────────────────────────────────────

@router.get("", response_model=list[JobOut])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    return [await _enrich_job(j, db) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await _fetch_job(job_id, current_user.id, db)
    return await _enrich_job(job, db)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete one job and all cascade-linked artifacts."""
    job = await _fetch_job(job_id, current_user.id, db)
    await db.delete(job)
    await db.commit()
    return None


# ── Tile grid (overview) ──────────────────────────────────────────────────────

@router.get("/{job_id}/tiles", response_model=list[TileOut])
async def list_tiles(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all tiles for a job with label status and image serving URL."""
    await _fetch_job(job_id, current_user.id, db)  # ensures job exists and belongs to user

    result = await db.execute(
        select(Tile)
        .where(Tile.job_id == job_id)
        .options(selectinload(Tile.image), selectinload(Tile.label))
    )
    tiles = result.scalars().all()
    return [_tile_out(t) for t in tiles]


# ── Next tile to label ────────────────────────────────────────────────────────

@router.get("/{job_id}/next-tile", response_model=TileOut | None)
async def next_tile(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the next tile the labeler should see, sampled ∝ g(s).
    Returns null when all tiles are labeled.
    """
    job = await _fetch_job(job_id, current_user.id, db)
    if job.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not ready for labeling (status: {job.status})",
        )

    # Query only the columns we need for sampling — avoids materialising
    # thousands of full ORM objects (including large detections_json blobs)
    # just to discover which tiles are still unlabeled.
    unlabeled_result = await db.execute(
        select(Tile.id, Tile.g_count)
        .where(Tile.job_id == job_id)
        .where(~exists().where(Label.tile_id == Tile.id))
    )
    unlabeled = unlabeled_result.all()

    if not unlabeled:
        return None  # all done

    candidates = [{"id": row.id, "g_count": row.g_count} for row in unlabeled]
    chosen = detector_service.sample_next_tile(candidates)

    # Fetch only the chosen tile with its relationships
    tile_result = await db.execute(
        select(Tile)
        .where(Tile.id == chosen["id"])
        .options(selectinload(Tile.image), selectinload(Tile.label))
    )
    tile = tile_result.scalar_one()
    return _tile_out(tile)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fetch_job(job_id: int, user_id: int, db: AsyncSession) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _enrich_job(job: Job, db: AsyncSession) -> JobOut:
    total_result = await db.execute(
        select(Tile).where(Tile.job_id == job.id)
    )
    total = len(total_result.scalars().all())

    labeled_result = await db.execute(
        select(Label).where(Label.job_id == job.id)
    )
    labeled = len(labeled_result.scalars().all())

    return _job_out(job, total_tiles=total, labeled_tiles=labeled)


def _job_out(job: Job, total_tiles: int, labeled_tiles: int) -> JobOut:
    return JobOut(
        id=job.id,
        name=job.name,
        description=job.description,
        model_id=job.model_id,
        status=job.status,
        epsilon=job.epsilon,
        created_at=job.created_at,
        error_message=job.error_message,
        total_tiles=total_tiles,
        labeled_tiles=labeled_tiles,
        yolo_finetune_status=getattr(job, "yolo_finetune_status", "idle") or "idle",
        yolo_finetune_error=getattr(job, "yolo_finetune_error", None),
        yolo_last_trained_bbox_count=getattr(job, "yolo_last_trained_bbox_count", 0) or 0,
        yolo_latest_model_id=getattr(job, "yolo_latest_model_id", None),
    )


def _tile_out(tile: Tile) -> TileOut:
    # Use the cropped sub-tile image when available; fall back to the full image.
    blob = tile.crop_blob_url if tile.crop_blob_url else tile.image.blob_url
    url = storage_service.get_serving_url(blob)
    return TileOut(
        id=tile.id,
        job_id=tile.job_id,
        image_id=tile.image_id,
        g_count=tile.g_count,
        g_count_raw=tile.g_count_raw,
        detections_json=tile.detections_json,
        is_labeled=tile.label is not None,
        image_url=url,
        tile_row=tile.tile_row or 0,
        tile_col=tile.tile_col or 0,
        grid_rows=tile.grid_rows or 1,
        grid_cols=tile.grid_cols or 1,
    )


async def _run_detector_background(job_id: int) -> None:
    """Wrapper that creates its own DB session for the background task."""
    async with AsyncSessionLocal() as db:
        await detector_service.run_detector_for_job(job_id, db)
