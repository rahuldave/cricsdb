"""Populate the bucket_baseline_* tables — denormalized per-cell aggregates.

See `internal_docs/spec-team-bucket-baseline.md` for the full spec.

Granularity: one row per (gender, team_type, tournament, season, team).
team='__league__' rows are pool-weighted league baselines aggregating the
whole cell; per-team rows mirror the team-specific endpoint output.
SUM-then-divide over cells at query time gives byte-identical numbers
to the live aggregator.

Six tables — match, batting, bowling, fielding, phase, partnership.
Total ~34K rows on the current DB.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_bucket_baseline.py

  Incremental (from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes only the cells touched by new matches, plus their
    per-team rows. Implementation: enumerate affected
    (g, tt, t, s) cells, DELETE matching rows, recompute via the
    same SQL as full but with a cell-level WHERE filter.

Phase boundaries match `api/routers/teams.py`:
    powerplay = over 0-5, middle = 6-14, death = 15-19.

Bowler `wickets` excludes run out / retired hurt / retired out /
obstructing the field (matches `api/routers/bowling.py`).

NULL tournaments stored as empty string (cricsheet has bilateral
matches with no event_name; SQL is cleaner with '' than NULL).
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
    Person, Match, MatchPlayer, Innings, Delivery, Wicket,
    FieldingCredit, KeeperAssignment, Partnership, PlayerScopeStats,
    BucketBaselineMatch, BucketBaselineBatting, BucketBaselineBowling,
    BucketBaselineFielding, BucketBaselinePhase, BucketBaselinePartnership,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

LEAGUE_TEAM = "__league__"
BOWLER_WICKET_EXCLUDED = (
    "run out", "retired hurt", "retired out", "obstructing the field",
)


# ─── Schema setup ───────────────────────────────────────────────────────

BUCKET_TABLES = [
    BucketBaselineMatch, BucketBaselineBatting, BucketBaselineBowling,
    BucketBaselineFielding, BucketBaselinePhase, BucketBaselinePartnership,
]


async def _ensure_tables(db, incremental: bool = False):
    """Register tables with deebase + create indexes idempotently.

    Indexes via raw `CREATE INDEX IF NOT EXISTS` since deebase's
    `indexes=` arg errors on re-create."""
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)
    await db.create(KeeperAssignment, pk="id", if_not_exists=True)
    await db.create(Partnership, pk="id", if_not_exists=True)
    await db.create(PlayerScopeStats,
                    pk=["person_id", "scope_key"], if_not_exists=True)

    await db.create(BucketBaselineMatch,        pk="id", if_not_exists=True)
    await db.create(BucketBaselineBatting,      pk="id", if_not_exists=True)
    await db.create(BucketBaselineBowling,      pk="id", if_not_exists=True)
    await db.create(BucketBaselineFielding,     pk="id", if_not_exists=True)
    await db.create(BucketBaselinePhase,        pk="id", if_not_exists=True)
    await db.create(BucketBaselinePartnership,  pk="id", if_not_exists=True)

    # Indexes — covering the common lookup pattern.
    common = "gender, team_type, tournament, season, team"
    for table, extra in [
        ("bucketbaselinematch", ""),
        ("bucketbaselinebatting", ""),
        ("bucketbaselinebowling", ""),
        ("bucketbaselinefielding", ""),
        ("bucketbaselinephase", ", phase, side"),
        ("bucketbaselinepartnership", ", wicket_number"),
    ]:
        idx_name = f"ix_{table}_lookup"
        await db.q(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({common}{extra})")


# ─── Cell-filter helpers ────────────────────────────────────────────────

def _cell_filter_clause(cells: list[tuple] | None, m_alias: str = "m") -> tuple[str, dict]:
    """Optionally restrict to a specific list of (g, tt, t, s) cells.

    Returns ('', {}) for full-rebuild mode (no restriction). Otherwise
    builds a `(g, tt, t, s) IN ((...), (...), ...)` filter as bind
    parameters; SQLite's row-value IN syntax handles this efficiently.
    """
    if not cells:
        return "", {}
    parts: list[str] = []
    params: dict = {}
    for i, (g, tt, t, s) in enumerate(cells):
        params[f"cf_g_{i}"]  = g
        params[f"cf_tt_{i}"] = tt
        params[f"cf_t_{i}"]  = t
        params[f"cf_s_{i}"]  = s
        parts.append(
            f"({m_alias}.gender = :cf_g_{i} AND {m_alias}.team_type = :cf_tt_{i} "
            f"AND COALESCE({m_alias}.event_name, '') = :cf_t_{i} AND {m_alias}.season = :cf_s_{i})"
        )
    return " AND (" + " OR ".join(parts) + ")", params


# ─── Per-table populate routines ────────────────────────────────────────
#
# Each routine writes BOTH the team='__league__' row (cell-wide) AND the
# per-team rows for that cell. SQL is one INSERT … SELECT … GROUP BY per
# table per kind (league vs per-team). Cell filter is optional —
# applied for incremental.


async def _populate_match(db, cells=None):
    cf, cfp = _cell_filter_clause(cells, "m")

    # League rows: cell-wide match-level totals.
    await db.q(
        f"""
        INSERT INTO bucketbaselinematch (
            gender, team_type, tournament, season, team,
            matches, decided, ties, no_results, toss_decided,
            bat_first_wins, field_first_wins
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            COUNT(*) AS matches,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END) AS decided,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_results,
            SUM(CASE WHEN m.toss_winner IS NOT NULL THEN 1 ELSE 0 END) AS toss_decided,
            SUM(CASE WHEN m.toss_decision = 'bat'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'field'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) AS bat_first_wins,
            SUM(CASE WHEN m.toss_decision = 'field'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'bat'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) AS field_first_wins
        FROM match m
        WHERE 1=1 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        """,
        cfp,
    )

    # Per-team rows: team's match record (won/lost from its perspective).
    # JOIN matchplayer to get teams per match. Each match has 2 teams
    # → 2 rows per match here; the GROUP BY collapses repeated teams
    # within the cell.
    await db.q(
        f"""
        INSERT INTO bucketbaselinematch (
            gender, team_type, tournament, season, team,
            matches, decided, ties, no_results, toss_decided,
            bat_first_wins, field_first_wins
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mp.team,
            COUNT(DISTINCT m.id) AS matches,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END) AS decided,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_results,
            SUM(CASE WHEN m.toss_winner IS NOT NULL THEN 1 ELSE 0 END) AS toss_decided,
            -- For per-team rows, "bat_first_wins" reads as "this team won
            -- after batting first" (NOT a league-level pool). Same shape
            -- column to keep schema uniform; query side picks which
            -- interpretation applies.
            SUM(CASE WHEN m.toss_winner = mp.team AND m.toss_decision = 'bat'
                     AND m.outcome_winner = mp.team THEN 1
                     WHEN m.toss_winner != mp.team AND m.toss_decision = 'field'
                     AND m.outcome_winner = mp.team THEN 1
                     ELSE 0 END) AS bat_first_wins,
            SUM(CASE WHEN m.toss_winner = mp.team AND m.toss_decision = 'field'
                     AND m.outcome_winner = mp.team THEN 1
                     WHEN m.toss_winner != mp.team AND m.toss_decision = 'bat'
                     AND m.outcome_winner = mp.team THEN 1
                     ELSE 0 END) AS field_first_wins
        FROM match m
        JOIN (SELECT DISTINCT match_id, team FROM matchplayer) mp
          ON mp.match_id = m.id
        WHERE 1=1 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mp.team
        """,
        cfp,
    )


async def _populate_batting(db, cells=None):
    cf, cfp = _cell_filter_clause(cells, "m")

    # League rows — every batting innings in the cell.
    await db.q(
        f"""
        WITH inn AS (
            SELECT
                m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                m.season, i.team AS innings_team, i.id AS innings_id,
                i.innings_number,
                SUM(d.runs_total) AS runs,
                SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
                SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours,
                SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
                SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team, i.id, i.innings_number
        )
        INSERT INTO bucketbaselinebatting (
            gender, team_type, tournament, season, team,
            innings_batted, total_runs, legal_balls, fours, sixes, dots,
            first_inn_runs_sum, first_inn_count,
            second_inn_runs_sum, second_inn_count,
            highest_inn_runs
        )
        SELECT
            gender, team_type, tournament, season, '{LEAGUE_TEAM}',
            COUNT(*) AS innings_batted,
            SUM(runs) AS total_runs,
            SUM(legal_balls) AS legal_balls,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes,
            SUM(dots) AS dots,
            SUM(CASE WHEN innings_number = 0 THEN runs ELSE 0 END) AS first_inn_runs_sum,
            SUM(CASE WHEN innings_number = 0 THEN 1 ELSE 0 END) AS first_inn_count,
            SUM(CASE WHEN innings_number = 1 THEN runs ELSE 0 END) AS second_inn_runs_sum,
            SUM(CASE WHEN innings_number = 1 THEN 1 ELSE 0 END) AS second_inn_count,
            COALESCE(MAX(runs), 0) AS highest_inn_runs
        FROM inn
        GROUP BY gender, team_type, tournament, season
        """,
        cfp,
    )

    # Per-team rows — innings where i.team = team.
    await db.q(
        f"""
        WITH inn AS (
            SELECT
                m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                m.season, i.team AS team, i.id AS innings_id,
                i.innings_number,
                SUM(d.runs_total) AS runs,
                SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
                SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours,
                SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
                SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team, i.id, i.innings_number
        )
        INSERT INTO bucketbaselinebatting (
            gender, team_type, tournament, season, team,
            innings_batted, total_runs, legal_balls, fours, sixes, dots,
            first_inn_runs_sum, first_inn_count,
            second_inn_runs_sum, second_inn_count,
            highest_inn_runs
        )
        SELECT
            gender, team_type, tournament, season, team,
            COUNT(*) AS innings_batted,
            SUM(runs) AS total_runs,
            SUM(legal_balls) AS legal_balls,
            SUM(fours) AS fours,
            SUM(sixes) AS sixes,
            SUM(dots) AS dots,
            SUM(CASE WHEN innings_number = 0 THEN runs ELSE 0 END) AS first_inn_runs_sum,
            SUM(CASE WHEN innings_number = 0 THEN 1 ELSE 0 END) AS first_inn_count,
            SUM(CASE WHEN innings_number = 1 THEN runs ELSE 0 END) AS second_inn_runs_sum,
            SUM(CASE WHEN innings_number = 1 THEN 1 ELSE 0 END) AS second_inn_count,
            COALESCE(MAX(runs), 0) AS highest_inn_runs
        FROM inn
        GROUP BY gender, team_type, tournament, season, team
        """,
        cfp,
    )


async def _populate_bowling(db, cells=None):
    """Bowling-side aggregates. Two-pass: INSERT delivery-side counters
    first (no wickets), then UPDATE wickets per cell+team in a separate
    pass. Avoids correlated subqueries in the SELECT — much faster
    plan."""
    cf, cfp = _cell_filter_clause(cells, "m")

    # League delivery counters — every delivery in scope.
    await db.q(
        f"""
        INSERT INTO bucketbaselinebowling (
            gender, team_type, tournament, season, team,
            innings_bowled, matches, runs_conceded, legal_balls,
            wides, noballs, fours_conceded, sixes_conceded, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            COUNT(DISTINCT i.id) AS innings_bowled,
            COUNT(DISTINCT m.id) AS matches,
            SUM(d.runs_total) AS runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
            SUM(CASE WHEN d.extras_wides > 0 THEN 1 ELSE 0 END) AS wides,
            SUM(CASE WHEN d.extras_noballs > 0 THEN 1 ELSE 0 END) AS noballs,
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots,
            0 AS wickets
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        """,
        cfp,
    )

    # Per-team delivery counters — innings where the team was bowling
    # (i.team != team AND match has team).
    await db.q(
        f"""
        WITH match_teams AS (
            SELECT DISTINCT match_id, team FROM matchplayer
        )
        INSERT INTO bucketbaselinebowling (
            gender, team_type, tournament, season, team,
            innings_bowled, matches, runs_conceded, legal_balls,
            wides, noballs, fours_conceded, sixes_conceded, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team,
            COUNT(DISTINCT i.id) AS innings_bowled,
            COUNT(DISTINCT m.id) AS matches,
            SUM(d.runs_total) AS runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
            SUM(CASE WHEN d.extras_wides > 0 THEN 1 ELSE 0 END) AS wides,
            SUM(CASE WHEN d.extras_noballs > 0 THEN 1 ELSE 0 END) AS noballs,
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) AS fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots,
            0 AS wickets
        FROM match m
        JOIN match_teams mt ON mt.match_id = m.id
        JOIN innings i ON i.match_id = m.id AND i.team != mt.team
        JOIN delivery d ON d.innings_id = i.id
        WHERE i.super_over = 0 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team
        """,
        cfp,
    )

    # League wickets — single GROUP BY pass over the wicket table.
    await db.q(
        f"""
        WITH wkt AS (
            SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                   m.season, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        )
        UPDATE bucketbaselinebowling
        SET wickets = (SELECT wickets FROM wkt
                       WHERE wkt.gender = bucketbaselinebowling.gender
                         AND wkt.team_type = bucketbaselinebowling.team_type
                         AND wkt.tournament = bucketbaselinebowling.tournament
                         AND wkt.season = bucketbaselinebowling.season)
        WHERE team = '{LEAGUE_TEAM}'
          AND EXISTS (SELECT 1 FROM wkt
                      WHERE wkt.gender = bucketbaselinebowling.gender
                        AND wkt.team_type = bucketbaselinebowling.team_type
                        AND wkt.tournament = bucketbaselinebowling.tournament
                        AND wkt.season = bucketbaselinebowling.season)
        """,
        cfp,
    )

    # Per-team wickets — group wickets by (cell, bowling_team).
    await db.q(
        f"""
        WITH match_teams AS (
            SELECT DISTINCT match_id, team FROM matchplayer
        ),
        wkt AS (
            SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                   m.season, mt.team AS bowling_team, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            JOIN match_teams mt ON mt.match_id = m.id AND mt.team != i.team
            WHERE i.super_over = 0
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team
        )
        UPDATE bucketbaselinebowling
        SET wickets = (SELECT wickets FROM wkt
                       WHERE wkt.gender = bucketbaselinebowling.gender
                         AND wkt.team_type = bucketbaselinebowling.team_type
                         AND wkt.tournament = bucketbaselinebowling.tournament
                         AND wkt.season = bucketbaselinebowling.season
                         AND wkt.bowling_team = bucketbaselinebowling.team)
        WHERE team != '{LEAGUE_TEAM}'
          AND EXISTS (SELECT 1 FROM wkt
                      WHERE wkt.gender = bucketbaselinebowling.gender
                        AND wkt.team_type = bucketbaselinebowling.team_type
                        AND wkt.tournament = bucketbaselinebowling.tournament
                        AND wkt.season = bucketbaselinebowling.season
                        AND wkt.bowling_team = bucketbaselinebowling.team)
        """,
        cfp,
    )


async def _populate_fielding(db, cells=None):
    """Fielding aggregates from fieldingcredit. fc has no team column —
    fielding-side team = the team in match that's NOT batting in this
    innings. Match → matchplayer gives the (match, team) pairs; pair
    that with i.team != team to get fielding-side rows."""
    cf, cfp = _cell_filter_clause(cells, "m")

    # League rows. Counts every fielding credit in the cell. Matches
    # count: distinct innings touched (mirrors _fielding_aggregates).
    await db.q(
        f"""
        INSERT INTO bucketbaselinefielding (
            gender, team_type, tournament, season, team,
            matches, catches, caught_and_bowled, stumpings, run_outs
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            -- "matches" denominator for the per-match rates: distinct
            -- match ids in scope (NOT distinct innings — every match
            -- has 2 fielding sides; per-match pool isn't 2x inflated).
            (SELECT COUNT(DISTINCT m2.id)
             FROM match m2 JOIN innings i2 ON i2.match_id = m2.id
             WHERE i2.super_over = 0
               AND m2.gender = m.gender AND m2.team_type = m.team_type
               AND COALESCE(m2.event_name, '') = COALESCE(m.event_name, '')
               AND m2.season = m.season) AS matches,
            SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
            SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS caught_and_bowled,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season
        """,
        cfp,
    )

    # Per-team rows. Fielding side = the (match, team) pair where
    # i.team != team. Pre-derive (match, team) via matchplayer to keep
    # the join surface narrow.
    await db.q(
        f"""
        WITH match_teams AS (
            SELECT DISTINCT match_id, team FROM matchplayer
        )
        INSERT INTO bucketbaselinefielding (
            gender, team_type, tournament, season, team,
            matches, catches, caught_and_bowled, stumpings, run_outs
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team,
            COUNT(DISTINCT i.id) AS matches,
            SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
            SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS caught_and_bowled,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN match_teams mt ON mt.match_id = m.id AND mt.team != i.team
        WHERE i.super_over = 0 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team
        """,
        cfp,
    )


async def _populate_phase(db, cells=None):
    """Phase splits per (cell, team, phase, side). 6 rows per (cell,
    team). Two-pass: INSERT delivery counters first (wickets=0), then
    UPDATE wickets per (cell, bowling team, phase) in a separate pass."""
    cf, cfp = _cell_filter_clause(cells, "m")

    phase_case = (
        "CASE WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay' "
        "WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle' "
        "WHEN d.over_number BETWEEN 15 AND 19 THEN 'death' END"
    )
    phase_case_w = phase_case.replace("d.over_number", "d2.over_number")

    # League BATTING.
    await db.q(
        f"""
        INSERT INTO bucketbaselinephase (
            gender, team_type, tournament, season, team, phase, side,
            runs, legal_balls, fours, sixes, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            {phase_case} AS phase, 'batting' AS side,
            SUM(d.runs_total),
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            0
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND d.over_number BETWEEN 0 AND 19 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, phase
        """,
        cfp,
    )

    # League BOWLING (delivery counters; wickets later).
    await db.q(
        f"""
        INSERT INTO bucketbaselinephase (
            gender, team_type, tournament, season, team, phase, side,
            runs, legal_balls, fours, sixes, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            {phase_case} AS phase, 'bowling' AS side,
            SUM(d.runs_total),
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            0
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND d.over_number BETWEEN 0 AND 19 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, phase
        """,
        cfp,
    )

    # Per-team BATTING per phase.
    await db.q(
        f"""
        INSERT INTO bucketbaselinephase (
            gender, team_type, tournament, season, team, phase, side,
            runs, legal_balls, fours, sixes, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team,
            {phase_case} AS phase, 'batting' AS side,
            SUM(d.runs_total),
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            0
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND d.over_number BETWEEN 0 AND 19 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team, phase
        """,
        cfp,
    )

    # Per-team BOWLING per phase (delivery counters; wickets later).
    await db.q(
        f"""
        WITH match_teams AS (
            SELECT DISTINCT match_id, team FROM matchplayer
        )
        INSERT INTO bucketbaselinephase (
            gender, team_type, tournament, season, team, phase, side,
            runs, legal_balls, fours, sixes, dots, wickets
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team,
            {phase_case} AS phase, 'bowling' AS side,
            SUM(d.runs_total),
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END),
            SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END),
            0
        FROM match m
        JOIN match_teams mt ON mt.match_id = m.id
        JOIN innings i ON i.match_id = m.id AND i.team != mt.team
        JOIN delivery d ON d.innings_id = i.id
        WHERE i.super_over = 0 AND d.over_number BETWEEN 0 AND 19 {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team, phase
        """,
        cfp,
    )

    # League BOWLING wickets per phase — single GROUP BY pass.
    await db.q(
        f"""
        WITH wkt AS (
            SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                   m.season, {phase_case_w} AS phase, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d2 ON d2.id = w.delivery_id
            JOIN innings i ON i.id = d2.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0
              AND d2.over_number BETWEEN 0 AND 19
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, phase
        )
        UPDATE bucketbaselinephase
        SET wickets = (
            SELECT wickets FROM wkt
            WHERE wkt.gender = bucketbaselinephase.gender
              AND wkt.team_type = bucketbaselinephase.team_type
              AND wkt.tournament = bucketbaselinephase.tournament
              AND wkt.season = bucketbaselinephase.season
              AND wkt.phase = bucketbaselinephase.phase
        )
        WHERE side = 'bowling' AND team = '{LEAGUE_TEAM}'
          AND EXISTS (
            SELECT 1 FROM wkt
            WHERE wkt.gender = bucketbaselinephase.gender
              AND wkt.team_type = bucketbaselinephase.team_type
              AND wkt.tournament = bucketbaselinephase.tournament
              AND wkt.season = bucketbaselinephase.season
              AND wkt.phase = bucketbaselinephase.phase
          )
        """,
        cfp,
    )

    # Per-team BOWLING wickets per (cell, bowling team, phase).
    await db.q(
        f"""
        WITH match_teams AS (
            SELECT DISTINCT match_id, team FROM matchplayer
        ),
        wkt AS (
            SELECT m.gender, m.team_type, COALESCE(m.event_name, '') AS tournament,
                   m.season, mt.team AS bowling_team,
                   {phase_case_w} AS phase, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d2 ON d2.id = w.delivery_id
            JOIN innings i ON i.id = d2.innings_id
            JOIN match m ON m.id = i.match_id
            JOIN match_teams mt ON mt.match_id = m.id AND mt.team != i.team
            WHERE i.super_over = 0
              AND d2.over_number BETWEEN 0 AND 19
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
              {cf}
            GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, mt.team, phase
        )
        UPDATE bucketbaselinephase
        SET wickets = (
            SELECT wickets FROM wkt
            WHERE wkt.gender = bucketbaselinephase.gender
              AND wkt.team_type = bucketbaselinephase.team_type
              AND wkt.tournament = bucketbaselinephase.tournament
              AND wkt.season = bucketbaselinephase.season
              AND wkt.phase = bucketbaselinephase.phase
              AND wkt.bowling_team = bucketbaselinephase.team
        )
        WHERE side = 'bowling' AND team != '{LEAGUE_TEAM}'
          AND EXISTS (
            SELECT 1 FROM wkt
            WHERE wkt.gender = bucketbaselinephase.gender
              AND wkt.team_type = bucketbaselinephase.team_type
              AND wkt.tournament = bucketbaselinephase.tournament
              AND wkt.season = bucketbaselinephase.season
              AND wkt.phase = bucketbaselinephase.phase
              AND wkt.bowling_team = bucketbaselinephase.team
          )
        """,
        cfp,
    )


async def _populate_partnership(db, cells=None):
    """Partnership aggregates per (cell, team, wicket_number).
    Excludes partnerships terminated by retired hurt / retired not out
    (matches the convention in api/routers/teams.py)."""
    cf, cfp = _cell_filter_clause(cells, "m")

    # League rows: every partnership in the cell, grouped by wicket_number.
    await db.q(
        f"""
        INSERT INTO bucketbaselinepartnership (
            gender, team_type, tournament, season, team, wicket_number,
            n, total_runs, total_balls, best_runs
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, '{LEAGUE_TEAM}',
            p.wicket_number,
            COUNT(*) AS n,
            SUM(p.partnership_runs) AS total_runs,
            SUM(p.partnership_balls) AS total_balls,
            COALESCE(MAX(p.partnership_runs), 0) AS best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND p.wicket_number IS NOT NULL
          AND (p.ended_by_kind IS NULL
               OR p.ended_by_kind NOT IN ('retired hurt', 'retired not out'))
          {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, p.wicket_number
        """,
        cfp,
    )

    # Per-team rows: i.team = batting team for the partnership.
    await db.q(
        f"""
        INSERT INTO bucketbaselinepartnership (
            gender, team_type, tournament, season, team, wicket_number,
            n, total_runs, total_balls, best_runs
        )
        SELECT
            m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team,
            p.wicket_number,
            COUNT(*),
            SUM(p.partnership_runs),
            SUM(p.partnership_balls),
            COALESCE(MAX(p.partnership_runs), 0)
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND p.wicket_number IS NOT NULL
          AND (p.ended_by_kind IS NULL
               OR p.ended_by_kind NOT IN ('retired hurt', 'retired not out'))
          {cf}
        GROUP BY m.gender, m.team_type, COALESCE(m.event_name, ''), m.season, i.team, p.wicket_number
        """,
        cfp,
    )


# ─── Public modes ───────────────────────────────────────────────────────

async def populate_full(db):
    """Drop + rebuild every bucket_baseline_* table from scratch."""
    print("[bucket_baseline] full rebuild starting…")
    await _ensure_tables(db, incremental=False)

    for table in ("bucketbaselinematch", "bucketbaselinebatting",
                  "bucketbaselinebowling", "bucketbaselinefielding",
                  "bucketbaselinephase", "bucketbaselinepartnership"):
        await db.q(f"DELETE FROM {table}")

    t0 = time.time()
    print("  match…");        await _populate_match(db);        print(f"    {time.time()-t0:.1f}s")
    t0 = time.time()
    print("  batting…");      await _populate_batting(db);      print(f"    {time.time()-t0:.1f}s")
    t0 = time.time()
    print("  bowling…");      await _populate_bowling(db);      print(f"    {time.time()-t0:.1f}s")
    t0 = time.time()
    print("  fielding…");     await _populate_fielding(db);     print(f"    {time.time()-t0:.1f}s")
    t0 = time.time()
    print("  phase…");        await _populate_phase(db);        print(f"    {time.time()-t0:.1f}s")
    t0 = time.time()
    print("  partnership…");  await _populate_partnership(db);  print(f"    {time.time()-t0:.1f}s")

    counts = {}
    for table in ("bucketbaselinematch", "bucketbaselinebatting",
                  "bucketbaselinebowling", "bucketbaselinefielding",
                  "bucketbaselinephase", "bucketbaselinepartnership"):
        rows = await db.q(f"SELECT COUNT(*) AS c FROM {table}")
        counts[table] = rows[0]["c"]
    print("[bucket_baseline] row counts:", counts)


async def populate_incremental(db, new_match_ids: list[int]):
    """Recompute cells touched by new_match_ids.

    Strategy: enumerate the (g, tt, t, s) cells the new matches belong
    to, DELETE all rows in those cells from every bucket_baseline_*
    table, then re-INSERT via the same SQL as the full populate but
    with a cell-level WHERE filter. Cell-level recompute is exact
    because the aggregates only depend on data within the cell.
    """
    if not new_match_ids:
        return
    await _ensure_tables(db, incremental=True)

    # Cells affected by these match ids.
    placeholders = ",".join(f":m{i}" for i in range(len(new_match_ids)))
    params = {f"m{i}": mid for i, mid in enumerate(new_match_ids)}
    cell_rows = await db.q(
        f"""
        SELECT DISTINCT m.gender, m.team_type,
               COALESCE(m.event_name, '') AS tournament, m.season
        FROM match m WHERE m.id IN ({placeholders})
        """,
        params,
    )
    cells = [(r["gender"], r["team_type"], r["tournament"], r["season"]) for r in cell_rows]
    if not cells:
        return

    print(f"[bucket_baseline] incremental — {len(cells)} cells touched, recomputing…")

    # Delete affected cells from every table.
    cf_parts = []
    cf_params = {}
    for i, (g, tt, t, s) in enumerate(cells):
        cf_params[f"d_g_{i}"]  = g
        cf_params[f"d_tt_{i}"] = tt
        cf_params[f"d_t_{i}"]  = t
        cf_params[f"d_s_{i}"]  = s
        cf_parts.append(
            f"(gender = :d_g_{i} AND team_type = :d_tt_{i} "
            f"AND tournament = :d_t_{i} AND season = :d_s_{i})"
        )
    cf_where = " OR ".join(cf_parts)

    for table in ("bucketbaselinematch", "bucketbaselinebatting",
                  "bucketbaselinebowling", "bucketbaselinefielding",
                  "bucketbaselinephase", "bucketbaselinepartnership"):
        await db.q(f"DELETE FROM {table} WHERE {cf_where}", cf_params)

    # Re-INSERT via the same per-table routines, scoped to the cells.
    await _populate_match(db, cells)
    await _populate_batting(db, cells)
    await _populate_bowling(db, cells)
    await _populate_fielding(db, cells)
    await _populate_phase(db, cells)
    await _populate_partnership(db, cells)


# ─── CLI ────────────────────────────────────────────────────────────────

async def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PATH, help="Path to cricket.db")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{args.db}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(_main())
