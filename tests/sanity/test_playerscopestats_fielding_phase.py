"""Sanity: playerscopestats_fielding_phase aggregate conservation.

Same shape as `test_playerscopestats_fielding_position.py`:
parent playerscopestats.{catches,stumpings,runouts} INCLUDE substitute
catches; this child EXCLUDES them (distribution-side semantics). So
the conservation is against the source `fieldingcredit` table with
matching predicates (is_substitute=0, regular innings, fielder_id
not null).

Three column-totals checked against fieldingcredit:

  - SUM(child.catches_in_phase)   == COUNT WHERE kind IN ('caught','caught_and_bowled')
  - SUM(child.stumpings_in_phase) == COUNT WHERE kind = 'stumped'
  - SUM(child.run_outs_in_phase)  == COUNT WHERE kind = 'run_out'

Plus a sibling-conservation check against playerscopestats_fielding_
position (the position-axis child of the same parent): both children
exclude substitutes and share the same source predicate, so their
catches / stumpings / run_outs sums must match.

Bucket integrity: phase_bucket BETWEEN 1 AND 3, no NULLs.

Spot-check Dhoni at IPL (keeper profile — heavy stumpings, mostly
powerplay/middle-overs catches).

Spec: internal_docs/spec-player-baseline-parity.md §3.1.2.

Usage:
  uv run python tests/sanity/test_playerscopestats_fielding_phase.py
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
    ("catches_in_phase",   ("'caught'", "'caught_and_bowled'"), "caught + caught_and_bowled"),
    ("stumpings_in_phase", ("'stumped'",),                       "stumped"),
    ("run_outs_in_phase",  ("'run_out'",),                        "run_out"),
]

# (phase_child_col, position_child_col)
SIBLING_COLS = [
    ("catches_in_phase",   "catches"),
    ("stumpings_in_phase", "stumpings"),
    ("run_outs_in_phase",  "run_outs"),
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

    print(f"Sanity: playerscopestats_fielding_phase conservation ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Bucket integrity 1..3.
    print("\n  1. Bucket-range integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) FILTER (WHERE phase_bucket IS NULL) AS null_count,
          COUNT(*) FILTER (WHERE phase_bucket < 1 OR phase_bucket > 3) AS oor_count,
          COUNT(*) AS total
        FROM playerscopestatsfieldingphase
    """).fetchone()
    ok, line = check(
        "phase_bucket IS NOT NULL and BETWEEN 1 AND 3",
        row["null_count"] == 0 and row["oor_count"] == 0,
        f"null={row['null_count']}, out_of_range={row['oor_count']}, total={row['total']}",
    )
    print(line); all_passed &= ok

    # 2. Aggregate conservation vs fieldingcredit (non-sub, regular).
    print("\n  2. Aggregate conservation vs fieldingcredit (non-sub, regular innings):")
    for child_col, kinds_tuple, descr in CONSERVED:
        kind_list = ", ".join(kinds_tuple)
        child_sum = conn.execute(
            f"SELECT COALESCE(SUM({child_col}), 0) AS s FROM playerscopestatsfieldingphase"
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

    # 3. Sibling conservation vs playerscopestats_fielding_position
    #    (same source rows, different axis). Sums must match.
    print("\n  3. Sibling conservation vs playerscopestats_fielding_position:")
    for phase_col, pos_col in SIBLING_COLS:
        phase_sum = conn.execute(
            f"SELECT COALESCE(SUM({phase_col}), 0) AS s FROM playerscopestatsfieldingphase"
        ).fetchone()["s"]
        pos_sum = conn.execute(
            f"SELECT COALESCE(SUM({pos_col}), 0) AS s FROM playerscopestatsfieldingposition"
        ).fetchone()["s"]
        ok, line = check(
            f"SUM(phase.{phase_col}) == SUM(position.{pos_col})",
            phase_sum == pos_sum,
            f"phase={phase_sum}, position={pos_sum}",
        )
        print(line); all_passed &= ok

    # 4. Per-(person, scope) inequality vs parent: child sums <= parent
    # (parent includes substitute credits, child excludes them).
    print("\n  4. Per-(person, scope) inequality vs parent playerscopestats:")
    for child_col, parent_col in [
        ("catches_in_phase",   "catches"),
        ("stumpings_in_phase", "stumpings"),
        ("run_outs_in_phase",  "runouts"),
    ]:
        row = conn.execute(f"""
            SELECT COUNT(*) AS violations
            FROM (
              SELECT
                pss.person_id,
                pss.scope_key,
                pss.{parent_col} AS parent_val,
                COALESCE(SUM(pssfph.{child_col}), 0) AS child_val
              FROM playerscopestats pss
              LEFT JOIN playerscopestatsfieldingphase pssfph
                ON pssfph.person_id = pss.person_id
               AND pssfph.scope_key = pss.scope_key
              GROUP BY pss.person_id, pss.scope_key
            )
            WHERE child_val > parent_val
        """).fetchone()
        ok, line = check(
            f"SUM(pssfph.{child_col}) <= pss.{parent_col} for every (person, scope)",
            row["violations"] == 0,
            f"{row['violations']} (person, scope) rows where child exceeds parent",
        )
        print(line); all_passed &= ok

    # 5. Spot-check Dhoni at IPL — heavy stumpings, distributed catches.
    print("\n  5. Spot-check Dhoni IPL (person='4a8a2e3b'):")
    rows = conn.execute("""
        SELECT pssfph.phase_bucket,
               SUM(pssfph.catches_in_phase)   AS catches,
               SUM(pssfph.stumpings_in_phase) AS stumpings,
               SUM(pssfph.run_outs_in_phase)  AS run_outs
        FROM playerscopestatsfieldingphase pssfph
        JOIN playerscopestats pss
          ON pssfph.scope_key = pss.scope_key AND pssfph.person_id = pss.person_id
        WHERE pss.person_id = '4a8a2e3b'
          AND pss.tournament = 'Indian Premier League'
        GROUP BY pssfph.phase_bucket
        ORDER BY pssfph.phase_bucket
    """).fetchall()
    total_stump = sum(r["stumpings"] for r in rows)
    total_catch = sum(r["catches"] for r in rows)
    distinct_phases = len({r["phase_bucket"] for r in rows})
    detail = (
        f"total_stumpings={total_stump}, total_catches={total_catch}, "
        f"phases_covered={distinct_phases}"
    )
    ok = total_stump >= 30 and total_catch >= 100 and distinct_phases == 3
    _, line = check(
        "Dhoni IPL: ≥30 stumps, ≥100 catches, all 3 phases present",
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
