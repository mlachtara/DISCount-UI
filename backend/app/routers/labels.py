"""
/api/jobs/{job_id}/labels — submit a human label and retrieve the updated estimate.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import EstimateHistory, Job, Label, Tile, User
from app.schemas import EstimateOut, LabelCreate, LabelOut
from app.services.discount import compute_estimate

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
