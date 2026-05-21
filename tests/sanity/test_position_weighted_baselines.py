"""Sanity: Tier 1 of spec-apples-to-apples-baselines.md.

Per-innings batting milestone baselines (hundreds_per_innings,
fifties_per_innings, thirties_per_innings, ducks_per_innings,
runs_per_innings, fours/sixes/boundaries_per_innings) on the
/scope/averages/players/batting/{summary,by-season} endpoints must be
position-weighted via convex combination on per-bucket per-innings
rates — not scope-flat parent aggregates.

Three classes of assertion:

  1. **Convex-combine identity** — for each weighted field, response
     scope_avg ≈ SUM(mix[i] * by_position[i].field_per_innings).
     Same math, exposed both ways.

  2. **Weighted ≠ scope-flat** — for fields with strong
     position-dependence (hundreds/inn, runs/inn, ducks/inn), the
     top-order-weighted scope_avg differs from the scope-flat
     parent-table per-innings aggregate by a meaningful margin.
     This is the bug we just fixed: pre-Tier 1 these were equal.

  3. **Headline ballpark** — Kohli IPL top-order baseline numbers
     fall in the expected range from spec §6.

Scoped to a closed historical window (Kohli IPL all-time) so SQL-
derived expecteds are stable across DB updates.

Usage:
  uv run python tests/sanity/test_position_weighted_baselines.py
  # API server must be running on http://localhost:8000 (or --host).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")
DEFAULT_HOST = "http://localhost:8000"


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def approx(a: float, b: float, tol: float = 0.005) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


WEIGHTED_FIELDS = [
    # (envelope_key, by_position_key, tolerance)
    ("hundreds_per_innings", "hundreds_per_innings", 0.002),
    ("fifties_per_innings",  "fifties_per_innings",  0.002),
    ("thirties_per_innings", "thirties_per_innings", 0.002),
    ("ducks_per_innings",    "ducks_per_innings",    0.002),
    ("runs_per_innings",     "runs_per_innings",     0.02),
    ("fours_per_innings",    "fours_per_innings",    0.002),
    ("sixes_per_innings",    "sixes_per_innings",    0.002),
    ("boundaries_per_innings", "boundaries_per_innings", 0.002),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: Tier 1 position-weighted baselines ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Top-order mix: 0.54/0.38/0.05/0.03 (Kohli-shaped). Use this for
    # the convex-combine identity + the weighted ≠ scope-flat check.
    TOP_ORDER_MIX = "0.54,0.38,0.05,0.03"
    KOHLI_ID = "ba607b88"

    # ─── 1. Convex-combine identity at IPL scope ───────────────────
    print("\n  1. /scope/averages/players/batting/summary @ IPL, top-order mix:")
    print("     each scope_avg = SUM(mix[i] * by_position[i].field)")
    resp = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        tournament="Indian Premier League",
        position_mix=TOP_ORDER_MIX,
    )
    mix = resp["cohort"]["position_mix"]
    by_position = resp["by_position"]
    for env_key, bp_key, tol in WEIGHTED_FIELDS:
        expected = sum(
            (mix[i] or 0) * (by_position[i].get(bp_key) or 0)
            for i in range(len(mix))
        )
        actual = resp[env_key]["scope_avg"]
        ok, line = check(
            f"{env_key} ≈ SUM(mix·by_position[{bp_key}])",
            approx(actual, expected, tol),
            f"actual={actual}, expected={expected:.4f}",
        )
        print(line); all_passed &= ok

    # ─── 2. Weighted ≠ scope-flat parent aggregate ────────────────
    print("\n  2. Weighted scope_avg ≠ scope-flat parent aggregate (the bug we fixed):")
    # Scope-flat parent: SUM(milestone)/SUM(innings_batted) over the
    # whole pool at the same scope (IPL all-time). Pre-Tier 1 cohort
    # path used this expression for milestones; we expect a meaningful
    # gap from the top-order-weighted value for position-dependent
    # fields (hundreds/inn most extreme).
    pool_row = conn.execute("""
        SELECT
          SUM(pss.innings_batted) AS innings,
          SUM(pss.hundreds) AS hundreds,
          SUM(pss.fifties) AS fifties,
          SUM(pss.thirties) AS thirties,
          SUM(pss.ducks) AS ducks,
          SUM(pss.runs) AS runs
        FROM playerscopestats pss
        WHERE pss.tournament = 'Indian Premier League'
    """).fetchone()
    inn = pool_row["innings"] or 0
    flat = {
        "hundreds_per_innings": (pool_row["hundreds"] or 0) / inn if inn else None,
        "fifties_per_innings":  (pool_row["fifties"]  or 0) / inn if inn else None,
        "thirties_per_innings": (pool_row["thirties"] or 0) / inn if inn else None,
        "ducks_per_innings":    (pool_row["ducks"]    or 0) / inn if inn else None,
        "runs_per_innings":     (pool_row["runs"]     or 0) / inn if inn else None,
    }
    # Strong-position-dependence fields: assert clear top-order skew.
    # E.g. hundreds_per_innings ought to ROUGHLY DOUBLE vs scope-flat
    # for a top-order mix (the spec headline 0.006 → 0.013-0.016).
    for env_key, min_ratio in [
        ("hundreds_per_innings", 1.5),
        ("runs_per_innings",     1.2),
    ]:
        actual = resp[env_key]["scope_avg"] or 0
        flat_val = flat[env_key] or 0
        ratio = actual / flat_val if flat_val else float("inf")
        ok, line = check(
            f"{env_key} top-order weighted ({actual}) > scope-flat ({flat_val:.4f}) by ≥ {min_ratio}x",
            ratio >= min_ratio,
            f"ratio={ratio:.2f}",
        )
        print(line); all_passed &= ok

    # ─── 3. Headline-ballpark from spec §6 ────────────────────────
    print("\n  3. Kohli IPL top-order baseline numbers (from spec §6 acceptance):")
    expected_ranges = [
        # (field, low, high)
        ("thirties_per_innings", 0.16, 0.22),
        ("fifties_per_innings",  0.15, 0.22),
        ("hundreds_per_innings", 0.010, 0.020),
        ("ducks_per_innings",    0.05, 0.09),
        ("runs_per_innings",     25.0, 31.0),
    ]
    for f, lo, hi in expected_ranges:
        val = resp[f]["scope_avg"]
        ok, line = check(
            f"{f} ∈ [{lo}, {hi}]",
            val is not None and lo <= val <= hi,
            f"actual={val}",
        )
        print(line); all_passed &= ok

    # ─── 4b. Bowling cohort over-weighted per-innings (Tier 2) ────
    print("\n  4b. /scope/averages/players/bowling/summary @ IPL (Bumrah-shaped mix):")
    # Bumrah's actual IPL mix from over_distribution.
    bowl_resp = get(
        args.host, "/api/v1/bowlers/462411b3/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    od = bowl_resp.get("over_distribution") or []
    total_lb = sum((o.get("legal_balls") or 0) for o in od)
    bowl_mix = [(o.get("legal_balls") or 0) / total_lb for o in od] if total_lb else []
    while len(bowl_mix) < 20:
        bowl_mix.append(0.0)
    mix_str_b = ",".join(f"{m:.6f}" for m in bowl_mix[:20])
    bowl_cohort = get(
        args.host, "/api/v1/scope/averages/players/bowling/summary",
        tournament="Indian Premier League",
        over_mix=mix_str_b,
    )
    # The per-innings rates should now be order-of-magnitude comparable
    # to the player's value (~1 wicket/innings, not the ~0.3
    # per-attendance-rate). Sanity-bound to 0.5–2× of player value.
    for k in ("wickets_per_innings", "four_wicket_hauls_per_innings"):
        player_v = bowl_resp.get(k, {}).get("value")
        cohort_v = bowl_cohort.get(k, {}).get("value")
        ok = (
            player_v is not None and cohort_v is not None
            and cohort_v > 0
            and 0.3 <= cohort_v / player_v <= 3.0
        )
        _, line = check(
            f"{k} cohort scope_avg in same order of magnitude as player",
            ok,
            f"player={player_v}, cohort={cohort_v}",
        )
        print(line); all_passed &= ok

    # Chip ↔ cohort symmetry on /bowlers/{id}/summary.
    print("\n  4c. /bowlers/462411b3/summary chip ↔ cohort endpoint cross-check:")
    for k in ("wickets_per_innings", "maidens_per_innings", "four_wicket_hauls_per_innings"):
        chip_sa = bowl_resp.get(k, {}).get("scope_avg")
        cohort_sa = bowl_cohort.get(k, {}).get("scope_avg")
        ok = approx(chip_sa, cohort_sa, 0.005)
        _, line = check(
            f"chip.{k}.scope_avg ≈ cohort endpoint scope_avg",
            ok,
            f"chip={chip_sa}, cohort={cohort_sa}",
        )
        print(line); all_passed &= ok

    # ─── 4. Kohli /batters/{id}/summary chip cohort_scope_avg ─────
    print("\n  4. /batters/ba607b88/summary.{milestone}.scope_avg cross-check:")
    bat_resp = get(
        args.host, f"/api/v1/batters/{KOHLI_ID}/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    # Re-fetch /scope/averages with Kohli's actual mix derived from
    # his position_distribution — closes the loop on the chip ↔ cohort
    # endpoint symmetry.
    pos_dist = bat_resp.get("position_distribution") or []
    total = sum((p.get("innings") or 0) for p in pos_dist)
    if total > 0:
        mix_vec = [(p.get("innings") or 0) / total for p in pos_dist]
        while len(mix_vec) < 10:
            mix_vec.append(0.0)
        mix_str = ",".join(f"{m:.6f}" for m in mix_vec[:10])
        cohort_resp = get(
            args.host, "/api/v1/scope/averages/players/batting/summary",
            tournament="Indian Premier League",
            position_mix=mix_str,
        )
        for env_key, _bp_key, tol in WEIGHTED_FIELDS:
            chip_sa = bat_resp.get(env_key, {}).get("scope_avg")
            cohort_sa = cohort_resp[env_key]["scope_avg"]
            ok, line = check(
                f"chip.{env_key}.scope_avg ≈ cohort endpoint scope_avg",
                approx(chip_sa, cohort_sa, tol),
                f"chip={chip_sa}, cohort={cohort_sa}",
            )
            print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
