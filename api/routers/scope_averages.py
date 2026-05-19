"""League-scope baseline endpoints — the "average team" / "average league
behaviour" counterpart to `/api/v1/teams/{team}/*`.

Every endpoint here mirrors a `/teams/{team}/*` sibling but with the
team filter dropped — the result is the pool-weighted average over the
current FilterBar scope. Used by the Teams Compare tab to render an
"average team" column alongside selected teams.

Path-level "team" parameter is gone; everything else (gender,
team_type, tournament, season_from, season_to, filter_venue,
series_type) is identical to the team siblings via FilterParams +
AuxParams.

The helpers `_team_innings_clause` and `_partnership_filter` in
`api.routers.teams` accept `team=None` precisely so this router can
reuse the same WHERE-clause logic — guaranteeing both code paths agree
on filter injection. Identity-bearing nested objects from the team
endpoints (highest_total, best_pair, keepers list, etc.) are kept where
they're meaningful at scope level (highest league total has a team
owner, league's best pair has people identity) and dropped where they
aren't (a "league average team" has no captain or home ground).

Spec: `internal_docs/spec-team-compare-average.md`.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..filters import FilterParams, AuxParams
from ..dependencies import get_db
from ..metrics_metadata import wrap_metric
from ..scope_averages_players import (
    batting_threshold,
    bowling_threshold,
    fielding_threshold,
    parse_mix,
    parse_drop,
    build_scope_clauses,
    convex_combine,
    batting_bucket_label,
    bowling_bucket_label,
    fielding_bucket_label,
)
from .teams import (
    _team_innings_clause, _partnership_filter, _scope_to_team_clause, _safe_div,
    _apply_batting_per_innings, _apply_bowling_per_innings,
    _apply_fielding_per_innings, _apply_partnerships_per_innings,
    _apply_results_per_team, _unique_teams_in_scope,
)
from .bucket_baseline_dispatch import (
    is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY,
)

router = APIRouter(prefix="/api/v1/scope/averages", tags=["Scope-Averages"])


# ── per-innings divisors ──────────────────────────────────────────
# Each scope-averages endpoint needs an innings_count (or matches × 2
# for fielding) to divide absolute counts by. Baseline path reads
# from bucketbaselinebatting / bucketbaselinebowling / bucketbaselinematch;
# live path runs a small COUNT(DISTINCT i.id) query against the
# delivery + innings + match tables.

async def _baseline_innings_batted(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(innings_batted) AS innings_batted FROM bucketbaselinebatting {where}",
        params,
    )
    return (rows[0].get("innings_batted") if rows else 0) or 0


async def _baseline_innings_bowled(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(innings_bowled) AS innings_bowled FROM bucketbaselinebowling {where}",
        params,
    )
    return (rows[0].get("innings_bowled") if rows else 0) or 0


async def _baseline_matches(filters, aux) -> int:
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"SELECT SUM(matches) AS matches FROM bucketbaselinematch {where}",
        params,
    )
    return (rows[0].get("matches") if rows else 0) or 0


async def _live_innings_batted(filters, aux) -> int:
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings_batted
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("innings_batted") if rows else 0) or 0


async def _live_innings_bowled(filters, aux) -> int:
    """Same as innings_batted but counts innings where the team was
    fielding. For league-scope (team=None), this equals innings_batted
    since every batting innings has a corresponding fielding innings."""
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings_bowled
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("innings_bowled") if rows else 0) or 0


async def _live_match_count(filters, aux) -> int:
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) AS matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("matches") if rows else 0) or 0


# ============================================================
# Summary (results / toss style — match-level aggregates)
# ============================================================

@router.get("/summary")
async def scope_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """League-scope match-level totals + toss/bat-first signals.

    Dispatches to bucket_baseline_match for precomputed-regime scopes
    (~10x faster); falls back to live aggregation for filter_venue /
    rivalry / series_type / partial-season filters.
    """
    if is_precomputed_scope(filters, aux):
        return await _summary_from_baseline(filters, aux)
    return await _summary_live(filters, aux)


async def _summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
            SUM(matches) AS matches,
            SUM(decided) AS decided,
            SUM(ties) AS ties,
            SUM(no_results) AS no_results,
            SUM(toss_decided) AS toss_decided,
            SUM(bat_first_wins) AS bat_first_wins,
            SUM(field_first_wins) AS field_first_wins
        FROM bucketbaselinematch {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    decided = r.get("decided", 0) or 0
    bf = r.get("bat_first_wins", 0) or 0
    bf_pct = round(bf * 100 / decided, 1) if decided > 0 else None
    pool = {
        "matches": r.get("matches", 0) or 0,
        "decided": decided,
        "ties": r.get("ties", 0) or 0,
        "no_results": r.get("no_results", 0) or 0,
        "toss_decided": r.get("toss_decided", 0) or 0,
        "bat_first_wins": bf,
        "field_first_wins": r.get("field_first_wins", 0) or 0,
        "bat_first_win_pct": bf_pct,
    }
    unique_teams = await _unique_teams_in_scope(filters, aux)
    return _apply_results_per_team(pool, unique_teams)


async def _summary_live(filters, aux):
    db = get_db()
    # Match-level filter only (no innings join).
    filters.team = None
    where, params = filters.build(has_innings_join=False, aux=aux)
    # Avg slot's auto-narrow to primary team's tournament universe.
    st_clause, st_params = _scope_to_team_clause(aux, filters)
    if st_clause:
        where = f"{where} AND {st_clause}" if where else st_clause
        params.update(st_params)
    where = where or "1=1"

    rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END) as decided,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
            SUM(CASE WHEN m.toss_winner IS NOT NULL THEN 1 ELSE 0 END) as toss_decided,
            SUM(CASE WHEN m.toss_decision = 'bat'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'field'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN m.toss_decision = 'field'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'bat'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as field_first_wins
        FROM match m
        WHERE {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    decided = r.get("decided", 0) or 0
    bf = r.get("bat_first_wins", 0) or 0
    bf_pct = round(bf * 100 / decided, 1) if decided > 0 else None
    pool = {
        "matches": r.get("matches", 0) or 0,
        "decided": decided,
        "ties": r.get("ties", 0) or 0,
        "no_results": r.get("no_results", 0) or 0,
        "toss_decided": r.get("toss_decided", 0) or 0,
        "bat_first_wins": bf,
        "field_first_wins": r.get("field_first_wins", 0) or 0,
        "bat_first_win_pct": bf_pct,
    }
    unique_teams = await _unique_teams_in_scope(filters, aux)
    return _apply_results_per_team(pool, unique_teams)


# ============================================================
# Batting
# ============================================================

@router.get("/batting/summary")
async def scope_batting_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope batting aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _batting_summary_from_baseline(filters, aux)
    return await _batting_summary_live(filters, aux)


def _format_batting_summary(
    innings_batted, total_runs, legal_balls, fours, sixes, dots,
    first_inn_runs_sum, first_inn_count,
    second_inn_runs_sum, second_inn_count,
    highest_total,
):
    runs = total_runs or 0
    balls = legal_balls or 0
    fours = fours or 0
    sixes = sixes or 0
    dots = dots or 0
    boundaries = fours + sixes
    avg_1st = round((first_inn_runs_sum or 0) / first_inn_count, 1) if first_inn_count else None
    avg_2nd = round((second_inn_runs_sum or 0) / second_inn_count, 1) if second_inn_count else None
    return {
        "innings_batted": innings_batted or 0,
        "total_runs": runs,
        "legal_balls": balls,
        "run_rate": _safe_div(runs, balls, 6),
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
    }


async def _batting_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
          SUM(innings_batted) AS innings_batted,
          SUM(total_runs) AS total_runs,
          SUM(legal_balls) AS legal_balls,
          SUM(fours) AS fours, SUM(sixes) AS sixes, SUM(dots) AS dots,
          SUM(first_inn_runs_sum) AS first_inn_runs_sum,
          SUM(first_inn_count) AS first_inn_count,
          SUM(second_inn_runs_sum) AS second_inn_runs_sum,
          SUM(second_inn_count) AS second_inn_count
        FROM bucketbaselinebatting {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    # Highest_total: pick the cell row with the largest highest_inn_runs.
    hi_rows = await db.q(
        f"""
        SELECT highest_inn_runs AS runs, highest_inn_match_id AS match_id,
               highest_inn_team AS team, highest_inn_innings_number AS innings_number
        FROM bucketbaselinebatting {where} AND highest_inn_runs > 0
        ORDER BY highest_inn_runs DESC, highest_inn_match_id LIMIT 1
        """,
        params,
    )
    highest = None
    if hi_rows:
        h = hi_rows[0]
        highest = {
            "runs": h["runs"],
            "team": h["team"],
            "match_id": h["match_id"],
            "innings_number": (h["innings_number"] or 0) + 1,
        }
    out = _format_batting_summary(highest_total=highest, **{k: r.get(k) for k in (
        "innings_batted", "total_runs", "legal_balls", "fours", "sixes", "dots",
        "first_inn_runs_sum", "first_inn_count",
        "second_inn_runs_sum", "second_inn_count",
    )})
    return _apply_batting_per_innings(out, out.get("innings_batted") or 0, drop_divisor=True)


async def _batting_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    total_runs = c.get("total_runs") or 0
    legal_balls = c.get("legal_balls") or 0
    fours = c.get("fours") or 0
    sixes = c.get("sixes") or 0
    dots = c.get("dots") or 0
    boundaries = fours + sixes

    # Per-innings totals → avg 1st/2nd-innings + highest single innings.
    innings_rows = await db.q(
        f"""
        SELECT
            i.id as innings_id, i.match_id, i.innings_number,
            i.team as innings_team,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number, i.team
        """,
        params,
    )
    first_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 0 and r["runs"] is not None]
    second_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 1 and r["runs"] is not None]
    avg_1st = round(sum(first_totals) / len(first_totals), 1) if first_totals else None
    avg_2nd = round(sum(second_totals) / len(second_totals), 1) if second_totals else None

    highest_total = None
    if innings_rows:
        top = max(innings_rows, key=lambda r: r["runs"] or 0)
        highest_total = {
            "runs": top["runs"] or 0,
            "team": top["innings_team"],
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }

    out = {
        "innings_batted": c.get("innings_batted") or 0,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
    }
    return _apply_batting_per_innings(out, out.get("innings_batted") or 0, drop_divisor=True)


@router.get("/batting/by-phase")
async def scope_batting_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted phase splits (PP 0-5 / Mid 6-14 / Death 15-19).
    Bucket-baseline path for precomputed scopes; live fallback for
    venue / rivalry / series_type filters."""
    if is_precomputed_scope(filters, aux):
        return await _batting_by_phase_from_baseline(filters, aux)
    return await _batting_by_phase_live(filters, aux)


