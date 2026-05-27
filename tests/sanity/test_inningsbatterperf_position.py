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

# Closed, stable scope (won't drift) per feedback_stable_historical_test_scopes.
SCOPE_TOURNAMENT = "Indian Premier League"
SCOPE_SEASON = "2016"
SCOPE_GENDER = "male"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    print(line)
    return ok


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

    # 2. From-deliveries parity for the fixed scope.
    print(f"\n  2. From-deliveries parity ({SCOPE_TOURNAMENT} {SCOPE_SEASON} {SCOPE_GENDER}):")
    inn_ids = [r["id"] for r in conn.execute(
        """SELECT i.id FROM innings i JOIN match m ON m.id = i.match_id
           WHERE m.gender = ? AND m.event_name = ? AND m.season = ?
             AND i.super_over = 0""",
        (SCOPE_GENDER, SCOPE_TOURNAMENT, SCOPE_SEASON),
    ).fetchall()]
    if not inn_ids:
        all_passed &= check("scope has innings", False, "0 innings — scope drifted?")
        conn.close()
        return 0 if all_passed else 1
    print(f"       scope innings = {len(inn_ids)}")

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
        for d in ds:
            b = d["batter_id"]
            if b is None:
                continue
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
        for b in {d["batter_id"] for d in ds if d["batter_id"] is not None}:
            ref_bucket[(b, iid)] = position_to_bucket(positions[b])

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
        (SCOPE_GENDER, SCOPE_TOURNAMENT, SCOPE_SEASON),
    ).fetchall():
        tbl_by_bucket[r["bk"]] = [
            r["rows"], r["runs"], r["balls"], r["dots"], r["fours"], r["sixes"],
        ]

    names = ["rows", "runs", "balls", "dots", "fours", "sixes"]
    buckets = sorted(set(ref_by_bucket) | set(tbl_by_bucket))
    mismatches = []
    for bk in buckets:
        ref = ref_by_bucket.get(bk, [0] * 6)
        tbl = tbl_by_bucket.get(bk, [0] * 6)
        for j, nm in enumerate(names):
            if ref[j] != tbl[j]:
                mismatches.append(f"bucket {bk} {nm}: table={tbl[j]} deliveries={ref[j]}")
    all_passed &= check(
        f"per-bucket {names} match deliveries across {len(buckets)} buckets",
        not mismatches,
        "; ".join(mismatches[:8]),
    )

    # 3. Spot-check: the biggest IPL-2016 innings sits in the bucket
    #    derive_positions assigns it (ties a concrete row to the convention).
    print("\n  3. Spot-check — top-scoring IPL 2016 innings:")
    top = conn.execute(
        """SELECT ibp.batter_id, ibp.innings_id, ibp.runs, ibp.position_bucket
           FROM inningsbatterperf ibp
           JOIN innings i ON i.id = ibp.innings_id
           JOIN match m ON m.id = i.match_id
           WHERE m.gender = ? AND m.event_name = ? AND m.season = ?
             AND i.super_over = 0
           ORDER BY ibp.runs DESC LIMIT 1""",
        (SCOPE_GENDER, SCOPE_TOURNAMENT, SCOPE_SEASON),
    ).fetchone()
    expected_bucket = ref_bucket.get((top["batter_id"], top["innings_id"]))
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
