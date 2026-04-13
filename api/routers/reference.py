"""Reference data endpoints: tournaments, seasons, teams, players."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1", tags=["Reference"])


@router.get("/tournaments")
async def list_tournaments():
    db = get_db()
    rows = await db.q(
        """
        SELECT event_name, team_type, gender,
               COUNT(*) as matches,
               GROUP_CONCAT(DISTINCT season) as seasons
        FROM match
        WHERE event_name IS NOT NULL
        GROUP BY event_name, team_type, gender
        ORDER BY matches DESC
        """
    )
    tournaments = []
    for r in rows:
        seasons_str = r.get("seasons") or ""
        season_list = sorted(seasons_str.split(",")) if seasons_str else []
        tournaments.append({
            "event_name": r["event_name"],
            "team_type": r["team_type"],
            "gender": r["gender"],
            "matches": r["matches"],
            "seasons": season_list,
        })
    return {"tournaments": tournaments}


@router.get("/seasons")
async def list_seasons():
    db = get_db()
    rows = await db.q("SELECT DISTINCT season FROM match ORDER BY season")
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
