"""SQL-anchored sanity for the player-baseline-aux-fallback arc's new /
narrowed surfaces (2026-05-29 api.md + regression-coverage sweep).

The regression harness (tests/regression/*) hashes API responses for
no-drift; it does NOT prove the numbers are CORRECT. This sanity test is
the SQL↔API layer that proves the new fields and the narrowing are right,
so the regression baselines they lock are known-good:

  §1 /players/{id}/result-counts — every count (matches / wins / losses /
     ties / no_results / toss_won / toss_lost) matches an INDEPENDENT
     matchplayer⋈match SQL, both all-time AND under a scope narrowing
     (gender+team_type+season). Proves the ResultFilter/TossFilter pill
     counts and that they narrow.

  §2 result-counts narrows under inning (Option-B match union): inning=0
     and inning=1 each return strictly fewer matches than the scope total,
     and partition it (inn0 + inn1 == total — every match the player was in
     is either batted-first or batted-second for their team).

  §3 matches_fielded (denominator B) on /fielders/{id}/summary == the SQL
     count of matches where the fielder was in the XI AND the opponent
     batted ≥1 regular innings, and matches_fielded <= squad matches.

In-process (no running server needed): constructs FilterBarParams/AuxParams
and calls the route handlers directly, mirroring
tests/sanity/test_catches_convention3.py.

Run: uv run python tests/sanity/test_result_counts_and_narrowing.py
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
from api.routers.reference import player_result_counts
from api.routers.fielding import fielding_summary

KOHLI = "ba607b88"
DHONI = "4a8a2e3b"

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label} — {detail}")


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


async def sql_result_counts(db, pid: str, where: str = "", params: dict | None = None) -> dict:
    """Independent re-derivation of result-counts over matchplayer⋈match."""
    p = {"pid": pid, **(params or {})}
    rows = await db.q(
        f"""
        SELECT
          COUNT(DISTINCT mp.match_id) AS matches,
          COUNT(DISTINCT CASE WHEN m.outcome_winner = mp.team THEN mp.match_id END) AS wins,
          COUNT(DISTINCT CASE WHEN m.outcome_winner IS NOT NULL AND m.outcome_winner != mp.team THEN mp.match_id END) AS losses,
          COUNT(DISTINCT CASE WHEN m.outcome_winner IS NULL THEN mp.match_id END) AS ties_nr,
          COUNT(DISTINCT CASE WHEN m.toss_winner = mp.team THEN mp.match_id END) AS toss_won,
          COUNT(DISTINCT CASE WHEN m.toss_winner IS NOT NULL AND m.toss_winner != mp.team THEN mp.match_id END) AS toss_lost
        FROM matchplayer mp JOIN match m ON m.id = mp.match_id
        WHERE mp.person_id = :pid {where}
        """,
        p,
    )
    return rows[0]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cricket.db"))
    args = ap.parse_args()
    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")
    db = deps._db

    # ── §1 result-counts == independent SQL (all-time + scoped) ──
    print("§1 result-counts SQL anchor")
    api = await player_result_counts(KOHLI, make_filters(), AuxParams())
    sql = await sql_result_counts(db, KOHLI)
    check("all-time matches", api["matches"] == sql["matches"], f'{api["matches"]} vs {sql["matches"]}')
    check("all-time wins", api["wins"] == sql["wins"], f'{api["wins"]} vs {sql["wins"]}')
    check("all-time losses", api["losses"] == sql["losses"], f'{api["losses"]} vs {sql["losses"]}')
    check("all-time ties+no_results", api["ties"] + api["no_results"] == sql["ties_nr"],
          f'{api["ties"]}+{api["no_results"]} vs {sql["ties_nr"]}')
    check("all-time toss_won", api["toss_won"] == sql["toss_won"], f'{api["toss_won"]} vs {sql["toss_won"]}')
    check("all-time toss_lost", api["toss_lost"] == sql["toss_lost"], f'{api["toss_lost"]} vs {sql["toss_lost"]}')

    # scoped: men's club, season 2016 (closed historical window)
    f_scoped = make_filters(gender="male", team_type="club", season_from="2016", season_to="2016")
    api_s = await player_result_counts(KOHLI, f_scoped, AuxParams())
    sql_s = await sql_result_counts(
        db, KOHLI,
        "AND m.gender = :g AND m.team_type = :tt AND m.season = :s",
        {"g": "male", "tt": "club", "s": "2016"})
    check("scoped (2016) narrows below all-time", api_s["matches"] < api["matches"],
          f'{api_s["matches"]} !< {api["matches"]}')
    check("scoped matches == SQL", api_s["matches"] == sql_s["matches"], f'{api_s["matches"]} vs {sql_s["matches"]}')
    check("scoped wins == SQL", api_s["wins"] == sql_s["wins"], f'{api_s["wins"]} vs {sql_s["wins"]}')
    check("scoped toss_won == SQL", api_s["toss_won"] == sql_s["toss_won"], f'{api_s["toss_won"]} vs {sql_s["toss_won"]}')

    # ── §2 inning narrowing (Option-B match union) partitions the scope ──
    print("§2 result-counts narrows + partitions under inning")
    f_ipl = make_filters(gender="male", team_type="club", tournament="Indian Premier League")
    base = await player_result_counts(KOHLI, f_ipl, AuxParams())
    inn0 = await player_result_counts(KOHLI, f_ipl, AuxParams(inning=0))
    inn1 = await player_result_counts(KOHLI, f_ipl, AuxParams(inning=1))
    check("inning=0 narrows below scope total", 0 < inn0["matches"] < base["matches"],
          f'{inn0["matches"]} vs {base["matches"]}')
    check("inning=1 narrows below scope total", 0 < inn1["matches"] < base["matches"],
          f'{inn1["matches"]} vs {base["matches"]}')
    check("inning 0+1 partition the scope total",
          inn0["matches"] + inn1["matches"] == base["matches"],
          f'{inn0["matches"]}+{inn1["matches"]} vs {base["matches"]}')

    # ── §3 matches_fielded (denominator B) == SQL (XI ∧ opponent batted) ──
    print("§3 matches_fielded SQL anchor")
    fld = await fielding_summary(DHONI, make_filters(gender="male", team_type="club",
                                                     tournament="Indian Premier League"), AuxParams())
    def _v(x):
        return x["value"] if isinstance(x, dict) else x
    mf_api = _v(fld["matches_fielded"])
    sq_api = _v(fld["matches"])
    rows = await db.q(
        """
        SELECT COUNT(DISTINCT mp.match_id) AS mf
        FROM matchplayer mp JOIN match m ON m.id = mp.match_id
        WHERE mp.person_id = :pid
          AND m.gender = 'male' AND m.team_type = 'club'
          AND m.event_name = 'Indian Premier League'
          AND EXISTS (SELECT 1 FROM innings i
                      WHERE i.match_id = mp.match_id
                        AND i.super_over = 0 AND i.team != mp.team)
        """,
        {"pid": DHONI},
    )
    mf_sql = rows[0]["mf"]
    check("matches_fielded == SQL (XI ∧ opponent batted)", mf_api == mf_sql, f"{mf_api} vs {mf_sql}")
    check("matches_fielded <= squad matches", mf_api <= sq_api, f"{mf_api} > {sq_api}")

    print(f"\n=== {PASS} pass / {FAIL} fail ===")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
