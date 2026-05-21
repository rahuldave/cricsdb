"""Sanity: spec-rate-vs-volume-audit §2.1 Group A envelopes.

Verifies the new per-innings rate envelopes added on top of the Phase F
Q6 set:

  - /batters/{id}/summary.runs_per_innings — value + scope_avg.
  - /bowlers/{id}/summary.four_wicket_hauls_per_innings — value +
    scope_avg.

Three checks per envelope:

  1. **Field presence** — the key exists on the response.
  2. **Value identity** — envelope.value equals runs/innings (batting)
     or four_wicket_hauls/innings (bowling), computed independently
     from the same /summary response numerator + denominator.
  3. **Cohort cross-check** — envelope.scope_avg equals the matching
     field on /scope/averages/players/{batting,bowling}/summary at
     the same scope. Sanity for the dual-query envelope semantics.

Scoped to closed historical windows (Kohli IPL all-time, Bumrah IPL
all-time) so SQL-derived expecteds are stable across DB updates
(feedback_stable_historical_test_scopes).

Usage:
  uv run python tests/sanity/test_q6_extension_envelopes.py
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


def approx(a: float, b: float, tol: float = 0.005) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: Q6 extension envelopes ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # ─── Test 1: /batters/{id}/summary.runs_per_innings ──────────
    print("\n  1. /batters/ba607b88/summary.runs_per_innings @ Kohli IPL:")
    bat_resp = get(
        args.host, "/api/v1/batters/ba607b88/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    rpi = bat_resp.get("runs_per_innings")
    ok = isinstance(rpi, dict)
    _, line = check("runs_per_innings envelope is present", ok)
    print(line); all_passed &= ok
    if not ok:
        # Without the envelope nothing else can be checked.
        return 1 if not all_passed else 0

    # Value identity: envelope.value == runs.value / innings.value
    runs_v = bat_resp["runs"]["value"]
    inn_v = bat_resp["innings"]["value"]
    expected = round(runs_v / inn_v, 2) if inn_v else None
    ok = approx(rpi["value"], expected, tol=0.01)
    _, line = check(
        "runs_per_innings.value == runs / innings",
        ok,
        f"expected={expected}, actual={rpi['value']}",
    )
    print(line); all_passed &= ok

    # SQL-anchored cross-check on the numerator/denominator.
    row = conn.execute("""
        SELECT SUM(runs) AS r, SUM(innings_batted) AS i
        FROM playerscopestats
        WHERE person_id = 'ba607b88'
          AND tournament = 'Indian Premier League'
          AND gender = 'male' AND team_type = 'club'
    """).fetchone()
    sql_expected = round(row["r"] / row["i"], 2) if row["i"] else None
    ok = approx(rpi["value"], sql_expected, tol=0.01)
    _, line = check(
        "runs_per_innings.value == sqlite3 cricket.db runs/innings_batted",
        ok,
        f"sql={sql_expected}, actual={rpi['value']}",
    )
    print(line); all_passed &= ok

    # Cohort cross-check: envelope.scope_avg == cohort /summary.runs_per_innings.value.
    cohort_resp = get(
        args.host, "/api/v1/scope/averages/players/batting/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        # Use Kohli's actual position mix at this scope to mirror the
        # cohort fold the /batters endpoint does. Approximation: most of
        # Kohli's IPL innings come at #3 (bucket 2). The runs_per_innings
        # field is scope-FLAT on the cohort (derived from the parent
        # table, not position-weighted) so the mix value doesn't matter
        # for THIS field — uniform mix is fine.
        position_mix="0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1",
    )
    cohort_rpi = cohort_resp.get("runs_per_innings", {}).get("value")
    ok = approx(rpi["scope_avg"], cohort_rpi, tol=0.02)
    _, line = check(
        "player.scope_avg == cohort.runs_per_innings.value",
        ok,
        f"cohort={cohort_rpi}, player.scope_avg={rpi['scope_avg']}",
    )
    print(line); all_passed &= ok

    # ─── Test 2: /bowlers/{id}/summary.four_wicket_hauls_per_innings ─
    print("\n  2. /bowlers/462411b3/summary.four_wicket_hauls_per_innings @ Bumrah IPL:")
    bowl_resp = get(
        args.host, "/api/v1/bowlers/462411b3/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
    )
    fwh_pi = bowl_resp.get("four_wicket_hauls_per_innings")
    ok = isinstance(fwh_pi, dict)
    _, line = check("four_wicket_hauls_per_innings envelope is present", ok)
    print(line); all_passed &= ok
    if not ok:
        return 1

    fwh_v = bowl_resp["four_wicket_hauls"]["value"]
    bowl_inn_v = bowl_resp["innings"]["value"]
    expected = round(fwh_v / bowl_inn_v, 4) if bowl_inn_v else None
    ok = approx(fwh_pi["value"], expected, tol=0.0001)
    _, line = check(
        "four_wicket_hauls_per_innings.value == four_wicket_hauls / innings",
        ok,
        f"expected={expected}, actual={fwh_pi['value']}",
    )
    print(line); all_passed &= ok

    # SQL-anchored: this is the four-wicket-haul count for Bumrah IPL.
    row = conn.execute("""
        SELECT SUM(four_wicket_hauls) AS fwh
        FROM playerscopestats
        WHERE person_id = '462411b3'
          AND tournament = 'Indian Premier League'
          AND gender = 'male' AND team_type = 'club'
    """).fetchone()
    sql_fwh = row["fwh"] or 0
    ok = sql_fwh == fwh_v
    _, line = check(
        "four_wicket_hauls volume matches sqlite3 cricket.db",
        ok,
        f"sql={sql_fwh}, api={fwh_v}",
    )
    print(line); all_passed &= ok

    # Cohort cross-check.
    cohort_bowl = get(
        args.host, "/api/v1/scope/averages/players/bowling/summary",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        over_mix="0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05",
    )
    cohort_fwh = cohort_bowl.get("four_wicket_hauls_per_innings", {}).get("value")
    ok = approx(fwh_pi["scope_avg"], cohort_fwh, tol=0.0005)
    _, line = check(
        "player.scope_avg == cohort.four_wicket_hauls_per_innings.value",
        ok,
        f"cohort={cohort_fwh}, player.scope_avg={fwh_pi['scope_avg']}",
    )
    print(line); all_passed &= ok

    # ─── Test 3: cohort /by-season — Group C mirrors ─────────────
    print("\n  3. /scope/averages/players/batting/by-season Group C fields:")
    bat_bs = get(
        args.host, "/api/v1/scope/averages/players/batting/by-season",
        person_id="ba607b88", gender="male", team_type="club",
        tournament="Indian Premier League",
        season_from="2016", season_to="2016",
    )
    seasons = bat_bs.get("by_season", [])
    ok = len(seasons) == 1 and seasons[0]["season"] == "2016"
    _, line = check("one season row (IPL 2016) returned", ok)
    print(line); all_passed &= ok
    if ok:
        r = seasons[0]
        for k in (
            "runs_per_innings", "hundreds_per_innings",
            "fifties_per_innings", "thirties_per_innings",
            "ducks_per_innings",
        ):
            ok = k in r and r[k] is not None
            _, line = check(f"  field {k} present and non-null", ok,
                            f"value={r.get(k)}")
            print(line); all_passed &= ok
        # Cross-check milestone rate against SQL (scope-flat).
        row = conn.execute("""
            SELECT SUM(hundreds)*1.0/SUM(innings_batted) AS hpi
            FROM playerscopestats
            WHERE tournament='Indian Premier League' AND season='2016'
              AND gender='male' AND team_type='club'
        """).fetchone()
        sql_hpi = round(row["hpi"], 3) if row["hpi"] is not None else None
        ok = approx(r["hundreds_per_innings"], sql_hpi, tol=0.001)
        _, line = check(
            "hundreds_per_innings matches sqlite3 scope-flat SQL",
            ok,
            f"sql={sql_hpi}, api={r['hundreds_per_innings']}",
        )
        print(line); all_passed &= ok

    print("\n  4. /scope/averages/players/bowling/by-season Group C field:")
    bowl_bs = get(
        args.host, "/api/v1/scope/averages/players/bowling/by-season",
        person_id="462411b3", gender="male", team_type="club",
        tournament="Indian Premier League",
        season_from="2018", season_to="2018",
    )
    seasons = bowl_bs.get("by_season", [])
    ok = len(seasons) == 1 and seasons[0]["season"] == "2018"
    _, line = check("one season row (IPL 2018) returned", ok)
    print(line); all_passed &= ok
    if ok:
        r = seasons[0]
        ok = (
            "four_wicket_hauls_per_innings" in r
            and r["four_wicket_hauls_per_innings"] is not None
        )
        _, line = check(
            "field four_wicket_hauls_per_innings present and non-null",
            ok,
            f"value={r.get('four_wicket_hauls_per_innings')}",
        )
        print(line); all_passed &= ok
        # Cross-check against SQL (scope-flat with balls/24 denominator).
        row = conn.execute("""
            SELECT SUM(four_wicket_hauls)*1.0 / (SUM(balls_bowled)/24.0) AS fwhpi
            FROM playerscopestats
            WHERE tournament='Indian Premier League' AND season='2018'
              AND gender='male' AND team_type='club'
        """).fetchone()
        sql_fwhpi = round(row["fwhpi"], 4) if row["fwhpi"] is not None else None
        ok = approx(r["four_wicket_hauls_per_innings"], sql_fwhpi, tol=0.0005)
        _, line = check(
            "four_wicket_hauls_per_innings matches sqlite3 scope-flat SQL",
            ok,
            f"sql={sql_fwhpi}, api={r['four_wicket_hauls_per_innings']}",
        )
        print(line); all_passed &= ok

    # ─── Test 5: player /by-season Group B rates ─────────────────
    print("\n  5. /batters/{id}/by-season Group B fields:")
    bat_bs = get(
        args.host, "/api/v1/batters/ba607b88/by-season",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        season_from="2016", season_to="2016",
    )
    row = bat_bs["by_season"][0] if bat_bs["by_season"] else {}
    inn = row.get("innings") or 0
    runs = row.get("runs") or 0
    hundreds = row.get("hundreds") or 0
    expected_rpi = round(runs / inn, 2) if inn else None
    expected_hpi = round(hundreds / inn, 3) if inn else None
    ok = approx(row.get("runs_per_innings"), expected_rpi, tol=0.01)
    _, line = check(
        "runs_per_innings == runs / innings (in-row)",
        ok,
        f"expected={expected_rpi}, actual={row.get('runs_per_innings')}",
    )
    print(line); all_passed &= ok
    ok = approx(row.get("hundreds_per_innings"), expected_hpi, tol=0.001)
    _, line = check(
        "hundreds_per_innings == hundreds / innings (in-row)",
        ok,
        f"expected={expected_hpi}, actual={row.get('hundreds_per_innings')}",
    )
    print(line); all_passed &= ok

    print("\n  6. /bowlers/{id}/by-season Group B fields:")
    bowl_bs = get(
        args.host, "/api/v1/bowlers/462411b3/by-season",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        season_from="2018", season_to="2018",
    )
    row = bowl_bs["by_season"][0] if bowl_bs["by_season"] else {}
    inn = row.get("innings") or 0
    wkts = row.get("wickets") or 0
    fwh = row.get("four_wicket_hauls") or 0
    expected_wpi = round(wkts / inn, 3) if inn else None
    expected_fwhpi = round(fwh / inn, 4) if inn else None
    ok = approx(row.get("wickets_per_innings"), expected_wpi, tol=0.001)
    _, line = check(
        "wickets_per_innings == wickets / innings (in-row)",
        ok,
        f"expected={expected_wpi}, actual={row.get('wickets_per_innings')}",
    )
    print(line); all_passed &= ok
    ok = approx(row.get("four_wicket_hauls_per_innings"), expected_fwhpi, tol=0.0001)
    _, line = check(
        "four_wicket_hauls_per_innings == four_wicket_hauls / innings",
        ok,
        f"expected={expected_fwhpi}, actual={row.get('four_wicket_hauls_per_innings')}",
    )
    print(line); all_passed &= ok

    print("\n  7. /fielders/{id}/by-season Group B fields:")
    field_bs = get(
        args.host, "/api/v1/fielders/4a8a2e3b/by-season",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        season_from="2016", season_to="2016",
    )
    row = field_bs["by_season"][0] if field_bs["by_season"] else {}
    matches = row.get("matches") or 0
    total = row.get("total") or 0
    catches = row.get("catches") or 0
    expected_dpm = round(total / matches, 3) if matches else None
    expected_cpm = round(catches / matches, 3) if matches else None
    ok = approx(row.get("dismissals_per_match"), expected_dpm, tol=0.001)
    _, line = check(
        "dismissals_per_match == total / matches (in-row)",
        ok,
        f"expected={expected_dpm}, actual={row.get('dismissals_per_match')}",
    )
    print(line); all_passed &= ok
    ok = approx(row.get("catches_per_match"), expected_cpm, tol=0.001)
    _, line = check(
        "catches_per_match == catches / matches (in-row)",
        ok,
        f"expected={expected_cpm}, actual={row.get('catches_per_match')}",
    )
    print(line); all_passed &= ok

    # ─── Test 8: direction metadata is wired in ──────────────────
    print("\n  8. direction metadata is set:")
    ok = rpi.get("direction") == "higher_better"
    _, line = check(
        "runs_per_innings.direction == higher_better",
        ok,
        f"actual={rpi.get('direction')}",
    )
    print(line); all_passed &= ok

    ok = fwh_pi.get("direction") == "higher_better"
    _, line = check(
        "four_wicket_hauls_per_innings.direction == higher_better",
        ok,
        f"actual={fwh_pi.get('direction')}",
    )
    print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    print("FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
