"""Populate playerscopestats_position — per-position batting aggregates.

Phase 2a of the player-baselines rollout. See
`internal_docs/spec-player-compare-average.md` §4.2 + §7 Phase 2a.
One row per (person_id, scope_key, position_bucket); the scope_key
matches the parent PlayerScopeStats row's hash of (tournament ||
season || gender || team_type).

position_bucket semantics: 1 = opener (positions 1 + 2 merged because
`derive_positions` makes the split arbitrary on ball 1); 2 = #3,
3 = #4, …, 10 = #11. Position 11 absorbs anything beyond 11 distinct
batters in one innings (rare 12th-man / concussion-sub edge cases).

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_position.py
    Truncates the table and rebuilds from every regular innings.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes only the rows for scope_keys touched by the new
    matches (same scope-recompute pattern as the parent populate).

Auto-called by import_data.py (full) and update_recent.py
(incremental) immediately after the parent PlayerScopeStats populate.

Position derivation is delegated to api.innings_positions —
the same helper drives PlayerScopeStats, this child table, and (later)
the fielding dismissed-batter-position child table; computing the
vector once per innings and reusing is the contract.

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
    PlayerScopeStatsPosition,
)
from api.innings_positions import derive_positions
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

BATTER_DISMISSAL_EXCLUDED = {"retired hurt", "retired out"}


def position_to_bucket(pos: int) -> int:
    """Map innings position 1..11 to the merged-opener bucket 1..10.

    1 or 2 → bucket 1 (opener); 3 → 2; 4 → 3; … 11 → 10.
    """
    return 1 if pos <= 2 else pos - 1


class _Acc:
    __slots__ = (
        "innings_set", "runs", "legal_balls", "dots",
        "fours", "sixes", "dismissals",
        "thirties", "fifties", "hundreds", "ducks",
        "failures_10", "seventies",
    )

    def __init__(self):
        self.innings_set: set[int] = set()
        self.runs = 0
        self.legal_balls = 0
        self.dots = 0
        self.fours = 0
        self.sixes = 0
        self.dismissals = 0
        # Tier 1 of spec-apples-to-apples-baselines.md — per-position
        # milestone counts. Filled by the post-aggregation pass that
        # walks per-innings (batter, runs).
        self.thirties = 0
        self.fifties = 0
        self.hundreds = 0
        self.ducks = 0
        # PT1 of spec-prob-baselines.md — extra per-position milestone
        # buckets for the batting ProbChip cohort baselines (failures
        # threshold matches the P(≤10) chip predicate).
        self.failures_10 = 0
        self.seventies = 0

    def to_row(self, person_id: str, scope_key: str, bucket: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "position_bucket": bucket,
            "innings": len(self.innings_set),
            "runs": self.runs,
            "legal_balls": self.legal_balls,
            "dots": self.dots,
            "fours": self.fours,
            "sixes": self.sixes,
            "dismissals": self.dismissals,
            "thirties": self.thirties,
            "fifties": self.fifties,
            "hundreds": self.hundreds,
            "ducks": self.ducks,
            "failures_10": self.failures_10,
            "seventies": self.seventies,
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
            ("scope_key", "position_bucket"),
            "scope_key",
        ],
    }
    table = await db.create(
        PlayerScopeStatsPosition,
        pk=["person_id", "scope_key", "position_bucket"],
        if_not_exists=True,
        **idx,
    )
    # Idempotent column migrations for per-position milestone bucketing
    # (Tier 1 of spec-apples-to-apples-baselines.md). Pre-existing DBs
    # that pre-date this populate version get the new columns appended;
    # new DBs created by `db.create` above already have them in schema.
    for col in ("thirties", "fifties", "hundreds", "ducks",
                "failures_10", "seventies"):
        try:
            await db.q(
                f"ALTER TABLE playerscopestatsposition ADD COLUMN {col} "
                f"INTEGER NOT NULL DEFAULT 0"
            )
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise
    return table


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str, int], _Acc]:
    """Aggregate per (person_id, scope_key, position_bucket) over the given matches.

    If match_ids is None, aggregates over every regular match.
    """
    if match_ids is not None and not match_ids:
        return {}

    # Match metadata keyed by id.
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

    # Tier 1 milestone bucketing (apples-to-apples). Stage per-innings
    # (batter, runs) and dismissed-set during the deliveries + wickets
    # passes, then drain into _Acc.thirties/fifties/hundreds/ducks at
    # the end. Mirrors the parent populate's milestone pass but keyed
    # to the per-position bucket so the cohort baseline can convex-
    # combine over positions.
    innings_runs: dict[tuple[str, int], int] = {}     # (batter_id, iid) -> runs this innings
    innings_dismissed: set[tuple[str, int]] = set()   # (batter_id, iid) — dismissed this innings (excluding retired)

    # Pass 1: deliveries — derive positions once per innings, then
    # accumulate batting tallies into the per-bucket _Acc. The
    # positions dict is saved so pass 2 (wickets) can look up the
    # dismissed batter's bucket without re-fetching deliveries.
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

            # Innings credit per (person, bucket). Also seed per-innings
            # runs at 0 so non-strikers who never face a legal ball
            # still get a milestone-bucket row at the end (relevant for
            # ducks). Mirrors the parent populate's seeding pattern.
            for pid, pos in positions.items():
                bucket = position_to_bucket(pos)
                get_acc(pid, scope_key, bucket).innings_set.add(iid)
                innings_runs.setdefault((pid, iid), 0)

            # Per-delivery: only the batter contributes; non_striker
            # already counted via the innings credit above.
            for d in ds:
                bid = d["batter_id"]
                if bid is None:
                    continue
                pos = positions.get(bid)
                if pos is None:
                    continue
                bucket = position_to_bucket(pos)
                legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
                if not legal:
                    continue
                acc = get_acc(bid, scope_key, bucket)
                acc.legal_balls += 1
                rb = d["runs_batter"]
                acc.runs += rb
                # Track per-innings runs for milestone bucketing (Tier 1).
                # Counted only on legal balls — matches the runs
                # numerator above; mirrors parent populate semantics.
                ir_key = (bid, iid)
                innings_runs[ir_key] = innings_runs.get(ir_key, 0) + rb
                # Dot rule matches parent populate: legal AND
                # runs_batter=0 AND runs_total=0.
                if rb == 0 and d["runs_total"] == 0:
                    acc.dots += 1
                if rb == 4:
                    acc.fours += 1
                elif rb == 6:
                    acc.sixes += 1

    # Pass 2: wickets — credit the dismissed batter's bucket.
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        w_rows = await db.q(f"""
            SELECT w.kind, w.player_out_id, d.innings_id
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.innings_id IN ({sub_list})
        """)
        for w in w_rows:
            iid = w["innings_id"]
            kind = w["kind"]
            pout = w["player_out_id"]
            if pout is None or kind in BATTER_DISMISSAL_EXCLUDED:
                continue
            positions = positions_by_innings.get(iid)
            if positions is None:
                continue
            pos = positions.get(pout)
            if pos is None:
                continue
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            bucket = position_to_bucket(pos)
            get_acc(pout, scope_key, bucket).dismissals += 1
            innings_dismissed.add((pout, iid))

    # Tier 1 milestone post-pass — bucket per-innings runs into 30s /
    # 50s / 100s / ducks per position bucket. Mirrors the parent
    # populate's milestone pass; bucket attribution uses the batter's
    # innings-start position (the same value `derive_positions`
    # produced and that fed dismissal credit above).
    for (pid, iid), runs in innings_runs.items():
        positions = positions_by_innings.get(iid)
        if positions is None:
            continue
        pos = positions.get(pid)
        if pos is None:
            continue
        mid = innings_match.get(iid)
        if mid is None:
            continue
        scope_key = match_meta[mid]["scope_key"]
        bucket = position_to_bucket(pos)
        acc = accs.get((pid, scope_key, bucket))
        if acc is None:
            continue
        if runs >= 100:
            acc.hundreds += 1
        elif runs >= 50:
            acc.fifties += 1
        elif runs >= 30:
            acc.thirties += 1
        # PT1 of spec-prob-baselines.md — non-elif counters layered on
        # top of the elif chain above. `seventies` overlaps `fifties`
        # (both count 70 ≤ runs < 100) so `fifties` keeps the
        # conventional "50-99" cricket meaning that Tier 1 (apples-to-
        # apples) baselines and existing API consumers depend on.
        # `failures_10` is independent of the chain; ducks (runs == 0)
        # are a subset.
        if 70 <= runs < 100:
            acc.seventies += 1
        if runs <= 10:
            acc.failures_10 += 1
        if runs == 0 and (pid, iid) in innings_dismissed:
            acc.ducks += 1

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
    """Truncate playerscopestats_position and rebuild from every regular match."""
    print("Populating playerscopestats_position (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsposition'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestatsposition")

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope_key, bucket) cells aggregated")

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
    populate: identify scope_keys touched by the new matches, find ALL
    matches in those scopes, recompute the (person, scope, bucket)
    aggregates from scratch over that set, then delete + reinsert.
    """
    if not new_match_ids:
        print("playerscopestats_position: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_position for {len(new_match_ids)} new matches…")
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

    # Delete old rows for every touched scope_key, then insert fresh.
    sk_list = ",".join(f"'{sk}'" for sk in scope_keys)
    deleted_rows = await db.q(
        f"SELECT COUNT(*) AS c FROM playerscopestatsposition WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(f"DELETE FROM playerscopestatsposition WHERE scope_key IN ({sk_list})")

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

    print(f"  playerscopestats_position: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(description="Populate playerscopestats_position").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
