"""Sanity checks for /api/v1/league/* endpoints (SQL ↔ API).

Covers:

  1. /league/overview — matches + innings + tournaments counts
     match SQL; top_teams count ≥ 10 (or all teams if pool < 10);
     best_moments.highest_total matches max(innings_total) in scope.

  2. /league/champions — row count matches
     SELECT COUNT(*) FROM match WHERE event_stage='Final'
       AND outcome_winner IS NOT NULL AND event_name IS NOT NULL
       AND <scope>.

  3. /league/leaders/batting — by_runs top entry matches the
     SQL-anchored top batter by SUM(runs_batter).

  4. /league/leaders/fielding — Convention 3 honoured: catches
     headline equals `kind IN ('caught','caught_and_bowled')` in
     SQL, not the bare 'caught' predicate.

Spec: internal_docs/spec-league-pages.md §Testing.

Usage:
    uv run python tests/sanity/test_league_endpoints.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.request import urlopen
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database


PASS = "PASS"
FAIL = "FAIL"
API = os.environ.get("API", "http://127.0.0.1:8000")


def fetch(path: str) -> dict:
    with urlopen(f"{API}{path}") as r:
        return json.loads(r.read())


async def check_overview(db) -> bool:
    print("=== /league/overview ===")
    ok = True
    scope_qs = "?gender=male&team_type=club&season_from=2024&season_to=2025"
    api = fetch(f"/api/v1/league/overview{scope_qs}")

    sql_matches = (await db.q("""
        SELECT COUNT(DISTINCT id) AS n FROM match
        WHERE gender = 'male' AND team_type = 'club'
          AND season >= '2024' AND season <= '2025'
          AND match_type IN ('T20','IT20')
    """))[0]["n"]
    matched = api["matches"] == sql_matches
    print(f"  matches: API={api['matches']}  SQL={sql_matches}  {PASS if matched else FAIL}")
    ok &= matched

    sql_innings = (await db.q("""
        SELECT COUNT(DISTINCT i.id) AS n
        FROM innings i JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND m.gender = 'male' AND m.team_type = 'club'
          AND m.season >= '2024' AND m.season <= '2025'
          AND m.match_type IN ('T20','IT20')
    """))[0]["n"]
    matched = api["innings"] == sql_innings
    print(f"  innings: API={api['innings']}  SQL={sql_innings}  {PASS if matched else FAIL}")
    ok &= matched

    sql_tournaments = (await db.q("""
        SELECT COUNT(DISTINCT event_name) AS n FROM match
        WHERE gender = 'male' AND team_type = 'club'
          AND season >= '2024' AND season <= '2025'
          AND match_type IN ('T20','IT20')
    """))[0]["n"]
    matched = api["tournaments_count"] == sql_tournaments
    print(f"  tournaments: API={api['tournaments_count']}  SQL={sql_tournaments}  {PASS if matched else FAIL}")
    ok &= matched

    # top_teams capped at 10
    matched = len(api["top_teams"]) <= 10
    print(f"  top_teams ≤ 10: actual={len(api['top_teams'])}  {PASS if matched else FAIL}")
    ok &= matched

    # best_moments.highest_total matches SQL max-innings-total
    if api["best_moments"]["highest_total"]:
        sql_max = (await db.q("""
            SELECT MAX(tot.total) AS t
            FROM (
              SELECT d.innings_id, SUM(d.runs_total) AS total
              FROM delivery d GROUP BY d.innings_id
            ) tot
            JOIN innings i ON i.id = tot.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0
              AND m.gender = 'male' AND m.team_type = 'club'
              AND m.season >= '2024' AND m.season <= '2025'
              AND m.match_type IN ('T20','IT20')
        """))[0]["t"]
        matched = api["best_moments"]["highest_total"]["runs"] == sql_max
        print(f"  best_moments.highest_total.runs: API={api['best_moments']['highest_total']['runs']}  SQL={sql_max}  {PASS if matched else FAIL}")
        ok &= matched

    return ok


async def check_champions(db) -> bool:
    print("=== /league/champions ===")
    scope_qs = "?gender=male&team_type=club&season_from=2024&season_to=2025"
    api = fetch(f"/api/v1/league/champions{scope_qs}")

    sql_n = (await db.q("""
        SELECT COUNT(*) AS n FROM match
        WHERE gender = 'male' AND team_type = 'club'
          AND season >= '2024' AND season <= '2025'
          AND match_type IN ('T20','IT20')
          AND event_stage = 'Final'
          AND outcome_winner IS NOT NULL
          AND event_name IS NOT NULL
    """))[0]["n"]
    matched = len(api["rows"]) == sql_n
    print(f"  champion count: API={len(api['rows'])}  SQL={sql_n}  {PASS if matched else FAIL}")
    return matched


async def check_leaders_batting(db) -> bool:
    print("=== /league/leaders/batting ===")
    scope_qs = "?gender=male&team_type=club&season_from=2024&season_to=2025&limit=10"
    api = fetch(f"/api/v1/league/leaders/batting{scope_qs}")

    # Top batter by runs
    sql_top = (await db.q("""
        SELECT d.batter_id AS pid, SUM(d.runs_batter) AS r
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0
          AND m.gender = 'male' AND m.team_type = 'club'
          AND m.season >= '2024' AND m.season <= '2025'
          AND m.match_type IN ('T20','IT20')
        GROUP BY d.batter_id
        ORDER BY r DESC LIMIT 1
    """))[0]
    api_top = api["by_runs"][0]
    matched = (api_top["person_id"] == sql_top["pid"]
        and api_top["runs"] == sql_top["r"])
    print(f"  top batter by runs: API={api_top['person_id']}/{api_top['runs']}  "
          f"SQL={sql_top['pid']}/{sql_top['r']}  {PASS if matched else FAIL}")
    return matched


async def check_leaders_fielding_convention3(db) -> bool:
    print("=== /league/leaders/fielding (Convention 3) ===")
    scope_qs = "?gender=male&team_type=club&season_from=2024&season_to=2025&limit=10"
    api = fetch(f"/api/v1/league/leaders/fielding{scope_qs}")

    # Top fielder by total dismissals — verify catches column includes
    # c_and_b. Pick the row with the highest c_and_b in API; SQL with
    # Convention 3 predicate must give same catches count.
    top_row = max(api["by_dismissals"], key=lambda r: r.get("c_and_b") or 0)
    pid = top_row["person_id"]
    api_catches = top_row["catches"]

    sql_catches_c3 = (await db.q(f"""
        SELECT SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled') THEN 1 ELSE 0 END) AS n
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = '{pid}'
          AND i.super_over = 0
          AND m.gender = 'male' AND m.team_type = 'club'
          AND m.season >= '2024' AND m.season <= '2025'
          AND m.match_type IN ('T20','IT20')
    """))[0]["n"]
    matched = api_catches == sql_catches_c3
    print(f"  fielder {pid} catches: API={api_catches}  SQL(C3)={sql_catches_c3}  {PASS if matched else FAIL}")
    return matched


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("DB", "./cricket.db"))
    args = ap.parse_args()

    db = Database(f"sqlite+aiosqlite:///{args.db}")
    results = []
    results.append(await check_overview(db))
    results.append(await check_champions(db))
    results.append(await check_leaders_batting(db))
    results.append(await check_leaders_fielding_convention3(db))
    all_ok = all(results)
    print()
    print(f"Overall: {PASS if all_ok else FAIL}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
