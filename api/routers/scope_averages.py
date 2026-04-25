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
    _team_innings_clause, _partnership_filter, _scope_to_team_clause, _safe_div,
)
from .bucket_baseline_dispatch import (
    is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY,
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
    return _format_batting_summary(highest_total=highest, **{k: r.get(k) for k in (
        "innings_batted", "total_runs", "legal_balls", "fours", "sixes", "dots",
        "first_inn_runs_sum", "first_inn_count",
        "second_inn_runs_sum", "second_inn_count",
    )})


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
    return {"by_phase": out}


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
    return {"by_phase": out}


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
    return {
        "season": season,
        "innings_batted": innings_batted or 0,
        "total_runs": runs,
        "legal_balls": balls,
        "run_rate": _safe_div(runs, balls, 6),
        "boundary_pct": _safe_div(boundaries, balls, 100, 1),
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
    }


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
    return {
        "innings_bowled": innings_bowled or 0,
        "matches": matches,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs, balls, 6),
        "strike_rate": _safe_div(balls, wickets) if wickets else None,
        "average": _safe_div(runs, wickets) if wickets else None,
        "dot_pct": _safe_div(dots, balls, 100, 1),
        "fours_conceded": fours_conceded or 0,
        "sixes_conceded": sixes_conceded or 0,
        "wides": wides or 0,
        "noballs": noballs or 0,
        "wides_per_match": _safe_div(wides or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(noballs or 0, matches, 1, 2),
    }


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
    return {"by_phase": [
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
    ]}


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

    return {"by_phase": [
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
    ]}


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
    return {
        "season": season,
        "innings_bowled": innings_bowled or 0,
        "runs_conceded": runs,
        "legal_balls": balls,
        "overs": round(balls / 6, 1) if balls else 0,
        "wickets": wickets or 0,
        "economy": _safe_div(runs, balls, 6),
        "dot_pct": _safe_div(dots or 0, balls, 100, 1),
        "boundaries_conceded": boundaries_conceded or 0,
    }


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


def _format_fielding_summary(matches, catches_only, caught_and_bowled, stumpings, run_outs):
    matches = matches or 0
    catches_only = catches_only or 0
    cnb = caught_and_bowled or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    catches = catches_only + cnb  # response.catches includes c_a_b
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
    return _format_fielding_summary(
        matches=r.get("matches"),
        catches_only=r.get("catches_only"),
        caught_and_bowled=r.get("caught_and_bowled"),
        stumpings=r.get("stumpings"),
        run_outs=r.get("run_outs"),
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
    return _format_fielding_summary(
        matches=matches,
        catches_only=catches_with_cnb - cnb,
        caught_and_bowled=cnb,
        stumpings=r.get("stumpings") or 0,
        run_outs=r.get("run_outs") or 0,
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


def _format_fielding_season_row(season, matches, catches, stumpings, run_outs):
    matches = matches or 0
    catches = catches or 0
    stumpings = stumpings or 0
    run_outs = run_outs or 0
    return {
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
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=m_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
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
    return {"by_season": [
        _format_fielding_season_row(
            season=r["season"], matches=matches_by_season.get(r["season"], 0),
            catches=r["catches"], stumpings=r["stumpings"], run_outs=r["run_outs"],
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
    return {
        "total": total,
        "count_50_plus": r.get("count_50_plus") or 0,
        "count_100_plus": r.get("count_100_plus") or 0,
        "avg_runs": avg_runs,
        "highest": highest,
    }


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
    return {"by_wicket": by_wicket}


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
    return {"by_wicket": by_wicket}


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
    return {"by_season": [
        {
            "season": r["season"],
            "total": r["total"] or 0,
            "count_50_plus": r["count_50_plus"] or 0,
            "count_100_plus": r["count_100_plus"] or 0,
            "avg_runs": round((r["total_runs"] or 0) / r["total"], 1) if r["total"] else None,
            "best_runs": r["best_runs"],
        }
        for r in rows
    ]}


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
