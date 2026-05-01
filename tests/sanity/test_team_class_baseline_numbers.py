"""DB-grounded numeric assertions for the v3 team_class FilterBar
migration. Pinned to closed historical windows so expected values
stay stable across DB rebuilds:
  - Men's T20I 2024-2025 (intl, full calendar window)
  - Women's T20I 2024-2025 (intl, FM symmetry sanity)
  - IPL 2025 (club, completed — defensive gate proof)

Three axes per anchor:
  AXIS A — match-count anchors via summary endpoints (SQL-vs-API
           contract: API uses pinned GROUND_TRUTH numbers derived by
           a DB-only subagent; if the constant equals the API count,
           the v3 backend correctly applies team_class on the live
           path).
  AXIS B — top-N batter/bowler lists via raw SQL (the API leaderboard
           sorts by avg/SR; A9-A12 anchors are by total_runs / wickets,
           so this is SQL-direct under filters.build()'s output).
  AXIS C — chip baselines via summary + scope endpoints (run rates).

For the FM-mode anchors, FilterBar `team_class=full_member` must
narrow team-side data correctly. For club anchors the defensive
backend gate must make team_class a no-op (Bp2 must equal Bp1).

Ground truth derived 2026-04-28 by a DB-only subagent (no api/ source
reads) — see internal_docs/team-class-anchor-numbers.md.

Usage:
  uv run python tests/sanity/test_team_class_baseline_numbers.py
  uv run python tests/sanity/test_team_class_baseline_numbers.py --db tmp/cricket-prod-test.db
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
from api.routers.teams import team_summary, _compute_batting_summary
from api.routers.scope_averages import scope_summary, scope_batting_summary
from api.full_members import full_member_clause


EPS = 0.05


def near(a, b) -> bool:
    if a is None and b is None: return True
    if a is None or b is None:  return False
    return abs(float(a) - float(b)) <= EPS


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux(**kwargs) -> AuxParams:
    return AuxParams(
        scope_to_team=kwargs.get("scope_to_team"),
        chip_team_class=kwargs.get("chip_team_class"),
    )


def env_value(env):
    return env.get("value") if isinstance(env, dict) else env


# ─── Closed-window scope definitions ──────────────────────────────────
INTL_24_25_M = dict(gender="male", team_type="international",
                    season_from="2024", season_to="2025")
INTL_24_25_W = dict(gender="female", team_type="international",
                    season_from="2024", season_to="2025")
IPL_2025 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2025", season_to="2025")


# ─── Ground truth (pinned 2026-04-28) ─────────────────────────────────
GROUND_TRUTH = {
    # A1, A2, A13, A14, A17, A18, D1, D2, Bp4: avg-col matches via
    # /scope/averages/summary — PER-TEAM averages post 2026-04-28
    # per-team transform (spec-avg-col-per-team-transform.md). Pool
    # implied: per_team × unique_teams ÷ 2.
    "A1": 17.4,    # 870 × 2 / 100 unique teams
    "A2": 25.45,   # 140 × 2 / 11 unique FM teams
    "A3": 22, "A4": 16,    # team-side raw counts (unchanged)
    "A5": 34, "A6": 31,
    "A7": 17, "A8": 0,
    "A13": 4.63,   # 44 × 2 / 19 unique teams in T20 WC
    "A14": 3.2,    # 16 × 2 / 10 unique FM teams in T20 WC
    "A15a": 1, "A15b": 1,
    "A16a": 0, "A16b": 0,
    "A17": 1.0, "A18": 1.0,  # Wankhede 1 match × 2 / 2 teams = 1.0
    "C1": 9.92, "C2": 9.82,
    "C3": 7.52, "C4": 8.50,
    "D1": 14.54,   # 596 × 2 / 82 unique women's teams
    "D2": 17.64,   # 97  × 2 / 11 unique women's FM teams
    "Bp1": 15, "Bp3": 14,
    "Bp4": 14.8,   # 74 IPL 2025 matches × 2 / 10 IPL teams
}


# A9 — Top-10 batters by total_runs, men_intl 2024-25 unbounded.
# 9th-10th place is sensitive to small DB drift (cricsheet retroactively
# edits a delivery and a tied pair flips); current pin reflects DB at
# commit-5 capture time. Anchor file's snapshot from 2026-04-28 had
# 987187b9 (Zeeshan Ali) at 9 with 914; current DB shows 908, dropping
# him to 11 (Buttler at 908 wins on DESC tiebreak). Re-capture if the
# tied entries shift further.
A9_TOP10_BATTERS_UNBOUNDED = [
    "6a97c7a4", "6f02fe2a", "df1f2f29", "33b67317", "552b228c",
    "06cad4f0", "074acfb4", "8ee36b18", "e3eb9e46", "99b75528",
]
# A10 — Top-10 batters, FM-only — completely different leaderboard
A10_TOP10_BATTERS_FM = [
    "8ee36b18", "99b75528", "f29185a1", "3d284ca3", "b0482a1d",
    "b8cc58c9", "1fc6ef83", "33609a8c", "9e52a414", "a4cc73aa",
]
# A11 — Top-10 bowlers by wickets, unbounded
A11_TOP10_BOWLERS_UNBOUNDED = [
    "e741ed8f", "596982e6", "d3851cd8", "c9d05f1a", "5935d694",
    "3c8faed4", "ef18b66e", "84dc72db", "a9a18e3e", "a62f55ba",
]
# A12 — Top-10 bowlers, FM-only
A12_TOP10_BOWLERS_FM = [
    "5b7ab5a9", "45a7e761", "24bb1c2f", "5935d694", "2cec2a92",
    "ef18b66e", "a97c8ec2", "244048f6", "dadbdb68", "249d60c9",
]


# ─── Helpers ──────────────────────────────────────────────────────────
async def matches_via_team_summary(scope, team):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await team_summary(team=team, filters=f, aux=aux)
    return env_value(resp.get("matches"))


async def matches_via_scope_summary(scope):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await scope_summary(filters=f, aux=aux)
    return resp.get("matches")


async def run_rate_team(scope, team):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await _compute_batting_summary(team, f, aux)
    return env_value(resp.get("run_rate"))


async def run_rate_league(scope):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await scope_batting_summary(filters=f, aux=aux)
    return resp.get("run_rate")


def expect(label, actual, expected, failures, *, fuzzy=False):
    ok = near(actual, expected) if fuzzy else actual == expected
    status = "PASS" if ok else f"FAIL (got {actual}, expected {expected})"
    print(f"  {label}: {status}")
    if not ok:
        failures.append(f"{label}: got {actual}, expected {expected}")


# ─── Top-10 SQL-direct (A9-A12) ───────────────────────────────────────
async def top10_batters_by_runs(scope_clauses, params):
    """Top-10 batter person_ids by total runs scored in scope.
    Tiebreak `person_id DESC` mirrors the anchor file's SQLite output
    on the pinned 2026-04-28 DB snapshot — without an explicit
    secondary sort SQLite is non-deterministic on ties."""
    where = " AND ".join(scope_clauses)
    sql = f"""
        SELECT d.batter_id AS person_id,
               SUM(d.runs_batter) AS runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0
          AND {where}
        GROUP BY d.batter_id
        ORDER BY runs DESC, d.batter_id DESC
        LIMIT 10
    """
    rows = await deps._db.q(sql, params)
    return [r["person_id"] for r in rows]


async def top10_bowlers_by_wickets(scope_clauses, params):
    """Top-10 bowler person_ids by wickets taken in scope (excludes
    run out / retired hurt / retired out / obstructing the field —
    bowler-attribution rules). Tiebreak `bowler_id DESC` mirrors the
    anchor file's pinned ordering."""
    where = " AND ".join(scope_clauses)
    sql = f"""
        SELECT d.bowler_id AS person_id, COUNT(*) AS wkts
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
          AND d.bowler_id IS NOT NULL
          AND i.super_over = 0
          AND {where}
        GROUP BY d.bowler_id
        ORDER BY wkts DESC, d.bowler_id DESC
        LIMIT 10
    """
    rows = await deps._db.q(sql, params)
    return [r["person_id"] for r in rows]


