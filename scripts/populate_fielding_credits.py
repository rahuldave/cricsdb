"""Populate the fielding_credit table from wicket + delivery data.

Modes:
  Full rebuild (default):
    python scripts/populate_fielding_credits.py
    Truncates fielding_credit and repopulates from all wickets.

  Incremental (called from update_recent.py):
    populate_incremental(db, new_match_ids)
    Only processes wickets from the given matches.

  Show unmatched fielder names:
    python scripts/populate_fielding_credits.py --show-unmatched
    Reports fielder names that couldn't be resolved to a person ID.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

# Allow running from repo root or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from models import Person, Match, MatchDate, MatchPlayer, Innings, Delivery, Wicket, FieldingCredit
from fielder_aliases import resolve_fielder_name

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cricket.db")

# Wicket kinds that produce fielding credits
FIELDING_KINDS = {"caught", "stumped", "run out", "caught and bowled"}


def _decode_fielders(raw) -> list[dict] | None:
    """Decode the fielders JSON, handling both double-encoded and normal formats."""
    if raw is None:
        return None
    # If it's already a list (post-fix format), return as-is
    if isinstance(raw, list):
        return raw
    # String — could be normal JSON or double-encoded
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        # Double-encoded: json.loads returns a string, parse again
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(parsed, list):
            return parsed
    return None


async def _build_name_lookup(db) -> dict[str, str]:
    """Build name -> person_id lookup from person + personname tables."""
    # Primary: person.name -> person.id
    rows = await db.q("SELECT id, name, unique_name FROM person")
    by_name: dict[str, str] = {}
    by_unique: dict[str, str] = {}
    for r in rows:
        by_name[r["name"]] = r["id"]
        if r["unique_name"]:
            by_unique[r["unique_name"]] = r["id"]

    # Secondary: personname.name -> person_id
    alias_rows = await db.q("SELECT person_id, name FROM personname")
    by_alias: dict[str, str] = {}
    for r in alias_rows:
        by_alias[r["name"]] = r["person_id"]

    return by_name, by_unique, by_alias


def _resolve_fielder_id(
    fielder_name: str,
    by_name: dict[str, str],
    by_unique: dict[str, str],
    by_alias: dict[str, str],
) -> str | None:
    """Resolve a fielder name to a person ID using multiple lookup strategies."""
    # 1. Apply alias mapping first
    canonical = resolve_fielder_name(fielder_name)
    if canonical is None:
        return None  # Explicitly unresolvable

    # 2. Direct person.name lookup
    if canonical in by_name:
        return by_name[canonical]

    # 3. person.unique_name lookup (handles "Imran Khan (2)" style)
    if canonical in by_unique:
        return by_unique[canonical]
    # Also try the original name against unique_name
    if fielder_name in by_unique:
        return by_unique[fielder_name]

    # 4. personname alias lookup
    if canonical in by_alias:
        return by_alias[canonical]
    if fielder_name in by_alias:
        return by_alias[fielder_name]

    return None


async def _process_wickets(db, wicket_rows, by_name, by_unique, by_alias, table):
    """Process wicket rows into fielding_credit inserts. Returns (inserted, unmatched_set)."""
    unmatched = set()
    batch = []
    batch_size = 2000

    for w in wicket_rows:
        kind = w["kind"]
        if kind not in FIELDING_KINDS:
            continue

        wicket_id = w["wicket_id"]
        delivery_id = w["delivery_id"]

        if kind == "caught and bowled":
            # No fielders JSON — the bowler is the fielder
            bowler_name = w["bowler"]
            bowler_id = w["bowler_id"]
            batch.append({
                "wicket_id": wicket_id,
                "delivery_id": delivery_id,
                "fielder_name": bowler_name,
                "fielder_id": bowler_id,
                "kind": "caught_and_bowled",
                "is_substitute": False,
            })
        else:
            # Parse fielders JSON
            fielders = _decode_fielders(w["fielders"])
            if not fielders:
                continue

            credit_kind = kind.replace(" ", "_")  # "run out" -> "run_out"
            for f in fielders:
                fname = f.get("name")
                if not fname:
                    continue
                is_sub = bool(f.get("substitute", False))
                fid = _resolve_fielder_id(fname, by_name, by_unique, by_alias)
                if fid is None:
                    unmatched.add(fname)

                batch.append({
                    "wicket_id": wicket_id,
                    "delivery_id": delivery_id,
                    "fielder_name": fname,
                    "fielder_id": fid,
                    "kind": credit_kind,
                    "is_substitute": is_sub,
                })

        if len(batch) >= batch_size:
            sa_table = table.sa_table
            async with db._engine.begin() as conn:
                await conn.execute(sa_table.insert(), batch)
            batch = []

    # Flush remaining
    if batch:
        sa_table = table.sa_table
        async with db._engine.begin() as conn:
            await conn.execute(sa_table.insert(), batch)

    return len(batch), unmatched


async def _ensure_tables(db, incremental=False):
    """Register existing tables with deebase so FK references resolve.

    In incremental mode, skip index creation (they already exist).
    Same pattern as get_match_tables() in import_data.py.
    """
    # Must register in dependency order: Person, Match, Innings, Delivery, Wicket
    await db.create(Person, pk="id", if_not_exists=True)
    await db.create(Match, pk="id", if_not_exists=True)
    await db.create(Innings, pk="id", if_not_exists=True)
    await db.create(Delivery, pk="id", if_not_exists=True)
    await db.create(Wicket, pk="id", if_not_exists=True)
    idx = {} if incremental else {"indexes": ["fielder_id", "delivery_id", "kind"]}
    return await db.create(
        FieldingCredit, pk="id", if_not_exists=True, **idx,
    )


async def populate_full(db, show_unmatched=False):
    """Full rebuild: truncate and repopulate all fielding credits."""
    print("Building name lookup tables...")
    by_name, by_unique, by_alias = await _build_name_lookup(db)
    print(f"  {len(by_name)} person names, {len(by_unique)} unique names, {len(by_alias)} aliases")

    table = await _ensure_tables(db)

    # Truncate
    await db.q("DELETE FROM fieldingcredit")
    print("Truncated fielding_credit table")

    # Fetch all wickets with delivery info
    print("Loading wickets...")
    wicket_rows = await db.q("""
        SELECT w.id as wicket_id, w.delivery_id, w.kind, w.fielders,
               d.bowler, d.bowler_id
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
    """)
    print(f"  {len(wicket_rows)} wickets to process")

    start = time.time()
    all_unmatched = set()
    batch = []
    batch_size = 2000
    inserted = 0

    for w in wicket_rows:
        kind = w["kind"]
        if kind not in FIELDING_KINDS:
            continue

        wicket_id = w["wicket_id"]
        delivery_id = w["delivery_id"]

        if kind == "caught and bowled":
            batch.append({
                "wicket_id": wicket_id,
                "delivery_id": delivery_id,
                "fielder_name": w["bowler"],
                "fielder_id": w["bowler_id"],
                "kind": "caught_and_bowled",
                "is_substitute": False,
            })
        else:
            fielders = _decode_fielders(w["fielders"])
            if not fielders:
                continue

            credit_kind = kind.replace(" ", "_")
            for f in fielders:
                fname = f.get("name")
                if not fname:
                    continue
                is_sub = bool(f.get("substitute", False))
                fid = _resolve_fielder_id(fname, by_name, by_unique, by_alias)
                if fid is None:
                    all_unmatched.add(fname)

                batch.append({
                    "wicket_id": wicket_id,
                    "delivery_id": delivery_id,
                    "fielder_name": fname,
                    "fielder_id": fid,
                    "kind": credit_kind,
                    "is_substitute": is_sub,
                })

        if len(batch) >= batch_size:
            sa_table = table.sa_table
            async with db._engine.begin() as conn:
                await conn.execute(sa_table.insert(), batch)
            inserted += len(batch)
            batch = []

    if batch:
        sa_table = table.sa_table
        async with db._engine.begin() as conn:
            await conn.execute(sa_table.insert(), batch)
        inserted += len(batch)

    elapsed = time.time() - start
    print(f"\nInserted {inserted} fielding credits in {elapsed:.1f}s")

    # Summary by kind
    counts = await db.q("""
        SELECT kind, COUNT(*) as cnt FROM fieldingcredit GROUP BY kind ORDER BY cnt DESC
    """)
    for r in counts:
        print(f"  {r['kind']}: {r['cnt']}")

    null_count = await db.q("SELECT COUNT(*) as cnt FROM fieldingcredit WHERE fielder_id IS NULL")
    print(f"\n  Unresolved fielder_id: {null_count[0]['cnt']} rows")

    if show_unmatched and all_unmatched:
        print(f"\n  {len(all_unmatched)} unmatched fielder names:")
        for name in sorted(all_unmatched):
            print(f"    {name}")

    return inserted


async def populate_incremental(db, new_match_ids: list[int]):
    """Incremental: add fielding credits only for wickets in the given matches.

    Called from update_recent.py after importing new matches.
    Does NOT truncate — only inserts new rows.
    """
    if not new_match_ids:
        return 0

    by_name, by_unique, by_alias = await _build_name_lookup(db)

    table = await _ensure_tables(db, incremental=True)

    # Fetch wickets only for the new matches
    placeholders = ",".join(str(mid) for mid in new_match_ids)
    wicket_rows = await db.q(f"""
        SELECT w.id as wicket_id, w.delivery_id, w.kind, w.fielders,
               d.bowler, d.bowler_id
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        WHERE i.match_id IN ({placeholders})
    """)

    if not wicket_rows:
        return 0

    batch = []
    inserted = 0

    for w in wicket_rows:
        kind = w["kind"]
        if kind not in FIELDING_KINDS:
            continue

        wicket_id = w["wicket_id"]
        delivery_id = w["delivery_id"]

        if kind == "caught and bowled":
            batch.append({
                "wicket_id": wicket_id,
                "delivery_id": delivery_id,
                "fielder_name": w["bowler"],
                "fielder_id": w["bowler_id"],
                "kind": "caught_and_bowled",
                "is_substitute": False,
            })
        else:
            fielders = _decode_fielders(w["fielders"])
            if not fielders:
                continue

            credit_kind = kind.replace(" ", "_")
            for f in fielders:
                fname = f.get("name")
                if not fname:
                    continue
                is_sub = bool(f.get("substitute", False))
                fid = _resolve_fielder_id(fname, by_name, by_unique, by_alias)

                batch.append({
                    "wicket_id": wicket_id,
                    "delivery_id": delivery_id,
                    "fielder_name": fname,
                    "fielder_id": fid,
                    "kind": credit_kind,
                    "is_substitute": is_sub,
                })

    if batch:
        sa_table = table.sa_table
        async with db._engine.begin() as conn:
            await conn.execute(sa_table.insert(), batch)
        inserted = len(batch)

    print(f"  Fielding credits: +{inserted} rows from {len(new_match_ids)} new matches")
    return inserted


async def main():
    ap = argparse.ArgumentParser(description="Populate fielding_credit table")
    ap.add_argument("--show-unmatched", action="store_true",
                    help="List fielder names that couldn't be resolved")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")

    await populate_full(db, show_unmatched=args.show_unmatched)


if __name__ == "__main__":
    asyncio.run(main())
