"""Sanity: playerscopestats_over pool conservation against parent.

For every (person_id, scope_key) row in `playerscopestats`, the SUM
over the corresponding `playerscopestats_over` rows must equal the
parent's bowling tally for each conserved column:

  - SUM(child.runs_conceded) == parent.runs_conceded
  - SUM(child.legal_balls)   == parent.balls_bowled
  - SUM(child.wickets)       == parent.wickets
  - SUM(child.dots)          == parent.bowling_dots
  - SUM(child.boundaries)    == parent.boundaries_conceded

Pool conservation is the design contract — the over-split refines the
parent's bowling numbers; nothing is created or destroyed.

Also asserts: over_number is BETWEEN 1 AND 20 (no NULLs, no
out-of-range from the 0→1 shift in populate).

Spec: internal_docs/spec-player-compare-average.md §4.3 + §7 Phase 2b.

Usage:
  uv run python tests/sanity/test_playerscopestats_over.py
  uv run python tests/sanity/test_playerscopestats_over.py --db /tmp/cricket-pssp-test.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

CONSERVED_COLUMNS = [
    ("runs_conceded", "runs_conceded"),
    ("legal_balls",   "balls_bowled"),
    ("wickets",       "wickets"),
    ("dots",          "bowling_dots"),
    ("boundaries",    "boundaries_conceded"),
    # Tier 2 of spec-apples-to-apples-baselines.md — 4-fer attribution
    # at over_number = over where the bowler's 4th wicket fell; SUM
    # across over buckets per (person, scope) must equal the parent
    # table's four_wicket_hauls total.
    ("four_wicket_hauls", "four_wicket_hauls"),
]


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    print(f"Sanity: playerscopestats_over pool conservation ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Over-number integrity — 1..20, no NULL.
    print("\n  1. Over-number integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) FILTER (WHERE over_number IS NULL) AS null_count,
          COUNT(*) FILTER (WHERE over_number < 1 OR over_number > 20) AS oor_count,
          COUNT(*) AS total
        FROM playerscopestatsover
    """).fetchone()
    ok, line = check(
        "over_number IS NOT NULL and BETWEEN 1 AND 20",
        row["null_count"] == 0 and row["oor_count"] == 0,
        f"null={row['null_count']}, out_of_range={row['oor_count']}, total={row['total']}",
    )
    print(line); all_passed &= ok

    # 2. Pool conservation per conserved column.
    print("\n  2. Pool conservation parent.col ↔ SUM(child.col):")
    for child_col, parent_col in CONSERVED_COLUMNS:
        row = conn.execute(f"""
            SELECT COUNT(*) AS mismatches
            FROM (
              SELECT
                pss.person_id,
                pss.scope_key,
                pss.{parent_col} AS parent_val,
                COALESCE(SUM(psso.{child_col}), 0) AS child_val
              FROM playerscopestats pss
              LEFT JOIN playerscopestatsover psso
                ON psso.person_id = pss.person_id
               AND psso.scope_key = pss.scope_key
              GROUP BY pss.person_id, pss.scope_key
            )
            WHERE parent_val != child_val
        """).fetchone()
        n = row["mismatches"]
        ok, line = check(
            f"SUM(psso.{child_col}) == pss.{parent_col}",
            n == 0,
            f"{n} (person, scope) rows mismatch",
        )
        print(line); all_passed &= ok

    # 3. Spot-check: Bumrah IPL (death-overs weighted).
    print("\n  3. Spot-check Bumrah IPL (person='462411b3'):")
    rows = conn.execute("""
        SELECT psso.over_number, psso.legal_balls, psso.wickets
        FROM playerscopestatsover psso
        JOIN playerscopestats pss
          ON psso.scope_key = pss.scope_key AND psso.person_id = pss.person_id
        WHERE pss.person_id = '462411b3'
          AND pss.tournament = 'Indian Premier League'
        ORDER BY psso.over_number
    """).fetchall()
    total_wkts = sum(r["wickets"] for r in rows)
    death_wkts = sum(r["wickets"] for r in rows if r["over_number"] >= 16)
    ok = total_wkts > 0 and death_wkts / total_wkts > 0.4
    line_detail = f"total_wickets={total_wkts}, death_wickets={death_wkts}, death_share={(death_wkts/total_wkts if total_wkts else 0):.1%}"
    _, line = check(
        "Bumrah's death share (overs 16-20) > 40% of total wickets",
        ok,
        line_detail,
    )
    print(line + f"   ({line_detail})")
    all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
