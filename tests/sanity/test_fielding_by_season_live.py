"""Sanity: /scope/averages/fielding/by-season on the live path.

The endpoint serves a precomputed scope from the bucket baselines and
every other scope from `_fielding_by_season_live`. Until 2026-11-14 a
second, unrelated function of the same name (the per-player keeper
cohort, Phase 3e) replaced the first at import time. So every scope
that is not precomputed gave HTTP 500 (TypeError: missing 2 required
positional arguments: 'filters' and 'aux').

The test calls the handler that the router registers for the path, so
it runs the same code as an HTTP request, with no server.

Checks:
  1. inning=0 (a live scope): the call succeeds, the seasons and the
     per-season matches and catches equal SQL. With inning set, a match
     has one fielding innings in scope, so catches_per_match is
     catches / matches. Option B: inning=0 on the fielding side is
     innings_number = 1 (`_option_b_team_inning`). The live path lists
     a season only when it has a fielding credit.
  2. filter_venue=Wankhede Stadium (a live scope): the same checks.
     With no inning, a match has two fielding innings, so
     catches_per_match is catches / matches / 2.
  3. IPL 2024 (a precomputed scope): the endpoint returns what
     `_fielding_by_season_from_baseline` returns, and the live path,
     called directly at the same scope, gives the same body.
  4. The other caller of the per-season live path, the player cohort
     `/players/fielding/by-season`, still works under a live scope.

Usage:
  uv run python tests/sanity/test_fielding_by_season_live.py
  uv run python tests/sanity/test_fielding_by_season_live.py --db tmp/cricket-prod-test.db

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deebase import Database  # noqa: E402
from api import dependencies as deps  # noqa: E402
from api.filters import FilterBarParams, AuxParams  # noqa: E402
from api.routers import scope_averages  # noqa: E402

IPL = "Indian Premier League"
VENUE = "Wankhede Stadium"
DHONI = "4a8a2e3b"


def _filters(**overrides) -> FilterBarParams:
    """A FilterBarParams with every field None, then `overrides`."""
    f = FilterBarParams()
    for k in ("gender", "team_type", "tournament", "season_from",
              "season_to", "team", "opponent", "venue", "team_class",
              "series_type"):
        setattr(f, k, None)
    for k, v in overrides.items():
        setattr(f, k, v)
    return f


def _aux(**overrides) -> AuxParams:
    """An AuxParams with every field None, then `overrides`."""
    a = AuxParams()
    for k in ("scope_to_team", "chip_team_class", "chip_baseline_scope_json",
              "inning", "result", "toss_outcome"):
        setattr(a, k, None)
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


def _handler(path: str):
    """The function the router registers for GET `path`."""
    full = scope_averages.router.prefix + path
    for r in scope_averages.router.routes:
        if getattr(r, "path", None) == full and "GET" in getattr(r, "methods", ()):
            return r.endpoint
    raise LookupError(f"no GET route {full}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    print(line)
    return ok


def sql_by_season(conn, extra_where: str, params: dict) -> dict:
    """Per-season (matches, catches, all fielding credits) for IPL men's club, from SQL."""
    base = ("m.gender = 'male' AND m.team_type = 'club' AND m.event_name = :t"
            " AND i.super_over = 0 AND " + extra_where)
    p = {"t": IPL, **params}
    matches = {
        r[0]: r[1] for r in conn.execute(
            f"SELECT m.season, COUNT(DISTINCT m.id) FROM match m"
            f" JOIN innings i ON i.match_id = m.id WHERE {base} GROUP BY m.season", p)
    }
    credits = {
        r[0]: (r[1], r[2]) for r in conn.execute(
            f"SELECT m.season,"
            f" SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled') THEN 1 ELSE 0 END),"
            f" SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled', 'stumped', 'run_out') THEN 1 ELSE 0 END)"
            f" FROM fieldingcredit fc"
            f" JOIN delivery d ON d.id = fc.delivery_id"
            f" JOIN innings i ON i.id = d.innings_id"
            f" JOIN match m ON m.id = i.match_id"
            f" WHERE {base} GROUP BY m.season", p)
    }
    return {s: (matches.get(s, 0), *credits.get(s, (0, 0))) for s in set(matches) | set(credits)}


