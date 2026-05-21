"""Populate playerscopestats_over — per-over bowling aggregates.

Phase 2b of the player-baselines rollout. See
`internal_docs/spec-player-compare-average.md` §4.3 + §7 Phase 2b.
One row per (person_id, scope_key, over_number); the scope_key
matches the parent PlayerScopeStats row's hash of (tournament ||
season || gender || team_type).

over_number convention: 1..20 in this table (the underlying delivery
table stores 0..19; we shift to 1-indexed at populate time so
consumers can speak in "Over 1" through "Over 20" idiom).

Modes:
  Full rebuild (default, standalone):
    uv run python scripts/populate_playerscopestats_over.py
    Truncates the table and rebuilds from every regular innings.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Recomputes only the rows for scope_keys touched by the new
    matches (same scope-recompute strategy as the parent populate).

Auto-called by import_data.py (full) and update_recent.py
(incremental) immediately after the position child populate.

Aggregation excluded-kinds match the parent PlayerScopeStats:
  - Bowler wickets exclude 'run out' / 'retired hurt' / 'retired out'
    / 'obstructing the field' (BOWLER_WICKET_EXCLUDED).
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
    PlayerScopeStatsOver,
)
from scripts.populate_player_scope_stats import make_scope_key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "cricket.db")

BOWLER_WICKET_EXCLUDED = {
    "run out", "retired hurt", "retired out", "obstructing the field",
}


class _Acc:
    __slots__ = (
        "runs_conceded", "legal_balls", "wickets", "dots", "boundaries",
        "maidens",
        "innings_set", "four_wicket_hauls",
    )

    def __init__(self):
        self.runs_conceded = 0
        self.legal_balls = 0
        self.wickets = 0
        self.dots = 0
        self.boundaries = 0
        # Maiden overs bowled by this person at this over-number across
        # scope. Filled by the post-pass that walks per (innings, over,
        # bowler) tuples and checks legal_balls == 6 AND runs == 0.
        self.maidens = 0
        # Tier 2 of spec-apples-to-apples-baselines.md.
        # innings_set — distinct innings where the bowler delivered ≥1
        # legal ball at this over_number. Used as the per-bucket
        # denominator for over-weighted per-innings cohort rates
        # (replaces the prior `wickets_per_over × 4` heuristic).
        self.innings_set: set[int] = set()
        # four_wicket_hauls — 4-fers attributed to this over_number by
        # the over in which the bowler's 4th wicket fell in that innings.
        # See §7 of the spec for the attribution-choice discussion.
        self.four_wicket_hauls = 0

    def to_row(self, person_id: str, scope_key: str, over_number: int) -> dict:
        return {
            "person_id": person_id,
            "scope_key": scope_key,
            "over_number": over_number,
            "runs_conceded": self.runs_conceded,
            "legal_balls": self.legal_balls,
            "wickets": self.wickets,
            "dots": self.dots,
            "boundaries": self.boundaries,
            "maidens": self.maidens,
            "innings_bowled": len(self.innings_set),
            "four_wicket_hauls": self.four_wicket_hauls,
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
            ("scope_key", "over_number"),
            "scope_key",
        ],
    }
    table = await db.create(
        PlayerScopeStatsOver,
        pk=["person_id", "scope_key", "over_number"],
        if_not_exists=True,
        **idx,
    )
    # Idempotent column migration for maidens (Q6 of
    # spec-player-baseline-parity.md). New DBs already have it via the
    # model; pre-existing DBs get it appended.
    # innings_bowled + four_wicket_hauls added by Tier 2 of
    # spec-apples-to-apples-baselines.md.
    for col in ("maidens", "innings_bowled", "four_wicket_hauls"):
        try:
            await db.q(
                f"ALTER TABLE playerscopestatsover ADD COLUMN {col} "
                f"INTEGER NOT NULL DEFAULT 0"
            )
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise
    return table


async def _aggregate_matches(
    db, match_ids: list[int] | None
) -> dict[tuple[str, str, int], _Acc]:
    """Aggregate per (person_id, scope_key, over_number) over the given matches.

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

    # Per (innings, over_number, bowler) tally to detect maiden overs.
    # A maiden = the bowler bowled all 6 legal balls of an over with 0
    # runs conceded (off the bat + extras). Filled in the deliveries
    # pass, drained into _Acc.maidens at the end.
    over_tally: dict[tuple[int, int, str], dict] = {}

    # Tier 2 of spec-apples-to-apples-baselines.md.
    # Per (innings, bowler) running wicket count + per-(innings, bowler,
    # over) attribution slot — when the bowler's wicket count crosses 4,
    # the over_bucket is recorded as the 4-fer's attribution bucket.
    # innings_wickets : (iid, bow) -> count
    # haul_attributed : set of (iid, bow) already credited (one per
    #                   bowler-innings, in the over the 4th wicket fell).
    innings_wickets: dict[tuple[int, str], int] = {}
    haul_attributed: set[tuple[int, str]] = set()
    haul_credits: list[tuple[str, str, int]] = []  # (bow, scope_key, over_bucket)

    def get_acc(person_id: str, scope_key: str, over_number: int) -> _Acc:
        key = (person_id, scope_key, over_number)
        acc = accs.get(key)
        if acc is None:
            acc = _Acc()
            accs[key] = acc
        return acc

    # Pass 1: deliveries — accumulate bowler-side tallies per over.
    chunk = 500
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        d_rows = await db.q(f"""
            SELECT innings_id, over_number, bowler_id,
                   runs_batter, runs_total,
                   extras_wides, extras_noballs
            FROM delivery
            WHERE innings_id IN ({sub_list})
        """)
        for d in d_rows:
            bow = d["bowler_id"]
            if bow is None:
                continue
            iid = d["innings_id"]
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            # 1-indexed bucket (delivery.over_number is 0-indexed).
            over_bucket = d["over_number"] + 1
            acc = get_acc(bow, scope_key, over_bucket)
            # runs_conceded counts every delivery (incl. wides + noballs).
            acc.runs_conceded += d["runs_total"]
            legal = (d["extras_wides"] == 0 and d["extras_noballs"] == 0)
            if legal:
                acc.legal_balls += 1
                # Tier 2: distinct innings where this bowler delivered
                # ≥1 legal ball at this over_number — per-bucket
                # innings denominator.
                acc.innings_set.add(iid)
            rb = d["runs_batter"]
            if rb == 0 and d["runs_total"] == 0:
                acc.dots += 1
            if rb == 4 or rb == 6:
                acc.boundaries += 1

            # Per-over maiden tally (keyed at innings × over × bowler so
            # split-over cases credit only the bowler who bowled all 6
            # legal balls).
            tkey = (iid, d["over_number"], bow)
            tally = over_tally.get(tkey)
            if tally is None:
                tally = {"legal": 0, "runs": 0}
                over_tally[tkey] = tally
            if legal:
                tally["legal"] += 1
            tally["runs"] += d["runs_total"]

    # Pass 2: wickets — credit the bowler's over bucket. Walk wickets
    # in INNINGS / OVER order so the running per-bowler-innings count
    # can attribute each 4-fer to the over its 4th wicket fell in.
    for start in range(0, len(innings_ids), chunk):
        sub = innings_ids[start:start + chunk]
        sub_list = ",".join(str(i) for i in sub)
        w_rows = await db.q(f"""
            SELECT w.kind, d.bowler_id, d.over_number, d.innings_id, d.delivery_index, d.id AS did
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            WHERE d.innings_id IN ({sub_list})
            ORDER BY d.innings_id, d.over_number, d.delivery_index, d.id
        """)
        for w in w_rows:
            bow = w["bowler_id"]
            kind = w["kind"]
            if bow is None or kind in BOWLER_WICKET_EXCLUDED:
                continue
            iid = w["innings_id"]
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            over_bucket = w["over_number"] + 1
            get_acc(bow, scope_key, over_bucket).wickets += 1
            # Tier 2: 4-fer attribution. Increment the running per-
            # (innings, bowler) wicket count; on crossing 4 (and only
            # once per bowler-innings), attribute to the over bucket.
            ikey = (iid, bow)
            innings_wickets[ikey] = innings_wickets.get(ikey, 0) + 1
            if innings_wickets[ikey] == 4 and ikey not in haul_attributed:
                haul_attributed.add(ikey)
                haul_credits.append((bow, scope_key, over_bucket))

    # Drain 4-fer attributions into the per-bucket _Acc.
    for bow, scope_key, over_bucket in haul_credits:
        get_acc(bow, scope_key, over_bucket).four_wicket_hauls += 1

    # Maiden detection — credit a maiden when one bowler bowled all 6
    # legal balls of an over conceding 0 runs (off the bat + extras).
    # Split overs (e.g. bowler retires hurt mid-over) never satisfy the
    # 6-legal-balls test under a single bowler key, so they're correctly
    # excluded by the same rule.
    for (iid, over_number_0idx, bow), tally in over_tally.items():
        if tally["legal"] == 6 and tally["runs"] == 0:
            mid = innings_match[iid]
            scope_key = match_meta[mid]["scope_key"]
            over_bucket = over_number_0idx + 1
            get_acc(bow, scope_key, over_bucket).maidens += 1

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
    """Truncate playerscopestats_over and rebuild from every regular match."""
    print("Populating playerscopestats_over (full rebuild)...")
    start = time.time()

    existing = await db.q(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='playerscopestatsover'"
    )
    table_exists = len(existing) > 0
    table = await _ensure_tables(db, incremental=table_exists)
    if table_exists:
        await db.q("DELETE FROM playerscopestatsover")

    print("  scanning all matches…")
    accs = await _aggregate_matches(db, match_ids=None)
    print(f"  {len(accs)} (person, scope_key, over) cells aggregated")

    rows: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, over_number), acc in accs.items():
        rows.append(acc.to_row(person_id, scope_key, over_number))
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
        print("playerscopestats_over: no new matches, skipping")
        return 0

    print(f"Populating playerscopestats_over for {len(new_match_ids)} new matches…")
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
        f"SELECT COUNT(*) AS c FROM playerscopestatsover WHERE scope_key IN ({sk_list})"
    )
    old_count = deleted_rows[0]["c"] if deleted_rows else 0
    await db.q(f"DELETE FROM playerscopestatsover WHERE scope_key IN ({sk_list})")

    rows_to_insert: list[dict] = []
    batch = 2000
    total = 0
    for (person_id, scope_key, over_number), acc in accs.items():
        if scope_key not in scope_keys:
            continue
        rows_to_insert.append(acc.to_row(person_id, scope_key, over_number))
        if len(rows_to_insert) >= batch:
            total += await _flush(db, table, rows_to_insert)
            rows_to_insert = []
    total += await _flush(db, table, rows_to_insert)

    print(f"  playerscopestats_over: replaced {old_count} rows with {total}")
    return total


async def main():
    argparse.ArgumentParser(description="Populate playerscopestats_over").parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")
    await populate_full(db)


if __name__ == "__main__":
    asyncio.run(main())
