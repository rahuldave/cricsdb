"""Chip-direction invariant — Compare-tab chips never lie.

The Teams Compare tab's "average" column displays per-innings values
(spec-avg-column-per-innings.md Commit 2). Each metric on the team
column carries a chip with `{value, scope_avg, delta_pct, direction}`.

For the chip to be visually honest, three invariants must hold for
every chip-bearing metric (direction != None) on every
(scope × team) combo:

  ASSERT 1 — chip_scope_avg == displayed_avg
    The chip's scope_avg field equals the value the avg column
    displays for the same metric on the same scope. If they diverge,
    the user reads the avg column number and the chip arrow as
    contradicting each other (the original bug).

  ASSERT 2 — delta_pct equals raw signed percentage difference
    delta_pct == round((value - scope_avg) / scope_avg × 100, 1)
    Just verifies wrap_metric's math. Direction tag does NOT flip
    the sign — sign is always the raw (value-avg) sign. The
    rendering layer (MetricDelta in the frontend) does the
    direction-aware color flip.

  ASSERT 3 — visual color matches direction × side-of-baseline
    Computed color = green if (direction='higher_better' and value > avg)
                  or (direction='lower_better' and value < avg).
    Otherwise red. ASSERT 3 just confirms the rendering rule is
    well-defined for this envelope; given ASSERT 1 + 2, it always
    holds.

Runs the matrix:
  scopes × teams × {summary, by-phase, by-wicket} per discipline
  ≈ 8 × 3 × ~25 chip-bearing metrics ≈ 600 assertions.

Includes the canonical reproducer (RCB + SRH + IPL 2025) as the
first row in the matrix — a permanent regression marker for the
original bug.

Conventions 2 and 3 in perf-bucket-baselines.md were unified
2026-04-26: both team-side and avg-endpoint return delivery COUNT
for wides/noballs (not run-total), and both treat `catches` as
inclusive of caught-and-bowled. ASSERT 1 now runs against every
chip-bearing metric without a skip-list — any divergence is a
real bug.

Usage:
  uv run python tests/sanity/test_chip_direction_invariant.py
  uv run python tests/sanity/test_chip_direction_invariant.py --db /tmp/cricket-prod-test.db
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from copy import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams

from api.routers.teams import (
    _compute_batting_summary, _compute_bowling_summary,
    team_fielding_summary,    # async route fn — call directly with team+filters+aux
    team_batting_by_phase,
    team_bowling_by_phase,
    team_partnerships_summary,
    team_partnerships_by_wicket,
)
from api.routers.scope_averages import (
    scope_batting_summary, scope_bowling_summary, scope_fielding_summary,
    scope_batting_by_phase, scope_bowling_by_phase,
    scope_partnerships_summary, scope_partnerships_by_wicket,
)


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux(scope_to_team: str | None = None, series_type: str | None = None,
             team_class: str | None = None) -> AuxParams:
    return AuxParams(
        series_type=series_type, scope_to_team=scope_to_team,
        team_class=team_class,
    )


def league_avg_aux_for(team_type: str | None, team: str) -> AuxParams:
    """Mirror of api.routers.teams._league_aux + the frontend's
    fetchSlot gate: scope_to_team narrows the avg only for closed
    leagues (team_type='club'). For internationals the avg defaults
    to the full pool, so chip ↔ displayed-avg agreement requires
    NOT passing scope_to_team to the avg endpoint either."""
    if team_type == "club":
        return make_aux(scope_to_team=team)
    return make_aux()


# ─── Test scopes ────────────────────────────────────────────────────────
#
# Includes the CANONICAL REPRODUCER (RCB + SRH + IPL 2025) as the first
# entry — this is the (scope, primary, compare) combo that surfaced the
# original bug. Failure here = regression.

SCOPES = [
    ("ipl_2025_rcb_srh",  {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League",   "season_from": "2025", "season_to": "2025"},
                          ["Royal Challengers Bengaluru", "Sunrisers Hyderabad"]),
    ("ipl_2024",          {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League",   "season_from": "2024", "season_to": "2024"},
                          ["Royal Challengers Bengaluru", "Mumbai Indians"]),
    ("ipl_2020_2024",     {"gender": "male",   "team_type": "club",          "tournament": "Indian Premier League",   "season_from": "2020", "season_to": "2024"},
                          ["Royal Challengers Bengaluru"]),
    ("rcb_unbounded",     {"gender": "male",   "team_type": "club"},
                          ["Royal Challengers Bengaluru"]),
    ("t20wc_men_2024",    {"gender": "male",   "team_type": "international", "tournament": "ICC Men's T20 World Cup", "season_from": "2024", "season_to": "2024"},
                          ["Australia", "India"]),
    ("aus_unbounded",     {"gender": "male",   "team_type": "international"},
                          ["Australia"]),
    # Canonical international reproducer for the 2026-04-27 avg-baseline
    # correction. Pre-fix, scope_to_team auto-narrow gave a 67-match
    # Aus-centered baseline; post-fix the avg col defaults to the full
    # 870-match pool. This row asserts chip ↔ displayed-avg agreement
    # under the new (un-narrowed) baseline. India is included because
    # the 2024 + 2025 calendar puts both teams in the same window with
    # very different schedules, so any leakage shows up immediately.
    ("aus_ind_men_intl_2024_2025",
                          {"gender": "male",   "team_type": "international",
                           "season_from": "2024", "season_to": "2025"},
                          ["Australia", "India"]),
    ("wpl_2024",          {"gender": "female", "team_type": "club",          "tournament": "Women's Premier League",  "season_from": "2024", "season_to": "2024"},
                          ["Royal Challengers Bengaluru"]),
    ("bbl_2024_25",       {"gender": "male",   "team_type": "club",          "tournament": "Big Bash League",         "season_from": "2024/25", "season_to": "2024/25"},
                          ["Sydney Sixers"]),
]


# ─── Comparison helpers ─────────────────────────────────────────────────

EPS = 0.15  # one decimal-place rounding tolerance + small drift across paths


def near(a, b) -> bool:
    """Float-tolerant equality. None vs None is equal; None vs not-None is not."""
    if a is None and b is None: return True
    if a is None or b is None:  return False
    return abs(float(a) - float(b)) <= EPS


def envelope_value(env: dict | None) -> float | None:
    return None if env is None else env.get("value")


def envelope_scope_avg(env: dict | None) -> float | None:
    return None if env is None else env.get("scope_avg")


def envelope_delta_pct(env: dict | None) -> float | None:
    return None if env is None else env.get("delta_pct")


def envelope_direction(env: dict | None) -> str | None:
    return None if env is None else env.get("direction")


# Field renames between team-side response and avg endpoint response.
# All other field names align.
SUMMARY_FIELD_MAP = {
    # team_response_key: avg_endpoint_field
    "innings_batted":        None,    # avg endpoint drops these
    "innings_bowled":        None,
    "matches":               "matches",
    "total_runs":            "total_runs",
    "legal_balls":           "legal_balls",
    "run_rate":              "run_rate",
    "boundary_pct":          "boundary_pct",
    "dot_pct":               "dot_pct",
    "fours":                 "fours",
    "sixes":                 "sixes",
    "fifties":               None,    # not on avg endpoint
    "hundreds":              None,
    "avg_1st_innings_total": "avg_1st_innings_total",
    "avg_2nd_innings_total": "avg_2nd_innings_total",
    "runs_conceded":         "runs_conceded",
    "overs":                 "overs",
    "wickets":               "wickets",
    "economy":               "economy",
    "strike_rate":           "strike_rate",
    "average":               "average",
    "fours_conceded":        "fours_conceded",
    "sixes_conceded":        "sixes_conceded",
    "wides":                 "wides",
    "noballs":               "noballs",
    "wides_per_match":       "wides_per_match",
    "noballs_per_match":     "noballs_per_match",
    "avg_opposition_total":  None,    # not on avg endpoint
    "catches":               "catches",
    "caught_and_bowled":     "caught_and_bowled",
    "stumpings":             "stumpings",
    "run_outs":              "run_outs",
    "total_dismissals_contributed": "total_dismissals_contributed",
    "catches_per_match":     "catches_per_match",
    "stumpings_per_match":   "stumpings_per_match",
    "run_outs_per_match":    "run_outs_per_match",
    "total":                 "total",
    "count_50_plus":         "count_50_plus",
    "count_100_plus":        "count_100_plus",
    "avg_runs":              "avg_runs",
}


# ─── Assertions ─────────────────────────────────────────────────────────

class Failure:
    __slots__ = ("test", "scope", "team", "metric", "msg")

    def __init__(self, test, scope, team, metric, msg):
        self.test = test
        self.scope = scope
        self.team = team
        self.metric = metric
        self.msg = msg

    def __str__(self):
        return f"[{self.test}] {self.scope} / {self.team} / {self.metric}: {self.msg}"


def check_assert_1(env, displayed, *, test, scope, team, metric) -> Failure | None:
    """chip_scope_avg == displayed_avg.

    Enforced on EVERY field in the team-summary envelope (whether
    chip-bearing or not) since Convention 2 + 3 were unified
    2026-04-26. Counts (direction=None) don't render chip arrows
    but the underlying scope_avg should still match the avg endpoint."""
    chip_avg = envelope_scope_avg(env)
    if not near(chip_avg, displayed):
        return Failure(test, scope, team, metric,
                       f"ASSERT 1: chip_scope_avg={chip_avg} ≠ displayed_avg={displayed}")
    return None


def check_assert_2(env, *, test, scope, team, metric) -> Failure | None:
    """delta_pct == round((value - scope_avg) / scope_avg × 100, 1).
    No direction-based sign flip — direction is informational only,
    consumed by the rendering layer to pick chip color."""
    direction = envelope_direction(env)
    if direction is None:
        return None
    value = envelope_value(env)
    avg = envelope_scope_avg(env)
    delta = envelope_delta_pct(env)
    if value is None or avg is None or avg == 0 or delta is None:
        return None
    expected = round((value - avg) / avg * 100, 1)
    if abs(expected - delta) > 0.1:
        return Failure(test, scope, team, metric,
                       f"ASSERT 2: delta_pct={delta} ≠ raw {(value - avg)/avg*100:.4f} "
                       f"(rounded {expected})")
    return None


def check_assert_3(env, *, test, scope, team, metric) -> Failure | None:
    """Chip color (green/red) is well-defined per direction × sign(delta_pct).
    Given ASSERT 1+2, this always holds — kept as a sanity check that
    direction tag and metric semantic agree (e.g. dot_pct on bowling
    side is higher_better; on batting side it's lower_better).

    GREEN if (higher_better AND value > avg) OR (lower_better AND value < avg).
    """
    direction = envelope_direction(env)
    if direction is None:
        return None
    value = envelope_value(env)
    avg = envelope_scope_avg(env)
    if value is None or avg is None:
        return None
    if abs(value - avg) < 1e-9:
        return None  # neutral
    team_higher = value > avg
    expected_green = (direction == "higher_better" and team_higher) or \
                     (direction == "lower_better" and not team_higher)
    delta = envelope_delta_pct(env)
    if delta is None:
        return None
    # Frontend rule: green if (direction='higher_better' and delta>0)
    #                      or (direction='lower_better' and delta<0).
    rendered_green = (direction == "higher_better" and delta > 0) or \
                     (direction == "lower_better" and delta < 0)
    if rendered_green != expected_green:
        return Failure(test, scope, team, metric,
                       f"ASSERT 3: rendered green={rendered_green} but "
                       f"value={value} {'>' if team_higher else '<'} avg={avg} "
                       f"with direction={direction} → expected green={expected_green}")
    return None


# ─── Per-discipline runners ─────────────────────────────────────────────

async def run_summary(*, name, team_fn, avg_fn, scope_label, scope, team, failures):
    """Run team-summary endpoint and matched avg endpoint, then check
    every envelope's chip_scope_avg against the avg's displayed value
    + delta_pct sign math."""
    f_team = make_filters(**scope); f_avg = make_filters(**scope)
    aux_team = make_aux()
    aux_avg = league_avg_aux_for(scope.get("team_type"), team)

    # team-side helper sigs differ — _compute_*_summary takes (team, filters, aux);
    # team_fielding_summary / team_partnerships_summary are route fns with the
    # same signature.
    team_resp = await team_fn(team, f_team, aux_team)
    avg_resp  = await avg_fn(f_avg, aux_avg)

    for key, env in team_resp.items():
        if not isinstance(env, dict) or "value" not in env:
            continue  # skip non-envelope fields (team, highest_total, etc.)
        avg_field = SUMMARY_FIELD_MAP.get(key)
        if avg_field is None:
            continue  # field doesn't exist on avg endpoint (or shouldn't compare)
        displayed = avg_resp.get(avg_field)
        for chk in (
            check_assert_1(env, displayed, test=name, scope=scope_label, team=team, metric=key),
            check_assert_2(env, test=name, scope=scope_label, team=team, metric=key),
            check_assert_3(env, test=name, scope=scope_label, team=team, metric=key),
        ):
            if chk: failures.append(chk)


async def run_partnerships_summary(*, scope_label, scope, team, failures):
    f_team = make_filters(**scope); f_avg = make_filters(**scope)
    aux_team = make_aux()
    aux_avg = league_avg_aux_for(scope.get("team_type"), team)
    team_resp = await team_partnerships_summary(team, f_team, aux_team, side="batting")
    avg_resp = await scope_partnerships_summary(f_avg, aux_avg)
    for key in ("total", "count_50_plus", "count_100_plus", "avg_runs"):
        env = team_resp.get(key)
        displayed = avg_resp.get(key)
        for chk in (
            check_assert_1(env, displayed, test="partnerships/summary",
                           scope=scope_label, team=team, metric=key),
            check_assert_2(env, test="partnerships/summary",
                           scope=scope_label, team=team, metric=key),
            check_assert_3(env, test="partnerships/summary",
                           scope=scope_label, team=team, metric=key),
        ):
            if chk: failures.append(chk)


async def run_by_phase(*, name, team_fn, avg_fn, scope_label, scope, team, failures):
    f_team = make_filters(**scope); f_avg = make_filters(**scope)
    aux_team = make_aux()
    aux_avg = league_avg_aux_for(scope.get("team_type"), team)
    team_resp = await team_fn(team, f_team, aux_team)
    avg_resp = await avg_fn(f_avg, aux_avg)
    avg_by_phase = {p["phase"]: p for p in avg_resp.get("by_phase", [])}
    team_by_phase = team_resp.get("phases", [])
    for ph in team_by_phase:
        phase = ph["phase"]
        avg_ph = avg_by_phase.get(phase, {})
        # Chip envelopes are on rate metrics only.
        for key in ("run_rate", "boundary_pct", "dot_pct", "economy"):
            env = ph.get(key)
            if not isinstance(env, dict): continue
            displayed = avg_ph.get(key)
            metric_label = f"{phase}/{key}"
            for chk in (
                check_assert_1(env, displayed, test=name,
                               scope=scope_label, team=team, metric=metric_label),
                check_assert_2(env, test=name,
                               scope=scope_label, team=team, metric=metric_label),
                check_assert_3(env, test=name,
                               scope=scope_label, team=team, metric=metric_label),
            ):
                if chk: failures.append(chk)


async def run_partnerships_by_wicket(*, scope_label, scope, team, failures):
    f_team = make_filters(**scope); f_avg = make_filters(**scope)
    aux_team = make_aux()
    aux_avg = league_avg_aux_for(scope.get("team_type"), team)
    team_resp = await team_partnerships_by_wicket(team, f_team, aux_team, side="batting")
    avg_resp = await scope_partnerships_by_wicket(f_avg, aux_avg)
    avg_by_wn = {r["wicket_number"]: r for r in avg_resp.get("by_wicket", [])}
    for r in team_resp.get("by_wicket", []):
        wn = r["wicket_number"]
        avg_r = avg_by_wn.get(wn, {})
        for key in ("n", "avg_runs"):
            env = r.get(key)
            if not isinstance(env, dict): continue
            displayed = avg_r.get(key)
            metric_label = f"w{wn}/{key}"
            for chk in (
                check_assert_1(env, displayed, test="partnerships/by-wicket",
                               scope=scope_label, team=team, metric=metric_label),
                check_assert_2(env, test="partnerships/by-wicket",
                               scope=scope_label, team=team, metric=metric_label),
                check_assert_3(env, test="partnerships/by-wicket",
                               scope=scope_label, team=team, metric=metric_label),
            ):
                if chk: failures.append(chk)


# ─── Main ───────────────────────────────────────────────────────────────

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
    pass_count = 0

    for scope_label, scope, teams in SCOPES:
        for team in teams:
            n_before = len(failures)

            await run_summary(
                name="batting/summary",
                team_fn=_compute_batting_summary,
                avg_fn=scope_batting_summary,
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )
            await run_summary(
                name="bowling/summary",
                team_fn=_compute_bowling_summary,
                avg_fn=scope_bowling_summary,
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )
            await run_summary(
                name="fielding/summary",
                team_fn=team_fielding_summary,
                avg_fn=scope_fielding_summary,
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )
            await run_partnerships_summary(
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )

            await run_by_phase(
                name="batting/by-phase",
                team_fn=team_batting_by_phase,
                avg_fn=scope_batting_by_phase,
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )
            await run_by_phase(
                name="bowling/by-phase",
                team_fn=team_bowling_by_phase,
                avg_fn=scope_bowling_by_phase,
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )

            await run_partnerships_by_wicket(
                scope_label=scope_label, scope=scope, team=team, failures=failures,
            )

            n_failed = len(failures) - n_before
            status = "PASS" if n_failed == 0 else f"FAIL ({n_failed})"
            print(f"  {scope_label} / {team}: {status}")
            if n_failed == 0:
                pass_count += 1

    print()
    if failures:
        print(f"=== Failures ({len(failures)}) ===")
        for f in failures[:30]:
            print(f"  {f}")
        if len(failures) > 30:
            print(f"  … + {len(failures) - 30} more")
        print(f"\n{pass_count} (scope, team) pairs PASS, {len(failures)} assertion failures")
        sys.exit(1)

    print(f"{pass_count} (scope, team) pairs PASS, 0 assertion failures")
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
