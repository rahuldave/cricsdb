"""Helpers for dispatching scope-aggregate endpoints to bucket_baseline_*
table reads when the scope is in the precomputed regime, falling back
to live aggregation otherwise.

Spec: internal_docs/spec-team-bucket-baseline.md
"""
from __future__ import annotations

from typing import Optional

from ..filters import FilterParams, AuxParams


LEAGUE_TEAM_KEY = "__league__"


def is_precomputed_scope(filters: FilterParams, aux: Optional[AuxParams]) -> bool:
    """Return True iff this scope is fully covered by bucket_baseline_*.

    Filters NOT in the precomputed regime → fall back to live:
      - filter_venue: not stored per cell.
      - filter_team / filter_opponent (rivalry context): per-pair too
        sparse to precompute.
      - aux.series_type other than 'all'/None: per-cell baselines are
        per-tournament, so series_type can't refine within a cell.

    Anything else (gender + team_type + optional tournament + optional
    season range + optional scope_to_team) → use the table.
    """
    if filters.venue:
        return False
    if filters.team is not None or filters.opponent is not None:
        return False
    if aux is not None and aux.series_type and aux.series_type != "all":
        return False
    return True


def baseline_where(
    filters: FilterParams,
    aux: Optional[AuxParams],
    team: str = LEAGUE_TEAM_KEY,
    table_alias: str = "",
) -> tuple[str, dict]:
    """Build the WHERE clause for SELECT-from-bucket_baseline_X queries.

    Args:
        filters: Request FilterParams (gender / team_type / tournament /
            season_from / season_to are honoured; venue / filter_team /
            filter_opponent assumed empty — caller gated on
            `is_precomputed_scope`).
        aux: AuxParams. `aux.scope_to_team` triggers the team-tournament
            IN-list narrowing when no explicit tournament filter is set.
        team: Either LEAGUE_TEAM_KEY for the pool-weighted league row
            or a real team name for a per-team query.
        table_alias: Optional alias prefix (e.g. "b" → `b.gender = …`).
            Defaults to bare column references.

    Returns:
        (where_str, params_dict). where_str includes leading "WHERE".
    """
    a = f"{table_alias}." if table_alias else ""
    parts: list[str] = [f"{a}team = :_team"]
    params: dict = {"_team": team}

    if filters.gender:
        parts.append(f"{a}gender = :_gender")
        params["_gender"] = filters.gender
    if filters.team_type:
        parts.append(f"{a}team_type = :_team_type")
        params["_team_type"] = filters.team_type

    if filters.tournament:
        parts.append(f"{a}tournament = :_tournament")
        params["_tournament"] = filters.tournament
    elif aux is not None and aux.scope_to_team:
        # Auto-narrow to the primary team's tournament universe via the
        # already-precomputed match table — no live JOIN to matchplayer
        # needed.
        sub = ["team = :_scope_to_team"]
        if filters.gender:    sub.append("gender = :_gender")
        if filters.team_type: sub.append("team_type = :_team_type")
        parts.append(
            f"{a}tournament IN ("
            f"SELECT DISTINCT tournament FROM bucketbaselinematch "
            f"WHERE {' AND '.join(sub)})"
        )
        params["_scope_to_team"] = aux.scope_to_team

    if filters.season_from:
        parts.append(f"{a}season >= :_season_from")
        params["_season_from"] = filters.season_from
    if filters.season_to:
        parts.append(f"{a}season <= :_season_to")
        params["_season_to"] = filters.season_to

    return "WHERE " + " AND ".join(parts), params
