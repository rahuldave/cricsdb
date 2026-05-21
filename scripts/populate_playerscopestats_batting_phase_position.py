"""Populate playerscopestats_batting_phase_position — position × phase
per-batter aggregates.

Tier 3 of internal_docs/spec-apples-to-apples-baselines.md. Mirrors
populate_playerscopestats_batting_phase.py, but each row is keyed by
(person_id, scope_key, phase_bucket, position_bucket) — 3 phases × 10
position buckets per (person, scope), up to 30 rows.

Used by the position-weighted /by-phase cohort path in
compute_players_batting_by_phase: per-bucket per-phase rates are
convex-combined by the player's per-phase position mix (since a
batter can have different "positions" in different phases — e.g.
came in mid-PP at #5 then bats most of the death overs).

For this rollout we use the **innings-level position** (the
derive_positions result for the whole innings) as the position
attribution for ALL phases the batter played in that innings, not a
per-phase first-ball-faced position. Rationale: simpler + matches the
PlayerScopeStatsPosition table's contract (so chips read consistently).
Within-phase position drift is rare and the bias is small.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_batting_phase_position.py

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Same scope-recompute strategy as siblings.

Auto-called by import_data.py + update_recent.py alongside the other
per-bucket child populates.
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
    PlayerScopeStatsBattingPhasePosition,
)
from api.innings_positions import derive_positions
from scripts.populate_player_scope_stats import make_scope_key
from scripts.populate_playerscopestats_position import position_to_bucket
from scripts.populate_playerscopestats_batting_phase import phase_bucket

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

BATTER_DISMISSAL_EXCLUDED = {"retired hurt", "retired out"}


class _Acc:
    __slots__ = (
        "innings_set", "balls", "runs", "dots",
        "fours", "sixes", "dismissals",
    )

    def __init__(self):
        self.innings_set: set[int] = set()
        self.balls = 0
        self.runs = 0
        self.dots = 0
        self.fours = 0
        self.sixes = 0
        self.dismissals = 0

    def to_row(self, person_id: str, scope_key: str,
               phase_b: int, position_b: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "phase_bucket": phase_b,
            "position_bucket": position_b,
            "innings_in_phase": len(self.innings_set),
            "balls_in_phase": self.balls,
            "runs_in_phase": self.runs,
            "dots_in_phase": self.dots,
            "fours_in_phase": self.fours,
            "sixes_in_phase": self.sixes,
            "boundaries_in_phase": self.fours + self.sixes,
            "dismissals_in_phase": self.dismissals,
        }


async def _ensure_tables(db, incremental: bool = False):
    """Register tables; create indexes only on full rebuild."""
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)

    idx = {} if incremental else {
        "indexes": [
            ("scope_key", "phase_bucket", "position_bucket"),
            "scope_key",
        ],
    }
    return await db.create(
        PlayerScopeStatsBattingPhasePosition,
        pk=["person_id", "scope_key", "phase_bucket", "position_bucket"],
        if_not_exists=True,
        **idx,
    )


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str, int, int], _Acc]:
    """Aggregate per (person_id, scope_key, phase_bucket, position_bucket)."""
    if match_ids is not None and not match_ids:
        return {}

    if match_ids is None:
        match_rows = await db.q("""
            SELECT id, event_name AS tournament, season, gender, team_type
            FROM match
        """)
    else:
        id_list = ",".join(str(m) for m in match_ids)
        match_rows = await db.q(f"""
            SELECT id, event_name AS tournament, season, gender, team_type
            FROM match
            WHERE id IN ({id_list})
        """)
    match_meta: dict[int, dict] = {}
    for r in match_rows:
        match_meta[r["id"]] = {
            "scope_key": make_scope_key(
                r["tournament"], r["season"] or "",
                r["gender"] or "", r["team_type"] or "",
            ),
        }
    if not match_meta:
        return {}

    mid_list = ",".join(str(i) for i in match_meta.keys())
    innings_rows = await db.q(f"""
        SELECT id, match_id
        FROM innings
        WHERE super_over = 0
          AND match_id IN ({mid_list})
    """)
    innings_match: dict[int, int] = {r["id"]: r["match_id"] for r in innings_rows}
    innings_ids = list(innings_match.keys())
    if not innings_ids:
        return {}

    accs: dict[tuple[str, str, int, int], _Acc] = {}

    def get_acc(person_id: str, scope_key: str,
                phase_b: int, position_b: int) -> _Acc:
        key = (person_id, scope_key, phase_b, position_b)
        acc = accs.get(key)
        if acc is None:
            acc = _Acc()
            accs[key] = acc
        return acc

    # Pass 1: deliveries — derive positions once per innings, then
    # accumulate batting tallies into the (phase, position) per-batter
    # cells.
    positions_by_innings: dict[int, dict[str, int]] = {}
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        d_rows = await db.q(f"""
            SELECT id, innings_id, over_number, delivery_index,
                   batter_id, non_striker_id,
                   runs_batter, runs_total,
                   extras_wides, extras_noballs
            FROM delivery
            WHERE innings_id IN ({sub_list})
            ORDER BY innings_id, over_number, delivery_index, id
        """)
        deliveries_by_innings: dict[int, list[dict]] = defaultdict(list)
        for d in d_rows:
            deliveries_by_innings[d["innings_id"]].append(d)

        for iid in sub:
            ds = deliveries_by_innings.get(iid, [])
            if not ds:
                continue
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            positions = derive_positions(ds)
            positions_by_innings[iid] = positions

            for d in ds:
                bid = d["batter_id"]
                if bid is None:
                    continue
                pos = positions.get(bid)
                if pos is None:
                    continue
                legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
                if not legal:
                    continue
                pos_b = position_to_bucket(pos)
                phase_b = phase_bucket(d["over_number"])
                acc = get_acc(bid, scope_key, phase_b, pos_b)
                acc.innings_set.add(iid)
                acc.balls += 1
                rb = d["runs_batter"]
                acc.runs += rb
                if rb == 0 and d["runs_total"] == 0:
                    acc.dots += 1
                if rb == 4:
                    acc.fours += 1
                elif rb == 6:
                    acc.sixes += 1

    # Pass 2: wickets — credit the dismissed batter's (phase, position)
    # bucket.
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        w_rows = await db.q(f"""
            SELECT w.kind, w.player_out_id, d.innings_id, d.over_number
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.innings_id IN ({sub_list})
        """)
        for w in w_rows:
            kind = w["kind"]
            pout = w["player_out_id"]
            if pout is None or kind in BATTER_DISMISSAL_EXCLUDED:
                continue
            iid = w["innings_id"]
            positions = positions_by_innings.get(iid)
            if positions is None:
                continue
            pos = positions.get(pout)
            if pos is None:
                continue
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            pos_b = position_to_bucket(pos)
            phase_b = phase_bucket(w["over_number"])
            get_acc(pout, scope_key, phase_b, pos_b).dismissals += 1

    return accs


# ============================================================
# Write paths
# ============================================================

async def _flush(db, table, rows: list[dict]) -> int:
    if not rows:
        return 0
    sa_table = table.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), rows)
    return len(rows)


async def populate_full(db) -> int:
    """Truncate playerscopestats_batting_phase_position and rebuild."""
    print("Populating playerscopestats_batting_phase_position (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsbattingphaseposition'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestatsbattingphaseposition")

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope, phase, position) cells aggregated")

    rows: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, phase_b, pos_b), acc in accs.items():
        rows.append(acc.to_row(person_id, scope_key, phase_b, pos_b))
        if len(rows) >= batch:
            total += await _flush(db, table, rows)
            rows = []
    total += await _flush(db, table, rows)

    elapsed = time.time() - start
    print(f"  Inserted {total} rows in {elapsed:.1f}s")
    return total


async def populate_incremental(db, new_match_ids: list[int]) -> int:
    if not new_match_ids:
        print("playerscopestats_batting_phase_position: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_batting_phase_position for {len(new_match_ids)} new matches…")
    table = await _ensure_tables(db, incremental=True)

    id_list = ",".join(str(m) for m in new_match_ids)
    rows = await db.q(f"""
        SELECT DISTINCT event_name AS tournament, season, gender, team_type
        FROM match
        WHERE id IN ({id_list})
    """)
    touched_scopes = [
        (r["tournament"], r["season"] or "", r["gender"] or "", r["team_type"] or "")
        for r in rows
    ]
    if not touched_scopes:
        print("  no scopes resolved, skipping")
        return 0

    scope_keys = [make_scope_key(*s) for s in touched_scopes]
    print(f"  {len(scope_keys)} scopes touched")

    where_parts = []
    params: dict = {}
    for i, (tn, se, ge, tt) in enumerate(touched_scopes):
        if tn is None:
            tn_clause = "event_name IS NULL"
        else:
            tn_clause = f"event_name = :tn{i}"
            params[f"tn{i}"] = tn
        where_parts.append(
            f"({tn_clause} AND season = :se{i} AND gender = :ge{i} AND team_type = :tt{i})"
        )
        params[f"se{i}"] = se
        params[f"ge{i}"] = ge
        params[f"tt{i}"] = tt
    where_sql = " OR ".join(where_parts)
    match_rows = await db.q(f"SELECT id FROM match WHERE {where_sql}", params)
    affected_match_ids = [r["id"] for r in match_rows]
    print(f"  {len(affected_match_ids)} total matches in touched scopes")

    accs = await _aggregate_matches(db, match_ids=affected_match_ids)

    sk_list = ",".join(f"'{sk}'" for sk in scope_keys)
    deleted_rows = await db.q(
        f"SELECT COUNT(*) AS c FROM playerscopestatsbattingphaseposition WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(
        f"DELETE FROM playerscopestatsbattingphaseposition WHERE scope_key IN ({sk_list})"
    )

    rows_to_insert: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, phase_b, pos_b), acc in accs.items():
        if scope_key not in scope_keys:
            continue
        rows_to_insert.append(acc.to_row(person_id, scope_key, phase_b, pos_b))
        if len(rows_to_insert) >= batch:
            total += await _flush(db, table, rows_to_insert)
            rows_to_insert = []
    total += await _flush(db, table, rows_to_insert)

    print(f"  playerscopestats_batting_phase_position: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(
        description="Populate playerscopestats_batting_phase_position"
    ).parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
