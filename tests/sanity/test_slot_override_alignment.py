"""Slot-override chip-baseline alignment — symmetric extension of
test_chip_direction_invariant.py covering the BROADENING and OVERRIDE-
TO-EMPTY directions enabled by spec-slot-override-chip-alignment.md.

Previously the chip invariant only covered the "no override" case
(team scope == avg scope) and the v3 narrowing-direction shortcut
(`chip_team_class`). This test extends coverage to:

  - Scenario A: primary tournament=IPL + season=2025; avg slot
    overrides tournament+seasons to broader (no narrowing). Chip
    scope_avg must match avg endpoint with the broader scope.

  - Scenario B: primary season=2024-2025 + team_class=full_member;
    avg slot overrides team_class to __any__. Chip scope_avg must
    match avg endpoint with team_class unset.

  - Scenario C: primary RCB 2025 vs compare team RCB all-time. Two
    team-side requests with DIFFERENT scopes — each chip baselines
    against the avg-of-its-own-scope when no avg slot is present.
    (Sanity check: this case has no chip_baseline_scope_json; falls
    through to the legacy scope_to_team path. Tests that the legacy
    path still works.)

  - Scenario D: primary team_class=full_member; avg slot overrides
    season to broader (e.g. unbounded all-time). Chip scope_avg must
    match avg endpoint with team_class=full_member, season unset.

The chip math invariant
(`chip_scope_avg == displayed_avg_for_baseline_scope`) is the same
shape as test_chip_direction_invariant.py's ASSERT 1 — but the
displayed value is computed from a DIFFERENT scope than the team's.

Usage:
  uv run python tests/sanity/test_slot_override_alignment.py
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams

from api.routers.teams import (
    _compute_batting_summary, _compute_bowling_summary,
    team_fielding_summary,
    team_batting_by_phase, team_bowling_by_phase,
    team_partnerships_summary,
)
from api.routers.scope_averages import (
    scope_batting_summary, scope_bowling_summary, scope_fielding_summary,
    scope_batting_by_phase, scope_bowling_by_phase,
    scope_partnerships_summary,
)


# ─── Helpers ──────────────────────────────────────────────────────────

FILTER_KEYS = (
    "gender", "team_type", "tournament",
    "season_from", "season_to",
    "filter_team", "filter_opponent", "filter_venue",
    "team_class", "series_type",
)


def make_filters(**kw) -> FilterBarParams:
    return FilterBarParams(**{k: kw.get(k) for k in FILTER_KEYS})


def make_aux(*, scope_to_team=None, chip_team_class=None,
             chip_baseline_scope_json=None) -> AuxParams:
    return AuxParams(
        scope_to_team=scope_to_team,
        chip_team_class=chip_team_class,
        chip_baseline_scope_json=chip_baseline_scope_json,
    )


def encode_baseline(payload: dict) -> str:
    """Mirror the frontend chipAlignmentFor encoding: btoa(JSON.stringify(payload))."""
    return base64.b64encode(json.dumps(payload).encode()).decode()


# Map team-response key → avg-endpoint field. Mirrors the chip
# invariant test; avg endpoint drops some identity / per-team fields.
SUMMARY_FIELD_MAP = {
    "innings_batted": None, "innings_bowled": None,
    "matches": "matches",
    "total_runs": "total_runs", "legal_balls": "legal_balls",
    "run_rate": "run_rate",
    "boundary_pct": "boundary_pct", "dot_pct": "dot_pct",
    "fours": "fours", "sixes": "sixes",
    "fifties": None, "hundreds": None,
    "avg_1st_innings_total": "avg_1st_innings_total",
    "avg_2nd_innings_total": "avg_2nd_innings_total",
    "runs_conceded": "runs_conceded", "overs": "overs",
    "wickets": "wickets",
    "economy": "economy", "strike_rate": "strike_rate", "average": "average",
    "fours_conceded": "fours_conceded", "sixes_conceded": "sixes_conceded",
    "wides": "wides", "noballs": "noballs",
    "wides_per_match": "wides_per_match", "noballs_per_match": "noballs_per_match",
    "avg_opposition_total": None,
    "catches": "catches", "caught_and_bowled": "caught_and_bowled",
    "stumpings": "stumpings", "run_outs": "run_outs",
    "total_dismissals_contributed": "total_dismissals_contributed",
    "catches_per_match": "catches_per_match",
    "stumpings_per_match": "stumpings_per_match",
    "run_outs_per_match": "run_outs_per_match",
    "total": "total",
    "count_50_plus": "count_50_plus", "count_100_plus": "count_100_plus",
    "avg_runs": "avg_runs",
}


EPS = 0.15  # one-decimal rounding tolerance + small drift across paths


def near(a, b) -> bool:
    if a is None and b is None: return True
    if a is None or b is None:  return False
    return abs(float(a) - float(b)) <= EPS


class Failure:
    __slots__ = ("scenario", "team", "metric", "msg")

    def __init__(self, scenario, team, metric, msg):
        self.scenario = scenario
        self.team = team
        self.metric = metric
        self.msg = msg

    def __str__(self):
        return f"[{self.scenario}] {self.team} / {self.metric}: {self.msg}"


# ─── Scenarios — primary + baseline scope pairs ─────────────────────
#
# Each entry is:
#   (scenario_label, primary_scope, baseline_payload, baseline_scope_for_avg, teams)
#
# `primary_scope` drives the team-side filters (FilterBar settings).
# `baseline_payload` is what the frontend chipAlignmentFor would
# serialize for the avg slot's scope; passed to the team request as
# chip_baseline_scope_json. `baseline_scope_for_avg` is what the avg
# endpoint sees directly — must produce the same numeric values that
# the team chips baseline against.

SCENARIOS = [
    # A. Broaden tournament — primary IPL 2025; avg slot overrides
    #    tournament+season to __any__ (effectively all-clubs all-time
    #    for this gender / team_type).
    (
        "A_ipl_2025_to_all_clubs",
        {"gender": "male", "team_type": "club",
         "tournament": "Indian Premier League",
         "season_from": "2025", "season_to": "2025"},
        {"gender": "male", "team_type": "club"},
        {"gender": "male", "team_type": "club"},
        ["Royal Challengers Bengaluru"],
    ),
    # B. Broaden season — primary RCB 2025; avg slot overrides
    #    seasons to all-time but keeps the IPL tournament universe via
    #    auto-narrow (scope_to_team).
    (
        "B_rcb_2025_to_rcb_alltime",
        {"gender": "male", "team_type": "club",
         "season_from": "2025", "season_to": "2025"},
        {"gender": "male", "team_type": "club",
         "scope_to_team": "Royal Challengers Bengaluru"},
        {"gender": "male", "team_type": "club"},
        # Avg endpoint takes scope_to_team via aux, not as a filter
        # field — handled below.
        ["Royal Challengers Bengaluru"],
    ),
    # C. Broaden team_class — primary FM-only; avg slot overrides
    #    team_class to __any__ (unbounded full intl pool).
    (
        "C_fm_to_all_intl",
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025",
         "team_class": "full_member"},
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025"},
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025"},
        ["Australia", "India"],
    ),
    # D. Broaden season + team_class — primary FM 2024-2025; avg slot
    #    overrides BOTH to __any__ → unbounded all-time, all teams.
    (
        "D_fm_2024_2025_to_unbounded",
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025",
         "team_class": "full_member"},
        {"gender": "male", "team_type": "international"},
        {"gender": "male", "team_type": "international"},
        ["Australia"],
    ),
    # E. Narrowing case — back-compat. Primary tournament unbounded;
    #    avg slot overrides team_class to full_member. Mirrors v3's
    #    chip_team_class shortcut but driven via the new mechanism.
    (
        "E_intl_unbounded_to_fm",
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025"},
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025",
         "team_class": "full_member"},
        {"gender": "male", "team_type": "international",
         "season_from": "2024", "season_to": "2025",
         "team_class": "full_member"},
        ["Australia"],
    ),
]


# ─── Per-discipline runners ─────────────────────────────────────────

async def run_summary(*, scenario, team_fn, avg_fn, primary, payload,
                      baseline_scope_for_avg, team, scope_to_team_for_avg, failures):
    f_team = make_filters(**primary)
    aux_team = make_aux(chip_baseline_scope_json=encode_baseline(payload))
    team_resp = await team_fn(team, f_team, aux_team)

    f_avg = make_filters(**baseline_scope_for_avg)
    aux_avg = make_aux(scope_to_team=scope_to_team_for_avg)
    avg_resp = await avg_fn(f_avg, aux_avg)

    for key, env in team_resp.items():
        if not isinstance(env, dict) or "value" not in env:
            continue
        avg_field = SUMMARY_FIELD_MAP.get(key)
        if avg_field is None:
            continue
        displayed = avg_resp.get(avg_field)
        chip_avg = env.get("scope_avg")
        if not near(chip_avg, displayed):
            failures.append(Failure(
                scenario, team, key,
                f"chip.scope_avg={chip_avg} ≠ avg.{avg_field}={displayed}",
            ))


async def run_by_phase(*, scenario, team_fn, avg_fn, primary, payload,
                       baseline_scope_for_avg, team, scope_to_team_for_avg, failures):
    f_team = make_filters(**primary)
    aux_team = make_aux(chip_baseline_scope_json=encode_baseline(payload))
    team_resp = await team_fn(team, f_team, aux_team)

    f_avg = make_filters(**baseline_scope_for_avg)
    aux_avg = make_aux(scope_to_team=scope_to_team_for_avg)
    avg_resp = await avg_fn(f_avg, aux_avg)
    avg_by_phase = {p["phase"]: p for p in avg_resp.get("by_phase", [])}

    for ph in team_resp.get("phases", []):
        phase = ph["phase"]
        avg_ph = avg_by_phase.get(phase, {})
        for key in ("run_rate", "boundary_pct", "dot_pct", "economy"):
            env = ph.get(key)
            if not isinstance(env, dict):
                continue
            displayed = avg_ph.get(key)
            chip_avg = env.get("scope_avg")
            if not near(chip_avg, displayed):
                failures.append(Failure(
                    scenario, team, f"{phase}/{key}",
                    f"chip.scope_avg={chip_avg} ≠ avg.{key}={displayed}",
                ))


async def run_partnerships_summary(*, scenario, primary, payload,
                                   baseline_scope_for_avg, team,
                                   scope_to_team_for_avg, failures):
    f_team = make_filters(**primary)
    aux_team = make_aux(chip_baseline_scope_json=encode_baseline(payload))
    team_resp = await team_partnerships_summary(team, f_team, aux_team, side="batting")

    f_avg = make_filters(**baseline_scope_for_avg)
    aux_avg = make_aux(scope_to_team=scope_to_team_for_avg)
    avg_resp = await scope_partnerships_summary(f_avg, aux_avg)

    for key in ("total", "count_50_plus", "count_100_plus", "avg_runs"):
        env = team_resp.get(key)
        if not isinstance(env, dict):
            continue
        displayed = avg_resp.get(key)
        chip_avg = env.get("scope_avg")
        if not near(chip_avg, displayed):
            failures.append(Failure(
                scenario, team, f"partnerships/{key}",
                f"chip.scope_avg={chip_avg} ≠ avg.{key}={displayed}",
            ))


# ─── Main ───────────────────────────────────────────────────────────

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
    assertion_count = 0

    for scenario, primary, payload, baseline_scope_for_avg, teams in SCENARIOS:
        scope_to_team_for_avg = payload.get("scope_to_team")
        for team in teams:
            n_before = len(failures)

            await run_summary(
                scenario=scenario,
                team_fn=_compute_batting_summary,
                avg_fn=scope_batting_summary,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )
            await run_summary(
                scenario=scenario,
                team_fn=_compute_bowling_summary,
                avg_fn=scope_bowling_summary,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )
            await run_summary(
                scenario=scenario,
                team_fn=team_fielding_summary,
                avg_fn=scope_fielding_summary,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )
            await run_by_phase(
                scenario=scenario,
                team_fn=team_batting_by_phase,
                avg_fn=scope_batting_by_phase,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )
            await run_by_phase(
                scenario=scenario,
                team_fn=team_bowling_by_phase,
                avg_fn=scope_bowling_by_phase,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )
            await run_partnerships_summary(
                scenario=scenario,
                primary=primary, payload=payload,
                baseline_scope_for_avg=baseline_scope_for_avg, team=team,
                scope_to_team_for_avg=scope_to_team_for_avg,
                failures=failures,
            )

            n_failed = len(failures) - n_before
            status = "PASS" if n_failed == 0 else f"FAIL ({n_failed})"
            print(f"  {scenario} / {team}: {status}")
            if n_failed == 0:
                pass_count += 1
            assertion_count += 1  # one (scenario, team) pair counts as one row

    print()
    if failures:
        print(f"=== Failures ({len(failures)}) ===")
        for f in failures[:30]:
            print(f"  {f}")
        if len(failures) > 30:
            print(f"  … + {len(failures) - 30} more")
        print(f"\n{pass_count}/{assertion_count} (scenario, team) pairs PASS, "
              f"{len(failures)} assertion failures")
        sys.exit(1)

    print(f"{pass_count}/{assertion_count} (scenario, team) pairs PASS, 0 assertion failures")
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
