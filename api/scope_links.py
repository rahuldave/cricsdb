"""Scope-derived suggested-splits — server-side mirror of
`frontend/src/components/scopeLinks.ts::suggestedSplits`.

Emits an ordered list of `(label, params)` pairs from an incoming
filter scope. Each pair is a one-click navigation hint: a related
scope the user is likely to want next ("Kohli IPL 2024 vs Kohli all
IPL").

Principle: for every narrowed axis, offer one-click broaden; for
every isolatable axis (opponent, venue), offer one-click isolate to
that axis with everything else dropped.

The Python and TypeScript implementations are kept in lockstep via
`tests/sanity/scope_splits_fixtures.json` — the same fixture drives
both test suites.

Spec: internal_docs/spec-distribution-stats.md §8.7.
"""

from __future__ import annotations

from typing import Optional


# Identity axes — always preserved across broadening splits. Gender
# only — `team_type` was previously here but is in fact a narrowing
# axis (club / international), not identity. Treating it as identity
# meant the "All cricket in <season>" link silently kept team_type
# narrowed, which is wrong (it should mean ALL cricket, not "all
# club cricket"). For opponent / venue isolation links, team_type
# is preserved separately via `_identity_with_type` since "vs
# Australia" within international scope is the natural reading.
IDENTITY_KEYS = ("gender",)


def _series_label(series_type: str) -> str:
    """Human-readable label for a series_type value used as the T1
    'specific' fallback when no tournament is set."""
    if series_type == "bilateral":
        return "bilaterals"
    if series_type == "icc":
        return "ICC events"
    if series_type == "club":
        return "club competitions"
    return series_type


def _truthy(d: dict, k: str) -> bool:
    """Treat empty string and None as absent."""
    v = d.get(k)
    return v is not None and v != ""


def _identity(scope: dict) -> dict:
    """Identity keys carried through every broadening split (gender)."""
    return {k: scope[k] for k in IDENTITY_KEYS if _truthy(scope, k)}


def _identity_with_type(scope: dict) -> dict:
    """Identity + team_type — used for opponent / venue isolation links
    (vs Australia within "international" makes sense; isolating to
    just the opponent without type would broaden too aggressively)."""
    out = _identity(scope)
    if _truthy(scope, "team_type"):
        out["team_type"] = scope["team_type"]
    return out


def _without(scope: dict, *keys: str) -> dict:
    """Scope copy with the named keys removed and falsy values dropped."""
    return {k: v for k, v in scope.items() if k not in keys and v}


def _season_tag(from_v: Optional[str], to_v: Optional[str]) -> str:
    """Mirror of frontend/src/components/scopeLinks.ts::seasonTag.
    "2024" if from==to, "2023–2024" range, "2023+" or "≤2024" half-open.
    """
    f = from_v if from_v else None
    t = to_v if to_v else None
    if f and t:
        return f if f == t else f"{f}–{t}"
    if f:
        return f"{f}+"
    if t:
        return f"≤{t}"
    return ""


def _season_params(scope: dict) -> dict:
    """Round-trip the scope's season range as URL params, dropping
    falsy bounds."""
    out = {}
    if _truthy(scope, "season_from"):
        out["season_from"] = scope["season_from"]
    if _truthy(scope, "season_to"):
        out["season_to"] = scope["season_to"]
    return out


