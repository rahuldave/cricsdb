"""Sanity: team-batting ProbChip scope-avg baselines on
/teams/{team}/batting/distribution.

Hits the running API (default http://localhost:8000) and verifies the
TT1.B dual-query baseline plumbing on each chip's ProbRecord:

  1. **Shape**: every milestone ProbRecord on the `runs.milestones` +
     `run_rate.milestones` blocks carries `scope_avg`, `delta_pct`,
     `direction`, `sample_size` keys (spec §4.1).

  2. **Direction-tag table**: matches spec §5. p_lt_100 / p_rr_leq_*
     are lower_better; the remaining chips on the batting POV are
     higher_better.

  3. **scope_avg == league-side ProbRecord.value**: the spec says the
     league side runs the SAME observation pipeline with `team=None`.
     Hitting the endpoint a second time with the path-team replaced by
     a non-existent team (so the team-side becomes empty AND the dual-
     query is still launched) is intractable — instead we re-derive
     the league side directly by re-running the master-sample +
     dossier helpers in-process against the same FilterParams/AuxParams
     with team=None, and assert chip-by-chip equality.

  4. **delta_pct sign**: delta_pct == (value − scope_avg) / scope_avg
     × 100, rounded 1 dp; null when scope_avg null or 0 (spec §4.1
     via enrich_prob_record).

  5. **sample_size == league denom**: for each non-conditional chip,
     sample_size equals league total observations at the same scope.
     Conditional chips' sample_size is the league conditioning-event
     denom — different (smaller) number, but well-defined.

  6. **Per-window scope_avg independence (spec decision c4)**: form
     windows compute their own per-window scope_avg, NOT lifetime
     carry-over. We confirm by checking that at least one window's
     scope_avg differs from the lifetime scope_avg on a marquee chip.

Spec: internal_docs/spec-prob-baselines-teams.md §4 + §5 + §9.

Usage:
  uv run python tests/sanity/test_prob_baselines_team_batting.py
  # API server must be running on http://localhost:8000 (or --host).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_HOST = "http://localhost:8000"
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

sys.path.insert(0, PROJECT_ROOT)

from deebase import Database
from api import dependencies as deps

# spec §5 direction tags.
EXPECTED_RUNS_DIRECTIONS: dict[str, str] = {
    "p_lt_100":  "lower_better",
    "p_geq_100": "higher_better",
    "p_geq_150": "higher_better",
    "p_geq_200": "higher_better",
    "p_geq_230": "higher_better",
    "p_150_given_100": "higher_better",
    "p_200_given_150": "higher_better",
    "p_230_given_200": "higher_better",
    "p_double_at_10":  "higher_better",
}

EXPECTED_RR_DIRECTIONS: dict[str, str] = {
    "p_rr_leq_7":  "lower_better",
    "p_rr_leq_8":  "lower_better",
    "p_rr_geq_9":  "higher_better",
    "p_rr_geq_10": "higher_better",
}


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


async def derive_league_lifetime(filters_kwargs: dict) -> dict:
    """Re-run the master-sample + dossier in-process with team=None to
    cross-check the league-side numbers attached to ProbRecord.scope_avg.
    """
    from api.filters import FilterBarParams, AuxParams
    from api.routers.teams import (
        _innings_master_sample_team_batting,
        _distribution_dossier_team_batting,
    )

    fb_kwargs = {
        "gender": filters_kwargs.get("gender"),
        "team_type": filters_kwargs.get("team_type"),
        "tournament": filters_kwargs.get("tournament"),
        "season_from": filters_kwargs.get("season_from"),
        "season_to": filters_kwargs.get("season_to"),
        "filter_team": None,
        "filter_opponent": filters_kwargs.get("filter_opponent"),
        "filter_venue": filters_kwargs.get("filter_venue"),
        "team_class": filters_kwargs.get("team_class"),
        "series_type": filters_kwargs.get("series_type"),
    }
    filters = FilterBarParams(**fb_kwargs)
    aux = AuxParams(inning=filters_kwargs.get("inning"))
    obs = await _innings_master_sample_team_batting(None, filters, aux)
    return _distribution_dossier_team_batting(obs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    # Initialise the in-process db so the cross-check helper can call
    # _innings_master_sample_team_batting directly. The HTTP-side test
    # uses its own pooled db; the in-process helper needs its own.
    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")

    print(f"Sanity: team-batting ProbChip scope-avg — /teams/.../batting/distribution ({args.host})")
    all_passed = True

    # Mumbai Indians at IPL — busiest single-team scope, spec §9 subject.
    TEAM = "Mumbai Indians"
    SCOPE = {
        "gender": "male",
        "team_type": "club",
        "tournament": "Indian Premier League",
        "as_of_date": "2025-01-01",
    }

    resp = get(args.host, f"/api/v1/teams/{urllib.parse.quote(TEAM)}/batting/distribution", **SCOPE)
    lifetime = resp["lifetime"]
    runs_ms = lifetime["runs"]["milestones"]
    rr_ms = lifetime["run_rate"]["milestones"]

    # ─── Test 1: shape ──────────────────────────────────────────────
    print("\n  1. ProbRecord shape extension (lifetime milestones):")
    for chip in EXPECTED_RUNS_DIRECTIONS:
        pr = runs_ms.get(chip)
        ok = pr is not None and all(
            k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
        )
        _, line = check(
            f"runs.{chip} carries scope_avg / delta_pct / direction / sample_size",
            ok,
            f"keys={sorted(pr.keys()) if pr else 'missing'}",
        )
        print(line); all_passed &= ok
    for chip in EXPECTED_RR_DIRECTIONS:
        pr = rr_ms.get(chip)
        ok = pr is not None and all(
            k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
        )
        _, line = check(
            f"run_rate.{chip} carries scope_avg / delta_pct / direction / sample_size",
            ok,
            f"keys={sorted(pr.keys()) if pr else 'missing'}",
        )
        print(line); all_passed &= ok

    # ─── Test 2: direction-tag table ───────────────────────────────
    print("\n  2. Direction tags match spec §5:")
    for chip, expected_dir in EXPECTED_RUNS_DIRECTIONS.items():
        actual_dir = runs_ms.get(chip, {}).get("direction")
        ok = actual_dir == expected_dir
        _, line = check(f"runs.{chip} direction={expected_dir}", ok, f"actual={actual_dir}")
        print(line); all_passed &= ok
    for chip, expected_dir in EXPECTED_RR_DIRECTIONS.items():
        actual_dir = rr_ms.get(chip, {}).get("direction")
        ok = actual_dir == expected_dir
        _, line = check(f"run_rate.{chip} direction={expected_dir}", ok, f"actual={actual_dir}")
        print(line); all_passed &= ok

    # ─── Test 3: scope_avg matches in-process league-side dossier ──
    print("\n  3. scope_avg matches in-process league-side ProbRecord.value:")
    league_lifetime = asyncio.run(derive_league_lifetime(SCOPE))
    league_runs_ms = league_lifetime["runs"]["milestones"]
    league_rr_ms = league_lifetime["run_rate"]["milestones"]
    for chip in EXPECTED_RUNS_DIRECTIONS:
        api_sa = runs_ms[chip].get("scope_avg")
        league_v = league_runs_ms[chip].get("value")
        # The attached scope_avg is rounded to 4dp; league_v is too.
        ok = api_sa == league_v
        _, line = check(
            f"runs.{chip} scope_avg == league value",
            ok,
            f"api={api_sa}, league={league_v}",
        )
        print(line); all_passed &= ok
    for chip in EXPECTED_RR_DIRECTIONS:
        api_sa = rr_ms[chip].get("scope_avg")
        league_v = league_rr_ms[chip].get("value")
        ok = api_sa == league_v
        _, line = check(
            f"run_rate.{chip} scope_avg == league value",
            ok,
            f"api={api_sa}, league={league_v}",
        )
        print(line); all_passed &= ok

    # ─── Test 4: delta_pct sign math ───────────────────────────────
    print("\n  4. delta_pct = (value − scope_avg) / scope_avg × 100:")
    for chip in EXPECTED_RUNS_DIRECTIONS:
        pr = runs_ms[chip]
        value, sa, dp = pr["value"], pr.get("scope_avg"), pr.get("delta_pct")
        if value is None or not sa:
            continue
        expected = round((value - sa) / sa * 100, 1)
        ok = dp == expected
        _, line = check(
            f"runs.{chip} delta_pct = (value−scope_avg)/scope_avg×100",
            ok,
            f"expected={expected}, actual={dp}",
        )
        print(line); all_passed &= ok

    # ─── Test 5: sample_size = league denom ────────────────────────
    print("\n  5. sample_size == league ProbRecord.denom (same chip):")
    for chip in ("p_geq_150", "p_double_at_10"):
        ss = runs_ms[chip].get("sample_size")
        league_denom = league_runs_ms[chip].get("denom")
        ok = ss == league_denom
        _, line = check(
            f"runs.{chip} sample_size == league denom",
            ok,
            f"sample_size={ss}, league_denom={league_denom}",
        )
        print(line); all_passed &= ok

    # ─── Test 6: per-window scope_avg independence (spec c4) ──────
    print("\n  6. Per-window scope_avg differs from lifetime (spec c4):")
    # last_60d should have a different league sample than lifetime;
    # at least one chip's scope_avg must differ. Pick p_geq_150 (a
    # mid-density milestone — almost guaranteed to vary across
    # windows on the league side).
    lifetime_p150_sa = runs_ms["p_geq_150"].get("scope_avg")
    any_differ = False
    for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        window_runs = resp["form"].get(window_key, {}).get("runs", {}).get("milestones", {})
        wsa = window_runs.get("p_geq_150", {}).get("scope_avg")
        if wsa is not None and lifetime_p150_sa is not None and wsa != lifetime_p150_sa:
            any_differ = True
            print(f"         (window {window_key} p_geq_150 scope_avg={wsa} vs lifetime={lifetime_p150_sa})")
            break
    ok = any_differ
    _, line = check(
        "At least one form window's scope_avg differs from lifetime",
        ok,
        "every window scope_avg == lifetime — per-window slicing not firing",
    )
    print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
