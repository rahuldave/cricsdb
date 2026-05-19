"""Sanity: /scope/averages/players/fielding/summary correctness.

Invariants:
  1. Outfielder cohort (is_keeper=0) has stumpings_per_match = 0 —
     outfielders can't stump, and the per-(person, scope) keeper-
     flag JOIN ensures no leak from a player's keeper-season data.
  2. Pool conservation — cohort.n_matches_total matches SQL.
  3. drop= invariant.
  4. Keeper cohort has higher stumpings + catches per match than
     outfielder cohort.

Spec: spec-player-compare-average.md §5.4 — fielding is NOT
position-weighted at the headline; cohort partitions on is_keeper
flag instead.

Usage:
  uv run python tests/sanity/test_scope_averages_players_fielding.py
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")
DEFAULT_HOST = "http://localhost:8000"


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: /scope/averages/players/fielding/summary ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    outfielders = get(
        args.host, "/api/v1/scope/averages/players/fielding/summary",
        tournament="Indian Premier League", is_keeper=0,
    )
    keepers = get(
        args.host, "/api/v1/scope/averages/players/fielding/summary",
        tournament="Indian Premier League", is_keeper=1,
    )

    # 1. Outfielders never stump.
    print("\n  1. Outfielder cohort never stumps:")
    ok = (outfielders["stumpings_per_match"]["scope_avg"] or 0) == 0.0
    _, line = check(
        "is_keeper=0 → stumpings_per_match == 0",
        ok,
        f"got {outfielders['stumpings_per_match']['scope_avg']}",
    )
    print(line); all_passed &= ok

    # 2. Pool conservation: cohort.n_matches_total matches SQL.
    print("\n  2. Pool conservation (n_matches_total vs SQL):")
    sql_out = conn.execute("""
        SELECT SUM(matches) FROM playerscopestats
        WHERE tournament = 'Indian Premier League' AND matches_as_keeper = 0
    """).fetchone()[0]
    sql_kp = conn.execute("""
        SELECT SUM(matches) FROM playerscopestats
        WHERE tournament = 'Indian Premier League' AND matches_as_keeper > 0
    """).fetchone()[0]
    ok = outfielders["cohort"]["n_matches_total"] == sql_out
    _, line = check(
        "outfielder cohort.n_matches_total matches SQL",
        ok,
        f"endpoint={outfielders['cohort']['n_matches_total']}, sql={sql_out}",
    )
    print(line); all_passed &= ok

    ok = keepers["cohort"]["n_matches_total"] == sql_kp
    _, line = check(
        "keeper cohort.n_matches_total matches SQL",
        ok,
        f"endpoint={keepers['cohort']['n_matches_total']}, sql={sql_kp}",
    )
    print(line); all_passed &= ok

    # 3. drop= invariant.
    print("\n  3. drop= invariant:")
    out_drop = get(
        args.host, "/api/v1/scope/averages/players/fielding/summary",
        tournament="Indian Premier League", is_keeper=0,
        drop="filter_team",
    )
    ok = out_drop["catches_per_match"]["scope_avg"] == outfielders["catches_per_match"]["scope_avg"]
    _, line = check(
        "drop=filter_team is no-op (not in scope-key axes)",
        ok,
    )
    print(line); all_passed &= ok

    out_drop_t = get(
        args.host, "/api/v1/scope/averages/players/fielding/summary",
        tournament="Indian Premier League", is_keeper=0,
        drop="tournament",
    )
    ok = out_drop_t["cohort"]["n_matches_total"] > outfielders["cohort"]["n_matches_total"]
    _, line = check(
        "drop=tournament widens cohort",
        ok,
        f"with_t={outfielders['cohort']['n_matches_total']}, drop_t={out_drop_t['cohort']['n_matches_total']}",
    )
    print(line); all_passed &= ok

    # 4. Keepers dominate outfielders on dismissals/match.
    print("\n  4. Keeper cohort has higher dismissals/match than outfielders:")
    kp = keepers["dismissals_per_match"]["scope_avg"]
    of = outfielders["dismissals_per_match"]["scope_avg"]
    ok = kp is not None and of is not None and kp > of
    _, line = check(
        "keeper.dismissals_per_match > outfielder.dismissals_per_match",
        ok,
        f"keeper={kp}, outfielder={of}",
    )
    print(line); all_passed &= ok

    # 5. by_dismissed_position[10] always returned.
    ok = len(outfielders["by_dismissed_position"]) == 10
    _, line = check(
        "by_dismissed_position always length 10",
        ok,
        f"length={len(outfielders['by_dismissed_position'])}",
    )
    print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
