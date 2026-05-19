"""Sanity: playerscopestats_fielding_position pool conservation.

This child differs from Phase 2a/2b in that the parent
`playerscopestats.{catches,stumpings,runouts}` INCLUDE substitute
catches, whereas this child EXCLUDES them (distribution-side
semantics — CLAUDE.md "Substitute fielders — INCLUDED in /leaders,
EXCLUDED in /distribution"). So the conservation is against the
source `fieldingcredit` table with the same predicates (is_substitute
filter, regular innings only, kind-grouped).

Three column-totals checked against fieldingcredit (regular innings,
non-substitute):

  - SUM(child.catches)   == COUNT WHERE kind IN ('caught','caught_and_bowled')
  - SUM(child.stumpings) == COUNT WHERE kind = 'stumped'
  - SUM(child.run_outs)  == COUNT WHERE kind = 'run_out'

Bucket integrity: position_bucket BETWEEN 1 AND 10, no NULLs.

Spot-check Dhoni at IPL (heavy stumpings + opener-concentrated
catches profile for a keeper).

Spec: internal_docs/spec-player-compare-average.md §4.4 + Phase 2c.

Usage:
  uv run python tests/sanity/test_playerscopestats_fielding_position.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

# (child_column, fieldingcredit_kind_list, predicate_description)
CONSERVED = [
    ("catches",   ("'caught'", "'caught_and_bowled'"), "caught + caught_and_bowled"),
    ("stumpings", ("'stumped'",),                       "stumped"),
    ("run_outs",  ("'run_out'",),                        "run_out"),
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

    print(f"Sanity: playerscopestats_fielding_position conservation ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Bucket integrity 1..10.
    print("\n  1. Bucket-range integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) FILTER (WHERE position_bucket IS NULL) AS null_count,
          COUNT(*) FILTER (WHERE position_bucket < 1 OR position_bucket > 10) AS oor_count,
          COUNT(*) AS total
        FROM playerscopestatsfieldingposition
    """).fetchone()
    ok, line = check(
        "position_bucket IS NOT NULL and BETWEEN 1 AND 10",
        row["null_count"] == 0 and row["oor_count"] == 0,
        f"null={row['null_count']}, out_of_range={row['oor_count']}, total={row['total']}",
    )
    print(line); all_passed &= ok

    # 2. Sum check vs fieldingcredit. Apply same predicates as the
    # populate script: is_substitute=0, regular innings, fielder_id
    # not null.
    print("\n  2. Aggregate conservation vs fieldingcredit (non-sub, regular innings):")
    for child_col, kinds_tuple, descr in CONSERVED:
        kind_list = ", ".join(kinds_tuple)
        child_sum = conn.execute(
            f"SELECT COALESCE(SUM({child_col}), 0) AS s FROM playerscopestatsfieldingposition"
        ).fetchone()["s"]
        fc_sum = conn.execute(f"""
            SELECT COUNT(*) AS c
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings  i ON i.id = d.innings_id
            WHERE COALESCE(fc.is_substitute, 0) = 0
              AND i.super_over = 0
              AND fc.fielder_id IS NOT NULL
              AND fc.kind IN ({kind_list})
        """).fetchone()["c"]
        ok, line = check(
            f"SUM(child.{child_col}) == fc kind {descr}, non-sub, regular",
            child_sum == fc_sum,
            f"child={child_sum}, fieldingcredit={fc_sum}",
        )
        print(line); all_passed &= ok

    # 3. Per-(person, scope) inequality vs parent: child sums must be
    # <= parent corresponding tallies (parent includes substitute
    # catches; child excludes them). The slack is exactly the
    # substitute-credit count per (fielder, scope).
    print("\n  3. Per-(person, scope) inequality vs parent playerscopestats:")
    for child_col, parent_col in [
        ("catches",   "catches"),
        ("stumpings", "stumpings"),
        ("run_outs",  "runouts"),
    ]:
        row = conn.execute(f"""
            SELECT COUNT(*) AS violations
            FROM (
              SELECT
                pss.person_id,
                pss.scope_key,
                pss.{parent_col} AS parent_val,
                COALESCE(SUM(pssfp.{child_col}), 0) AS child_val
              FROM playerscopestats pss
              LEFT JOIN playerscopestatsfieldingposition pssfp
                ON pssfp.person_id = pss.person_id
               AND pssfp.scope_key = pss.scope_key
              GROUP BY pss.person_id, pss.scope_key
            )
            WHERE child_val > parent_val
        """).fetchone()
        ok, line = check(
            f"SUM(pssfp.{child_col}) <= pss.{parent_col} for every (person, scope)",
            row["violations"] == 0,
            f"{row['violations']} (person, scope) rows where child exceeds parent",
        )
        print(line); all_passed &= ok

    # 4. Spot-check Dhoni at IPL (keeper profile: nontrivial stumpings,
    # opener-concentrated catches). Aggregate across IPL seasons —
    # pssfp + pss join per scope_key yields one row per (season,
    # bucket), so the per-bucket totals need a SUM().
    print("\n  4. Spot-check Dhoni IPL (person='4a8a2e3b'):")
    rows = conn.execute("""
        SELECT pssfp.position_bucket,
               SUM(pssfp.catches)   AS catches,
               SUM(pssfp.stumpings) AS stumpings,
               SUM(pssfp.run_outs)  AS run_outs
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pssfp.scope_key = pss.scope_key AND pssfp.person_id = pss.person_id
        WHERE pss.person_id = '4a8a2e3b'
          AND pss.tournament = 'Indian Premier League'
        GROUP BY pssfp.position_bucket
        ORDER BY pssfp.position_bucket
    """).fetchall()
    total_stump = sum(r["stumpings"] for r in rows)
    total_catch = sum(r["catches"] for r in rows)
    opener_catch = next((r["catches"] for r in rows if r["position_bucket"] == 1), 0)
    detail = f"total_stumpings={total_stump}, total_catches={total_catch}, opener_catches={opener_catch}"
    ok = total_stump >= 30 and total_catch >= 100 and opener_catch >= 30
    _, line = check(
        "Dhoni IPL: ≥30 stumps, ≥100 catches, ≥30 opener catches",
        ok,
        detail,
    )
    print(line + f"   ({detail})")
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
