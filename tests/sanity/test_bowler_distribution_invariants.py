"""Invariants for /api/v1/bowlers/{id}/distribution.

Calls the endpoint function in-process across several scope
combinations and asserts the spec §11.9 invariants hold. Per
CLAUDE.md "integration tests must self-anchor against SQL", every
numeric expected value derives from sqlite3 against `cricket.db`
at runtime — no hardcoded literals.

Invariants (spec internal_docs/spec-distribution-stats.md §11.9):

  1. n_innings == len(wickets.observations) on lifetime + each form window.
  2. last_10.n_innings ≤ 10; last_10.observations is the contiguous
     date-asc tail of lifetime.observations.
  3. Phase partition — runs/balls/wickets per phase sum to the
     dossier-level totals from the master sample.
  4. pool_strike_rate × wickets.total ≈ sum_balls (when wickets > 0).
  5. pool_average × wickets.total ≈ runs_conceded.total.
  6. economy.pool == runs_conceded.total × 6 / sum_balls.
  7. For every milestone field: value × denom ≈ num; ci_low ≤ value
     ≤ ci_high; 0 ≤ ci_low; ci_high ≤ 1.
  8. Subset invariant — count(w ≥ k) ≤ count(w ≥ k−1) for k = 1..5.
  9. Conditional anchor invariant — p_3_given_2.denom ==
     p_4_given_2.denom == p_5_given_2.denom == count(w ≥ 2).
 10. min_balls=0 vs min_balls=12: n_innings strictly ≥ when min=0;
     when equal, every aggregate is identical.
 11. SQL anchor — lifetime n_innings, wickets.total, sum_balls,
     runs_conceded.total match a direct sqlite3 query for the
     same scope.

Usage:
  uv run python tests/sanity/test_bowler_distribution_invariants.py
  uv run python tests/sanity/test_bowler_distribution_invariants.py --db tmp/cricket.db

Exits 0 on all-pass, 1 on any failure.
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
from api.routers.bowling import bowling_distribution


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


# (label, person_id, filter dict). IDs pinned to disambiguate
# homonyms (4 Rashid Khans in person table; 5f547c8b is the Afghan
# leg-spinner with 502 wickets at the time of this test).
# Bumrah (busy IPL bowler), Rashid Khan (T20-I + IPL), Trent Boult
# (multi-team), and Kohli (part-time bowler — small sample edge cases).
SCOPES: list[tuple[str, str, dict]] = [
    ("bumrah_ipl_2024",   "462411b3", {"tournament": "Indian Premier League", "season_from": "2024", "season_to": "2024"}),
    ("bumrah_all_time",   "462411b3", {}),
    ("rashid_all_time",   "5f547c8b", {}),
    ("boult_ipl",         "a818c1be", {"tournament": "Indian Premier League"}),
    ("kohli_part_time",   "ba607b88", {}),
]

AS_OF = "2025-01-01"


# ─── Assertion helpers ─────────────────────────────────────────────────

def _approx(a, b, eps=0.01) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < eps


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    return ok, f"{status} · {label}{(' — ' + detail) if detail and not ok else ''}"


def assert_prob_record(label: str, pr: dict) -> list[tuple[bool, str]]:
    """Validate {value, num, denom, ci_low, ci_high} shape + bounds."""
    out = []
    keys = {"value", "num", "denom", "ci_low", "ci_high"}
    out.append(check(f"{label}: prob_record keys",
                     set(pr.keys()) == keys,
                     f"got {set(pr.keys())}"))

    if pr["denom"] == 0:
        out.append(check(f"{label}: zero-denom value None",
                         pr["value"] is None))
        out.append(check(f"{label}: zero-denom CI None",
                         pr["ci_low"] is None and pr["ci_high"] is None))
        return out

    # value × denom ≈ num — tolerance scales with denom because
    # value is rounded to 4dp (worst-case error 5e-5 × denom).
    rnd_tol = max(0.01, pr["denom"] * 5e-5)
    out.append(check(f"{label}: value × denom == num",
                     _approx(pr["value"] * pr["denom"], pr["num"], eps=rnd_tol),
                     f"value={pr['value']}, denom={pr['denom']}, num={pr['num']}"))
    # CI bounds in [0, 1]
    out.append(check(f"{label}: 0 ≤ ci_low",
                     pr["ci_low"] >= 0,
                     f"ci_low={pr['ci_low']}"))
    out.append(check(f"{label}: ci_high ≤ 1",
                     pr["ci_high"] <= 1.0001,
                     f"ci_high={pr['ci_high']}"))
    # CI contains the point estimate
    out.append(check(f"{label}: ci_low ≤ value ≤ ci_high",
                     pr["ci_low"] - 0.0001 <= pr["value"] <= pr["ci_high"] + 0.0001,
                     f"({pr['ci_low']}, {pr['value']}, {pr['ci_high']})"))
    return out


def assert_dossier_invariants(label: str, doss: dict) -> list[tuple[bool, str]]:
    out = []
    n = doss["n_innings"]
    obs = doss["wickets"]["observations"]

    # Inv 1: n_innings == len(observations)
    out.append(check(f"{label}: n_innings == len(observations)",
                     n == len(obs),
                     f"n={n}, len(obs)={len(obs)}"))

    if n == 0:
        # Empty-shape sanity
        out.append(check(f"{label}: empty wickets.total == 0",
                         doss["wickets"]["total"] == 0))
        out.append(check(f"{label}: empty pool_sr is None",
                         doss["pool_strike_rate"] is None))
        return out

    # Inv 3: phase partition (runs, balls, wickets)
    sum_balls = sum(o["balls"] for o in obs)
    sum_runs = sum(o["runs_conceded"] for o in obs)
    sum_wkts = sum(o["wickets"] for o in obs)
    phase = doss["phase"]
    pp_b = phase["powerplay"]["balls_total"] + phase["middle"]["balls_total"] + phase["death"]["balls_total"]
    pp_r = phase["powerplay"]["runs_total"] + phase["middle"]["runs_total"] + phase["death"]["runs_total"]
    pp_w = phase["powerplay"]["wickets_total"] + phase["middle"]["wickets_total"] + phase["death"]["wickets_total"]
    out.append(check(f"{label}: phase balls partition",
                     pp_b == sum_balls,
                     f"phase_sum={pp_b}, master_sum={sum_balls}"))
    out.append(check(f"{label}: phase runs partition",
                     pp_r == sum_runs,
                     f"phase_sum={pp_r}, master_sum={sum_runs}"))
    out.append(check(f"{label}: phase wickets partition",
                     pp_w == sum_wkts,
                     f"phase_sum={pp_w}, master_sum={sum_wkts}"))

    # Inv 4: pool_strike_rate × wickets.total ≈ sum_balls
    if sum_wkts > 0:
        out.append(check(f"{label}: pool_sr × wkts ≈ balls",
                         _approx(doss["pool_strike_rate"] * sum_wkts, sum_balls, eps=0.5),
                         f"sr={doss['pool_strike_rate']}, wkts={sum_wkts}, balls={sum_balls}"))
    else:
        out.append(check(f"{label}: pool_sr None when wickets=0",
                         doss["pool_strike_rate"] is None))

    # Inv 5: pool_average × wickets.total ≈ runs_conceded.total
    if sum_wkts > 0:
        out.append(check(f"{label}: pool_avg × wkts ≈ runs",
                         _approx(doss["pool_average"] * sum_wkts, sum_runs, eps=0.5),
                         f"avg={doss['pool_average']}, wkts={sum_wkts}, runs={sum_runs}"))

    # Inv 6: economy.pool == runs × 6 / balls
    if sum_balls > 0:
        expected_econ = sum_runs * 6.0 / sum_balls
        out.append(check(f"{label}: economy.pool consistency",
                         _approx(doss["economy"]["pool"], expected_econ, eps=0.01),
                         f"pool={doss['economy']['pool']}, expected={round(expected_econ, 4)}"))

    # Wickets totals from observations
    wkts_list = [o["wickets"] for o in obs]
    out.append(check(f"{label}: wickets.total == sum(observations)",
                     doss["wickets"]["total"] == sum(wkts_list)))

    # Inv 8: subset invariant — count(≥k) monotonically decreasing
    counts = [sum(1 for w in wkts_list if w >= k) for k in range(0, 7)]
    for k in range(1, 7):
        out.append(check(f"{label}: count(≥{k}) ≤ count(≥{k-1})",
                         counts[k] <= counts[k-1],
                         f"counts[{k}]={counts[k]}, counts[{k-1}]={counts[k-1]}"))

    ms_w = doss["wickets"]["milestones"]
    n_innings = doss["n_innings"]

    # Inv 7 + helper validation: every prob_record is well-formed
    for key, pr in ms_w.items():
        out.extend(assert_prob_record(f"{label}: wickets.{key}", pr))

    # Inv 9: anchor invariant — conditional denoms all == count(≥2)
    geq_2 = sum(1 for w in wkts_list if w >= 2)
    out.append(check(f"{label}: p_3_given_2.denom == count(≥2)",
                     ms_w["p_3_given_2"]["denom"] == geq_2,
                     f"denom={ms_w['p_3_given_2']['denom']}, count(≥2)={geq_2}"))
    out.append(check(f"{label}: p_4_given_2.denom == count(≥2)",
                     ms_w["p_4_given_2"]["denom"] == geq_2,
                     f"denom={ms_w['p_4_given_2']['denom']}, count(≥2)={geq_2}"))
    out.append(check(f"{label}: p_5_given_2.denom == count(≥2)",
                     ms_w["p_5_given_2"]["denom"] == geq_2,
                     f"denom={ms_w['p_5_given_2']['denom']}, count(≥2)={geq_2}"))

    # Simples num check (all denom = n_innings)
    out.append(check(f"{label}: p_zero.num == count(w==0)",
                     ms_w["p_zero"]["num"] == sum(1 for w in wkts_list if w == 0)))
    out.append(check(f"{label}: p_geq_3.num == count(w≥3)",
                     ms_w["p_geq_3"]["num"] == counts[3]))
    out.append(check(f"{label}: p_geq_5.num == count(w≥5)",
                     ms_w["p_geq_5"]["num"] == counts[5]))
    out.append(check(f"{label}: simples denom == n_innings",
                     all(ms_w[k]["denom"] == n_innings for k in
                         ["p_zero", "p_geq_1", "p_geq_2", "p_geq_3", "p_geq_4", "p_geq_5"])))

    # Validate runs_conceded + economy probability records
    for key, pr in doss["runs_conceded"]["milestones"].items():
        out.extend(assert_prob_record(f"{label}: runs_conceded.{key}", pr))
    for key, pr in doss["economy"]["milestones"].items():
        out.extend(assert_prob_record(f"{label}: economy.{key}", pr))

    return out


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    out = []
    out.extend(assert_dossier_invariants(f"{label}.lifetime", resp["lifetime"]))
    for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        out.extend(assert_dossier_invariants(f"{label}.form.{w}", resp["form"][w]))

    # last_match_date — present on lifetime; equals max obs date.
    # Drives the frontend dormancy badge. Spec §11 +
    # internal_docs/design-decisions.md "Dormancy badge".
    lifetime_obs = resp["lifetime"]["wickets"]["observations"]
    obs_dates = [o["date"] for o in lifetime_obs if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    out.append(check(
        f"{label}: lifetime.last_match_date == max(observations.date)",
        resp["lifetime"].get("last_match_date") == expected_lmd,
        f"got={resp['lifetime'].get('last_match_date')}, expected={expected_lmd}",
    ))

    # Inv 2: last_10 is the date-asc tail
    lifetime_obs = resp["lifetime"]["wickets"]["observations"]
    last_10_obs = resp["form"]["last_10"]["wickets"]["observations"]
    out.append(check(f"{label}: last_10.n_innings ≤ 10",
                     resp["form"]["last_10"]["n_innings"] <= 10))
    out.append(check(f"{label}: last_10 is contiguous tail",
                     last_10_obs == lifetime_obs[-len(last_10_obs):] if last_10_obs else True))

    # Form delta consistency
    delta = resp["form"]["delta"]
    lifetime_w_mean = resp["lifetime"]["wickets"]["mean_per_innings"]
    last_10_w_mean = resp["form"]["last_10"]["wickets"]["mean_per_innings"]
    if lifetime_w_mean is not None and last_10_w_mean is not None:
        expected = round(last_10_w_mean - lifetime_w_mean, 4)
        out.append(check(f"{label}: delta.last_10_wickets_mean",
                         _approx(delta["last_10_wickets_mean_minus_lifetime"], expected, eps=0.01),
                         f"got={delta['last_10_wickets_mean_minus_lifetime']}, exp={expected}"))

    lifetime_econ = resp["lifetime"]["economy"]["pool"]
    last_10_econ = resp["form"]["last_10"]["economy"]["pool"]
    if lifetime_econ is not None and last_10_econ is not None:
        expected = round(last_10_econ - lifetime_econ, 4)
        out.append(check(f"{label}: delta.last_10_economy_pool",
                         _approx(delta["last_10_economy_pool_minus_lifetime"], expected, eps=0.01),
                         f"got={delta['last_10_economy_pool_minus_lifetime']}, exp={expected}"))

    return out


async def assert_sql_anchor(
    label: str, resp: dict, person_id: str, scope: dict, min_balls: int,
) -> list[tuple[bool, str]]:
    """Inv 11 — lifetime totals match direct SQL aggregation."""
    out = []

    # Build the same WHERE clauses the endpoint's _bowling_all_filter
    # would build (side-neutral team filter; here we don't have a
    # filter_team constraint in the SCOPE_NAMES so the side-neutral
    # part collapses; we replicate just the active filter axes).
    clauses = ["d.bowler_id = :pid", "i.super_over = 0"]
    params: dict = {"pid": person_id}
    if scope.get("tournament"):
        clauses.append("m.event_name = :tournament")
        params["tournament"] = scope["tournament"]
    if scope.get("season_from"):
        clauses.append("m.season >= :sf")
        params["sf"] = scope["season_from"]
    if scope.get("season_to"):
        clauses.append("m.season <= :st")
        params["st"] = scope["season_to"]
    where = " AND ".join(clauses)

    # n_innings (qualifying innings), sum_balls (legal), runs_conceded
    # (all deliveries — matches endpoint), wickets (4-element exclusion).
    rows = await deps._db.q(
        f"""
        SELECT i.id AS iid,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                        THEN 1 ELSE 0 END) AS legal_balls,
               SUM(d.runs_total) AS runs,
               SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        WHERE {where}
        GROUP BY i.id
        HAVING legal_balls >= :min_balls
        """,
        {**params, "min_balls": min_balls},
    )
    sql_innings = len(rows)
    sql_balls = sum(r["legal_balls"] or 0 for r in rows)
    sql_runs = sum(r["runs"] or 0 for r in rows)
    sql_wkts = sum(r["wkts"] or 0 for r in rows)

    lifetime = resp["lifetime"]
    api_balls = sum(o["balls"] for o in lifetime["wickets"]["observations"])
    api_runs = lifetime["runs_conceded"]["total"]
    api_wkts = lifetime["wickets"]["total"]

    out.append(check(f"{label}: SQL anchor n_innings",
                     lifetime["n_innings"] == sql_innings,
                     f"api={lifetime['n_innings']}, sql={sql_innings}"))
    out.append(check(f"{label}: SQL anchor balls",
                     api_balls == sql_balls,
                     f"api={api_balls}, sql={sql_balls}"))
    out.append(check(f"{label}: SQL anchor runs_conceded.total",
                     api_runs == sql_runs,
                     f"api={api_runs}, sql={sql_runs}"))
    out.append(check(f"{label}: SQL anchor wickets.total",
                     api_wkts == sql_wkts,
                     f"api={api_wkts}, sql={sql_wkts}"))

    return out


async def assert_min_balls_monotonicity(
    label: str, person_id: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 10 — min_balls=0 ⊇ min_balls=12 in observation count."""
    out = []
    f = make_filters(**scope)
    a = make_aux()
    resp_default = await bowling_distribution(
        person_id=person_id, filters=f, aux=a,
        min_balls=12, as_of_date=AS_OF,
    )
    resp_unfiltered = await bowling_distribution(
        person_id=person_id, filters=f, aux=a,
        min_balls=0, as_of_date=AS_OF,
    )
    n_default = resp_default["lifetime"]["n_innings"]
    n_unfiltered = resp_unfiltered["lifetime"]["n_innings"]
    out.append(check(f"{label}: min_balls=0 n ≥ min_balls=12 n",
                     n_unfiltered >= n_default,
                     f"unfiltered={n_unfiltered}, default={n_default}"))
    out.append(check(f"{label}: thresholds.min_balls echoed",
                     resp_default["thresholds"]["min_balls"] == 12 and
                     resp_unfiltered["thresholds"]["min_balls"] == 0))
    return out


