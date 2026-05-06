"""Wilson 95% confidence interval for binomial proportions.

Used by every probability field in the distribution dossiers
(/batters/{id}/distribution, /bowlers/{id}/distribution). Single
import site so the bowler v1 endpoint and the batter retrofit
share one source of truth.

Spec: internal_docs/spec-distribution-stats.md §11.3.
"""

from __future__ import annotations

import math


def wilson_ci(num: int, denom: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson 95% CI for `num` successes in `denom` trials.

    Returns (None, None) when `denom <= 0` (undefined). Bounded in
    [0, 1] always; non-degenerate at `num == 0` or `num == denom`.
    Closed-form score-test inversion — no scipy dependency.
    """
    if denom <= 0:
        return (None, None)
    p = num / denom
    z2 = z * z
    den = 1.0 + z2 / denom
    center = (p + z2 / (2.0 * denom)) / den
    half = z * math.sqrt(p * (1.0 - p) / denom + z2 / (4.0 * denom * denom)) / den
    return (max(0.0, center - half), min(1.0, center + half))


def prob_record(num: int, denom: int) -> dict:
    """Standard probability shape used across distribution dossiers.

    Returns `{value, num, denom, ci_low, ci_high}` — uniform across
    simples (denom = n_innings) and conditionals (denom = count of
    innings reaching the conditioning threshold).

    `value` is None when `denom == 0` (undefined ratio); CI bounds
    likewise. All numerics rounded to 4 dp for response stability.
    """
    if denom <= 0:
        return {"value": None, "num": num, "denom": 0,
                "ci_low": None, "ci_high": None}
    lo, hi = wilson_ci(num, denom)
    return {
        "value": round(num / denom, 4),
        "num": num,
        "denom": denom,
        "ci_low": round(lo, 4) if lo is not None else None,
        "ci_high": round(hi, 4) if hi is not None else None,
    }
