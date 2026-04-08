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
