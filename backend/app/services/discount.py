"""
k-DISCOUNT estimator.

Reference: Perez, Maji, Sheldon (2023) — "DISCOUNT: Counting in Large Image
Collections with Detector-Based Importance Sampling"  arXiv:2306.03151

The single-region estimator (S = Ω, all tiles in the job):

    F̂_kDIS(Ω) = G(Ω) · w̄         where  w̄ = (1/n) Σ f(sᵢ)/g(sᵢ)

    σ̂²(Ω)   = (1/n) Σ (f(sᵢ)/g(sᵢ) − F̂/G(Ω))²

    95% CI   = F̂ ± 1.96 · G(Ω) · σ̂(Ω) / √n

This file is intentionally dependency-light (only numpy/scipy) so it is easy
to unit-test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class DiscountEstimate:
    n_labeled: int
    total_tiles: int
    g_total: float       # G(Ω) = Σ g(s) over all tiles
    estimate: float      # F̂_kDIS
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    std_error: Optional[float]


def compute_estimate(
    all_g_counts: list[float],
    labeled_pairs: list[tuple[float, int]],  # [(g(sᵢ), f(sᵢ)), ...]
) -> DiscountEstimate:
    """
    Compute the k-DISCOUNT estimate from all detector counts and the subset
    of human-labeled (g, f) pairs.

    Parameters
    ----------
    all_g_counts:
        g(s) value (detector count + epsilon) for *every* tile in the job.
    labeled_pairs:
        (g(sᵢ), f(sᵢ)) for each tile that has been labeled by a human.
    """
    n_total = len(all_g_counts)
    G_omega = float(np.sum(all_g_counts))
    n = len(labeled_pairs)

    if n == 0:
        # No labels yet — fall back to raw detector total as initial estimate
        return DiscountEstimate(
            n_labeled=0,
            total_tiles=n_total,
            g_total=G_omega,
            estimate=G_omega,
            ci_lower=None,
            ci_upper=None,
            std_error=None,
        )

    # Importance weights  wᵢ = f(sᵢ) / g(sᵢ)
    weights = np.array([f / g for g, f in labeled_pairs], dtype=float)

    w_bar = float(np.mean(weights))
    estimate = G_omega * w_bar

    if n < 2:
        # Can't estimate variance with a single sample
        return DiscountEstimate(
            n_labeled=n,
            total_tiles=n_total,
            g_total=G_omega,
            estimate=estimate,
            ci_lower=None,
            ci_upper=None,
            std_error=None,
        )

    # Variance of importance weights (see §3.4 of the paper)
    sigma2 = float(np.mean((weights - w_bar) ** 2))
    std_error = G_omega * float(np.sqrt(sigma2 / n))

    ci_lower = max(0.0, estimate - 1.96 * std_error)
    ci_upper = estimate + 1.96 * std_error

    return DiscountEstimate(
        n_labeled=n,
        total_tiles=n_total,
        g_total=G_omega,
        estimate=estimate,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        std_error=std_error,
    )
