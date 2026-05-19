"""Sanity: playerscopestats_position pool conservation against parent.

For every (person_id, scope_key) row in the parent `playerscopestats`,
the SUM over the corresponding child `playerscopestats_position` rows
must equal the parent's batting tally for each conserved column:

  - SUM(child.innings)     == parent.innings_batted
  - SUM(child.runs)        == parent.runs
  - SUM(child.legal_balls) == parent.legal_balls
  - SUM(child.dismissals)  == parent.dismissals
  - SUM(child.fours)       == parent.fours
  - SUM(child.sixes)       == parent.sixes
  - SUM(child.dots)        == parent.dots

Pool conservation is the design contract — the child is a per-bucket
refinement of the parent's batting numbers; nothing is created or
destroyed in the split.

Implementation: one SQL query produces a row per (person, scope) with
the parent value and the child SUM side-by-side; we report counts of
mismatches per column. Zero mismatches = pass.

Position-bucket sanity is asserted separately: every row must have
position_bucket in 1..10 (no NULL, no out-of-range).

Spec: internal_docs/spec-player-compare-average.md §4.2 + §7 Phase 2a.

Usage:
  uv run python tests/sanity/test_playerscopestats_position.py
  uv run python tests/sanity/test_playerscopestats_position.py --db /tmp/cricket-pssp-test.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

CONSERVED_COLUMNS = [
    ("innings",     "innings_batted"),
    ("runs",        "runs"),
    ("legal_balls", "legal_balls"),
    ("dismissals",  "dismissals"),
    ("fours",       "fours"),
    ("sixes",       "sixes"),
    ("dots",        "dots"),
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

    print(f"Sanity: playerscopestats_position pool conservation ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Bucket range — no NULL, no out-of-range.
    print("\n  1. Bucket-range integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) FILTER (WHERE position_bucket IS NULL) AS null_count,
          COUNT(*) FILTER (WHERE position_bucket < 1 OR position_bucket > 10) AS oor_count,
          COUNT(*) AS total
        FROM playerscopestatsposition
    """).fetchone()
    ok, line = check(
        "position_bucket IS NOT NULL and BETWEEN 1 AND 10",
        row["null_count"] == 0 and row["oor_count"] == 0,
        f"null={row['null_count']}, out_of_range={row['oor_count']}, total={row['total']}",
    )
    print(line); all_passed &= ok

    # 2. Pool conservation per conserved column. For each (person,
    # scope), the SUM over child rows must equal the parent value.
    print("\n  2. Pool conservation parent.col ↔ SUM(child.col):")

    # Build one query per conserved column comparing parent.val ↔
    # COALESCE(SUM(child.val), 0) for the same (person_id, scope_key).
    for child_col, parent_col in CONSERVED_COLUMNS:
        row = conn.execute(f"""
            SELECT COUNT(*) AS mismatches
            FROM (
              SELECT
                pss.person_id,
                pss.scope_key,
                pss.{parent_col} AS parent_val,
                COALESCE(SUM(pssp.{child_col}), 0) AS child_val
              FROM playerscopestats pss
              LEFT JOIN playerscopestatsposition pssp
                ON pssp.person_id = pss.person_id
               AND pssp.scope_key = pss.scope_key
              GROUP BY pss.person_id, pss.scope_key
            )
            WHERE parent_val != child_val
        """).fetchone()
        n = row["mismatches"]
        ok, line = check(
            f"SUM(pssp.{child_col}) == pss.{parent_col}",
            n == 0,
            f"{n} (person, scope) rows mismatch",
        )
        print(line); all_passed &= ok

    # 3. Spot-check: a known-good (person, scope) pair has expected
    #    non-trivial row count + non-zero opener bucket.
    print("\n  3. Spot-check Kohli IPL (person='ba607b88'):")
    rows = conn.execute("""
        SELECT pssp.position_bucket, pssp.innings, pssp.runs
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pssp.scope_key = pss.scope_key AND pssp.person_id = pss.person_id
        WHERE pss.person_id = 'ba607b88'
          AND pss.tournament = 'Indian Premier League'
        ORDER BY pssp.position_bucket
    """).fetchall()
    ok = len(rows) >= 1 and any(r["position_bucket"] == 1 and r["innings"] > 0 for r in rows)
    line_detail = ", ".join(f"b{r['position_bucket']}={r['innings']}/{r['runs']}" for r in rows)
    _, line = check(
        "Kohli IPL has rows; opener bucket non-zero",
        ok,
        line_detail,
    )
    print(line + (f"  ({line_detail})" if ok else ""))
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
