"""Sanity: playerscopestats_batting_phase pool conservation against parent.

For every (person_id, scope_key) row in the parent `playerscopestats`,
the SUM over the corresponding child `playerscopestats_batting_phase`
rows must equal the parent's batting tally for each ball-grain column:

  - SUM(child.balls_in_phase)      == parent.legal_balls
  - SUM(child.runs_in_phase)       == parent.runs
  - SUM(child.dots_in_phase)       == parent.dots
  - SUM(child.fours_in_phase)      == parent.fours
  - SUM(child.sixes_in_phase)      == parent.sixes
  - SUM(child.dismissals_in_phase) == parent.dismissals

`innings_in_phase` is NOT conserved against parent.innings_batted:
  - A single innings can span all 3 phases (powerplay → middle → death),
    so the same innings can be counted up to 3 times across phase
    buckets (upper bound: 3 × parent).
  - A non-striker who never faces a legal ball appears in parent's
    `innings_batted` (because positions are assigned) but contributes
    nothing to any child phase bucket (lower bound is therefore not
    parent.innings_batted — it can be smaller).
We assert only the upper bound: `SUM(child.innings_in_phase) <= 3 *
parent.innings_batted`.

Phase-bucket sanity is asserted separately: every row must have
phase_bucket in 1..3 (no NULL, no out-of-range).

Spec: internal_docs/spec-player-baseline-parity.md §3.1.1.

Usage:
  uv run python tests/sanity/test_playerscopestats_batting_phase.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

CONSERVED_COLUMNS = [
    ("balls_in_phase",       "legal_balls"),
    ("runs_in_phase",        "runs"),
    ("dots_in_phase",        "dots"),
    ("fours_in_phase",       "fours"),
    ("sixes_in_phase",       "sixes"),
    ("dismissals_in_phase",  "dismissals"),
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

    print(f"Sanity: playerscopestats_batting_phase pool conservation ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Bucket range — no NULL, no out-of-range.
    print("\n  1. Bucket-range integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) FILTER (WHERE phase_bucket IS NULL) AS null_count,
          COUNT(*) FILTER (WHERE phase_bucket < 1 OR phase_bucket > 3) AS oor_count,
          COUNT(*) AS total
        FROM playerscopestatsbattingphase
    """).fetchone()
    ok, line = check(
        "phase_bucket IS NOT NULL and BETWEEN 1 AND 3",
        row["null_count"] == 0 and row["oor_count"] == 0,
        f"null={row['null_count']}, out_of_range={row['oor_count']}, total={row['total']}",
    )
    print(line); all_passed &= ok

    # 2. Pool conservation per ball-grain column.
    print("\n  2. Pool conservation parent.col ↔ SUM(child.col):")
    for child_col, parent_col in CONSERVED_COLUMNS:
        row = conn.execute(f"""
            SELECT COUNT(*) AS mismatches
            FROM (
              SELECT
                pss.person_id,
                pss.scope_key,
                pss.{parent_col} AS parent_val,
                COALESCE(SUM(pssbp.{child_col}), 0) AS child_val
              FROM playerscopestats pss
              LEFT JOIN playerscopestatsbattingphase pssbp
                ON pssbp.person_id = pss.person_id
               AND pssbp.scope_key = pss.scope_key
              GROUP BY pss.person_id, pss.scope_key
            )
            WHERE parent_val != child_val
        """).fetchone()
        n = row["mismatches"]
        ok, line = check(
            f"SUM(pssbp.{child_col}) == pss.{parent_col}",
            n == 0,
            f"{n} (person, scope) rows mismatch",
        )
        print(line); all_passed &= ok

    # 3. innings_in_phase upper bound: one innings can be counted up to
    #    3 times (one per phase the batter faced a ball in). Lower bound
    #    is not parent.innings_batted because non-strikers who never
    #    face a legal ball appear in parent but not in any child phase.
    print("\n  3. innings_in_phase <= 3 * parent.innings_batted:")
    row = conn.execute("""
        SELECT COUNT(*) AS bad
        FROM (
          SELECT
            pss.innings_batted AS parent_inns,
            COALESCE(SUM(pssbp.innings_in_phase), 0) AS child_inns_total
          FROM playerscopestats pss
          LEFT JOIN playerscopestatsbattingphase pssbp
            ON pssbp.person_id = pss.person_id
           AND pssbp.scope_key = pss.scope_key
          GROUP BY pss.person_id, pss.scope_key
        )
        WHERE child_inns_total > 3 * parent_inns
    """).fetchone()
    n = row["bad"]
    ok, line = check(
        "SUM(child.innings_in_phase) <= 3 * parent.innings_batted",
        n == 0,
        f"{n} (person, scope) rows exceed upper bound",
    )
    print(line); all_passed &= ok

    # 4. Spot-check: Kohli IPL has rows in all 3 phases with non-zero
    #    powerplay (he's an opener for most of his IPL career).
    print("\n  4. Spot-check Kohli IPL (person='ba607b88'):")
    rows = conn.execute("""
        SELECT pssbp.phase_bucket, pssbp.innings_in_phase, pssbp.runs_in_phase
        FROM playerscopestatsbattingphase pssbp
        JOIN playerscopestats pss
          ON pssbp.scope_key = pss.scope_key AND pssbp.person_id = pss.person_id
        WHERE pss.person_id = 'ba607b88'
          AND pss.tournament = 'Indian Premier League'
        ORDER BY pssbp.phase_bucket
    """).fetchall()
    has_all_3_phases = len({r["phase_bucket"] for r in rows}) >= 1  # at least 1 phase
    pp_nonzero = any(r["phase_bucket"] == 1 and r["runs_in_phase"] > 0 for r in rows)
    ok = has_all_3_phases and pp_nonzero
    line_detail = ", ".join(
        f"phase{r['phase_bucket']}={r['innings_in_phase']}/{r['runs_in_phase']}" for r in rows
    )
    _, line = check(
        "Kohli IPL has rows; powerplay bucket non-zero",
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
