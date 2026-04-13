"""
/api/jobs — create, list, and inspect counting jobs.
"""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.models import CVModel, Job, JobImage, Label, Tile, UploadedImage
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
):
    """
    Create a job, attach images, then launch the detector as a background task.
    """
    # Validate model exists
    model_result = await db.execute(select(CVModel).where(CVModel.id == body.model_id))
    if model_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Model not found")

    # Validate images exist
    for img_id in body.image_ids:
        img_result = await db.execute(
            select(UploadedImage).where(UploadedImage.id == img_id)
        )
        if img_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Image {img_id} not found")

    job = Job(
        name=body.name,
        description=body.description,
        model_id=body.model_id,
        epsilon=body.epsilon,
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
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()
    return [await _enrich_job(j, db) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _fetch_job(job_id, db)
    return await _enrich_job(job, db)


# ── Tile grid (overview) ──────────────────────────────────────────────────────

@router.get("/{job_id}/tiles", response_model=list[TileOut])
async def list_tiles(job_id: int, db: AsyncSession = Depends(get_db)):
    """Return all tiles for a job with label status and image serving URL."""
    await _fetch_job(job_id, db)  # ensures job exists

    result = await db.execute(
        select(Tile)
        .where(Tile.job_id == job_id)
        .options(selectinload(Tile.image), selectinload(Tile.label))
    )
    tiles = result.scalars().all()
    return [_tile_out(t) for t in tiles]


# ── Next tile to label ────────────────────────────────────────────────────────

@router.get("/{job_id}/next-tile", response_model=TileOut | None)
async def next_tile(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Return the next tile the labeler should see, sampled ∝ g(s).
    Returns null when all tiles are labeled.
    """
    job = await _fetch_job(job_id, db)
    if job.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not ready for labeling (status: {job.status})",
        )

    result = await db.execute(
        select(Tile)
        .where(Tile.job_id == job_id)
        .options(selectinload(Tile.label), selectinload(Tile.image))
    )
    all_tiles = result.scalars().all()
    unlabeled = [t for t in all_tiles if t.label is None]

    if not unlabeled:
        return None  # all done

    candidates = [{"id": t.id, "g_count": t.g_count} for t in unlabeled]
    chosen = detector_service.sample_next_tile(candidates)

    # Fetch full tile with relationships
    tile_result = await db.execute(
        select(Tile)
        .where(Tile.id == chosen["id"])
        .options(selectinload(Tile.image), selectinload(Tile.label))
    )
    tile = tile_result.scalar_one()
    return _tile_out(tile)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fetch_job(job_id: int, db: AsyncSession) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
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
    )


def _tile_out(tile: Tile) -> TileOut:
    url = storage_service.get_serving_url(tile.image.blob_url)
    return TileOut(
        id=tile.id,
        job_id=tile.job_id,
        image_id=tile.image_id,
        g_count=tile.g_count,
        g_count_raw=tile.g_count_raw,
        detections_json=tile.detections_json,
        is_labeled=tile.label is not None,
        image_url=url,
    )


async def _run_detector_background(job_id: int) -> None:
    """Wrapper that creates its own DB session for the background task."""
    async with AsyncSessionLocal() as db:
        await detector_service.run_detector_for_job(job_id, db)
