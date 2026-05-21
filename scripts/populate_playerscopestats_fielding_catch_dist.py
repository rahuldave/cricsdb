"""Populate playerscopestats_fielding_catch_dist — per-scope match-grain
catch distribution. PT4 of internal_docs/spec-prob-baselines.md.

One row per (person_id, scope_key); the scope_key matches the parent
PlayerScopeStats row's hash of (tournament || season || gender ||
team_type). Three count columns bucket every match the person played
in this scope by their non-substitute catch count in that match:

  matches_with_0    — match where the player took 0 catches.
  matches_with_1    — match where the player took exactly 1 catch.
  matches_with_ge2  — match where the player took ≥ 2 catches.

Population semantics:
  - Master sample = matchplayer rows in regular (non-super-over)
    matches at the scope. Substitute appearances aren't in this sample
    (matchplayer only records squad members).
  - Per-match catch count = SUM over fieldingcredit where
    fc.fielder_id = person_id AND fc.is_substitute = 0 AND
    fc.kind IN ('caught', 'caught_and_bowled')  — Convention 3.

Cohort prob math at consumer time (api/routers/scope_averages.py
compute_players_fielding_cohort):
  P(=0) = SUM(matches_with_0)   / SUM(matches_total)  across keeper-cohort.

DROP+CREATE on full populate per spec §3 — no idempotent ALTER.

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_fielding_catch_dist.py
    Drops the table and rebuilds from every regular match.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes the rows for scope_keys touched by the new matches.
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
    FieldingCredit, PlayerScopeStatsFieldingCatchDist,
)
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")


async def _ensure_tables(db, incremental: bool = False):
    """Register tables; create indexes only on full rebuild."""
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(MatchPlayer, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    await db.create(FieldingCredit, pk="id", if_not_exists=True)

    idx = {} if incremental else {"indexes": ["scope_key"]}
    table = await db.create(
        PlayerScopeStatsFieldingCatchDist,
        pk=["person_id", "scope_key"],
        if_not_exists=True,
        **idx,
    )
    return table


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str], list[int]]:
    """Aggregate per (person_id, scope_key) → [m0, m1, mge2].

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
    match_meta: dict[int, str] = {}
    for r in match_rows:
        match_meta[r["id"]] = make_scope_key(
            r["tournament"], r["season"] or "",
            r["gender"] or "", r["team_type"] or "",
        )
    if not match_meta:
        return {}

    # Per-(person, match) non-substitute catch count from fieldingcredit
    # joined to delivery → innings → match. is_substitute=0 + Convention 3.
    mid_list = ",".join(str(m) for m in match_meta)
    catches_rows = await db.q(f"""
        SELECT fc.fielder_id AS person_id,
               i.match_id    AS match_id,
               COUNT(*)      AS catches
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i  ON i.id = d.innings_id
        WHERE fc.kind IN ('caught', 'caught_and_bowled')
          AND COALESCE(fc.is_substitute, 0) = 0
          AND fc.fielder_id IS NOT NULL
          AND i.match_id IN ({mid_list})
        GROUP BY fc.fielder_id, i.match_id
    """)
    catches_by_pm: dict[tuple[str, int], int] = {
        (r["person_id"], r["match_id"]): r["catches"] for r in catches_rows
    }

    # Master sample — every matchplayer at the scope. is_substitute on
    # matchplayer (if the column exists in this codebase's data model)
    # is not filtered here because matchplayer records squad members
    # only; substitute appearances aren't recorded in matchplayer.
    mp_rows = await db.q(f"""
        SELECT mp.person_id, mp.match_id
        FROM matchplayer mp
        WHERE mp.match_id IN ({mid_list})
    """)

    # Bucket per (person, scope_key).
    accs: dict[tuple[str, str], list[int]] = {}
    for mp in mp_rows:
        pid = mp["person_id"]
        mid = mp["match_id"]
        scope_key = match_meta.get(mid)
        if scope_key is None:
            continue
        key = (pid, scope_key)
        bucket = accs.get(key)
        if bucket is None:
            bucket = [0, 0, 0]  # [m0, m1, mge2]
            accs[key] = bucket
        c = catches_by_pm.get((pid, mid), 0)
        if c == 0:
            bucket[0] += 1
        elif c == 1:
            bucket[1] += 1
        else:
            bucket[2] += 1
    return accs


async def _flush(db, table, rows: list[dict]) -> int:
    if not rows:
        return 0
    sa_table = table.sa_table
    async with db._engine.begin() as conn:
        await conn.execute(sa_table.insert(), rows)
    return len(rows)


async def populate_full(db) -> int:
    """Drop+create playerscopestats_fielding_catch_dist and rebuild."""
    print("Populating playerscopestats_fielding_catch_dist (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsfieldingcatchdist'"
    )
    if len(existing) > 0:
        await db.q("DROP TABLE playerscopestatsfieldingcatchdist")
    table = await _ensure_tables(db, incremental=False)

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope_key) cells aggregated")

    rows: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key), (m0, m1, mge2) in accs.items():
        rows.append({
            "person_id": person_id,
            "scope_key": scope_key,
            "matches_with_0": m0,
            "matches_with_1": m1,
            "matches_with_ge2": mge2,
        })
        if len(rows) >= batch:
            total += await _flush(db, table, rows)
            rows = []
    total += await _flush(db, table, rows)

    elapsed = time.time() - start
    print(f"  Inserted {total} rows in {elapsed:.1f}s")
    return total


async def populate_incremental(db, new_match_ids: list[int]) -> int:
    """Recompute rows for the scope_keys touched by `new_match_ids`."""
    if not new_match_ids:
        print("playerscopestats_fielding_catch_dist: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_fielding_catch_dist for {len(new_match_ids)} new matches…")
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
    deleted = await db.q(
        f"SELECT COUNT(*) AS c FROM playerscopestatsfieldingcatchdist WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted[0]["c"] if deleted else 0
    await db.q(f"DELETE FROM playerscopestatsfieldingcatchdist WHERE scope_key IN ({sk_list})")

    rows_to_insert: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key), (m0, m1, mge2) in accs.items():
        if scope_key not in scope_keys:
            continue
        rows_to_insert.append({
            "person_id": person_id,
            "scope_key": scope_key,
            "matches_with_0": m0,
            "matches_with_1": m1,
            "matches_with_ge2": mge2,
        })
        if len(rows_to_insert) >= batch:
            total += await _flush(db, table, rows_to_insert)
            rows_to_insert = []
    total += await _flush(db, table, rows_to_insert)

    print(f"  playerscopestats_fielding_catch_dist: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(
        description="Populate playerscopestats_fielding_catch_dist"
    ).parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
