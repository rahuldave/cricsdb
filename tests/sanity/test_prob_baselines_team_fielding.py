"""Sanity: team-fielding ProbChip scope-avg baselines on
/teams/{team}/fielding/distribution.

Mirrors test_prob_baselines_team_batting.py and team_bowling.py.
Three blocks: catches (4 chips, all directional) + run_outs +
stumpings (3-simple partitions, p_eq_1 direction=None and renders
no caption). 6 directional chips per partition block, 10 chips
total.

  1. ProbRecord shape extension on every milestone.
  2. Direction-tag table matches spec §5; p_eq_1 stays direction=None.
  3. scope_avg == in-process league-side ProbRecord.value.
  4. delta_pct math (skipped on direction=None chips).
  5. sample_size == league denom (non-conditional samples).
  6. Per-window scope_avg independence.

Spec: internal_docs/spec-prob-baselines-teams.md §4 + §5.
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

EXPECTED_CATCHES_DIRECTIONS: dict[str, str | None] = {
    "p_eq_0":  "lower_better",
    "p_geq_3": "higher_better",
    "p_geq_5": "higher_better",
    "p_geq_7": "higher_better",
}

EXPECTED_COUNT_DIRECTIONS: dict[str, str | None] = {
    "p_eq_0":  "lower_better",
    "p_eq_1":  None,
    "p_geq_2": "higher_better",
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
    from api.filters import FilterBarParams, AuxParams
    from api.routers.teams import (
        _innings_master_sample_team_fielding,
        _distribution_dossier_team_fielding,
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
    obs = await _innings_master_sample_team_fielding(None, filters, aux)
    return _distribution_dossier_team_fielding(obs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")

    print(f"Sanity: team-fielding ProbChip scope-avg — /teams/.../fielding/distribution ({args.host})")
    all_passed = True

    TEAM = "Mumbai Indians"
    SCOPE = {
        "gender": "male", "team_type": "club",
        "tournament": "Indian Premier League",
        "as_of_date": "2025-01-01",
    }
    resp = get(args.host, f"/api/v1/teams/{urllib.parse.quote(TEAM)}/fielding/distribution", **SCOPE)
    lifetime = resp["lifetime"]

    blocks = (
        ("catches",   lifetime["catches"]["milestones"],   EXPECTED_CATCHES_DIRECTIONS),
        ("run_outs",  lifetime["run_outs"]["milestones"],  EXPECTED_COUNT_DIRECTIONS),
        ("stumpings", lifetime["stumpings"]["milestones"], EXPECTED_COUNT_DIRECTIONS),
    )

    # ─── Test 1: shape ──────────────────────────────────────────────
    print("\n  1. ProbRecord shape extension:")
    for block_name, ms, dirs in blocks:
        for chip in dirs:
            pr = ms.get(chip)
            ok = pr is not None and all(
                k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
            )
            _, line = check(
                f"{block_name}.{chip} carries scope_avg / delta_pct / direction / sample_size",
                ok,
                f"keys={sorted(pr.keys()) if pr else 'missing'}",
            )
            print(line); all_passed &= ok

    # ─── Test 2: direction tags ─────────────────────────────────────
    print("\n  2. Direction tags match spec §5:")
    for block_name, ms, dirs in blocks:
        for chip, expected_dir in dirs.items():
            actual_dir = ms.get(chip, {}).get("direction")
            ok = actual_dir == expected_dir
            _, line = check(f"{block_name}.{chip} direction={expected_dir}", ok, f"actual={actual_dir}")
            print(line); all_passed &= ok

    # ─── Test 3: scope_avg matches in-process league value ─────────
    print("\n  3. scope_avg matches in-process league-side ProbRecord.value:")
    league_lifetime = asyncio.run(derive_league_lifetime(SCOPE))
    for block_name, ms, dirs in blocks:
        league_ms = league_lifetime[block_name]["milestones"]
        for chip in dirs:
            api_sa = ms[chip].get("scope_avg")
            league_v = league_ms[chip].get("value")
            ok = api_sa == league_v
            _, line = check(
                f"{block_name}.{chip} scope_avg == league value",
                ok,
                f"api={api_sa}, league={league_v}",
            )
            print(line); all_passed &= ok

    # ─── Test 4: delta_pct math (direction=null chips have None delta) ──
    print("\n  4. delta_pct = (value − scope_avg) / scope_avg × 100:")
    for block_name, ms, dirs in blocks:
        for chip, direction in dirs.items():
            pr = ms[chip]
            v, sa, dp = pr["value"], pr.get("scope_avg"), pr.get("delta_pct")
            if direction is None:
                # Descriptive chip — delta_pct must be None.
                ok = dp is None
                _, line = check(
                    f"{block_name}.{chip} direction=None → delta_pct=None",
                    ok,
                    f"actual={dp}",
                )
                print(line); all_passed &= ok
                continue
            if v is None or not sa:
                continue
            expected = round((v - sa) / sa * 100, 1)
            ok = dp == expected
            _, line = check(
                f"{block_name}.{chip} delta_pct math",
                ok,
                f"expected={expected}, actual={dp}",
            )
            print(line); all_passed &= ok

    # ─── Test 5: sample_size == league denom ───────────────────────
    print("\n  5. sample_size == league ProbRecord.denom (spot checks):")
    samples = (
        ("catches",   "p_geq_3"),
        ("catches",   "p_geq_5"),
        ("run_outs",  "p_geq_2"),
        ("stumpings", "p_geq_2"),
    )
    for block_name, chip in samples:
        ms = lifetime[block_name]["milestones"]
        league_ms = league_lifetime[block_name]["milestones"]
        ok = ms[chip].get("sample_size") == league_ms[chip].get("denom")
        _, line = check(
            f"{block_name}.{chip} sample_size == league denom",
            ok,
            f"sample_size={ms[chip].get('sample_size')}, league_denom={league_ms[chip].get('denom')}",
        )
        print(line); all_passed &= ok

    # ─── Test 6: per-window scope_avg independence ─────────────────
    print("\n  6. Per-window scope_avg differs from lifetime (spec c4):")
    lifetime_sa = lifetime["catches"]["milestones"]["p_geq_3"].get("scope_avg")
    any_differ = False
    for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        wms = resp["form"].get(window_key, {}).get("catches", {}).get("milestones", {})
        wsa = wms.get("p_geq_3", {}).get("scope_avg")
        if wsa is not None and lifetime_sa is not None and wsa != lifetime_sa:
            any_differ = True
            print(f"         (window {window_key} catches.p_geq_3 scope_avg={wsa} vs lifetime={lifetime_sa})")
            break
    ok = any_differ
    _, line = check("At least one form window's scope_avg differs from lifetime", ok)
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
