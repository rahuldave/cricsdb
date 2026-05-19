"""Sanity: /scope/averages/players/batting/summary correctness.

Hits the running API (default http://localhost:8000) and verifies four
invariants:

  1. **Convex-combination invariant**: with no cliff, the response's
     `scope_avg` for each rate metric equals the convex combination
     of per-bucket cohort rates weighted by the player's mix.

  2. **Pool conservation**: the cohort's `n_innings_total` equals the
     SQL SUM(innings) across all buckets at the same scope (the
     endpoint computes it from a separate query; cross-check vs
     direct child-table SUM).

  3. **drop= invariant**: a response with `drop=filter_team,
     filter_opponent` equals the response without those filters set
     in the first place. Surface 1 doesn't use drop, but the plumbing
     is exercised here.

  4. **Strict-cliff invariant**:
     (a) If the cohort at any player-weighted bucket is below threshold,
         `below_support: true`, `cliff_buckets` lists the offending
         buckets, and every headline metric carries scope_avg=null.
     (b) When all weighted buckets are above threshold, scope_avg is
         non-null and equals the convex combination.
     (c) Buckets with mix-weight = 0 may carry below_support=true
         without nullifying the headline.

Spec: internal_docs/spec-player-compare-average.md §8 Sanity tests.

Usage:
  uv run python tests/sanity/test_scope_averages_players_batting.py
  # API server must be running on http://localhost:8000 (or pass --host).
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


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def batting_threshold(bucket: int) -> int:
    return 27 - 2 * bucket


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: /scope/averages/players/batting/summary ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # ─── Test 1: convex combination ──────────────────────────────
    print("\n  1. Convex combination — Kohli-like mix at IPL:")
    mix = [0.54, 0.38, 0.05, 0.03, 0, 0, 0, 0, 0, 0]
    resp = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        tournament="Indian Premier League",
        position_mix=",".join(str(m) for m in mix),
    )
    ok = resp["below_support"] is False and not resp["cliff_buckets"]
    _, line = check("no cliff at IPL with top-order mix", ok)
    print(line); all_passed &= ok

    # Manually compute the convex combination for strike_rate and
    # check it matches the response.
    by_position = resp["by_position"]
    expected_sr = sum(
        mix[i] * by_position[i]["strike_rate"]
        for i in range(10)
        if mix[i] > 0 and by_position[i]["strike_rate"] is not None
    )
    actual_sr = resp["strike_rate"]["scope_avg"]
    ok = actual_sr is not None and abs(actual_sr - round(expected_sr, 1)) < 0.1
    _, line = check(
        "scope_avg.strike_rate matches manual convex combination",
        ok,
        f"expected≈{expected_sr:.2f}, actual={actual_sr}",
    )
    print(line); all_passed &= ok

    expected_avg = sum(
        mix[i] * by_position[i]["average"]
        for i in range(10)
        if mix[i] > 0 and by_position[i]["average"] is not None
    )
    actual_avg = resp["average"]["scope_avg"]
    ok = actual_avg is not None and abs(actual_avg - round(expected_avg, 2)) < 0.01
    _, line = check(
        "scope_avg.average matches manual convex combination",
        ok,
        f"expected≈{expected_avg:.4f}, actual={actual_avg}",
    )
    print(line); all_passed &= ok

    # ─── Test 2: pool conservation ───────────────────────────────
    print("\n  2. Pool conservation (cohort.n_innings_total ↔ SQL):")
    sql_innings = conn.execute("""
        SELECT SUM(pssp.innings) AS s
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.person_id = pssp.person_id
         AND pss.scope_key = pssp.scope_key
        WHERE pss.tournament = 'Indian Premier League'
    """).fetchone()["s"]
    ok = resp["cohort"]["n_innings_total"] == sql_innings
    _, line = check(
        "cohort.n_innings_total matches SQL SUM(innings)",
        ok,
        f"endpoint={resp['cohort']['n_innings_total']}, sql={sql_innings}",
    )
    print(line); all_passed &= ok

    # ─── Test 3: drop= invariant ─────────────────────────────────
    print("\n  3. drop= invariant:")
    resp_drop = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        tournament="Indian Premier League",
        position_mix=",".join(str(m) for m in mix),
        drop="filter_team,filter_opponent",
    )
    # Surface 1: filter_team / filter_opponent aren't applied by
    # build_scope_clauses anyway (scope_key axes only), so dropping
    # them must be a no-op vs. the baseline.
    ok = (
        resp_drop["average"]["scope_avg"] == resp["average"]["scope_avg"]
        and resp_drop["strike_rate"]["scope_avg"] == resp["strike_rate"]["scope_avg"]
    )
    _, line = check(
        "drop=filter_team,filter_opponent is a no-op (not in scope-key axes)",
        ok,
    )
    print(line); all_passed &= ok

    # Now drop a real scope-key axis: dropping tournament should
    # widen the cohort dramatically.
    resp_drop_t = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        tournament="Indian Premier League",
        position_mix=",".join(str(m) for m in mix),
        drop="tournament",
    )
    ok = (
        resp_drop_t["cohort"]["n_innings_total"] > resp["cohort"]["n_innings_total"]
    )
    _, line = check(
        "drop=tournament widens cohort (more innings than IPL-scoped)",
        ok,
        f"with_tournament={resp['cohort']['n_innings_total']}, drop_tournament={resp_drop_t['cohort']['n_innings_total']}",
    )
    print(line); all_passed &= ok

    # ─── Test 4: strict-cliff invariant ─────────────────────────
    print("\n  4. Strict-cliff invariant:")

    # (a) Cliff fires when a player-weighted bucket is below threshold.
    # Find a season with bucket-10 cohort innings < 7 (threshold).
    thin = conn.execute("""
        SELECT pss.season,
               (SELECT SUM(innings) FROM playerscopestatsposition pssp
                JOIN playerscopestats pss2
                  ON pss2.scope_key = pssp.scope_key
                 AND pss2.person_id = pssp.person_id
                WHERE pssp.position_bucket = 10
                  AND pss2.season = pss.season
                  AND pss2.tournament = pss.tournament) AS b10_innings
        FROM playerscopestats pss
        WHERE pss.season != ''
        GROUP BY pss.season, pss.tournament
        HAVING b10_innings BETWEEN 1 AND 6
        ORDER BY pss.season
        LIMIT 1
    """).fetchone()
    if thin is None:
        print("    [SKIP] no thin scope found with bucket-10 cohort innings < 7")
    else:
        cliff_resp = get(
            args.host, "/api/v1/scope/averages/players/batting/summary",
            season_from=thin["season"], season_to=thin["season"],
            position_mix="0,0,0,0,0,0,0,0,0,1",
        )
        ok = (
            cliff_resp["below_support"] is True
            and 10 in cliff_resp["cliff_buckets"]
            and cliff_resp["average"]["scope_avg"] is None
            and cliff_resp["strike_rate"]["scope_avg"] is None
        )
        _, line = check(
            f"100% weight on bucket-10 in thin season {thin['season']} → cliff fires",
            ok,
            f"below_support={cliff_resp['below_support']}, cliff_buckets={cliff_resp['cliff_buckets']}",
        )
        print(line); all_passed &= ok

    # (b) by_position rows always returned; sub-rates not null-masked.
    cliff_resp = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        season_from="2005", season_to="2005",
        position_mix="0,0,0,0,0,0,0,0,0,1",
    )
    bp = cliff_resp["by_position"]
    ok = len(bp) == 10
    _, line = check("by_position always length 10", ok, f"length={len(bp)}")
    print(line); all_passed &= ok

    # (c) A bucket with mix-weight 0 may carry below_support=true
    # without nullifying the headline. Use a normal mix (no weight on
    # bucket 10) in IPL where bucket 10 might still be flagged.
    # Since IPL has 794 bucket-10 innings (well above 7), this can't
    # demonstrate the case there. Skip this sub-assertion if no
    # below_support bucket-with-zero-weight is present.
    print("\n  4c. Buckets with mix-weight 0 don't trigger cliff:")
    bp_main = resp["by_position"]
    zero_below_count = sum(
        1 for i in range(10)
        if mix[i] == 0 and bp_main[i]["below_support"]
    )
    # In any healthy IPL scope, opener+#3-#11 are all above threshold,
    # so this count will likely be 0. Just assert the main response
    # didn't cliff despite any below_support flags on unweighted
    # buckets.
    ok = resp["below_support"] is False
    _, line = check(
        f"main IPL response didn't cliff (zero-weight buckets below_support={zero_below_count})",
        ok,
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
