"""Sanity: /scope/averages/players/bowling/summary correctness.

Invariants:
  1. Convex-combination: response scope_avg.economy matches the manual
     Σ over_mix[o] × cohort_economy[o] computation from by_over.
  2. Pool conservation: cohort.n_balls_total matches SQL SUM.
  3. drop= invariant: drop=filter_team is a no-op (not in scope-key
     axes); drop=tournament widens the cohort.
  4. Strict-cliff: 100% weight on a thin over → cliff fires, scope_avg
     null for all rate metrics.

Spec: spec-player-compare-average.md §8 Sanity tests, Phase 3.2.

Usage:
  uv run python tests/sanity/test_scope_averages_players_bowling.py
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


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def bowling_threshold(over: int) -> int:
    if over in (1, 2, 20):
        return 60
    if 3 <= over <= 6 or 16 <= over <= 19:
        return 50
    return 30


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: /scope/averages/players/bowling/summary ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Bumrah-shaped mix at IPL (PP + death heavy).
    mix = [0.02, 0.10, 0.05, 0.10, 0.07, 0.08, 0.02, 0.01, 0.01, 0.01,
           0.03, 0.04, 0.05, 0.04, 0.05, 0.04, 0.10, 0.07, 0.08, 0.03]
    resp = get(
        args.host, "/api/v1/scope/averages/players/bowling/summary",
        tournament="Indian Premier League",
        over_mix=",".join(str(m) for m in mix),
    )

    # 1. Convex combo.
    print("\n  1. Convex combination — Bumrah-shaped mix at IPL:")
    ok = resp["below_support"] is False
    _, line = check("no cliff", ok)
    print(line); all_passed &= ok

    by_over = resp["by_over"]
    expected_econ = sum(
        mix[i] * by_over[i]["economy"]
        for i in range(20)
        if mix[i] > 0 and by_over[i]["economy"] is not None
    )
    actual_econ = resp["economy"]["scope_avg"]
    ok = actual_econ is not None and abs(actual_econ - round(expected_econ, 2)) < 0.01
    _, line = check(
        "scope_avg.economy matches manual convex combination",
        ok,
        f"expected={expected_econ:.4f}, actual={actual_econ}",
    )
    print(line); all_passed &= ok

    # 2. Pool conservation.
    print("\n  2. Pool conservation (cohort.n_balls_total ↔ SQL):")
    sql_balls = conn.execute("""
        SELECT SUM(psso.legal_balls) AS s
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON pss.person_id = psso.person_id AND pss.scope_key = psso.scope_key
        WHERE pss.tournament = 'Indian Premier League'
    """).fetchone()["s"]
    ok = resp["cohort"]["n_balls_total"] == sql_balls
    _, line = check(
        "cohort.n_balls_total matches SQL SUM(legal_balls)",
        ok,
        f"endpoint={resp['cohort']['n_balls_total']}, sql={sql_balls}",
    )
    print(line); all_passed &= ok

    # 3. drop= invariant.
    print("\n  3. drop= invariant:")
    resp_drop = get(
        args.host, "/api/v1/scope/averages/players/bowling/summary",
        tournament="Indian Premier League",
        over_mix=",".join(str(m) for m in mix),
        drop="filter_team,filter_opponent",
    )
    ok = resp_drop["economy"]["scope_avg"] == resp["economy"]["scope_avg"]
    _, line = check(
        "drop=filter_team,filter_opponent is no-op",
        ok,
    )
    print(line); all_passed &= ok

    resp_drop_t = get(
        args.host, "/api/v1/scope/averages/players/bowling/summary",
        tournament="Indian Premier League",
        over_mix=",".join(str(m) for m in mix),
        drop="tournament",
    )
    ok = resp_drop_t["cohort"]["n_balls_total"] > resp["cohort"]["n_balls_total"]
    _, line = check(
        "drop=tournament widens cohort",
        ok,
        f"with_t={resp['cohort']['n_balls_total']}, drop_t={resp_drop_t['cohort']['n_balls_total']}",
    )
    print(line); all_passed &= ok

    # 4. Strict-cliff. Find a thin scope where some over has cohort
    # balls below threshold.
    print("\n  4. Strict-cliff invariant:")
    thin = conn.execute("""
        SELECT pss.season, SUM(psso.legal_balls) AS balls
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON psso.scope_key = pss.scope_key AND psso.person_id = pss.person_id
        WHERE psso.over_number = 20
        GROUP BY pss.season
        HAVING balls BETWEEN 1 AND 59
        ORDER BY balls
        LIMIT 1
    """).fetchone()
    if thin is None:
        print("    [SKIP] no thin scope found with over-20 balls < 60")
    else:
        cliff_mix = [0.0] * 19 + [1.0]  # 100% on over 20
        cliff_resp = get(
            args.host, "/api/v1/scope/averages/players/bowling/summary",
            season_from=thin["season"], season_to=thin["season"],
            over_mix=",".join(str(m) for m in cliff_mix),
        )
        ok = (
            cliff_resp["below_support"] is True
            and 20 in cliff_resp["cliff_buckets"]
            and cliff_resp["economy"]["scope_avg"] is None
        )
        _, line = check(
            f"100% weight on over-20 in thin season {thin['season']} → cliff fires",
            ok,
            f"below_support={cliff_resp['below_support']}, cliff_buckets={cliff_resp['cliff_buckets']}",
        )
        print(line); all_passed &= ok

    # by_over always length 20.
    ok = len(resp["by_over"]) == 20
    _, line = check("by_over always length 20", ok, f"length={len(resp['by_over'])}")
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
