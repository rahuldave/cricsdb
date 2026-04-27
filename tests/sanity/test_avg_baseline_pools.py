"""Avg-baseline pool sizes — pinned to a closed historical window.

Tests the THREE baseline modes for the Compare-tab avg column:

  1. UNBOUNDED — `gender=male&team_type=international&season=YYYY`,
     no scope_to_team, no team_class. The full international pool.
  2. FULL-MEMBER — same scope + `team_class=full_member`. Restricts
     to matches where BOTH teams are ICC full members.
  3. SCOPE-TO-TEAM — same scope + `scope_to_team=<team>`. Narrows to
     matches whose `event_name` appears in <team>'s tournament universe.
     Correct semantic for closed leagues (RCB → IPL); semantically
     misleading for internationals (a single team's universe contains
     that team in every match) — kept here as a regression marker for
     the 2026-04-27 frontend gate (Mechanism A): for internationals,
     production no longer applies this narrowing by default.

Pinned to season=2018 so the counts are stable across DB rebuilds —
no future deliveries land in 2018; the only mutation would be
cricsheet retroactively adding/removing a 2018 match (rare, audited
manually). For the IPL club-regression check, the 2018 IPL has a
fixed 60-match schedule; this row exists so any inadvertent
regression of the club-side scope_to_team narrow is caught here.

Usage:
  uv run python tests/sanity/test_avg_baseline_pools.py
  uv run python tests/sanity/test_avg_baseline_pools.py --db /tmp/cricket-prod-test.db
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams
from api.routers.scope_averages import scope_summary as scope_summary_endpoint


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux(**kwargs) -> AuxParams:
    return AuxParams(
        series_type=kwargs.get("series_type"),
        scope_to_team=kwargs.get("scope_to_team"),
        team_class=kwargs.get("team_class"),
    )


# Pinned counts — derived from cricket.db, expected stable for season=2018.
# If a DB rebuild changes these, investigate before bumping the constants.
EXPECTED = [
    # (label, scope_kwargs, aux_kwargs, expected_match_count)
    ("men_intl 2018 unbounded",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018"),
     dict(),
     104),
    ("men_intl 2018 full-member only",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018"),
     dict(team_class="full_member"),
     20),
    ("men_intl 2018 scope_to_team=Australia (= regression marker — the OLD bug)",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018"),
     dict(scope_to_team="Australia"),
     # Aus's all-time tournament universe ∩ men_intl 2018 = 8 matches.
     # Compare against the unbounded 104. The big spread is the bug
     # the 2026-04-27 Mechanism A gate eliminated (frontend no longer
     # passes scope_to_team for internationals). Keeping it pinned so
     # any drift in `_scope_to_team_clause` semantics is caught.
     8),
    ("ipl 2018 unbounded (club regression)",
     dict(gender="male", team_type="club", season_from="2018", season_to="2018",
          tournament="Indian Premier League"),
     dict(),
     60),
    ("ipl 2018 scope_to_team=RCB (club narrow OK)",
     dict(gender="male", team_type="club", season_from="2018", season_to="2018",
          tournament="Indian Premier League"),
     dict(scope_to_team="Royal Challengers Bengaluru"),
     60),  # tournament filter dominates — scope_to_team is a no-op
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")
    await deps._db.q("PRAGMA journal_mode = WAL")

    failures = []
    for label, scope, aux_kwargs, expected in EXPECTED:
        f = make_filters(**scope)
        a = make_aux(**aux_kwargs)
        resp = await scope_summary_endpoint(filters=f, aux=a)
        actual = resp.get("matches")
        if expected is None:
            print(f"  {label}: matches={actual} (no expectation)")
            continue
        ok = actual == expected
        status = "PASS" if ok else f"FAIL (got {actual}, expected {expected})"
        print(f"  {label}: {status}")
        if not ok:
            failures.append((label, expected, actual))

    print()
    if failures:
        print(f"=== {len(failures)} failure(s) ===")
        for label, exp, act in failures:
            print(f"  {label}: expected {exp}, got {act}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
