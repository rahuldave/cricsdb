"""Teams router — team records, results, head-to-head, by-season."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])


def _team_filter_clause(filters: FilterParams, team_param: str = ":team") -> tuple[str, dict]:
    """Build match-level filter clause for team queries (no innings join)."""
    where, params = filters.build(has_innings_join=False)
    parts = [f"(m.team1 = {team_param} OR m.team2 = {team_param})"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


@router.get("/{team}/summary")
async def team_summary(
    team: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    filt, params = _team_filter_clause(filters)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
            SUM(CASE WHEN m.toss_winner = :team THEN 1 ELSE 0 END) as toss_wins,
            SUM(CASE WHEN m.outcome_winner = :team AND m.toss_decision = 'bat'
                     AND m.toss_winner = :team THEN 1
                     WHEN m.outcome_winner = :team AND m.toss_decision = 'field'
                     AND m.toss_winner != :team THEN 1
                     ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN m.outcome_winner = :team AND m.toss_decision = 'field'
                     AND m.toss_winner = :team THEN 1
                     WHEN m.outcome_winner = :team AND m.toss_decision = 'bat'
                     AND m.toss_winner != :team THEN 1
                     ELSE 0 END) as field_first_wins
        FROM match m
        WHERE {filt}
        """,
        params,
    )
    row = rows[0] if rows else {}
    matches = row.get("matches", 0) or 0
    wins = row.get("wins", 0) or 0
    win_pct = round(wins * 100 / matches, 1) if matches > 0 else 0

    # Gender breakdown — only when no gender filter is active. Lets the
    # frontend warn the user when a team has matches in both men's and
    # women's cricket and they're seeing combined stats. Identical
    # filter scope to the main query, just grouped by gender.
    gender_breakdown = None
    if filters.gender is None:
        gb_rows = await db.q(
            f"""
            SELECT m.gender as gender, COUNT(*) as n
            FROM match m
            WHERE {filt}
            GROUP BY m.gender
            """,
            params,
        )
        gb = {r["gender"]: r["n"] for r in gb_rows if r["gender"]}
        male = gb.get("male", 0)
        female = gb.get("female", 0)
        # Only surface when BOTH sides have matches in the current
        # filter scope — otherwise there's nothing to disambiguate.
        if male > 0 and female > 0:
            gender_breakdown = {"male": male, "female": female}

    # Tier 2 — keepers used by this team (fielding innings where
    # keeper_assignment picked someone, grouped by that someone).
    # Match-level filters apply via params (already include :team).
    k_filt, k_params = filters.build(has_innings_join=True)
    k_params["team"] = team
    # The FIELDING team = NOT the batting team; team_filt ensures the
    # match involves this side, and i.team != :team means we're looking
    # at innings where the OTHER side was batting (i.e. our team fielding).
    k_parts = [
        "(m.team1 = :team OR m.team2 = :team)",
        "i.team != :team",
    ]
    if k_filt:
        k_parts.append(k_filt)
    k_clause = " AND ".join(k_parts)

    keepers_rows = await db.q(
        f"""
        SELECT ka.keeper_id, p.name, COUNT(*) as innings_kept
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN person p ON p.id = ka.keeper_id
        WHERE ka.keeper_id IS NOT NULL AND {k_clause}
        GROUP BY ka.keeper_id, p.name
        ORDER BY innings_kept DESC
        """,
        k_params,
    )
    keepers = [
        {"person_id": r["keeper_id"], "name": r["name"], "innings_kept": r["innings_kept"]}
        for r in keepers_rows
    ]

    ambig_rows = await db.q(
        f"""
        SELECT COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE ka.keeper_id IS NULL AND {k_clause}
        """,
        k_params,
    )
    keeper_ambiguous = ambig_rows[0]["c"] if ambig_rows else 0

    return {
        "team": team,
        "matches": matches,
        "wins": wins,
        "losses": row.get("losses", 0) or 0,
        "ties": row.get("ties", 0) or 0,
        "no_results": row.get("no_results", 0) or 0,
        "win_pct": win_pct,
        "toss_wins": row.get("toss_wins", 0) or 0,
        "bat_first_wins": row.get("bat_first_wins", 0) or 0,
        "field_first_wins": row.get("field_first_wins", 0) or 0,
        "gender_breakdown": gender_breakdown,
        "keepers": keepers,
        "keeper_ambiguous_innings": keeper_ambiguous,
    }


