"""Sanity: per-bucket cohort fields on /batters/{id}/summary
position_distribution.

Spec: internal_docs/spec-mix-and-performance-charts.md §3.1 — the
mix-histogram + performance-vs-cohort charts read two cohort fields
attached to each `position_distribution` entry without a second
roundtrip:

  - `cohort_innings_share` — bucket's share of cohort-total innings;
    sums to 1.0 across the 10 buckets.
  - `cohort_strike_rate`   — cohort runs × 100 / cohort balls at
    this bucket.

Invariants:
  1. Length-10 array, one entry per bucket (1=opener, 2=#3, …, 10=#11).
  2. `cohort_innings_share` sums to 1.0 ± 1e-6.
  3. `cohort_strike_rate` at the opener bucket matches a direct SQL
     aggregate.
  4. SR drops at the tail — bucket 10 (#11) SR is strictly less than
     bucket 1 (opener) SR (the universal T20 pattern — tail-enders
     can't time the ball like openers).

Usage:
  uv run python tests/sanity/test_batter_summary_position_distribution.py
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

    print(f"Sanity: /batters/{{id}}/summary position_distribution cohort fields ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Kohli IPL — densely populated cohort at scope.
    resp = get(
        args.host, "/api/v1/batters/ba607b88/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    pd = resp["position_distribution"]

    print("\n  1. Shape:")
    ok = len(pd) == 10
    _, line = check("position_distribution length 10", ok, f"got {len(pd)}")
    print(line); all_passed &= ok

    buckets = [e.get("bucket") for e in pd]
    ok = buckets == list(range(1, 11))
    _, line = check("buckets 1..10 in order", ok, f"got {buckets}")
    print(line); all_passed &= ok

    print("\n  2. cohort_innings_share sums to 1.0:")
    total = sum((e.get("cohort_innings_share") or 0) for e in pd)
    ok = abs(total - 1.0) < 1e-6
    _, line = check(
        "sum(cohort_innings_share) ≈ 1.0",
        ok, f"sum = {total:.9f}",
    )
    print(line); all_passed &= ok

    print("\n  3. cohort_strike_rate at opener matches SQL:")
    row = conn.execute("""
        SELECT SUM(pssp.runs) AS runs,
               SUM(pssp.legal_balls) AS balls
        FROM playerscopestatsposition pssp
        WHERE pssp.position_bucket = 1
          AND pssp.scope_key IN (
              SELECT scope_key FROM playerscopestats pss
              WHERE pss.gender = 'male'
                AND pss.team_type = 'club'
                AND pss.tournament = 'Indian Premier League'
          )
    """).fetchone()
    expected_sr = round((row["runs"] or 0) * 100 / (row["balls"] or 1), 2)
    actual_sr = pd[0].get("cohort_strike_rate")
    ok = actual_sr is not None and abs(actual_sr - expected_sr) < 0.01
    _, line = check(
        "opener cohort_strike_rate matches SQL",
        ok, f"sql={expected_sr}, api={actual_sr}",
    )
    print(line); all_passed &= ok

    print("\n  4. Tail SR < opener SR (universal T20 pattern):")
    opener_sr = pd[0].get("cohort_strike_rate")
    tail_sr = pd[9].get("cohort_strike_rate")  # bucket 10 = #11
    ok = (opener_sr is not None and tail_sr is not None
          and tail_sr < opener_sr)
    _, line = check(
        "#11 cohort SR < opener cohort SR",
        ok, f"opener={opener_sr}, #11={tail_sr}",
    )
    print(line); all_passed &= ok

    print()
    print("=" * 60)
    print("ALL PASSED" if all_passed else "FAILURES")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
