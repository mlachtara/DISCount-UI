"""
/api/jobs/{job_id}/estimate — current estimate and full history for charts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import EstimateHistory, Job, Label, Tile, User
from app.schemas import EstimateHistoryPoint, EstimateOut
from app.services.discount import compute_estimate

router = APIRouter(prefix="/api/jobs", tags=["estimates"])


@router.get("/{job_id}/estimate", response_model=EstimateOut)
async def get_estimate(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current k-DISCOUNT estimate for the job."""
    await _verify_job_owner(job_id, current_user.id, db)

    all_g = await _all_g(job_id, db)
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
async def get_estimate_history(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the full sequence of estimate snapshots — one per label submitted.
    Used by the convergence and standard-error charts.
    """
    await _verify_job_owner(job_id, current_user.id, db)

    result = await db.execute(
        select(EstimateHistory)
        .where(EstimateHistory.job_id == job_id)
        .order_by(EstimateHistory.n_labeled)
    )
    return [EstimateHistoryPoint.model_validate(h) for h in result.scalars()]


# ── helpers ───────────────────────────────────────────────────────────────────

async def _verify_job_owner(job_id: int, user_id: int, db: AsyncSession) -> None:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job not found")


async def _all_g(job_id: int, db: AsyncSession) -> list[float]:
    result = await db.execute(select(Tile.g_count).where(Tile.job_id == job_id))
    return [row[0] for row in result.all()]


async def _labeled_pairs(
    job_id: int, db: AsyncSession
) -> list[tuple[float, int]]:
    result = await db.execute(
        select(Label.f_count, Tile.g_count)
        .join(Tile, Label.tile_id == Tile.id)
        .where(Label.job_id == job_id)
    )
    return [(g, f) for f, g in result.all()]
