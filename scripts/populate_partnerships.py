"""Populate the partnership table from ordered delivery + wicket data.

See `internal_docs/spec-team-stats.md` for the full spec. One row per on-field
batting partnership. `partnership_runs` includes all extras;
`partnership_balls` is legal balls only. Per-batter runs are off-the-bat.
`batter1` is the earlier-arriver (= survivor of the previous partnership;
= striker on first delivery for the opening stand).

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_partnerships.py
    Truncates partnership and repopulates from all non-super-over innings.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Rescans partnerships for the given matches only.

Called automatically by import_data.py (full) and update_recent.py
(incremental) after the keeper_assignment populate call.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import (
    Person, Match, MatchPlayer, Innings, Delivery, Wicket,
    FieldingCredit, KeeperAssignment, Partnership,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")


async def _ensure_tables(db, incremental: bool = False):
    """Register all tables with deebase so FK references resolve.

    In incremental mode, skip index creation (they already exist).
    """
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)
    await db.create(KeeperAssignment, pk="id", if_not_exists=True)

    idx = {} if incremental else {
        "indexes": [
            "innings_id", "batter1_id", "batter2_id",
            "wicket_number", "unbroken",
        ],
    }
    return await db.create(Partnership, pk="id", if_not_exists=True, **idx)


def _process_innings(innings_id, deliveries, wickets_by_delivery) -> list[dict]:
    """Scan one innings's ordered deliveries + emit partnership rows.

    Returns a list of row dicts ready for bulk insert.
    """
    if not deliveries:
        return []

    rows = []
    d0 = deliveries[0]

    # Open the first partnership: striker + non-striker on ball 1.
    # batter1 = striker (arbitrary for the opening stand).
    state = {
        "batter1_id": d0["batter_id"],
        "batter1_name": d0["batter"] or "",
        "batter2_id": d0["non_striker_id"],
        "batter2_name": d0["non_striker"] or "",
        "batter1_runs": 0, "batter1_balls": 0,
        "batter2_runs": 0, "batter2_balls": 0,
        "partnership_runs": 0, "partnership_balls": 0,
        "start_delivery_id": d0["id"],
    }
    wicket_count = 0
    # Between partnerships (after a wicket) we remember the survivor so
    # the next delivery's batter/non_striker can identify the newcomer.
    pending_survivor_id = None
    pending_survivor_name = None

    for d in deliveries:
        # If the previous delivery ended with a wicket, open a new partnership
        # now using this delivery's batter + non_striker.
        if state is None:
            pair = [
                (d["batter_id"], d["batter"] or ""),
                (d["non_striker_id"], d["non_striker"] or ""),
            ]
            # Survivor is whoever of the new pair matches pending_survivor.
            if pending_survivor_id is not None and pair[0][0] == pending_survivor_id:
                b1, b2 = pair[0], pair[1]
            elif pending_survivor_id is not None and pair[1][0] == pending_survivor_id:
                b1, b2 = pair[1], pair[0]
            elif pending_survivor_name and pair[0][1] == pending_survivor_name:
                b1, b2 = pair[0], pair[1]
            elif pending_survivor_name and pair[1][1] == pending_survivor_name:
                b1, b2 = pair[1], pair[0]
            else:
                # Survivor unidentifiable — fall back to the current striker
                # as batter1 (arbitrary).
                b1, b2 = pair[0], pair[1]
            state = {
                "batter1_id": b1[0], "batter1_name": b1[1],
                "batter2_id": b2[0], "batter2_name": b2[1],
                "batter1_runs": 0, "batter1_balls": 0,
                "batter2_runs": 0, "batter2_balls": 0,
                "partnership_runs": 0, "partnership_balls": 0,
                "start_delivery_id": d["id"],
            }
            pending_survivor_id = None
            pending_survivor_name = None

        legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
        state["partnership_runs"] += d["runs_total"]
        if legal:
            state["partnership_balls"] += 1

        striker_id = d["batter_id"]
        striker_name = d["batter"] or ""
        is_batter1 = (
            (striker_id is not None and striker_id == state["batter1_id"])
            or (striker_id is None and striker_name == state["batter1_name"])
        )
        if is_batter1:
            state["batter1_runs"] += d["runs_batter"]
            if legal:
                state["batter1_balls"] += 1
        else:
            state["batter2_runs"] += d["runs_batter"]
            if legal:
                state["batter2_balls"] += 1

        # Handle wicket(s) on this delivery. The common case is one wicket;
        # the rare two-wickets-on-one-ball case (e.g. striker caught +
        # non-striker run out same ball) is handled by emitting the first
        # partnership termination and a zero-run partnership for the
        # interstitial one, then letting the NEXT delivery identify the
        # new pair.
        wickets_here = wickets_by_delivery.get(d["id"], [])
        for i, w in enumerate(wickets_here):
            wicket_count += 1
            out_id = w["player_out_id"]
            out_name = w["player_out"] or ""
            b1_is_out = (
                (out_id is not None and out_id == state["batter1_id"])
                or (out_id is None and out_name == state["batter1_name"])
            )
            if b1_is_out:
                survivor_id = state["batter2_id"]
                survivor_name = state["batter2_name"]
            else:
                survivor_id = state["batter1_id"]
                survivor_name = state["batter1_name"]

            rows.append({
                "innings_id": innings_id,
                "wicket_number": wicket_count,
                "batter1_id": state["batter1_id"],
                "batter2_id": state["batter2_id"],
                "batter1_name": state["batter1_name"],
                "batter2_name": state["batter2_name"],
                "batter1_runs": state["batter1_runs"],
                "batter1_balls": state["batter1_balls"],
                "batter2_runs": state["batter2_runs"],
                "batter2_balls": state["batter2_balls"],
                "partnership_runs": state["partnership_runs"],
                "partnership_balls": state["partnership_balls"],
                "start_delivery_id": state["start_delivery_id"],
                "end_delivery_id": d["id"],
                "unbroken": False,
                "ended_by_kind": w["kind"],
            })

            if i < len(wickets_here) - 1:
                # Another wicket on the same delivery — open + immediately
                # close a zero-run partnership. batter2 unknown for now
                # (will be overwritten by the next delivery's pair); we
                # emit with survivor as batter1 and batter2 = NULL.
                state = {
                    "batter1_id": survivor_id,
                    "batter1_name": survivor_name,
                    "batter2_id": None,
                    "batter2_name": "",
                    "batter1_runs": 0, "batter1_balls": 0,
                    "batter2_runs": 0, "batter2_balls": 0,
                    "partnership_runs": 0, "partnership_balls": 0,
                    "start_delivery_id": d["id"],
                }
                # Loop continues; next iteration emits another row for
                # the next wicket on this delivery.
            else:
                state = None
                pending_survivor_id = survivor_id
                pending_survivor_name = survivor_name

    # Innings ended — emit unbroken partnership if state is still open.
    if state is not None:
        rows.append({
            "innings_id": innings_id,
            "wicket_number": None,
            "batter1_id": state["batter1_id"],
            "batter2_id": state["batter2_id"],
            "batter1_name": state["batter1_name"],
            "batter2_name": state["batter2_name"],
            "batter1_runs": state["batter1_runs"],
            "batter1_balls": state["batter1_balls"],
            "batter2_runs": state["batter2_runs"],
            "batter2_balls": state["batter2_balls"],
            "partnership_runs": state["partnership_runs"],
            "partnership_balls": state["partnership_balls"],
            "start_delivery_id": state["start_delivery_id"],
            "end_delivery_id": deliveries[-1]["id"],
            "unbroken": True,
            "ended_by_kind": None,
        })

    return rows


async def _load_innings_batch(db, innings_ids: list[int]):
    """Load deliveries + wickets for a batch of innings.

    Returns (deliveries_by_innings, wickets_by_delivery_by_innings).
    """
    if not innings_ids:
        return {}, {}
    id_list = ",".join(str(i) for i in innings_ids)

    delivery_rows = await db.q(f"""
        SELECT id, innings_id, over_number, delivery_index,
               batter_id, non_striker_id, batter, non_striker,
               runs_total, runs_batter, extras_wides, extras_noballs
        FROM delivery
        WHERE innings_id IN ({id_list})
        ORDER BY innings_id, over_number, delivery_index, id
    """)
    deliveries_by_innings: dict[int, list[dict]] = defaultdict(list)
    for d in delivery_rows:
        deliveries_by_innings[d["innings_id"]].append(d)

    delivery_ids = [d["id"] for d in delivery_rows]
    wickets_by_delivery_by_innings: dict[int, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    if delivery_ids:
        # Chunk wicket load in 20K-id batches to avoid overly-long SQL.
        chunk = 20000
        for start in range(0, len(delivery_ids), chunk):
            sub = delivery_ids[start:start + chunk]
            sub_list = ",".join(str(i) for i in sub)
            w_rows = await db.q(f"""
                SELECT w.id, w.delivery_id, w.kind,
                       w.player_out, w.player_out_id,
                       d.innings_id
                FROM wicket w
                JOIN delivery d ON d.id = w.delivery_id
                WHERE w.delivery_id IN ({sub_list})
                ORDER BY w.delivery_id, w.id
            """)
            for w in w_rows:
                wickets_by_delivery_by_innings[w["innings_id"]][w["delivery_id"]].append(w)

    return deliveries_by_innings, wickets_by_delivery_by_innings


async def _flush_batch(db, table, batch: list[dict]) -> int:
    if not batch:
        return 0
    sa_table = table.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), batch)
    return len(batch)


async def populate_full(db):
    """Truncate partnership and rebuild from every non-super-over innings."""
    print("Populating partnerships (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='partnership'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM partnership")

    innings_rows = await db.q("""
        SELECT id FROM innings WHERE super_over = 0 ORDER BY id
    """)
    all_innings_ids = [r["id"] for r in innings_rows]
    print(f"  {len(all_innings_ids)} regular innings to process")

    batch: list[dict] = []
    batch_size = 2000
    total = 0
    innings_batch_size = 500

    for i in range(0, len(all_innings_ids), innings_batch_size):
        sub = all_innings_ids[i:i + innings_batch_size]
        deliveries_by_innings, wickets_by_innings = await _load_innings_batch(db, sub)

        for iid in sub:
            rows = _process_innings(
                iid,
                deliveries_by_innings.get(iid, []),
                wickets_by_innings.get(iid, {}),
            )
            batch.extend(rows)
            if len(batch) >= batch_size:
                total += await _flush_batch(db, table, batch)
                batch = []

    total += await _flush_batch(db, table, batch)

    elapsed = time.time() - start
    print(f"  Inserted {total} partnerships in {elapsed:.1f}s")

    unbroken = await db.q("SELECT COUNT(*) as c FROM partnership WHERE unbroken = 1")
    ended = await db.q("SELECT COUNT(*) as c FROM partnership WHERE unbroken = 0")
    print(f"  ended: {ended[0]['c']}, unbroken: {unbroken[0]['c']}")

    return total


async def populate_incremental(db, new_match_ids: list[int]) -> int:
    """Rescan partnerships for the given matches (delete + reinsert)."""
    if not new_match_ids:
        print("Partnerships: no new matches, skipping")
        return 0

    print(f"Populating partnerships for {len(new_match_ids)} new matches...")
    table = await _ensure_tables(db, incremental=True)

    id_list = ",".join(str(m) for m in new_match_ids)
    innings_rows = await db.q(f"""
        SELECT id FROM innings
        WHERE match_id IN ({id_list}) AND super_over = 0
        ORDER BY id
    """)
    innings_ids = [r["id"] for r in innings_rows]
    if not innings_ids:
        print("  no innings found for these matches")
        return 0

    iid_list = ",".join(str(i) for i in innings_ids)
    await db.q(f"DELETE FROM partnership WHERE innings_id IN ({iid_list})")

    deliveries_by_innings, wickets_by_innings = await _load_innings_batch(db, innings_ids)

    batch: list[dict] = []
    batch_size = 2000
    total = 0
    for iid in innings_ids:
        rows = _process_innings(
            iid,
            deliveries_by_innings.get(iid, []),
            wickets_by_innings.get(iid, {}),
        )
        batch.extend(rows)
        if len(batch) >= batch_size:
            total += await _flush_batch(db, table, batch)
            batch = []
    total += await _flush_batch(db, table, batch)

    print(f"  Partnerships: +{total} rows from {len(innings_ids)} innings")
    return total


async def main():
    argparse.ArgumentParser(description="Populate partnership").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
