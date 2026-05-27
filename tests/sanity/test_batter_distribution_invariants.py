"""Invariants for /api/v1/batters/{id}/distribution.

Calls the endpoint function in-process (no running uvicorn needed)
across several scope combinations and asserts the spec §8.10
invariants hold.

Invariants (spec internal_docs/spec-distribution-stats.md §8.10):

  1. `n_innings == len(observations)` on lifetime + each form window.
  2. `last_10.n_innings ≤ 10`.
  3. `last_10.observations` is the contiguous date-asc tail of
     `lifetime.observations`.
  4. Phase partition — runs_total per phase sums to runs.total.
  5. Phase partition — balls_total per phase sums to runs.balls_total.
  6. mean_per_innings × n_innings ≈ runs.total.
  7. average × n_dismissals ≈ runs.total when n_dismissals > 0;
     average is None when n_dismissals == 0.
  8. milestones.p_X × n_innings == count(observations satisfying X).
  9. form.delta.last_10_mean_minus_lifetime ==
     last_10.runs.mean_per_innings − lifetime.runs.mean_per_innings.
 10. SQL anchor — lifetime n_innings, runs.total, runs.balls_total
     match a direct sqlite3 query against cricket.db for the same
     filter scope.

Usage:
  uv run python tests/sanity/test_batter_distribution_invariants.py
  uv run python tests/sanity/test_batter_distribution_invariants.py --db tmp/cricket-prod-test.db

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
from api.routers.batting import batting_distribution


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


# (label, person_id, filter dict). Pin as_of_date deterministically
# per test so form.last_60d window is reproducible.
SCOPES = [
    ("kohli_ipl_2024",
     "ba607b88",
     {"tournament": "Indian Premier League", "season_from": "2024", "season_to": "2024"}),
    ("kohli_all_time",
     "ba607b88",
     {}),
    ("kohli_ipl_2023",
     "ba607b88",
     {"tournament": "Indian Premier League", "season_from": "2023", "season_to": "2023"}),
    ("kohli_vs_csk_ipl",
     "ba607b88",
     {"tournament": "Indian Premier League", "filter_opponent": "Chennai Super Kings"}),
]

AS_OF = "2025-01-01"


# ─── Assertion helpers ──────────────────────────────────────────────────

def _approx(a, b, eps=0.01) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < eps


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    return ok, f"{status} · {label}{(' — ' + detail) if detail and not ok else ''}"


def assert_dossier_invariants(label: str, doss: dict) -> list[tuple[bool, str]]:
    """Run dossier-level invariants (1, 4, 5, 6, 7, 8) on lifetime or
    a form-window dossier."""
    results: list[tuple[bool, str]] = []
    n = doss["n_innings"]
    obs = doss["runs"]["observations"]

    # 1
    results.append(check(
        f"{label} · n_innings == len(observations)",
        n == len(obs),
        f"n_innings={n} len(obs)={len(obs)}",
    ))

    # 4 — phase runs partition
    runs_total = doss["runs"]["total"]
    phase_runs_sum = sum(doss["phase"][p]["runs_total"] for p in ("powerplay", "middle", "death"))
    results.append(check(
        f"{label} · phase runs partition",
        runs_total == phase_runs_sum,
        f"runs.total={runs_total} sum(phase.runs_total)={phase_runs_sum}",
    ))

    # 5 — phase balls partition
    balls_total = doss["runs"]["balls_total"]
    phase_balls_sum = sum(doss["phase"][p]["balls_total"] for p in ("powerplay", "middle", "death"))
    results.append(check(
        f"{label} · phase balls partition",
        balls_total == phase_balls_sum,
        f"balls_total={balls_total} sum(phase.balls_total)={phase_balls_sum}",
    ))

    # 6 — mean × n ≈ total
    if n > 0:
        mean = doss["runs"]["mean_per_innings"]
        results.append(check(
            f"{label} · mean × n ≈ total",
            _approx(mean * n, runs_total, eps=n * 0.01 + 0.5),
            f"mean={mean} n={n} mean*n={mean*n} total={runs_total}",
        ))

    # 7 — average × n_dismissals ≈ total
    n_dism = doss["n_dismissals"]
    avg = doss["runs"]["average"]
    if n_dism > 0:
        results.append(check(
            f"{label} · average × n_dismissals ≈ total",
            _approx(avg * n_dism, runs_total, eps=n_dism * 0.01 + 0.5),
            f"avg={avg} n_dism={n_dism} avg*n_dism={avg*n_dism} total={runs_total}",
        ))
    else:
        results.append(check(
            f"{label} · average is None when n_dismissals == 0",
            avg is None,
            f"avg={avg} n_dism={n_dism}",
        ))

    # 8 — milestone denominator correctness for the simples (post-§13:
    # every milestone is a ProbRecord {value, num, denom, ci_low, ci_high}.
    if n > 0:
        ms = doss["milestones"]
        runs_list = [o["runs"] for o in obs]

        def _check_pr(pr: dict, ctx: str) -> None:
            # Required milestone-ProbRecord keys must be present. The record
            # also carries cohort/CI fields (scope_avg, delta_pct, direction,
            # sample_size) added by prob-baselines — allow them (superset).
            keys = {"value", "num", "denom", "ci_low", "ci_high"}
            results.append(check(
                f"{label} · {ctx} ProbRecord shape",
                keys.issubset(set(pr.keys())),
                f"got {set(pr.keys())}",
            ))
            if pr["denom"] > 0:
                # value × denom ≈ num — tolerance scales with denom (4dp round).
                rnd_tol = max(0.01, pr["denom"] * 5e-5)
                results.append(check(
                    f"{label} · {ctx} value × denom ≈ num",
                    abs(pr["value"] * pr["denom"] - pr["num"]) < rnd_tol,
                    f"v={pr['value']} d={pr['denom']} n={pr['num']}",
                ))
                results.append(check(
                    f"{label} · {ctx} ci_low ≤ value ≤ ci_high",
                    pr["ci_low"] - 1e-4 <= pr["value"] <= pr["ci_high"] + 1e-4,
                    f"({pr['ci_low']}, {pr['value']}, {pr['ci_high']})",
                ))
                results.append(check(
                    f"{label} · {ctx} 0 ≤ ci_low",
                    pr["ci_low"] >= 0,
                    f"ci_low={pr['ci_low']}",
                ))
                results.append(check(
                    f"{label} · {ctx} ci_high ≤ 1",
                    pr["ci_high"] <= 1.0001,
                    f"ci_high={pr['ci_high']}",
                ))

        for label_p, threshold, pred in [
            ("p_failure_10", 10, lambda r: r <= 10),
            ("p_25_plus", 25, lambda r: r >= 25),
            ("p_30_plus", 30, lambda r: r >= 30),
            ("p_50_plus", 50, lambda r: r >= 50),
            ("p_100_plus", 100, lambda r: r >= 100),
        ]:
            count_actual = sum(1 for r in runs_list if pred(r))
            pr = ms[label_p]
            _check_pr(pr, label_p)
            results.append(check(
                f"{label} · {label_p} num matches actual count",
                pr["num"] == count_actual,
                f"actual={count_actual} pr.num={pr['num']}",
            ))
            results.append(check(
                f"{label} · {label_p} denom == n_innings",
                pr["denom"] == n,
                f"pr.denom={pr['denom']} n={n}",
            ))

        # 8b — conditional milestones: denom = count(≥B). When count(≥B) == 0
        # the prob_record returns {value:None, denom:0, ci:None,None}.
        for label_p, num_thr, denom_thr in [
            ("p_50_given_30", 50, 30),
            ("p_70_given_50", 70, 50),
        ]:
            count_num = sum(1 for r in runs_list if r >= num_thr)
            count_denom = sum(1 for r in runs_list if r >= denom_thr)
            pr = ms[label_p]
            _check_pr(pr, label_p)
            results.append(check(
                f"{label} · {label_p} denom == count(≥{denom_thr})",
                pr["denom"] == count_denom,
                f"pr.denom={pr['denom']} count(≥{denom_thr})={count_denom}",
            ))
            if count_denom == 0:
                results.append(check(
                    f"{label} · {label_p} value None when count(≥{denom_thr})==0",
                    pr["value"] is None,
                    f"got {pr['value']}",
                ))
            else:
                expected = count_num / count_denom
                results.append(check(
                    f"{label} · {label_p} value ≈ count(≥{num_thr})/count(≥{denom_thr})",
                    pr["value"] is not None and abs(pr["value"] - expected) < 1e-3,
                    f"expected≈{expected:.4f} got={pr['value']}",
                ))
                # Subset invariant — value ≤ 1 (count(≥A) ≤ count(≥B) for A > B).
                results.append(check(
                    f"{label} · {label_p} ≤ 1 (subset invariant)",
                    pr["value"] is not None and pr["value"] <= 1.0 + 1e-9,
                    f"got={pr['value']}",
                ))

    return results


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    """Run cross-section invariants (2, 3, 9) on the full response."""
    results: list[tuple[bool, str]] = []
    lifetime = resp["lifetime"]
    last_10 = resp["form"]["last_10"]
    delta = resp["form"]["delta"]

    # last_match_date — present on lifetime; equals max obs date.
    # Drives the frontend dormancy badge. Spec §8 +
    # internal_docs/design-decisions.md "Dormancy badge".
    obs_dates = [o["date"] for o in lifetime["runs"]["observations"] if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    results.append(check(
        f"{label} · lifetime.last_match_date == max(observations.date)",
        lifetime.get("last_match_date") == expected_lmd,
        f"got={lifetime.get('last_match_date')}, expected={expected_lmd}",
    ))

    # 2 — last_10 size
    results.append(check(
        f"{label} · last_10.n_innings ≤ 10",
        last_10["n_innings"] <= 10,
        f"last_10.n_innings={last_10['n_innings']}",
    ))

    # 3 — last_10 is tail of lifetime (date-asc, so last 10 of
    # lifetime.observations are the last_10 sample)
    lifetime_obs = lifetime["runs"]["observations"]
    last_10_obs = last_10["runs"]["observations"]
    expected_tail = lifetime_obs[-len(last_10_obs):] if last_10_obs else []
    results.append(check(
        f"{label} · last_10 is contiguous tail of lifetime",
        last_10_obs == expected_tail,
        f"len(tail)={len(expected_tail)} len(last_10)={len(last_10_obs)}",
    ))

    # 9 — delta consistency
    if last_10["n_innings"] > 0 and lifetime["n_innings"] > 0:
        lt_mean = lifetime["runs"]["mean_per_innings"]
        l10_mean = last_10["runs"]["mean_per_innings"]
        expected_delta = round(l10_mean - lt_mean, 2)
        results.append(check(
            f"{label} · form.delta.last_10_mean_minus_lifetime",
            _approx(delta["last_10_mean_minus_lifetime"], expected_delta),
            f"delta={delta['last_10_mean_minus_lifetime']} expected={expected_delta}",
        ))
        lt_med = lifetime["runs"]["median"]
        l10_med = last_10["runs"]["median"]
        expected_med_delta = round(l10_med - lt_med, 2)
        results.append(check(
            f"{label} · form.delta.last_10_median_minus_lifetime",
            _approx(delta["last_10_median_minus_lifetime"], expected_med_delta),
            f"delta={delta['last_10_median_minus_lifetime']} expected={expected_med_delta}",
        ))

    return results


async def assert_sql_anchor(
    label: str, resp: dict, person_id: str, scope: dict
) -> list[tuple[bool, str]]:
    """Invariant 10 — lifetime totals match a direct SQL aggregation."""
    results: list[tuple[bool, str]] = []

    # Runs are all-ball (spec-batting-allball-runs-single-source.md §2): no
    # legal gate on the WHERE; balls gates on legal in its CASE below.
    clauses = [
        "d.batter_id = :pid",
        "i.super_over = 0",
    ]
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
    if scope.get("filter_opponent"):
        clauses.append(
            "(("
            "m.team1 = :opp AND i.team = m.team2)"
            " OR (m.team2 = :opp AND i.team = m.team1))"
        )
        params["opp"] = scope["filter_opponent"]
    where = " AND ".join(clauses)

    rows = await deps._db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings,
               SUM(d.runs_batter) AS runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                        THEN 1 ELSE 0 END) AS balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    sql = rows[0]
    sql_innings = sql["innings"] or 0
    sql_runs = sql["runs"] or 0
    sql_balls = sql["balls"] or 0

    lifetime = resp["lifetime"]
    results.append(check(
        f"{label} · SQL anchor n_innings",
        lifetime["n_innings"] == sql_innings,
        f"api={lifetime['n_innings']} sql={sql_innings}",
    ))
    results.append(check(
        f"{label} · SQL anchor runs.total",
        lifetime["runs"]["total"] == sql_runs,
        f"api={lifetime['runs']['total']} sql={sql_runs}",
    ))
    results.append(check(
        f"{label} · SQL anchor balls_total",
        lifetime["runs"]["balls_total"] == sql_balls,
        f"api={lifetime['runs']['balls_total']} sql={sql_balls}",
    ))

    return results


# ─── Main ───────────────────────────────────────────────────────────────

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

    for label, person_id, scope_dict in SCOPES:
        filters = make_filters(**scope_dict)
        aux = make_aux()
        resp = await batting_distribution(
            person_id=person_id,
            filters=filters,
            aux=aux,
            as_of_date=AS_OF,
        )

        all_results += assert_dossier_invariants(f"{label}/lifetime", resp["lifetime"])
        all_results += assert_dossier_invariants(f"{label}/last_10", resp["form"]["last_10"])
        all_results += assert_dossier_invariants(f"{label}/last_60d", resp["form"]["last_60d"])
        all_results += assert_dossier_invariants(f"{label}/last_6mo", resp["form"]["last_6mo"])
        all_results += assert_dossier_invariants(f"{label}/last_1yr", resp["form"]["last_1yr"])
        all_results += assert_endpoint_invariants(label, resp)
        all_results += await assert_sql_anchor(label, resp, person_id, scope_dict)

    failures = [m for ok, m in all_results if not ok]
    for ok, m in all_results:
        print(m)
    print()
    print(f"{len(all_results) - len(failures)}/{len(all_results)} pass · {len(failures)} fail")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