def men_intl_2425_clauses(fm: bool):
    clauses = [
        "m.gender = :gender",
        "m.team_type = :team_type",
        "m.season >= :season_from",
        "m.season <= :season_to",
    ]
    params = {"gender": "male", "team_type": "international",
              "season_from": "2024", "season_to": "2025"}
    if fm:
        clauses.append(full_member_clause(table_alias="m"))
    return clauses, params


# ─── Test runner ──────────────────────────────────────────────────────
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

    print("─── AXIS A: match counts (SQL-vs-API via summary endpoints) ───")
    expect("A1 men_intl 24-25 unbounded",
           await matches_via_scope_summary(INTL_24_25_M),
           GROUND_TRUTH["A1"], failures, fuzzy=True)
    expect("A2 men_intl 24-25 FM",
           await matches_via_scope_summary({**INTL_24_25_M, "team_class": "full_member"}),
           GROUND_TRUTH["A2"], failures, fuzzy=True)
    expect("A3 Aus unbounded",
           await matches_via_team_summary(INTL_24_25_M, "Australia"),
           GROUND_TRUTH["A3"], failures)
    expect("A4 Aus FM",
           await matches_via_team_summary({**INTL_24_25_M, "team_class": "full_member"}, "Australia"),
           GROUND_TRUTH["A4"], failures)
    expect("A5 Ind unbounded",
           await matches_via_team_summary(INTL_24_25_M, "India"),
           GROUND_TRUTH["A5"], failures)
    expect("A6 Ind FM",
           await matches_via_team_summary({**INTL_24_25_M, "team_class": "full_member"}, "India"),
           GROUND_TRUTH["A6"], failures)
    expect("A7 Scotland unbounded",
           await matches_via_team_summary(INTL_24_25_M, "Scotland"),
           GROUND_TRUTH["A7"], failures)
    expect("A8 Scotland FM (associate → 0)",
           await matches_via_team_summary({**INTL_24_25_M, "team_class": "full_member"}, "Scotland"),
           GROUND_TRUTH["A8"], failures)

    expect("A13 T20 WC (Men) unbounded",
           await matches_via_scope_summary({**INTL_24_25_M, "tournament": "T20 World Cup (Men)"}),
           GROUND_TRUTH["A13"], failures, fuzzy=True)
    expect("A14 T20 WC (Men) FM",
           await matches_via_scope_summary({**INTL_24_25_M, "tournament": "T20 World Cup (Men)",
                                             "team_class": "full_member"}),
           GROUND_TRUTH["A14"], failures, fuzzy=True)

    # Rivalries — measured via team_summary with filter_opponent set.
    expect("A15a Ind-Aus unbounded",
           await matches_via_team_summary({**INTL_24_25_M, "filter_opponent": "Australia"}, "India"),
           GROUND_TRUTH["A15a"], failures)
    expect("A15b Ind-Aus FM (both FM, no-op)",
           await matches_via_team_summary({**INTL_24_25_M, "filter_opponent": "Australia",
                                             "team_class": "full_member"}, "India"),
           GROUND_TRUTH["A15b"], failures)
    expect("A16a Ind-Scotland unbounded (no meeting in scope)",
           await matches_via_team_summary({**INTL_24_25_M, "filter_opponent": "Scotland"}, "India"),
           GROUND_TRUTH["A16a"], failures)
    expect("A16b Ind-Scotland FM (FM ≤ unbounded)",
           await matches_via_team_summary({**INTL_24_25_M, "filter_opponent": "Scotland",
                                             "team_class": "full_member"}, "India"),
           GROUND_TRUTH["A16b"], failures)

    expect("A17 Wankhede intl unbounded",
           await matches_via_scope_summary({**INTL_24_25_M, "filter_venue": "Wankhede Stadium"}),
           GROUND_TRUTH["A17"], failures, fuzzy=True)
    expect("A18 Wankhede intl FM",
           await matches_via_scope_summary({**INTL_24_25_M, "filter_venue": "Wankhede Stadium",
                                             "team_class": "full_member"}),
           GROUND_TRUTH["A18"], failures, fuzzy=True)

    print()
    print("─── AXIS C: chip baselines (run rates) ───")
    expect("C1 Aus RR unbounded",
           await run_rate_team(INTL_24_25_M, "Australia"),
           GROUND_TRUTH["C1"], failures, fuzzy=True)
    expect("C2 Aus RR FM",
           await run_rate_team({**INTL_24_25_M, "team_class": "full_member"}, "Australia"),
           GROUND_TRUTH["C2"], failures, fuzzy=True)
    expect("C3 League RR unbounded",
           await run_rate_league(INTL_24_25_M),
           GROUND_TRUTH["C3"], failures, fuzzy=True)
    expect("C4 League RR FM",
           await run_rate_league({**INTL_24_25_M, "team_class": "full_member"}),
           GROUND_TRUTH["C4"], failures, fuzzy=True)

    print()
    print("─── AXIS D: women's intl symmetry ───")
    expect("D1 women_intl 24-25 unbounded",
           await matches_via_scope_summary(INTL_24_25_W),
           GROUND_TRUTH["D1"], failures, fuzzy=True)
    expect("D2 women_intl 24-25 FM",
           await matches_via_scope_summary({**INTL_24_25_W, "team_class": "full_member"}),
           GROUND_TRUTH["D2"], failures, fuzzy=True)

    print()
    print("─── B-prime: club no-op (DEFENSIVE GATE PROOF) ───")
    bp1 = await matches_via_team_summary(IPL_2025, "Royal Challengers Bengaluru")
    bp2 = await matches_via_team_summary({**IPL_2025, "team_class": "full_member"}, "Royal Challengers Bengaluru")
    expect("Bp1 RCB IPL 2025 (control)", bp1, GROUND_TRUTH["Bp1"], failures)
    # CRITICAL: Bp2 must equal Bp1 — proves the defensive backend gate
    # makes team_class a no-op when team_type='club'. If Bp2 == 0, the
    # FM clause naively fired against a club URL.
    if bp2 == bp1:
        print(f"  Bp2 RCB IPL 2025 + team_class=fm (gate fires → noop): PASS (=={bp1})")
    else:
        print(f"  Bp2 RCB IPL 2025 + team_class=fm: FAIL (got {bp2}, must equal Bp1={bp1})")
        failures.append(f"Bp2 club gate: got {bp2}, must equal Bp1={bp1} (defensive gate failed)")
    expect("Bp3 SRH IPL 2025 (control)",
           await matches_via_team_summary(IPL_2025, "Sunrisers Hyderabad"),
           GROUND_TRUTH["Bp3"], failures)
    expect("Bp4 IPL 2025 per-team avg",
           await matches_via_scope_summary(IPL_2025),
           GROUND_TRUTH["Bp4"], failures, fuzzy=True)

    print()
    print("─── AXIS B: top-10 lists (SQL-direct) ───")
    cl_unb, p_unb = men_intl_2425_clauses(fm=False)
    cl_fm, p_fm = men_intl_2425_clauses(fm=True)

    a9 = await top10_batters_by_runs(cl_unb, p_unb)
    a10 = await top10_batters_by_runs(cl_fm, p_fm)
    a11 = await top10_bowlers_by_wickets(cl_unb, p_unb)
    a12 = await top10_bowlers_by_wickets(cl_fm, p_fm)

    expect("A9  top-10 batters unbounded", a9, A9_TOP10_BATTERS_UNBOUNDED, failures)
    expect("A10 top-10 batters FM (no associates)", a10, A10_TOP10_BATTERS_FM, failures)
    expect("A11 top-10 bowlers unbounded", a11, A11_TOP10_BOWLERS_UNBOUNDED, failures)
    expect("A12 top-10 bowlers FM", a12, A12_TOP10_BOWLERS_FM, failures)

    print()
    if failures:
        print(f"=== {len(failures)} FAILURE(S) ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
