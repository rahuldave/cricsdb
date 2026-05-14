"""Helpers for dispatching scope-aggregate endpoints to bucket_baseline_*
table reads when the scope is in the precomputed regime, falling back
to live aggregation otherwise.

Spec: internal_docs/spec-team-bucket-baseline.md
"""
from __future__ import annotations

from typing import Optional

from ..filters import FilterParams, AuxParams, _is_set
from ..tournament_canonical import (
    is_canonical_with_variants, variants as canonical_variants,
    event_name_in_clause,
)


LEAGUE_TEAM_KEY = "__league__"


def is_precomputed_scope(filters: FilterParams, aux: Optional[AuxParams]) -> bool:
    """Return True iff this scope is fully covered by bucket_baseline_*.

    Filters NOT in the precomputed regime → fall back to live:
      - filter_venue: not stored per cell.
      - filter_team / filter_opponent (rivalry context): per-pair too
        sparse to precompute.
      - filters.series_type other than 'all'/None: per-cell baselines
        are per-tournament, so series_type can't refine within a cell.
      - filters.team_class: bucket tables don't carry a team-class
        dimension; tier filtering must run live. Reject only when the
        filter would actually fire (matched team_type) — cross-type
        values are silent no-ops so bucket dispatch can stay enabled.

    Anything else (gender + team_type + optional tournament + optional
    season range + optional scope_to_team) → use the table.
    """
    if _is_set(filters.venue):
        return False
    if _is_set(filters.team) or _is_set(filters.opponent):
        return False
    if _is_set(filters.series_type) and filters.series_type != "all":
        return False
    if _is_set(filters.team_class):
        if filters.team_class == "full_member" and filters.team_type == "international":
            return False
        if filters.team_class in ("primary_club", "secondary_club") and filters.team_type == "club":
            return False
    # Inning narrowing — bucket tables don't carry an innings dimension.
    # Live aggregation handles it; precompute later iff measured hot.
    # Spec: internal_docs/spec-inning-split.md §5.4.
    if aux is not None and aux.inning is not None:
        return False
    # Result / toss_outcome aux filters are match-level slices that the
    # pre-aggregated bucket tables don't carry. Force the live path so
    # the filter actually fires. Spec:
    # internal_docs/spec-splits-mosaic.md §1.2.
    if aux is not None and (aux.result is not None or aux.toss_outcome is not None):
        return False
    return True


def baseline_where(
    filters: FilterParams,
    aux: Optional[AuxParams],
    team: Optional[str] = LEAGUE_TEAM_KEY,
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
        team: Either LEAGUE_TEAM_KEY for the pool-weighted league row,
            a real team name for a per-team query, or None to skip the
            team clause entirely (used by bucketbaselinemoments, which
            has no team column).
        table_alias: Optional alias prefix (e.g. "b" → `b.gender = …`).
            Defaults to bare column references.

    Returns:
        (where_str, params_dict). where_str includes leading "WHERE".
    """
    a = f"{table_alias}." if table_alias else ""
    parts: list[str] = []
    params: dict = {}
    if team is not None:
        parts.append(f"{a}team = :_team")
        params["_team"] = team

    if _is_set(filters.gender):
        parts.append(f"{a}gender = :_gender")
        params["_gender"] = filters.gender
    if _is_set(filters.team_type):
        parts.append(f"{a}team_type = :_team_type")
        params["_team_type"] = filters.team_type

    if _is_set(filters.tournament):
        # Bucket tables store the RAW cricsheet event_name as the
        # tournament value (see populate_bucket_baseline.py — no
        # canonicalization at population time). When the request's
        # tournament filter is a canonical that maps to multiple
        # variants (e.g. "T20 World Cup (Men)" → ICC World Twenty20 /
        # World T20 / ICC Men's T20 World Cup), expand to an IN-list
        # so all variants match. Single-variant / non-canonical names
        # fall through to equality.
        if is_canonical_with_variants(filters.tournament):
            parts.append(event_name_in_clause(
                canonical_variants(filters.tournament),
                col=f"{a}tournament",
            ))
        else:
            parts.append(f"{a}tournament = :_tournament")
            params["_tournament"] = filters.tournament
    elif aux is not None and aux.scope_to_team:
        # Auto-narrow to the primary team's tournament universe via the
        # already-precomputed match table — no live JOIN to matchplayer
        # needed.
        sub = ["team = :_scope_to_team"]
        if _is_set(filters.gender):    sub.append("gender = :_gender")
        if _is_set(filters.team_type): sub.append("team_type = :_team_type")
        parts.append(
            f"{a}tournament IN ("
            f"SELECT DISTINCT tournament FROM bucketbaselinematch "
            f"WHERE {' AND '.join(sub)})"
        )
        params["_scope_to_team"] = aux.scope_to_team

    if _is_set(filters.season_from):
        parts.append(f"{a}season >= :_season_from")
        params["_season_from"] = filters.season_from
    if _is_set(filters.season_to):
        parts.append(f"{a}season <= :_season_to")
        params["_season_to"] = filters.season_to

    if not parts:
        return "", params
    return "WHERE " + " AND ".join(parts), params
