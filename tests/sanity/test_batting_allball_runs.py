"""Sanity: player batting runs are ALL-BALL; balls/SR stay legal.

The headline red-then-green of spec-batting-allball-runs-single-source.md
§2/§8. Before the fix, the player batting read queries summed
d.runs_batter under a WHERE that excluded no-balls, so a batsman silently
lost the runs he scored off no-balls (V Kohli: 13117 instead of 13166).
This test pins the corrected convention on the live endpoints:

  - /batters/{id}/summary.runs == all-ball SQL (SUM(runs_batter) over ALL
    the batter's deliveries, super-overs excluded), strictly GREATER than
    the old legal-only SQL — the strictly-greater assertion is the one
    that was RED against the pre-fix code (which returned the legal-only
    number).
  - summary.balls_faced == legal-ball SQL (a no-ball is never a ball
    faced), so strike rate = all-ball runs / legal balls.
  - by-season / by-over runs sum to the same all-ball total (the tabs
    moved with the summary — no tab left on the old convention).

Anchored entirely against sqlite at runtime (per testing discipline), at
all-time + a closed narrowed scope (IPL 2016), so it can't drift.

Usage:
  uv run python tests/sanity/test_batting_allball_runs.py
  uv run python tests/sanity/test_batting_allball_runs.py --host http://localhost:8000
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

KOHLI = "ba607b88"


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{host}{path}" + (f"?{qs}" if qs else "")
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def val(x):
    """Unwrap a metric envelope ({'value': n, ...}) or a bare scalar."""
    return x.get("value") if isinstance(x, dict) else x


def runs_sql(conn, person_id, legal_only, scope=""):
    gate = " AND d.extras_wides = 0 AND d.extras_noballs = 0" if legal_only else ""
    return conn.execute(
        f"""SELECT COALESCE(SUM(d.runs_batter), 0) AS r
            FROM delivery d JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.batter_id = ? AND i.super_over = 0{gate}{scope}""",
        (person_id,),
    ).fetchone()[0]


def legal_balls_sql(conn, person_id, scope=""):
    return conn.execute(
        f"""SELECT COUNT(*) AS b
            FROM delivery d JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.batter_id = ? AND i.super_over = 0
              AND d.extras_wides = 0 AND d.extras_noballs = 0{scope}""",
        (person_id,),
    ).fetchone()[0]


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         {detail}" if detail and not ok else ""))
    return ok


def summary_block(conn, host, label, scope_sql, params):
    ok = True
    s = get(host, f"/api/v1/batters/{KOHLI}/summary", **params)
    runs, balls, sr = val(s.get("runs")), val(s.get("balls_faced")), val(s.get("strike_rate"))
    allball = runs_sql(conn, KOHLI, legal_only=False, scope=scope_sql)
    legalonly = runs_sql(conn, KOHLI, legal_only=True, scope=scope_sql)
    legalballs = legal_balls_sql(conn, KOHLI, scope=scope_sql)

    ok &= check(f"{label}: summary.runs == all-ball SQL ({allball})",
                runs == allball, f"api={runs} sql={allball}")
    # The red-demonstrating assertion: pre-fix code returned legal-only.
    ok &= check(f"{label}: all-ball runs STRICTLY > legal-only ({allball} > {legalonly})",
                allball > legalonly and runs > legalonly,
                f"api={runs} allball={allball} legalonly={legalonly}")
    ok &= check(f"{label}: summary.balls_faced == legal-ball SQL ({legalballs})",
                balls == legalballs, f"api={balls} sql={legalballs}")
    ok &= check(f"{label}: strike_rate == all-ball runs / legal balls",
                sr == round(runs * 100 / balls, 2) if balls else sr is None,
                f"sr={sr} recomputed={round(runs*100/balls,2) if balls else None}")
    return ok, runs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    print(f"Sanity: all-ball batting runs ({args.host})")
    ok = True

    # 1. All-time summary.
    print("\n  1. All-time summary:")
    o, alltime_runs = summary_block(conn, args.host, "all-time", "", {})
    ok &= o

    # 2. Narrowed closed scope (IPL 2016) — convention holds under filters.
    print("\n  2. IPL 2016 (closed narrowed scope):")
    scope_sql = " AND m.event_name = 'Indian Premier League' AND m.season = '2016'"
    o, _ = summary_block(conn, args.host, "IPL2016", scope_sql,
                         {"tournament": "Indian Premier League",
                          "season_from": "2016", "season_to": "2016"})
    ok &= o

    # 3. Cross-tab consistency: by-season + by-over runs sum to the
    #    all-time summary (every tab moved to all-ball together).
    print("\n  3. Cross-tab consistency (all-time):")
    bs = get(args.host, f"/api/v1/batters/{KOHLI}/by-season")
    season_runs = sum(val(r.get("runs")) for r in bs.get("by_season", bs.get("seasons", [])))
    ok &= check(f"sum(by-season runs) == summary runs ({alltime_runs})",
                season_runs == alltime_runs, f"by_season={season_runs} summary={alltime_runs}")
    bo = get(args.host, f"/api/v1/batters/{KOHLI}/by-over")
    over_runs = sum(val(r.get("runs")) for r in bo.get("by_over", bo.get("overs", [])))
    ok &= check(f"sum(by-over runs) == summary runs ({alltime_runs})",
                over_runs == alltime_runs, f"by_over={over_runs} summary={alltime_runs}")

    conn.close()
    print("\n" + ("ALL PASS" if ok else "SOME FAILURES — see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
