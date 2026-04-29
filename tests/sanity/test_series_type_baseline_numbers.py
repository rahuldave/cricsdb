"""DB-grounded numeric assertions for the series_type FilterBar
promotion. Pinned to closed historical windows so expected values
stay stable across DB rebuilds.

The promotion is inert by design — the backend SQL output for
?series_type=bilateral_only is byte-identical pre/post (same
series_type_clause fires; only the param-binding source changed
from AuxParams to FilterBarParams). This test pins the BACKEND
behaviour: SQL ground truth (independent) MUST match what the API
returns when filters.series_type is set.

If a future refactor accidentally drops series_type from
FilterBarParams or rewires it to a different clause, every anchor
here breaks loudly.

Anchors (S1-S10 from internal_docs/series-type-anchor-numbers.md):
  S1  men_intl 2024-25 plain                       870
  S2  + bilateral_only                             802
  S3  + tournament_only / icc                       68
  S4  + tournament=T20 WC + bilateral_only           0
  S5  + tournament=T20 WC + icc                     44
  S6  + filter_team=India + bilateral_only          27
  S7  + filter_team=India + filter_opponent=Aus
       + bilateral_only                              0
  S8  women_intl 2024-25 + bilateral_only          535
  S9  club 2024-25 + bilateral_only                  0
  S10 + Australia + bilateral_only                  16

Each anchor asserted via two paths:
  1. Independent SQL (the DB-direct count, NOT through api/ logic).
  2. The /matches endpoint (or /teams/{team}/summary for S10) with
     filters.series_type set, proving the FilterBar field reaches
     the backend clause.

Usage:
  uv run python tests/sanity/test_series_type_baseline_numbers.py
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
from api.routers.teams import team_summary
from api.routers.matches import list_matches
from api.tournament_canonical import series_type_clause


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    # Pass explicit None for every Query-defaulted field; AuxParams()
    # with no args leaves Query() instances in self.x, which then leak
    # into SQL bind params downstream.
    return AuxParams(scope_to_team=None, chip_team_class=None)


def env_value(env):
    return env.get("value") if isinstance(env, dict) else env


# ─── Ground truth (pinned 2026-04-28) ─────────────────────────────────
GROUND_TRUTH = {
    "S1":  870,
    "S2":  802,
    "S3":   68,
    "S4":    0,
    "S5":   44,
    "S6":   27,
    "S7":    0,
    "S8":  535,
    "S9":    0,
    "S10":  16,
}

# Closed-window scopes
INTL_24_25_M = dict(gender="male", team_type="international",
                    season_from="2024", season_to="2025")
INTL_24_25_W = dict(gender="female", team_type="international",
                    season_from="2024", season_to="2025")
CLUB_24_25_M = dict(gender="male", team_type="club",
                    season_from="2024", season_to="2025")
T20_WC_24 = dict(tournament="T20 World Cup (Men)",
                 season_from="2024", season_to="2024")


# ─── Independent SQL (no api/filters or routers) ──────────────────────
async def sql_count(where_extras: list[str]) -> int:
    where = " AND ".join(where_extras) if where_extras else "1=1"
    sql = f"SELECT COUNT(*) AS c FROM match m WHERE {where}"
    rows = await deps._db.q(sql, {})
    return rows[0]["c"]


def men_intl_24_25_clauses() -> list[str]:
    return [
        "m.gender = 'male'",
        "m.team_type = 'international'",
        "m.season >= '2024'",
        "m.season <= '2025'",
    ]


def women_intl_24_25_clauses() -> list[str]:
    return [
        "m.gender = 'female'",
        "m.team_type = 'international'",
        "m.season >= '2024'",
        "m.season <= '2025'",
    ]


def club_24_25_clauses() -> list[str]:
    return [
        "m.gender = 'male'",
        "m.team_type = 'club'",
        "m.season >= '2024'",
        "m.season <= '2025'",
    ]


# ─── API-path counts ──────────────────────────────────────────────────
async def matches_via_list_matches(scope: dict, **extra) -> int:
    f = make_filters(**{**scope, **extra})
    # Pass every Query-default explicitly — calling the endpoint
    # directly bypasses FastAPI dependency resolution.
    resp = await list_matches(
        filters=f, aux=make_aux(),
        team=None, player_id=None, limit=1, offset=0,
    )
    return resp["total"]


async def matches_via_team_summary(scope: dict, team: str, **extra) -> int:
    f = make_filters(**{**scope, **extra})
    resp = await team_summary(team=team, filters=f, aux=make_aux())
    return env_value(resp["matches"])


# ─── Test runner ──────────────────────────────────────────────────────
def expect(label, actual_sql, actual_api, expected, failures):
    sql_ok = actual_sql == expected
    api_ok = actual_api == expected
    if sql_ok and api_ok:
        print(f"  {label}: PASS (sql={actual_sql} api={actual_api})")
    else:
        msg = f"{label}: expected {expected}; sql={actual_sql} api={actual_api}"
        print(f"  {label}: FAIL — {msg}")
        failures.append(msg)


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

    failures: list[str] = []

    # Build the bilateral / tournament-only clause strings for SQL
    # anchors (uses the canonical helper, NOT the FilterBar pipeline).
    bilat_clause = series_type_clause("bilateral_only")
    icc_clause = series_type_clause("tournament_only")

    # ─── S1: plain men_intl 24-25 ───
    sql = await sql_count(men_intl_24_25_clauses())
    api = await matches_via_list_matches(INTL_24_25_M)
    expect("S1 men_intl 24-25 plain", sql, api, GROUND_TRUTH["S1"], failures)

    # ─── S2: + bilateral_only ───
    sql = await sql_count(men_intl_24_25_clauses() + [bilat_clause])
    api = await matches_via_list_matches(INTL_24_25_M, series_type="bilateral_only")
    expect("S2 + bilateral_only", sql, api, GROUND_TRUTH["S2"], failures)

    # ─── S3: + tournament_only ───
    sql = await sql_count(men_intl_24_25_clauses() + [icc_clause])
    api = await matches_via_list_matches(INTL_24_25_M, series_type="tournament_only")
    expect("S3 + tournament_only", sql, api, GROUND_TRUTH["S3"], failures)

    # ─── S4: + T20 WC + bilateral_only (= 0, ICC ∩ bilateral) ───
    sql = await sql_count(men_intl_24_25_clauses() + [bilat_clause]
                          + ["m.event_name = 'ICC Men''s T20 World Cup'"])
    api = await matches_via_list_matches(
        INTL_24_25_M,
        tournament="T20 World Cup (Men)",
        season_from="2024", season_to="2024",
        series_type="bilateral_only",
    )
    expect("S4 T20 WC + bilateral_only", sql, api, GROUND_TRUTH["S4"], failures)

    # ─── S5: + T20 WC + icc ───
    sql = await sql_count(men_intl_24_25_clauses() + [icc_clause]
                          + ["m.event_name = 'ICC Men''s T20 World Cup'"])
    api = await matches_via_list_matches(
        INTL_24_25_M,
        tournament="T20 World Cup (Men)",
        season_from="2024", season_to="2024",
        series_type="tournament_only",
    )
    expect("S5 T20 WC + icc", sql, api, GROUND_TRUTH["S5"], failures)

    # ─── S6: + India + bilateral_only ───
    sql = await sql_count(men_intl_24_25_clauses() + [bilat_clause]
                          + ["('India' IN (m.team1, m.team2))"])
    api = await matches_via_list_matches(
        INTL_24_25_M, filter_team="India", series_type="bilateral_only"
    )
    expect("S6 India + bilateral_only", sql, api, GROUND_TRUTH["S6"], failures)

    # ─── S7: + India + Aus + bilateral_only ───
    sql = await sql_count(
        men_intl_24_25_clauses() + [bilat_clause]
        + ["((m.team1='India' AND m.team2='Australia') OR (m.team1='Australia' AND m.team2='India'))"]
    )
    api = await matches_via_list_matches(
        INTL_24_25_M, filter_team="India", filter_opponent="Australia",
        series_type="bilateral_only",
    )
    expect("S7 India vs Aus + bilateral_only", sql, api, GROUND_TRUTH["S7"], failures)

    # ─── S8: women_intl 24-25 + bilateral_only ───
    sql = await sql_count(women_intl_24_25_clauses() + [bilat_clause])
    api = await matches_via_list_matches(INTL_24_25_W, series_type="bilateral_only")
    expect("S8 women_intl + bilateral_only", sql, api, GROUND_TRUTH["S8"], failures)

    # ─── S9: club + bilateral_only (= 0, bilateral requires intl) ───
    sql = await sql_count(club_24_25_clauses() + [bilat_clause])
    api = await matches_via_list_matches(CLUB_24_25_M, series_type="bilateral_only")
    expect("S9 club + bilateral_only", sql, api, GROUND_TRUTH["S9"], failures)

    # ─── S10: + Australia + bilateral_only — via team_summary ───
    sql = await sql_count(
        men_intl_24_25_clauses() + [bilat_clause]
        + ["('Australia' IN (m.team1, m.team2))"]
    )
    api = await matches_via_team_summary(
        INTL_24_25_M, team="Australia", series_type="bilateral_only"
    )
    expect("S10 Aus + bilateral_only", sql, api, GROUND_TRUTH["S10"], failures)

    print()
    if failures:
        print(f"FAIL — {len(failures)} anchor(s) failed:")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    print(f"ALL PASS — {len(GROUND_TRUTH)} anchors green")


if __name__ == "__main__":
    asyncio.run(main())
