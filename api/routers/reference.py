"""Reference data endpoints: tournaments, seasons, teams, players."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams
from ..tournament_canonical import (
    canonicalize, variants as canonical_variants,
    is_canonical_with_variants, event_name_in_clause,
    series_type_clause as _series_type_clause,
)

router = APIRouter(prefix="/api/v1", tags=["Reference"])


def _reference_clauses(
    team: Optional[str],
    gender: Optional[str],
    team_type: Optional[str],
    tournament: Optional[str],
    season_from: Optional[str] = None,
    season_to: Optional[str] = None,
    filter_venue: Optional[str] = None,
    series_type: Optional[str] = None,
) -> tuple[list[str], dict]:
    """Build WHERE fragments for /tournaments and /seasons.

    Every dimension passed in narrows the result set — picking
    tournament=IPL on the Teams page makes the seasons dropdown show
    just IPL seasons; setting filter_venue=Wankhede narrows both lists
    to tournaments/seasons played there; series_type=bilateral narrows
    to international bilateral series only. Path team wins over any
    filter_team in the URL.

    Callers drop their own self-referential axis (tournaments endpoint
    omits `tournament`; seasons omits `season_from`/`season_to`) before
    passing through here.
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
    if season_from:
        parts.append("m.season >= :season_from")
        params["season_from"] = season_from
    if season_to:
        parts.append("m.season <= :season_to")
        params["season_to"] = season_to
    if filter_venue:
        parts.append("m.venue = :filter_venue")
        params["filter_venue"] = filter_venue
    if series_type:
        st = _series_type_clause(series_type)
        if st:
            parts.append(st)
    return parts, params


@router.get("/tournaments")
async def list_tournaments(
    team: Optional[str] = Query(None),
    opponent: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    team_type: Optional[str] = Query(None),
    season_from: Optional[str] = Query(None),
    season_to: Optional[str] = Query(None),
    filter_venue: Optional[str] = Query(None),
    series_type: Optional[str] = Query(None, description="all / bilateral / icc / club (narrows the tournament list)"),
):
    """List tournaments, narrowed by every FilterBar field the page
    has set — gender, team_type, team, season range, filter_venue,
    plus the Series-tab page-local `series_type`. Tournament itself is
    intentionally not a filter here (that would make the list self-
    referential — you're picking from this list).

    When both `team` and `opponent` are set, returns only tournaments
    where the two teams actually played each other — lets FilterBar
    decide whether a rivalry implies a single competition (MI vs CSK
    → IPL) or spans many (India vs Australia → bilaterals + ICC).

    `series_type=bilateral` narrows the dropdown to international
    bilateral series; `icc` to ICC events; `club` to club tournaments.
    Used by the Series dossier so picking "bilateral" hides WC etc.
    from the tournament picker."""
    db = get_db()
    parts, params = _reference_clauses(
        team, gender, team_type, None,
        season_from=season_from, season_to=season_to,
        filter_venue=filter_venue, series_type=series_type,
    )
    if opponent:
        parts.append(
            "((m.team1 = :team AND m.team2 = :opponent)"
            " OR (m.team1 = :opponent AND m.team2 = :team))"
        )
        params["opponent"] = opponent
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
    filter_team: Optional[str] = Query(None),
    filter_opponent: Optional[str] = Query(None),
    filter_venue: Optional[str] = Query(None),
    series_type: Optional[str] = Query(None),
):
    """Seasons narrowed by every FilterBar field the page has set —
    team / gender / team_type / tournament / filter_venue — plus
    page-local series_type and the rivalry pair (filter_team +
    filter_opponent). When tournament=IPL, only IPL seasons are
    returned — so the From/To pickers can't offer 2009/10 (a Champions
    League season) or 2026 (a season MI has played but IPL hasn't
    entered yet). filter_venue=Wankhede narrows to seasons that
    actually saw matches there.

    season_from / season_to are intentionally NOT accepted here — the
    endpoint builds the list the From/To pickers choose from (self-
    referential)."""
    db = get_db()
    # Rivalry pair narrows like the tournaments endpoint — if the page
    # has filter_team+filter_opponent, only seasons where the two teams
    # actually met are relevant.
    parts, params = _reference_clauses(
        team, gender, team_type, tournament,
        filter_venue=filter_venue, series_type=series_type,
    )
    if filter_team and filter_opponent:
        parts.append(
            "((m.team1 = :filter_team AND m.team2 = :filter_opponent)"
            " OR (m.team1 = :filter_opponent AND m.team2 = :filter_team))"
        )
        params["filter_team"] = filter_team
        params["filter_opponent"] = filter_opponent
    elif filter_team:
        parts.append("(m.team1 = :filter_team OR m.team2 = :filter_team)")
        params["filter_team"] = filter_team
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
    if filters.venue:
        where_parts.append("m.venue = :filter_venue")
        params["filter_venue"] = filters.venue
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
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Name-typeahead for players, optionally narrowed to a scope.

    Without scope (no FilterBar / aux params set), returns global ranking
    by total innings in the requested role.

    With scope, narrows to people who appeared on either team in scope
    matches — consistent with how /series/*-leaders scope (match-level
    team filter). This keeps the Series tab's picker from surfacing
    e.g. AB de Villiers when the dossier is scoped to T20 WC 2022-2026.
    """
    db = get_db()
    params: dict = {"q": q, "limit": limit}

    # Detect scope from raw filter fields — NOT from the WHERE clause,
    # because `build(has_innings_join=True)` always emits the baseline
    # `i.super_over = 0` clause, which would falsely route every
    # unscoped request through the slower innings-joined path AND
    # exclude super-over deliveries (changing `innings` counts
    # compared to the legacy query).
    has_scope = bool(
        filters.gender or filters.team_type or filters.tournament
        or filters.season_from or filters.season_to
        or filters.team or filters.opponent or filters.venue
        or (aux.series_type and aux.series_type != 'all')
    )
    scope_where = ""
    if has_scope:
        scope_where, scope_params = filters.build_side_neutral(
            has_innings_join=True, aux=aux,
        )
        params.update(scope_params)

    if role == "fielder":
        if has_scope:
            rows = await db.q(
                f"""
                SELECT p.id, p.name, p.unique_name,
                       COUNT(DISTINCT i.id) as innings
                FROM person p
                JOIN fieldingcredit fc ON fc.fielder_id = p.id
                JOIN delivery d ON d.id = fc.delivery_id
                JOIN innings i ON i.id = d.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE (p.name LIKE :q || '%'
                       OR p.unique_name LIKE '%' || :q || '%'
                       OR p.id IN (
                           SELECT pn.person_id FROM personname pn
                           WHERE pn.name LIKE '%' || :q || '%'
                       ))
                  AND {scope_where}
                GROUP BY p.id
                ORDER BY innings DESC
                LIMIT :limit
                """,
                params,
            )
        else:
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

    if has_scope:
        rows = await db.q(
            f"""
            SELECT p.id, p.name, p.unique_name,
                   COUNT(DISTINCT d.innings_id) as innings
            FROM person p
            JOIN delivery d ON {join_col} = p.id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE (p.name LIKE :q || '%'
                   OR p.unique_name LIKE '%' || :q || '%'
                   OR p.id IN (
                       SELECT pn.person_id FROM personname pn
                       WHERE pn.name LIKE '%' || :q || '%'
                   ))
              AND {scope_where}
            GROUP BY p.id
            ORDER BY innings DESC
            LIMIT :limit
            """,
            params,
        )
    else:
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
