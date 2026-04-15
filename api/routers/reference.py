"""Reference data endpoints: tournaments, seasons, teams, players."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams
from ..tournament_canonical import (
    canonicalize, variants as canonical_variants,
    is_canonical_with_variants, event_name_in_clause,
)

router = APIRouter(prefix="/api/v1", tags=["Reference"])


def _reference_clauses(
    team: Optional[str],
    gender: Optional[str],
    team_type: Optional[str],
    tournament: Optional[str],
) -> tuple[list[str], dict]:
    """Build WHERE fragments for /tournaments and /seasons.

    All four dimensions narrow the result set — so picking
    tournament=IPL on the Teams page makes the seasons dropdown show
    just IPL seasons. Path team wins over any filter_team in the URL.
    """
    parts: list[str] = []
    params: dict = {}
    if team:
        parts.append("(m.team1 = :team OR m.team2 = :team)")
        params["team"] = team
    if gender:
        parts.append("m.gender = :gender")
        params["gender"] = gender
    if team_type:
        parts.append("m.team_type = :team_type")
        params["team_type"] = team_type
    if tournament:
        # Expand canonicals → IN (variants) so picking "T20 World Cup
        # (Men)" narrows seasons across all three cricsheet variants.
        if is_canonical_with_variants(tournament):
            parts.append(event_name_in_clause(canonical_variants(tournament)))
        else:
            parts.append("m.event_name = :tournament")
            params["tournament"] = tournament
    return parts, params


@router.get("/tournaments")
async def list_tournaments(
    team: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    team_type: Optional[str] = Query(None),
):
    """List tournaments, narrowed by team / gender / team_type so the
    dropdown reflects what's reachable from the current filter state.
    Tournament itself is intentionally not a filter here (that would
    make the list self-referential — you're picking from this list)."""
    db = get_db()
    parts, params = _reference_clauses(team, gender, team_type, None)
    parts.append("m.event_name IS NOT NULL")
    where = " AND ".join(parts)
    rows = await db.q(
        f"""
        SELECT m.event_name, m.team_type, m.gender,
               COUNT(*) as matches,
               GROUP_CONCAT(DISTINCT m.season) as seasons
        FROM match m
        WHERE {where}
        GROUP BY m.event_name, m.team_type, m.gender
        ORDER BY matches DESC
        """,
        params,
    )
    # Merge cricsheet variants under their canonical display name so the
    # FilterBar dropdown shows "T20 World Cup (Men)" as a single entry
    # instead of three separate ones that each cover only part of history.
    # The `event_name` field carries the CANONICAL (not cricsheet raw),
    # matching the tournament value downstream endpoints now accept.
    merged: dict[tuple[str, str | None, str | None], dict] = {}
    for r in rows:
        canon = canonicalize(r["event_name"])
        key = (canon, r["team_type"], r["gender"])
        entry = merged.setdefault(key, {
            "event_name": canon,
            "team_type": r["team_type"],
            "gender": r["gender"],
            "matches": 0,
            "seasons": set(),
        })
        entry["matches"] += r["matches"] or 0
        if r.get("seasons"):
            entry["seasons"].update(r["seasons"].split(","))

    tournaments = [
        {
            "event_name": e["event_name"],
            "team_type": e["team_type"],
            "gender": e["gender"],
            "matches": e["matches"],
            "seasons": sorted(e["seasons"]),
        }
        for e in sorted(merged.values(), key=lambda x: (-x["matches"], x["event_name"]))
    ]
    return {"tournaments": tournaments}


@router.get("/seasons")
async def list_seasons(
    team: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    team_type: Optional[str] = Query(None),
    tournament: Optional[str] = Query(None),
):
    """Seasons narrowed by team / gender / team_type / tournament. When
    tournament=IPL, only IPL seasons are returned — so the From/To
    pickers can't offer 2009/10 (a Champions League season) or 2026 (a
    season MI has played but IPL hasn't entered yet)."""
    db = get_db()
    parts, params = _reference_clauses(team, gender, team_type, tournament)
    where = " AND ".join(parts) if parts else "1=1"
    rows = await db.q(
        f"""
        SELECT DISTINCT m.season FROM match m
        WHERE {where}
        ORDER BY m.season
        """,
        params,
    )
    return {"seasons": [r["season"] for r in rows]}


@router.get("/teams")
async def list_teams(
    filters: FilterParams = Depends(),
    q: Optional[str] = Query(None),
):
    db = get_db()
    where_parts = ["1=1"]
    params: dict = {}

    if filters.gender:
        where_parts.append("m.gender = :gender")
        params["gender"] = filters.gender
    if filters.team_type:
        where_parts.append("m.team_type = :team_type")
        params["team_type"] = filters.team_type
    if filters.tournament:
        if is_canonical_with_variants(filters.tournament):
            where_parts.append(event_name_in_clause(canonical_variants(filters.tournament)))
        else:
            where_parts.append("m.event_name = :tournament")
            params["tournament"] = filters.tournament
    if filters.season_from:
        where_parts.append("m.season >= :season_from")
        params["season_from"] = filters.season_from
    if filters.season_to:
        where_parts.append("m.season <= :season_to")
        params["season_to"] = filters.season_to
    if q:
        where_parts.append("mp.team LIKE :q")
        params["q"] = f"%{q}%"

    where_clause = " AND ".join(where_parts)

    rows = await db.q(
        f"""
        SELECT mp.team as name, COUNT(DISTINCT mp.match_id) as matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE {where_clause}
        GROUP BY mp.team
        ORDER BY matches DESC
        """,
        params,
    )
    return {"teams": rows}


@router.get("/players")
async def search_players(
    q: str = Query(..., min_length=2),
    role: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    db = get_db()
    params: dict = {"q": q, "limit": limit}

    if role == "fielder":
        # Fielder search: ranked by total dismissals from fielding_credit
        rows = await db.q(
            """
            SELECT p.id, p.name, p.unique_name,
                   COUNT(*) as innings
            FROM person p
            JOIN fieldingcredit fc ON fc.fielder_id = p.id
            WHERE p.name LIKE :q || '%'
               OR p.unique_name LIKE '%' || :q || '%'
               OR p.id IN (
                   SELECT pn.person_id FROM personname pn
                   WHERE pn.name LIKE '%' || :q || '%'
               )
            GROUP BY p.id
            ORDER BY innings DESC
            LIMIT :limit
            """,
            params,
        )
        return {"players": rows}

    if role == "batter":
        join_col = "d.batter_id"
    elif role == "bowler":
        join_col = "d.bowler_id"
    else:
        join_col = "d.batter_id"

    rows = await db.q(
        f"""
        SELECT p.id, p.name, p.unique_name,
               COUNT(DISTINCT d.innings_id) as innings
        FROM person p
        JOIN delivery d ON {join_col} = p.id
        WHERE p.name LIKE :q || '%'
           OR p.unique_name LIKE '%' || :q || '%'
           OR p.id IN (
               SELECT pn.person_id FROM personname pn
               WHERE pn.name LIKE '%' || :q || '%'
           )
        GROUP BY p.id
        ORDER BY innings DESC
        LIMIT :limit
        """,
        params,
    )
    return {"players": rows}
