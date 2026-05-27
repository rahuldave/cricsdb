"""Invariants for /api/v1/fielders/{id}/distribution.

Calls the endpoint function in-process across several scope
combinations and asserts the spec §13.8 invariants hold. Per
CLAUDE.md "integration tests must self-anchor against SQL", every
numeric expected value derives from sqlite3 against `cricket.db`
at runtime — no hardcoded literals.

Invariants (spec internal_docs/spec-distribution-stats.md §13.8):

  1. n_matches == len(observations) on lifetime + each form window.
  2. last_10.n_matches ≤ 10; last_10.observations is the contiguous
     date-asc tail of lifetime.observations.
  3. Three-simples-sum-to-1 invariant — for each block,
     p_zero.value + p_one.value + p_geq_2.value == 1.0.
  4. catches.total == sum(o.catches for o in observations).
     Same for run_outs and stumpings.
  5. mean_per_match × n_matches ≈ total per block.
  6. stumpings is null ⟺ innings_kept == 0. Both sides tested.
  7. Substitute reconciliation — catches.total + substitute_catches ==
     /fielders/{id}/summary.catches for the same scope.
  8. For every milestone field: value × denom ≈ num; ci_low ≤ value
     ≤ ci_high; 0 ≤ ci_low; ci_high ≤ 1.
  9. SQL anchor — lifetime n_matches, catches.total, stumpings.total
     match a direct sqlite3 query for the same scope.
 10. Form-window monotonicity: last_10.n_matches ≤ 10.

Usage:
  uv run python tests/sanity/test_fielder_distribution_invariants.py
  uv run python tests/sanity/test_fielder_distribution_invariants.py --db tmp/cricket.db

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
from api.routers.fielding import fielding_distribution, fielding_summary


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


# (label, person_id, filter dict). IDs from `person` table:
#   Dhoni: 4a8a2e3b — keeper, IPL + India career.
#   Pant: 919a3be2 — keeper, fewer matches.
#   Kohli: ba607b88 — non-keeper outfielder.
#   AB de Villiers: c4487b84 — has both keeper and non-keeper innings;
#     stresses the iff(stumpings, innings_kept>0) invariant.
SCOPES: list[tuple[str, str, dict]] = [
    ("dhoni_all_time",   "4a8a2e3b", {}),
    ("dhoni_ipl",        "4a8a2e3b", {"tournament": "Indian Premier League"}),
    ("kohli_all_time",   "ba607b88", {}),
    ("pant_all_time",    "919a3be2", {}),
    ("abdv_all_time",    "c4487b84", {}),
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
                     keys.issubset(set(pr.keys())),
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


def assert_count_block(label: str, block: dict, key: str, observations: list[dict]) -> list[tuple[bool, str]]:
    """Validate a count block (catches / run_outs / stumpings)."""
    out = []
    n = len(observations)
    vals = [o[key] for o in observations]

    # Inv 4: total == sum
    out.append(check(f"{label}.{key}: total == sum(observations)",
                     block["total"] == sum(vals),
                     f"total={block['total']}, sum={sum(vals)}"))

    if n == 0:
        return out

    # Inv 5: mean × n ≈ total. Mean is rounded to 4dp; worst-case
    # roundoff scales with n.
    rnd_tol = max(0.01, n * 5e-5)
    out.append(check(f"{label}.{key}: mean × n ≈ total",
                     _approx(block["mean_per_match"] * n, block["total"], eps=rnd_tol),
                     f"mean={block['mean_per_match']}, n={n}, total={block['total']}"))

    # Three milestone simples
    ms = block["milestones"]
    keys_expected = {"p_zero", "p_one", "p_geq_2"}
    out.append(check(f"{label}.{key}: milestone keys",
                     set(ms.keys()) == keys_expected,
                     f"got {set(ms.keys())}"))

    # Validate each prob_record
    for k, pr in ms.items():
        out.extend(assert_prob_record(f"{label}.{key}.{k}", pr))

    # Inv 3: simples sum to 1
    if ms["p_zero"]["value"] is not None:
        s = (ms["p_zero"]["value"] + ms["p_one"]["value"]
             + ms["p_geq_2"]["value"])
        out.append(check(f"{label}.{key}: p_zero + p_one + p_geq_2 ≈ 1",
                         _approx(s, 1.0, eps=0.001),
                         f"sum={s}"))

    # Simples num check (denom = n_matches)
    out.append(check(f"{label}.{key}: p_zero.num == count(==0)",
                     ms["p_zero"]["num"] == sum(1 for v in vals if v == 0)))
    out.append(check(f"{label}.{key}: p_one.num == count(==1)",
                     ms["p_one"]["num"] == sum(1 for v in vals if v == 1)))
    out.append(check(f"{label}.{key}: p_geq_2.num == count(>=2)",
                     ms["p_geq_2"]["num"] == sum(1 for v in vals if v >= 2)))
    out.append(check(f"{label}.{key}: simples denom == n_matches",
                     all(ms[k]["denom"] == n for k in keys_expected)))

    return out


def assert_dossier_invariants(label: str, doss: dict) -> list[tuple[bool, str]]:
    out = []
    n = doss["n_matches"]
    obs = doss["observations"]

    # Inv 1: n_matches == len(observations)
    out.append(check(f"{label}: n_matches == len(observations)",
                     n == len(obs),
                     f"n={n}, len(obs)={len(obs)}"))

    # Inv 6: stumpings is null ⟺ innings_kept == 0
    innings_kept = doss["innings_kept"]
    if innings_kept == 0:
        out.append(check(f"{label}: innings_kept=0 → stumpings is None",
                         doss["stumpings"] is None,
                         f"got {type(doss['stumpings']).__name__}"))
    else:
        out.append(check(f"{label}: innings_kept>0 → stumpings is dict",
                         isinstance(doss["stumpings"], dict),
                         f"got {type(doss['stumpings']).__name__}"))

    if n == 0:
        out.append(check(f"{label}: empty catches.total == 0",
                         doss["catches"]["total"] == 0))
        return out

    # Inv 4: per-block total checks
    out.extend(assert_count_block(label, doss["catches"], "catches", obs))
    out.extend(assert_count_block(label, doss["run_outs"], "run_outs", obs))
    if doss["stumpings"] is not None:
        out.extend(assert_count_block(label, doss["stumpings"], "stumpings", obs))

    return out


def assert_endpoint_invariants(label: str, resp: dict) -> list[tuple[bool, str]]:
    out = []
    out.extend(assert_dossier_invariants(f"{label}.lifetime", resp["lifetime"]))
    for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        out.extend(assert_dossier_invariants(f"{label}.form.{w}", resp["form"][w]))

    # last_match_date — present on lifetime; equals max obs date.
    # Drives the frontend dormancy badge. Spec §13 +
    # internal_docs/design-decisions.md "Dormancy badge".
    lifetime_obs = resp["lifetime"]["observations"]
    obs_dates = [o["date"] for o in lifetime_obs if o.get("date")]
    expected_lmd = max(obs_dates) if obs_dates else None
    out.append(check(
        f"{label}: lifetime.last_match_date == max(observations.date)",
        resp["lifetime"].get("last_match_date") == expected_lmd,
        f"got={resp['lifetime'].get('last_match_date')}, expected={expected_lmd}",
    ))

    # Inv 2 + 10: last_10 is the date-asc tail, n_matches ≤ 10
    lifetime_obs = resp["lifetime"]["observations"]
    last_10_obs = resp["form"]["last_10"]["observations"]
    out.append(check(f"{label}: last_10.n_matches ≤ 10",
                     resp["form"]["last_10"]["n_matches"] <= 10))
    out.append(check(f"{label}: last_10 is contiguous tail",
                     last_10_obs == lifetime_obs[-len(last_10_obs):] if last_10_obs else True))

    # Form delta consistency — catches mean
    delta = resp["form"]["delta"]
    lifetime_c_mean = resp["lifetime"]["catches"]["mean_per_match"]
    last_10_c_mean = resp["form"]["last_10"]["catches"]["mean_per_match"]
    if lifetime_c_mean is not None and last_10_c_mean is not None:
        expected = round(last_10_c_mean - lifetime_c_mean, 4)
        out.append(check(f"{label}: delta.last_10_catches",
                         _approx(delta["last_10_catches_mean_minus_lifetime"], expected, eps=0.01),
                         f"got={delta['last_10_catches_mean_minus_lifetime']}, exp={expected}"))

    # Stumpings delta is null when lifetime stumpings is null
    if resp["lifetime"]["stumpings"] is None:
        for w in ("last_10", "last_60d", "last_6mo", "last_1yr"):
            key = f"{w}_stumpings_mean_minus_lifetime"
            out.append(check(f"{label}: delta.{key} is None (non-keeper)",
                             delta[key] is None,
                             f"got {delta[key]}"))

    return out


async def assert_sql_anchor(
    label: str, resp: dict, person_id: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 9 — lifetime totals match direct SQL aggregation."""
    out = []

    # Build match-level scope clause matching what build_side_neutral
    # would produce for the active filter axes.
    match_clauses = []
    params: dict = {"pid": person_id}
    if scope.get("tournament"):
        match_clauses.append("m.event_name = :tournament")
        params["tournament"] = scope["tournament"]
    if scope.get("season_from"):
        match_clauses.append("m.season >= :sf")
        params["sf"] = scope["season_from"]
    if scope.get("season_to"):
        match_clauses.append("m.season <= :st")
        params["st"] = scope["season_to"]
    match_where = " AND ".join(match_clauses) if match_clauses else "1=1"

    # n_matches: distinct matches the player was in, in scope
    rows = await deps._db.q(
        f"""
        SELECT COUNT(DISTINCT mp.match_id) AS n
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE mp.person_id = :pid AND {match_where}
        """,
        params,
    )
    sql_n_matches = rows[0]["n"] if rows else 0

    # Catches: non-substitute, scope-bound. Convention 3 — caught-and-
    # bowled is folded into catches (2026-05-08 fix; predicate matches
    # the endpoint at api/routers/fielding.py).
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS c
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = :pid
          AND fc.kind IN ('caught', 'caught_and_bowled')
          AND COALESCE(fc.is_substitute, 0) = 0
          AND {match_where}
        """,
        params,
    )
    sql_catches = rows[0]["c"] if rows else 0

    # Substitute catches
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS c
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = :pid
          AND fc.kind = 'caught'
          AND fc.is_substitute = 1
          AND {match_where}
        """,
        params,
    )
    sql_subs = rows[0]["c"] if rows else 0

    # Stumpings
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS c
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = :pid
          AND fc.kind = 'stumped'
          AND {match_where}
        """,
        params,
    )
    sql_stumpings = rows[0]["c"] if rows else 0

    # Innings kept
    rows = await deps._db.q(
        f"""
        SELECT COUNT(*) AS c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE ka.keeper_id = :pid AND {match_where}
        """,
        params,
    )
    sql_innings_kept = rows[0]["c"] if rows else 0

    lifetime = resp["lifetime"]
    out.append(check(f"{label}: SQL anchor n_matches",
                     lifetime["n_matches"] == sql_n_matches,
                     f"api={lifetime['n_matches']}, sql={sql_n_matches}"))
    out.append(check(f"{label}: SQL anchor catches.total",
                     lifetime["catches"]["total"] == sql_catches,
                     f"api={lifetime['catches']['total']}, sql={sql_catches}"))
    out.append(check(f"{label}: SQL anchor substitute_catches",
                     lifetime["substitute_catches"] == sql_subs,
                     f"api={lifetime['substitute_catches']}, sql={sql_subs}"))
    out.append(check(f"{label}: SQL anchor innings_kept",
                     lifetime["innings_kept"] == sql_innings_kept,
                     f"api={lifetime['innings_kept']}, sql={sql_innings_kept}"))
    if lifetime["stumpings"] is not None:
        out.append(check(f"{label}: SQL anchor stumpings.total",
                         lifetime["stumpings"]["total"] == sql_stumpings,
                         f"api={lifetime['stumpings']['total']}, sql={sql_stumpings}"))

    return out


async def assert_substitute_reconciliation(
    label: str, resp: dict, person_id: str, scope: dict,
) -> list[tuple[bool, str]]:
    """Inv 7 — catches.total + substitute_catches == /fielders/{id}/summary.catches"""
    out = []
    f = make_filters(**scope)
    a = make_aux()
    summary = await fielding_summary(person_id=person_id, filters=f, aux=a)

    api_catches = resp["lifetime"]["catches"]["total"]
    api_subs = resp["lifetime"]["substitute_catches"]
    # /summary.catches is a MetricEnvelope dict since the Phase-4 migration.
    sc = summary["catches"]
    summary_catches = sc["value"] if isinstance(sc, dict) else sc

    out.append(check(
        f"{label}: catches.total + substitute_catches == summary.catches",
        api_catches + api_subs == summary_catches,
        f"distribution={api_catches}+{api_subs}, summary={summary_catches}",
    ))
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
        resp = await fielding_distribution(
            person_id=pid, filters=filters, aux=aux,
            as_of_date=AS_OF,
        )

        all_results.extend(assert_endpoint_invariants(label, resp))
        all_results.extend(await assert_sql_anchor(label, resp, pid, scope_dict))
        all_results.extend(await assert_substitute_reconciliation(label, resp, pid, scope_dict))

    # Empty-scope edge case
    pid = "4a8a2e3b"  # Dhoni
    empty_filters = make_filters(filter_venue="Nonexistent Stadium XYZ")
    resp = await fielding_distribution(
        person_id=pid, filters=empty_filters, aux=make_aux(),
        as_of_date=AS_OF,
    )
    all_results.append(check(
        "empty_scope: lifetime.n_matches == 0",
        resp["lifetime"]["n_matches"] == 0,
    ))
    all_results.append(check(
        "empty_scope: catches.total == 0",
        resp["lifetime"]["catches"]["total"] == 0,
    ))
    all_results.append(check(
        "empty_scope: stumpings is None",
        resp["lifetime"]["stumpings"] is None,
    ))
    # Probability records on empty sample
    all_results.extend(assert_prob_record(
        "empty_scope: catches.p_zero",
        resp["lifetime"]["catches"]["milestones"]["p_zero"],
    ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Fielder distribution sanity: {len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
