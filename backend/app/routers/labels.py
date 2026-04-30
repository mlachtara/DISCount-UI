"""
/api/jobs/{job_id}/labels — submit a human label and retrieve the updated estimate.
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.models import BBoxAnnotation, CVModel, EstimateHistory, Job, Label, Tile, User
from app.schemas import (
    BBoxOut,
    BBoxSubmitRequest,
    EstimateOut,
    FineTuneStatusOut,
    LabelCreate,
    LabelOut,
)
from app.services.discount import compute_estimate
from app.services import detector as detector_service

router = APIRouter(prefix="/api/jobs", tags=["labels"])


@router.post("/{job_id}/labels", response_model=EstimateOut)
async def submit_label(
    job_id: int,
    body: LabelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record a human-provided count for a tile, then return the updated
    k-DISCOUNT estimate so the UI can update the live charts immediately.
    """
    # Verify job belongs to this user
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify tile belongs to job
    tile_result = await db.execute(
        select(Tile).where(Tile.id == body.tile_id, Tile.job_id == job_id)
    )
    tile = tile_result.scalar_one_or_none()
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found in this job")

    if body.f_count < 0:
        raise HTTPException(status_code=422, detail="f_count must be ≥ 0")

    # Upsert label (allow correction of an existing label)
    existing = await db.execute(
        select(Label).where(Label.tile_id == body.tile_id)
    )
    label = existing.scalar_one_or_none()
    if label is None:
        label = Label(tile_id=body.tile_id, job_id=job_id, f_count=body.f_count)
        db.add(label)
    else:
        label.f_count = body.f_count
        label.labeled_at = datetime.utcnow()

    await db.flush()

    # Recompute estimate and store history snapshot
    estimate = await _recompute_and_store(job_id, db)
    await db.commit()

    return estimate


@router.get("/{job_id}/labels", response_model=list[LabelOut])
async def list_labels(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all submitted labels for a job."""
    # Verify job belongs to user
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(Label).where(Label.job_id == job_id).order_by(Label.labeled_at)
    )
    return [LabelOut.model_validate(l) for l in result.scalars()]


@router.post("/{job_id}/bboxes", response_model=list[BBoxOut])
async def submit_bboxes(
    job_id: int,
    body: BBoxSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace bbox annotations for one tile, optionally triggering YOLO fine-tuning."""
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    tile_result = await db.execute(
        select(Tile).where(Tile.id == body.tile_id, Tile.job_id == job_id)
    )
    tile = tile_result.scalar_one_or_none()
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found in this job")

    await db.execute(
        delete(BBoxAnnotation).where(
            BBoxAnnotation.job_id == job_id,
            BBoxAnnotation.tile_id == body.tile_id,
        )
    )
    for box in body.boxes:
        if box.x2 <= box.x1 or box.y2 <= box.y1:
            raise HTTPException(status_code=422, detail="Each bbox must have x2>x1 and y2>y1.")
        db.add(
            BBoxAnnotation(
                job_id=job_id,
                tile_id=body.tile_id,
                class_id=box.class_id,
                x1=box.x1,
                y1=box.y1,
                x2=box.x2,
                y2=box.y2,
            )
        )
    await db.commit()

    model_result = await db.execute(select(CVModel).where(CVModel.id == job.model_id))
    model = model_result.scalar_one_or_none()
    if (model.model_kind if model else "yolo_v8") == "yolo_v8":
        # Mark queued quickly; the background task will move to running/failed/idle.
        job.yolo_finetune_status = "queued"
        job.yolo_finetune_error = None
        await db.commit()
        background_tasks.add_task(_run_yolo_finetune_background, job_id)

    result = await db.execute(
        select(BBoxAnnotation)
        .where(BBoxAnnotation.job_id == job_id, BBoxAnnotation.tile_id == body.tile_id)
        .order_by(BBoxAnnotation.id.asc())
    )
    return [BBoxOut.model_validate(r) for r in result.scalars()]


@router.get("/{job_id}/bboxes/{tile_id}", response_model=list[BBoxOut])
async def list_bboxes_for_tile(
    job_id: int,
    tile_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    if job_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = await db.execute(
        select(BBoxAnnotation)
        .where(BBoxAnnotation.job_id == job_id, BBoxAnnotation.tile_id == tile_id)
        .order_by(BBoxAnnotation.id.asc())
    )
    return [BBoxOut.model_validate(r) for r in result.scalars()]


@router.get("/{job_id}/finetune-status", response_model=FineTuneStatusOut)
async def get_finetune_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    model_kind = "yolo_v8"
    if job.model_id:
        model_result = await db.execute(select(CVModel).where(CVModel.id == job.model_id))
        model = model_result.scalar_one_or_none()
        if model is not None:
            model_kind = model.model_kind or "yolo_v8"
    bbox_tiles_result = await db.execute(
        select(func.count(func.distinct(BBoxAnnotation.tile_id))).where(BBoxAnnotation.job_id == job_id)
    )
    current_bbox_tile_count = int(bbox_tiles_result.scalar() or 0)
    last = int(job.yolo_last_trained_bbox_count or 0)
    next_auto = max(detector_service.FINE_TUNE_TRIGGER_EVERY, last + detector_service.FINE_TUNE_TRIGGER_EVERY)
    return FineTuneStatusOut(
        job_id=job_id,
        model_kind=model_kind,
        status=job.yolo_finetune_status or "idle",
        last_trained_bbox_count=last,
        current_bbox_tile_count=current_bbox_tile_count,
        next_auto_train_at=next_auto,
        latest_model_id=job.yolo_latest_model_id,
        error=job.yolo_finetune_error,
    )


# ── Estimate helpers ──────────────────────────────────────────────────────────

async def _recompute_and_store(job_id: int, db: AsyncSession) -> EstimateOut:
    """Compute the k-DISCOUNT estimate and persist a history snapshot."""
    # Fetch only g_count — no need to materialise full ORM objects for 1000s of tiles
    g_result = await db.execute(
        select(Tile.g_count).where(Tile.job_id == job_id)
    )
    all_g = [row[0] for row in g_result.all()]

    # All labels (including the one just added) joined to get g(s) for each
    labels_result = await db.execute(
        select(Label.f_count, Tile.g_count)
        .join(Tile, Label.tile_id == Tile.id)
        .where(Label.job_id == job_id)
    )
    pairs = [(g, f) for f, g in labels_result.all()]

    est = compute_estimate(all_g, pairs)

    # Persist snapshot
    snap = EstimateHistory(
        job_id=job_id,
        n_labeled=est.n_labeled,
        estimate=est.estimate,
        ci_lower=est.ci_lower,
        ci_upper=est.ci_upper,
        std_error=est.std_error,
    )
    db.add(snap)

    return EstimateOut(
        job_id=job_id,
        n_labeled=est.n_labeled,
        total_tiles=est.total_tiles,
        estimate=est.estimate,
        ci_lower=est.ci_lower,
        ci_upper=est.ci_upper,
        std_error=est.std_error,
        g_total=est.g_total,
    )


async def _run_yolo_finetune_background(job_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await detector_service.maybe_run_yolo_finetune(job_id, db)
