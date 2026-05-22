"""Sanity: per-bucket cohort fields on /bowlers/{id}/summary over_distribution.

Spec: internal_docs/spec-mix-and-performance-charts.md §3.2 — the
mix-histogram + performance-vs-cohort charts read three cohort fields
attached to each `over_distribution` entry without a second roundtrip:

  - `cohort_balls_share`           — bucket's share of cohort-total
    legal balls; sums to 1.0 across the 20 buckets.
  - `cohort_economy`               — cohort runs × 6 / cohort balls
    at this bucket.
  - `cohort_wickets_per_innings`   — cohort wickets / cohort
    innings_bowled at this bucket.

Invariants:
  1. Length-20 array, one entry per over (1..20).
  2. `cohort_balls_share` is non-null on every bucket that the cohort
     touches; sums to 1.0 ± 1e-6.
  3. `cohort_economy` at a known bucket equals the SQL-derived value
     within rounding.
  4. `cohort_wickets_per_innings` is monotonically non-trivial:
     death overs (16-20) have a strictly higher mean than powerplay
     (1-6) — the rate-of-wicket curve in T20 cricket.

Usage:
  uv run python tests/sanity/test_bowler_summary_over_distribution.py
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

    print(f"Sanity: /bowlers/{{id}}/summary over_distribution cohort fields ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Bumrah at IPL — densely populated, all 20 over buckets have data.
    resp = get(
        args.host, "/api/v1/bowlers/462411b3/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    od = resp["over_distribution"]

    # 1. Length 20.
    print("\n  1. Shape:")
    ok = len(od) == 20
    _, line = check("over_distribution length 20", ok, f"got {len(od)}")
    print(line); all_passed &= ok

    overs = [e.get("over") for e in od]
    ok = overs == list(range(1, 21))
    _, line = check("over numbers 1..20 in order", ok, f"got {overs}")
    print(line); all_passed &= ok

    # 2. Cohort balls share sums to 1.
    print("\n  2. cohort_balls_share sums to 1.0:")
    total = sum((e.get("cohort_balls_share") or 0) for e in od)
    ok = abs(total - 1.0) < 1e-6
    _, line = check(
        "sum(cohort_balls_share) ≈ 1.0",
        ok, f"sum = {total:.9f}",
    )
    print(line); all_passed &= ok

    # 3. cohort_economy at over 1 matches a direct SQL aggregate.
    print("\n  3. cohort_economy at over 1 matches SQL:")
    row = conn.execute("""
        SELECT SUM(psso.runs_conceded) AS runs,
               SUM(psso.legal_balls)   AS balls
        FROM playerscopestatsover psso
        WHERE psso.over_number = 1
          AND psso.scope_key IN (
              SELECT scope_key FROM playerscopestats pss
              WHERE pss.gender = 'male'
                AND pss.team_type = 'club'
                AND pss.tournament = 'Indian Premier League'
          )
    """).fetchone()
    expected_econ = round((row["runs"] or 0) * 6 / (row["balls"] or 1), 2)
    actual_econ = od[0].get("cohort_economy")
    ok = actual_econ is not None and abs(actual_econ - expected_econ) < 0.01
    _, line = check(
        "over 1 cohort_economy matches SQL",
        ok, f"sql={expected_econ}, api={actual_econ}",
    )
    print(line); all_passed &= ok

    # 4. cohort_wickets_per_innings: death > powerplay.
    print("\n  4. cohort_wickets_per_innings: death > powerplay:")
    pp_vals = [e.get("cohort_wickets_per_innings") for e in od[0:6]
               if e.get("cohort_wickets_per_innings") is not None]
    death_vals = [e.get("cohort_wickets_per_innings") for e in od[15:20]
                  if e.get("cohort_wickets_per_innings") is not None]
    pp_mean = sum(pp_vals) / len(pp_vals)
    death_mean = sum(death_vals) / len(death_vals)
    ok = death_mean > pp_mean
    _, line = check(
        "mean(death overs) > mean(powerplay overs)",
        ok, f"pp_mean={pp_mean:.3f}, death_mean={death_mean:.3f}",
    )
    print(line); all_passed &= ok

    print()
    print("=" * 60)
    print("ALL PASSED" if all_passed else "FAILURES")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
