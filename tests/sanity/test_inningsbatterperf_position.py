"""Sanity: inningsbatterperf.position_bucket + dots correctness.

Phase 3a of spec-player-baseline-aux-fallback.md adds two columns to the
per-innings batter table so the live cohort fallback can group a filtered
pool by the batter's merged-opener position bucket without re-deriving
batting order over ~3M deliveries per request:

  - position_bucket: 1 = opener (innings positions 1+2 merged), 2 = #3,
    … 10 = #11 — the SAME convention as the precomputed cohort table
    playerscopestatsposition (api.innings_positions.derive_positions +
    populate_playerscopestats_position.position_to_bucket).
  - dots: legal balls faced for 0 runs off the bat AND 0 runs total.

Parity strategy — the table must reproduce a from-scratch derivation off
the raw deliveries (the ground truth both this table and the precompute
are built from). For a fixed closed scope (IPL 2016, men's), we aggregate
per position_bucket two ways and assert they match exactly:

  (A) GROUP BY inningsbatterperf.position_bucket over the scope.
  (B) derive_positions() over the same innings' deliveries, tallying
      per-(batter, innings) runs/balls/dots/fours/sixes in Python and
      bucketing with position_to_bucket().

A == B proves the precomputed columns can stand in for re-deriving
positions live. We use deliveries rather than playerscopestatsposition
as the anchor because the cohort scope_key encodes a tier/competition
predicate that does not reverse-map to a plain event_name+season filter;
deliveries are the stronger, unambiguous ground truth.

Plus: bucket/dots range integrity (no NULL, no 0-leak from the populate
seed, 1..10, dots in [0, balls]) and a concrete spot-check.

Usage:
  uv run python tests/sanity/test_inningsbatterperf_position.py
  uv run python tests/sanity/test_inningsbatterperf_position.py --db /tmp/x.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")

from api.innings_positions import derive_positions
from scripts.populate_playerscopestats_position import position_to_bucket

# Closed, stable scopes (won't drift) per feedback_stable_historical_test_scopes.
# Two scopes so the exact per-bucket parity isn't confined to men's franchise
# T20 — the derivation is gender/format-agnostic, but the data shapes differ,
# so a women's scope is a real second exercise. (gender, event_name, season)
PARITY_SCOPES = [
    ("male", "Indian Premier League", "2016"),
    ("female", "Women's Big Bash League", "2018/19"),
]

NAMES = ["rows", "runs", "balls", "dots", "fours", "sixes"]


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    print(line)
    return ok


def scope_parity(conn, gender: str, tourn: str, season: str):
    """Aggregate inningsbatterperf by position_bucket for one scope and
    compare to a from-deliveries derivation. Returns
    (n_innings, mismatches, ref_bucket) — mismatches empty = pass;
    ref_bucket maps (batter_id, innings_id) -> bucket for the spot-check."""
    inn_ids = [r["id"] for r in conn.execute(
        """SELECT i.id FROM innings i JOIN match m ON m.id = i.match_id
           WHERE m.gender = ? AND m.event_name = ? AND m.season = ?
             AND i.super_over = 0""",
        (gender, tourn, season),
    ).fetchall()]
    if not inn_ids:
        return 0, ["0 innings — scope drifted?"], {}

    # (B) reference from raw deliveries.
    ref_metrics: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])  # runs,balls,dots,fours,sixes
    ref_bucket: dict[tuple, int] = {}
    for iid in inn_ids:
        ds = conn.execute(
            """SELECT batter_id, non_striker_id, runs_batter, runs_total,
                      extras_wides, extras_noballs
               FROM delivery WHERE innings_id = ?
               ORDER BY over_number, delivery_index, id""",
            (iid,),
        ).fetchall()
        positions = derive_positions(ds)
        striker_pids: set = set()
        for d in ds:
            b = d["batter_id"]
            if b is None:
                continue
            striker_pids.add(b)
            legal = d["extras_wides"] == 0 and d["extras_noballs"] == 0
            m = ref_metrics[(b, iid)]
            m[0] += d["runs_batter"]
            if legal:
                m[1] += 1
                if d["runs_batter"] == 0 and d["runs_total"] == 0:
                    m[2] += 1
            if d["runs_batter"] == 4:
                m[3] += 1
            if d["runs_batter"] == 6:
                m[4] += 1
        # Bucket every player who batted — striker OR non-striker —
        # since inningsbatterperf now carries a row for pure non-striker
        # innings too (spec §4.3). derive_positions yields both ends.
        for pid in positions:
            ref_bucket[(pid, iid)] = position_to_bucket(positions[pid])
        # Pure non-striker rows: 0 runs/balls/dots/fours/sixes, mirroring
        # the populate's non-striker INSERT. Touch the defaultdict to
        # materialise the 0-row so the per-bucket COUNT(*) matches side A.
        for pid in positions:
            if pid not in striker_pids:
                _ = ref_metrics[(pid, iid)]

    ref_by_bucket: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])  # rows,runs,balls,dots,fours,sixes
    for key, metr in ref_metrics.items():
        agg = ref_by_bucket[ref_bucket[key]]
        agg[0] += 1
        for j in range(5):
            agg[j + 1] += metr[j]

    # (A) from the precomputed table.
    tbl_by_bucket: dict[int, list[int]] = {}
    for r in conn.execute(
        """SELECT ibp.position_bucket AS bk, COUNT(*) AS rows,
                  SUM(ibp.runs) AS runs, SUM(ibp.balls) AS balls,
                  SUM(ibp.dots) AS dots, SUM(ibp.fours) AS fours,
                  SUM(ibp.sixes) AS sixes
           FROM inningsbatterperf ibp
           JOIN innings i ON i.id = ibp.innings_id
           JOIN match m ON m.id = i.match_id
           WHERE m.gender = ? AND m.event_name = ? AND m.season = ?
             AND i.super_over = 0
           GROUP BY ibp.position_bucket""",
        (gender, tourn, season),
    ).fetchall():
        tbl_by_bucket[r["bk"]] = [
            r["rows"], r["runs"], r["balls"], r["dots"], r["fours"], r["sixes"],
        ]

    mismatches = []
    for bk in sorted(set(ref_by_bucket) | set(tbl_by_bucket)):
        ref = ref_by_bucket.get(bk, [0] * 6)
        tbl = tbl_by_bucket.get(bk, [0] * 6)
        for j, nm in enumerate(NAMES):
            if ref[j] != tbl[j]:
                mismatches.append(f"bucket {bk} {nm}: table={tbl[j]} deliveries={ref[j]}")
    return len(inn_ids), mismatches, ref_bucket


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    print(f"Sanity: inningsbatterperf position_bucket + dots ({args.db})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # 1. Range integrity — no NULL, no 0-leak (0 is the populate seed),
    #    1..10, dots in [0, balls].
    print("\n  1. Range integrity:")
    row = conn.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN position_bucket IS NULL THEN 1 ELSE 0 END) AS pb_null,
          SUM(CASE WHEN position_bucket = 0 THEN 1 ELSE 0 END) AS pb_zero,
          SUM(CASE WHEN position_bucket < 1 OR position_bucket > 10 THEN 1 ELSE 0 END) AS pb_oor,
          SUM(CASE WHEN dots IS NULL THEN 1 ELSE 0 END) AS dots_null,
          SUM(CASE WHEN dots < 0 OR dots > balls THEN 1 ELSE 0 END) AS dots_bad
        FROM inningsbatterperf
    """).fetchone()
    all_passed &= check(
        "position_bucket NOT NULL, no 0-leak, BETWEEN 1 AND 10",
        row["pb_null"] == 0 and row["pb_zero"] == 0 and row["pb_oor"] == 0,
        f"null={row['pb_null']} zero={row['pb_zero']} oor={row['pb_oor']} total={row['total']}",
    )
    all_passed &= check(
        "dots NOT NULL and within [0, balls]",
        row["dots_null"] == 0 and row["dots_bad"] == 0,
        f"null={row['dots_null']} bad={row['dots_bad']}",
    )

    # Global exact dots reconciliation — every row's dots summed equals the
    # raw count of legal no-run deliveries (one striker faces each such
    # ball), proving dots correct across ALL rows, not just the sampled
    # parity scopes below.
    gd = conn.execute("SELECT COALESCE(SUM(dots), 0) AS s FROM inningsbatterperf").fetchone()["s"]
    raw = conn.execute(
        """SELECT COUNT(*) AS c FROM delivery
           WHERE batter_id IS NOT NULL AND extras_wides = 0 AND extras_noballs = 0
             AND runs_batter = 0 AND runs_total = 0"""
    ).fetchone()["c"]
    all_passed &= check(
        "SUM(dots) == raw legal no-run deliveries (global, exact)",
        gd == raw, f"table={gd} raw={raw}",
    )

    # 2. From-deliveries parity per scope (both genders/formats).
    print("\n  2. From-deliveries per-bucket parity:")
    first_scope_ref: dict[tuple, int] = {}
    for idx, (gender, tourn, season) in enumerate(PARITY_SCOPES):
        n_inn, mismatches, ref_bucket = scope_parity(conn, gender, tourn, season)
        if idx == 0:
            first_scope_ref = ref_bucket
            first_scope = (gender, tourn, season)
        all_passed &= check(
            f"{tourn} {season} ({gender}, {n_inn} innings): per-bucket "
            f"{NAMES} match deliveries",
            n_inn > 0 and not mismatches,
            "; ".join(mismatches[:8]) or "0 innings — scope drifted?",
        )

    # 2b. Non-striker completion (spec §4.3): inningsbatterperf must now
    #     carry a row per (batter OR non-striker, innings) so the row
    #     count equals the summary's _batting_innings_filter innings count
    #     — and pure non-striker rows (0 runs, 0 balls) must exist.
    print("\n  2b. Non-striker innings completion:")
    for gender, tourn, season in PARITY_SCOPES:
        tbl_rows = conn.execute(
            """SELECT COUNT(*) AS c FROM inningsbatterperf ib
               JOIN innings i ON i.id = ib.innings_id
               JOIN match m ON m.id = i.match_id
               WHERE m.gender=? AND m.event_name=? AND m.season=? AND i.super_over=0""",
            (gender, tourn, season),
        ).fetchone()["c"]
        true_inn = conn.execute(
            """SELECT COUNT(*) AS c FROM (
                 SELECT DISTINCT pid, innings_id FROM (
                   SELECT batter_id AS pid, innings_id FROM delivery WHERE batter_id IS NOT NULL
                   UNION
                   SELECT non_striker_id AS pid, innings_id FROM delivery WHERE non_striker_id IS NOT NULL
                 ) u
                 JOIN innings i ON i.id = u.innings_id
                 JOIN match m ON m.id = i.match_id
                 WHERE m.gender=? AND m.event_name=? AND m.season=? AND i.super_over=0
               )""",
            (gender, tourn, season),
        ).fetchone()["c"]
        all_passed &= check(
            f"{tourn} {season} ({gender}): rows == (batter OR non-striker) innings",
            tbl_rows == true_inn, f"table={tbl_rows} true={true_inn}",
        )
    ns_rows = conn.execute(
        """SELECT COUNT(*) AS c FROM inningsbatterperf ib
           WHERE ib.balls = 0 AND ib.runs = 0
             AND NOT EXISTS (
               SELECT 1 FROM delivery d
               WHERE d.innings_id = ib.innings_id AND d.batter_id = ib.batter_id)"""
    ).fetchone()["c"]
    all_passed &= check(
        "pure non-striker rows present (0 balls, never faced as striker)",
        ns_rows > 0, f"count={ns_rows}",
    )

    # 2c. not_out semantics (records audit §6.2): not_out's complement is
    #     a NON-RETIRED dismissal, matching the cohort's
    #     BATTER_DISMISSAL_EXCLUDED. This locks the records `*` and the
    #     Commit-3 rollup's dismissals = SUM(NOT not_out).
    print("\n  2c. not_out excludes retired (records audit):")
    bad = conn.execute("""
        SELECT
          SUM(CASE WHEN ib.not_out = 0 AND NOT EXISTS (
                SELECT 1 FROM wicket w JOIN delivery d ON d.id = w.delivery_id
                WHERE d.innings_id = ib.innings_id AND w.player_out_id = ib.batter_id
                  AND w.kind NOT IN ('retired hurt','retired out'))
               THEN 1 ELSE 0 END) AS out_without_dismissal,
          SUM(CASE WHEN ib.not_out = 1 AND EXISTS (
                SELECT 1 FROM wicket w JOIN delivery d ON d.id = w.delivery_id
                WHERE d.innings_id = ib.innings_id AND w.player_out_id = ib.batter_id
                  AND w.kind NOT IN ('retired hurt','retired out'))
               THEN 1 ELSE 0 END) AS notout_with_dismissal
        FROM inningsbatterperf ib
    """).fetchone()
    all_passed &= check(
        "not_out=0 iff a non-retired dismissal exists (no leaks either way)",
        bad["out_without_dismissal"] == 0 and bad["notout_with_dismissal"] == 0,
        f"out_without_dismissal={bad['out_without_dismissal']} "
        f"notout_with_dismissal={bad['notout_with_dismissal']}",
    )

    # 3. Spot-check: the biggest innings in the first scope sits in the
    #    bucket derive_positions assigns it (ties a concrete row to the rule).
    g, t, s = first_scope
    print(f"\n  3. Spot-check — top-scoring {t} {s} innings:")
    top = conn.execute(
        """SELECT ibp.batter_id, ibp.innings_id, ibp.runs, ibp.position_bucket
           FROM inningsbatterperf ibp
           JOIN innings i ON i.id = ibp.innings_id
           JOIN match m ON m.id = i.match_id
           WHERE m.gender = ? AND m.event_name = ? AND m.season = ?
             AND i.super_over = 0
           ORDER BY ibp.runs DESC LIMIT 1""",
        (g, t, s),
    ).fetchone()
    expected_bucket = first_scope_ref.get((top["batter_id"], top["innings_id"]))
    all_passed &= check(
        f"row (runs={top['runs']}) position_bucket matches derive_positions",
        top["position_bucket"] == expected_bucket,
        f"table={top['position_bucket']} derived={expected_bucket}",
    )

    conn.close()
    print()
    print("ALL PASS" if all_passed else "SOME FAILURES — see above")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
