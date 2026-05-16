"""Populate the records-page precomputed aggregate tables.

Three tables back the /series/records + /teams/{team}/records endpoints:

  - innings_total: per-innings totals (runs, wickets, sixes, fours,
    super_over) — feeds highest/lowest team totals + most-sixes-by-team.
  - innings_batter_perf: per-(batter, innings) perf — feeds best-
    individual-batting.
  - match_bowler_perf: per-(bowler, match) perf — feeds best-bowling-
    figures.

Without these, every records request runs 5 full delivery-table scans
(3M rows). With them, each record list is a single read on the small
aggregate table joined to match for scope filtering. See
internal_docs/spec-records-precompute.md for the full design.

Modes:
  Full rebuild (standalone):
    uv run python scripts/populate_records_aggregates.py
    Drops all three table contents and rebuilds from every non-super-
    over innings (+ super_over=1 retained for total/sixes accounting).

  Incremental (from update_recent.py):
    populate_incremental(db, new_match_ids)
    Rescans the three tables for the given matches only.

Called automatically by import_data.py (full) and update_recent.py
(incremental) after the bucket_baseline populate call.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import (
    Person, Match, Innings, Delivery, Wicket, FieldingCredit,
    InningsTotal, InningsBatterPerf, MatchBowlerPerf, MatchFielderPerf,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")


async def _ensure_tables(db, incremental: bool = False):
    """Register all tables with deebase so FK references resolve.

    In incremental mode, skip index creation (already there).
    """
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)

    # InningsTotal: PK on innings_id. Sort indexes for the records SQL:
    #   total_runs DESC (highest), total_runs ASC + wkts>=10 (lowest
    #   all-out), total_sixes DESC (most sixes per innings).
    it_idx = {} if incremental else {"indexes": ["total_runs", "total_sixes"]}
    await db.create(
        InningsTotal, pk="innings_id", if_not_exists=True, **it_idx,
    )

    # InningsBatterPerf: composite PK (batter_id, innings_id). Need a
    # secondary index on innings_id alone for join-from-match scope
    # filters, and an index on runs DESC for the unfiltered best-
    # batting query.
    ib_idx = {} if incremental else {
        "indexes": ["innings_id", "runs"],
    }
    await db.create(
        InningsBatterPerf, pk=["batter_id", "innings_id"],
        if_not_exists=True, **ib_idx,
    )

    # MatchBowlerPerf: composite PK (bowler_id, match_id). Need a
    # secondary index on match_id alone for join-from-match scope
    # filters, and a composite on (wickets, runs) for ORDER BY
    # wickets DESC, runs ASC LIMIT N.
    mb_idx = {} if incremental else {
        "indexes": ["match_id", ("wickets", "runs")],
    }
    await db.create(
        MatchBowlerPerf, pk=["bowler_id", "match_id"],
        if_not_exists=True, **mb_idx,
    )

    # MatchFielderPerf: composite PK (fielder_id, match_id). Secondary
    # index on match_id alone for join-from-match scope filters. Plus
    # standalone indexes on the three count columns + dismissals
    # (denormalized sum) for the per-record-list ORDER BY clauses.
    mf_idx = {} if incremental else {
        "indexes": ["match_id", "catches", "stumpings", "dismissals"],
    }
    await db.create(
        MatchFielderPerf, pk=["fielder_id", "match_id"],
        if_not_exists=True, **mf_idx,
    )


# Wicket kinds excluded from BOWLER wicket-credit (live SQL uses same
# predicate in best_bowling_figures). The live SQL for lowest_all_out
# uses a different exclusion (retired hurt + retired not out) — keep
# both predicates faithful per their respective semantics.
BOWLER_WICKET_EXCLUDE = "('run out', 'retired hurt', 'retired out', 'obstructing the field')"
ALL_OUT_WICKET_EXCLUDE = "('retired hurt', 'retired not out')"


async def _populate_innings_total(db, scope_clause: str = ""):
    """Populate innings_total. scope_clause is `''` for full, or
    `WHERE i.match_id IN (...)` for incremental."""
    # Aggregate sixes/fours/runs + denormalize super_over per innings,
    # then JOIN a second aggregate for wickets that fell. Both are
    # delivery scans but bounded by scope_clause when incremental.
    where_i = scope_clause.replace("i.", "i.") if scope_clause else ""
    where_d = scope_clause.replace("i.match_id", "d.match_id_via_innings")
    # Simpler: do it in one SQL using a CTE.
    join = ""
    if scope_clause:
        # innings_id must be in the scoped set; gather match ids → innings ids first
        inn_ids = await db.q(
            f"SELECT id FROM innings WHERE {scope_clause.replace('i.', '')}"
        )
        ids = [r["id"] for r in inn_ids]
        if not ids:
            return 0
        id_list = ",".join(str(i) for i in ids)
        scope_d = f"AND d.innings_id IN ({id_list})"
        # Inside the wicket subquery the delivery alias is `d2`.
        scope_w = f"AND d2.innings_id IN ({id_list})"
        scope_i = f"AND i.id IN ({id_list})"
    else:
        scope_d = scope_w = scope_i = ""

    sql = f"""
        INSERT INTO inningstotal (innings_id, total_runs, total_wkts,
                                  total_sixes, total_fours, super_over)
        SELECT
            d.innings_id,
            SUM(d.runs_total) AS total_runs,
            COALESCE(wk.wkts, 0) AS total_wkts,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS total_sixes,
            SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS total_fours,
            i.super_over AS super_over
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        LEFT JOIN (
            SELECT d2.innings_id, COUNT(*) AS wkts
            FROM wicket w
            JOIN delivery d2 ON d2.id = w.delivery_id
            WHERE w.kind NOT IN {ALL_OUT_WICKET_EXCLUDE}
              {scope_w}
            GROUP BY d2.innings_id
        ) wk ON wk.innings_id = d.innings_id
        WHERE 1=1 {scope_d}
        GROUP BY d.innings_id, i.super_over, wk.wkts
    """
    async with db._engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(sql))
        return result.rowcount


async def _populate_innings_batter_perf(db, scope_clause: str = ""):
    """Per-(batter, innings) perf. Live SQL filters super_over=0 in the
    records query, but we store everything and let the read filter."""
    if scope_clause:
        inn_ids = await db.q(
            f"SELECT id FROM innings WHERE {scope_clause.replace('i.', '')}"
        )
        ids = [r["id"] for r in inn_ids]
        if not ids:
            return 0
        id_list = ",".join(str(i) for i in ids)
        scope_d = f"AND d.innings_id IN ({id_list})"
    else:
        scope_d = ""

    sql = f"""
        INSERT INTO inningsbatterperf
            (batter_id, innings_id, runs, balls, fours, sixes, not_out)
        SELECT
            d.batter_id,
            d.innings_id,
            SUM(d.runs_batter) AS runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls,
            SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) AS fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
            CASE WHEN EXISTS (
                SELECT 1 FROM wicket w
                JOIN delivery d2 ON d2.id = w.delivery_id
                WHERE d2.innings_id = d.innings_id
                  AND w.player_out_id = d.batter_id
            ) THEN 0 ELSE 1 END AS not_out
        FROM delivery d
        WHERE d.batter_id IS NOT NULL {scope_d}
        GROUP BY d.batter_id, d.innings_id
    """
    async with db._engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(sql))
        return result.rowcount


async def _populate_match_bowler_perf(db, scope_clause: str = ""):
    """Per-(bowler, match) perf — wickets / runs / balls."""
    if scope_clause:
        m_ids = await db.q(
            f"SELECT DISTINCT i.match_id FROM innings i WHERE {scope_clause.replace('i.', '')}"
        )
        ids = [r["match_id"] for r in m_ids]
        if not ids:
            return 0
        id_list = ",".join(str(i) for i in ids)
        scope_m = f"AND m.id IN ({id_list})"
    else:
        scope_m = ""

    sql = f"""
        INSERT INTO matchbowlerperf
            (bowler_id, match_id, wickets, runs, balls)
        SELECT
            d.bowler_id,
            m.id AS match_id,
            SUM(CASE WHEN w.id IS NOT NULL
                          AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
                     THEN 1 ELSE 0 END) AS wickets,
            SUM(d.runs_total) AS runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls
        FROM delivery d
        LEFT JOIN wicket w ON w.delivery_id = d.id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND d.bowler_id IS NOT NULL
          {scope_m}
        GROUP BY d.bowler_id, m.id
    """
    async with db._engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(sql))
        return result.rowcount


async def _populate_match_fielder_perf(db, scope_clause: str = ""):
    """Per-(fielder, match) fielding tallies — feeds /fielders/{id}/records.

    Source: fielding_credit table (already populated by
    populate_fielding_credits). Catches INCLUDE caught_and_bowled per
    Convention 3. Volume framing — no is_substitute filter.
    """
    if scope_clause:
        # scope_clause is `i.match_id IN (...)` — translate to match ids.
        m_ids = await db.q(
            f"SELECT DISTINCT i.match_id FROM innings i WHERE {scope_clause.replace('i.', '')}"
        )
        ids = [r["match_id"] for r in m_ids]
        if not ids:
            return 0
        id_list = ",".join(str(i) for i in ids)
        scope_m = f"AND m.id IN ({id_list})"
    else:
        scope_m = ""

    # fc.delivery_id → delivery → innings → match. fc has no direct
    # match_id; thread through delivery.
    sql = f"""
        INSERT INTO matchfielderperf
            (fielder_id, match_id, catches, stumpings, run_outs, dismissals)
        SELECT
            fc.fielder_id,
            m.id AS match_id,
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) AS catches,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
            COUNT(*) AS dismissals
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id IS NOT NULL
          {scope_m}
        GROUP BY fc.fielder_id, m.id
    """
    async with db._engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(sql))
        return result.rowcount


async def populate_full(db):
    """Truncate and rebuild all three records aggregate tables."""
    print("Populating records aggregates (full rebuild)…")
    start = time.time()

    # DROP TABLE before re-create — DELETE FROM would leave the old
    # indexes, then _ensure_tables (incremental=False) would try to
    # CREATE INDEX on them again and fail. DROP TABLE wipes both rows
    # and indexes; the indexes get recreated cleanly below.
    for tbl in ("inningstotal", "inningsbatterperf", "matchbowlerperf",
                "matchfielderperf"):
        await db.q(f"DROP TABLE IF EXISTS {tbl}")

    await _ensure_tables(db, incremental=False)

    t0 = time.time()
    n = await _populate_innings_total(db)
    print(f"  innings_total: {n} rows in {time.time()-t0:.1f}s")

    t0 = time.time()
    n = await _populate_innings_batter_perf(db)
    print(f"  innings_batter_perf: {n} rows in {time.time()-t0:.1f}s")

    t0 = time.time()
    n = await _populate_match_bowler_perf(db)
    print(f"  match_bowler_perf: {n} rows in {time.time()-t0:.1f}s")

    t0 = time.time()
    n = await _populate_match_fielder_perf(db)
    print(f"  match_fielder_perf: {n} rows in {time.time()-t0:.1f}s")

    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s")


async def populate_incremental(db, new_match_ids: list[int]):
    """Rescan rows for the given matches. Idempotent: delete + reinsert
    rows whose match_id is in new_match_ids.

    Called from update_recent.py after import + the dependent populates
    (fielding_credits / keeper_assignments / partnerships / bucket_baseline).
    """
    if not new_match_ids:
        return

    await _ensure_tables(db, incremental=True)

    match_id_list = ",".join(str(m) for m in new_match_ids)

    # Innings ids touched by these matches — drives both innings_total
    # and innings_batter_perf scope.
    inn_rows = await db.q(
        f"SELECT id FROM innings WHERE match_id IN ({match_id_list})"
    )
    inn_ids = [r["id"] for r in inn_rows]
    if inn_ids:
        inn_list = ",".join(str(i) for i in inn_ids)
        await db.q(f"DELETE FROM inningstotal WHERE innings_id IN ({inn_list})")
        await db.q(f"DELETE FROM inningsbatterperf WHERE innings_id IN ({inn_list})")

    # match_bowler_perf + match_fielder_perf are per-match grain.
    await db.q(f"DELETE FROM matchbowlerperf WHERE match_id IN ({match_id_list})")
    await db.q(f"DELETE FROM matchfielderperf WHERE match_id IN ({match_id_list})")

    scope = f"i.match_id IN ({match_id_list})"
    await _populate_innings_total(db, scope)
    await _populate_innings_batter_perf(db, scope)
    await _populate_match_bowler_perf(db, scope)
    await _populate_match_fielder_perf(db, scope)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PATH, help="Path to cricket.db")
    args = parser.parse_args()

    print(f"DB: {args.db}")
    db = Database(f"sqlite+aiosqlite:///{args.db}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
