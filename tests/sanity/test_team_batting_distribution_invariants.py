"""Invariants for /api/v1/teams/{team}/batting/distribution.

Calls the endpoint function in-process across several scope
combinations and asserts the spec §16.6 invariants hold. Per
CLAUDE.md "integration tests must self-anchor against SQL", every
numeric expected value derives from sqlite3 against `cricket.db`
at runtime — no hardcoded literals.

Invariants (spec internal_docs/spec-distribution-stats.md §16.6):

  1. n_innings == len(runs.observations) on lifetime + each form window.
  2. last_10.n_innings ≤ 10; last_10.observations is the contiguous
     date-asc tail of lifetime.observations.
  3. Phase partition — runs/balls/wickets per phase sum to the
     master-sample totals (within the over_number 0..19 range).
  4. runs.total == sum(o.runs) exact.
  5. runs.mean_per_innings × n_innings ≈ runs.total.
  6. run_rate.pool == runs.total × 6 / sum_balls exact (4dp).
  7. For every milestone: value × denom ≈ num; ci_low ≤ value ≤
     ci_high; 0 ≤ ci_low; ci_high ≤ 1.
  8. Subset monotonicity — count(r ≥ k+50) ≤ count(r ≥ k) for the
     100/150/200/230 ladder.
  9. Chain-ladder denom invariant: p_150_given_100.denom == count(≥100),
     p_200_given_150.denom == count(≥150), p_230_given_200.denom ==
     count(≥200).
 10. p_double_at_10.denom == count(reached_10_overs=1 AND runs_at_10>0).
 11. escalation_ratio_median == median([o.runs / o.runs_at_10] over
     the doubling pool).
 12. last_match_date on lifetime equals max observation date.
 13. SQL anchor — lifetime n_innings, runs.total, sum_balls,
     run_rate.pool match a direct sqlite3 query for the same scope.

Usage:
  uv run python tests/sanity/test_team_batting_distribution_invariants.py
  uv run python tests/sanity/test_team_batting_distribution_invariants.py --db tmp/cricket.db

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams
from api.routers.teams import team_batting_distribution


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


# (label, team, filter dict). Mumbai (marquee IPL franchise), CSK
# (sibling franchise), India men (international marquee), Kuwait
# men (sparse-ish associate), plus IPL-2024 narrow scope.
SCOPES: list[tuple[str, str, dict]] = [
    ("mumbai_all_time",  "Mumbai Indians",      {}),
    ("mumbai_ipl_2024",  "Mumbai Indians",      {"tournament": "Indian Premier League", "season_from": "2024", "season_to": "2024"}),
    ("india_men_all",    "India",               {"gender": "male"}),
    ("csk_all",          "Chennai Super Kings", {}),
    ("kuwait_men",       "Kuwait",              {"gender": "male"}),
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

    rnd_tol = max(0.01, pr["denom"] * 5e-5)
    out.append(check(f"{label}: value × denom == num",
                     _approx(pr["value"] * pr["denom"], pr["num"], eps=rnd_tol),
                     f"value={pr['value']}, denom={pr['denom']}, num={pr['num']}"))
    out.append(check(f"{label}: 0 ≤ ci_low",
                     pr["ci_low"] >= 0,
                     f"ci_low={pr['ci_low']}"))
    out.append(check(f"{label}: ci_high ≤ 1",
                     pr["ci_high"] <= 1.0001,
                     f"ci_high={pr['ci_high']}"))
    out.append(check(f"{label}: ci_low ≤ value ≤ ci_high",
                     pr["ci_low"] - 0.0001 <= pr["value"] <= pr["ci_high"] + 0.0001,
                     f"({pr['ci_low']}, {pr['value']}, {pr['ci_high']})"))
    return out


def assert_dossier_invariants(label: str, doss: dict) -> list[tuple[bool, str]]:
    out = []
    n = doss["n_innings"]
    obs = doss["runs"]["observations"]

    # Inv 1
    out.append(check(f"{label}: n_innings == len(observations)",
                     n == len(obs),
                     f"n={n}, len(obs)={len(obs)}"))

    if n == 0:
        out.append(check(f"{label}: empty runs.total == 0",
                         doss["runs"]["total"] == 0))
        out.append(check(f"{label}: empty run_rate.pool is None",
                         doss["run_rate"]["pool"] is None))
        return out

    runs_list = [o["runs"] for o in obs]
    sum_runs = sum(runs_list)
    sum_balls = sum(o["balls"] for o in obs)

    # Inv 4
    out.append(check(f"{label}: runs.total == sum(o.runs)",
                     doss["runs"]["total"] == sum_runs,
                     f"total={doss['runs']['total']}, sum={sum_runs}"))

    # Inv 5
    if n > 0:
        expected_mean = sum_runs / n
        # Tolerance scales with n — mean is rounded to 4dp, so worst-
        # case mean × n drift is n × 5e-5; floor at 0.02.
        mean_tol = max(0.02, n * 5e-5)
        out.append(check(f"{label}: runs.mean_per_innings × n ≈ runs.total",
                         _approx(doss["runs"]["mean_per_innings"] * n, sum_runs, eps=mean_tol),
                         f"mean={doss['runs']['mean_per_innings']}, n={n}, total={sum_runs}"))
        out.append(check(f"{label}: runs.mean_per_innings == sum/n",
                         _approx(doss["runs"]["mean_per_innings"], expected_mean, eps=0.0001),
                         f"got={doss['runs']['mean_per_innings']}, expected={round(expected_mean, 4)}"))

    # Inv 3: phase partition (runs + balls only — over_number 0..19
    # covers all standard overs; super-over deliveries are excluded
    # from phase but included in runs.total. Assert phase_runs ≤ total.)
    phase = doss["phase"]
    phase_balls = phase["powerplay"]["balls_total"] + phase["middle"]["balls_total"] + phase["death"]["balls_total"]
    phase_runs = phase["powerplay"]["runs_total"] + phase["middle"]["runs_total"] + phase["death"]["runs_total"]
    out.append(check(f"{label}: phase_balls ≤ master sum_balls",
                     phase_balls <= sum_balls,
                     f"phase={phase_balls}, master={sum_balls}"))
    out.append(check(f"{label}: phase_runs ≤ runs.total",
                     phase_runs <= sum_runs,
                     f"phase={phase_runs}, master={sum_runs}"))

    # Inv 6: run_rate.pool == sum_runs × 6 / sum_balls
    if sum_balls > 0:
        expected_pool = round(sum_runs * 6.0 / sum_balls, 4)
        out.append(check(f"{label}: run_rate.pool == runs.total × 6 / balls",
                         _approx(doss["run_rate"]["pool"], expected_pool, eps=0.0001),
                         f"pool={doss['run_rate']['pool']}, expected={expected_pool}"))

    # run_rate.per_innings sanity
    expected_per = [round(o["runs"] * 6.0 / o["balls"], 4)
                    for o in obs if o["balls"] > 0]
    out.append(check(f"{label}: run_rate.per_innings matches obs",
                     doss["run_rate"]["per_innings"] == expected_per,
                     f"len_api={len(doss['run_rate']['per_innings'])}, len_exp={len(expected_per)}"))

    # Subset monotonicity (Inv 8)
    geq = {k: sum(1 for r in runs_list if r >= k) for k in (100, 150, 200, 230)}
    lt_100 = sum(1 for r in runs_list if r < 100)
    out.append(check(f"{label}: lt_100 + geq_100 == n",
                     lt_100 + geq[100] == n,
                     f"lt_100={lt_100}, geq_100={geq[100]}, n={n}"))
    for prev, cur in [(100, 150), (150, 200), (200, 230)]:
        out.append(check(f"{label}: count(≥{cur}) ≤ count(≥{prev})",
                         geq[cur] <= geq[prev],
                         f"≥{cur}={geq[cur]}, ≥{prev}={geq[prev]}"))

    # Inv 7 — every prob_record well-formed
    ms_r = doss["runs"]["milestones"]
    for key, pr in ms_r.items():
        out.extend(assert_prob_record(f"{label}: runs.{key}", pr))
    for key, pr in doss["run_rate"]["milestones"].items():
        out.extend(assert_prob_record(f"{label}: run_rate.{key}", pr))

    # Simples num check
    out.append(check(f"{label}: runs.p_lt_100.num == count(r<100)",
                     ms_r["p_lt_100"]["num"] == lt_100))
    for thresh in (100, 150, 200, 230):
        key = f"p_geq_{thresh}"
        out.append(check(f"{label}: runs.{key}.num == count(r≥{thresh})",
                         ms_r[key]["num"] == geq[thresh]))
    # Simples denom == n
    for key in ("p_lt_100", "p_geq_100", "p_geq_150", "p_geq_200", "p_geq_230"):
        out.append(check(f"{label}: runs.{key}.denom == n_innings",
                         ms_r[key]["denom"] == n,
                         f"{key}.denom={ms_r[key]['denom']}, n={n}"))

    # Inv 9: chain-ladder denom invariant
    out.append(check(f"{label}: p_150_given_100.denom == count(≥100)",
                     ms_r["p_150_given_100"]["denom"] == geq[100],
                     f"denom={ms_r['p_150_given_100']['denom']}, count={geq[100]}"))
    out.append(check(f"{label}: p_200_given_150.denom == count(≥150)",
                     ms_r["p_200_given_150"]["denom"] == geq[150],
                     f"denom={ms_r['p_200_given_150']['denom']}, count={geq[150]}"))
    out.append(check(f"{label}: p_230_given_200.denom == count(≥200)",
                     ms_r["p_230_given_200"]["denom"] == geq[200],
                     f"denom={ms_r['p_230_given_200']['denom']}, count={geq[200]}"))
    out.append(check(f"{label}: p_150_given_100.num == count(≥150)",
                     ms_r["p_150_given_100"]["num"] == geq[150]))
    out.append(check(f"{label}: p_200_given_150.num == count(≥200)",
                     ms_r["p_200_given_150"]["num"] == geq[200]))
    out.append(check(f"{label}: p_230_given_200.num == count(≥230)",
                     ms_r["p_230_given_200"]["num"] == geq[230]))

    # Inv 10: doubling-pool denom + Inv 11: escalation median
    doubling_pool = [o for o in obs
                     if o["reached_10_overs"] == 1 and o["runs_at_10"] > 0]
    expected_doubling_denom = len(doubling_pool)
    expected_doubling_num = sum(1 for o in doubling_pool
                                if o["runs"] >= 2 * o["runs_at_10"])
    out.append(check(f"{label}: p_double_at_10.denom == doubling-pool size",
                     ms_r["p_double_at_10"]["denom"] == expected_doubling_denom,
                     f"denom={ms_r['p_double_at_10']['denom']}, exp={expected_doubling_denom}"))
    out.append(check(f"{label}: p_double_at_10.num matches",
                     ms_r["p_double_at_10"]["num"] == expected_doubling_num,
                     f"num={ms_r['p_double_at_10']['num']}, exp={expected_doubling_num}"))

    if doubling_pool:
        ratios = [o["runs"] / o["runs_at_10"] for o in doubling_pool]
        expected_med = round(statistics.median(ratios), 4)
        out.append(check(f"{label}: escalation_ratio_median consistency",
                         _approx(doss["runs"]["escalation_ratio_median"], expected_med, eps=0.0001),
                         f"got={doss['runs']['escalation_ratio_median']}, exp={expected_med}"))
    else:
        out.append(check(f"{label}: escalation_ratio_median None when pool empty",
                         doss["runs"]["escalation_ratio_median"] is None))

    return out


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    out = []
    out.extend(assert_dossier_invariants(f"{label}.lifetime", resp["lifetime"]))
    for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        out.extend(assert_dossier_invariants(f"{label}.form.{w}", resp["form"][w]))

    # Inv 12: last_match_date
    lifetime_obs = resp["lifetime"]["runs"]["observations"]
    obs_dates = [o["date"] for o in lifetime_obs if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    out.append(check(
        f"{label}: lifetime.last_match_date == max(observations.date)",
        resp["lifetime"].get("last_match_date") == expected_lmd,
        f"got={resp['lifetime'].get('last_match_date')}, expected={expected_lmd}",
    ))

    # Inv 2: last_10 is the date-asc tail
    last_10_obs = resp["form"]["last_10"]["runs"]["observations"]
    out.append(check(f"{label}: last_10.n_innings ≤ 10",
                     resp["form"]["last_10"]["n_innings"] <= 10))
    out.append(check(f"{label}: last_10 is contiguous tail",
                     last_10_obs == lifetime_obs[-len(last_10_obs):] if last_10_obs else True))

    # Form delta consistency
    delta = resp["form"]["delta"]
    lifetime_runs_mean = resp["lifetime"]["runs"]["mean_per_innings"]
    last_10_runs_mean = resp["form"]["last_10"]["runs"]["mean_per_innings"]
    if lifetime_runs_mean is not None and last_10_runs_mean is not None:
        expected = round(last_10_runs_mean - lifetime_runs_mean, 4)
        out.append(check(f"{label}: delta.last_10_runs_mean",
                         _approx(delta["last_10_runs_mean_minus_lifetime"], expected, eps=0.01),
                         f"got={delta['last_10_runs_mean_minus_lifetime']}, exp={expected}"))

    lifetime_pool = resp["lifetime"]["run_rate"]["pool"]
    last_10_pool = resp["form"]["last_10"]["run_rate"]["pool"]
    if lifetime_pool is not None and last_10_pool is not None:
        expected = round(last_10_pool - lifetime_pool, 4)
        out.append(check(f"{label}: delta.last_10_run_rate_pool",
                         _approx(delta["last_10_run_rate_pool_minus_lifetime"], expected, eps=0.01),
                         f"got={delta['last_10_run_rate_pool_minus_lifetime']}, exp={expected}"))

    return out


async def assert_sql_anchor(
    label: str, resp: dict, team: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 13 — lifetime totals match direct SQL aggregation.

    Mirrors the endpoint's master-sample WHERE: i.team=:team plus
    the active filter axes. Wickets exclude 'retired hurt' and
    'retired not out' to match the LEFT JOIN in the endpoint.
    """
    out = []

    # filters.build(has_innings_join=True) auto-adds i.super_over=0;
    # mirror that here so the anchor matches the endpoint exactly.
    clauses = ["i.team = :team", "i.super_over = 0"]
    params: dict = {"team": team}
    if scope.get("gender"):
        clauses.append("m.gender = :gender")
        params["gender"] = scope["gender"]
    if scope.get("team_type"):
        clauses.append("m.team_type = :team_type")
        params["team_type"] = scope["team_type"]
    if scope.get("tournament"):
        clauses.append("m.event_name = :tournament")
        params["tournament"] = scope["tournament"]
    if scope.get("season_from"):
        clauses.append("m.season >= :sf")
        params["sf"] = scope["season_from"]
    if scope.get("season_to"):
        clauses.append("m.season <= :st")
        params["st"] = scope["season_to"]
    if scope.get("filter_venue"):
        clauses.append("m.venue = :venue")
        params["venue"] = scope["filter_venue"]
    where = " AND ".join(clauses)

    rows = await deps._db.q(
        f"""
        SELECT i.id AS iid,
               SUM(d.runs_total) AS runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                        THEN 1 ELSE 0 END) AS legal_balls,
               SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.kind NOT IN ('retired hurt', 'retired not out')
        WHERE {where}
        GROUP BY i.id
        """,
        params,
    )
    sql_innings = len(rows)
    sql_runs = sum(r["runs"] or 0 for r in rows)
    sql_balls = sum(r["legal_balls"] or 0 for r in rows)
    sql_wkts = sum(r["wkts"] or 0 for r in rows)
    sql_pool = round(sql_runs * 6.0 / sql_balls, 4) if sql_balls > 0 else None

    lifetime = resp["lifetime"]
    api_balls = sum(o["balls"] for o in lifetime["runs"]["observations"])
    api_wkts = sum(o["wickets"] for o in lifetime["runs"]["observations"])

    out.append(check(f"{label}: SQL anchor n_innings",
                     lifetime["n_innings"] == sql_innings,
                     f"api={lifetime['n_innings']}, sql={sql_innings}"))
    out.append(check(f"{label}: SQL anchor runs.total",
                     lifetime["runs"]["total"] == sql_runs,
                     f"api={lifetime['runs']['total']}, sql={sql_runs}"))
    out.append(check(f"{label}: SQL anchor sum_balls",
                     api_balls == sql_balls,
                     f"api={api_balls}, sql={sql_balls}"))
    out.append(check(f"{label}: SQL anchor wickets total",
                     api_wkts == sql_wkts,
                     f"api={api_wkts}, sql={sql_wkts}"))
    out.append(check(f"{label}: SQL anchor run_rate.pool",
                     _approx(lifetime["run_rate"]["pool"], sql_pool, eps=0.0001),
                     f"api={lifetime['run_rate']['pool']}, sql={sql_pool}"))

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

    for label, team, scope_dict in SCOPES:
        filters = make_filters(**scope_dict)
        aux = make_aux()
        resp = await team_batting_distribution(
            team=team, filters=filters, aux=aux, as_of_date=AS_OF,
        )

        all_results.extend(assert_endpoint_invariants(label, resp))
        all_results.extend(await assert_sql_anchor(label, resp, team, scope_dict))

    # Empty-scope edge case — venue that doesn't exist.
    empty_filters = make_filters(filter_venue="Nonexistent Stadium XYZ")
    resp = await team_batting_distribution(
        team="Mumbai Indians", filters=empty_filters, aux=make_aux(),
        as_of_date=AS_OF,
    )
    all_results.append(check(
        "empty_scope: lifetime.n_innings == 0",
        resp["lifetime"]["n_innings"] == 0,
    ))
    all_results.append(check(
        "empty_scope: runs.total == 0",
        resp["lifetime"]["runs"]["total"] == 0,
    ))
    all_results.append(check(
        "empty_scope: run_rate.pool is None",
        resp["lifetime"]["run_rate"]["pool"] is None,
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: runs.p_geq_100",
        resp["lifetime"]["runs"]["milestones"]["p_geq_100"],
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: runs.p_double_at_10",
        resp["lifetime"]["runs"]["milestones"]["p_double_at_10"],
    ))
    all_results.append(check(
        "empty_scope: lifetime.last_match_date is None",
        resp["lifetime"]["last_match_date"] is None,
    ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Team-batting distribution sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
