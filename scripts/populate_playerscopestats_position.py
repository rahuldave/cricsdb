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

D2 single source of truth (spec-batting-allball-runs-single-source.md
§5): this table is a pure rollup of inningsbatterperf, grouped on
person × position_bucket × scope fields. position_bucket already lives
on each inningsbatterperf row (filled by derive_positions in the records
populate), and not_out already excludes 'retired hurt' / 'retired out',
so the cohort is all-ball + dismissal-convention-correct by construction
and identical to the live (3b) aggregation reading the same table.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import (
    Person, Match, MatchPlayer, Innings, Delivery, Wicket,
    PlayerScopeStatsPosition,
)
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")


def position_to_bucket(pos: int) -> int:
    """Map innings position 1..11 to the merged-opener bucket 1..10.

    1 or 2 → bucket 1 (opener); 3 → 2; 4 → 3; … 11 → 10.
    """
    return 1 if pos <= 2 else pos - 1


class _Acc:
    """One (person, scope_key, position_bucket) cell. Filled by summing
    pre-aggregated inningsbatterperf GROUP BY rows (D2 rollup) — runs/
    fours/sixes are all-ball, legal_balls/dots legal-only, by construction
    of inningsbatterperf, so live (3b) and precomputed paths are identical.
    """
    __slots__ = (
        "innings", "runs", "legal_balls", "dots",
        "fours", "sixes", "dismissals",
        "thirties", "fifties", "hundreds", "ducks",
        "failures_10", "seventies",
    )

    def __init__(self):
        self.innings = 0
        self.runs = 0
        self.legal_balls = 0
        self.dots = 0
        self.fours = 0
        self.sixes = 0
        self.dismissals = 0
        # Tier 1 (apples-to-apples) per-position milestone counts +
        # PT1 (prob-baselines) failures_10 / seventies — all derived from
        # each inningsbatterperf row's all-ball runs + not_out below.
        self.thirties = 0
        self.fifties = 0
        self.hundreds = 0
        self.ducks = 0
        self.failures_10 = 0
        self.seventies = 0

    def add_group(self, r: dict) -> None:
        """Accumulate one inningsbatterperf GROUP BY row into this cell."""
        self.innings += r["innings"]
        self.runs += r["runs"]
        self.legal_balls += r["legal_balls"]
        self.dots += r["dots"]
        self.fours += r["fours"]
        self.sixes += r["sixes"]
        self.dismissals += r["dismissals"]
        self.thirties += r["thirties"]
        self.fifties += r["fifties"]
        self.hundreds += r["hundreds"]
        self.ducks += r["ducks"]
        self.failures_10 += r["failures_10"]
        self.seventies += r["seventies"]

    def to_row(self, person_id: str, scope_key: str, bucket: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "position_bucket": bucket,
            "innings": self.innings,
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
    # Idempotent ALTER fallback for the legacy Tier 1 columns (apples-
    # to-apples baselines). Pre-existing DBs that pre-date Tier 1 get
    # them appended; new DBs already have them via the model.
    #
    # No ALTER for PT1 columns (failures_10, seventies) — by spec-prob-
    # baselines.md §3 workflow, schema-management is DROP+CREATE on
    # full populate, not ALTER. The full populate's `_ensure_tables`
    # drops the table when full mode AND table exists (see
    # populate_full), so DBs re-built from scratch pick the new
    # columns from the model directly.
    for col in ("thirties", "fifties", "hundreds", "ducks"):
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
    """Roll up inningsbatterperf into per (person, scope_key, bucket) cells.

    D2 single-source-of-truth: every column is a GROUP BY of the per-
    innings batting table (already all-ball runs + legal balls + the
    non-striker rows from Commit 2), grouped on person × position_bucket
    × the four scope fields that make_scope_key hashes. So this cohort is
    convention-correct by construction and identical to the live (3b)
    aggregation that reads the same table — no delivery rescan, no
    re-derivation of batting order.

    Milestones derive from each row's all-ball runs + not_out exactly as
    the apples-to-apples / prob-baselines specs define them:
    thirties/fifties/hundreds are the mutually-exclusive 30-49 / 50-99 /
    100+ bands; seventies overlaps fifties (70-99); failures_10 = runs≤10;
    ducks = dismissed for 0 (not_out already excludes retired).

    If match_ids is None, rolls up every regular innings.
    """
    if match_ids is not None and not match_ids:
        return {}

    if match_ids is None:
        scope = ""
        params: dict = {}
    else:
        id_list = ",".join(str(m) for m in match_ids)
        scope = f"AND i.match_id IN ({id_list})"
        params = {}

    group_rows = await db.q(f"""
        SELECT
            ib.batter_id AS pid,
            ib.position_bucket AS bucket,
            m.event_name AS tournament, m.season AS season,
            m.gender AS gender, m.team_type AS team_type,
            COUNT(*) AS innings,
            SUM(ib.runs) AS runs,
            SUM(ib.balls) AS legal_balls,
            SUM(ib.dots) AS dots,
            SUM(ib.fours) AS fours,
            SUM(ib.sixes) AS sixes,
            SUM(CASE WHEN ib.not_out = 0 THEN 1 ELSE 0 END) AS dismissals,
            SUM(CASE WHEN ib.runs >= 30 AND ib.runs < 50 THEN 1 ELSE 0 END) AS thirties,
            SUM(CASE WHEN ib.runs >= 50 AND ib.runs < 100 THEN 1 ELSE 0 END) AS fifties,
            SUM(CASE WHEN ib.runs >= 100 THEN 1 ELSE 0 END) AS hundreds,
            SUM(CASE WHEN ib.runs >= 70 AND ib.runs < 100 THEN 1 ELSE 0 END) AS seventies,
            SUM(CASE WHEN ib.runs <= 10 THEN 1 ELSE 0 END) AS failures_10,
            SUM(CASE WHEN ib.runs = 0 AND ib.not_out = 0 THEN 1 ELSE 0 END) AS ducks
        FROM inningsbatterperf ib
        JOIN innings i ON i.id = ib.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 {scope}
        GROUP BY ib.batter_id, ib.position_bucket,
                 m.event_name, m.season, m.gender, m.team_type
    """, params)

    # (event_name, season, gender, team_type) → scope_key is effectively
    # injective, so each GROUP BY row maps to one cell; accumulate via a
    # dict so any hash collision merges cleanly (and matches the parent
    # populate's scope_key grouping).
    accs: dict[tuple[str, str, int], _Acc] = {}
    for r in group_rows:
        scope_key = make_scope_key(
            r["tournament"], r["season"] or "",
            r["gender"] or "", r["team_type"] or "",
        )
        key = (r["pid"], scope_key, r["bucket"])
        acc = accs.get(key)
        if acc is None:
            acc = _Acc()
            accs[key] = acc
        acc.add_group(r)

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
    """Drop+create playerscopestats_position and rebuild from every regular match.

    Spec-prob-baselines.md §3 workflow: schema-management is DROP+
    CREATE on full populate (not idempotent ALTER), so the on-disk
    schema is always a function of the current model definition. The
    DROP also wipes any indexes — `_ensure_tables(incremental=False)`
    rebuilds them.
    """
    print("Populating playerscopestats_position (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsposition'"
    )
    if len(existing) > 0:
        await db.q("DROP TABLE playerscopestatsposition")
    table = await _ensure_tables(db, incremental=False)

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
