"""DB-grounded numeric assertions on the Compare-tab avg column.

Pinned to closed historical windows so the expected values stay
stable across DB rebuilds:
  - Men's T20I 2024-2025 (international, full calendar window)
  - IPL 2025 (club, completed season — 74 matches)

For each (scope, team) combo we compute the team-side and avg-side
ground-truth numbers DIRECTLY from sqlite (concatenated run-rate
formula, raw legal-ball counts, etc.), then exercise the API and
assert agreement on TWO axes:

  AXIS A — endpoints match DB:
    team_resp[metric].value          == sqlite_team_value
    avg_resp[metric]                 == sqlite_avg_value

  AXIS B — chip ↔ displayed avg col agreement:
    team_resp[metric].scope_avg      == avg_resp[metric]

The 2026-04-27 baseline correction added a `team_class=full_member`
aux filter for the Compare-tab avg slot. AXIS B currently FAILS for
the cross-product (team without team_class, avg with team_class=fm)
because the team's `_league_aux` doesn't honour the avg slot's
team_class — chip baselines against the unbounded pool while the
avg col displays the FM pool. This test pins that contract so the
fix lands with proof.

Usage:
  uv run python tests/sanity/test_avg_baseline_numbers.py
  uv run python tests/sanity/test_avg_baseline_numbers.py --db /tmp/cricket-prod-test.db

Set CRICSDB_TEST_BASE_URL to point at a different uvicorn instance
(default http://localhost:8000).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams
from api.routers.teams import (
    _compute_batting_summary, _compute_bowling_summary,
    team_fielding_summary, team_partnerships_summary,
)
from api.routers.scope_averages import (
    scope_batting_summary, scope_bowling_summary,
    scope_fielding_summary, scope_partnerships_summary,
)


EPS = 0.15  # decimal-rounding + concat-vs-mean drift tolerance


def near(a, b) -> bool:
    if a is None and b is None: return True
    if a is None or b is None:  return False
    return abs(float(a) - float(b)) <= EPS


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux(**kwargs) -> AuxParams:
    return AuxParams(
        series_type=kwargs.get("series_type"),
        scope_to_team=kwargs.get("scope_to_team"),
        team_class=kwargs.get("team_class"),
        chip_team_class=kwargs.get("chip_team_class"),
    )


# ─── Closed-window scope definitions ──────────────────────────────────

INTL_2024_25 = dict(gender="male", team_type="international",
                    season_from="2024", season_to="2025")
IPL_2025 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2025", season_to="2025")
IPL_2024 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2024", season_to="2024")


# ─── Ground truth ─────────────────────────────────────────────────────
# Computed directly from sqlite on 2026-04-27. These are CLOSED
# windows; numbers should not change unless cricsheet retroactively
# edits a match (rare; flagged via update_recent dry-run). If a
# rebuild changes any of these, investigate before bumping.

GROUND_TRUTH = {
    # (scope_label, scope, metric, mode, team_or_None) → expected value
    # mode is "team" or "avg".
    # ───── INTL 2024-2025 ─────
    ("intl_24_25", "matches",  "team", "Australia"): 22,
    ("intl_24_25", "matches",  "team", "India"):     34,
    ("intl_24_25", "run_rate", "team", "Australia"): 9.91,
    ("intl_24_25", "run_rate", "team", "India"):     9.39,
    ("intl_24_25", "matches",  "avg",  None):                       870,
    ("intl_24_25", "run_rate", "avg",  None):                       7.52,
    ("intl_24_25", "matches",  "avg",  ("team_class", "full_member")): 140,
    ("intl_24_25", "run_rate", "avg",  ("team_class", "full_member")): 8.5,

    # ───── IPL 2025 ─────
    ("ipl_25", "matches",  "team", "Royal Challengers Bengaluru"): 15,
    ("ipl_25", "matches",  "team", "Sunrisers Hyderabad"):         14,
    ("ipl_25", "run_rate", "team", "Royal Challengers Bengaluru"): 9.69,
    ("ipl_25", "run_rate", "team", "Sunrisers Hyderabad"):         10.04,
    ("ipl_25", "matches",  "avg",  None):                           74,
    ("ipl_25", "run_rate", "avg",  None):                           9.63,
    # IPL avg with scope_to_team=RCB is identical (tournament filter dominates)
    ("ipl_25", "matches",  "avg", ("scope_to_team", "Royal Challengers Bengaluru")): 74,
    ("ipl_25", "run_rate", "avg", ("scope_to_team", "Royal Challengers Bengaluru")): 9.63,
}


# ─── Test runners ─────────────────────────────────────────────────────

class Failure:
    __slots__ = ("axis", "scope", "team", "metric", "msg")
    def __init__(self, axis, scope, team, metric, msg):
        self.axis = axis; self.scope = scope; self.team = team
        self.metric = metric; self.msg = msg
    def __str__(self):
        return f"[{self.axis}] {self.scope} / {self.team or 'avg'} / {self.metric}: {self.msg}"


def env_value(env: Any) -> float | None:
    if isinstance(env, dict): return env.get("value")
    return env


def env_scope_avg(env: Any) -> float | None:
    if isinstance(env, dict): return env.get("scope_avg")
    return None


async def assert_team_numbers(scope_label, scope, team, failures):
    """AXIS A — team endpoint values agree with ground truth."""
    f = make_filters(**scope)
    aux = make_aux()
    team_resp = await _compute_batting_summary(team, f, aux)

    # matches comes from the batting summary as a flat or envelope value.
    for metric in ("run_rate",):
        gt_key = (scope_label, metric, "team", team)
        if gt_key not in GROUND_TRUTH:
            continue
        expected = GROUND_TRUTH[gt_key]
        actual = env_value(team_resp.get(metric))
        if not near(actual, expected):
            failures.append(Failure(
                "AXIS_A_team", scope_label, team, metric,
                f"team value {actual} ≠ ground truth {expected}",
            ))


async def assert_avg_numbers(scope_label, scope, mode_key, failures):
    """AXIS A — avg endpoint values agree with ground truth.

    mode_key is None (no extra aux), ("team_class", "full_member"),
    or ("scope_to_team", <team>).
    """
    f = make_filters(**scope)
    aux_kwargs: dict = {}
    if mode_key:
        aux_kwargs[mode_key[0]] = mode_key[1]
    aux = make_aux(**aux_kwargs)
    avg_resp = await scope_batting_summary(f, aux)

    for metric in ("run_rate",):
        gt_key = (scope_label, metric, "avg", mode_key)
        if gt_key not in GROUND_TRUTH:
            continue
        expected = GROUND_TRUTH[gt_key]
        actual = avg_resp.get(metric)
        if not near(actual, expected):
            failures.append(Failure(
                "AXIS_A_avg", scope_label,
                f"mode={mode_key}", metric,
                f"avg value {actual} ≠ ground truth {expected}",
            ))


async def assert_chip_aligns(scope_label, scope, team, avg_aux_kwargs, failures, *, chip_team_class=None):
    """AXIS B — chip's scope_avg equals avg endpoint's displayed value
    when the avg col uses avg_aux_kwargs.

    The team request takes the ambient scope (no team_class) PLUS an
    optional `chip_team_class` aux hint that aligns chip baselines
    with the avg slot's scope. With chip_team_class=None this is the
    pre-fix behaviour (FAILS when avg_aux_kwargs has team_class set).
    """
    f_team = make_filters(**scope)
    f_avg = make_filters(**scope)
    team_aux_kwargs: dict = {}
    if chip_team_class:
        team_aux_kwargs["chip_team_class"] = chip_team_class
    team_aux = make_aux(**team_aux_kwargs)
    avg_aux = make_aux(**avg_aux_kwargs)

    team_resp = await _compute_batting_summary(team, f_team, team_aux)
    avg_resp = await scope_batting_summary(f_avg, avg_aux)

    for metric in ("run_rate", "boundary_pct", "dot_pct"):
        chip_avg = env_scope_avg(team_resp.get(metric))
        displayed = avg_resp.get(metric)
        if chip_avg is None and displayed is None:
            continue
        if not near(chip_avg, displayed):
            avg_label = avg_aux_kwargs or "(plain)"
            chip_label = f"chip_team_class={chip_team_class}" if chip_team_class else "chip-default"
            failures.append(Failure(
                "AXIS_B_chip", scope_label,
                f"{team} {chip_label} vs avg {avg_label}", metric,
                f"chip.scope_avg={chip_avg} ≠ avg.{metric}={displayed}",
            ))


# ─── Main matrix ──────────────────────────────────────────────────────

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

    failures: list[Failure] = []

    print("─── AXIS A: endpoint values vs DB ground truth ───")

    # INTL 2024-2025
    for team in ("Australia", "India"):
        await assert_team_numbers("intl_24_25", INTL_2024_25, team, failures)
    for mode_key in (None, ("team_class", "full_member")):
        await assert_avg_numbers("intl_24_25", INTL_2024_25, mode_key, failures)
        label = mode_key or "(plain)"
        print(f"  intl_24_25 avg {label}: checked")

    # IPL 2025
    for team in ("Royal Challengers Bengaluru", "Sunrisers Hyderabad"):
        await assert_team_numbers("ipl_25", IPL_2025, team, failures)
    for mode_key in (None, ("scope_to_team", "Royal Challengers Bengaluru")):
        await assert_avg_numbers("ipl_25", IPL_2025, mode_key, failures)
        label = mode_key or "(plain)"
        print(f"  ipl_25 avg {label}: checked")

    print()
    print("─── AXIS B: chip's scope_avg ↔ displayed avg col ───")

    # Existing alignment (no team_class anywhere) — must pass pre AND post fix
    for team in ("Australia", "India"):
        await assert_chip_aligns(
            "intl_24_25", INTL_2024_25, team,
            avg_aux_kwargs={}, failures=failures,
        )
        print(f"  intl_24_25 / {team} / plain-avg: checked")

    # Closed-league alignment (RCB, SRH on IPL 2025) — must pass
    for team in ("Royal Challengers Bengaluru", "Sunrisers Hyderabad"):
        await assert_chip_aligns(
            "ipl_25", IPL_2025, team,
            avg_aux_kwargs={}, failures=failures,
        )
        print(f"  ipl_25 / {team} / plain-avg: checked")

    # The bug case — avg col has team_class=fm but team request has no
    # chip_team_class hint. Pre-fix this FAILS; post-fix the team request
    # (with chip_team_class=full_member) aligns to the FM pool.
    for team in ("Australia", "India"):
        await assert_chip_aligns(
            "intl_24_25", INTL_2024_25, team,
            avg_aux_kwargs={"team_class": "full_member"},
            chip_team_class="full_member",
            failures=failures,
        )
        print(f"  intl_24_25 / {team} / FM-avg + chip_team_class=fm: checked")

    # Sanity: when avg has team_class=fm and team request DOESN'T pass
    # chip_team_class, the chip should NOT align (the alignment is
    # intentional and gated). Asserting the negative makes the gate
    # observable in tests.
    for team in ("Australia",):
        f_team = make_filters(**INTL_2024_25)
        f_avg = make_filters(**INTL_2024_25)
        team_aux = make_aux()
        avg_aux = make_aux(team_class="full_member")
        team_resp = await _compute_batting_summary(team, f_team, team_aux)
        avg_resp = await scope_batting_summary(f_avg, avg_aux)
        chip_avg = env_scope_avg(team_resp.get("run_rate"))
        displayed = avg_resp.get("run_rate")
        if near(chip_avg, displayed):
            failures.append(Failure(
                "AXIS_B_negative", "intl_24_25", team, "run_rate",
                f"expected divergence (no chip_team_class hint) but "
                f"chip.scope_avg={chip_avg} == avg={displayed}",
            ))
        print(f"  intl_24_25 / {team} / FM-avg + NO hint: checked (expect divergence)")

    print()
    if failures:
        print(f"=== FAILURES ({len(failures)}) ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
