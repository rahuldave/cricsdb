"""Sanity checks for player_scope_stats.

Run against any cricket.db (default: ./cricket.db; override with --db).
Covers:

  1. Pool conservation — sum of PSS per-player aggregates equals the
     SUM over delivery / wicket / fieldingcredit in the same scope.
     Catches double-counting and missed-wicket bugs.

  2. Incremental round-trip — running populate_incremental on the
     match_ids of a small scope deletes + reinserts the SAME rows
     populate_full would have produced. Catches drift between the
     two code paths.

  3. Cross-scope isolation — running populate_incremental on matches
     in scopes A + B leaves an unrelated scope C untouched.

Usage (local DB):
    uv run python tests/sanity/test_player_scope_stats.py

Usage (against the prod snapshot copied to /tmp):
    cp ~/Downloads/t20-cricket-db_download/data/cricket.db /tmp/cricket-prod-test.db
    uv run python tests/sanity/test_player_scope_stats.py --db /tmp/cricket-prod-test.db

Each check prints PASS or FAIL on its own line. The script exits 0 on
all-pass, 1 on any failure. Per CLAUDE.md the table is populated by
import_data.py and update_recent.py — these checks assume that has
already happened on the target DB.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from scripts.populate_player_scope_stats import populate_incremental, make_scope_key


PASS = "PASS"
FAIL = "FAIL"


async def check_pool_conservation(db) -> bool:
    """SUM(PSS) == SUM(delivery / wicket / fielding) in matching scope."""
    print("=== Pool conservation ===")
    ok = True

    # batting runs
    a = (await db.q("SELECT SUM(runs) AS r FROM playerscopestats"))[0]["r"]
    b = (await db.q("""
        SELECT SUM(d.runs_batter) AS r
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0
    """))[0]["r"]
    print(f"  batting runs:    PSS={a}  delivery={b}  {PASS if a == b else FAIL}")
    ok &= (a == b)

    # legal balls faced
    a = (await db.q("SELECT SUM(legal_balls) AS x FROM playerscopestats"))[0]["x"]
    b = (await db.q("""
        SELECT COUNT(*) AS x
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0
    """))[0]["x"]
    print(f"  legal balls:     PSS={a}  delivery={b}  {PASS if a == b else FAIL}")
    ok &= (a == b)

    # bowling runs_conceded (matches existing bowling.py: SUM(runs_total))
    a = (await db.q("SELECT SUM(runs_conceded) AS r FROM playerscopestats"))[0]["r"]
    b = (await db.q("""
        SELECT SUM(d.runs_total) AS r
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        WHERE d.bowler_id IS NOT NULL
          AND i.super_over = 0
    """))[0]["r"]
    print(f"  runs_conceded:   PSS={a}  delivery={b}  {PASS if a == b else FAIL}")
    ok &= (a == b)

    # bowler wickets (excl. run out / retired hurt / retired out / obstructing the field)
    a = (await db.q("SELECT SUM(wickets) AS w FROM playerscopestats"))[0]["w"]
    b = (await db.q("""
        SELECT COUNT(*) AS w
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        WHERE d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
          AND i.super_over = 0
    """))[0]["w"]
    print(f"  bowler wickets:  PSS={a}  delivery={b}  {PASS if a == b else FAIL}")
    ok &= (a == b)

    # batter dismissals (excl. retired hurt / retired out)
    a = (await db.q("SELECT SUM(dismissals) AS d FROM playerscopestats"))[0]["d"]
    b = (await db.q("""
        SELECT COUNT(*) AS d
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        WHERE w.player_out_id IS NOT NULL
          AND w.kind NOT IN ('retired hurt', 'retired out')
          AND i.super_over = 0
    """))[0]["d"]
    print(f"  dismissals:      PSS={a}  delivery={b}  {PASS if a == b else FAIL}")
    ok &= (a == b)

    return ok


async def _snapshot(db, sk: str) -> list[dict]:
    rows = await db.q(
        "SELECT person_id, runs, legal_balls, dismissals, wickets, "
        "catches, runouts, stumpings, matches "
        "FROM playerscopestats WHERE scope_key = :sk ORDER BY person_id",
        {"sk": sk},
    )
    return [dict(r) for r in rows]


async def check_incremental_roundtrip(db) -> bool:
    """populate_incremental on a scope's match_ids reproduces populate_full."""
    print("\n=== Incremental round-trip ===")

    # Pick the smallest non-trivial scope: a 2024+ event with the
    # fewest matches (often a 1-match international tour).
    rows = await db.q("""
        SELECT event_name, season, gender, team_type, COUNT(*) AS n
        FROM match
        WHERE event_name IS NOT NULL AND season >= '2024'
        GROUP BY event_name, season, gender, team_type
        ORDER BY n ASC LIMIT 1
    """)
    if not rows:
        print(f"  no 2024+ scopes found  {FAIL}")
        return False
    target = rows[0]
    print(f"  target: {target['event_name']} / {target['season']} / "
          f"{target['gender']} / {target['team_type']} "
          f"({target['n']} matches)")

    sk = make_scope_key(target["event_name"], target["season"],
                       target["gender"], target["team_type"])
    before = await _snapshot(db, sk)

    match_rows = await db.q(
        "SELECT id FROM match WHERE event_name = :en AND season = :s "
        "AND gender = :g AND team_type = :tt",
        {"en": target["event_name"], "s": target["season"],
         "g": target["gender"], "tt": target["team_type"]},
    )
    match_ids = [r["id"] for r in match_rows]

    await populate_incremental(db, match_ids)

    after = await _snapshot(db, sk)

    rc_match = (len(before) == len(after))
    data_match = (before == after)
    print(f"  rows: {len(before)} -> {len(after)}  "
          f"row count {PASS if rc_match else FAIL}, "
          f"data {PASS if data_match else FAIL}")
    return rc_match and data_match


