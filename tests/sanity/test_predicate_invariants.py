"""Predicate invariants + variant-axis inventory (Phase 2 of the
invariants audit).

Two SQL-level sanity check classes:

  §6.4 — Dots-predicate semantic equivalence.
         Asserts the three different "dot ball" predicates used
         across api/routers/{batting,bowling}.py count exactly the
         same rows on cricket.db. The three forms:
           1. `runs_batter = 0 AND runs_extras = 0`     — batting
           2. `runs_total = 0`                           — bowling
           3. `runs_total = 0 AND extras_wides = 0
               AND extras_noballs = 0`                   — bowling /distribution
         Per the schema, runs_total = runs_batter + runs_extras
         identically (no row in the DB violates this), so all three
         predicates are guaranteed equivalent. Locking it down
         catches:
           - A future schema change introducing a runs_total field
             that doesn't sum its components.
           - A populate-script bug that breaks the invariant.
           - Anyone copy-pasting one predicate but applying it on
             data with a different schema.

  §6.5 — Variant-axis inventory.
         Counts innings with super_over=1, target_overs<20 (DLS-
         truncated chase), target_overs=20 (full T20 chase),
         declared=1, forfeited=1. Surfaces the volume so the next
         metric design can decide whether to filter or include each
         variant. Currently:
           - super_over=1 is auto-filtered everywhere via
             api/filters.py:245 (i.super_over = 0).
           - DLS-truncated innings (target_overs < 20) are NOT
             filtered or branched on anywhere — they count as full
             innings in per-innings normalisations. ~724 innings
             affected, ~5.9% of all 2nd innings.
           - declared / forfeited columns exist but no T20 row in
             the DB sets them. Reserved for future format support.

Usage:
  uv run python tests/sanity/test_predicate_invariants.py
  uv run python tests/sanity/test_predicate_invariants.py --db tmp/cricket-prod-test.db

Exits 0 on all-pass, 1 on any failure or unexpected schema state.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    return ok, f"{status} · {label}{(' — ' + detail) if detail and not ok else ''}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    results: list[tuple[bool, str]] = []

    # ─── §6.4 — Dots-predicate equivalence ────────────────────────────

    def n(sql: str) -> int:
        cur.execute(sql)
        return cur.fetchone()[0]

    n_batting_dots = n("SELECT COUNT(*) FROM delivery WHERE runs_batter = 0 AND runs_extras = 0")
    n_bowling_dots = n("SELECT COUNT(*) FROM delivery WHERE runs_total = 0")
    n_bowling_strict = n(
        "SELECT COUNT(*) FROM delivery WHERE runs_total = 0 "
        "AND extras_wides = 0 AND extras_noballs = 0"
    )

    results.append(check(
        "§6.4 batting-dots == bowling-dots (predicate equivalence)",
        n_batting_dots == n_bowling_dots,
        f"batting={n_batting_dots} bowling={n_bowling_dots}",
    ))
    results.append(check(
        "§6.4 bowling-dots == bowling-strict-dots (subset equality)",
        n_bowling_dots == n_bowling_strict,
        f"bowling={n_bowling_dots} strict={n_bowling_strict}",
    ))

    # Underlying schema invariant: runs_total = runs_batter + runs_extras
    # for every row. If this ever fails, all three predicates above
    # diverge silently.
    n_violations = n(
        "SELECT COUNT(*) FROM delivery WHERE runs_batter + runs_extras != runs_total"
    )
    results.append(check(
        "§6.4 schema invariant: runs_total == runs_batter + runs_extras (every row)",
        n_violations == 0,
        f"violations={n_violations}",
    ))

    # ─── §6.5 — Variant-axis inventory ────────────────────────────────
    # These are not pass/fail assertions in the strict sense — they
    # surface counts so we can see at a glance whether any variant
    # is non-trivial enough to warrant explicit handling. We assert:
    #   1. super_over count is small (auto-filtered).
    #   2. DLS-truncated count is non-zero AND under 10% of 2nd innings
    #      (so the audit's framing — "non-trivial but small minority"
    #      — stays accurate as the DB grows).
    #   3. declared / forfeited remain at zero (T20 doesn't use these;
    #      a non-zero count means data has changed and we need to
    #      reconsider filter coverage).

    n_innings_total = n("SELECT COUNT(*) FROM innings")
    n_super_over = n("SELECT COUNT(*) FROM innings WHERE super_over = 1")
    n_full_chase = n("SELECT COUNT(*) FROM innings WHERE target_overs = 20")
    n_dls_short = n("SELECT COUNT(*) FROM innings WHERE target_overs IS NOT NULL AND target_overs < 20")
    n_target_overs_anom = n("SELECT COUNT(*) FROM innings WHERE target_overs > 20")
    n_declared = n("SELECT COUNT(*) FROM innings WHERE declared = 1")
    n_forfeited = n("SELECT COUNT(*) FROM innings WHERE forfeited = 1")

    print(f"§6.5 innings inventory ({args.db}):")
    print(f"  total innings:                  {n_innings_total:>7,}")
    print(f"  super_over = 1:                 {n_super_over:>7,}  ({100*n_super_over/n_innings_total:.2f}%)")
    print(f"  target_overs = 20 (full chase): {n_full_chase:>7,}")
    print(f"  target_overs < 20 (DLS short):  {n_dls_short:>7,}  ({100*n_dls_short/(n_full_chase + n_dls_short):.2f}% of 2nd innings)")
    print(f"  target_overs > 20 (anomaly):    {n_target_overs_anom:>7,}")
    print(f"  declared = 1:                   {n_declared:>7,}")
    print(f"  forfeited = 1:                  {n_forfeited:>7,}")
    print()

    results.append(check(
        "§6.5 super_over rare (< 5% of innings)",
        n_super_over / max(n_innings_total, 1) < 0.05,
        f"super_over={n_super_over}/{n_innings_total}",
    ))
    results.append(check(
        "§6.5 DLS-truncated non-zero (variant exists in data)",
        n_dls_short > 0,
        f"target_overs<20: {n_dls_short}",
    ))
    results.append(check(
        "§6.5 DLS-truncated stays under 10% of 2nd innings",
        n_full_chase + n_dls_short == 0 or
        n_dls_short / (n_full_chase + n_dls_short) < 0.10,
        f"DLS={n_dls_short}/{n_full_chase + n_dls_short} "
        f"({100*n_dls_short/max(1, n_full_chase + n_dls_short):.2f}%)",
    ))
    results.append(check(
        "§6.5 target_overs > 20 NEVER (T20 schema invariant)",
        n_target_overs_anom == 0,
        f"target_overs>20: {n_target_overs_anom}",
    ))
    results.append(check(
        "§6.5 declared = 0 (T20 doesn't declare; non-zero ⇒ schema changed)",
        n_declared == 0,
        f"declared=1: {n_declared}",
    ))
    results.append(check(
        "§6.5 forfeited = 0 (T20 doesn't forfeit; non-zero ⇒ schema changed)",
        n_forfeited == 0,
        f"forfeited=1: {n_forfeited}",
    ))

    # ─── Summary ──────────────────────────────────────────────────────

    failures = [msg for ok, msg in results if not ok]
    passes = [msg for ok, msg in results if ok]

    print(f"Predicate invariants + variant inventory: "
          f"{len(passes)} pass, {len(failures)} fail")
    for msg in failures:
        print(f"  {msg}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
