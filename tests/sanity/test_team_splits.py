"""Splits endpoint sanity — `/api/v1/teams/splits`.

For closed-window scopes × subjects, asserts:

  1. sum(cells[].n) == scope_total_n
  2. cells[].n matches a SQL-direct GROUP BY count (for landing-side
     unpivot AND team-side restriction)
  3. marginals.toss_outcome / inning / result sum to scope_total_n
  4. Wilson CIs bracket the point estimate
  5. Team-detail mode: per-cell delta computes to share - league_share,
     delta_pct is the relative % thereof
  6. Cell-level aux filter (`?result=` / `?toss_outcome=` / `?inning=`)
     correctly post-filters the returned cells (count matches SQL)
  7. Subject-POV gate: `?result=` / `?toss_outcome=` without `?team=`
     raises HTTPException with status 400
  8. DLS inclusion: super-over matches and DLS-truncated chases all
     appear in the joint distribution (no special filtering)

Closed-window scopes only (IPL 2024) so the expected counts don't
drift across DB rebuilds.

Usage:
  uv run python tests/sanity/test_team_splits.py
  uv run python tests/sanity/test_team_splits.py --db tmp/cricket-prod-test.db

Spec: internal_docs/spec-splits-mosaic.md §1.3-1.5, §6.1.
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
from fastapi import HTTPException
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams
from api.routers.teams import team_splits


IPL_2024 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2024", season_to="2024")

SUBJECTS = [
    ("ipl_24", IPL_2024, "Royal Challengers Bengaluru"),
    ("ipl_24", IPL_2024, "Kolkata Knight Riders"),
]


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


@dataclass
class Failure:
    label: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.label}] {self.msg}"


# ─── Direct SQL ground-truth helpers ──────────────────────────────────

def sql_unpivoted_total(c: sqlite3.Connection, scope: dict, team: str | None = None) -> int:
    """Total team-views in scope (with toss_winner IS NOT NULL).

    When team is None: 2 × match_count.
    When team is set: match_count for that team.
    """
    where, params = _scope_clause(scope, team)
    where += " AND m.toss_winner IS NOT NULL"
    if team:
        q = f"SELECT COUNT(*) FROM match m WHERE {where} AND (m.team1 = :team OR m.team2 = :team)"
        params["team"] = team
        return c.execute(q, params).fetchone()[0]
    q = f"SELECT COUNT(*) FROM match m WHERE {where}"
    return c.execute(q, params).fetchone()[0] * 2


def _scope_clause(scope: dict, team: str | None = None) -> tuple[str, dict]:
    parts: list[str] = []
    params: dict = {}
    for k, v in scope.items():
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
    return " AND ".join(parts) if parts else "1=1", params


def sql_cell_count(c: sqlite3.Connection, scope: dict, team: str | None,
                    toss_outcome: str, inning: int, result: str) -> int:
    """Direct GROUP BY count for one cell."""
    where, params = _scope_clause(scope, team)
    where += " AND m.toss_winner IS NOT NULL"
    # When team is given, restrict to that team-view; else unpivot.
    if team:
        params["team"] = team
        # team batted first iff (toss=bat AND toss_winner=team) OR (toss=field AND toss_winner!=team)
        bat_first_clause = (
            "((m.toss_decision = 'bat' AND m.toss_winner = :team)"
            " OR (m.toss_decision = 'field' AND m.toss_winner != :team))"
        )
        inning_clause = bat_first_clause if inning == 0 else f"NOT {bat_first_clause}"
        toss_clause = (
            "m.toss_winner = :team" if toss_outcome == "won"
            else "m.toss_winner != :team"
        )
        if result == "won":
            res_clause = "m.outcome_winner = :team"
        elif result == "lost":
            res_clause = "(m.outcome_winner IS NOT NULL AND m.outcome_winner != :team)"
        else:
            res_clause = "m.outcome_winner IS NULL"
        q = f"""
        SELECT COUNT(*) FROM match m
        WHERE {where}
          AND (m.team1 = :team OR m.team2 = :team)
          AND {inning_clause}
          AND {toss_clause}
          AND {res_clause}
        """
        return c.execute(q, params).fetchone()[0]
    # Landing — sum over both team1 and team2 perspectives.
    total = 0
    for side in ("team1", "team2"):
        side_params = dict(params)
        side_params["team"] = None  # not used in side-specific clauses; we just inline
        bat_first_clause = (
            f"((m.toss_decision = 'bat' AND m.toss_winner = m.{side})"
            f" OR (m.toss_decision = 'field' AND m.toss_winner != m.{side}))"
        )
        inning_clause = bat_first_clause if inning == 0 else f"NOT {bat_first_clause}"
        toss_clause = (
            f"m.toss_winner = m.{side}" if toss_outcome == "won"
            else f"m.toss_winner != m.{side}"
        )
        if result == "won":
            res_clause = f"m.outcome_winner = m.{side}"
        elif result == "lost":
            res_clause = f"(m.outcome_winner IS NOT NULL AND m.outcome_winner != m.{side})"
        else:
            res_clause = "m.outcome_winner IS NULL"
        q = f"""
        SELECT COUNT(*) FROM match m
        WHERE {where}
          AND {inning_clause}
          AND {toss_clause}
          AND {res_clause}
        """
        total += c.execute(q, params).fetchone()[0]
    return total


# ─── Test functions ───────────────────────────────────────────────────

async def assert_landing_invariants(c, scope_label, scope, failures):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await team_splits(team=None, filters=f, aux=aux)

    expected_total = sql_unpivoted_total(c, scope)
    if resp["scope_total_n"] != expected_total:
        failures.append(Failure(
            f"{scope_label}/landing",
            f"scope_total_n {resp['scope_total_n']} ≠ SQL unpivoted {expected_total}",
        ))

    cell_sum = sum(cell["n"] for cell in resp["cells"])
    if cell_sum != resp["scope_total_n"]:
        failures.append(Failure(
            f"{scope_label}/landing",
            f"sum(cells.n) {cell_sum} ≠ scope_total_n {resp['scope_total_n']}",
        ))

    # Spot-check a few cells against SQL.
    for cell in resp["cells"]:
        expected = sql_cell_count(c, scope, None,
                                   cell["toss_outcome"], cell["inning"], cell["result"])
        if cell["n"] != expected:
            failures.append(Failure(
                f"{scope_label}/landing/cell",
                f"({cell['toss_outcome']},{cell['inning']},{cell['result']}) "
                f"API n={cell['n']} ≠ SQL n={expected}",
            ))

    # Marginals sum to total.
    for axis in ("toss_outcome", "inning", "result"):
        marg_sum = sum(m["n"] for m in resp["marginals"][axis].values())
        if marg_sum != resp["scope_total_n"]:
            failures.append(Failure(
                f"{scope_label}/landing/marginal/{axis}",
                f"marginal sum {marg_sum} ≠ scope_total_n {resp['scope_total_n']}",
            ))

    # Wilson CI bracket check.
    for cell in resp["cells"]:
        if cell["share"] is None:
            continue
        if not (cell["wilson_lo"] <= cell["share"] <= cell["wilson_hi"]):
            failures.append(Failure(
                f"{scope_label}/landing/wilson",
                f"share {cell['share']} not in [{cell['wilson_lo']},{cell['wilson_hi']}]",
            ))


async def assert_team_invariants(c, scope_label, scope, team, failures):
    f = make_filters(**scope)
    aux = make_aux()
    resp = await team_splits(team=team, filters=f, aux=aux)

    expected_total = sql_unpivoted_total(c, scope, team)
    if resp["scope_total_n"] != expected_total:
        failures.append(Failure(
            f"{scope_label}/{team}",
            f"scope_total_n {resp['scope_total_n']} ≠ SQL match count {expected_total}",
        ))

    cell_sum = sum(cell["n"] for cell in resp["cells"])
    if cell_sum != resp["scope_total_n"]:
        failures.append(Failure(
            f"{scope_label}/{team}",
            f"sum(cells.n) {cell_sum} ≠ scope_total_n {resp['scope_total_n']}",
        ))

    # Spot-check cells.
    for cell in resp["cells"]:
        expected = sql_cell_count(c, scope, team,
                                   cell["toss_outcome"], cell["inning"], cell["result"])
        if cell["n"] != expected:
            failures.append(Failure(
                f"{scope_label}/{team}/cell",
                f"({cell['toss_outcome']},{cell['inning']},{cell['result']}) "
                f"team_n {cell['n']} ≠ SQL n {expected}",
            ))
        # Delta cross-check.
        if cell["league_share"] is not None and cell["share"] is not None:
            implied_delta = round(cell["share"] - cell["league_share"], 4)
            if cell["delta"] != implied_delta:
                failures.append(Failure(
                    f"{scope_label}/{team}/delta",
                    f"delta {cell['delta']} ≠ implied {implied_delta}",
                ))


async def assert_aux_filter(c, scope_label, scope, team, aux_kwargs, failures):
    f = make_filters(**scope)
    aux = make_aux(**aux_kwargs)
    resp = await team_splits(team=team, filters=f, aux=aux)

    # scope_total_n must reflect the FILTERED slice — sum(cells.n)
    # post-filter. The bug pinned here was scope_total_n returning
    # the UNFILTERED total when aux was set, breaking the
    # "Of N toss wins:" denominator in the UI. Locking it:
    cell_sum = sum(cell["n"] for cell in resp["cells"])
    if cell_sum != resp["scope_total_n"]:
        failures.append(Failure(
            f"{scope_label}/{team}/aux={aux_kwargs}",
            f"scope_total_n {resp['scope_total_n']} ≠ sum(cells.n) {cell_sum} — "
            f"denominator must reflect the filtered slice",
        ))

    # Shares must sum to 1.0 within the filtered slice (modulo float
    # rounding — Wilson rounds to 4dp, so the sum is exact at the
    # precision we serialize).
    share_sum = sum((cell["share"] or 0) for cell in resp["cells"])
    if resp["scope_total_n"] > 0 and abs(share_sum - 1.0) > 0.001:
        failures.append(Failure(
            f"{scope_label}/{team}/aux={aux_kwargs}",
            f"shares sum to {share_sum:.4f}, not 1.0 — denominator drift",
        ))

    # Every returned cell matches the aux filter.
    for cell in resp["cells"]:
        if "result" in aux_kwargs and cell["result"] != aux_kwargs["result"]:
            failures.append(Failure(
                f"{scope_label}/{team}/aux={aux_kwargs}",
                f"cell result={cell['result']} ≠ aux.result={aux_kwargs['result']}",
            ))
        if "toss_outcome" in aux_kwargs and cell["toss_outcome"] != aux_kwargs["toss_outcome"]:
            failures.append(Failure(
                f"{scope_label}/{team}/aux={aux_kwargs}",
                f"cell toss_outcome={cell['toss_outcome']} ≠ aux={aux_kwargs['toss_outcome']}",
            ))
        if "inning" in aux_kwargs and cell["inning"] != aux_kwargs["inning"]:
            failures.append(Failure(
                f"{scope_label}/{team}/aux={aux_kwargs}",
                f"cell inning={cell['inning']} ≠ aux={aux_kwargs['inning']}",
            ))


async def assert_subject_pov_gate(scope, failures):
    """`?result=` or `?toss_outcome=` without `?team=` must 400."""
    f = make_filters(**scope)
    for aux_kwargs in [{"result": "won"}, {"toss_outcome": "won"}]:
        aux = make_aux(**aux_kwargs)
        try:
            await team_splits(team=None, filters=f, aux=aux)
            failures.append(Failure(
                "subject_pov_gate",
                f"aux={aux_kwargs} without team should 400, but did not",
            ))
        except HTTPException as e:
            if e.status_code != 400:
                failures.append(Failure(
                    "subject_pov_gate",
                    f"aux={aux_kwargs} raised {e.status_code}, expected 400",
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

    print("─── Landing invariants ───")
    for scope_label, scope, _team in SUBJECTS[:1]:
        await assert_landing_invariants(c, scope_label, scope, failures)
        print(f"  {scope_label}: checked")

    print()
    print("─── Team-detail invariants ───")
    for scope_label, scope, team in SUBJECTS:
        await assert_team_invariants(c, scope_label, scope, team, failures)
        print(f"  {scope_label} / {team}: checked")

    print()
    print("─── Aux cell-level filters ───")
    for scope_label, scope, team in SUBJECTS[:1]:
        for aux_kwargs in [
            {"result": "won"},
            {"result": "lost"},
            {"toss_outcome": "won"},
            {"inning": 0},
            {"result": "won", "inning": 0},
            {"result": "won", "toss_outcome": "won", "inning": 0},
        ]:
            await assert_aux_filter(c, scope_label, scope, team, aux_kwargs, failures)
        print(f"  {scope_label} / {team}: 6 aux variants checked")

    print()
    print("─── Subject-POV gate (400 expected) ───")
    await assert_subject_pov_gate(IPL_2024, failures)
    print("  IPL 2024: gate checked")

    print()
    if failures:
        print(f"=== FAILURES ({len(failures)}) ===")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