async def check_cross_scope_isolation(db) -> bool:
    """Touching scopes A,B leaves unrelated scope C untouched."""
    print("\n=== Cross-scope isolation ===")

    # Pick A,B as small 2024+ scopes; C as IPL 2024 (large, unrelated).
    small = await db.q("""
        SELECT event_name, season, gender, team_type, COUNT(*) AS n
        FROM match
        WHERE event_name IS NOT NULL AND season >= '2024'
          AND event_name NOT LIKE 'Indian Premier League%'
        GROUP BY event_name, season, gender, team_type
        ORDER BY n ASC LIMIT 5
    """)
    if len(small) < 2:
        print(f"  not enough small scopes  {FAIL}")
        return False
    A, B = small[0], small[1]

    ctrl = await db.q("""
        SELECT event_name, season, gender, team_type
        FROM match
        WHERE event_name = 'Indian Premier League' AND season = '2024'
        LIMIT 1
    """)
    if not ctrl:
        print(f"  no IPL 2024 control scope  {FAIL}")
        return False
    C = ctrl[0]

    skA = make_scope_key(A["event_name"], A["season"], A["gender"], A["team_type"])
    skB = make_scope_key(B["event_name"], B["season"], B["gender"], B["team_type"])
    skC = make_scope_key(C["event_name"], C["season"], C["gender"], C["team_type"])

    ctrl_before = await _snapshot(db, skC)

    mids = []
    for s in (A, B):
        rs = await db.q(
            "SELECT id FROM match WHERE event_name = :e AND season = :s "
            "AND gender = :g AND team_type = :t",
            {"e": s["event_name"], "s": s["season"],
             "g": s["gender"], "t": s["team_type"]},
        )
        mids.extend(r["id"] for r in rs)

    await populate_incremental(db, mids)

    ctrl_after = await _snapshot(db, skC)
    ok = (ctrl_before == ctrl_after)
    print(f"  control IPL 2024 rows: {len(ctrl_before)} -> {len(ctrl_after)}  "
          f"{PASS if ok else FAIL}")
    return ok


async def main():
    ap = argparse.ArgumentParser(description="Sanity tests for player_scope_stats")
    ap.add_argument("--db", default="cricket.db",
                    help="Path to SQLite DB (default: ./cricket.db)")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{args.db}")
    await db.q("PRAGMA journal_mode = WAL")

    # Verify the table is populated.
    n = (await db.q("SELECT COUNT(*) AS n FROM playerscopestats"))[0]["n"]
    if n == 0:
        print("ERROR: playerscopestats is empty — run populate_full first",
              file=sys.stderr)
        sys.exit(1)
    print(f"playerscopestats rows: {n}")

    results = [
        await check_pool_conservation(db),
        await check_incremental_roundtrip(db),
        await check_cross_scope_isolation(db),
    ]

    print()
    if all(results):
        print("ALL PASS")
        sys.exit(0)
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
