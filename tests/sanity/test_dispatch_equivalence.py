"""Endpoint dispatch equivalence: baseline-path vs live-path produce
byte-identical responses for the precomputed regime.

The regression suite (tests/regression/) compares HEAD vs patched
responses, but for URLs in the precomputed regime BOTH HEAD and
patched return baseline answers (since HEAD has the dispatch already
shipped). It doesn't independently prove baseline matches live —
only that baseline is stable.

This script bypasses the dispatch by calling the `_xxx_baseline` and
`_xxx_live` helpers directly with the same FilterParams + AuxParams,
then diffs the returned dicts. If any pair drifts, the dispatch is
unsafe (would return different numbers for the same scope based on
which path serves it).

Hits ~22 endpoints × ~10 scopes = ~220 pair-comparisons. Runs in a
few seconds since each is a single SQL query.

Usage:
    uv run python tests/sanity/test_dispatch_equivalence.py
    uv run python tests/sanity/test_dispatch_equivalence.py --db /tmp/cricket-prod-test.db
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams

from api.routers.scope_averages import (
    _summary_from_baseline,                _summary_live,
    _batting_summary_from_baseline,        _batting_summary_live,
    _batting_by_phase_from_baseline,       _batting_by_phase_live,
    _batting_by_season_from_baseline,      _batting_by_season_live,
    _bowling_summary_from_baseline,        _bowling_summary_live,
    _bowling_by_phase_from_baseline,       _bowling_by_phase_live,
    _bowling_by_season_from_baseline,      _bowling_by_season_live,
    _fielding_summary_from_baseline,       _fielding_summary_live,
    _fielding_by_season_from_baseline,     _fielding_by_season_live,
    _partnerships_summary_from_baseline,   _partnerships_summary_live,
    _partnerships_by_wicket_from_baseline, _partnerships_by_wicket_live,
    _partnerships_by_season_from_baseline, _partnerships_by_season_live,
)
from api.routers.teams import (
    _batting_aggregates_baseline,           _batting_aggregates_live,
    _bowling_aggregates_baseline,           _bowling_aggregates_live,
    _fielding_aggregates_baseline,          _fielding_aggregates_live,
    _batting_by_phase_aggregates_baseline,  _batting_by_phase_aggregates_live,
    _bowling_by_phase_aggregates_baseline,  _bowling_by_phase_aggregates_live,
)


def make_filters(**kwargs) -> FilterBarParams:
    """Construct a FilterBarParams with explicit values (FastAPI Depends
    bypassed). Defaults for unspecified keys are None."""
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue")
    f = FilterBarParams(**{k: kwargs.get(k) for k in keys})
    return f


def make_aux(scope_to_team: str | None = None) -> AuxParams:
    return AuxParams(series_type=None, scope_to_team=scope_to_team)


# ─── Test scopes ────────────────────────────────────────────────────────
#
# Each row: (label, scope-dict). Scope keys mirror FilterBarParams.
# All combinations stay within the precomputed regime — no
# filter_venue / rivalry / series_type set.

SCOPES = [
    ("ipl_2024",        {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League",         "season_from": "2024",   "season_to": "2024"}),
    ("ipl_2020_2024",   {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League",         "season_from": "2020",   "season_to": "2024"}),
    ("ipl_alltime",     {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League"}),
    ("bbl_2024",        {"gender": "male",   "team_type": "club",          "tournament": "Big Bash League",               "season_from": "2024/25", "season_to": "2024/25"}),
    ("wbbl",            {"gender": "female", "team_type": "club",          "tournament": "Women's Big Bash League"}),
    ("wpl_2024",        {"gender": "female", "team_type": "club",          "tournament": "Women's Premier League",        "season_from": "2024",   "season_to": "2024"}),
    ("t20wc_men_2024",  {"gender": "male",   "team_type": "international", "tournament": "ICC Men's T20 World Cup",       "season_from": "2024",   "season_to": "2024"}),
    ("t20wc_men_all",   {"gender": "male",   "team_type": "international", "tournament": "ICC Men's T20 World Cup"}),
    ("men_intl_2024",   {"gender": "male",   "team_type": "international", "season_from": "2024",                          "season_to": "2024"}),
    ("women_intl_all",  {"gender": "female", "team_type": "international"}),
    ("club_men_alltime",{"gender": "male",   "team_type": "club"}),
]

# Teams to test per scope (when applicable).
TEAMS_BY_SCOPE = {
    "ipl_2024":        ["Royal Challengers Bengaluru", "Mumbai Indians", "Chennai Super Kings"],
    "ipl_2020_2024":   ["Royal Challengers Bengaluru", "Mumbai Indians"],
    "ipl_alltime":     ["Royal Challengers Bengaluru"],
    "bbl_2024":        ["Sydney Sixers"],
    "wbbl":            ["Sydney Sixers"],
    "wpl_2024":        ["Royal Challengers Bengaluru"],
    "t20wc_men_2024":  ["Australia", "India"],
    "t20wc_men_all":   ["Australia"],
    "men_intl_2024":   ["India", "England"],
    "women_intl_all":  ["Australia"],
    "club_men_alltime":["Royal Challengers Bengaluru"],
}


# ─── Endpoint matrix ────────────────────────────────────────────────────
#
# (label, baseline_fn, live_fn, takes_team) — takes_team=True means the
# helper is the per-team variant called by /teams/{team}/* endpoints
# (and league counterparts via team=None for envelope wrap).

ENDPOINTS_NO_TEAM = [
    ("scope/summary",                _summary_from_baseline,                _summary_live),
    ("scope/batting/summary",        _batting_summary_from_baseline,        _batting_summary_live),
    ("scope/batting/by-phase",       _batting_by_phase_from_baseline,       _batting_by_phase_live),
    ("scope/batting/by-season",      _batting_by_season_from_baseline,      _batting_by_season_live),
    ("scope/bowling/summary",        _bowling_summary_from_baseline,        _bowling_summary_live),
    ("scope/bowling/by-phase",       _bowling_by_phase_from_baseline,       _bowling_by_phase_live),
    ("scope/bowling/by-season",      _bowling_by_season_from_baseline,      _bowling_by_season_live),
    ("scope/fielding/summary",       _fielding_summary_from_baseline,       _fielding_summary_live),
    ("scope/fielding/by-season",     _fielding_by_season_from_baseline,     _fielding_by_season_live),
    ("scope/partnerships/summary",   _partnerships_summary_from_baseline,   _partnerships_summary_live),
    ("scope/partnerships/by-wicket", _partnerships_by_wicket_from_baseline, _partnerships_by_wicket_live),
    ("scope/partnerships/by-season", _partnerships_by_season_from_baseline, _partnerships_by_season_live),
]

ENDPOINTS_TEAM = [
    ("team_batting_aggregates",          _batting_aggregates_baseline,          _batting_aggregates_live),
    ("team_bowling_aggregates",          _bowling_aggregates_baseline,          _bowling_aggregates_live),
    ("team_fielding_aggregates",         _fielding_aggregates_baseline,         _fielding_aggregates_live),
    ("team_batting_by_phase_aggregates", _batting_by_phase_aggregates_baseline, _batting_by_phase_aggregates_live),
    ("team_bowling_by_phase_aggregates", _bowling_by_phase_aggregates_baseline, _bowling_by_phase_aggregates_live),
]


def diff(a, b, path="") -> list[str]:
    """Recursive structural diff. Returns list of one-line difference
    descriptions. Float comparison tolerant to 0.05 (one decimal place
    rounding noise from SUM-then-divide vs AVG)."""
    if type(a) is not type(b):
        return [f"{path}: type {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a: out.append(f"{path}.{k}: missing in baseline")
            elif k not in b: out.append(f"{path}.{k}: missing in live")
            else: out.extend(diff(a[k], b[k], f"{path}.{k}"))
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [f"{path}: list len {len(a)} vs {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, f"{path}[{i}]"))
        return out
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            if a != b: return [f"{path}: {a!r} vs {b!r}"]
            return []
        if abs(float(a) - float(b)) > 0.05:
            return [f"{path}: {a} vs {b}"]
        return []
    if a != b:
        return [f"{path}: {a!r} vs {b!r}"]
    return []


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

    pass_count = 0
    fail_count = 0
    failures: list[tuple[str, str, list[str]]] = []

    for scope_label, scope in SCOPES:
        filters = make_filters(**scope)
        aux = make_aux()

        # No-team endpoints (always team=None, league baseline).
        for name, fn_b, fn_l in ENDPOINTS_NO_TEAM:
            # Re-create FilterParams each call — _team_innings_clause
            # mutates filters.team to None.
            f_b = make_filters(**scope); f_l = make_filters(**scope)
            try:
                bl = await fn_b(f_b, aux)
                lv = await fn_l(f_l, aux)
            except Exception as e:
                fail_count += 1
                failures.append((name, scope_label, [f"exception: {e}"]))
                continue
            d = diff(bl, lv)
            if d:
                fail_count += 1
                failures.append((name, scope_label, d))
            else:
                pass_count += 1

        # Per-team helpers.
        for team in TEAMS_BY_SCOPE.get(scope_label, []):
            for name, fn_b, fn_l in ENDPOINTS_TEAM:
                f_b = make_filters(**scope); f_l = make_filters(**scope)
                try:
                    bl = await fn_b(team, f_b, aux)
                    lv = await fn_l(team, f_l, aux)
                except Exception as e:
                    fail_count += 1
                    failures.append((f"{name}({team})", scope_label, [f"exception: {e}"]))
                    continue
                d = diff(bl, lv)
                if d:
                    fail_count += 1
                    failures.append((f"{name}({team})", scope_label, d))
                else:
                    pass_count += 1

    print(f"\n{pass_count} pairs equivalent, {fail_count} failures")
    if failures:
        print(f"\n=== Failures ({len(failures)}) ===")
        for name, scope, diffs in failures:
            print(f"\n* {name} | {scope}")
            for d in diffs[:5]:  # cap at 5 lines per failure
                print(f"    {d}")
            if len(diffs) > 5:
                print(f"    ... +{len(diffs) - 5} more")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
