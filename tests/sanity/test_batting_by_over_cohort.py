"""Sanity: Tier 4 of spec-apples-to-apples-baselines.md.

Per-over batting cohort endpoint
/api/v1/scope/averages/players/batting/by-over.

Three assertions:

1. **Response shape** — 20 entries (overs 1..20); cohort.ball_mix has
   20 entries summing to ~1.0.

2. **SR monotone-ish** — per-bucket SR is generally higher in death
   overs than powerplay overs (sanity-checks the cohort isn't
   inverted). Specifically: avg SR of overs 16..20 strictly greater
   than avg SR of overs 1..5.

3. **Per-bucket SR matches direct SQL** — for over 10 (a stable
   middle-overs bucket), the API's strike_rate equals SQL-derived
   SUM(runs)/SUM(legal_balls_faced) × 100.

Scoped to IPL all-time (stable historical scope).

Usage:
  uv run python tests/sanity/test_batting_by_over_cohort.py
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


def approx(a: float, b: float, tol: float = 0.1) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: Tier 4 per-over batting cohort ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Kohli IPL (large stable scope).
    resp = get(
        args.host, "/api/v1/scope/averages/players/batting/by-over",
        person_id="ba607b88", gender="male", team_type="club",
        tournament="Indian Premier League",
    )

    # 1. Response shape.
    print("\n  1. Response shape:")
    by_over = resp.get("by_over") or []
    ok, line = check(
        "by_over has 20 entries (overs 1..20)",
        len(by_over) == 20 and [r["over"] for r in by_over] == list(range(1, 21)),
        f"got {len(by_over)} entries",
    )
    print(line); all_passed &= ok

    ball_mix = resp.get("cohort", {}).get("ball_mix") or []
    mix_sum = sum(ball_mix)
    ok, line = check(
        "cohort.ball_mix length=20 and sums to ~1.0",
        len(ball_mix) == 20 and approx(mix_sum, 1.0, tol=0.01),
        f"sum={mix_sum}, length={len(ball_mix)}",
    )
    print(line); all_passed &= ok

    # 2. SR death > SR powerplay.
    print("\n  2. Cohort SR pattern:")
    pp_srs = [r["strike_rate"] for r in by_over[:5] if r["strike_rate"] is not None]
    death_srs = [r["strike_rate"] for r in by_over[15:20] if r["strike_rate"] is not None]
    pp_avg = sum(pp_srs) / len(pp_srs) if pp_srs else 0
    death_avg = sum(death_srs) / len(death_srs) if death_srs else 0
    ok, line = check(
        "avg cohort SR overs 16-20 > avg cohort SR overs 1-5",
        death_avg > pp_avg,
        f"death_avg={death_avg:.1f}, pp_avg={pp_avg:.1f}",
    )
    print(line); all_passed &= ok

    # 3. Per-bucket SR matches direct SQL (over 10, middle-overs).
    print("\n  3. Over 10 SR matches direct SQL:")
    row = conn.execute("""
        SELECT SUM(psbo.runs)*1.0/SUM(psbo.legal_balls_faced)*100 AS sr
        FROM playerscopestatsbattingover psbo
        JOIN playerscopestats pss ON pss.scope_key=psbo.scope_key AND pss.person_id=psbo.person_id
        WHERE pss.tournament='Indian Premier League'
          AND psbo.over_number=10
    """).fetchone()
    sql_sr = round(row["sr"], 1) if row["sr"] is not None else None
    api_sr = by_over[9]["strike_rate"]  # 0-indexed → over 10
    ok, line = check(
        "over 10 SR matches sqlite3 cricket.db",
        approx(api_sr, sql_sr, tol=0.05),
        f"sql={sql_sr}, api={api_sr}",
    )
    print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES")
        return 1


if __name__ == "__main__":
    sys.exit(main())
