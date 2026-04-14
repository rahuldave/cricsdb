"""Apply manual keeper resolutions from partition CSVs.

Reads every `docs/keeper-ambiguous/*.csv` and for each row with a
non-empty `resolved_keeper_id`, updates the corresponding
`keeper_assignment` row to (keeper_id=X, method='manual',
confidence='definitive', ambiguous_reason=NULL).

Two use cases handled by the same mechanism:
  1. Filling in an ambiguous NULL row
  2. Overriding a high/medium/low confidence algorithmic assignment
     (just append a new row to any partition CSV with that innings_id
     and the corrected keeper_id)

Idempotent: running it twice in a row is a no-op.

Usage:
  uv run python scripts/apply_keeper_resolutions.py

Also called automatically at the end of populate_full /
populate_incremental in populate_keeper_assignments.py — this script
is the standalone entry point for applying resolutions between full
DB rebuilds.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deebase import Database
from scripts.populate_keeper_assignments import (
    _read_existing_partitions,
    _apply_resolutions,
    DB_PATH,
)


async def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.q("PRAGMA journal_mode = WAL")

    _, resolutions = _read_existing_partitions()
    if not resolutions:
        print("No resolutions found in docs/keeper-ambiguous/*.csv")
        return

    # Load all person IDs for validation
    person_rows = await db.q("SELECT id FROM person")
    person_ids = {r["id"] for r in person_rows}

    print(f"Applying {len(resolutions)} resolutions from partition CSVs...")
    stats = await _apply_resolutions(db, resolutions, person_ids)

    print(f"\n  Applied:               {stats['applied']}")
    print(f"  High-conf overrides:   {stats['overrides']}")
    print(f"  Skipped (bad person):  {stats['skipped_no_person']}")
    print(f"  Skipped (no innings):  {stats['skipped_no_innings']}")


if __name__ == "__main__":
    asyncio.run(main())
