"""
One-time pass: canonicalize duplicate team names in cricket.db.

Reads the mapping from team_aliases.py and runs UPDATE statements
against every column in every table that holds a team name.

Idempotent — running it twice is harmless (the second run finds zero
rows to update because the canonical name doesn't appear as a key
in TEAM_ALIASES).

Usage:
    uv run python scripts/fix_team_names.py
    uv run python scripts/fix_team_names.py --dry-run

Tables and columns affected:
- match.team1, match.team2, match.outcome_winner, match.toss_winner
- innings.team
- matchplayer.team
"""

import argparse
import asyncio
import os
import sys

# Make sibling team_aliases.py importable when running this from scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from team_aliases import TEAM_ALIASES  # noqa: E402

from deebase import Database  # noqa: E402

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cricket.db",
)

# (table, column) tuples that hold team-name strings
TEAM_COLUMNS = [
    ("match", "team1"),
    ("match", "team2"),
    ("match", "outcome_winner"),
    ("match", "toss_winner"),
    ("innings", "team"),
    ("matchplayer", "team"),
]


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
    print(f"{len(TEAM_ALIASES)} alias entries\n")

    grand_total = 0
    for old, new in TEAM_ALIASES.items():
        for table, col in TEAM_COLUMNS:
            count_rows = await db.q(
                f"SELECT COUNT(*) as c FROM {table} WHERE {col} = :old",
                {"old": old},
            )
            n = count_rows[0]["c"] if count_rows else 0
            if n == 0:
                continue
            print(f"  {table}.{col:18}  {n:>6}  {old}  →  {new}")
            grand_total += n
            if not args.dry_run:
                await db.q(
                    f"UPDATE {table} SET {col} = :new WHERE {col} = :old",
                    {"new": new, "old": old},
                )

    print(f"\n{'WOULD UPDATE' if args.dry_run else 'UPDATED'} {grand_total} rows total")

    if not args.dry_run:
        await db.q("VACUUM")
        print("VACUUM complete")


if __name__ == "__main__":
    asyncio.run(main())
