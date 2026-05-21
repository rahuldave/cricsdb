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


def enrich_prob_record(
    pr: dict,
    scope_avg: float | None,
    direction: str | None,
    sample_size: int | None = None,
) -> dict:
    """Mutate a `prob_record` in place to attach a cohort baseline.

    Adds `scope_avg`, `delta_pct`, `direction`, `sample_size` — the
    ProbChip cohort-baseline extension from spec-prob-baselines.md §4.1.

    `direction` is the polarity literal ('higher_better' / 'lower_better'
    / None) — the chip orientation, not a metrics-registry key, because
    each prob chip's polarity is fixed (no per-chip METRIC_DIRECTIONS
    lookup needed; see spec §6).

    `delta_pct` matches `wrap_metric` semantics — signed (value - scope_avg)
    / scope_avg × 100, rounded to 1 dp. Null when either side is null,
    scope_avg is zero, or direction is None (no polarity → comparison
    not meaningful, e.g. fielding P(=1)).
    """
    value = pr.get("value")
    delta_pct: float | None = None
    if (
        value is not None
        and scope_avg not in (None, 0)
        and direction is not None
    ):
        delta_pct = round((value - scope_avg) / scope_avg * 100, 1)
    pr["scope_avg"] = round(scope_avg, 4) if scope_avg is not None else None
    pr["delta_pct"] = delta_pct
    pr["direction"] = direction
    pr["sample_size"] = sample_size
    return pr
