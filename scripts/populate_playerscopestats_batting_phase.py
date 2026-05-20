"""Populate playerscopestats_batting_phase — per-phase batting aggregates.

Spec: `internal_docs/spec-player-baseline-parity.md` §3.1.1.
One row per (person_id, scope_key, phase_bucket); the scope_key matches
the parent PlayerScopeStats row's hash of (tournament || season ||
gender || team_type).

phase_bucket: 1=powerplay (overs 0-5), 2=middle (6-14), 3=death (15-19).
Matches the parent populate's `_phase` boundaries and the team-side
phase conventions in `api/routers/teams.py`.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_batting_phase.py
    Truncates the table and rebuilds from every regular innings.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes only the rows for scope_keys touched by the new matches
    (same scope-recompute pattern as the parent and sibling populates).

Auto-called by import_data.py (full) and update_recent.py (incremental)
immediately after the position child populate.

Aggregation excluded-kinds match the parent:
  - Batter dismissals exclude 'retired hurt' / 'retired out'
    (BATTER_DISMISSAL_EXCLUDED).
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
    PlayerScopeStatsBattingPhase,
)
from api.innings_positions import derive_positions
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

BATTER_DISMISSAL_EXCLUDED = {"retired hurt", "retired out"}


def phase_bucket(over_number_0idx: int) -> int:
    """Map a 0-indexed over_number to the phase bucket.

    1 = powerplay (overs 0-5), 2 = middle (6-14), 3 = death (15-19).
    Matches the parent populate's `_phase` boundaries.
    """
    if over_number_0idx <= 5:
        return 1
    if over_number_0idx <= 14:
        return 2
    return 3


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

    def to_row(self, person_id: str, scope_key: str, bucket: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "phase_bucket": bucket,
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
            ("scope_key", "phase_bucket"),
            "scope_key",
        ],
    }
    return await db.create(
        PlayerScopeStatsBattingPhase,
        pk=["person_id", "scope_key", "phase_bucket"],
        if_not_exists=True,
        **idx,
    )


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str, int], _Acc]:
    """Aggregate per (person_id, scope_key, phase_bucket) over the given matches."""
    if match_ids is not None and not match_ids:
        return {}

    # Match metadata.
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

    # Innings list (regular only).
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

    accs: dict[tuple[str, str, int], _Acc] = {}

    def get_acc(person_id: str, scope_key: str, bucket: int) -> _Acc:
        key = (person_id, scope_key, bucket)
        acc = accs.get(key)
        if acc is None:
            acc = _Acc()
            accs[key] = acc
        return acc

    # Pass 1: deliveries — per (batter, scope, phase) accumulator.
    # innings_set captures the set of innings where the batter faced ≥1
    # legal ball in this phase.
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        d_rows = await db.q(f"""
            SELECT id, innings_id, over_number, delivery_index,
                   batter_id, runs_batter, runs_total,
                   extras_wides, extras_noballs
            FROM delivery
            WHERE innings_id IN ({sub_list})
        """)
        for d in d_rows:
            bid = d["batter_id"]
            if bid is None:
                continue
            legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
            if not legal:
                continue
            iid = d["innings_id"]
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            bucket = phase_bucket(d["over_number"])
            acc = get_acc(bid, scope_key, bucket)
            acc.innings_set.add(iid)
            acc.balls += 1
            rb = d["runs_batter"]
            acc.runs += rb
            # Dot rule matches parent populate: legal AND
            # runs_batter=0 AND runs_total=0.
            if rb == 0 and d["runs_total"] == 0:
                acc.dots += 1
            if rb == 4:
                acc.fours += 1
            elif rb == 6:
                acc.sixes += 1

    # Pass 2: wickets — credit the dismissed batter's phase bucket.
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
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            bucket = phase_bucket(w["over_number"])
            get_acc(pout, scope_key, bucket).dismissals += 1

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
    """Truncate playerscopestats_batting_phase and rebuild from every regular match."""
    print("Populating playerscopestats_batting_phase (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='playerscopestatsbattingphase'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestatsbattingphase")

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope_key, phase) cells aggregated")

    rows: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, bucket), acc in accs.items():
        rows.append(acc.to_row(person_id, scope_key, bucket))
        if len(rows) >= batch:
            total += await _flush(db, table, rows)
            rows = []
    total += await _flush(db, table, rows)

    elapsed = time.time() - start
    print(f"  Inserted {total} rows in {elapsed:.1f}s")
    return total


async def populate_incremental(db, new_match_ids: list[int]) -> int:
    """Recompute rows touched by the new matches (scope-recompute strategy)."""
    if not new_match_ids:
        print("playerscopestats_batting_phase: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_batting_phase for {len(new_match_ids)} new matches…")
    table = await _ensure_tables(db, incremental=True)

    # Touched scopes.
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

    # Every match in each touched scope.
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
        f"SELECT COUNT(*) AS c FROM playerscopestatsbattingphase WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(f"DELETE FROM playerscopestatsbattingphase WHERE scope_key IN ({sk_list})")

    rows_to_insert: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, bucket), acc in accs.items():
        if scope_key not in scope_keys:
            continue
        rows_to_insert.append(acc.to_row(person_id, scope_key, bucket))
        if len(rows_to_insert) >= batch:
            total += await _flush(db, table, rows_to_insert)
            rows_to_insert = []
    total += await _flush(db, table, rows_to_insert)

    print(f"  playerscopestats_batting_phase: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(description="Populate playerscopestats_batting_phase").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