async def live_scope_case(label, endpoint, filters, aux, expected, per_match_divisor) -> bool:
    """Call the endpoint for one live scope and compare with SQL."""
    print(f"\n  {label}:")
    ok_all = True
    try:
        out = await endpoint(filters=filters, aux=aux)
    except Exception as e:  # the 2026-11-14 bug was a TypeError here
        return check("endpoint call succeeds", False, f"{type(e).__name__}: {e}")
    ok_all &= check("endpoint call succeeds", True)
    rows = out.get("by_season") if isinstance(out, dict) else None
    ok_all &= check("body has a non-empty by_season list", bool(rows), f"got {out!r:.200}")
    if not rows:
        return False
    # The live SQL lists a season only when it has a fielding credit.
    got_seasons = [r["season"] for r in rows]
    want_seasons = sorted(s for s, (_, _, credits) in expected.items() if credits)
    ok_all &= check("seasons == SQL seasons", got_seasons == want_seasons,
                    f"api {got_seasons} vs sql {want_seasons}")
    bad = []
    for r in rows:
        m, c, _ = expected.get(r["season"], (0, 0, 0))
        want_cpm = round(c / m / per_match_divisor, 2) if m else None
        if r["matches"] != m or r["catches_per_match"] is None or abs(r["catches_per_match"] - want_cpm) > 0.011:
            bad.append(f"{r['season']}: api matches={r['matches']} cpm={r['catches_per_match']}"
                       f" vs sql matches={m} cpm={want_cpm}")
    ok_all &= check("per-season matches and catches_per_match == SQL", not bad, "; ".join(bad[:5]))
    return ok_all


async def run(db_path: str) -> bool:
    deps._db = Database(f"sqlite+aiosqlite:///{db_path}")
    await deps._db.q("PRAGMA journal_mode = WAL")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    endpoint = _handler("/fielding/by-season")
    ipl = dict(gender="male", team_type="club", tournament=IPL)
    ok_all = True

    # 1. inning=0 → fielding innings_number = 1 (Option B).
    ok_all &= await live_scope_case(
        "1. inning=0 (live)", endpoint, _filters(**ipl), _aux(inning=0),
        sql_by_season(conn, "i.innings_number = 1", {}), per_match_divisor=1,
    )

    # 2. filter_venue, no inning → two fielding innings per match.
    ok_all &= await live_scope_case(
        f"2. filter_venue={VENUE} (live)", endpoint, _filters(**ipl, venue=VENUE), _aux(),
        sql_by_season(conn, "m.venue = :v", {"v": VENUE}), per_match_divisor=2,
    )

    # 3. A precomputed scope still goes to the baseline.
    print("\n  3. IPL 2024 (precomputed):")
    pre = dict(ipl, season_from="2024", season_to="2024")
    got = await endpoint(filters=_filters(**pre), aux=_aux())
    want = await scope_averages._fielding_by_season_from_baseline(_filters(**pre), _aux())
    ok_all &= check("endpoint == _fielding_by_season_from_baseline", got == want and bool(got["by_season"]),
                    f"{got!r:.200} vs {want!r:.200}")
    # The live path, called directly at the same scope, gives the same
    # body, to 0.011 (the rounding of the per-innings counts).
    live = await scope_averages._fielding_by_season_live(_filters(**pre), _aux())
    same = len(live["by_season"]) == len(want["by_season"]) and all(
        a.keys() == b.keys() and all(
            abs(a[k] - b[k]) <= 0.011 if isinstance(a[k], float) else a[k] == b[k] for k in a)
        for a, b in zip(live["by_season"], want["by_season"]))
    ok_all &= check("_fielding_by_season_live == baseline at the same scope", same,
                    f"{live!r:.200} vs {want!r:.200}")

    # 4. The player cohort's per-season live path (the other function
    #    that used to share the name) under live scopes.
    print("\n  4. /players/fielding/by-season under live scopes:")
    pl = _handler("/players/fielding/by-season")
    for label, f, a in (("inning=1", _filters(**ipl), _aux(inning=1)),
                        (f"filter_venue={VENUE}", _filters(**ipl, venue=VENUE), _aux())):
        try:
            out = await pl(person_id=DHONI, filters=f, aux=a, drop=None)
            rows = out["by_season"]
            ok = bool(rows) and all(r["n_matches"] > 0 for r in rows)
            ok_all &= check(f"{label}: rows with n_matches > 0", ok, f"{rows!r:.200}")
        except Exception as e:
            ok_all &= check(f"{label}: call succeeds", False, f"{type(e).__name__}: {e}")

    conn.close()
    return ok_all


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(PROJECT_ROOT, "cricket.db"))
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1
    print(f"Sanity: /scope/averages/fielding/by-season live path ({args.db})")
    ok = asyncio.run(run(args.db))
    print("\nALL PASS" if ok else "\nFAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