OVER_RANGES = [
    ("powerplay", [1, 6]),
    ("middle",    [7, 15]),
    ("death",     [16, 20]),
]


async def _batting_by_phase_from_baseline(filters, aux):
    db = get_db()
    # Two SUM passes against bucket_baseline_phase: batting rows for
    # delivery counters; bowling rows separately give wickets-lost
    # because that's actually a bowler-credited count for the phase
    # (mirrored to wickets_lost in the live aggregator's wkt query
    # which only excludes retired*).
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    bat_rows = await db.q(
        f"""
        SELECT phase,
               SUM(runs) AS runs,
               SUM(legal_balls) AS balls,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots
        FROM bucketbaselinephase {where} AND side='batting'
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in bat_rows if r["phase"]}

    # wickets_lost in the live aggregator excludes only retired*; our
    # baseline phase.wickets is bowler-credited (excludes run-out etc.)
    # — wider exclusion. To match exactly, we run a small live query
    # for wickets_lost.
    # NOTE: live path's wickets_lost uses a different exclusion list;
    # match it with a targeted query that respects only retired*.
    where_live, params_live = _team_innings_clause(filters, None, side="batting", aux=aux)
    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where_live}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params_live,
    )
    wkt_by_phase = {r["phase"]: r["wickets_lost"] for r in wkt_rows if r["phase"]}

    out = []
    for phase, ranges in OVER_RANGES:
        s = by_phase.get(phase) or {}
        runs = s.get("runs") or 0
        balls = s.get("balls") or 0
        fours = s.get("fours") or 0
        sixes = s.get("sixes") or 0
        dots = s.get("dots") or 0
        boundaries = fours + sixes
        out.append({
            "phase": phase,
            "overs_range": ranges,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wkt_by_phase.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return _phase_per_innings(out, await _baseline_innings_batted(filters, aux))


def _phase_per_innings(rows: list[dict], innings_count: int) -> dict:
    """Divide phase-row absolute counts by innings_count. Per-innings
    treatment for the avg endpoint (rates stay pool ≡ per-innings)."""
    if innings_count and innings_count > 0:
        keys = ("runs", "runs_conceded", "balls", "wickets_lost", "wickets",
                "fours", "sixes", "fours_conceded", "sixes_conceded")
        for r in rows:
            for k in keys:
                v = r.get(k)
                if v is not None:
                    r[k] = round(v / innings_count, 2)
    return {"by_phase": rows}


async def _batting_by_phase_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}

    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wkt_by_phase = {r["phase"]: r["wickets_lost"] for r in wkt_rows if r["phase"]}

    out = []
    for phase, ranges in OVER_RANGES:
        s = by_phase.get(phase) or {}
        runs = s.get("runs") or 0
        balls = s.get("balls") or 0
        fours = s.get("fours") or 0
        sixes = s.get("sixes") or 0
        dots = s.get("dots") or 0
        boundaries = fours + sixes
        out.append({
            "phase": phase,
            "overs_range": ranges,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wkt_by_phase.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return _phase_per_innings(out, await _live_innings_batted(filters, aux))


@router.get("/batting/by-season")
async def scope_batting_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted batting aggregates per season — drives the season-
    trajectory strip in the Compare tab."""
    if is_precomputed_scope(filters, aux):
        return await _batting_by_season_from_baseline(filters, aux)
    return await _batting_by_season_live(filters, aux)


def _format_batting_season_row(season, innings_batted, total_runs, legal_balls, fours, sixes, dots):
    runs = total_runs or 0
    balls = legal_balls or 0
    fours = fours or 0
    sixes = sixes or 0
    dots = dots or 0
    boundaries = fours + sixes
    inn = innings_batted or 0
    out = {
        "season": season,
        "innings_batted": inn,
        "total_runs": runs,
        "legal_balls": balls,
        "run_rate": _safe_div(runs, balls, 6),
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
    }
    return _apply_batting_per_innings(out, inn, drop_divisor=True)


async def _batting_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_batted) AS innings_batted,
               SUM(total_runs) AS total_runs,
               SUM(legal_balls) AS legal_balls,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots
        FROM bucketbaselinebatting {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    return {"by_season": [_format_batting_season_row(**r) for r in rows]}


async def _batting_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    return {"by_season": [_format_batting_season_row(**r) for r in rows]}


# ============================================================
# Bowling
# ============================================================

@router.get("/bowling/summary")
async def scope_bowling_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope bowling aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_summary_from_baseline(filters, aux)
    return await _bowling_summary_live(filters, aux)


def _format_bowling_summary(
    innings_bowled, matches, runs_conceded, legal_balls,
    wides, noballs, fours_conceded, sixes_conceded, dots, wickets,
):
    runs = runs_conceded or 0
    balls = legal_balls or 0
    dots = dots or 0
    matches = matches or 0
    wickets = wickets or 0
    inn = innings_bowled or 0
    fours = fours_conceded or 0
    sixes = sixes_conceded or 0
    out = {
        "innings_bowled": inn,
        "matches": matches,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs, balls, 6),
        "strike_rate": _safe_div(balls, wickets) if wickets else None,
        "average": _safe_div(runs, wickets) if wickets else None,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": fours,
        "sixes_conceded": sixes,
        "boundaries_conceded": fours + sixes,
        "wides": wides or 0,
        "noballs": noballs or 0,
        "wides_per_match": _safe_div(wides or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(noballs or 0, matches, 1, 2),
    }
    return _apply_bowling_per_innings(out, inn, drop_divisor=True)


async def _bowling_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT
            SUM(innings_bowled) AS innings_bowled,
            SUM(matches) AS matches,
            SUM(runs_conceded) AS runs_conceded,
            SUM(legal_balls) AS legal_balls,
            SUM(wides) AS wides,
            SUM(noballs) AS noballs,
            SUM(fours_conceded) AS fours_conceded,
            SUM(sixes_conceded) AS sixes_conceded,
            SUM(dots) AS dots,
            SUM(wickets) AS wickets
        FROM bucketbaselinebowling {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    return _format_bowling_summary(
        innings_bowled=r.get("innings_bowled"), matches=r.get("matches"),
        runs_conceded=r.get("runs_conceded"), legal_balls=r.get("legal_balls"),
        wides=r.get("wides"), noballs=r.get("noballs"),
        fours_conceded=r.get("fours_conceded"), sixes_conceded=r.get("sixes_conceded"),
        dots=r.get("dots"), wickets=r.get("wickets"),
    )


async def _bowling_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.extras_wides > 0 THEN 1 ELSE 0 END) as wides,
            SUM(CASE WHEN d.extras_noballs > 0 THEN 1 ELSE 0 END) as noballs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    wkt_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        """,
        params,
    )
    matches_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    return _format_bowling_summary(
        innings_bowled=c.get("innings_bowled"),
        matches=matches_rows[0]["matches"] if matches_rows else 0,
        runs_conceded=c.get("runs_conceded"), legal_balls=c.get("legal_balls"),
        wides=c.get("wides"), noballs=c.get("noballs"),
        fours_conceded=c.get("fours_conceded"), sixes_conceded=c.get("sixes_conceded"),
        dots=c.get("dots"),
        wickets=wkt_rows[0]["wickets"] if wkt_rows else 0,
    )


@router.get("/bowling/by-phase")
async def scope_bowling_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling phase splits."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_by_phase_from_baseline(filters, aux)
    return await _bowling_by_phase_live(filters, aux)


def _format_bowling_phase_row(phase, ranges, runs_conceded, balls, fours_conceded, sixes_conceded, dots, wickets):
    runs = runs_conceded or 0
    balls = balls or 0
    fours = fours_conceded or 0
    sixes = sixes_conceded or 0
    dots = dots or 0
    boundaries = fours + sixes
    return {
        "phase": phase, "overs_range": ranges,
        "runs_conceded": runs, "balls": balls,
        "economy": _safe_div(runs, balls, 6),
        "wickets": wickets or 0,
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": fours, "sixes_conceded": sixes,
    }


async def _bowling_by_phase_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT phase,
               SUM(runs) AS runs_conceded,
               SUM(legal_balls) AS balls,
               SUM(fours) AS fours_conceded,
               SUM(sixes) AS sixes_conceded,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets
        FROM bucketbaselinephase {where} AND side='bowling'
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}
    out = [
        _format_bowling_phase_row(
            phase=phase, ranges=ranges,
            runs_conceded=(by_phase.get(phase) or {}).get("runs_conceded"),
            balls=(by_phase.get(phase) or {}).get("balls"),
            fours_conceded=(by_phase.get(phase) or {}).get("fours_conceded"),
            sixes_conceded=(by_phase.get(phase) or {}).get("sixes_conceded"),
            dots=(by_phase.get(phase) or {}).get("dots"),
            wickets=(by_phase.get(phase) or {}).get("wickets"),
        )
        for phase, ranges in OVER_RANGES
    ]
    return _phase_per_innings(out, await _baseline_innings_bowled(filters, aux))


async def _bowling_by_phase_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
        GROUP BY phase
        """,
        params,
    )
    by_phase = {r["phase"]: r for r in rows if r["phase"]}

    wkt_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.over_number BETWEEN 0 AND 19
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wkt_by_phase = {r["phase"]: r["wickets"] for r in wkt_rows if r["phase"]}

    out = [
        _format_bowling_phase_row(
            phase=phase, ranges=ranges,
            runs_conceded=(by_phase.get(phase) or {}).get("runs_conceded"),
            balls=(by_phase.get(phase) or {}).get("balls"),
            fours_conceded=(by_phase.get(phase) or {}).get("fours_conceded"),
            sixes_conceded=(by_phase.get(phase) or {}).get("sixes_conceded"),
            dots=(by_phase.get(phase) or {}).get("dots"),
            wickets=wkt_by_phase.get(phase, 0),
        )
        for phase, ranges in OVER_RANGES
    ]
    return _phase_per_innings(out, await _live_innings_bowled(filters, aux))


