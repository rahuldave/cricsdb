"""Sanity checks for bucket_baseline_* — the precomputed per-cell
team / league baselines (Phase 2 of Compare-tab perf).

Covers:

  1. Pool conservation — SUM-over-cells from the league rows equals
     the live aggregator's output for the whole DB and for a sampled
     (gender, team_type) bucket.

  2. Per-team correctness — for ~6 random (team, gender, team_type,
     tournament, season) cells, the baseline-table SUM equals the
     live-aggregator output for the same scope. Numeric: equality
     to the precision the API exposes.

  3. Incremental round-trip — running populate_incremental on the
     match_ids of a small set of cells DELETEs + reinserts the SAME
     rows populate_full would have produced.

  4. Cross-cell isolation — running populate_incremental on a few
     cells leaves unrelated cells untouched.

Usage (local DB):
    uv run python tests/sanity/test_bucket_baseline.py

Usage (against the prod snapshot copied to project-local tmp/):
    mkdir -p tmp && cp ~/Downloads/t20-cricket-db_download/data/cricket.db tmp/cricket-prod-test.db
    uv run python tests/sanity/test_bucket_baseline.py --db tmp/cricket-prod-test.db

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from scripts.populate_bucket_baseline import (
    populate_full, populate_incremental, LEAGUE_TEAM,
)


PASS = "PASS"
FAIL = "FAIL"


async def check_pool_conservation(db) -> bool:
    """SUM-over-cells from league rows equals SUM over the underlying
    delivery/wicket tables, for both the whole DB and one sampled
    (gender, team_type) bucket."""
    print("=== Pool conservation ===")
    ok = True

    # Whole-DB total runs from baseline = whole-DB total runs from delivery.
    a = (await db.q(
        f"SELECT SUM(total_runs) AS r FROM bucketbaselinebatting WHERE team = '{LEAGUE_TEAM}'"
    ))[0]["r"]
    b = (await db.q(
        "SELECT SUM(d.runs_total) AS r FROM delivery d "
        "JOIN innings i ON i.id = d.innings_id WHERE i.super_over = 0"
    ))[0]["r"]
    if (a or 0) == (b or 0):
        print(f"  {PASS}: whole-DB runs match ({a})")
    else:
        print(f"  {FAIL}: whole-DB runs diverge — baseline={a}, delivery={b}")
        ok = False

    # Whole-DB legal balls.
    a = (await db.q(
        f"SELECT SUM(legal_balls) AS r FROM bucketbaselinebatting WHERE team = '{LEAGUE_TEAM}'"
    ))[0]["r"]
    b = (await db.q(
        "SELECT SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS r "
        "FROM delivery d JOIN innings i ON i.id = d.innings_id WHERE i.super_over = 0"
    ))[0]["r"]
    if (a or 0) == (b or 0):
        print(f"  {PASS}: whole-DB legal balls match ({a})")
    else:
        print(f"  {FAIL}: legal balls diverge — baseline={a}, delivery={b}")
        ok = False

    # Whole-DB bowler-credited wickets.
    a = (await db.q(
        f"SELECT SUM(wickets) AS w FROM bucketbaselinebowling WHERE team = '{LEAGUE_TEAM}'"
    ))[0]["w"]
    b = (await db.q(
        "SELECT COUNT(*) AS w FROM wicket w "
        "JOIN delivery d ON d.id = w.delivery_id "
        "JOIN innings i ON i.id = d.innings_id "
        "WHERE i.super_over = 0 AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')"
    ))[0]["w"]
    if (a or 0) == (b or 0):
        print(f"  {PASS}: whole-DB bowler wickets match ({a})")
    else:
        print(f"  {FAIL}: wickets diverge — baseline={a}, delivery={b}")
        ok = False

    # Whole-DB fielding catches.
    a = (await db.q(
        f"SELECT SUM(catches) AS c FROM bucketbaselinefielding WHERE team = '{LEAGUE_TEAM}'"
    ))[0]["c"]
    b = (await db.q(
        "SELECT COUNT(*) AS c FROM fieldingcredit fc "
        "JOIN delivery d ON d.id = fc.delivery_id "
        "JOIN innings i ON i.id = d.innings_id "
        "WHERE i.super_over = 0 AND fc.kind = 'caught'"
    ))[0]["c"]
    if (a or 0) == (b or 0):
        print(f"  {PASS}: whole-DB catches match ({a})")
    else:
        print(f"  {FAIL}: catches diverge — baseline={a}, fieldingcredit={b}")
        ok = False

    # Whole-DB partnerships count (excluding retired).
    a = (await db.q(
        f"SELECT SUM(n) AS n FROM bucketbaselinepartnership WHERE team = '{LEAGUE_TEAM}'"
    ))[0]["n"]
    b = (await db.q(
        "SELECT COUNT(*) AS n FROM partnership p "
        "JOIN innings i ON i.id = p.innings_id "
        "WHERE i.super_over = 0 AND p.wicket_number IS NOT NULL "
        "AND (p.ended_by_kind IS NULL OR p.ended_by_kind NOT IN ('retired hurt', 'retired not out'))"
    ))[0]["n"]
    if (a or 0) == (b or 0):
        print(f"  {PASS}: whole-DB partnerships match ({a})")
    else:
        print(f"  {FAIL}: partnerships diverge — baseline={a}, partnership={b}")
        ok = False

    return ok


async def check_per_team_cell(db, gender, team_type, tournament, season, team) -> bool:
    """For one (cell, team), compare baseline-table sums to live aggregates."""
    label = f"{team} | {gender}/{team_type} | {tournament or '(no-tournament)'} | {season}"
    print(f"=== Per-team cell: {label} ===")
    ok = True

    # Batting runs + balls vs live.
    bl = await db.q(
        "SELECT total_runs, legal_balls, fours, sixes, dots, innings_batted "
        "FROM bucketbaselinebatting "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s AND team=:team",
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": team},
    )
    if not bl:
        print(f"  {FAIL}: baseline row missing")
        return False
    bl = bl[0]

    live = await db.q(
        """
        SELECT
            SUM(d.runs_total) AS total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots,
            COUNT(DISTINCT i.id) AS innings_batted
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND m.gender = :g AND m.team_type = :tt
          AND COALESCE(m.event_name, '') = :t AND m.season = :s
          AND i.team = :team
        """,
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": team},
    )
    live = live[0] if live else {}

    for col in ("total_runs", "legal_balls", "fours", "sixes", "dots", "innings_batted"):
        b_val, l_val = bl.get(col), live.get(col)
        if b_val == l_val:
            print(f"  {PASS}: batting.{col} = {b_val}")
        else:
            print(f"  {FAIL}: batting.{col} diverges — baseline={b_val}, live={l_val}")
            ok = False
    return ok


async def check_league_cell(db, gender, team_type, tournament, season) -> bool:
    """For one (cell, '__league__'), spot-check matches + bowling wickets."""
    label = f"LEAGUE | {gender}/{team_type} | {tournament or '(no-tournament)'} | {season}"
    print(f"=== League cell: {label} ===")
    ok = True

    bl = await db.q(
        "SELECT matches FROM bucketbaselinematch "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s AND team=:team",
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": LEAGUE_TEAM},
    )
    if not bl:
        print(f"  {FAIL}: baseline match row missing")
        return False
    bl_matches = bl[0]["matches"]

    live = (await db.q(
        "SELECT COUNT(*) AS m FROM match m "
        "WHERE m.gender = :g AND m.team_type = :tt "
        "AND COALESCE(m.event_name, '') = :t AND m.season = :s",
        {"g": gender, "tt": team_type, "t": tournament, "s": season},
    ))[0]["m"]
    if bl_matches == live:
        print(f"  {PASS}: matches = {bl_matches}")
    else:
        print(f"  {FAIL}: matches diverge — baseline={bl_matches}, live={live}")
        ok = False

    # Bowling wickets at league level — every credit-eligible wicket in cell.
    bl_w = (await db.q(
        "SELECT wickets FROM bucketbaselinebowling "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s AND team=:team",
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": LEAGUE_TEAM},
    ))[0]["wickets"]
    live_w = (await db.q(
        """
        SELECT COUNT(*) AS w FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
          AND m.gender = :g AND m.team_type = :tt
          AND COALESCE(m.event_name, '') = :t AND m.season = :s
        """,
        {"g": gender, "tt": team_type, "t": tournament, "s": season},
    ))[0]["w"]
    if bl_w == live_w:
        print(f"  {PASS}: bowling wickets = {bl_w}")
    else:
        print(f"  {FAIL}: wickets diverge — baseline={bl_w}, live={live_w}")
        ok = False
    return ok


async def check_identity_cols(db, gender, team_type, tournament, season, team) -> bool:
    """For one (cell, team), verify highest_inn / lowest_all_out
    identity + fifties/hundreds + worst_inn_runs + best_pair_partnership_id
    all match the live computation."""
    label = f"{team} | {gender}/{team_type} | {tournament} | {season}"
    print(f"=== Identity cols: {label} ===")
    ok = True

    # Highest innings score live.
    live = await db.q(
        """
        SELECT i.id AS innings_id, i.match_id, i.innings_number, i.team,
               SUM(d.runs_total) AS runs
        FROM delivery d JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND m.gender = :g AND m.team_type = :tt
          AND COALESCE(m.event_name, '') = :t AND m.season = :s AND i.team = :team
        GROUP BY i.id ORDER BY runs DESC, i.id LIMIT 1
        """,
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": team},
    )
    bl = await db.q(
        "SELECT highest_inn_runs, highest_inn_match_id, highest_inn_innings_number, fifties, hundreds "
        "FROM bucketbaselinebatting "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s AND team=:team",
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": team},
    )
    if not bl or not live:
        print(f"  {FAIL}: missing data")
        return False
    bl, live = bl[0], live[0]
    if bl["highest_inn_runs"] == live["runs"] and bl["highest_inn_match_id"] == live["match_id"]:
        print(f"  {PASS}: highest_inn_runs={bl['highest_inn_runs']} match={bl['highest_inn_match_id']}")
    else:
        print(f"  {FAIL}: highest mismatch — baseline={bl}, live={live}")
        ok = False

    # Fifties + hundreds live.
    live_fh = await db.q(
        """
        WITH bi AS (
            SELECT d.batter_id, i.id AS inn_id, SUM(d.runs_batter) AS r
            FROM delivery d JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0
              AND d.extras_wides = 0 AND d.extras_noballs = 0
              AND m.gender = :g AND m.team_type = :tt
              AND COALESCE(m.event_name, '') = :t AND m.season = :s AND i.team = :team
            GROUP BY d.batter_id, i.id
        )
        SELECT
          SUM(CASE WHEN r BETWEEN 50 AND 99 THEN 1 ELSE 0 END) AS fifties,
          SUM(CASE WHEN r >= 100 THEN 1 ELSE 0 END) AS hundreds
        FROM bi
        """,
        {"g": gender, "tt": team_type, "t": tournament, "s": season, "team": team},
    )
    lf = live_fh[0] if live_fh else {}
    if (bl["fifties"] or 0) == (lf.get("fifties") or 0) and (bl["hundreds"] or 0) == (lf.get("hundreds") or 0):
        print(f"  {PASS}: fifties={bl['fifties']} hundreds={bl['hundreds']}")
    else:
        print(f"  {FAIL}: fifties/hundreds — baseline=({bl['fifties']},{bl['hundreds']}) live=({lf.get('fifties')},{lf.get('hundreds')})")
        ok = False
    return ok


async def check_incremental_roundtrip(db) -> bool:
    """Pick one small cell, snapshot its baseline rows, run
    populate_incremental on the match ids in that cell, verify rows
    are byte-identical."""
    print("=== Incremental round-trip ===")

    # Pick a small cell — find one with ~6-12 matches.
    target = (await db.q(
        """
        SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament, m.season,
               COUNT(*) AS c
        FROM match m
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        HAVING c BETWEEN 6 AND 12
        ORDER BY c DESC
        LIMIT 1
        """
    ))
    if not target:
        print(f"  {FAIL}: no candidate cell found")
        return False
    g, tt, t, s = target[0]["gender"], target[0]["team_type"], target[0]["tournament"], target[0]["season"]
    print(f"  cell: {g}/{tt} | {t!r} | {s} ({target[0]['c']} matches)")

    # Snapshot baseline rows for this cell.
    # bucketbaselinemoments has no `team` column — at most 1 row per
    # cell, ORDER BY 1 keeps the query uniform without an ordering key.
    def _order_clause(table):
        if table == "bucketbaselinephase":
            return "ORDER BY team, phase, side"
        if table == "bucketbaselinepartnership":
            return "ORDER BY team, wicket_number"
        if table == "bucketbaselinepartnershiptop":
            return "ORDER BY wicket_number, rank"
        if table == "bucketbaselinemoments":
            return "ORDER BY 1"
        return "ORDER BY team"

    snapshot = {}
    for table in ("bucketbaselinematch", "bucketbaselinebatting",
                  "bucketbaselinebowling", "bucketbaselinefielding",
                  "bucketbaselinephase", "bucketbaselinepartnership",
                  "bucketbaselinemoments", "bucketbaselinepartnershiptop"):
        rows = await db.q(
            f"SELECT * FROM {table} WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s {_order_clause(table)}",
            {"g": g, "tt": tt, "t": t, "s": s},
        )
        # Strip surrogate id (varies between runs).
        snapshot[table] = [{k: v for k, v in r.items() if k != "id"} for r in rows]

    # Get the match ids for this cell.
    match_ids = [r["id"] for r in await db.q(
        "SELECT id FROM match WHERE gender=:g AND team_type=:tt AND COALESCE(event_name, '')=:t AND season=:s",
        {"g": g, "tt": tt, "t": t, "s": s},
    )]
    print(f"  matches in cell: {len(match_ids)}")

    # Run incremental against this cell.
    await populate_incremental(db, match_ids)

    # Re-snapshot.
    after = {}
    for table in snapshot.keys():
        rows = await db.q(
            f"SELECT * FROM {table} WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s {_order_clause(table)}",
            {"g": g, "tt": tt, "t": t, "s": s},
        )
        after[table] = [{k: v for k, v in r.items() if k != "id"} for r in rows]

    ok = True
    for table in snapshot.keys():
        if snapshot[table] == after[table]:
            print(f"  {PASS}: {table} unchanged ({len(snapshot[table])} rows)")
        else:
            print(f"  {FAIL}: {table} differs — before={len(snapshot[table])} rows, after={len(after[table])} rows")
            # Show first diverging row for debugging.
            for i, (b, a) in enumerate(zip(snapshot[table], after[table])):
                if b != a:
                    print(f"    row {i}: before={b}")
                    print(f"            after ={a}")
                    break
            ok = False
    return ok


async def check_highest_team_total(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """Bucket-derived (team, total, match_id, opponent) — must match
    live SQL byte-identical at the given scope. `live_where` uses
    `m.*` prefixes (event_name, season, gender, team_type); `bucket_where`
    uses the bucket table's unprefixed scope columns (tournament,
    season, gender, team_type)."""
    print(f"=== /series highest_team_total: {scope_desc} ===")
    live = await db.q(
        f"""SELECT i.team, tot.total, m.id AS match_id,
                   CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent
            FROM (SELECT d.innings_id, SUM(d.runs_total) AS total
                  FROM delivery d GROUP BY d.innings_id) tot
            JOIN innings i ON i.id = tot.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}
            ORDER BY tot.total DESC, m.id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT highest_inn_team AS team,
                   highest_inn_runs AS total,
                   highest_inn_match_id AS match_id,
                   (SELECT CASE WHEN team1 = highest_inn_team
                                THEN team2 ELSE team1 END
                      FROM match WHERE id = highest_inn_match_id) AS opponent
            FROM bucketbaselinebatting
            WHERE team = '{LEAGUE_TEAM}'
              AND highest_inn_match_id IS NOT NULL
              {(' AND ' + bucket_where) if bucket_where else ''}
            ORDER BY highest_inn_runs DESC, highest_inn_match_id ASC LIMIT 1""",
        params,
    )
    l = dict(live[0]) if live else None
    b = dict(bucket[0]) if bucket else None
    if l == b:
        print(f"  {PASS}: {l}")
        return True
    print(f"  {FAIL}: live={l} bucket={b}")
    return False


async def check_top_scorer_wicket_taker(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """playerscopestats-driven top scorer / top wicket-taker — must
    match live SQL byte-identical (person_id + runs / wickets) at the
    given scope. Phase A of spec-series-precompute-followup.md."""
    print(f"=== /series top scorer + top wicket-taker: {scope_desc} ===")
    ok = True

    # Top scorer (live ts_q shape).
    live = await db.q(
        f"""SELECT d.batter_id AS person_id, SUM(d.runs_batter) AS runs
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 AND m.match_type IN ('T20','IT20')
              AND d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
              {(' AND ' + live_where) if live_where else ''}
            GROUP BY d.batter_id
            ORDER BY runs DESC, d.batter_id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT person_id, SUM(runs) AS runs
            FROM playerscopestats
            {(' WHERE ' + bucket_where) if bucket_where else ''}
            GROUP BY person_id
            ORDER BY runs DESC, person_id ASC LIMIT 1""",
        params,
    )
    if live and bucket and live[0]["person_id"] == bucket[0]["person_id"] and live[0]["runs"] == bucket[0]["runs"]:
        print(f"  PASS: top_scorer person_id={live[0]['person_id']}, runs={live[0]['runs']}")
    else:
        print(f"  FAIL: live={live[0] if live else None} bucket={bucket[0] if bucket else None}")
        ok = False

    # Top wicket-taker (live tw_q shape).
    live = await db.q(
        f"""SELECT d.bowler_id AS person_id, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 AND m.match_type IN ('T20','IT20')
              AND d.bowler_id IS NOT NULL
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              {(' AND ' + live_where) if live_where else ''}
            GROUP BY d.bowler_id
            ORDER BY wickets DESC, d.bowler_id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT person_id, SUM(wickets) AS wickets
            FROM playerscopestats
            {(' WHERE ' + bucket_where) if bucket_where else ''}
            GROUP BY person_id
            ORDER BY wickets DESC, person_id ASC LIMIT 1""",
        params,
    )
    if live and bucket and live[0]["person_id"] == bucket[0]["person_id"] and live[0]["wickets"] == bucket[0]["wickets"]:
        print(f"  PASS: top_wicket_taker person_id={live[0]['person_id']}, wickets={live[0]['wickets']}")
    else:
        print(f"  FAIL: live={live[0] if live else None} bucket={bucket[0] if bucket else None}")
        ok = False

    return ok


async def check_batting_by_inning_roundtrip(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """bucketbaselinebatting first_inn_* / second_inn_* must match live
    SQL byte-identical at the league row level (team='__league__').
    Phase D of spec-series-precompute-followup.md."""
    print(f"=== /teams batting by-inning: {scope_desc} ===")
    ok = True
    for inn in (0, 1):
        prefix = "first_inn" if inn == 0 else "second_inn"
        live = await db.q(
            f"""SELECT
                SUM(CASE WHEN i.innings_number = :inn THEN d.runs_total ELSE 0 END) AS runs,
                COUNT(DISTINCT CASE WHEN i.innings_number = :inn THEN i.id END) AS count_inn,
                SUM(CASE WHEN i.innings_number = :inn AND d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_batter=4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END) AS fours,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_batter=6 THEN 1 ELSE 0 END) AS sixes,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_total=0 AND d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS dots
            FROM delivery d
            JOIN innings i ON i.id=d.innings_id
            JOIN match m ON m.id=i.match_id
            WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}""",
            {**params, "inn": inn},
        )
        wkts_live = await db.q(
            f"""SELECT COUNT(*) AS wkts
            FROM wicket w
            JOIN delivery d ON d.id=w.delivery_id
            JOIN innings i ON i.id=d.innings_id
            JOIN match m ON m.id=i.match_id
            WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
              AND i.innings_number = :inn
              AND w.kind NOT IN ('retired hurt','retired not out')
              {(' AND ' + live_where) if live_where else ''}""",
            {**params, "inn": inn},
        )
        bucket = await db.q(
            f"""SELECT
                SUM({prefix}_runs_sum)     AS runs,
                SUM({prefix}_count)        AS count_inn,
                SUM({prefix}_legal_balls)  AS balls,
                SUM({prefix}_fours)        AS fours,
                SUM({prefix}_sixes)        AS sixes,
                SUM({prefix}_dots)         AS dots,
                SUM({prefix}_wickets_lost) AS wkts
            FROM bucketbaselinebatting
            WHERE team = '{LEAGUE_TEAM}'
              {(' AND ' + bucket_where) if bucket_where else ''}""",
            params,
        )
        l = dict(live[0]) if live else {}
        b = dict(bucket[0]) if bucket else {}
        l_wkts = wkts_live[0]["wkts"] if wkts_live else 0
        passed = True
        for k in ("runs", "count_inn", "balls", "fours", "sixes", "dots"):
            if (l.get(k) or 0) != (b.get(k) or 0):
                passed = False
                print(f"  {FAIL}: {prefix}.{k} live={l.get(k)} bucket={b.get(k)}")
        if l_wkts != (b.get("wkts") or 0):
            passed = False
            print(f"  {FAIL}: {prefix}.wickets_lost live={l_wkts} bucket={b.get('wkts')}")
        if passed:
            print(f"  {PASS}: {prefix} runs={b['runs']} balls={b['balls']} wkts={b['wkts']}")
        else:
            ok = False
    return ok


async def check_bowling_by_inning_roundtrip(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """bucketbaselinebowling first_inn_* / second_inn_* must match live
    SQL byte-identical at the league row level. Phase D."""
    print(f"=== /teams bowling by-inning: {scope_desc} ===")
    ok = True
    for inn in (0, 1):
        prefix = "first_inn" if inn == 0 else "second_inn"
        live = await db.q(
            f"""SELECT
                SUM(CASE WHEN i.innings_number = :inn THEN d.runs_total ELSE 0 END) AS runs,
                COUNT(DISTINCT CASE WHEN i.innings_number = :inn THEN i.id END) AS count_inn,
                SUM(CASE WHEN i.innings_number = :inn AND d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_batter=4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END) AS fours,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_batter=6 THEN 1 ELSE 0 END) AS sixes,
                SUM(CASE WHEN i.innings_number = :inn AND d.runs_total=0 AND d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS dots
            FROM delivery d
            JOIN innings i ON i.id=d.innings_id
            JOIN match m ON m.id=i.match_id
            WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}""",
            {**params, "inn": inn},
        )
        wkts_live = await db.q(
            f"""SELECT COUNT(*) AS wkts
            FROM wicket w
            JOIN delivery d ON d.id=w.delivery_id
            JOIN innings i ON i.id=d.innings_id
            JOIN match m ON m.id=i.match_id
            WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
              AND i.innings_number = :inn
              AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field','retired not out')
              {(' AND ' + live_where) if live_where else ''}""",
            {**params, "inn": inn},
        )
        bucket = await db.q(
            f"""SELECT
                SUM({prefix}_runs_conceded)   AS runs,
                SUM({prefix}_count)           AS count_inn,
                SUM({prefix}_balls)           AS balls,
                SUM({prefix}_fours_conceded)  AS fours,
                SUM({prefix}_sixes_conceded)  AS sixes,
                SUM({prefix}_dots)            AS dots,
                SUM({prefix}_wickets)         AS wkts
            FROM bucketbaselinebowling
            WHERE team = '{LEAGUE_TEAM}'
              {(' AND ' + bucket_where) if bucket_where else ''}""",
            params,
        )
        l = dict(live[0]) if live else {}
        b = dict(bucket[0]) if bucket else {}
        l_wkts = wkts_live[0]["wkts"] if wkts_live else 0
        passed = True
        for k in ("runs", "count_inn", "balls", "fours", "sixes", "dots"):
            if (l.get(k) or 0) != (b.get(k) or 0):
                passed = False
                print(f"  {FAIL}: {prefix}.{k} live={l.get(k)} bucket={b.get(k)}")
        if l_wkts != (b.get("wkts") or 0):
            passed = False
            print(f"  {FAIL}: {prefix}.wickets live={l_wkts} bucket={b.get('wkts')}")
        if passed:
            print(f"  {PASS}: {prefix} runs={b['runs']} balls={b['balls']} wkts={b['wkts']}")
        else:
            ok = False
    return ok


async def check_fielders_leaders_roundtrip(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """playerscopestats-driven fielders-leaders aggregates — must match
    live SQL byte-identical (top by total dismissals + top by run outs
    + top by keeper dismissals) at the given scope. Phase A part 4 of
    spec-series-precompute-followup.md.

    Live SQL aggregates over fieldingcredit; bucket aggregates over
    SUM(catches) + SUM(stumpings) + SUM(runouts) (and SUM(catches_as_keeper)
    + SUM(stumpings) for keeper). The equivalence relies on
    populate_player_scope_stats writing those columns from the SAME
    fieldingcredit rows the live SQL would scan.
    """
    print(f"=== /series fielders-leaders: {scope_desc} ===")
    ok = True

    # by_dismissals — top fielder by total dismissals (catches+stumpings+runouts).
    # Convention 3: catches includes caught_and_bowled.
    live = await db.q(
        f"""SELECT fc.fielder_id AS person_id,
                   SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) AS catches,
                   SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
                   SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
                   COUNT(*) AS total
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE fc.fielder_id IS NOT NULL
              AND i.super_over = 0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}
            GROUP BY fc.fielder_id
            ORDER BY total DESC, fc.fielder_id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT person_id,
                   SUM(catches) AS catches,
                   SUM(stumpings) AS stumpings,
                   SUM(runouts) AS run_outs,
                   SUM(catches) + SUM(stumpings) + SUM(runouts) AS total
            FROM playerscopestats
            {(' WHERE ' + bucket_where) if bucket_where else ''}
            GROUP BY person_id
            HAVING total > 0
            ORDER BY total DESC, person_id ASC LIMIT 1""",
        params,
    )
    if (live and bucket
            and live[0]["person_id"] == bucket[0]["person_id"]
            and live[0]["total"] == bucket[0]["total"]
            and live[0]["catches"] == bucket[0]["catches"]
            and live[0]["stumpings"] == bucket[0]["stumpings"]
            and live[0]["run_outs"] == bucket[0]["run_outs"]):
        print(f"  PASS: by_dismissals person_id={live[0]['person_id']}, "
              f"total={live[0]['total']} (c={live[0]['catches']}, s={live[0]['stumpings']}, ro={live[0]['run_outs']})")
    else:
        print(f"  FAIL by_dismissals: live={live[0] if live else None} bucket={bucket[0] if bucket else None}")
        ok = False

    # by_run_outs — top fielder by run-outs.
    live = await db.q(
        f"""SELECT fc.fielder_id AS person_id,
                   SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE fc.fielder_id IS NOT NULL
              AND i.super_over = 0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}
            GROUP BY fc.fielder_id
            HAVING run_outs > 0
            ORDER BY run_outs DESC, fc.fielder_id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT person_id, SUM(runouts) AS run_outs
            FROM playerscopestats
            {(' WHERE ' + bucket_where) if bucket_where else ''}
            GROUP BY person_id
            HAVING run_outs > 0
            ORDER BY run_outs DESC, person_id ASC LIMIT 1""",
        params,
    )
    if (live and bucket
            and live[0]["person_id"] == bucket[0]["person_id"]
            and live[0]["run_outs"] == bucket[0]["run_outs"]):
        print(f"  PASS: by_run_outs person_id={live[0]['person_id']}, run_outs={live[0]['run_outs']}")
    else:
        print(f"  FAIL by_run_outs: live={live[0] if live else None} bucket={bucket[0] if bucket else None}")
        ok = False

    # by_keeper_dismissals — keeper catches_as_keeper + stumpings.
    # Equivalence: live joins fieldingcredit to keeperassignment with
    # fc.fielder_id = ka.keeper_id; bucket reads catches_as_keeper which
    # populate writes from the same join. Keepers don't bowl so catches
    # vs caught+c&b is identical here.
    live = await db.q(
        f"""SELECT ka.keeper_id AS person_id,
                   SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) AS catches,
                   SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
                   SUM(CASE WHEN fc.kind IN ('caught','stumped','caught_and_bowled') THEN 1 ELSE 0 END) AS total
            FROM keeperassignment ka
            JOIN innings i ON i.id = ka.innings_id
            JOIN match m ON m.id = i.match_id
            JOIN delivery d ON d.innings_id = i.id
            JOIN fieldingcredit fc ON fc.delivery_id = d.id AND fc.fielder_id = ka.keeper_id
            WHERE ka.keeper_id IS NOT NULL
              AND i.super_over = 0 AND m.match_type IN ('T20','IT20')
              {(' AND ' + live_where) if live_where else ''}
            GROUP BY ka.keeper_id
            HAVING total > 0
            ORDER BY total DESC, ka.keeper_id ASC LIMIT 1""",
        params,
    )
    bucket = await db.q(
        f"""SELECT person_id,
                   SUM(catches_as_keeper) AS catches,
                   SUM(stumpings) AS stumpings,
                   SUM(catches_as_keeper) + SUM(stumpings) AS total
            FROM playerscopestats
            {(' WHERE ' + bucket_where) if bucket_where else ''}
            GROUP BY person_id
            HAVING total > 0
            ORDER BY total DESC, person_id ASC LIMIT 1""",
        params,
    )
    if (live and bucket
            and live[0]["person_id"] == bucket[0]["person_id"]
            and live[0]["total"] == bucket[0]["total"]):
        print(f"  PASS: by_keeper person_id={live[0]['person_id']}, total={live[0]['total']}")
    else:
        print(f"  FAIL by_keeper: live={live[0] if live else None} bucket={bucket[0] if bucket else None}")
        ok = False

    return ok


async def check_partnership_top_roundtrip(
    db, scope_desc: str, live_where: str, bucket_where: str, params: dict,
) -> bool:
    """bucketbaselinepartnershiptop-derived top-K per (cell, wicket) —
    must match live SQL byte-identical at the given scope. Phase C of
    spec-series-precompute-followup.md.

    The scope here is a SINGLE cell — the precompute stores top-K per
    cell, so cross-cell merging happens at request time. Roundtrip test
    locks the per-cell layer.
    """
    print(f"=== /series partnerships top-by-wicket: {scope_desc} ===")
    ok = True
    for wn in (1, 5, 10):
        live = await db.q(
            f"""WITH ranked AS (
                SELECT p.id AS partnership_id, p.partnership_runs AS runs,
                       p.partnership_balls AS balls,
                       ROW_NUMBER() OVER (
                           ORDER BY p.partnership_runs DESC,
                                    p.partnership_balls ASC,
                                    p.id ASC
                       ) AS rnk
                FROM partnership p
                JOIN innings i ON i.id = p.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE i.super_over = 0 AND m.match_type IN ('T20','IT20')
                  AND p.wicket_number IS NOT NULL AND p.wicket_number = :wn
                  {(' AND ' + live_where) if live_where else ''}
            )
            SELECT partnership_id, runs, balls FROM ranked WHERE rnk <= 10
            ORDER BY rnk""",
            {**params, "wn": wn},
        )
        bucket = await db.q(
            f"""SELECT partnership_id, runs, balls
                FROM bucketbaselinepartnershiptop
                WHERE wicket_number = :wn
                  {(' AND ' + bucket_where) if bucket_where else ''}
                ORDER BY rank""",
            {**params, "wn": wn},
        )
        l = [dict(r) for r in live]
        b = [dict(r) for r in bucket]
        if l == b:
            print(f"  {PASS}: wicket={wn} top-{len(l)}")
        else:
            print(f"  {FAIL}: wicket={wn}")
            print(f"    live  ({len(l)} rows): {l[:3]}...")
            print(f"    bucket({len(b)} rows): {b[:3]}...")
            ok = False
    return ok


async def check_cross_cell_isolation(db) -> bool:
    """populate_incremental on cell A leaves cell B untouched."""
    print("=== Cross-cell isolation ===")

    # Two distinct small cells.
    rows = await db.q(
        """
        SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament, m.season, COUNT(*) AS c
        FROM match m
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        HAVING c BETWEEN 4 AND 10
        ORDER BY c DESC
        LIMIT 2
        """
    )
    if len(rows) < 2:
        print(f"  {FAIL}: need 2 cells, got {len(rows)}")
        return False
    cell_a = rows[0]
    cell_b = rows[1]

    # Snapshot cell B baseline rows.
    snapshot_b = await db.q(
        "SELECT * FROM bucketbaselinebatting "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s ORDER BY team",
        {"g": cell_b["gender"], "tt": cell_b["team_type"], "t": cell_b["tournament"], "s": cell_b["season"]},
    )
    snapshot_b = [{k: v for k, v in r.items() if k != "id"} for r in snapshot_b]

    # Run incremental on cell A's matches.
    a_ids = [r["id"] for r in await db.q(
        "SELECT id FROM match WHERE gender=:g AND team_type=:tt AND COALESCE(event_name, '')=:t AND season=:s",
        {"g": cell_a["gender"], "tt": cell_a["team_type"], "t": cell_a["tournament"], "s": cell_a["season"]},
    )]
    await populate_incremental(db, a_ids)

    # Re-snapshot cell B; should be unchanged.
    after_b = await db.q(
        "SELECT * FROM bucketbaselinebatting "
        "WHERE gender=:g AND team_type=:tt AND tournament=:t AND season=:s ORDER BY team",
        {"g": cell_b["gender"], "tt": cell_b["team_type"], "t": cell_b["tournament"], "s": cell_b["season"]},
    )
    after_b = [{k: v for k, v in r.items() if k != "id"} for r in after_b]

    if snapshot_b == after_b:
        print(f"  {PASS}: cell B untouched ({len(snapshot_b)} rows)")
        return True
    print(f"  {FAIL}: cell B changed after running incremental on cell A")
    return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    parser.add_argument("--populate", action="store_true",
                        help="Run populate_full first (use against fresh /tmp copy)")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{args.db}")
    await db.q("PRAGMA journal_mode = WAL")

    if args.populate:
        await populate_full(db)

    sample_cells = [
        ("male", "club", "Indian Premier League", "2024", "Royal Challengers Bengaluru"),
        ("male", "club", "Indian Premier League", "2023", "Mumbai Indians"),
        ("male", "international", "ICC Men's T20 World Cup", "2024", "Australia"),
    ]
    sample_league_cells = [
        ("male", "club", "Indian Premier League", "2024"),
        ("male", "international", "ICC Men's T20 World Cup", "2024"),
    ]

    all_ok = True
    all_ok &= await check_pool_conservation(db)
    for cell in sample_cells:
        all_ok &= await check_per_team_cell(db, *cell)
        all_ok &= await check_identity_cols(db, *cell)
    for cell in sample_league_cells:
        all_ok &= await check_league_cell(db, *cell)
    # Phase B — highest_team_total roundtrip at 5 scopes.
    ht_scopes = [
        ("all-cricket", "", "", {}),
        ("men's club, all-time",
         "m.gender = :g AND m.team_type = :tt",
         "gender = :g AND team_type = :tt",
         {"g": "male", "tt": "club"}),
        ("women's international, all-time",
         "m.gender = :g AND m.team_type = :tt",
         "gender = :g AND team_type = :tt",
         {"g": "female", "tt": "international"}),
        ("IPL 2023",
         "m.event_name = :t AND m.season = :s",
         "tournament = :t AND season = :s",
         {"t": "Indian Premier League", "s": "2023"}),
        ("Men's International 2024",
         "m.gender = :g AND m.team_type = :tt AND m.season = :s",
         "gender = :g AND team_type = :tt AND season = :s",
         {"g": "male", "tt": "international", "s": "2024"}),
    ]
    for scope in ht_scopes:
        all_ok &= await check_highest_team_total(db, *scope)

    # Phase A — top scorer / wicket-taker roundtrip at 5 scopes.
    for scope in ht_scopes:
        all_ok &= await check_top_scorer_wicket_taker(db, *scope)

    # Phase A pt 4 — fielders-leaders roundtrip at 5 scopes.
    for scope in ht_scopes:
        all_ok &= await check_fielders_leaders_roundtrip(db, *scope)

    # Phase D — per-team inning splits in bucketbaselinebatting +
    # bucketbaselinebowling. Checked at league row level across 5 scopes.
    for scope in ht_scopes:
        all_ok &= await check_batting_by_inning_roundtrip(db, *scope)
        all_ok &= await check_bowling_by_inning_roundtrip(db, *scope)

    # Phase C — top partnerships per wicket roundtrip at 3 single-cell
    # scopes (precompute is per-cell; multi-cell merging is endpoint-side).
    pt_scopes = [
        ("IPL 2024 (male club)",
         "m.event_name = :t AND m.season = :s AND m.gender = :g AND m.team_type = :tt",
         "tournament = :t AND season = :s AND gender = :g AND team_type = :tt",
         {"t": "Indian Premier League", "s": "2024", "g": "male", "tt": "club"}),
        ("BBL 2023/24 (male club)",
         "m.event_name = :t AND m.season = :s AND m.gender = :g AND m.team_type = :tt",
         "tournament = :t AND season = :s AND gender = :g AND team_type = :tt",
         {"t": "Big Bash League", "s": "2023/24", "g": "male", "tt": "club"}),
        ("WBBL 2023/24 (female club)",
         "m.event_name = :t AND m.season = :s AND m.gender = :g AND m.team_type = :tt",
         "tournament = :t AND season = :s AND gender = :g AND team_type = :tt",
         {"t": "Women's Big Bash League", "s": "2023/24", "g": "female", "tt": "club"}),
    ]
    for scope in pt_scopes:
        all_ok &= await check_partnership_top_roundtrip(db, *scope)

    all_ok &= await check_incremental_roundtrip(db)
    all_ok &= await check_cross_cell_isolation(db)

    print()
    print("ALL PASS" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
