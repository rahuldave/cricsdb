"""Populate playerscopestats_fielding_position — per (fielder, dismissed-batter-position) aggregates.

Phase 2c of the player-baselines rollout. See
`internal_docs/spec-player-compare-average.md` §4.4 + §7 Phase 2c.
One row per (person_id [fielder], scope_key, position_bucket [the
DISMISSED batter's merged-opener bucket]); the scope_key matches the
parent PlayerScopeStats row's hash of (tournament || season || gender
|| team_type).

Conventions (CLAUDE.md):

  - **Convention 3**: `catches` includes caught_and_bowled —
    predicate is `kind IN ('caught', 'caught_and_bowled')`. The c&b
    sub-count is NOT broken out separately here; it's already folded
    into the catches headline.

  - **Substitute fielders EXCLUDED** (is_substitute = 0). This child
    table feeds distribution-side consumers (cohort baseline + per-
    fielder histogram); the per-match denominator is matchplayer-
    based, so substitute appearances would miscalibrate. The
    asymmetry is structural, not normative — `/fielders/leaders`
    keeps subs in for the volume headline.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_fielding_position.py

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)

Auto-called by import_data.py (full) and update_recent.py
(incremental) immediately after the per-over child populate.

Position derivation reuses api.innings_positions.derive_positions —
the same helper Phase 1.5 extracted; the dismissed batter's position
in their innings becomes the bucket assignment.
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
    FieldingCredit, PlayerScopeStatsFieldingPosition,
)
from api.innings_positions import derive_positions
from scripts.populate_playerscopestats_position import position_to_bucket
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")


class _Acc:
    __slots__ = ("catches", "stumpings", "run_outs")

    def __init__(self):
        self.catches = 0
        self.stumpings = 0
        self.run_outs = 0

    def to_row(self, person_id: str, scope_key: str, bucket: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "position_bucket": bucket,
            "catches": self.catches,
            "stumpings": self.stumpings,
            "run_outs": self.run_outs,
            "dismissals": self.catches + self.stumpings + self.run_outs,
        }


async def _ensure_tables(db, incremental: bool = False):
    """Register tables; create indexes only on full rebuild."""
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)

    idx = {} if incremental else {
        "indexes": [
            ("scope_key", "position_bucket"),
            "scope_key",
        ],
    }
    return await db.create(
        PlayerScopeStatsFieldingPosition,
        pk=["person_id", "scope_key", "position_bucket"],
        if_not_exists=True,
        **idx,
    )


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str, int], _Acc]:
    """Aggregate per (fielder_id, scope_key, dismissed-batter-bucket).

    If match_ids is None, aggregates over every regular match.
    """
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

    # Pass 1: derive positions per innings (cached, so we don't re-
    # fetch deliveries when looking up the dismissed batter's bucket
    # in pass 2).
    positions_by_innings: dict[int, dict[str, int]] = {}
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        d_rows = await db.q(f"""
            SELECT innings_id, over_number, delivery_index, id,
                   batter_id, non_striker_id
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
            positions_by_innings[iid] = derive_positions(ds)

    # Pass 2: fielding credits — for each non-substitute credit, look
    # up the dismissed batter's bucket via the cached positions and
    # accumulate by kind.
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        fc_rows = await db.q(f"""
            SELECT fc.fielder_id, fc.kind, fc.is_substitute,
                   w.player_out_id, d.innings_id
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN wicket w   ON w.id  = fc.wicket_id
            WHERE fc.fielder_id IS NOT NULL
              AND COALESCE(fc.is_substitute, 0) = 0
              AND d.innings_id IN ({sub_list})
        """)
        for fc in fc_rows:
            fielder = fc["fielder_id"]
            pout = fc["player_out_id"]
            kind = fc["kind"]
            iid = fc["innings_id"]
            if pout is None:
                continue
            positions = positions_by_innings.get(iid)
            if positions is None:
                continue
            pos = positions.get(pout)
            if pos is None:
                # Dismissed batter never appeared as striker or non-
                # striker in this innings — shouldn't happen in
                # practice but skip defensively.
                continue
            bucket = position_to_bucket(pos)
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            acc = get_acc(fielder, scope_key, bucket)
            # Convention 3: caught + caught_and_bowled both count as catches.
            if kind in ("caught", "caught_and_bowled"):
                acc.catches += 1
            elif kind == "stumped":
                acc.stumpings += 1
            elif kind == "run_out":
                acc.run_outs += 1
            # Other kinds (e.g. retired) are not in fieldingcredit by
            # construction; ignore any anomalies.

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
    """Truncate and rebuild from every regular match."""
    print("Populating playerscopestats_fielding_position (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsfieldingposition'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestatsfieldingposition")

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (fielder, scope_key, bucket) cells aggregated")

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
    """Recompute rows touched by the new matches.

    Same scope-recompute strategy as the parent PlayerScopeStats
    populate.
    """
    if not new_match_ids:
        print("playerscopestats_fielding_position: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_fielding_position for {len(new_match_ids)} new matches…")
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
        f"SELECT COUNT(*) AS c FROM playerscopestatsfieldingposition WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(f"DELETE FROM playerscopestatsfieldingposition WHERE scope_key IN ({sk_list})")

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

    print(f"  playerscopestats_fielding_position: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(description="Populate playerscopestats_fielding_position").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