@router.get("/bowling/by-season")
async def scope_bowling_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling aggregates per season."""
    if is_precomputed_scope(filters, aux):
        return await _bowling_by_season_from_baseline(filters, aux)
    return await _bowling_by_season_live(filters, aux)


def _format_bowling_season_row(season, innings_bowled, runs_conceded, legal_balls, boundaries_conceded, dots, wickets):
    runs = runs_conceded or 0
    balls = legal_balls or 0
    inn = innings_bowled or 0
    out = {
        "season": season,
        "innings_bowled": inn,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets or 0,
        "economy": _safe_div(runs, balls, 6),
        "dot_pct": _safe_div(dots or 0, balls, 100, 1),
        "boundaries_conceded": boundaries_conceded or 0,
    }
    # `boundaries_conceded` isn't in BOWLING_COUNT_KEYS — divide it
    # explicitly per spec by-season transform.
    if inn:
        out["boundaries_conceded"] = round((boundaries_conceded or 0) / inn, 2)
    return _apply_bowling_per_innings(out, inn, drop_divisor=True)


async def _bowling_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_bowled) AS innings_bowled,
               SUM(runs_conceded) AS runs_conceded,
               SUM(legal_balls) AS legal_balls,
               SUM(fours_conceded + sixes_conceded) AS boundaries_conceded,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets
        FROM bucketbaselinebowling {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    return {"by_season": [_format_bowling_season_row(**r) for r in rows]}


async def _bowling_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN (d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0)
                     OR d.runs_batter = 6 THEN 1 ELSE 0 END) as boundaries_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    wkt_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')
        GROUP BY m.season
        """,
        params,
    )
    wkt_by_season = {r["season"]: r["wickets"] for r in wkt_rows}
    return {"by_season": [
        _format_bowling_season_row(
            season=r["season"], innings_bowled=r["innings_bowled"],
            runs_conceded=r["runs_conceded"], legal_balls=r["legal_balls"],
            boundaries_conceded=r["boundaries_conceded"], dots=r["dots"],
            wickets=wkt_by_season.get(r["season"], 0),
        )
        for r in rows
    ]}


