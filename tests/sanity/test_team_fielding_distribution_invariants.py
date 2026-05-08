"""Invariants for /api/v1/teams/{team}/fielding/distribution.

Calls the endpoint function in-process across several scope
combinations and asserts the spec §16.6 invariants hold. Per
CLAUDE.md "integration tests must self-anchor against SQL", every
numeric expected value derives from sqlite3 against `cricket.db`
at runtime — no hardcoded literals.

Invariants (spec internal_docs/spec-distribution-stats.md §16.6):

  1. n_innings_fielded == len(observations) on lifetime + each form window.
  2. last_10.n_innings_fielded ≤ 10; last_10.observations is the
     contiguous date-asc tail of lifetime.observations.
  3. catches.total / run_outs.total / stumpings.total each ==
     sum of per-innings observations exactly.
  4. wickets_total scalar == sum(o.wickets_total) exact.
  5. substitute_catches scalar == sum(o.substitute_catches) exact.
  6. {block}.mean_per_innings × n ≈ {block}.total per block (4dp tol).
  7. For every milestone: value × denom ≈ num; ci_low ≤ value ≤
     ci_high; 0 ≤ ci_low; ci_high ≤ 1.
  8. Catches subset monotonicity — count(c ≥ k) ≤ count(c ≥ k−1)
     for k = 1..max.
  9. Run-outs / Stumpings 3-simple partition: p_eq_0.num + p_eq_1.num
     + p_geq_2.num == n; all three denoms == n.
 10. Stumpings block ALWAYS shipped (never None), unlike player-fielder
     §13 — verified at every scope.
 11. last_match_date on lifetime equals max observation date.
 12. SQL anchor — lifetime n_innings_fielded, catches/run_outs/
     stumpings totals, wickets_total, substitute_catches match a
     direct sqlite3 query for the same scope.
 13. Form delta has exactly 12 entries (4 windows × 3 metrics).

Usage:
  uv run python tests/sanity/test_team_fielding_distribution_invariants.py
  uv run python tests/sanity/test_team_fielding_distribution_invariants.py --db tmp/cricket.db

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
from api.routers.teams import team_fielding_distribution


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
                     set(pr.keys()) == keys))

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
                     pr["ci_low"] >= 0))
    out.append(check(f"{label}: ci_high ≤ 1",
                     pr["ci_high"] <= 1.0001))
    out.append(check(f"{label}: ci_low ≤ value ≤ ci_high",
                     pr["ci_low"] - 0.0001 <= pr["value"] <= pr["ci_high"] + 0.0001))
    return out


def _assert_count_block(
    label: str, block: dict, vals: list[int], n: int,
    expected_milestone_keys: set[str],
) -> list[tuple[bool, str]]:
    """Generic per-block invariants — total, mean × n, prob records."""
    out = []
    total = sum(vals)
    out.append(check(f"{label}: total == sum(o)",
                     block["total"] == total,
                     f"got={block['total']}, sum={total}"))

    out.append(check(f"{label}: milestone keys match",
                     set(block["milestones"].keys()) == expected_milestone_keys,
                     f"got={set(block['milestones'].keys())}, exp={expected_milestone_keys}"))

    if n > 0:
        mean_tol = max(0.02, n * 5e-5)
        out.append(check(f"{label}: mean × n ≈ total",
                         _approx(block["mean_per_innings"] * n, total, eps=mean_tol),
                         f"mean={block['mean_per_innings']}, n={n}, total={total}"))

    for key, pr in block["milestones"].items():
        out.extend(assert_prob_record(f"{label}.{key}", pr))

    return out


def assert_dossier_invariants(label: str, doss: dict) -> list[tuple[bool, str]]:
    out = []
    n = doss["n_innings_fielded"]
    obs = doss["observations"]

    # Inv 1
    out.append(check(f"{label}: n_innings_fielded == len(observations)",
                     n == len(obs),
                     f"n={n}, len(obs)={len(obs)}"))

    # Inv 10: stumpings block ALWAYS shipped (never None)
    out.append(check(f"{label}: stumpings block is dict (never None)",
                     isinstance(doss["stumpings"], dict),
                     f"got type={type(doss['stumpings']).__name__}"))

    if n == 0:
        out.append(check(f"{label}: empty catches.total == 0",
                         doss["catches"]["total"] == 0))
        out.append(check(f"{label}: empty stumpings.total == 0",
                         doss["stumpings"]["total"] == 0))
        out.append(check(f"{label}: empty wickets_total == 0",
                         doss["wickets_total"] == 0))
        return out

    # Inv 4 + 5: top-level scalars
    expected_wkts = sum(o["wickets_total"] for o in obs)
    expected_subs = sum(o["substitute_catches"] for o in obs)
    out.append(check(f"{label}: wickets_total == sum(o.wickets_total)",
                     doss["wickets_total"] == expected_wkts,
                     f"got={doss['wickets_total']}, exp={expected_wkts}"))
    out.append(check(f"{label}: substitute_catches == sum(o.subs)",
                     doss["substitute_catches"] == expected_subs,
                     f"got={doss['substitute_catches']}, exp={expected_subs}"))

    # ── catches block (4 milestones, no ladder) ───────────────────
    catches_vals = [o["catches"] for o in obs]
    out.extend(_assert_count_block(
        f"{label}: catches", doss["catches"], catches_vals, n,
        {"p_eq_0", "p_geq_3", "p_geq_5", "p_geq_7"},
    ))

    # Catches simples num check
    ms_c = doss["catches"]["milestones"]
    out.append(check(f"{label}: catches.p_eq_0.num == count(c==0)",
                     ms_c["p_eq_0"]["num"] == sum(1 for x in catches_vals if x == 0)))
    for thresh in (3, 5, 7):
        out.append(check(f"{label}: catches.p_geq_{thresh}.num == count(c≥{thresh})",
                         ms_c[f"p_geq_{thresh}"]["num"] == sum(1 for x in catches_vals if x >= thresh)))
    # Simples denom == n
    for key in ("p_eq_0", "p_geq_3", "p_geq_5", "p_geq_7"):
        out.append(check(f"{label}: catches.{key}.denom == n",
                         ms_c[key]["denom"] == n))

    # Inv 8: catches subset monotonicity (k=1..max)
    if catches_vals:
        max_c = max(catches_vals)
        for k in range(1, max_c + 1):
            ck = sum(1 for x in catches_vals if x >= k)
            ck_prev = sum(1 for x in catches_vals if x >= k - 1)
            out.append(check(f"{label}: count(c≥{k}) ≤ count(c≥{k-1})",
                             ck <= ck_prev))

    # ── run_outs block (3-simple partition) ───────────────────────
    ro_vals = [o["run_outs"] for o in obs]
    out.extend(_assert_count_block(
        f"{label}: run_outs", doss["run_outs"], ro_vals, n,
        {"p_eq_0", "p_eq_1", "p_geq_2"},
    ))

    # Inv 9: 3-simple partition
    ms_ro = doss["run_outs"]["milestones"]
    sum_ro_nums = ms_ro["p_eq_0"]["num"] + ms_ro["p_eq_1"]["num"] + ms_ro["p_geq_2"]["num"]
    out.append(check(f"{label}: run_outs partition num sum == n",
                     sum_ro_nums == n,
                     f"sum={sum_ro_nums}, n={n}"))
    for key in ("p_eq_0", "p_eq_1", "p_geq_2"):
        out.append(check(f"{label}: run_outs.{key}.denom == n",
                         ms_ro[key]["denom"] == n))
    # Verify per-simple num against vals
    out.append(check(f"{label}: run_outs.p_eq_0.num matches",
                     ms_ro["p_eq_0"]["num"] == sum(1 for x in ro_vals if x == 0)))
    out.append(check(f"{label}: run_outs.p_eq_1.num matches",
                     ms_ro["p_eq_1"]["num"] == sum(1 for x in ro_vals if x == 1)))
    out.append(check(f"{label}: run_outs.p_geq_2.num matches",
                     ms_ro["p_geq_2"]["num"] == sum(1 for x in ro_vals if x >= 2)))

    # ── stumpings block (3-simple partition, always shipped) ──────
    st_vals = [o["stumpings"] for o in obs]
    out.extend(_assert_count_block(
        f"{label}: stumpings", doss["stumpings"], st_vals, n,
        {"p_eq_0", "p_eq_1", "p_geq_2"},
    ))

    ms_st = doss["stumpings"]["milestones"]
    sum_st_nums = ms_st["p_eq_0"]["num"] + ms_st["p_eq_1"]["num"] + ms_st["p_geq_2"]["num"]
    out.append(check(f"{label}: stumpings partition num sum == n",
                     sum_st_nums == n,
                     f"sum={sum_st_nums}, n={n}"))
    for key in ("p_eq_0", "p_eq_1", "p_geq_2"):
        out.append(check(f"{label}: stumpings.{key}.denom == n",
                         ms_st[key]["denom"] == n))

    return out


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    out = []
    out.extend(assert_dossier_invariants(f"{label}.lifetime", resp["lifetime"]))
    for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        out.extend(assert_dossier_invariants(f"{label}.form.{w}", resp["form"][w]))

    # Inv 11
    lifetime_obs = resp["lifetime"]["observations"]
    obs_dates = [o["date"] for o in lifetime_obs if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    out.append(check(
        f"{label}: lifetime.last_match_date == max(observations.date)",
        resp["lifetime"].get("last_match_date") == expected_lmd,
    ))

    # Inv 2
    last_10_obs = resp["form"]["last_10"]["observations"]
    out.append(check(f"{label}: last_10.n_innings_fielded ≤ 10",
                     resp["form"]["last_10"]["n_innings_fielded"] <= 10))
    out.append(check(f"{label}: last_10 is contiguous tail",
                     last_10_obs == lifetime_obs[-len(last_10_obs):] if last_10_obs else True))

    # Inv 13
    delta = resp["form"]["delta"]
    out.append(check(f"{label}: delta has 12 entries",
                     len(delta) == 12,
                     f"got {len(delta)}: {sorted(delta.keys())}"))

    # Form delta consistency for one metric
    for metric in ("catches", "run_outs", "stumpings"):
        lt_mean = resp["lifetime"][metric]["mean_per_innings"]
        l10_mean = resp["form"]["last_10"][metric]["mean_per_innings"]
        if lt_mean is not None and l10_mean is not None:
            expected = round(l10_mean - lt_mean, 4)
            out.append(check(f"{label}: delta.last_10_{metric}_mean",
                             _approx(delta[f"last_10_{metric}_mean_minus_lifetime"], expected, eps=0.01)))

    return out


async def assert_sql_anchor(
    label: str, resp: dict, team: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 12 — lifetime totals match direct SQL aggregation against
    the OPP's batting innings (i.team != team AND match has team).
    Catches/run_outs/stumpings filtered by team's matchplayers.
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

    # n_innings_fielded
    rows = await deps._db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS n
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    sql_n = rows[0]["n"] if rows else 0

    # Catches / run_outs / stumpings totals
    fc_filters: dict[str, str] = {
        "catches":   "fc.kind = 'caught' AND COALESCE(fc.is_substitute,0) = 0",
        "run_outs":  "fc.kind = 'run_out' AND COALESCE(fc.is_substitute,0) = 0",
        "stumpings": "fc.kind = 'stumped'",
    }
    sql_totals = {}
    for k, fc_filter in fc_filters.items():
        rows = await deps._db.q(
            f"""
            SELECT COUNT(*) AS total
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND {fc_filter}
              AND fc.fielder_id IN
                (SELECT mp.person_id FROM matchplayer mp
                 WHERE mp.match_id = i.match_id AND mp.team = :team)
            """,
            params,
        )
        sql_totals[k] = rows[0]["total"] if rows else 0

    # Substitute catches (no matchplayer constraint)
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS total
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND fc.kind = 'caught' AND fc.is_substitute = 1
        """,
        params,
    )
    sql_subs = rows[0]["total"] if rows else 0

    # Wickets_total (any kind)
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS total
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    sql_wkts = rows[0]["total"] if rows else 0

    lifetime = resp["lifetime"]
    out.append(check(f"{label}: SQL anchor n_innings_fielded",
                     lifetime["n_innings_fielded"] == sql_n,
                     f"api={lifetime['n_innings_fielded']}, sql={sql_n}"))
    out.append(check(f"{label}: SQL anchor catches.total",
                     lifetime["catches"]["total"] == sql_totals["catches"],
                     f"api={lifetime['catches']['total']}, sql={sql_totals['catches']}"))
    out.append(check(f"{label}: SQL anchor run_outs.total",
                     lifetime["run_outs"]["total"] == sql_totals["run_outs"],
                     f"api={lifetime['run_outs']['total']}, sql={sql_totals['run_outs']}"))
    out.append(check(f"{label}: SQL anchor stumpings.total",
                     lifetime["stumpings"]["total"] == sql_totals["stumpings"],
                     f"api={lifetime['stumpings']['total']}, sql={sql_totals['stumpings']}"))
    out.append(check(f"{label}: SQL anchor substitute_catches",
                     lifetime["substitute_catches"] == sql_subs,
                     f"api={lifetime['substitute_catches']}, sql={sql_subs}"))
    out.append(check(f"{label}: SQL anchor wickets_total",
                     lifetime["wickets_total"] == sql_wkts,
                     f"api={lifetime['wickets_total']}, sql={sql_wkts}"))

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
        resp = await team_fielding_distribution(
            team=team, filters=filters, aux=aux, as_of_date=AS_OF,
        )

        all_results.extend(assert_endpoint_invariants(label, resp))
        all_results.extend(await assert_sql_anchor(label, resp, team, scope_dict))

    # Empty-scope edge case
    empty_filters = make_filters(filter_venue="Nonexistent Stadium XYZ")
    resp = await team_fielding_distribution(
        team="Mumbai Indians", filters=empty_filters, aux=make_aux(),
        as_of_date=AS_OF,
    )
    all_results.append(check(
        "empty_scope: lifetime.n_innings_fielded == 0",
        resp["lifetime"]["n_innings_fielded"] == 0,
    ))
    all_results.append(check(
        "empty_scope: stumpings block still shipped",
        isinstance(resp["lifetime"]["stumpings"], dict),
    ))
    all_results.append(check(
        "empty_scope: wickets_total == 0",
        resp["lifetime"]["wickets_total"] == 0,
    ))
    all_results.append(check(
        "empty_scope: substitute_catches == 0",
        resp["lifetime"]["substitute_catches"] == 0,
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: catches.p_eq_0",
        resp["lifetime"]["catches"]["milestones"]["p_eq_0"],
    ))
    all_results.extend(assert_prob_record(
        "empty_scope: stumpings.p_geq_2",
        resp["lifetime"]["stumpings"]["milestones"]["p_geq_2"],
    ))
    all_results.append(check(
        "empty_scope: lifetime.last_match_date is None",
        resp["lifetime"]["last_match_date"] is None,
    ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Team-fielding distribution sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