@router.get("/{team}/results")
async def team_results(
    team: str,
    filters: FilterParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    filt, params = _team_filter_clause(filters)
    params["team"] = team
    params["limit"] = limit
    params["offset"] = offset

    # total count
    count_rows = await db.q(
        f"SELECT COUNT(*) as total FROM match m WHERE {filt}", params
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = await db.q(
        f"""
        SELECT
            m.id as match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = m.id ORDER BY md.date LIMIT 1) as date,
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
            m.venue,
            m.city,
            m.event_name as tournament,
            m.toss_winner,
            m.toss_decision,
            CASE
                WHEN m.outcome_winner = :team THEN 'won'
                WHEN m.outcome_winner IS NOT NULL AND m.outcome_winner != :team THEN 'lost'
                WHEN m.outcome_result = 'tie' THEN 'tied'
                WHEN m.outcome_result = 'no result' THEN 'no result'
                ELSE 'no result'
            END as result,
            CASE
                WHEN m.outcome_by_runs IS NOT NULL THEN CAST(m.outcome_by_runs AS TEXT) || ' runs'
                WHEN m.outcome_by_wickets IS NOT NULL THEN CAST(m.outcome_by_wickets AS TEXT) || ' wickets'
                ELSE NULL
            END as margin,
            m.player_of_match
        FROM match m
        WHERE {filt}
        ORDER BY date DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    return {"results": rows, "total": total}


@router.get("/{team}/vs/{opponent}")
async def team_vs_opponent(
    team: str,
    opponent: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    base_where, params = filters.build(has_innings_join=False)
    params["team"] = team
    params["opponent"] = opponent

    match_clause = (
        "(m.team1 = :team OR m.team2 = :team) AND "
        "(m.team1 = :opponent OR m.team2 = :opponent)"
    )
    if base_where:
        match_clause += f" AND {base_where}"

    # Overall record
    overall_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner = :opponent THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {match_clause}
        """,
        params,
    )
    overall = overall_rows[0] if overall_rows else {}

    # By season
    by_season = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner = :opponent THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {match_clause}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    # Match list
    matches = await db.q(
        f"""
        SELECT
            m.id as match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = m.id ORDER BY md.date LIMIT 1) as date,
            m.venue,
            m.event_name as tournament,
            CASE
                WHEN m.outcome_winner = :team THEN 'won'
                WHEN m.outcome_winner = :opponent THEN 'lost'
                WHEN m.outcome_result = 'tie' THEN 'tied'
                ELSE 'no result'
            END as result,
            CASE
                WHEN m.outcome_by_runs IS NOT NULL THEN CAST(m.outcome_by_runs AS TEXT) || ' runs'
                WHEN m.outcome_by_wickets IS NOT NULL THEN CAST(m.outcome_by_wickets AS TEXT) || ' wickets'
                ELSE NULL
            END as margin
        FROM match m
        WHERE {match_clause}
        ORDER BY date DESC
        """,
        params,
    )

    return {
        "team": team,
        "opponent": opponent,
        "overall": overall,
        "by_season": by_season,
        "matches": matches,
    }


@router.get("/{team}/opponents-matrix")
async def team_opponents_matrix(
    team: str,
    filters: FilterParams = Depends(),
    top_n: int = Query(20, ge=1, le=200),
):
    """Opponents × seasons win-matrix for the Teams > vs Opponent tab.

    Returns:
      - `opponents`: top-N opponents by total matches with W/L/T totals
        (the "who we play most" rollup for the stacked bar).
      - `seasons`: sorted list of seasons present in scope.
      - `cells`: one entry per (opponent, season) with matches/wins/
        losses/ties/win_pct — feeds the heatmap. Only cells for the
        top-N opponents are returned (noise suppression).
    """
    db = get_db()
    filt, params = _team_filter_clause(filters)
    params["team"] = team

    # Rollup — per opponent totals
    rollup = await db.q(
        f"""
        SELECT
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {filt}
        GROUP BY opponent
        ORDER BY matches DESC
        """,
        params,
    )
    top_opponents = [r["opponent"] for r in rollup[:top_n]]

    opponents = []
    for r in rollup[:top_n]:
        matches = r["matches"] or 0
        wins = r["wins"] or 0
        opponents.append({
            "name": r["opponent"],
            "matches": matches,
            "wins": wins,
            "losses": r["losses"] or 0,
            "ties": r["ties"] or 0,
            "no_results": r["no_results"] or 0,
            "win_pct": round(wins * 100 / matches, 1) if matches > 0 else None,
        })

    # Cells — one per (opponent, season) for top-N opponents
    cells = []
    seasons_set: set[str] = set()
    if top_opponents:
        opp_list = ",".join(f"'{o.replace(chr(39), chr(39)+chr(39))}'" for o in top_opponents)
        cell_rows = await db.q(
            f"""
            SELECT
                m.season,
                CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
                COUNT(*) as matches,
                SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN m.outcome_winner IS NOT NULL
                         AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties
            FROM match m
            WHERE {filt}
              AND (CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END) IN ({opp_list})
            GROUP BY m.season, opponent
            ORDER BY m.season, opponent
            """,
            params,
        )
        for r in cell_rows:
            season = r["season"]
            seasons_set.add(season)
            matches = r["matches"] or 0
            wins = r["wins"] or 0
            cells.append({
                "season": season,
                "opponent": r["opponent"],
                "matches": matches,
                "wins": wins,
                "losses": r["losses"] or 0,
                "ties": r["ties"] or 0,
                "win_pct": round(wins * 100 / matches, 1) if matches > 0 else None,
            })

    return {
        "team": team,
        "seasons": sorted(seasons_set),
        "opponents": opponents,
        "cells": cells,
    }


@router.get("/{team}/opponents")
async def team_opponents(
    team: str,
    filters: FilterParams = Depends(),
):
    """Return opponents the team has actually played (non-zero matches), respecting filters."""
    db = get_db()
    filt, params = _team_filter_clause(filters)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as name,
            COUNT(*) as matches
        FROM match m
        WHERE {filt}
        GROUP BY name
        ORDER BY matches DESC, name
        """,
        params,
    )
    return {"opponents": rows}


@router.get("/{team}/by-season")
async def team_by_season(
    team: str,
    filters: FilterParams = Depends(),
):
    db = get_db()
    filt, params = _team_filter_clause(filters)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {filt}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    seasons = []
    for r in rows:
        matches = r["matches"] or 0
        wins = r["wins"] or 0
        win_pct = round(wins * 100 / matches, 1) if matches > 0 else 0
        seasons.append({**r, "win_pct": win_pct})

    return {"seasons": seasons}


# ============================================================
# Team ball-level stats — batting, bowling, fielding, partnerships.
# See docs/spec-team-stats.md.
# ============================================================


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _team_innings_clause(
    filters: FilterParams, team: str, side: str = "batting",
) -> tuple[str, dict]:
    """Build WHERE clause for team-scoped innings queries.

    side='batting' → innings where :team batted (i.team = :team)
    side='fielding' → innings where :team was in the field (i.team != :team
                      AND :team is one of the match teams)

    The path :team takes precedence over any filter_team query param.
    """
    # Null out filter_team so our :team bind isn't clobbered. Each request
    # gets a fresh FilterParams via Depends() so this mutation is safe.
    filters.team = None
    where, params = filters.build(has_innings_join=True)
    params["team"] = team
    if side == "batting":
        parts = ["i.team = :team"]
    else:
        parts = ["i.team != :team", "(m.team1 = :team OR m.team2 = :team)"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


@router.get("/{team}/batting/summary")
async def team_batting_summary(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting")

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
    innings_batted = c.get("innings_batted") or 0
    total_runs = c.get("total_runs") or 0
    legal_balls = c.get("legal_balls") or 0
    fours = c.get("fours") or 0
    sixes = c.get("sixes") or 0
    dots = c.get("dots") or 0
    boundaries = fours + sixes

    # Per-innings totals (runs + balls + innings_number + whether all-out)
    innings_rows = await db.q(
        f"""
        SELECT
            i.id as innings_id, i.match_id, i.innings_number,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            (SELECT COUNT(*) FROM wicket w2
             JOIN delivery d2 ON d2.id = w2.delivery_id
             WHERE d2.innings_id = i.id
               AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_lost
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number
        """,
        params,
    )

    avg_1st = None
    avg_2nd = None
    first_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 0 and r["runs"] is not None]
    second_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 1 and r["runs"] is not None]
    if first_totals:
        avg_1st = round(sum(first_totals) / len(first_totals), 1)
    if second_totals:
        avg_2nd = round(sum(second_totals) / len(second_totals), 1)

    highest_total = None
    lowest_all_out = None
    if innings_rows:
        top = max(innings_rows, key=lambda r: r["runs"] or 0)
        highest_total = {
            "runs": top["runs"] or 0,
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }
        all_out = [r for r in innings_rows if (r["wickets_lost"] or 0) >= 10]
        if all_out:
            lo = min(all_out, key=lambda r: r["runs"] or 0)
            lowest_all_out = {
                "runs": lo["runs"] or 0,
                "match_id": lo["match_id"],
                "innings_number": lo["innings_number"] + 1,
            }

    # 50s / 100s count — aggregate from batter-level innings stats for
    # this team. Use delivery-level grouping so filter scope is respected.
    player_inn_rows = await db.q(
        f"""
        SELECT d.batter_id, i.id as innings_id,
               SUM(d.runs_batter) as r
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id, i.id
        """,
        params,
    )
    fifties = sum(1 for r in player_inn_rows if 50 <= (r["r"] or 0) < 100)
    hundreds = sum(1 for r in player_inn_rows if (r["r"] or 0) >= 100)

    return {
        "team": team,
        "innings_batted": innings_batted,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "fifties": fifties,
        "hundreds": hundreds,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
        "lowest_all_out_total": lowest_all_out,
    }


@router.get("/{team}/batting/by-season")
async def team_batting_by_season(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting")

    # Per-season aggregate deliveries
    season_rows = await db.q(
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

    # Per-innings totals for highest / lowest all-out
    innings_rows = await db.q(
        f"""
        SELECT
            m.season, i.id as innings_id,
            SUM(d.runs_total) as runs,
            (SELECT COUNT(*) FROM wicket w2
             JOIN delivery d2 ON d2.id = w2.delivery_id
             WHERE d2.innings_id = i.id
               AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_lost
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, i.id
        """,
        params,
    )
    by_season_innings: dict[str, list] = {}
    for r in innings_rows:
        by_season_innings.setdefault(r["season"], []).append(r)

    seasons = []
    for s in season_rows:
        season = s["season"]
        total_runs = s["total_runs"] or 0
        innings_batted = s["innings_batted"] or 0
        legal_balls = s["legal_balls"] or 0
        fours = s["fours"] or 0
        sixes = s["sixes"] or 0
        dots = s["dots"] or 0
        boundaries = fours + sixes

        inn_list = by_season_innings.get(season, [])
        highest = max((r["runs"] or 0 for r in inn_list), default=0)
        all_out = [r for r in inn_list if (r["wickets_lost"] or 0) >= 10]
        lowest_all_out = min((r["runs"] or 0 for r in all_out), default=None)

        seasons.append({
            "season": season,
            "innings_batted": innings_batted,
            "total_runs": total_runs,
            "legal_balls": legal_balls,
            "avg_innings_total": _safe_div(total_runs, innings_batted, 1, 1),
            "run_rate": _safe_div(total_runs, legal_balls, 6),
            "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
            "dot_pct": _safe_div(dots, legal_balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
            "highest_total": highest,
            "lowest_all_out_total": lowest_all_out,
        })

    return {"seasons": seasons}


@router.get("/{team}/batting/by-phase")
async def team_batting_by_phase(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting")

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )

    # Wickets lost per phase (same filter scope, but via wicket join)
    wicket_where, wicket_params = _team_innings_clause(filters, team, side="batting")
    wicket_rows = await db.q(
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
        WHERE {wicket_where}
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        wicket_params,
    )
    wicket_map = {r["phase"]: r["wickets_lost"] for r in wicket_rows}

    phase_ranges = {
        "powerplay": [1, 6],
        "middle": [7, 15],
        "death": [16, 20],
    }
    phases = []
    for r in rows:
        phase = r["phase"]
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        boundaries = fours + sixes
        phases.append({
            "phase": phase,
            "overs_range": phase_ranges.get(phase, []),
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wicket_map.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        })
    return {"phases": phases}


@router.get("/{team}/batting/top-batters")
async def team_top_batters(
    team: str,
    filters: FilterParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting")
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT d.batter_id as person_id, p.name,
               SUM(d.runs_batter) as runs,
               COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
               SUM(CASE WHEN d.runs_batter = 4
                        AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
               COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE {where} AND d.batter_id IS NOT NULL
        GROUP BY d.batter_id, p.name
        ORDER BY runs DESC
        LIMIT :lim
        """,
        params,
    )
    top = []
    for r in rows:
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        top.append({
            "person_id": r["person_id"],
            "name": r["name"] or r["person_id"],
            "runs": runs,
            "balls": balls,
            "strike_rate": _safe_div(runs, balls, 100),
            "fours": r["fours"] or 0,
            "sixes": r["sixes"] or 0,
            "innings": r["innings"] or 0,
        })
    return {"top_batters": top}


@router.get("/{team}/batting/phase-season-heatmap")
async def team_batting_phase_season_heatmap(
    team: str, filters: FilterParams = Depends(),
):
    """Season × phase matrix for batting — both run_rate and
    wickets_lost per cell, so the frontend can render two heatmaps
    from one round-trip.

    Cells: {season, phase, run_rate, wickets_lost, balls}.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting")

    rate_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, phase
        ORDER BY m.season
        """,
        params,
    )

    wicket_rows = await db.q(
        f"""
        SELECT
            m.season,
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
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season, phase
        """,
        params,
    )
    wmap = {(r["season"], r["phase"]): r["wickets_lost"] for r in wicket_rows}

    seasons, seen_s = [], set()
    cells = []
    for r in rate_rows:
        s = r["season"]
        if s not in seen_s:
            seen_s.add(s)
            seasons.append(s)
        balls = r["balls"] or 0
        innings = r["innings"] or 0
        wkts = wmap.get((s, r["phase"]), 0)
        cells.append({
            "season": s,
            "phase": r["phase"],
            "run_rate": round((r["runs"] or 0) * 6 / balls, 2) if balls else None,
            "wickets_lost": wkts,
            "wickets_per_innings": round(wkts / innings, 2) if innings else None,
            "innings": innings,
            "balls": balls,
        })
    seasons.sort()
    return {
        "team": team,
        "seasons": seasons,
        "phases": ["powerplay", "middle", "death"],
        "cells": cells,
    }


# Bowling wickets exclude these kinds — a run-out isn't credited to the
# bowler, nor are retirement/obstructing-the-field.
BOWLER_WICKET_EXCLUDE = "('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')"


@router.get("/{team}/bowling/summary")
async def team_bowling_summary(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            COUNT(*) as all_balls,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(d.extras_wides) as wides,
            SUM(d.extras_noballs) as noballs,
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
    runs_conceded = c.get("runs_conceded") or 0
    legal_balls = c.get("legal_balls") or 0
    innings_bowled = c.get("innings_bowled") or 0
    fours = c.get("fours_conceded") or 0
    sixes = c.get("sixes_conceded") or 0
    dots = c.get("dots") or 0

    # Wickets taken by bowlers on this team
    w_where = where  # same scope
    w_params = params.copy()
    wicket_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {w_where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        """,
        w_params,
    )
    wickets = wicket_rows[0]["wickets"] if wicket_rows else 0

    # Matches count for per-match averages
    match_count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    matches = match_count_rows[0]["matches"] if match_count_rows else 0

    # Opposition innings totals (for avg / worst conceded / best defence)
    opp_innings = await db.q(
        f"""
        SELECT i.id as innings_id, i.match_id, i.innings_number,
               SUM(d.runs_total) as runs,
               (SELECT COUNT(*) FROM wicket w2
                JOIN delivery d2 ON d2.id = w2.delivery_id
                WHERE d2.innings_id = i.id
                  AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_taken,
               m.outcome_winner
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number, m.outcome_winner
        """,
        params,
    )
    avg_opp_total = None
    if opp_innings:
        avg_opp_total = round(
            sum(r["runs"] or 0 for r in opp_innings) / len(opp_innings), 1
        )
    # Worst conceded: highest opposition total
    worst = None
    if opp_innings:
        top = max(opp_innings, key=lambda r: r["runs"] or 0)
        worst = {
            "runs": top["runs"] or 0,
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }
    # Best defence: lowest total successfully defended (team bowled 2nd,
    # bowled out opposition OR ran out overs with lower score than the
    # opposition's target). Simpler heuristic: innings where our team
    # WON (outcome_winner = :team), innings_number = 1 (chase failed),
    # lowest opposition runs.
    best_defence = None
    defended = [
        r for r in opp_innings
        if r["outcome_winner"] == team and r["innings_number"] == 1
    ]
    if defended:
        lo = min(defended, key=lambda r: r["runs"] or 0)
        best_defence = {
            "runs": lo["runs"] or 0,
            "match_id": lo["match_id"],
        }

    return {
        "team": team,
        "innings_bowled": innings_bowled,
        "matches": matches,
        "runs_conceded": runs_conceded,
        "legal_balls": legal_balls,
        "overs": round(legal_balls / 6, 1) if legal_balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs_conceded, legal_balls, 6),
        "strike_rate": _safe_div(legal_balls, wickets),
        "average": _safe_div(runs_conceded, wickets),
        "dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours_conceded": fours,
        "sixes_conceded": sixes,
        "wides": c.get("wides") or 0,
        "noballs": c.get("noballs") or 0,
        "wides_per_match": _safe_div(c.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(c.get("noballs") or 0, matches, 1, 2),
        "avg_opposition_total": avg_opp_total,
        "worst_conceded": worst,
        "best_defence": best_defence,
    }


@router.get("/{team}/bowling/by-season")
async def team_bowling_by_season(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    season_rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
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

    # Wickets per season
    w_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY m.season
        """,
        params,
    )
    wicket_map = {r["season"]: r["wickets"] for r in w_rows}

    # Opposition innings totals per season (for avg + worst)
    opp_inn_rows = await db.q(
        f"""
        SELECT m.season, i.id as innings_id,
               SUM(d.runs_total) as runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, i.id
        """,
        params,
    )
    by_season_opp: dict[str, list] = {}
    for r in opp_inn_rows:
        by_season_opp.setdefault(r["season"], []).append(r)

    seasons = []
    for s in season_rows:
        season = s["season"]
        runs_conc = s["runs_conceded"] or 0
        legal_balls = s["legal_balls"] or 0
        innings_bowled = s["innings_bowled"] or 0
        fours = s["fours_conceded"] or 0
        sixes = s["sixes_conceded"] or 0
        dots = s["dots"] or 0
        wickets = wicket_map.get(season, 0)
        opp_list = by_season_opp.get(season, [])
        avg_opp = round(sum(r["runs"] or 0 for r in opp_list) / len(opp_list), 1) if opp_list else None
        worst = max((r["runs"] or 0 for r in opp_list), default=0)

        seasons.append({
            "season": season,
            "innings_bowled": innings_bowled,
            "runs_conceded": runs_conc,
            "legal_balls": legal_balls,
            "overs": round(legal_balls / 6, 1) if legal_balls else 0,
            "wickets": wickets,
            "economy": _safe_div(runs_conc, legal_balls, 6),
            "avg_opposition_total": avg_opp,
            "dot_pct": _safe_div(dots, legal_balls, 100, 1),
            "boundaries_conceded": fours + sixes,
            "worst_conceded": worst,
        })

    return {"seasons": seasons}


@router.get("/{team}/bowling/by-phase")
async def team_bowling_by_phase(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )

    w_rows = await db.q(
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
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY phase
        """,
        params,
    )
    wicket_map = {r["phase"]: r["wickets"] for r in w_rows}

    phase_ranges = {
        "powerplay": [1, 6],
        "middle": [7, 15],
        "death": [16, 20],
    }
    phases = []
    for r in rows:
        phase = r["phase"]
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        phases.append({
            "phase": phase,
            "overs_range": phase_ranges.get(phase, []),
            "runs_conceded": runs,
            "balls": balls,
            "economy": _safe_div(runs, balls, 6),
            "wickets": wicket_map.get(phase, 0),
            "boundary_pct": _safe_div(fours + sixes, balls, 100, 1),
            "dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours_conceded": fours,
            "sixes_conceded": sixes,
        })
    return {"phases": phases}


@router.get("/{team}/bowling/top-bowlers")
async def team_top_bowlers(
    team: str,
    filters: FilterParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT d.bowler_id as person_id, p.name,
               SUM(d.runs_total) as runs_conceded,
               COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
               COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.bowler_id
        WHERE {where} AND d.bowler_id IS NOT NULL
        GROUP BY d.bowler_id, p.name
        ORDER BY balls DESC
        LIMIT :lim
        """,
        params,
    )

    # Wickets per bowler (separate query so we filter wicket-kind)
    w_rows = await db.q(
        f"""
        SELECT d.bowler_id as person_id, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
          AND d.bowler_id IS NOT NULL
        GROUP BY d.bowler_id
        """,
        params,
    )
    w_map = {r["person_id"]: r["wickets"] for r in w_rows}

    # Re-sort by wickets
    top = []
    for r in rows:
        pid = r["person_id"]
        balls = r["balls"] or 0
        runs = r["runs_conceded"] or 0
        wickets = w_map.get(pid, 0)
        top.append({
            "person_id": pid,
            "name": r["name"] or pid,
            "wickets": wickets,
            "runs_conceded": runs,
            "balls": balls,
            "overs": round(balls / 6, 1) if balls else 0,
            "economy": _safe_div(runs, balls, 6),
            "average": _safe_div(runs, wickets),
            "strike_rate": _safe_div(balls, wickets),
            "innings": r["innings"] or 0,
        })
    top.sort(key=lambda r: r["wickets"] or 0, reverse=True)
    return {"top_bowlers": top[:limit]}


@router.get("/{team}/bowling/phase-season-heatmap")
async def team_bowling_phase_season_heatmap(
    team: str, filters: FilterParams = Depends(),
):
    """Season × phase matrix for bowling — both economy and wickets
    per cell. Cells: {season, phase, economy, wickets, balls}."""
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    rate_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, phase
        ORDER BY m.season
        """,
        params,
    )

    wicket_rows = await db.q(
        f"""
        SELECT
            m.season,
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
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY m.season, phase
        """,
        params,
    )
    wmap = {(r["season"], r["phase"]): r["wickets"] for r in wicket_rows}

    seasons, seen_s = [], set()
    cells = []
    for r in rate_rows:
        s = r["season"]
        if s not in seen_s:
            seen_s.add(s)
            seasons.append(s)
        balls = r["balls"] or 0
        innings = r["innings"] or 0
        wkts = wmap.get((s, r["phase"]), 0)
        cells.append({
            "season": s,
            "phase": r["phase"],
            "economy": round((r["runs"] or 0) * 6 / balls, 2) if balls else None,
            "wickets": wkts,
            "wickets_per_innings": round(wkts / innings, 2) if innings else None,
            "innings": innings,
            "balls": balls,
        })
    seasons.sort()
    return {
        "team": team,
        "seasons": seasons,
        "phases": ["powerplay", "middle", "death"],
        "cells": cells,
    }


@router.get("/{team}/fielding/summary")
async def team_fielding_summary(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    # fielding_credit aggregation — fc joins via delivery, so we can reuse
    # the delivery-level clause directly.
    kind_rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        """,
        params,
    )
    by_kind = {r["kind"]: r["cnt"] for r in kind_rows}
    catches = by_kind.get("caught", 0)
    caught_and_bowled = by_kind.get("caught_and_bowled", 0)
    stumpings = by_kind.get("stumped", 0)
    run_outs = by_kind.get("run_out", 0)

    # Match count when this team was in the field
    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND i.team != :team
          AND (m.team1 = :team OR m.team2 = :team)
        """,
        {"team": team},
    )
    matches = match_rows[0]["matches"] if match_rows else 0

    return {
        "team": team,
        "matches": matches,
        "catches": catches,
        "caught_and_bowled": caught_and_bowled,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + caught_and_bowled + stumpings + run_outs,
        "catches_per_match": _safe_div(catches + caught_and_bowled, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }


@router.get("/{team}/fielding/by-season")
async def team_fielding_by_season(team: str, filters: FilterParams = Depends()):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")

    rows = await db.q(
        f"""
        SELECT m.season, fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, fc.kind
        ORDER BY m.season
        """,
        params,
    )

    # Matches per season (for per-match rates)
    match_rows = await db.q(
        """
        SELECT m.season, COUNT(DISTINCT m.id) as matches
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND i.team != :team
          AND (m.team1 = :team OR m.team2 = :team)
        GROUP BY m.season
        """,
        {"team": team},
    )
    match_map = {r["season"]: r["matches"] for r in match_rows}

    by_season: dict[str, dict] = {}
    for r in rows:
        s = r["season"]
        by_season.setdefault(s, {
            "season": s, "catches": 0, "caught_and_bowled": 0,
            "stumpings": 0, "run_outs": 0,
        })
        kind = r["kind"]
        cnt = r["cnt"]
        if kind == "caught":
            by_season[s]["catches"] = cnt
        elif kind == "caught_and_bowled":
            by_season[s]["caught_and_bowled"] = cnt
        elif kind == "stumped":
            by_season[s]["stumpings"] = cnt
        elif kind == "run_out":
            by_season[s]["run_outs"] = cnt

    seasons = []
    for s in sorted(by_season.keys()):
        row = by_season[s]
        matches = match_map.get(s, 0)
        total_catches = row["catches"] + row["caught_and_bowled"]
        seasons.append({
            **row,
            "matches": matches,
            "catches_per_match": _safe_div(total_catches, matches, 1, 2),
            "stumpings_per_match": _safe_div(row["stumpings"], matches, 1, 2),
            "run_outs_per_match": _safe_div(row["run_outs"], matches, 1, 2),
            "total_dismissals_contributed": (
                row["catches"] + row["caught_and_bowled"]
                + row["stumpings"] + row["run_outs"]
            ),
        })
    return {"seasons": seasons}


@router.get("/{team}/fielding/top-fielders")
async def team_top_fielders(
    team: str,
    filters: FilterParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding")
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT fc.fielder_id as person_id, p.name, fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = fc.fielder_id
        WHERE {where} AND fc.fielder_id IS NOT NULL
        GROUP BY fc.fielder_id, p.name, fc.kind
        """,
        params,
    )

    by_player: dict[str, dict] = {}
    for r in rows:
        pid = r["person_id"]
        if pid not in by_player:
            by_player[pid] = {
                "person_id": pid,
                "name": r["name"] or pid,
                "catches": 0, "caught_and_bowled": 0,
                "stumpings": 0, "run_outs": 0,
            }
        kind = r["kind"]
        if kind == "caught":
            by_player[pid]["catches"] = r["cnt"]
        elif kind == "caught_and_bowled":
            by_player[pid]["caught_and_bowled"] = r["cnt"]
        elif kind == "stumped":
            by_player[pid]["stumpings"] = r["cnt"]
        elif kind == "run_out":
            by_player[pid]["run_outs"] = r["cnt"]

    players = list(by_player.values())
    for p in players:
        p["total"] = (
            p["catches"] + p["caught_and_bowled"]
            + p["stumpings"] + p["run_outs"]
        )
    players.sort(key=lambda p: p["total"], reverse=True)
    return {"top_fielders": players[:limit]}


def _partnership_filter(filters: FilterParams, team: str, side: str):
    """Build WHERE clause for partnership table queries.

    side='batting' → partnerships when :team batted (i.team = :team)
    side='bowling' → partnerships against :team's bowling
                     (i.team != :team AND :team in match)
    """
    filters.team = None
    where, params = filters.build(has_innings_join=True)
    params["team"] = team
    if side == "batting":
        parts = ["i.team = :team"]
    else:
        parts = ["i.team != :team", "(m.team1 = :team OR m.team2 = :team)"]
    if where:
        parts.append(where)
    return " AND ".join(parts), params


def _validate_side(side: str) -> str:
    return side if side in ("batting", "bowling") else "batting"


@router.get("/{team}/partnerships/by-wicket")
async def team_partnerships_by_wicket(
    team: str,
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side)

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

    # Best partnership detail per wicket (one extra query, indexed lookup)
    by_wicket = []
    for r in rows:
        wn = r["wicket_number"]
        best_rows = await db.q(
            f"""
            SELECT p.id as partnership_id, p.partnership_runs as runs,
                   p.partnership_balls as balls,
                   p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                   p.batter1_runs, p.batter1_balls, p.batter2_runs, p.batter2_balls,
                   m.id as match_id, m.season, m.event_name as tournament,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as opponent
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
        best = best_rows[0] if best_rows else None
        by_wicket.append({
            "wicket_number": wn,
            "n": r["n"],
            "avg_runs": r["avg_runs"],
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"],
            "best_partnership": (
                {
                    "partnership_id": best["partnership_id"],
                    "match_id": best["match_id"],
                    "date": best["date"],
                    "season": best["season"],
                    "tournament": best["tournament"],
                    "opponent": best["opponent"],
                    "runs": best["runs"],
                    "balls": best["balls"],
                    "batter1": {
                        "person_id": best["batter1_id"],
                        "name": best["batter1_name"],
                        "runs": best["batter1_runs"],
                        "balls": best["batter1_balls"],
                    },
                    "batter2": {
                        "person_id": best["batter2_id"],
                        "name": best["batter2_name"],
                        "runs": best["batter2_runs"],
                        "balls": best["batter2_balls"],
                    },
                }
                if best else None
            ),
        })

    return {"team": team, "side": side, "by_wicket": by_wicket}


@router.get("/{team}/partnerships/best-pairs")
async def team_partnerships_best_pairs(
    team: str,
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
    min_n: int = Query(2, ge=1, le=20),
    top_n: int = Query(3, ge=1, le=10),
):
    """Per-wicket "most prolific pairs" — top-N pairs ranked by **total
    runs together** at that wicket. Captures both volume (how many
    partnerships) and quality (avg per partnership) — pure-average
    ranking gave a 5-game purple patch the same weight as a multi-year
    workhorse pair, missing the actual bread-and-butter combinations.

    For each (batterA, batterB) pair (canonicalized so order doesn't
    matter) at each wicket number, we compute:
      n           — number of partnerships together
      avg_runs    — average runs per partnership
      total_runs  — n × avg, the ranking metric
      best_runs   — single biggest partnership

    Returns top `top_n` pairs per wicket, requiring at least `min_n`
    partnerships together to qualify.

    Different from the by-wicket "best_partnership" which shows a
    single one-off blockbuster. For side='bowling', "pair" = the
    opposition pair that did best against us at that wicket.
    """
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side)
    params["min_n"] = min_n

    # Canonicalize pair (smaller id first) so AB+CD and CD+AB count as
    # one pair regardless of who arrived first.
    rows = await db.q(
        f"""
        SELECT
            wicket_number,
            CASE WHEN batter1_id < batter2_id THEN batter1_id ELSE batter2_id END as p1_id,
            CASE WHEN batter1_id < batter2_id THEN batter2_id ELSE batter1_id END as p2_id,
            COUNT(*) as n,
            ROUND(AVG(partnership_runs), 1) as avg_runs,
            ROUND(AVG(partnership_balls), 1) as avg_balls,
            MAX(partnership_runs) as best_runs,
            SUM(partnership_runs) as total_runs
        FROM (
            SELECT p.* FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.wicket_number IS NOT NULL
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.batter1_id IS NOT NULL
              AND p.batter2_id IS NOT NULL
        )
        GROUP BY wicket_number, p1_id, p2_id
        HAVING COUNT(*) >= :min_n
        ORDER BY wicket_number, total_runs DESC, avg_runs DESC
        """,
        params,
    )

    # Bucket top-N rows per wicket
    pairs_per_wicket: dict[int, list[dict]] = {}
    for r in rows:
        wn = r["wicket_number"]
        bucket = pairs_per_wicket.setdefault(wn, [])
        if len(bucket) < top_n:
            bucket.append(r)

    # Resolve names in one shot
    person_ids: set[str] = set()
    for bucket in pairs_per_wicket.values():
        for r in bucket:
            person_ids.add(r["p1_id"])
            person_ids.add(r["p2_id"])
    name_map: dict[str, str] = {}
    if person_ids:
        id_list = ",".join(f"'{pid}'" for pid in person_ids)
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({id_list})"
        )
        name_map = {r["id"]: r["name"] for r in name_rows}

    by_wicket = []
    for wn in sorted(pairs_per_wicket.keys()):
        pairs = []
        for rank, r in enumerate(pairs_per_wicket[wn], start=1):
            pairs.append({
                "rank": rank,
                "batter1": {"person_id": r["p1_id"], "name": name_map.get(r["p1_id"], r["p1_id"])},
                "batter2": {"person_id": r["p2_id"], "name": name_map.get(r["p2_id"], r["p2_id"])},
                "n": r["n"],
                "avg_runs": r["avg_runs"],
                "avg_balls": r["avg_balls"],
                "best_runs": r["best_runs"],
                "total_runs": r["total_runs"],
            })
        by_wicket.append({
            "wicket_number": wn,
            "pairs": pairs,
        })

    return {
        "team": team,
        "side": side,
        "min_n": min_n,
        "top_n": top_n,
        "by_wicket": by_wicket,
    }


@router.get("/{team}/partnerships/heatmap")
async def team_partnerships_heatmap(
    team: str,
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side)

    rows = await db.q(
        f"""
        SELECT m.season, p.wicket_number,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               COUNT(*) as n
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season, p.wicket_number
        ORDER BY m.season, p.wicket_number
        """,
        params,
    )

    seasons: list[str] = []
    seen_seasons = set()
    wickets: list[int] = []
    seen_wickets = set()
    cells = []
    for r in rows:
        s = r["season"]
        wn = r["wicket_number"]
        if s not in seen_seasons:
            seen_seasons.add(s)
            seasons.append(s)
        if wn not in seen_wickets:
            seen_wickets.add(wn)
            wickets.append(wn)
        cells.append({
            "season": s,
            "wicket_number": wn,
            "avg_runs": r["avg_runs"],
            "n": r["n"],
        })
    seasons.sort()
    wickets.sort()

    return {
        "team": team,
        "side": side,
        "seasons": seasons,
        "wickets": wickets,
        "cells": cells,
    }


@router.get("/{team}/partnerships/top")
async def team_partnerships_top(
    team: str,
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
    limit: int = Query(10, ge=1, le=50),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side)
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT p.id as partnership_id,
               p.partnership_runs as runs, p.partnership_balls as balls,
               p.wicket_number, p.unbroken, p.ended_by_kind,
               p.batter1_id, p.batter1_name,
               p.batter2_id, p.batter2_name,
               p.batter1_runs, p.batter1_balls,
               p.batter2_runs, p.batter2_balls,
               m.id as match_id, m.season, m.event_name as tournament,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
               CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as opponent
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        ORDER BY p.partnership_runs DESC, p.id
        LIMIT :lim
        """,
        params,
    )

    partnerships = []
    for r in rows:
        partnerships.append({
            "partnership_id": r["partnership_id"],
            "match_id": r["match_id"],
            "date": r["date"],
            "season": r["season"],
            "tournament": r["tournament"],
            "opponent": r["opponent"],
            "wicket_number": r["wicket_number"],
            "runs": r["runs"],
            "balls": r["balls"],
            "unbroken": bool(r["unbroken"]),
            "ended_by_kind": r["ended_by_kind"],
            "batter1": {
                "person_id": r["batter1_id"],
                "name": r["batter1_name"],
                "runs": r["batter1_runs"],
                "balls": r["batter1_balls"],
            },
            "batter2": {
                "person_id": r["batter2_id"],
                "name": r["batter2_name"],
                "runs": r["batter2_runs"],
                "balls": r["batter2_balls"],
            },
        })
    return {"team": team, "side": side, "partnerships": partnerships}