# ============================================================
# Fielding
# ============================================================

@router.get("/fielding/summary")
async def scope_fielding_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope fielding aggregates."""
    if is_precomputed_scope(filters, aux):
        return await _fielding_summary_from_baseline(filters, aux)
    return await _fielding_summary_live(filters, aux)


def _format_fielding_summary(matches, catches_only, caught_and_bowled, stumpings, run_outs, *, inning_active: bool = False):
    matches = matches or 0
    catches_only = catches_only or 0
    cnb = caught_and_bowled or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    catches = catches_only + cnb  # response.catches includes c_a_b
    out = {
        "matches": matches,
        "catches": catches,
        "caught_and_bowled": cnb,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + stumpings + run_outs,
        "catches_per_match": _safe_div(catches, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    # inning_active narrows each match to 1 fielding innings in scope
    # (vs 2 for the all-innings case). Spec: spec-inning-split.md §5.5.
    mult = 1 if inning_active else 2
    return _apply_fielding_per_innings(
        out, matches * mult, halve_per_match=not inning_active,
    )


async def _fielding_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT SUM(matches) AS matches,
               SUM(catches) AS catches_only,
               SUM(caught_and_bowled) AS caught_and_bowled,
               SUM(stumpings) AS stumpings,
               SUM(run_outs) AS run_outs
        FROM bucketbaselinefielding {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    inning_active = aux is not None and aux.inning is not None
    return _format_fielding_summary(
        matches=r.get("matches"),
        catches_only=r.get("catches_only"),
        caught_and_bowled=r.get("caught_and_bowled"),
        stumpings=r.get("stumpings"),
        run_outs=r.get("run_outs"),
        inning_active=inning_active,
    )


async def _fielding_summary_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) as caught_and_bowled,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    matches_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        """,
        params,
    )
    matches = matches_rows[0]["matches"] if matches_rows else 0
    # Live SQL puts c_a_b into "catches"; baseline keeps them split.
    # Normalise to the baseline shape so the formatter handles both.
    catches_with_cnb = r.get("catches") or 0
    cnb = r.get("caught_and_bowled") or 0
    inning_active = aux is not None and aux.inning is not None
    return _format_fielding_summary(
        matches=matches,
        catches_only=catches_with_cnb - cnb,
        caught_and_bowled=cnb,
        stumpings=r.get("stumpings") or 0,
        run_outs=r.get("run_outs") or 0,
        inning_active=inning_active,
    )


@router.get("/fielding/by-season")
async def scope_fielding_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted fielding aggregates per season."""
    if is_precomputed_scope(filters, aux):
        return await _fielding_by_season_from_baseline(filters, aux)
    return await _fielding_by_season_live(filters, aux)


def _format_fielding_season_row(season, matches, catches, stumpings, run_outs, *, inning_active: bool = False):
    matches = matches or 0
    catches = catches or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    out = {
        "season": season,
        "matches": matches,
        "catches": catches,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + stumpings + run_outs,
        "catches_per_match": _safe_div(catches, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    mult = 1 if inning_active else 2
    return _apply_fielding_per_innings(
        out, matches * mult, halve_per_match=not inning_active,
    )


async def _fielding_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    # SUM matches per season from bucketbaselinematch (matches denominator);
    # SUM catches+stumpings+run_outs from bucketbaselinefielding.
    f_rows = await db.q(
        f"""
        SELECT season,
               SUM(catches + caught_and_bowled) AS catches,
               SUM(stumpings) AS stumpings,
               SUM(run_outs) AS run_outs
        FROM bucketbaselinefielding {where}
        GROUP BY season
        HAVING SUM(catches + caught_and_bowled + stumpings + run_outs) > 0
        ORDER BY season
        """,
        params,
    )
    where_m, params_m = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    m_rows = await db.q(
        f"SELECT season, SUM(matches) AS matches FROM bucketbaselinematch {where_m} GROUP BY season",
        params_m,
    )
    m_by_season = {r["season"]: r["matches"] for r in m_rows}
    inning_active = aux is not None and aux.inning is not None
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=m_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
            inning_active=inning_active,
        )
        for r in f_rows
    ]}


async def _fielding_by_season_live(filters, aux):
    db = get_db()
    where, params = _team_innings_clause(filters, None, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    matches_rows = await db.q(
        f"""
        SELECT m.season, COUNT(DISTINCT m.id) as matches
        FROM match m
        JOIN innings i ON i.match_id = m.id
        WHERE {where}
        GROUP BY m.season
        """,
        params,
    )
    matches_by_season = {r["season"]: r["matches"] for r in matches_rows}
    inning_active = aux is not None and aux.inning is not None
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=matches_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
            inning_active=inning_active,
        )
        for r in rows
    ]}


# ============================================================
# Partnerships
# ============================================================

@router.get("/partnerships/summary")
async def scope_partnerships_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted partnership aggregates across the whole league."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_summary_from_baseline(filters, aux)
    return await _partnerships_summary_live(filters, aux)


async def _fetch_partnership_identity(db, partnership_id: int) -> dict | None:
    """One small SELECT against partnership table for identity payload —
    same shape as the live endpoint's `highest` / `best_partnership`."""
    if partnership_id is None:
        return None
    rows = await db.q(
        """
        SELECT p.id AS partnership_id, p.partnership_runs AS runs,
               p.partnership_balls AS balls,
               p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
               m.id AS match_id, m.season, m.event_name AS tournament,
               i.team AS team,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) AS date
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE p.id = :pid
        """,
        {"pid": partnership_id},
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "partnership_id": r["partnership_id"],
        "match_id": r["match_id"],
        "date": r["date"],
        "season": r["season"],
        "tournament": r["tournament"],
        "team": r["team"],
        "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
        "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
        "runs": r["runs"],
        "balls": r["balls"],
    }


