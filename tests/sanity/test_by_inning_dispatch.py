"""Pure-unit test for the by-inning dispatch wrappers.

`_batting_by_inning_aggregates` and `_bowling_by_inning_aggregates`
(api/routers/teams.py) are 3-line dispatch routers:

    if is_precomputed_scope(filters, aux):
        return await _xxx_baseline(team, filters, aux)
    return await _xxx_live(team, filters, aux)

The decision is pure — only the delegate functions touch the DB. This
test mocks the delegates with async sentinels and verifies each
dispatch wrapper routes correctly under representative filter combos.
That guards against a future refactor that:
  - flips the gate (e.g. dropping the is_precomputed_scope check)
  - swaps the baseline/live delegates
  - adds a non-pure decision (e.g. reading the DB to decide)

Spec: spec-series-precompute-followup.md Phase D part 2.

Usage:
  uv run python tests/sanity/test_by_inning_dispatch.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.filters import FilterBarParams, AuxParams
from api.routers import teams as teams_router


def _filters(**overrides) -> FilterBarParams:
    f = FilterBarParams()
    for k in ("gender", "team_type", "tournament", "season_from",
              "season_to", "team", "opponent", "venue", "team_class",
              "series_type"):
        setattr(f, k, None)
    for k, v in overrides.items():
        setattr(f, k, v)
    return f


def _aux(**overrides) -> AuxParams:
    a = AuxParams()
    for k in ("scope_to_team", "chip_team_class", "chip_baseline_scope_json",
              "inning", "result", "toss_outcome"):
        setattr(a, k, None)
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


async def _run_dispatch(wrapper_attr: str, baseline_attr: str, live_attr: str,
                        team, filters, aux):
    """Call the wrapper with the baseline+live delegates mocked, return
    which path was taken: 'baseline' | 'live'.
    """
    BASELINE_SENTINEL = {"path": "baseline"}
    LIVE_SENTINEL = {"path": "live"}

    async def fake_baseline(*args, **kwargs):
        return BASELINE_SENTINEL

    async def fake_live(*args, **kwargs):
        return LIVE_SENTINEL

    with mock.patch.object(teams_router, baseline_attr, side_effect=fake_baseline), \
         mock.patch.object(teams_router, live_attr,     side_effect=fake_live):
        wrapper = getattr(teams_router, wrapper_attr)
        result = await wrapper(team, filters, aux)
    return result["path"]


def main():
    cases = [
        # (description, filters_overrides, aux_overrides, expected_path)
        ("empty scope (all-cricket) → baseline",
         {}, {}, "baseline"),
        ("gender + team_type → baseline",
         {"gender": "male", "team_type": "international"}, {}, "baseline"),
        ("filter_venue set → live",
         {"venue": "Eden Gardens"}, {}, "live"),
        ("filter_team set (rivalry) → live",
         {"team": "India"}, {}, "live"),
        ("filter_opponent set → live",
         {"opponent": "Australia"}, {}, "live"),
        ("aux.inning=0 → live",
         {}, {"inning": 0}, "live"),
        ("aux.result='won' → live",
         {}, {"result": "won"}, "live"),
        ("aux.toss_outcome='lost' → live",
         {}, {"toss_outcome": "lost"}, "live"),
        ("series_type='bilateral' → live",
         {"series_type": "bilateral"}, {}, "live"),
        ("series_type='all' (default) → baseline",
         {"series_type": "all"}, {}, "baseline"),
        ("team_class=full_member + team_type=international → live",
         {"team_class": "full_member", "team_type": "international"}, {}, "live"),
        ("team_class=full_member + cross-type → baseline (silent no-op)",
         {"team_class": "full_member", "team_type": "club"}, {}, "baseline"),
        ("tournament narrowing via FilterBar → baseline",
         {"tournament": "Indian Premier League"}, {}, "baseline"),
        ("season range only → baseline",
         {"season_from": "2024", "season_to": "2024"}, {}, "baseline"),
    ]

    wrappers = [
        ("_batting_by_inning_aggregates",
         "_batting_by_inning_aggregates_baseline",
         "_batting_by_inning_aggregates_live"),
        ("_bowling_by_inning_aggregates",
         "_bowling_by_inning_aggregates_baseline",
         "_bowling_by_inning_aggregates_live"),
    ]

    failures = []
    total = 0
    for wrapper, baseline_attr, live_attr in wrappers:
        for desc, f_over, a_over, expected in cases:
            total += 1
            got = asyncio.run(_run_dispatch(
                wrapper, baseline_attr, live_attr,
                team="India", filters=_filters(**f_over), aux=_aux(**a_over),
            ))
            if got != expected:
                failures.append(f"FAIL: {wrapper} · {desc} — expected {expected}, got {got}")

    if failures:
        for f in failures:
            print(f)
        print()
        print(f"FAILED: {len(failures)}/{total}")
        sys.exit(1)
    print(f"PASS: by-inning dispatch — {total} cases (2 wrappers × {len(cases)} filter combos)")
    print()
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