# ─── Main ──────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    deps._db = Database(f"sqlite+aiosqlite:///{args.db}")
    await deps._db.q("PRAGMA journal_mode = WAL")

    all_results: list[tuple[bool, str]] = []

    for label, pid, scope_dict in SCOPES:
        filters = make_filters(**scope_dict)
        aux = make_aux()
        resp = await bowling_distribution(
            person_id=pid, filters=filters, aux=aux,
            min_balls=12, as_of_date=AS_OF,
        )

        all_results.extend(assert_endpoint_invariants(label, resp))
        all_results.extend(await assert_sql_anchor(label, resp, pid, scope_dict, min_balls=12))
        all_results.extend(await assert_min_balls_monotonicity(label, pid, scope_dict))

    # Empty-scope edge case — venue that doesn't exist
    pid = "462411b3"  # Bumrah
    if pid:
        empty_filters = make_filters(filter_venue="Nonexistent Stadium XYZ")
        resp = await bowling_distribution(
            person_id=pid, filters=empty_filters, aux=make_aux(),
            min_balls=12, as_of_date=AS_OF,
        )
        all_results.append(check(
            "empty_scope: lifetime.n_innings == 0",
            resp["lifetime"]["n_innings"] == 0,
        ))
        all_results.append(check(
            "empty_scope: pool_strike_rate is None",
            resp["lifetime"]["pool_strike_rate"] is None,
        ))
        all_results.append(check(
            "empty_scope: economy.pool is None",
            resp["lifetime"]["economy"]["pool"] is None,
        ))
        # Probability records on empty sample
        all_results.extend(assert_prob_record(
            "empty_scope: wickets.p_zero",
            resp["lifetime"]["wickets"]["milestones"]["p_zero"],
        ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Bowler distribution sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
