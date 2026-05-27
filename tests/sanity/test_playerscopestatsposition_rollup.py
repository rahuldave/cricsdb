"""Sanity: playerscopestatsposition == rollup of inningsbatterperf (exact).

The headline cross-check of spec-batting-allball-runs-single-source.md
§5/§8/D2. The position cohort is now built as a pure GROUP BY of
inningsbatterperf (person × scope_key × position_bucket). This test
re-derives that rollup INDEPENDENTLY from inningsbatterperf and asserts
the stored table matches it exactly — every column, every cell, integer
counts (no to-2dp). That proves:

  - the precomputed cohort (what /scope/averages/players/* reads) equals
    the live aggregation 3b will run over the same per-innings table, so
    the "typical player" comparison can't jump at the precompute/live
    boundary (D2);
  - the convention is all-ball by construction — runs for a closed scope
    equal the all-ball delivery sum, strictly above the old legal-only
    number (IPL 2016 men's: 17962, not 17899).

Usage:
  uv run python tests/sanity/test_playerscopestatsposition_rollup.py
  uv run python tests/sanity/test_playerscopestatsposition_rollup.py --db /tmp/x.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

from scripts.populate_player_scope_stats import make_scope_key

# Closed, stable scopes (won't drift) + their expected all-ball run total
# (the spec §1 evidence — proves the cohort moved off the old legal-only
# number). (gender, event_name, season, expected_allball_runs)
PARITY_SCOPES = [
    ("male", "Indian Premier League", "2016", 17962),
    ("female", "Women's Big Bash League", "2018/19", None),
]

# (column name in playerscopestatsposition, matching SQL over inningsbatterperf)
ROLLUP_COLS = [
    ("innings", "COUNT(*)"),
    ("runs", "SUM(ib.runs)"),
    ("legal_balls", "SUM(ib.balls)"),
    ("dots", "SUM(ib.dots)"),
    ("fours", "SUM(ib.fours)"),
    ("sixes", "SUM(ib.sixes)"),
    ("dismissals", "SUM(CASE WHEN ib.not_out = 0 THEN 1 ELSE 0 END)"),
    ("thirties", "SUM(CASE WHEN ib.runs >= 30 AND ib.runs < 50 THEN 1 ELSE 0 END)"),
    ("fifties", "SUM(CASE WHEN ib.runs >= 50 AND ib.runs < 100 THEN 1 ELSE 0 END)"),
    ("hundreds", "SUM(CASE WHEN ib.runs >= 100 THEN 1 ELSE 0 END)"),
    ("ducks", "SUM(CASE WHEN ib.runs = 0 AND ib.not_out = 0 THEN 1 ELSE 0 END)"),
    ("failures_10", "SUM(CASE WHEN ib.runs <= 10 THEN 1 ELSE 0 END)"),
    ("seventies", "SUM(CASE WHEN ib.runs >= 70 AND ib.runs < 100 THEN 1 ELSE 0 END)"),
]


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         {detail}" if detail and not ok else ""))
    return ok


def scope_parity(conn, gender, event, season, expected_runs):
    team_types = [r["team_type"] for r in conn.execute(
        "SELECT DISTINCT team_type FROM match WHERE gender=? AND event_name=? AND season=?",
        (gender, event, season),
    ).fetchall()]
    if len(team_types) != 1:
        return ["scope spans team_types %s — pick a single-class scope" % team_types]

    scope_key = make_scope_key(event, season, gender, team_types[0] or "")
    col_names = [c for c, _ in ROLLUP_COLS]

    stored = {
        (r["person_id"], r["position_bucket"]): tuple(r[c] for c in col_names)
        for r in conn.execute(
            f"SELECT person_id, position_bucket, {', '.join(col_names)} "
            f"FROM playerscopestatsposition WHERE scope_key = ?", (scope_key,),
        ).fetchall()
    }

    rollup_sql = ", ".join(f"{expr} AS {name}" for name, expr in ROLLUP_COLS)
    fresh = {
        (r["pid"], r["bk"]): tuple(r[c] for c in col_names)
        for r in conn.execute(
            f"""SELECT ib.batter_id AS pid, ib.position_bucket AS bk, {rollup_sql}
                FROM inningsbatterperf ib
                JOIN innings i ON i.id = ib.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE i.super_over = 0 AND m.gender=? AND m.event_name=? AND m.season=?
                GROUP BY ib.batter_id, ib.position_bucket""",
            (gender, event, season),
        ).fetchall()
    }

    errs = []
    if set(stored) != set(fresh):
        only_s = len(set(stored) - set(fresh))
        only_f = len(set(fresh) - set(stored))
        errs.append(f"cell-set mismatch: stored-only={only_s} fresh-only={only_f}")
    for key in set(stored) & set(fresh):
        if stored[key] != fresh[key]:
            diffs = [f"{col_names[j]}: stored={stored[key][j]} fresh={fresh[key][j]}"
                     for j in range(len(col_names)) if stored[key][j] != fresh[key][j]]
            errs.append(f"{key}: " + "; ".join(diffs))
    if expected_runs is not None:
        total = sum(v[1] for v in fresh.values())
        if total != expected_runs:
            errs.append(f"all-ball runs {total} != expected {expected_runs}")
    return errs[:8]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    print(f"Sanity: playerscopestatsposition == inningsbatterperf rollup ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ok = True

    print("\n  1. Per-scope exact-integer rollup parity:")
    for gender, event, season, exp in PARITY_SCOPES:
        errs = scope_parity(conn, gender, event, season, exp)
        ok &= check(f"{event} {season} ({gender}): all columns == rollup of inningsbatterperf",
                    not errs, "; ".join(errs))

    # 2. Global identity — the table's column totals equal the same
    #    aggregates straight off inningsbatterperf (super_over=0). Guards
    #    the whole-DB write path, not just the two sampled scopes.
    print("\n  2. Global column totals == inningsbatterperf totals:")
    pos = conn.execute(
        "SELECT SUM(innings) i, SUM(runs) r, SUM(legal_balls) b, SUM(dots) d, "
        "SUM(fours) f, SUM(sixes) s, SUM(dismissals) dis, SUM(ducks) du "
        "FROM playerscopestatsposition"
    ).fetchone()
    ibp = conn.execute("""
        SELECT COUNT(*) i, SUM(ib.runs) r, SUM(ib.balls) b, SUM(ib.dots) d,
               SUM(ib.fours) f, SUM(ib.sixes) s,
               SUM(CASE WHEN ib.not_out=0 THEN 1 ELSE 0 END) dis,
               SUM(CASE WHEN ib.runs=0 AND ib.not_out=0 THEN 1 ELSE 0 END) du
        FROM inningsbatterperf ib JOIN innings i ON i.id=ib.innings_id
        WHERE i.super_over=0
    """).fetchone()
    for k in ("i", "r", "b", "d", "f", "s", "dis", "du"):
        ok &= check(f"global {k}: position={pos[k]} inningsbatterperf={ibp[k]}",
                    pos[k] == ibp[k], f"{pos[k]} != {ibp[k]}")

    conn.close()
    print("\n" + ("ALL PASS" if ok else "SOME FAILURES — see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