def suggested_splits(scope: dict) -> list[dict]:
    """Walk the active scope, emit related-scope navigation hints.

    Each entry is `{"label": str, "params": dict}` — `params` is the
    URL search-param dict the destination link should carry. Labels
    are user-facing strings.

    See spec §8.7 for the decision table.
    """
    splits: list[dict] = []
    identity = _identity(scope)
    identity_with_type = _identity_with_type(scope)

    has_tournament = _truthy(scope, "tournament")
    has_series_type = _truthy(scope, "series_type")
    has_team_type = _truthy(scope, "team_type")
    has_season_from = _truthy(scope, "season_from")
    has_season_to = _truthy(scope, "season_to")
    has_any_season = has_season_from or has_season_to

    has_opponent = _truthy(scope, "filter_opponent")
    has_venue = _truthy(scope, "filter_venue")

    season_params = _season_params(scope)
    season_tag_str = _season_tag(scope.get("season_from"), scope.get("season_to"))
    season_suffix = f" in {season_tag_str}" if has_any_season else ""

    # ── Four-tier broadening ladder over (tournament > series_type) ×
    #    team_type × season. Each tier emits one link if its drop
    #    actually changes the scope. Skip a tier when its drop is
    #    a no-op or the result equals a later tier's params (dedupe).

    # T1 — specific (tournament wins; series_type is the fallback).
    # Drops season ONLY (keeps every other narrowing) so it's distinct
    # from T2/T3/T4. Skip when no season is set (would equal current).
    if has_tournament and has_any_season:
        p = {**identity}
        if has_team_type: p["team_type"] = scope["team_type"]
        if has_series_type: p["series_type"] = scope["series_type"]
        p["tournament"] = scope["tournament"]
        splits.append({"label": f"All {scope['tournament']}", "params": p})
    elif has_series_type and has_any_season and not has_tournament:
        # No tournament — series_type is the most specific axis. Drop
        # season; keep type + series_type.
        p = {**identity}
        if has_team_type: p["team_type"] = scope["team_type"]
        p["series_type"] = scope["series_type"]
        splits.append({
            "label": f"All {_series_label(scope['series_type'])}",
            "params": p,
        })

    # T2 — type-only (drop tournament + series_type; keep team_type +
    # season). Fires only when team_type is set AND something more
    # specific (tournament or series_type) is also set, so dropping
    # actually broadens.
    if has_team_type and (has_tournament or has_series_type):
        type_lbl = "club" if scope["team_type"] == "club" else "international"
        p = {**identity, "team_type": scope["team_type"], **season_params}
        splits.append({
            "label": f"All {type_lbl} cricket{season_suffix}",
            "params": p,
        })

    # T3 — all cricket in season (drop type + tournament + series_type;
    # keep season). Fires only when season is set AND something
    # broader-than-season is also set; without season this would equal
    # T4 (all-time), so dedupe.
    if has_any_season and (has_team_type or has_tournament or has_series_type):
        p = {**identity, **season_params}
        splits.append({
            "label": f"All cricket{season_suffix}",
            "params": p,
        })

    # T4 — all-time (drop every narrowing).
    if has_tournament or has_series_type or has_team_type or has_any_season:
        splits.append({"label": "All-time", "params": {**identity}})

    # ── Opponent axis (independent of the broadening ladder).
    # Isolation keeps team_type so "vs Australia" reads in the
    # international context the user is in.
    if has_opponent:
        opponent = scope["filter_opponent"]
        splits.append({
            "label": f"vs {opponent}, all-time",
            "params": {**identity_with_type, "filter_opponent": opponent},
        })
        splits.append({
            "label": "vs all opponents",
            "params": _without(scope, "filter_opponent"),
        })

    # ── Venue axis (same shape as opponent).
    if has_venue:
        venue = scope["filter_venue"]
        splits.append({
            "label": f"at {venue}, all-time",
            "params": {**identity_with_type, "filter_venue": venue},
        })
        splits.append({
            "label": "at all venues",
            "params": _without(scope, "filter_venue"),
        })

    # ── Gender flip (only useful on women's scope; men's is the
    #    asymmetric default — flipping male → female would 0 out
    #    most player profiles unsurprisingly) ───────────────────────
    if scope.get("gender") == "female":
        flipped = {k: v for k, v in scope.items() if v}
        flipped["gender"] = "male"
        splits.append({"label": "Switch to men's", "params": flipped})

    return splits


def scope_dict_from_filters(filters) -> dict:
    """Convert a FilterBarParams instance to the scope dict shape used
    by `suggested_splits`. Maps internal short names (team, opponent,
    venue) to their URL-key forms (filter_team, filter_opponent,
    filter_venue) so emitted `params` round-trip back through the URL."""
    return {
        "gender": filters.gender,
        "team_type": filters.team_type,
        "tournament": filters.tournament,
        "season_from": filters.season_from,
        "season_to": filters.season_to,
        "filter_team": filters.team,
        "filter_opponent": filters.opponent,
        "filter_venue": filters.venue,
        "team_class": filters.team_class,
        "series_type": filters.series_type,
    }
