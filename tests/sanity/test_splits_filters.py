"""Splits aux-filter sanity — `?result=` and `?toss_outcome=` on team
endpoints.

Drives `/teams/{team}/summary` with each aux-filter value and asserts
the `matches` count agrees with a direct SQL count using the same
predicate. Also asserts the partition identities:

  matches(result=won)  + matches(result=lost)  + matches(result=tied)
    == matches(unfiltered)

  matches(toss=won) + matches(toss=lost) + matches(toss_winner IS NULL)
    == matches(unfiltered)

Closed-window scopes only (IPL 2024, Men's T20I 2024-2025) so the
expected counts don't drift across DB rebuilds.

Usage:
  uv run python tests/sanity/test_splits_filters.py
  uv run python tests/sanity/test_splits_filters.py --db tmp/cricket-prod-test.db

Spec: internal_docs/spec-splits-mosaic.md §1.1.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams
from api.routers.teams import team_summary


# ─── Closed windows ───────────────────────────────────────────────────

IPL_2024 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2024", season_to="2024")
INTL_2024_25 = dict(gender="male", team_type="international",
                    season_from="2024", season_to="2025")

SUBJECTS: list[tuple[str, dict, str]] = [
    ("ipl_24", IPL_2024, "Royal Challengers Bengaluru"),
    ("ipl_24", IPL_2024, "Kolkata Knight Riders"),
    ("intl_24_25", INTL_2024_25, "India"),
    ("intl_24_25", INTL_2024_25, "Australia"),
]


# ─── Helpers ──────────────────────────────────────────────────────────

def make_filters(**kw) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kw.get(k) for k in keys})


def make_aux(**kw) -> AuxParams:
    return AuxParams(
        scope_to_team=kw.get("scope_to_team"),
        chip_team_class=kw.get("chip_team_class"),
        chip_baseline_scope_json=kw.get("chip_baseline_scope_json"),
        inning=kw.get("inning"),
        result=kw.get("result"),
        toss_outcome=kw.get("toss_outcome"),
    )


def _sql_scope_clause(scope: dict, team: str) -> tuple[str, dict]:
    """Build a match-level WHERE clause matching FilterBarParams.build()
    for the closed-window scopes used here. Sufficient for COUNT(*)
    correctness; doesn't need every flag the real builder honours."""
    parts = ["(m.team1 = :team OR m.team2 = :team)"]
    params: dict = {"team": team}
    for k, v in scope.items():
        # season_from/to → range; everything else equality.
        if k == "season_from":
            parts.append("m.season >= :season_from")
            params["season_from"] = v
        elif k == "season_to":
            parts.append("m.season <= :season_to")
            params["season_to"] = v
        elif k == "tournament":
            parts.append("m.event_name = :tournament")
            params["tournament"] = v
        elif k in ("gender", "team_type"):
            parts.append(f"m.{k} = :{k}")
            params[k] = v
    return " AND ".join(parts), params


def sql_count(c: sqlite3.Connection, scope: dict, team: str,
              extra_clause: str = "", extra_params: dict | None = None) -> int:
    where, params = _sql_scope_clause(scope, team)
    if extra_clause:
        where = f"{where} AND {extra_clause}"
    if extra_params:
        params.update(extra_params)
    q = f"SELECT COUNT(*) AS n FROM match m WHERE {where}"
    return c.execute(q, params).fetchone()[0]


@dataclass
class Failure:
    scope: str
    team: str
    aux_label: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.scope} / {self.team} / {self.aux_label}] {self.msg}"


async def assert_aux_matches(c: sqlite3.Connection, scope_label: str,
                              scope: dict, team: str,
                              failures: list[Failure]) -> None:
    """For each aux variant, call team_summary and compare matches
    count to the SQL ground truth."""
    base_filt = make_filters(**scope)

    # ── result filter ────────────────────────────────────────────────
    cases_result = [
        ("won",  "m.outcome_winner = :team",                                   {}),
        ("lost", "m.outcome_winner IS NOT NULL AND m.outcome_winner != :team", {}),
        ("tied", "m.outcome_winner IS NULL",                                   {}),
    ]
    for value, sql_extra, sql_extra_params in cases_result:
        f = make_filters(**scope)
        aux = make_aux(result=value)
        resp = await team_summary(team, f, aux)
        actual = resp.get("matches", {}).get("value", 0)
        expected = sql_count(c, scope, team, sql_extra, sql_extra_params)
        if actual != expected:
            failures.append(Failure(
                scope_label, team, f"result={value}",
                f"API matches={actual} ≠ SQL count={expected}",
            ))

    # ── toss_outcome filter ──────────────────────────────────────────
    cases_toss = [
        ("won",  "m.toss_winner IS NOT NULL AND m.toss_winner = :team",  {}),
        ("lost", "m.toss_winner IS NOT NULL AND m.toss_winner != :team", {}),
    ]
    for value, sql_extra, sql_extra_params in cases_toss:
        f = make_filters(**scope)
        aux = make_aux(toss_outcome=value)
        resp = await team_summary(team, f, aux)
        actual = resp.get("matches", {}).get("value", 0)
        expected = sql_count(c, scope, team, sql_extra, sql_extra_params)
        if actual != expected:
            failures.append(Failure(
                scope_label, team, f"toss_outcome={value}",
                f"API matches={actual} ≠ SQL count={expected}",
            ))

    # ── partition identities ─────────────────────────────────────────
    f_un = make_filters(**scope)
    aux_un = make_aux()
    total_unfiltered = (await team_summary(team, f_un, aux_un)).get("matches", {}).get("value", 0)

    sum_results = 0
    for value, _, _ in cases_result:
        f = make_filters(**scope)
        aux = make_aux(result=value)
        sum_results += (await team_summary(team, f, aux)).get("matches", {}).get("value", 0)
    if sum_results != total_unfiltered:
        failures.append(Failure(
            scope_label, team, "partition_result",
            f"won+lost+tied={sum_results} ≠ unfiltered={total_unfiltered}",
        ))

    sum_toss = 0
    for value, _, _ in cases_toss:
        f = make_filters(**scope)
        aux = make_aux(toss_outcome=value)
        sum_toss += (await team_summary(team, f, aux)).get("matches", {}).get("value", 0)
    toss_null = sql_count(c, scope, team, "m.toss_winner IS NULL", {})
    if sum_toss + toss_null != total_unfiltered:
        failures.append(Failure(
            scope_label, team, "partition_toss",
            f"won+lost+toss_null = {sum_toss}+{toss_null} ≠ unfiltered={total_unfiltered}",
        ))


# ─── Main ─────────────────────────────────────────────────────────────

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

    c = sqlite3.connect(args.db)
    failures: list[Failure] = []

    for scope_label, scope, team in SUBJECTS:
        await assert_aux_matches(c, scope_label, scope, team, failures)
        print(f"  {scope_label} / {team}: checked")

    print()
    if failures:
        print(f"=== FAILURES ({len(failures)}) ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
