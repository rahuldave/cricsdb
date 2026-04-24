# tests/sanity

Standalone python scripts that verify denormalized tables match their
source-of-truth aggregations. Pool-conservation tests + round-trip
tests for the populate scripts that build summary tables on top of
`delivery` / `wicket` / `fieldingcredit` / `keeperassignment`.

Different from `tests/regression/` (HEAD-vs-patched URL md5-diff) and
`tests/integration/` (agent-browser end-to-end). Sanity tests are
data-layer only: they don't hit the API or the UI, they read the DB.

Run after a populate-script change, or against the prod-snapshot copy
in `/tmp` to confirm a refactor didn't drift values:

```bash
# Local cricket.db
uv run python tests/sanity/test_player_scope_stats.py

# Prod snapshot
cp ~/Downloads/t20-cricket-db_download/data/cricket.db /tmp/cricket-prod-test.db
# (run populate first if the snapshot doesn't have the new table)
uv run python -c "
import asyncio, sys; sys.path.insert(0, '.')
from deebase import Database
from scripts.populate_player_scope_stats import populate_full
async def go():
    db = Database('sqlite+aiosqlite:////tmp/cricket-prod-test.db')
    await db.q('PRAGMA journal_mode = WAL')
    await populate_full(db)
asyncio.run(go())
"
uv run python tests/sanity/test_player_scope_stats.py --db /tmp/cricket-prod-test.db
```

Each script exits 0 on all-pass, 1 on any failure.
