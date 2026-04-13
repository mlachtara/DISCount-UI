"""
/api/jobs/{job_id}/estimate — current estimate and full history for charts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EstimateHistory, Label, Tile
from app.schemas import EstimateHistoryPoint, EstimateOut
from app.services.discount import compute_estimate

router = APIRouter(prefix="/api/jobs", tags=["estimates"])


@router.get("/{job_id}/estimate", response_model=EstimateOut)
async def get_estimate(job_id: int, db: AsyncSession = Depends(get_db)):
    """Return the current k-DISCOUNT estimate for the job."""
    all_g = await _all_g(job_id, db)
    if all_g is None:
        raise HTTPException(status_code=404, detail="Job not found")

    pairs = await _labeled_pairs(job_id, db)
    est = compute_estimate(all_g, pairs)

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


@router.get("/{job_id}/estimate/history", response_model=list[EstimateHistoryPoint])
async def get_estimate_history(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Return the full sequence of estimate snapshots — one per label submitted.
    Used by the convergence and standard-error charts.
    """
    result = await db.execute(
        select(EstimateHistory)
        .where(EstimateHistory.job_id == job_id)
        .order_by(EstimateHistory.n_labeled)
    )
    return [EstimateHistoryPoint.model_validate(h) for h in result.scalars()]


# ── helpers ───────────────────────────────────────────────────────────────────

async def _all_g(job_id: int, db: AsyncSession) -> list[float] | None:
    result = await db.execute(select(Tile).where(Tile.job_id == job_id))
    tiles = result.scalars().all()
    if not tiles:
        # Check job existence separately to distinguish "no tiles" from "no job"
        from app.models import Job
        j = await db.execute(select(Job).where(Job.id == job_id))
        if j.scalar_one_or_none() is None:
            return None
    return [t.g_count for t in tiles]


async def _labeled_pairs(
    job_id: int, db: AsyncSession
) -> list[tuple[float, int]]:
    result = await db.execute(
        select(Label, Tile)
        .join(Tile, Label.tile_id == Tile.id)
        .where(Label.job_id == job_id)
    )
    return [(tile.g_count, label.f_count) for label, tile in result]
