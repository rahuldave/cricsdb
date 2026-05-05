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


# Identity axes — always preserved across splits. Distinct from the
# narrowing axes which the splits broaden / isolate.
IDENTITY_KEYS = ("gender", "team_type")


def _truthy(d: dict, k: str) -> bool:
    """Treat empty string and None as absent."""
    v = d.get(k)
    return v is not None and v != ""


def _identity(scope: dict) -> dict:
    """Identity keys carried through every split (gender, team_type)."""
    return {k: scope[k] for k in IDENTITY_KEYS if _truthy(scope, k)}


def _without(scope: dict, *keys: str) -> dict:
    """Scope copy with the named keys removed and falsy values dropped."""
    return {k: v for k, v in scope.items() if k not in keys and v}


def suggested_splits(scope: dict) -> list[dict]:
    """Walk the active scope, emit related-scope navigation hints.

    Each entry is `{"label": str, "params": dict}` — `params` is the
    URL search-param dict the destination link should carry. Labels
    are user-facing strings.

    See spec §8.7 for the decision table.
    """
    splits: list[dict] = []
    identity = _identity(scope)

    has_tournament = _truthy(scope, "tournament")
    has_season_from = _truthy(scope, "season_from")
    has_season_to = _truthy(scope, "season_to")
    has_single_season = (
        has_season_from and has_season_to
        and scope["season_from"] == scope["season_to"]
    )
    has_season_range = (has_season_from or has_season_to) and not has_single_season
    has_any_season = has_single_season or has_season_range

    has_opponent = _truthy(scope, "filter_opponent")
    has_venue = _truthy(scope, "filter_venue")

    # ── Tournament × season axis ──────────────────────────────────────
    if has_tournament and has_single_season:
        tournament = scope["tournament"]
        season = scope["season_from"]
        splits.append({
            "label": f"All {tournament}",
            "params": {**identity, "tournament": tournament},
        })
        splits.append({
            "label": f"All cricket in {season}",
            "params": {
                **identity,
                "season_from": season,
                "season_to": season,
            },
        })
        splits.append({"label": "All-time", "params": {**identity}})
    elif has_tournament and not has_any_season:
        # Tournament only — offer all-time. ("Latest edition" requires DB
        # lookup; deferred per §6.4.)
        splits.append({"label": "All-time", "params": {**identity}})
    elif has_any_season and not has_tournament:
        splits.append({"label": "All-time", "params": {**identity}})

    # ── Opponent axis ─────────────────────────────────────────────────
    if has_opponent:
        opponent = scope["filter_opponent"]
        splits.append({
            "label": f"vs {opponent}, all-time",
            "params": {**identity, "filter_opponent": opponent},
        })
        splits.append({
            "label": "vs all opponents",
            "params": _without(scope, "filter_opponent"),
        })

    # ── Venue axis ────────────────────────────────────────────────────
    if has_venue:
        venue = scope["filter_venue"]
        splits.append({
            "label": f"at {venue}, all-time",
            "params": {**identity, "filter_venue": venue},
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
