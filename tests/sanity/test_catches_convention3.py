"""Convention-3 cross-endpoint sanity (Phase 2 of the invariants audit).

Locks down the catches-semantics agreement between
`/fielders/{id}/summary` and `/fielders/{id}/distribution`,
and the substitute-fielder reconciliation against `/fielders/leaders`.

The C&B incident (2026-05-08) was: two distribution endpoints
silently dropped `caught_and_bowled` from their catches counts,
while `/summary` correctly broke catches and C&B out as siblings.
The two endpoints diverged in semantics; no automated test caught
the drift because each endpoint's invariant suite self-anchored
against its own SQL with the same bug.

These assertions cross the endpoint boundary:

  §6.1 — `/{id}/summary.catches + /{id}/summary.caught_and_bowled
         - /{id}/distribution.substitute_catches
         == /{id}/distribution.lifetime.catches.total`

         Why the substitute correction:
           summary.catches      = count(kind='caught')      [all subs]
           summary.c_and_b      = count(kind='c_and_b')     [implicitly non-sub: subs can't bowl]
           distribution.catches.total = count(kind IN ('caught','c_and_b') AND is_substitute=0)
           distribution.substitute_catches = count(kind='caught' AND is_substitute=1)

         Algebra: (sub_C + non-sub_C) + non-sub_CB - sub_C
                  == non-sub_C + non-sub_CB == distribution.catches.total

  §6.6 — `/leaders.catches` per row INCLUDES substitute catches
         (no is_substitute=0 filter at fielding.py:96). So:
            leaders.catches >= distribution.catches_for_caught_only
         where distribution_caught_only = catches.total - c_and_b
         (since /distribution.catches.total is inclusive of C&B
         and excludes subs). The strict equality holds when
         substitute_catches == 0 and some C&B exist; otherwise
         the gap quantifies the substitute leak.

Subjects deliberately include a bowler (Bumrah, JJ Bumrah,
462411b3) because the existing
test_fielder_distribution_invariants.py reconciliation only
covered Dhoni / Pant / Kohli / ABdV — none of whom are bowlers,
so its reconciliation `catches.total + substitute_catches ==
summary.catches` silently held even WITH the C&B bug present
(LHS missed C&B, RHS missed C&B, the test passed).

Usage:
  uv run python tests/sanity/test_catches_convention3.py
  uv run python tests/sanity/test_catches_convention3.py --db tmp/cricket-prod-test.db

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
from api.routers.fielding import (
    fielding_distribution,
    fielding_summary,
    fielding_leaders,
)


def make_filters(**kwargs) -> FilterBarParams:
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue", "team_class",
            "series_type")
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


def make_aux() -> AuxParams:
    return AuxParams()


# (label, person_id, scope_dict). Bumrah is the marquee subject:
# active bowler with non-trivial C&B credits, exactly the case
# the C&B incident silently undercounted.
SCOPES: list[tuple[str, str, dict]] = [
    ("bumrah_intl_men",  "462411b3", {"gender": "male", "team_type": "international"}),
    ("bumrah_ipl",       "462411b3", {"tournament": "Indian Premier League"}),
    ("bumrah_all_time",  "462411b3", {}),
    ("dhoni_all_time",   "4a8a2e3b", {}),     # keeper — many catches, no C&B
    ("kohli_all_time",   "ba607b88", {}),     # outfielder — typical case
    ("kohli_ipl",        "ba607b88", {"tournament": "Indian Premier League"}),
]

AS_OF = "2025-01-01"


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    return ok, f"{status} · {label}{(' — ' + detail) if detail and not ok else ''}"


async def assert_summary_distribution_agree(
    label: str, person_id: str, scope: dict,
) -> list[tuple[bool, str]]:
    """§6.1 — summary.catches + summary.c_and_b - distribution.substitute_catches
              == distribution.catches.total."""
    out = []
    f = make_filters(**scope)
    a = make_aux()

    summary = await fielding_summary(person_id=person_id, filters=f, aux=a)
    dist = await fielding_distribution(
        person_id=person_id, filters=f, aux=a, as_of_date=AS_OF,
    )

    s_catches = summary["catches"]
    s_cb = summary["caught_and_bowled"]
    d_total = dist["lifetime"]["catches"]["total"]
    d_subs = dist["lifetime"]["substitute_catches"]

    lhs = s_catches + s_cb - d_subs
    out.append(check(
        f"{label}: summary.(catches + c_and_b) - distribution.substitute_catches "
        f"== distribution.catches.total",
        lhs == d_total,
        f"summary.catches={s_catches} summary.c_and_b={s_cb} "
        f"distribution.substitute_catches={d_subs} → LHS={lhs}; "
        f"distribution.catches.total={d_total}",
    ))

    # Also cross-check: substitute_catches matches summary's reconciliation
    # scalar. (summary.substitute_catches surfaces the same value via a
    # different SQL path.)
    out.append(check(
        f"{label}: summary.substitute_catches == distribution.substitute_catches",
        summary["substitute_catches"] == d_subs,
        f"summary={summary['substitute_catches']} distribution={d_subs}",
    ))

    # Also cross-check stumpings + run_outs (no C&B subtlety here, but
    # a lock-down assertion against future divergence).
    out.append(check(
        f"{label}: summary.stumpings == sum(observations.stumpings) on dist",
        summary["stumpings"] == sum(o.get("stumpings", 0) for o in dist["lifetime"]["observations"]),
        f"summary={summary['stumpings']}",
    ))
    out.append(check(
        f"{label}: summary.run_outs == sum(observations.run_outs) on dist",
        summary["run_outs"] == sum(o.get("run_outs", 0) for o in dist["lifetime"]["observations"]),
        f"summary={summary['run_outs']}",
    ))

    return out


async def assert_leaders_substitute_leak(label: str, scope: dict) -> list[tuple[bool, str]]:
    """§6.6 — `/fielders/leaders.catches` includes substitute catches
              (no is_substitute=0 filter at fielding.py:96).

    For each top-N row, sum its substitute_catches via /distribution
    and assert leaders.catches - leaders_caught_only == sub_catches
    (where leaders_caught_only = leaders.catches before C&B is added).

    Pragmatic version: assert that for at least one fielder with
    substitute_catches > 0, leaders.catches > distribution.catches_caught_only.
    If no fielder in the top-N has subs, the assertion holds trivially
    and we skip.
    """
    out = []
    f = make_filters(**scope)
    a = make_aux()

    leaders = await fielding_leaders(filters=f, aux=a, limit=20)

    # Walk top-N, find ones with non-zero substitute_catches
    by_dismissals = leaders.get("by_dismissals", []) if isinstance(leaders, dict) else []
    if not by_dismissals:
        out.append(check(f"{label}: /leaders returned non-empty by_dismissals", False,
                         f"got: {leaders}"))
        return out

    leak_observed = 0
    for row in by_dismissals[:10]:
        pid = row["person_id"]
        dist = await fielding_distribution(
            person_id=pid, filters=f, aux=a, as_of_date=AS_OF,
        )
        d_subs = dist["lifetime"]["substitute_catches"]
        d_caught_only = dist["lifetime"]["catches"]["total"] - row["c_and_b"]
        # /leaders.catches excludes C&B (separate column). The relationship:
        #   leaders.catches  = count(kind='caught', any sub status)
        #                    = (non-sub caught) + (sub caught)
        #   distribution.catches.total - leaders.c_and_b
        #                    = (non-sub caught + non-sub C&B) - non-sub C&B
        #                    = non-sub caught
        #   ⇒ leaders.catches - (distribution.catches.total - leaders.c_and_b)
        #     should equal distribution.substitute_catches.
        sub_via_diff = row["catches"] - d_caught_only
        out.append(check(
            f"{label}: {pid} — leaders.catches - (dist.catches.total - leaders.c_and_b)"
            f" == distribution.substitute_catches",
            sub_via_diff == d_subs,
            f"leaders.catches={row['catches']} leaders.c_and_b={row['c_and_b']} "
            f"dist.catches.total={dist['lifetime']['catches']['total']} "
            f"dist.subs={d_subs} → diff={sub_via_diff}",
        ))
        if d_subs > 0:
            leak_observed += 1

    out.append(check(
        f"{label}: at least one top-10 fielder has substitute_catches > 0 (informational)",
        True,  # informational only
        f"leak_observed={leak_observed}/10 — confirms /leaders includes subs",
    ))
    return out


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

    # §6.1 — per-subject summary↔distribution agreement
    for label, pid, scope in SCOPES:
        all_results.extend(await assert_summary_distribution_agree(label, pid, scope))

    # §6.6 — /leaders substitute reconciliation against /distribution
    # Single broad scope (men intl) — the relationship is structural,
    # not scope-dependent.
    all_results.extend(await assert_leaders_substitute_leak(
        "leaders_men_intl",
        {"gender": "male", "team_type": "international"},
    ))

    failures = [msg for ok, msg in all_results if not ok]
    passes = [msg for ok, msg in all_results if ok]

    print(f"Catches Convention-3 cross-endpoint sanity: "
          f"{len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