async def _partnerships_summary_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT SUM(n) AS total,
               SUM(count_50_plus) AS count_50_plus,
               SUM(count_100_plus) AS count_100_plus,
               SUM(total_runs) AS total_runs
        FROM bucketbaselinepartnership {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    total = r.get("total") or 0
    avg_runs = round((r.get("total_runs") or 0) / total, 1) if total else None
    # Highest: pick row with MAX(best_runs); fetch identity by partnership_id.
    hi_rows = await db.q(
        f"""
        SELECT best_runs, best_pair_partnership_id
        FROM bucketbaselinepartnership {where} AND best_runs > 0
        ORDER BY best_runs DESC, best_pair_partnership_id LIMIT 1
        """,
        params,
    )
    highest = None
    if hi_rows:
        highest_full = await _fetch_partnership_identity(db, hi_rows[0]["best_pair_partnership_id"])
        if highest_full:
            # /partnerships/summary live shape strips tournament/season/
            # partnership_id from the identity payload — match it.
            highest = {
                "runs": highest_full["runs"], "balls": highest_full["balls"],
                "match_id": highest_full["match_id"], "date": highest_full["date"],
                "team": highest_full["team"],
                "batter1": highest_full["batter1"],
                "batter2": highest_full["batter2"],
            }
    out = {
        "total": total,
        "count_50_plus": r.get("count_50_plus") or 0,
        "count_100_plus": r.get("count_100_plus") or 0,
        "avg_runs": avg_runs,
        "highest": highest,
    }
    return _apply_partnerships_per_innings(out, await _baseline_innings_batted(filters, aux))


async def _partnerships_summary_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN p.partnership_runs >= 50 THEN 1 ELSE 0 END) as count_50_plus,
            SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
            ROUND(AVG(p.partnership_runs), 1) as avg_runs,
            MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        """,
        params,
    )
    c = core[0] if core else {}
    total = c.get("total") or 0
    best = c.get("best_runs")

    highest = None
    if best:
        hi_rows = await db.q(
            f"""
            SELECT p.id, p.partnership_runs as runs, p.partnership_balls as balls,
                   p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                   m.id as match_id,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   i.team as team
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.partnership_runs = :best
            ORDER BY p.id
            LIMIT 1
            """,
            {**params, "best": best},
        )
        if hi_rows:
            r = hi_rows[0]
            highest = {
                "runs": r["runs"], "balls": r["balls"],
                "match_id": r["match_id"], "date": r["date"],
                "team": r["team"],
                "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
                "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
            }

    out = {
        "total": total,
        "count_50_plus": c.get("count_50_plus") or 0,
        "count_100_plus": c.get("count_100_plus") or 0,
        "avg_runs": c.get("avg_runs"),
        "highest": highest,
    }
    return _apply_partnerships_per_innings(out, await _live_innings_batted(filters, aux))


@router.get("/partnerships/by-wicket")
async def scope_partnerships_by_wicket(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-wicket league averages — runs / partnership at each wicket
    position. The `best_partnership` per wicket carries identity
    (specific pair + match)."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_by_wicket_from_baseline(filters, aux)
    return await _partnerships_by_wicket_live(filters, aux)


async def _partnerships_by_wicket_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    # Aggregate per wicket_number: SUM counters, MAX best_runs.
    agg_rows = await db.q(
        f"""
        SELECT wicket_number,
               SUM(n) AS n,
               SUM(total_runs) AS total_runs,
               SUM(total_balls) AS total_balls,
               COALESCE(MAX(best_runs), 0) AS best_runs
        FROM bucketbaselinepartnership {where}
        GROUP BY wicket_number ORDER BY wicket_number
        """,
        params,
    )
    # Per wicket, find the cell holding MAX(best_runs); then
    # _fetch_partnership_identity. One small SELECT per wicket
    # position (max 10 calls).
    by_wicket = []
    for r in agg_rows:
        wn = r["wicket_number"]
        best = None
        if r["best_runs"]:
            id_rows = await db.q(
                f"""
                SELECT best_pair_partnership_id
                FROM bucketbaselinepartnership {where}
                  AND wicket_number = :_wn AND best_runs > 0
                ORDER BY best_runs DESC, best_pair_partnership_id LIMIT 1
                """,
                {**params, "_wn": wn},
            )
            if id_rows:
                best = await _fetch_partnership_identity(db, id_rows[0]["best_pair_partnership_id"])
        n = r["n"] or 0
        by_wicket.append({
            "wicket_number": wn,
            "n": n,
            "avg_runs": round((r["total_runs"] or 0) / n, 1) if n else None,
            "avg_balls": round((r["total_balls"] or 0) / n, 1) if n else None,
            "best_runs": r["best_runs"] or 0,
            "best_partnership": best,
        })
    return _by_wicket_per_innings(by_wicket, await _baseline_innings_batted(filters, aux))


def _by_wicket_per_innings(rows: list[dict], innings_batted: int) -> dict:
    """Divide each by-wicket row's `n` count by innings_batted —
    spec-avg-column-per-innings.md `/scope/averages/partnerships/by-wicket`."""
    if innings_batted and innings_batted > 0:
        for r in rows:
            v = r.get("n")
            if v is not None:
                r["n"] = round(v / innings_batted, 2)
    return {"by_wicket": rows}


async def _partnerships_by_wicket_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT p.wicket_number,
               COUNT(*) as n,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               ROUND(AVG(p.partnership_balls), 1) as avg_balls,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY p.wicket_number
        ORDER BY p.wicket_number
        """,
        params,
    )

    by_wicket = []
    for r in rows:
        wn = r["wicket_number"]
        best = None
        if r["best_runs"]:
            best_rows = await db.q(
                f"""
                SELECT p.id as partnership_id, p.partnership_runs as runs,
                       p.partnership_balls as balls,
                       p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                       m.id as match_id, m.season, m.event_name as tournament,
                       i.team as team,
                       (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date
                FROM partnership p
                JOIN innings i ON i.id = p.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE {where}
                  AND p.wicket_number = :wn
                  AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
                  AND p.partnership_runs = :best
                ORDER BY p.id
                LIMIT 1
                """,
                {**params, "wn": wn, "best": r["best_runs"]},
            )
            if best_rows:
                bb = best_rows[0]
                best = {
                    "partnership_id": bb["partnership_id"],
                    "match_id": bb["match_id"],
                    "date": bb["date"],
                    "season": bb["season"],
                    "tournament": bb["tournament"],
                    "team": bb["team"],
                    "runs": bb["runs"],
                    "balls": bb["balls"],
                    "batter1": {"person_id": bb["batter1_id"], "name": bb["batter1_name"]},
                    "batter2": {"person_id": bb["batter2_id"], "name": bb["batter2_name"]},
                }
        by_wicket.append({
            "wicket_number": wn,
            "n": r["n"],
            "avg_runs": r["avg_runs"],
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"],
            "best_partnership": best,
        })
    return _by_wicket_per_innings(by_wicket, await _live_innings_batted(filters, aux))


