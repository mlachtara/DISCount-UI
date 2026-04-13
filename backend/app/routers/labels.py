"""
/api/jobs/{job_id}/labels — submit a human label and retrieve the updated estimate.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EstimateHistory, Label, Tile
from app.schemas import EstimateOut, LabelCreate, LabelOut
from app.services.discount import compute_estimate

router = APIRouter(prefix="/api/jobs", tags=["labels"])


@router.post("/{job_id}/labels", response_model=EstimateOut)
async def submit_label(
    job_id: int,
    body: LabelCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Record a human-provided count for a tile, then return the updated
    k-DISCOUNT estimate so the UI can update the live charts immediately.
    """
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
async def list_labels(job_id: int, db: AsyncSession = Depends(get_db)):
    """Return all submitted labels for a job."""
    result = await db.execute(
        select(Label).where(Label.job_id == job_id).order_by(Label.labeled_at)
    )
    return [LabelOut.model_validate(l) for l in result.scalars()]


# ── Estimate helpers ──────────────────────────────────────────────────────────

async def _recompute_and_store(job_id: int, db: AsyncSession) -> EstimateOut:
    """Compute the k-DISCOUNT estimate and persist a history snapshot."""
    # All tiles
    all_tiles_result = await db.execute(
        select(Tile).where(Tile.job_id == job_id)
    )
    all_tiles = all_tiles_result.scalars().all()
    all_g = [t.g_count for t in all_tiles]

    # All labels (including the one just added)
    labels_result = await db.execute(
        select(Label, Tile)
        .join(Tile, Label.tile_id == Tile.id)
        .where(Label.job_id == job_id)
    )
    pairs = [(tile.g_count, label.f_count) for label, tile in labels_result]

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
