"""
One-time pass: canonicalize venue / city / venue_country on the match
table, using api/venue_aliases.py as the source of truth.

Mirrors scripts/fix_team_names.py and scripts/fix_event_names.py. Safe
to run against the main DB or a /tmp copy. Idempotent — re-running is a
no-op because canonical values resolve to themselves.

Usage:
    uv run python scripts/fix_venue_names.py
    uv run python scripts/fix_venue_names.py --dry-run
    uv run python scripts/fix_venue_names.py --db /tmp/cricket-prod-test.db

Output: unknown (venue, city) pairs (i.e. pairs missing from
VENUE_ALIASES) are written to docs/venue-worklist/unknowns-<date>.csv
so the next worklist cycle can fold them in.

Column addition: if `match.venue_country` doesn't yet exist, the script
adds it via idempotent ALTER TABLE ADD COLUMN. New DBs already have it
via the Match model in models/tables.py.
"""

import argparse
import asyncio
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database  # noqa: E402
from api.venue_aliases import resolve_or_raw  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO_ROOT, "cricket.db")
WORKLIST_DIR = os.path.join(REPO_ROOT, "docs", "venue-worklist")


async def ensure_venue_country_column(db):
    """Add match.venue_country TEXT NULL if it doesn't exist yet.
    Catches the 'duplicate column' error, which is the idempotent signal
    in SQLite land."""
    try:
        await db.q("ALTER TABLE match ADD COLUMN venue_country TEXT")
        print("Added match.venue_country column")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            pass  # already exists
        else:
            raise


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB,
                    help=f"Path to cricket.db (default: {DEFAULT_DB})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{args.db}")
    print(f"DB: {args.db}")

    if not args.dry_run:
        await ensure_venue_country_column(db)

    # Pull every distinct (venue, city, venue_country) group. Grouping
    # on venue_country too means we only UPDATE rows whose current
    # value differs from the resolver output — makes the script truly
    # idempotent on re-runs.
    try:
        rows = await db.q("""
            SELECT COALESCE(venue,'')          AS venue,
                   COALESCE(city,'')           AS city,
                   COALESCE(venue_country,'')  AS venue_country,
                   COUNT(*)                    AS n
            FROM   match
            GROUP  BY venue, city, venue_country
            ORDER  BY n DESC
        """)
    except Exception:
        # Pre-migration DB: no venue_country column yet
        rows = await db.q("""
            SELECT COALESCE(venue,'')   AS venue,
                   COALESCE(city,'')    AS city,
                   ''                   AS venue_country,
                   COUNT(*)             AS n
            FROM   match
            GROUP  BY venue, city
            ORDER  BY n DESC
        """)

    venue_changes = 0
    city_changes = 0
    country_fills = 0
    unchanged = 0
    unknown: list[tuple[str, str]] = []

    for row in rows:
        raw_v = row["venue"] or None
        raw_c = row["city"] or None
        current_country = row.get("venue_country") or None
        n = row["n"]

        canon_v, canon_c, country = resolve_or_raw(raw_v, raw_c)

        if country is None and raw_v is not None:
            unknown.append((raw_v, raw_c or ""))

        # Build SET / WHERE
        set_parts = []
        params = {"raw_v": raw_v, "raw_c": raw_c}
        where_parts = []
        if raw_v is None:
            where_parts.append("venue IS NULL")
        else:
            where_parts.append("venue = :raw_v")
        if raw_c is None:
            where_parts.append("city IS NULL")
        else:
            where_parts.append("city = :raw_c")

        if canon_v != raw_v:
            set_parts.append("venue = :canon_v")
            params["canon_v"] = canon_v
            venue_changes += n
        if canon_c != raw_c:
            set_parts.append("city = :canon_c")
            params["canon_c"] = canon_c
            city_changes += n
        if country is not None and country != current_country:
            set_parts.append("venue_country = :country")
            params["country"] = country
            country_fills += n
        if not set_parts:
            unchanged += n
            continue

        if not args.dry_run:
            sql = (f"UPDATE match SET {', '.join(set_parts)} "
                   f"WHERE {' AND '.join(where_parts)}")
            await db.q(sql, params)

    print(f"\n{'WOULD UPDATE' if args.dry_run else 'UPDATED'}:")
    print(f"  venue changes:          {venue_changes} rows")
    print(f"  city changes:           {city_changes} rows")
    print(f"  venue_country fills:    {country_fills} rows")
    print(f"  unchanged rows:         {unchanged}")

    if unknown:
        os.makedirs(WORKLIST_DIR, exist_ok=True)
        today = dt.date.today().isoformat()
        out_path = os.path.join(WORKLIST_DIR, f"unknowns-{today}.csv")
        print(f"\n!! {len(unknown)} unknown (venue, city) pair(s) — not in VENUE_ALIASES:")
        for v, c in unknown:
            print(f"     {v!r:60} | city={c!r}")
        if not args.dry_run:
            new_file = not os.path.exists(out_path)
            with open(out_path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(["raw_venue", "raw_city"])
                for v, c in sorted(unknown):
                    w.writerow([v, c])
            print(f"   → wrote list to {out_path}")

    # Verify (only in live mode — column may not exist during dry-run)
    if not args.dry_run:
        check = await db.q("SELECT COUNT(*) AS c FROM match WHERE venue_country IS NULL AND venue IS NOT NULL")
        null_cc = check[0]["c"] if check else 0
        if null_cc:
            print(f"\nAfter run: {null_cc} matches still have venue_country NULL (unknown venues).")


if __name__ == "__main__":
    asyncio.run(main())