@router.get("/partnerships/by-season")
async def scope_partnerships_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-season partnership aggregates across the whole league."""
    if is_precomputed_scope(filters, aux):
        return await _partnerships_by_season_from_baseline(filters, aux)
    return await _partnerships_by_season_live(filters, aux)


async def _partnerships_by_season_from_baseline(filters, aux):
    db = get_db()
    where, params = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(n) AS total,
               SUM(count_50_plus) AS count_50_plus,
               SUM(count_100_plus) AS count_100_plus,
               SUM(total_runs) AS total_runs,
               COALESCE(MAX(best_runs), 0) AS best_runs
        FROM bucketbaselinepartnership {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    # Per-season innings_batted divisor from bucketbaselinebatting (same scope).
    where_b, params_b = baseline_where(filters, aux, team=LEAGUE_TEAM_KEY)
    inn_rows = await db.q(
        f"SELECT season, SUM(innings_batted) AS innings_batted FROM bucketbaselinebatting {where_b} GROUP BY season",
        params_b,
    )
    inn_by_season = {r["season"]: r["innings_batted"] or 0 for r in inn_rows}
    out = []
    for r in rows:
        total = r["total"] or 0
        season = r["season"]
        row = {
            "season": season,
            "total": total,
            "count_50_plus": r["count_50_plus"] or 0,
            "count_100_plus": r["count_100_plus"] or 0,
            "avg_runs": round((r["total_runs"] or 0) / total, 1) if total else None,
            "best_runs": r["best_runs"],
        }
        out.append(_apply_partnerships_per_innings(row, inn_by_season.get(season, 0)))
    return {"by_season": out}


async def _partnerships_by_season_live(filters, aux):
    db = get_db()
    where, params = _partnership_filter(filters, None, "batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT m.season,
               COUNT(*) as total,
               SUM(CASE WHEN p.partnership_runs >= 50 THEN 1 ELSE 0 END) as count_50_plus,
               SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    # Per-season innings_batted divisor — same scope, side='batting'.
    where_inn, params_inn = _team_innings_clause(filters, None, side="batting", aux=aux)
    inn_rows = await db.q(
        f"""
        SELECT m.season, COUNT(DISTINCT i.id) AS innings_batted
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where_inn}
        GROUP BY m.season
        """,
        params_inn,
    )
    inn_by_season = {r["season"]: r["innings_batted"] or 0 for r in inn_rows}
    out = []
    for r in rows:
        season = r["season"]
        row = {
            "season": season,
            "total": r["total"] or 0,
            "count_50_plus": r["count_50_plus"] or 0,
            "count_100_plus": r["count_100_plus"] or 0,
            "avg_runs": r["avg_runs"],
            "best_runs": r["best_runs"],
        }
        out.append(_apply_partnerships_per_innings(row, inn_by_season.get(season, 0)))
    return {"by_season": out}


# ════════════════════════════════════════════════════════════════════
# /scope/averages/players/* — Phase 3 of spec-player-compare-average.md
# ════════════════════════════════════════════════════════════════════
#
# Position-adaptive cohort baseline endpoints. Each accepts a mix
# vector + the standard FilterBar axes (scope_key axes honoured;
# venue/team/opponent/team_class/series_type scope below the
# precomputed-table grain and are intentionally NOT applied — matches
# Phase 2's /summary distribution-array contract).
#
# Strict-cliff sliding scale: if any bucket the player has non-zero
# mix-weight on has a cohort sample below the bucket's threshold, the
# entire response's `scope_avg` is null. Convex combination over the
# player's full mix otherwise — no drops, no renormalisation.
# Spec §5.1 + §6.


@router.get("/players/batting/summary")
async def scope_players_batting_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    position_mix: str = Query(
        ...,
        description=(
            "Comma-separated 10-element vector of the player's mix"
            " across position buckets (1=opener for positions 1+2"
            " merged, 2=#3, ..., 10=#11). Must sum to 1.0 +/- 0.001."
            " Trailing zeros may be omitted."
        ),
    ),
    drop: Optional[str] = Query(
        None,
        description=(
            "Comma-separated FilterBar axis names to mask before"
            " clause construction. Per-endpoint structural plumbing"
            " for tautology-prone cohort surfaces; unused for the"
            " player-compare baseline path. Recognised names:"
            " gender, team_type, tournament, season, filter_venue,"
            " filter_team, filter_opponent, team_class, series_type."
        ),
    ),
):
    """Position-mix-weighted cohort baseline for batting.

    Returns cohort metadata, strict-cliff flags, six envelope-wrapped
    headline metrics, and the per-bucket aggregates in by_position.
    """
    db = get_db()
    try:
        mix = parse_mix(position_mix, 10)
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    where, params = build_scope_clauses(filters, drop=drop_set)

    # Use a scope_key IN-subquery rather than a JOIN to playerscopestats.
    # SQLite's planner picks parent-first scan-and-search for the JOIN
    # form (~800ms unfiltered, ~97K join lookups); the IN-subquery form
    # runs an index seek on scope_key and aggregates in ~165ms.
    #
    # Parallel: launch the per-bucket aggregation and the pool-totals
    # query together via asyncio.gather. Two index scans rather than
    # two serial round-trips — unfiltered drops from ~520ms to ~280ms.
    main_sql = f"""
        SELECT pssp.position_bucket,
               SUM(pssp.innings)      AS innings,
               SUM(pssp.runs)         AS runs,
               SUM(pssp.legal_balls)  AS legal_balls,
               SUM(pssp.dismissals)   AS dismissals,
               SUM(pssp.fours)        AS fours,
               SUM(pssp.sixes)        AS sixes,
               SUM(pssp.dots)         AS dots,
               COUNT(DISTINCT pssp.person_id) AS n_players
        FROM playerscopestatsposition pssp
        WHERE pssp.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY pssp.position_bucket
        ORDER BY pssp.position_bucket
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT pssp.person_id) AS n_players,
               SUM(pssp.innings)              AS n_innings_total
        FROM playerscopestatsposition pssp
        WHERE pssp.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
    """
    rows, pool = await asyncio.gather(
        db.q(main_sql, params),
        db.q(pool_sql, params),
    )
    by_bucket = {r["position_bucket"]: r for r in rows}
    n_players_total = (pool[0].get("n_players") if pool else 0) or 0
    n_innings_total = (pool[0].get("n_innings_total") if pool else 0) or 0

    by_position: list[dict] = []
    for b in range(1, 11):
        r = by_bucket.get(b)
        threshold = batting_threshold(b)
        if r is None:
            by_position.append({
                "bucket": b, "label": batting_bucket_label(b),
                "n_innings": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "innings_per_player": None, "runs_per_player": None,
                "average": None, "strike_rate": None,
                "boundary_pct": None, "dot_pct": None,
            })
            continue
        innings = r["innings"] or 0
        runs = r["runs"] or 0
        balls = r["legal_balls"] or 0
        dismissals = r["dismissals"] or 0
        boundaries = (r["fours"] or 0) + (r["sixes"] or 0)
        dots = r["dots"] or 0
        n_p = r["n_players"] or 0
        by_position.append({
            "bucket": b, "label": batting_bucket_label(b),
            "n_innings": innings, "n_players": n_p, "threshold": threshold,
            "below_support": innings < threshold,
            "innings_per_player": round(innings / n_p, 2) if n_p else None,
            "runs_per_player":    round(runs / n_p, 2) if n_p else None,
            "average":            round(runs / dismissals, 2) if dismissals else None,
            "strike_rate":        round(runs / balls * 100, 1) if balls else None,
            "boundary_pct":       round(boundaries / balls * 100, 1) if balls else None,
            "dot_pct":            round(dots / balls * 100, 1) if balls else None,
        })

    # Strict-cliff gate.
    cliff_buckets: list[int] = [
        b for b in range(1, 11)
        if mix[b - 1] > 0 and by_position[b - 1]["below_support"]
    ]

    cohort_block = {
        "match_dimension": "position_mix",
        "position_mix": mix,
        "n_players": n_players_total,
        "n_innings_total": n_innings_total,
    }

    if cliff_buckets:
        return {
            "cohort": cohort_block,
            "below_support": True,
            "cliff_buckets": cliff_buckets,
            "innings_batted": wrap_metric(None, None, "bat_innings",     sample_size=n_innings_total),
            "runs":           wrap_metric(None, None, "bat_runs",        sample_size=n_innings_total),
            "average":        wrap_metric(None, None, "bat_average",     sample_size=n_innings_total),
            "strike_rate":    wrap_metric(None, None, "bat_strike_rate", sample_size=n_innings_total),
            "boundary_pct":   wrap_metric(None, None, "boundary_pct",    sample_size=n_innings_total),
            "dot_pct":        wrap_metric(None, None, "bat_dot_pct",     sample_size=n_innings_total),
            "by_position": by_position,
        }

    def cv(field: str) -> Optional[float]:
        return convex_combine(mix, {b: by_position[b - 1][field] for b in range(1, 11)})

    cc_innings = cv("innings_per_player")
    cc_runs    = cv("runs_per_player")
    cc_avg     = cv("average")
    cc_sr      = cv("strike_rate")
    cc_bp      = cv("boundary_pct")
    cc_dp      = cv("dot_pct")

    def _r(v: Optional[float], ndigits: int) -> Optional[float]:
        return round(v, ndigits) if v is not None else None

    return {
        "cohort": cohort_block,
        "below_support": False,
        "cliff_buckets": [],
        "innings_batted": wrap_metric(_r(cc_innings, 2), _r(cc_innings, 2), "bat_innings",     sample_size=n_innings_total),
        "runs":           wrap_metric(_r(cc_runs, 2),    _r(cc_runs, 2),    "bat_runs",        sample_size=n_innings_total),
        "average":        wrap_metric(_r(cc_avg, 2),     _r(cc_avg, 2),     "bat_average",     sample_size=n_innings_total),
        "strike_rate":    wrap_metric(_r(cc_sr, 1),      _r(cc_sr, 1),      "bat_strike_rate", sample_size=n_innings_total),
        "boundary_pct":   wrap_metric(_r(cc_bp, 1),      _r(cc_bp, 1),      "boundary_pct",    sample_size=n_innings_total),
        "dot_pct":        wrap_metric(_r(cc_dp, 1),      _r(cc_dp, 1),      "bat_dot_pct",     sample_size=n_innings_total),
        "by_position": by_position,
    }


@router.get("/players/bowling/summary")
async def scope_players_bowling_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    over_mix: str = Query(
        ...,
        description=(
            "Comma-separated 20-element vector of the bowler's mix"
            " across overs 1..20. Must sum to 1.0 +/- 0.001."
            " Trailing zeros may be omitted."
        ),
    ),
    drop: Optional[str] = Query(
        None,
        description=(
            "Comma-separated FilterBar axis names to mask before"
            " clause construction. Recognised: gender, team_type,"
            " tournament, season, filter_venue, filter_team,"
            " filter_opponent, team_class, series_type."
        ),
    ),
):
    """Over-mix-weighted cohort baseline for bowling.

    Returns cohort metadata, strict-cliff flags, five envelope-wrapped
    headline rates (economy, average, strike_rate, dot_pct,
    wickets_per_over), and per-over aggregates in by_over[20].

    Sliding-scale thresholds on cohort `legal_balls` per over:
    U-shape (60-50-30-50-60). Any over the bowler has non-zero
    mix-weight on must be at or above its threshold; otherwise the
    entire response's scope_avg is null.
    """
    db = get_db()
    try:
        mix = parse_mix(over_mix, 20)
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    where, params = build_scope_clauses(filters, drop=drop_set)

    main_sql = f"""
        SELECT psso.over_number,
               SUM(psso.runs_conceded) AS runs_conceded,
               SUM(psso.legal_balls)   AS legal_balls,
               SUM(psso.wickets)       AS wickets,
               SUM(psso.dots)          AS dots,
               SUM(psso.boundaries)    AS boundaries,
               COUNT(DISTINCT psso.person_id) AS n_players
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
        GROUP BY psso.over_number
        ORDER BY psso.over_number
    """
    pool_sql = f"""
        SELECT COUNT(DISTINCT psso.person_id) AS n_players,
               SUM(psso.legal_balls)           AS n_balls_total
        FROM playerscopestatsover psso
        WHERE psso.scope_key IN (
            SELECT scope_key FROM playerscopestats pss WHERE {where}
        )
    """
    rows, pool = await asyncio.gather(
        db.q(main_sql, params),
        db.q(pool_sql, params),
    )
    by_over = {r["over_number"]: r for r in rows}
    n_players_total = (pool[0].get("n_players") if pool else 0) or 0
    n_balls_total = (pool[0].get("n_balls_total") if pool else 0) or 0

    by_over_arr: list[dict] = []
    for o in range(1, 21):
        r = by_over.get(o)
        threshold = bowling_threshold(o)
        if r is None:
            by_over_arr.append({
                "over": o, "label": bowling_bucket_label(o),
                "n_balls": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "economy": None, "average": None, "strike_rate": None,
                "dot_pct": None, "wickets_per_over": None,
                "boundary_pct": None,
            })
            continue
        balls = r["legal_balls"] or 0
        runs = r["runs_conceded"] or 0
        wickets = r["wickets"] or 0
        dots = r["dots"] or 0
        boundaries = r["boundaries"] or 0
        by_over_arr.append({
            "over": o, "label": bowling_bucket_label(o),
            "n_balls": balls, "n_players": r["n_players"] or 0,
            "threshold": threshold,
            "below_support": balls < threshold,
            "economy":          round(runs * 6 / balls, 2)            if balls else None,
            "average":          round(runs / wickets, 2)              if wickets else None,
            "strike_rate":      round(balls / wickets, 2)             if wickets else None,
            "dot_pct":          round(dots / balls * 100, 1)          if balls else None,
            "wickets_per_over": round(wickets * 6 / balls, 3)         if balls else None,
            "boundary_pct":     round(boundaries / balls * 100, 1)    if balls else None,
        })

    cliff_buckets: list[int] = [
        o for o in range(1, 21)
        if mix[o - 1] > 0 and by_over_arr[o - 1]["below_support"]
    ]

    cohort_block = {
        "match_dimension": "over_mix",
        "over_mix": mix,
        "n_players": n_players_total,
        "n_balls_total": n_balls_total,
    }

    if cliff_buckets:
        return {
            "cohort": cohort_block,
            "below_support": True,
            "cliff_buckets": cliff_buckets,
            "economy":          wrap_metric(None, None, "bowl_economy",      sample_size=n_balls_total),
            "average":          wrap_metric(None, None, "bowl_average",      sample_size=n_balls_total),
            "strike_rate":      wrap_metric(None, None, "bowl_strike_rate",  sample_size=n_balls_total),
            "dot_pct":          wrap_metric(None, None, "bowl_dot_pct",      sample_size=n_balls_total),
            "wickets_per_over": wrap_metric(None, None, "bowl_wickets_per_over", sample_size=n_balls_total),
            "boundary_pct":     wrap_metric(None, None, "bowl_boundary_pct", sample_size=n_balls_total),
            "by_over": by_over_arr,
        }

    def cv(field: str) -> Optional[float]:
        return convex_combine(mix, {o: by_over_arr[o - 1][field] for o in range(1, 21)})

    cc_econ = cv("economy")
    cc_avg  = cv("average")
    cc_sr   = cv("strike_rate")
    cc_dp   = cv("dot_pct")
    cc_wpo  = cv("wickets_per_over")
    cc_bp   = cv("boundary_pct")

    def _r(v: Optional[float], ndigits: int) -> Optional[float]:
        return round(v, ndigits) if v is not None else None

    return {
        "cohort": cohort_block,
        "below_support": False,
        "cliff_buckets": [],
        "economy":          wrap_metric(_r(cc_econ, 2), _r(cc_econ, 2), "bowl_economy",         sample_size=n_balls_total),
        "average":          wrap_metric(_r(cc_avg, 2),  _r(cc_avg, 2),  "bowl_average",         sample_size=n_balls_total),
        "strike_rate":      wrap_metric(_r(cc_sr, 2),   _r(cc_sr, 2),   "bowl_strike_rate",     sample_size=n_balls_total),
        "dot_pct":          wrap_metric(_r(cc_dp, 1),   _r(cc_dp, 1),   "bowl_dot_pct",         sample_size=n_balls_total),
        "wickets_per_over": wrap_metric(_r(cc_wpo, 3),  _r(cc_wpo, 3),  "bowl_wickets_per_over", sample_size=n_balls_total),
        "boundary_pct":     wrap_metric(_r(cc_bp, 1),   _r(cc_bp, 1),   "bowl_boundary_pct",    sample_size=n_balls_total),
        "by_over": by_over_arr,
    }


@router.get("/players/fielding/summary")
async def scope_players_fielding_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    is_keeper: int = Query(
        ...,
        description=(
            "Binary axis. 0 = outfielder cohort (pss.matches_as_keeper"
            " = 0); 1 = keeper cohort (pss.matches_as_keeper > 0)."
            " Spec §5.4 — fielding is NOT position-weighted at the"
            " headline; the partition is on this binary instead."
        ),
        ge=0, le=1,
    ),
    drop: Optional[str] = Query(
        None,
        description="See batting/summary for recognised axis names.",
    ),
):
    """Keeper-flag-partitioned cohort baseline for fielding.

    Returns per-match rates (catches, stumpings, run_outs, total
    dismissals — all higher=better) over the partition selected by
    is_keeper. Substitute catches are EXCLUDED from the numerator
    (Spec §5.2 + CLAUDE.md). Per-dismissed-position cohort sub-rates
    are returned in by_dismissed_position[10] for next-spec impact-
    weighted analyses; this headline doesn't weight by position.
    """
    db = get_db()
    try:
        drop_set = parse_drop(drop)
        if drop_set is not None:
            from ..filters import _DROP_AXES
            unknown = drop_set - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"drop= contains unknown axis name(s): {sorted(unknown)}."
                    f" Recognised: {sorted(_DROP_AXES)}."
                )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    where, params = build_scope_clauses(filters, drop=drop_set)

    # Cohort partition: matches_as_keeper > 0 selects keepers; = 0
    # selects pure outfielders. Subtotals over `catches`, `stumpings`,
    # `runouts`, `matches` aggregated from parent playerscopestats —
    # non-substitute numerator comes from the fielding-position child
    # in parallel (substitute fielders excluded there at populate).
    # The keeper-flag partition is PER (person, scope) — a player who
    # kept in 2023 but not 2024 belongs to the outfielder cohort for
    # 2024 only. Use a JOIN so the matches_as_keeper predicate gates
    # at the right grain rather than IN-subquery which leaks across
    # scope_keys for one person.
    keeper_pred = ">" if is_keeper else "="
    pool_sql = f"""
        SELECT COUNT(*)                       AS n_fielders,
               SUM(pss.matches)               AS n_matches_total
        FROM playerscopestats pss
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
    """
    # Non-substitute catches/stumpings/run_outs from the fielding-
    # position child, joined per-row to the parent keeper-partition.
    nonsub_sql = f"""
        SELECT SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
    """
    by_dis_pos_sql = f"""
        SELECT pssfp.position_bucket,
               SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals,
               COUNT(DISTINCT pssfp.person_id) AS n_players
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.person_id = pssfp.person_id
         AND pss.scope_key = pssfp.scope_key
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {where}
        GROUP BY pssfp.position_bucket
        ORDER BY pssfp.position_bucket
    """

    pool, nonsub, by_dis_rows = await asyncio.gather(
        db.q(pool_sql, params),
        db.q(nonsub_sql, params),
        db.q(by_dis_pos_sql, params),
    )

    n_fielders = (pool[0].get("n_fielders") if pool else 0) or 0
    n_matches = (pool[0].get("n_matches_total") if pool else 0) or 0

    nonsub_catches    = (nonsub[0].get("catches") if nonsub else 0) or 0
    nonsub_stumpings  = (nonsub[0].get("stumpings") if nonsub else 0) or 0
    nonsub_run_outs   = (nonsub[0].get("run_outs") if nonsub else 0) or 0
    nonsub_dismissals = (nonsub[0].get("dismissals") if nonsub else 0) or 0

    def _r(num: int, den: int, ndigits: int) -> Optional[float]:
        return round(num / den, ndigits) if den else None

    catches_pm    = _r(nonsub_catches,    n_matches, 3)
    stumpings_pm  = _r(nonsub_stumpings,  n_matches, 3)
    run_outs_pm   = _r(nonsub_run_outs,   n_matches, 3)
    dismissals_pm = _r(nonsub_dismissals, n_matches, 3)

    # by_dismissed_position — per-bucket cohort sub-rates for next-spec.
    by_dis: list[dict] = []
    by_dis_by_bucket = {r["position_bucket"]: r for r in by_dis_rows}
    for b in range(1, 11):
        r = by_dis_by_bucket.get(b)
        threshold = fielding_threshold(b)
        if r is None:
            by_dis.append({
                "bucket": b, "label": fielding_bucket_label(b),
                "n_dismissals": 0, "n_players": 0, "threshold": threshold,
                "below_support": True,
                "catches_per_match": None, "stumpings_per_match": None,
                "run_outs_per_match": None, "dismissals_per_match": None,
            })
            continue
        dis = r["dismissals"] or 0
        by_dis.append({
            "bucket": b, "label": fielding_bucket_label(b),
            "n_dismissals": dis, "n_players": r["n_players"] or 0,
            "threshold": threshold,
            "below_support": dis < threshold,
            "catches_per_match":    _r(r["catches"] or 0, n_matches, 4),
            "stumpings_per_match":  _r(r["stumpings"] or 0, n_matches, 4),
            "run_outs_per_match":   _r(r["run_outs"] or 0, n_matches, 4),
            "dismissals_per_match": _r(dis, n_matches, 4),
        })

    cohort_block = {
        "match_dimension": "is_keeper",
        "is_keeper": is_keeper,
        "n_fielders": n_fielders,
        "n_matches_total": n_matches,
    }

    # No per-headline cliff for fielding (spec §5.4): the binary
    # is_keeper axis isn't a sliding-scale dimension. The
    # by_dismissed_position[].below_support flags surface for the
    # next-spec impact-weighted analyses to consume.
    return {
        "cohort": cohort_block,
        "catches_per_match":    wrap_metric(catches_pm,    catches_pm,    "field_catches_per_match",    sample_size=n_matches),
        "stumpings_per_match":  wrap_metric(stumpings_pm,  stumpings_pm,  "field_stumpings_per_match",  sample_size=n_matches),
        "run_outs_per_match":   wrap_metric(run_outs_pm,   run_outs_pm,   "field_run_outs_per_match",   sample_size=n_matches),
        "dismissals_per_match": wrap_metric(dismissals_pm, dismissals_pm, "field_dismissals_per_match", sample_size=n_matches),
        "by_dismissed_position": by_dis,
    }
