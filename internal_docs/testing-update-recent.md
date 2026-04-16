# Smoke-testing `update_recent.py` against a prod snapshot

Goal: verify that an incremental import run (the same code that plash
will execute when you deploy an update) works against the real plash
database, without touching your local `./cricket.db` or the live prod
DB.

## Why

Most incremental bugs surface only against real data:

- A cricsheet schema change that only affects recent files.
- A populate script (fielding / keeper / partnership) that regresses
  on a specific match.
- An index or migration that behaves differently on the 435 MB prod
  DB vs. your local dev copy.
- A season transition (e.g. first 2025/26 match) that breaks
  season-range queries.

Running `update_recent.py --days 30` against your dev DB catches
schema problems but not data-volume problems. Running it against a
copy of the prod snapshot does.

## The copy path (always use /tmp, never touch the Downloads file)

1. Download the prod bundle from plash:

   ```bash
   # via the plash CLI or dashboard; leaves
   # ~/Downloads/t20-cricket-db_download.tar and the extracted dir
   # ~/Downloads/t20-cricket-db_download/ containing data/cricket.db
   ```

2. Copy the DB to `/tmp` — **never** run `update_recent.py` directly
   against the Downloads path:

   ```bash
   cp ~/Downloads/t20-cricket-db_download/data/cricket.db \
      /tmp/cricket-prod-test.db
   ```

   The reason is that `update_recent.py` opens the DB in WAL mode and
   writes. A failed run can leave the DB in a partially-updated state
   that's hard to untangle. Keep the pristine Downloads copy as your
   "known good" reference; mutate only the `/tmp` copy, which you can
   delete and re-copy as often as you like.

3. Run the incremental import against the `/tmp` copy via the `--db`
   flag:

   ```bash
   # dry-run first
   uv run python update_recent.py --db /tmp/cricket-prod-test.db \
     --days 30 --dry-run

   # if dry-run looks sane, do it for real
   uv run python update_recent.py --db /tmp/cricket-prod-test.db \
     --days 30
   ```

4. Inspect the result — you can point a local uvicorn at the test
   DB by exporting the path or by temporarily symlinking:

   ```bash
   # quick check via sqlite3
   sqlite3 /tmp/cricket-prod-test.db \
     "SELECT MAX(date) FROM matchdate; SELECT COUNT(*) FROM match;"

   # or serve the test DB via the API to click around
   ln -sf /tmp/cricket-prod-test.db ./cricket.db.test
   # then temporarily edit api/dependencies.py to point at
   # ./cricket.db.test, or start a second uvicorn with an env var.
   # The --db flag does NOT yet propagate into the API — it's
   # import-only. Add this if you end up needing it often.
   ```

5. Clean up when done:

   ```bash
   rm /tmp/cricket-prod-test.db
   ```

## What `update_recent.py --db` does NOT change

- The FastAPI server (`api/*`) still reads from `./cricket.db` (dev)
  or `data/cricket.db` (prod). `--db` is a script-level override
  used only by the import.
- No impact on `deploy.sh`. Deploy still ships the code tree; if you
  want to push the prod DB back up after a smoke test, you'd still
  have to do `bash deploy.sh --first` with the test DB renamed to
  `./cricket.db` (and you almost certainly don't want to).

## Don't

- Don't run against `~/Downloads/...` directly. One bad run leaves you
  without a pristine reference.
- Don't skip `--dry-run` on the first attempt against a fresh
  snapshot. It prints the latest-date gap + file count so you can
  confirm the window makes sense.
- Don't forget to re-copy between runs if you want to test the same
  window twice — the first run will have already imported those
  matches and the second will dedupe to zero.

## What the import does (for reference)

On success, `update_recent.py --db <path>` will:

1. Download cricsheet's `recently_added_<N>_json.zip` into a temp dir.
2. Filter to T20 / IT20 files.
3. Dedupe against the target DB's `match.filename` set.
4. Insert matches + innings + deliveries + wickets.
5. Populate `fieldingcredit`, `keeper_assignment`, `partnership` for
   the new match IDs (incremental mode — does not touch old rows).
6. Ensure composite covering indexes exist
   (`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`) and re-run
   `ANALYZE`, so the batting/bowling leaderboard queries stay fast.
   See `internal_docs/perf-leaderboards.md` for why.
7. Regenerate `frontend/src/generated/site-stats.json` (home-page
   masthead totals).

Step 6 is why the index/ANALYZE calls live in `update_recent.py` as
well as `import_data.py`: a SQLite schema has no way to enforce that
stats stay fresh, so we refresh them after every batch.
