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

from fastapi import APIRouter, Depends, Query

from ..filters import FilterParams, AuxParams
from ..dependencies import get_db
from .teams import (
    _team_innings_clause, _partnership_filter, _safe_div,
)

router = APIRouter(prefix="/api/v1/scope/averages", tags=["Scope-Averages"])


# ============================================================
# Summary (results / toss style — match-level aggregates)
# ============================================================

@router.get("/summary")
async def scope_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """League-scope match-level totals + toss/bat-first signals.

    Many fields from `/teams/{team}/summary` aren't meaningful for the
    league average (per-team `wins/losses/win_pct` collapse to ~50/50
    over the whole field). The endpoint still returns them so the
    response shape is symmetric with the team sibling — the frontend
    chooses which rows to render in the average column.
    """
    db = get_db()
    # Match-level filter only (no innings join).
    filters.team = None
    where, params = filters.build(has_innings_join=False, aux=aux)
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
    matches = r.get("matches", 0) or 0
    decided = r.get("decided", 0) or 0
    bf = r.get("bat_first_wins", 0) or 0
    ff = r.get("field_first_wins", 0) or 0
    bf_pct = round(bf * 100 / decided, 1) if decided > 0 else None

    return {
        "matches": matches,
        "decided": decided,
        "ties": r.get("ties", 0) or 0,
        "no_results": r.get("no_results", 0) or 0,
        "toss_decided": r.get("toss_decided", 0) or 0,
        "bat_first_wins": bf,
        "field_first_wins": ff,
        "bat_first_win_pct": bf_pct,
    }


# ============================================================
# Batting
# ============================================================

@router.get("/batting/summary")
async def scope_batting_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope batting aggregates.

    Mirrors `/teams/{team}/batting/summary` but with team=None — every
    delivery in scope contributes to the pool. Rates (RR, boundary%,
    dot%) are pool-weighted (SUM/SUM) rather than mean-of-team-means.
    """
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

    return {
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


@router.get("/batting/by-phase")
async def scope_batting_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted phase splits (PP 0-5 / Mid 6-14 / Death 15-19)."""
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

    # Wickets per phase.
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

    OVER_RANGES = [
        ("powerplay", [1, 6]),
        ("middle",    [7, 15]),
        ("death",     [16, 20]),
    ]
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
    return {"by_phase": out}


