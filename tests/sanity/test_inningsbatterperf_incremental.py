"""Sanity: the INCREMENTAL records-aggregate populate fills position_bucket
+ dots, not just the full rebuild.

D11 of spec-player-baseline-aux-fallback.md is explicit: incremental
ingest (update_recent.py → populate_records_aggregates.populate_incremental)
must fill the new columns too. Both paths funnel through
_populate_innings_batter_perf, which now runs the derive_positions()
second pass — this test proves the incremental path actually triggers it.

Strategy (no network — exercises the real code path on a /tmp copy):
  1. Copy the working DB to /tmp (never mutate the original).
  2. Pick a few matches, ZERO their inningsbatterperf.position_bucket +
     dots (simulating the pre-fill seed state) so a regression where the
     incremental path skips the Python pass would leave them at 0.
  3. Run populate_incremental(db, match_ids) — it DELETE+reinserts those
     rows through _populate_innings_batter_perf.
  4. Assert the reinserted rows have position_bucket in 1..10 (no 0-leak)
     and position_bucket + dots matching a from-deliveries derivation.

Usage:
  uv run python tests/sanity/test_inningsbatterperf_incremental.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sqlite3
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
SRC_DB = os.path.join(PROJECT_ROOT, "cricket.db")
TMP_DB = "/tmp/cricket-ibp-incr-test.db"

from deebase import Database
from api.innings_positions import derive_positions
from scripts.populate_playerscopestats_position import position_to_bucket
from scripts.populate_records_aggregates import populate_incremental


def _reference(conn: sqlite3.Connection, inn_ids: list[int]):
    """From-deliveries (batter, innings) -> (bucket, dots) over inn_ids."""
    ref: dict[tuple, tuple[int, int]] = {}
    for iid in inn_ids:
        ds = conn.execute(
            """SELECT batter_id, non_striker_id, runs_batter, runs_total,
                      extras_wides, extras_noballs
               FROM delivery WHERE innings_id = ?
               ORDER BY over_number, delivery_index, id""",
            (iid,),
        ).fetchall()
        positions = derive_positions(ds)
        dots: dict[str, int] = defaultdict(int)
        for d in ds:
            b = d["batter_id"]
            if b is None:
                continue
            if (d["extras_wides"] == 0 and d["extras_noballs"] == 0
                    and d["runs_batter"] == 0 and d["runs_total"] == 0):
                dots[b] += 1
        for b in {d["batter_id"] for d in ds if d["batter_id"] is not None}:
            ref[(b, iid)] = (position_to_bucket(positions[b]), dots[b])
    return ref


async def _run(db, match_ids):
    await db.q("PRAGMA journal_mode = WAL")
    # Zero the new columns for these matches' rows so a skipped Python
    # pass would be visible as a 0-leak after the reinsert.
    mlist = ",".join(str(m) for m in match_ids)
    await db.q(f"""
        UPDATE inningsbatterperf SET position_bucket = 0, dots = 0
        WHERE innings_id IN (SELECT id FROM innings WHERE match_id IN ({mlist}))
    """)
    await populate_incremental(db, match_ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=SRC_DB)
    args = parser.parse_args()
    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        return 1

    print(f"Sanity: inningsbatterperf incremental fill (copy of {args.db})")
    shutil.copy(args.db, TMP_DB)

    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    # Pick a handful of recent matches that have batting innings.
    match_ids = [r["id"] for r in conn.execute(
        """SELECT DISTINCT m.id
           FROM match m JOIN innings i ON i.match_id = m.id
           JOIN inningsbatterperf ibp ON ibp.innings_id = i.id
           ORDER BY m.id DESC LIMIT 5"""
    ).fetchall()]
    inn_ids = [r["id"] for r in conn.execute(
        f"SELECT id FROM innings WHERE match_id IN ({','.join(str(m) for m in match_ids)})"
    ).fetchall()]
    print(f"  matches={match_ids} innings={len(inn_ids)}")
    expected = _reference(conn, inn_ids)
    conn.close()

    db = Database(f"sqlite+aiosqlite:///{TMP_DB}")
    asyncio.run(_run(db, match_ids))

    conn = sqlite3.connect(TMP_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""SELECT batter_id, innings_id, position_bucket, dots
            FROM inningsbatterperf
            WHERE innings_id IN ({','.join(str(i) for i in inn_ids)})"""
    ).fetchall()
    conn.close()

    all_passed = True
    zero_leak = [r for r in rows if r["position_bucket"] == 0]
    ok = len(rows) > 0 and not zero_leak
    print(f"  [{'PASS' if ok else 'FAIL'}] reinserted {len(rows)} rows, no position_bucket 0-leak"
          + ("" if ok else f" (zeros={len(zero_leak)})"))
    all_passed &= ok

    mismatches = []
    for r in rows:
        exp = expected.get((r["batter_id"], r["innings_id"]))
        if exp is None or (r["position_bucket"], r["dots"]) != exp:
            mismatches.append(
                f"{r['batter_id']}@{r['innings_id']}: table=({r['position_bucket']},{r['dots']}) exp={exp}"
            )
    ok = not mismatches
    print(f"  [{'PASS' if ok else 'FAIL'}] position_bucket + dots match deliveries for all rows"
          + ("" if ok else "\n         " + "; ".join(mismatches[:6])))
    all_passed &= ok

    print()
    print("ALL PASS" if all_passed else "SOME FAILURES — see above")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
