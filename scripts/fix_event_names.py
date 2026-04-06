"""
One-time pass: canonicalize tournament names in cricket.db.

Mirrors scripts/fix_team_names.py but for the `event_name` column on
the `match` table. Reads the mapping from event_aliases.py.

Idempotent — running it twice is harmless.

Usage:
    uv run python scripts/fix_event_names.py
    uv run python scripts/fix_event_names.py --dry-run
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_aliases import EVENT_ALIASES  # noqa: E402

from deebase import Database  # noqa: E402

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cricket.db",
)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Report row counts that would change without writing")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")

    print(f"DB: {DB_PATH}")
    print(f"{len(EVENT_ALIASES)} alias entries\n")

    grand_total = 0
    for old, new in EVENT_ALIASES.items():
        count_rows = await db.q(
            "SELECT COUNT(*) as c FROM match WHERE event_name = :old",
            {"old": old},
        )
        n = count_rows[0]["c"] if count_rows else 0
        if n == 0:
            continue
        print(f"  match.event_name  {n:>6}  {old}  →  {new}")
        grand_total += n
        if not args.dry_run:
            await db.q(
                "UPDATE match SET event_name = :new WHERE event_name = :old",
                {"new": new, "old": old},
            )

    print(f"\n{'WOULD UPDATE' if args.dry_run else 'UPDATED'} {grand_total} rows total")

    if not args.dry_run:
        await db.q("VACUUM")
        print("VACUUM complete")


if __name__ == "__main__":
    asyncio.run(main())