@router.get("/batting/by-season")
async def scope_batting_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted batting aggregates per season — drives the season-
    trajectory strip in the Compare tab."""
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
    seasons = []
    for r in rows:
        runs = r["total_runs"] or 0
        balls = r["legal_balls"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        dots = r["dots"] or 0
        boundaries = fours + sixes
        seasons.append({
            "season": r["season"],
            "innings_batted": r["innings_batted"] or 0,
            "total_runs": runs,
            "legal_balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return {"by_season": seasons}


# ============================================================
# Bowling
# ============================================================

@router.get("/bowling/summary")
async def scope_bowling_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope bowling aggregates.

    Identical SQL pattern to the batting summary — 'fielding side'
    selects every delivery where someone was bowling, and at league
    scope that's just every delivery (no team filter to apply).
    """
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
    runs = c.get("runs_conceded") or 0
    balls = c.get("legal_balls") or 0
    dots = c.get("dots") or 0

    wkt_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        """,
        params,
    )
    wickets = wkt_rows[0]["wickets"] if wkt_rows else 0

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

    return {
        "innings_bowled": c.get("innings_bowled") or 0,
        "matches": matches,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs, balls, 6),
        "strike_rate": _safe_div(balls, wickets) if wickets else None,
        "average": _safe_div(runs, wickets) if wickets else None,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": c.get("fours_conceded") or 0,
        "sixes_conceded": c.get("sixes_conceded") or 0,
        "wides": c.get("wides") or 0,
        "noballs": c.get("noballs") or 0,
        "wides_per_match": _safe_div(c.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(c.get("noballs") or 0, matches, 1, 2),
    }


@router.get("/bowling/by-phase")
async def scope_bowling_by_phase(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling phase splits."""
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
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        GROUP BY phase
        """,
        params,
    )
    wkt_by_phase = {r["phase"]: r["wickets"] for r in wkt_rows if r["phase"]}

    OVER_RANGES = [
        ("powerplay", [1, 6]),
        ("middle",    [7, 15]),
        ("death",     [16, 20]),
    ]
    out = []
    for phase, ranges in OVER_RANGES:
        s = by_phase.get(phase) or {}
        runs = s.get("runs_conceded") or 0
        balls = s.get("balls") or 0
        fours = s.get("fours_conceded") or 0
        sixes = s.get("sixes_conceded") or 0
        dots = s.get("dots") or 0
        boundaries = fours + sixes
        out.append({
            "phase": phase,
            "overs_range": ranges,
            "runs_conceded": runs,
            "balls": balls,
            "economy": _safe_div(runs, balls, 6),
            "wickets": wkt_by_phase.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours_conceded": fours,
            "sixes_conceded": sixes,
        })
    return {"by_phase": out}


@router.get("/bowling/by-season")
async def scope_bowling_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted bowling aggregates per season."""
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
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        GROUP BY m.season
        """,
        params,
    )
    wkt_by_season = {r["season"]: r["wickets"] for r in wkt_rows}

    seasons = []
    for r in rows:
        runs = r["runs_conceded"] or 0
        balls = r["legal_balls"] or 0
        dots = r["dots"] or 0
        seasons.append({
            "season": r["season"],
            "innings_bowled": r["innings_bowled"] or 0,
            "runs_conceded": runs,
            "legal_balls": balls,
            "overs": round(balls / 6, 1) if balls else 0,
            "wickets": wkt_by_season.get(r["season"], 0),
            "economy": _safe_div(runs, balls, 6),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "boundaries_conceded": r["boundaries_conceded"] or 0,
        })
    return {"by_season": seasons}


# ============================================================
# Fielding
# ============================================================

@router.get("/fielding/summary")
async def scope_fielding_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted league-scope fielding aggregates.

    Per-match rates (catches_per_match etc.) are pool-weighted: total
    catches in scope / total matches in scope. The denominator is
    distinct matches that touched the filter, NOT distinct (team,
    match) pairs (which would inflate by 2 — every match has 2
    fielding sides).
    """
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
    catches = r.get("catches") or 0
    cnb = r.get("caught_and_bowled") or 0
    stumpings = r.get("stumpings") or 0
    run_outs = r.get("run_outs") or 0

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

    return {
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


@router.get("/fielding/by-season")
async def scope_fielding_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted fielding aggregates per season."""
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

    seasons = []
    for r in rows:
        catches = r["catches"] or 0
        stumpings = r["stumpings"] or 0
        run_outs = r["run_outs"] or 0
        m_count = matches_by_season.get(r["season"], 0)
        seasons.append({
            "season": r["season"],
            "matches": m_count,
            "catches": catches,
            "stumpings": stumpings,
            "run_outs": run_outs,
            "total_dismissals_contributed": catches + stumpings + run_outs,
            "catches_per_match": _safe_div(catches, m_count, 1, 2),
            "stumpings_per_match": _safe_div(stumpings, m_count, 1, 2),
            "run_outs_per_match": _safe_div(run_outs, m_count, 1, 2),
        })
    return {"by_season": seasons}


# ============================================================
# Partnerships
# ============================================================

@router.get("/partnerships/summary")
async def scope_partnerships_summary(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Pool-weighted partnership aggregates across the whole league.

    Mirrors `/teams/{team}/partnerships/summary` but `side` is irrelevant
    (every partnership counts toward the league baseline). The "best
    pair" lookup retains identity — there's a specific scope-wide
    leading pair.
    """
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

    return {
        "total": total,
        "count_50_plus": c.get("count_50_plus") or 0,
        "count_100_plus": c.get("count_100_plus") or 0,
        "avg_runs": c.get("avg_runs"),
        "highest": highest,
    }


@router.get("/partnerships/by-wicket")
async def scope_partnerships_by_wicket(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-wicket league averages — runs / partnership at each wicket
    position. The `best_partnership` per wicket carries identity
    (specific pair + match)."""
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
    return {"by_wicket": by_wicket}


@router.get("/partnerships/by-season")
async def scope_partnerships_by_season(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-season partnership aggregates across the whole league."""
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
    return {
        "by_season": [
            {
                "season": r["season"],
                "total": r["total"] or 0,
                "count_50_plus": r["count_50_plus"] or 0,
                "count_100_plus": r["count_100_plus"] or 0,
                "avg_runs": r["avg_runs"],
                "best_runs": r["best_runs"],
            }
            for r in rows
        ],
    }
