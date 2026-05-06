"""Sanity invariants for api/wilson.py — closed-form Wilson 95% CI.

Validates the helper used by every probability field across the
distribution dossiers (batter + bowler). Pinned-fixture and
property-based checks together ensure both:

  - Specific (num, denom) tuples produce the exact analytic Wilson
    bounds (catches off-by-one or sign errors).
  - General properties hold (CI within [0,1]; lo ≤ value ≤ hi;
    monotonicity in n; symmetry at p̂=0 vs p̂=1).

Spec: internal_docs/spec-distribution-stats.md §11.3.

Usage:
  uv run python tests/sanity/test_wilson_ci.py

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.wilson import wilson_ci, prob_record


def _check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    return ok, f"{status} · {label}{(' — ' + detail) if detail and not ok else ''}"


def _approx(a: float | None, b: float | None, eps: float = 1e-4) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < eps


def _analytic_wilson(num: int, denom: int, z: float = 1.96) -> tuple[float, float]:
    """Independent reproduction of the Wilson formula for cross-check."""
    p = num / denom
    z2 = z * z
    den = 1.0 + z2 / denom
    center = (p + z2 / (2.0 * denom)) / den
    half = z * math.sqrt(p * (1.0 - p) / denom + z2 / (4.0 * denom * denom)) / den
    return (max(0.0, center - half), min(1.0, center + half))


# ─── Pinned-fixture checks ─────────────────────────────────────────────

# (label, num, denom, expected_lo, expected_hi). Expected values
# match the published Wilson interval (cf. Wilson 1927; Brown,
# Cai, DasGupta 2001). Cross-check: 5/10 → [0.2366, 0.7634] is the
# standard textbook example. Validates against helper to 4 dp.
PINNED: list[tuple[str, int, int, float | None, float | None]] = [
    ("zero denom", 0, 0, None, None),
    ("zero denom positive num", 5, 0, None, None),
    ("zero successes n=10", 0, 10, 0.0, 0.2775),
    ("all successes n=10", 10, 10, 0.7225, 1.0),
    ("half successes n=10 (textbook)", 5, 10, 0.2366, 0.7634),
    ("rare event n=35 (P(>=5|>=2) shape)", 1, 35, 0.0051, 0.1453),
    ("rare event n=87 (P(>=5) shape)", 1, 87, 0.0020, 0.0623),
    ("p_near_zero n=87", 4, 87, 0.0180, 0.1123),
    ("conditional anchor n=35 (P(>=3|>=2))", 12, 35, 0.2083, 0.5085),
    ("large n p=0.5", 50, 100, 0.4038, 0.5962),
    ("very large n", 500, 1000, 0.4691, 0.5309),
]


def check_pinned() -> list[tuple[bool, str]]:
    out = []
    for label, num, denom, exp_lo, exp_hi in PINNED:
        lo, hi = wilson_ci(num, denom)
        out.append(_check(
            f"wilson_ci({num},{denom}) lo == {exp_lo}",
            _approx(lo, exp_lo),
            detail=f"got {lo}",
        ))
        out.append(_check(
            f"wilson_ci({num},{denom}) hi == {exp_hi}",
            _approx(hi, exp_hi),
            detail=f"got {hi}",
        ))
    return out


# ─── Property-based checks ─────────────────────────────────────────────

def check_properties() -> list[tuple[bool, str]]:
    out = []

    # Bounds: lo in [0,1], hi in [0,1], lo <= hi
    for n in [1, 5, 10, 35, 100, 1000]:
        for k in [0, 1, n // 4, n // 2, 3 * n // 4, n]:
            lo, hi = wilson_ci(k, n)
            assert lo is not None and hi is not None
            out.append(_check(
                f"bounds ({k},{n}): 0 ≤ lo",
                lo >= 0,
                detail=f"lo={lo}",
            ))
            out.append(_check(
                f"bounds ({k},{n}): hi ≤ 1",
                hi <= 1,
                detail=f"hi={hi}",
            ))
            out.append(_check(
                f"bounds ({k},{n}): lo ≤ hi",
                lo <= hi,
                detail=f"lo={lo}, hi={hi}",
            ))

    # Containment: lo ≤ p̂ ≤ hi (the point estimate falls inside its CI)
    for n in [10, 35, 100, 500]:
        for k in [1, n // 4, n // 2, 3 * n // 4, n - 1]:
            lo, hi = wilson_ci(k, n)
            p = k / n
            assert lo is not None and hi is not None
            out.append(_check(
                f"containment ({k},{n}): lo ≤ p̂ ≤ hi",
                lo <= p + 1e-9 and p - 1e-9 <= hi,
                detail=f"lo={lo}, p̂={p}, hi={hi}",
            ))

    # Symmetry: wilson(k, n) and wilson(n-k, n) are mirror-symmetric around 0.5
    for n in [10, 35, 100]:
        for k in [0, 1, 2, n // 3]:
            lo_a, hi_a = wilson_ci(k, n)
            lo_b, hi_b = wilson_ci(n - k, n)
            out.append(_check(
                f"symmetry ({k},{n}) vs ({n-k},{n}): hi_a ≈ 1 - lo_b",
                _approx(hi_a, 1 - lo_b),
                detail=f"hi_a={hi_a}, 1-lo_b={1 - lo_b}",
            ))

    # Monotonicity in n at fixed p̂: doubling sample with same p̂ tightens CI
    for k_per_unit in [1, 5]:
        for n in [10, 100]:
            lo_a, hi_a = wilson_ci(k_per_unit, n)
            lo_b, hi_b = wilson_ci(2 * k_per_unit, 2 * n)
            assert lo_a is not None and hi_a is not None
            assert lo_b is not None and hi_b is not None
            width_a = hi_a - lo_a
            width_b = hi_b - lo_b
            out.append(_check(
                f"width shrinks with n: ({k_per_unit},{n}) vs ({2*k_per_unit},{2*n})",
                width_b < width_a,
                detail=f"width_a={width_a}, width_b={width_b}",
            ))

    # Edge: zero successes — lo == 0 (analytically)
    for n in [1, 10, 100]:
        lo, _ = wilson_ci(0, n)
        out.append(_check(
            f"zero successes lo == 0 (n={n})",
            lo == 0.0,
            detail=f"lo={lo}",
        ))

    # Edge: full successes — hi ≈ 1 (analytically; clamped, may
    # be 1.0 - sub-machine-eps before the min(1.0, ...) clamp)
    for n in [1, 10, 100]:
        _, hi = wilson_ci(n, n)
        out.append(_check(
            f"full successes hi ≈ 1 (n={n})",
            _approx(hi, 1.0, eps=1e-12),
            detail=f"hi={hi}",
        ))

    # Cross-check helper against independent re-implementation
    for n in [10, 35, 87, 100, 1000]:
        for k in [0, 1, n // 3, n // 2, n - 1, n]:
            lo, hi = wilson_ci(k, n)
            elo, ehi = _analytic_wilson(k, n)
            out.append(_check(
                f"matches analytic re-impl ({k},{n})",
                _approx(lo, elo) and _approx(hi, ehi),
                detail=f"helper=({lo},{hi}) analytic=({elo},{ehi})",
            ))

    return out


# ─── prob_record shape ─────────────────────────────────────────────────

def check_prob_record_shape() -> list[tuple[bool, str]]:
    out = []

    # Zero-denom case
    r = prob_record(0, 0)
    out.append(_check("prob_record(0,0) value None", r["value"] is None))
    out.append(_check("prob_record(0,0) ci_low None", r["ci_low"] is None))
    out.append(_check("prob_record(0,0) ci_high None", r["ci_high"] is None))
    out.append(_check("prob_record(0,0) num=0", r["num"] == 0))
    out.append(_check("prob_record(0,0) denom=0", r["denom"] == 0))

    # Standard case
    r = prob_record(12, 35)
    out.append(_check("prob_record(12,35) value rounded", _approx(r["value"], 0.3429)))
    out.append(_check("prob_record(12,35) num", r["num"] == 12))
    out.append(_check("prob_record(12,35) denom", r["denom"] == 35))
    out.append(_check(
        "prob_record(12,35) ci_low ≤ value ≤ ci_high",
        r["ci_low"] <= r["value"] <= r["ci_high"],
        detail=f"got ({r['ci_low']}, {r['value']}, {r['ci_high']})",
    ))

    # All keys present
    expected_keys = {"value", "num", "denom", "ci_low", "ci_high"}
    out.append(_check(
        "prob_record has expected keys",
        set(prob_record(1, 10).keys()) == expected_keys,
    ))

    return out


# ─── Main ──────────────────────────────────────────────────────────────

def main() -> int:
    all_results: list[tuple[bool, str]] = []
    all_results.extend(check_pinned())
    all_results.extend(check_properties())
    all_results.extend(check_prob_record_shape())

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Wilson CI sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
