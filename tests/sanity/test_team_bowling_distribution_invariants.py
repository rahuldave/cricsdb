"""Invariants for /api/v1/teams/{team}/bowling/distribution.

Calls the endpoint function in-process across several scope
combinations and asserts the spec §16.6 invariants hold. Per
CLAUDE.md "integration tests must self-anchor against SQL", every
numeric expected value derives from sqlite3 against `cricket.db`
at runtime — no hardcoded literals.

Invariants (spec internal_docs/spec-distribution-stats.md §16.6):

  1. n_innings == len(wickets.observations) on lifetime + each form window.
  2. last_10.n_innings ≤ 10; last_10.observations is the contiguous
     date-asc tail of lifetime.observations.
  3. Phase totals (runs/balls/wickets) ≤ master sums (super-over
     deliveries excluded by filters.build but phase aggregates
     ignore over_number ≥ 20 anyway).
  4. wickets.total == sum(o.wickets); runs_conceded.total ==
     sum(o.runs_conceded); both exact.
  5. wickets.total ≤ 10 × n_innings (T20 ceiling).
  6. economy.pool == runs_conceded.total × 6 / sum_balls exact (4dp).
  7. For every milestone: value × denom ≈ num; ci_low ≤ value ≤
     ci_high; 0 ≤ ci_low; ci_high ≤ 1.
  8. Subset monotonicity — count(w ≥ k) ≤ count(w ≥ k−1) for
     k = 1..10; same for runs_conceded chain.
  9. Chain-ladder + anchored conditional invariants:
     - p_7_given_5.denom == count(w ≥ 5)
     - p_10_given_5.denom == count(w ≥ 5)
     - p_150_given_100.denom == count(rc ≥ 100), etc.
 10. Over-aware invariants:
     - p_geq_3_at_10.denom == count(reached_10_overs=1)
     - p_eq_10_given_3_at_10.denom == count(reached_10 AND wkts_at_10≥3)
     - p_double_at_10.denom == count(reached_10 AND runs_at_10>0)
 11. escalation_ratio_median == median(rc / runs_at_10 over doubling pool).
 12. last_match_date on lifetime equals max observation date.
 13. SQL anchor — lifetime n_innings, wickets.total, runs_conceded.total,
     sum_balls, economy.pool match a direct sqlite3 query for the
     same scope (with team-credited wicket exclusion).

Usage:
  uv run python tests/sanity/test_team_bowling_distribution_invariants.py
  uv run python tests/sanity/test_team_bowling_distribution_invariants.py --db tmp/cricket.db

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
from api.routers.teams import team_bowling_distribution


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


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
    obs = doss["wickets"]["observations"]

    # Inv 1
    out.append(check(f"{label}: n_innings == len(observations)",
                     n == len(obs),
                     f"n={n}, len(obs)={len(obs)}"))

    if n == 0:
        out.append(check(f"{label}: empty wickets.total == 0",
                         doss["wickets"]["total"] == 0))
        out.append(check(f"{label}: empty runs_conceded.total == 0",
                         doss["runs_conceded"]["total"] == 0))
        out.append(check(f"{label}: empty economy.pool is None",
                         doss["economy"]["pool"] is None))
        return out

    wkts_list = [o["wickets"] for o in obs]
    rc_list = [o["runs_conceded"] for o in obs]
    sum_wkts = sum(wkts_list)
    sum_rc = sum(rc_list)
    sum_balls = sum(o["balls"] for o in obs)

    # Inv 4
    out.append(check(f"{label}: wickets.total == sum(o.wickets)",
                     doss["wickets"]["total"] == sum_wkts,
                     f"total={doss['wickets']['total']}, sum={sum_wkts}"))
    out.append(check(f"{label}: runs_conceded.total == sum(o.rc)",
                     doss["runs_conceded"]["total"] == sum_rc,
                     f"total={doss['runs_conceded']['total']}, sum={sum_rc}"))

    # Inv 5: T20 ceiling
    out.append(check(f"{label}: wickets.total ≤ 10 × n",
                     sum_wkts <= 10 * n,
                     f"wkts={sum_wkts}, ceil={10 * n}"))

    # Mean × n consistency for wickets + runs_conceded
    mean_tol = max(0.02, n * 5e-5)
    if doss["wickets"]["mean_per_innings"] is not None:
        out.append(check(f"{label}: wickets.mean × n ≈ wickets.total",
                         _approx(doss["wickets"]["mean_per_innings"] * n, sum_wkts, eps=mean_tol),
                         f"mean={doss['wickets']['mean_per_innings']}, n={n}, total={sum_wkts}"))
    if doss["runs_conceded"]["mean_per_innings"] is not None:
        out.append(check(f"{label}: runs_conceded.mean × n ≈ rc.total",
                         _approx(doss["runs_conceded"]["mean_per_innings"] * n, sum_rc, eps=mean_tol),
                         f"mean={doss['runs_conceded']['mean_per_innings']}, n={n}, total={sum_rc}"))

    # Inv 3: phase totals ≤ master sums
    phase = doss["phase"]
    phase_balls = sum(phase[p]["balls_total"] for p in ("powerplay", "middle", "death"))
    phase_runs = sum(phase[p]["runs_total"] for p in ("powerplay", "middle", "death"))
    phase_wkts = sum(phase[p]["wickets_total"] for p in ("powerplay", "middle", "death"))
    out.append(check(f"{label}: phase_balls ≤ master sum_balls",
                     phase_balls <= sum_balls,
                     f"phase={phase_balls}, master={sum_balls}"))
    out.append(check(f"{label}: phase_runs ≤ runs_conceded.total",
                     phase_runs <= sum_rc,
                     f"phase={phase_runs}, master={sum_rc}"))
    out.append(check(f"{label}: phase_wkts ≤ wickets.total",
                     phase_wkts <= sum_wkts,
                     f"phase={phase_wkts}, master={sum_wkts}"))

    # Inv 6: economy.pool consistency
    if sum_balls > 0:
        expected_pool = round(sum_rc * 6.0 / sum_balls, 4)
        out.append(check(f"{label}: economy.pool == rc.total × 6 / balls",
                         _approx(doss["economy"]["pool"], expected_pool, eps=0.0001),
                         f"pool={doss['economy']['pool']}, expected={expected_pool}"))

    # economy.per_innings sanity
    expected_per = [round(o["runs_conceded"] * 6.0 / o["balls"], 4)
                    for o in obs if o["balls"] > 0]
    out.append(check(f"{label}: economy.per_innings matches obs",
                     doss["economy"]["per_innings"] == expected_per,
                     f"len_api={len(doss['economy']['per_innings'])}, len_exp={len(expected_per)}"))

    # ── wickets block ─────────────────────────────────────────────
    counts_w = {k: sum(1 for w in wkts_list if w >= k) for k in range(0, 11)}
    counts_w_eq = {k: sum(1 for w in wkts_list if w == k) for k in range(0, 11)}
    counts_w_leq = {k: sum(1 for w in wkts_list if w <= k) for k in range(0, 11)}

    # Inv 8: subset monotonicity
    for k in range(1, 11):
        out.append(check(f"{label}: count(w≥{k}) ≤ count(w≥{k-1})",
                         counts_w[k] <= counts_w[k-1],
                         f"≥{k}={counts_w[k]}, ≥{k-1}={counts_w[k-1]}"))

    ms_w = doss["wickets"]["milestones"]
    for key, pr in ms_w.items():
        out.extend(assert_prob_record(f"{label}: wickets.{key}", pr))

    # Simples num/denom
    out.append(check(f"{label}: wickets.p_leq_3.num == count(w≤3)",
                     ms_w["p_leq_3"]["num"] == counts_w_leq[3]))
    out.append(check(f"{label}: wickets.p_geq_5.num == count(w≥5)",
                     ms_w["p_geq_5"]["num"] == counts_w[5]))
    out.append(check(f"{label}: wickets.p_geq_7.num == count(w≥7)",
                     ms_w["p_geq_7"]["num"] == counts_w[7]))
    out.append(check(f"{label}: wickets.p_eq_10.num == count(w==10)",
                     ms_w["p_eq_10"]["num"] == counts_w_eq[10]))
    for key in ("p_leq_3", "p_geq_5", "p_geq_7", "p_eq_10"):
        out.append(check(f"{label}: wickets.{key}.denom == n",
                         ms_w[key]["denom"] == n,
                         f"{key}.denom={ms_w[key]['denom']}"))

    # Inv 9: anchored ladder denom == count(≥5)
    out.append(check(f"{label}: p_7_given_5.denom == count(w≥5)",
                     ms_w["p_7_given_5"]["denom"] == counts_w[5],
                     f"denom={ms_w['p_7_given_5']['denom']}, count={counts_w[5]}"))
    out.append(check(f"{label}: p_10_given_5.denom == count(w≥5)",
                     ms_w["p_10_given_5"]["denom"] == counts_w[5]))
    out.append(check(f"{label}: p_7_given_5.num == count(w≥7)",
                     ms_w["p_7_given_5"]["num"] == counts_w[7]))
    out.append(check(f"{label}: p_10_given_5.num == count(w==10)",
                     ms_w["p_10_given_5"]["num"] == counts_w_eq[10]))

    # Inv 10: over-aware
    reached_10 = [o for o in obs if o["reached_10_overs"] == 1]
    early_break = [o for o in reached_10 if o["wickets_at_10"] >= 3]
    finished_after = sum(1 for o in early_break if o["wickets"] == 10)
    out.append(check(f"{label}: p_geq_3_at_10.denom == count(reached_10)",
                     ms_w["p_geq_3_at_10"]["denom"] == len(reached_10),
                     f"denom={ms_w['p_geq_3_at_10']['denom']}, exp={len(reached_10)}"))
    out.append(check(f"{label}: p_geq_3_at_10.num == count(early_break)",
                     ms_w["p_geq_3_at_10"]["num"] == len(early_break),
                     f"num={ms_w['p_geq_3_at_10']['num']}, exp={len(early_break)}"))
    out.append(check(f"{label}: p_eq_10_given_3_at_10.denom == count(early_break)",
                     ms_w["p_eq_10_given_3_at_10"]["denom"] == len(early_break),
                     f"denom={ms_w['p_eq_10_given_3_at_10']['denom']}, exp={len(early_break)}"))
    out.append(check(f"{label}: p_eq_10_given_3_at_10.num == count(finished_after)",
                     ms_w["p_eq_10_given_3_at_10"]["num"] == finished_after,
                     f"num={ms_w['p_eq_10_given_3_at_10']['num']}, exp={finished_after}"))

    # ── runs_conceded block ───────────────────────────────────────
    counts_rc = {k: sum(1 for r in rc_list if r >= k) for k in (100, 150, 200, 230)}
    counts_rc_lt = {k: sum(1 for r in rc_list if r < k) for k in (100, 150, 200, 230)}

    for prev, cur in [(100, 150), (150, 200), (200, 230)]:
        out.append(check(f"{label}: count(rc≥{cur}) ≤ count(rc≥{prev})",
                         counts_rc[cur] <= counts_rc[prev]))

    ms_rc = doss["runs_conceded"]["milestones"]
    for key, pr in ms_rc.items():
        out.extend(assert_prob_record(f"{label}: runs_conceded.{key}", pr))

    out.append(check(f"{label}: rc.p_lt_100.num == count(rc<100)",
                     ms_rc["p_lt_100"]["num"] == counts_rc_lt[100]))
    out.append(check(f"{label}: rc.p_lt_150.num == count(rc<150)",
                     ms_rc["p_lt_150"]["num"] == counts_rc_lt[150]))
    for thresh in (150, 200, 230):
        out.append(check(f"{label}: rc.p_geq_{thresh}.num == count(rc≥{thresh})",
                         ms_rc[f"p_geq_{thresh}"]["num"] == counts_rc[thresh]))
    for key in ("p_lt_100", "p_lt_150", "p_geq_150", "p_geq_200", "p_geq_230"):
        out.append(check(f"{label}: rc.{key}.denom == n",
                         ms_rc[key]["denom"] == n))

    # Chain-ladder denoms
    out.append(check(f"{label}: rc.p_150_given_100.denom == count(≥100)",
                     ms_rc["p_150_given_100"]["denom"] == counts_rc[100]))
    out.append(check(f"{label}: rc.p_200_given_150.denom == count(≥150)",
                     ms_rc["p_200_given_150"]["denom"] == counts_rc[150]))
    out.append(check(f"{label}: rc.p_230_given_200.denom == count(≥200)",
                     ms_rc["p_230_given_200"]["denom"] == counts_rc[200]))
    out.append(check(f"{label}: rc.p_150_given_100.num == count(≥150)",
                     ms_rc["p_150_given_100"]["num"] == counts_rc[150]))
    out.append(check(f"{label}: rc.p_200_given_150.num == count(≥200)",
                     ms_rc["p_200_given_150"]["num"] == counts_rc[200]))
    out.append(check(f"{label}: rc.p_230_given_200.num == count(≥230)",
                     ms_rc["p_230_given_200"]["num"] == counts_rc[230]))

    # Doubling pool + escalation (Inv 10 + 11)
    doubling_pool = [o for o in obs
                     if o["reached_10_overs"] == 1 and o["runs_at_10"] > 0]
    expected_doubling_denom = len(doubling_pool)
    expected_doubling_num = sum(1 for o in doubling_pool
                                if o["runs_conceded"] >= 2 * o["runs_at_10"])
    out.append(check(f"{label}: rc.p_double_at_10.denom == doubling-pool",
                     ms_rc["p_double_at_10"]["denom"] == expected_doubling_denom))
    out.append(check(f"{label}: rc.p_double_at_10.num matches",
                     ms_rc["p_double_at_10"]["num"] == expected_doubling_num))

    if doubling_pool:
        ratios = [o["runs_conceded"] / o["runs_at_10"] for o in doubling_pool]
        expected_med = round(statistics.median(ratios), 4)
        out.append(check(f"{label}: rc.escalation_ratio_median consistency",
                         _approx(doss["runs_conceded"]["escalation_ratio_median"], expected_med, eps=0.0001),
                         f"got={doss['runs_conceded']['escalation_ratio_median']}, exp={expected_med}"))
    else:
        out.append(check(f"{label}: rc.escalation_ratio_median None when pool empty",
                         doss["runs_conceded"]["escalation_ratio_median"] is None))

    # ── economy block ─────────────────────────────────────────────
    ms_ec = doss["economy"]["milestones"]
    for key, pr in ms_ec.items():
        out.extend(assert_prob_record(f"{label}: economy.{key}", pr))

    return out


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    out = []
    out.extend(assert_dossier_invariants(f"{label}.lifetime", resp["lifetime"]))
    for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        out.extend(assert_dossier_invariants(f"{label}.form.{w}", resp["form"][w]))

    # Inv 12: last_match_date
    lifetime_obs = resp["lifetime"]["wickets"]["observations"]
    obs_dates = [o["date"] for o in lifetime_obs if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    out.append(check(
        f"{label}: lifetime.last_match_date == max(observations.date)",
        resp["lifetime"].get("last_match_date") == expected_lmd,
        f"got={resp['lifetime'].get('last_match_date')}, expected={expected_lmd}",
    ))

    # Inv 2: last_10 contiguous tail
    last_10_obs = resp["form"]["last_10"]["wickets"]["observations"]
    out.append(check(f"{label}: last_10.n_innings ≤ 10",
                     resp["form"]["last_10"]["n_innings"] <= 10))
    out.append(check(f"{label}: last_10 is contiguous tail",
                     last_10_obs == lifetime_obs[-len(last_10_obs):] if last_10_obs else True))

    # Form delta consistency — 12 entries × 3 metric families
    delta = resp["form"]["delta"]
    out.append(check(f"{label}: delta has 12 entries",
                     len(delta) == 12,
                     f"got {len(delta)}: {sorted(delta.keys())}"))

    lifetime_w_mean = resp["lifetime"]["wickets"]["mean_per_innings"]
    last_10_w_mean = resp["form"]["last_10"]["wickets"]["mean_per_innings"]
    if lifetime_w_mean is not None and last_10_w_mean is not None:
        expected = round(last_10_w_mean - lifetime_w_mean, 4)
        out.append(check(f"{label}: delta.last_10_wickets_mean",
                         _approx(delta["last_10_wickets_mean_minus_lifetime"], expected, eps=0.01)))

    lifetime_rc_mean = resp["lifetime"]["runs_conceded"]["mean_per_innings"]
    last_10_rc_mean = resp["form"]["last_10"]["runs_conceded"]["mean_per_innings"]
    if lifetime_rc_mean is not None and last_10_rc_mean is not None:
        expected = round(last_10_rc_mean - lifetime_rc_mean, 4)
        out.append(check(f"{label}: delta.last_10_runs_conceded_mean",
                         _approx(delta["last_10_runs_conceded_mean_minus_lifetime"], expected, eps=0.01)))

    lifetime_pool = resp["lifetime"]["economy"]["pool"]
    last_10_pool = resp["form"]["last_10"]["economy"]["pool"]
    if lifetime_pool is not None and last_10_pool is not None:
        expected = round(last_10_pool - lifetime_pool, 4)
        out.append(check(f"{label}: delta.last_10_economy_pool",
                         _approx(delta["last_10_economy_pool_minus_lifetime"], expected, eps=0.01)))

    return out


async def assert_sql_anchor(
    label: str, resp: dict, team: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 13 — lifetime totals match direct SQL aggregation against
    the OPP's batting innings (i.team != team AND match has team).
    Wickets use the team-credited 4-kind exclusion (includes run-outs).
    """
    out = []

    clauses = ["i.team != :team",
               "(m.team1 = :team OR m.team2 = :team)",
               "i.super_over = 0"]
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
               SUM(d.runs_total) AS runs_conceded,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                        THEN 1 ELSE 0 END) AS legal_balls,
               SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wkts
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.kind NOT IN ('retired hurt', 'retired out', 'retired not out', 'obstructing the field')
        WHERE {where}
        GROUP BY i.id
        """,
        params,
    )
    sql_innings = len(rows)
    sql_runs = sum(r["runs_conceded"] or 0 for r in rows)
    sql_balls = sum(r["legal_balls"] or 0 for r in rows)
    sql_wkts = sum(r["wkts"] or 0 for r in rows)
    sql_pool = round(sql_runs * 6.0 / sql_balls, 4) if sql_balls > 0 else None

    lifetime = resp["lifetime"]
    api_balls = sum(o["balls"] for o in lifetime["wickets"]["observations"])

    out.append(check(f"{label}: SQL anchor n_innings",
                     lifetime["n_innings"] == sql_innings,
                     f"api={lifetime['n_innings']}, sql={sql_innings}"))
    out.append(check(f"{label}: SQL anchor wickets.total",
                     lifetime["wickets"]["total"] == sql_wkts,
                     f"api={lifetime['wickets']['total']}, sql={sql_wkts}"))
    out.append(check(f"{label}: SQL anchor runs_conceded.total",
                     lifetime["runs_conceded"]["total"] == sql_runs,
                     f"api={lifetime['runs_conceded']['total']}, sql={sql_runs}"))
    out.append(check(f"{label}: SQL anchor sum_balls",
                     api_balls == sql_balls,
                     f"api={api_balls}, sql={sql_balls}"))
    out.append(check(f"{label}: SQL anchor economy.pool",
                     _approx(lifetime["economy"]["pool"], sql_pool, eps=0.0001),
                     f"api={lifetime['economy']['pool']}, sql={sql_pool}"))

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
        resp = await team_bowling_distribution(
            team=team, filters=filters, aux=aux, as_of_date=AS_OF,
        )

        all_results.extend(assert_endpoint_invariants(label, resp))
        all_results.extend(await assert_sql_anchor(label, resp, team, scope_dict))

    # Empty-scope edge case
    empty_filters = make_filters(filter_venue="Nonexistent Stadium XYZ")
    resp = await team_bowling_distribution(
        team="Mumbai Indians", filters=empty_filters, aux=make_aux(),
        as_of_date=AS_OF,
    )
    all_results.append(check(
        "empty_scope: lifetime.n_innings == 0",
        resp["lifetime"]["n_innings"] == 0,
    ))
    all_results.append(check(
        "empty_scope: wickets.total == 0",
        resp["lifetime"]["wickets"]["total"] == 0,
    ))
    all_results.append(check(
        "empty_scope: runs_conceded.total == 0",
        resp["lifetime"]["runs_conceded"]["total"] == 0,
    ))
    all_results.append(check(
        "empty_scope: economy.pool is None",
        resp["lifetime"]["economy"]["pool"] is None,
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: wickets.p_geq_5",
        resp["lifetime"]["wickets"]["milestones"]["p_geq_5"],
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: rc.p_double_at_10",
        resp["lifetime"]["runs_conceded"]["milestones"]["p_double_at_10"],
    ))
    all_results.append(check(
        "empty_scope: lifetime.last_match_date is None",
        resp["lifetime"]["last_match_date"] is None,
    ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Team-bowling distribution sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
