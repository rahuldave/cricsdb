"""Avg-baseline per-team match counts — pinned to a closed historical window.

Tests the THREE baseline modes for the Compare-tab avg column:

  1. UNBOUNDED — `gender=male&team_type=international&season=YYYY`,
     no scope_to_team, no team_class. The full international pool.
  2. FULL-MEMBER — same scope + `team_class=full_member`. Restricts
     to matches where BOTH teams are ICC full members.
  3. SCOPE-TO-TEAM — same scope + `scope_to_team=<team>`. Narrows to
     matches whose `event_name` appears in <team>'s tournament universe.

`/scope/averages/summary.matches` returns the PER-TEAM average match
count (per `spec-avg-col-per-team-transform.md`, 2026-04-28). The
underlying pool counts are still measurable (pool = per_team × unique_teams ÷ 2)
but this test pins what the avg col displays end-to-end.

Pinned to season=2018 so the counts are stable across DB rebuilds —
no future deliveries land in 2018; the only mutation would be
cricsheet retroactively adding/removing a 2018 match (rare, audited
manually).

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
            "filter_team", "filter_opponent", "filter_venue", "team_class")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux(**kwargs) -> AuxParams:
    return AuxParams(
        series_type=kwargs.get("series_type"),
        scope_to_team=kwargs.get("scope_to_team"),
        chip_team_class=kwargs.get("chip_team_class"),
    )


# Pinned per-team match counts (post 2026-04-28 per-team transform).
# Pool sizes implied: per_team × unique_teams ÷ 2.
# Unbounded men intl 2018: 53 unique teams, 3.92 per team → 3.92 × 53 / 2 ≈ 104 pool.
# Full-member 2018: 10 unique FM teams, 4.0 per team → 4.0 × 10 / 2 = 20 pool.
EXPECTED = [
    # (label, scope_kwargs, aux_kwargs, expected_per_team_matches)
    ("men_intl 2018 unbounded (53 unique teams)",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018"),
     dict(),
     3.92),
    ("men_intl 2018 full-member only (10 unique FM teams)",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018",
          team_class="full_member"),
     dict(),
     4.0),
    ("men_intl 2018 scope_to_team=Australia (regression marker)",
     dict(gender="male", team_type="international", season_from="2018", season_to="2018"),
     dict(scope_to_team="Australia"),
     # Aus's all-time tournament universe ∩ men_intl 2018 — narrowed
     # match pool (4 unique teams in those events). Per-team avg = 4.0.
     # Pre-2026-04-27 Mechanism A frontend would silently apply this
     # narrowing on internationals; today the frontend gates it on
     # team_type='club' so this row exists as a regression marker for
     # `_scope_to_team_clause` semantics.
     4.0),
    ("ipl 2018 unbounded (8 IPL teams)",
     dict(gender="male", team_type="club", season_from="2018", season_to="2018",
          tournament="Indian Premier League"),
     dict(),
     # 60 IPL matches, 8 teams → 60 × 2 / 8 = 15 per team.
     15.0),
    ("ipl 2018 scope_to_team=RCB (club narrow OK — tournament dominates)",
     dict(gender="male", team_type="club", season_from="2018", season_to="2018",
          tournament="Indian Premier League"),
     dict(scope_to_team="Royal Challengers Bengaluru"),
     15.0),
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
        # Per-team values are floats — tolerate 0.01 rounding drift.
        ok = actual is not None and abs(float(actual) - expected) <= 0.01
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
