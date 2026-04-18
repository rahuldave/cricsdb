# Data Pipeline

How `cricket.db` is built and kept in sync with cricsheet.org.

## Sources

Cricsheet hosts data at two different URL prefixes (this is easy to get
wrong — `/downloads/people.csv` returns 404):

| Kind | URL prefix |
|---|---|
| Match JSON archives | `https://cricsheet.org/downloads/{code}_json.zip` |
| Registry CSVs (people, names) | `https://cricsheet.org/register/{file}` |

### Match archives we use

The 22 archives below cover all international and club T20 cricket on
cricsheet. They are listed in `import_data.py:MATCH_DIRS`.

**International T20s** (4 archives)
- `t20s_male_json`, `t20s_female_json` — full T20 internationals
- `it20s_male_json`, `it20s_female_json` — associate-nation T20Is

**Club T20 leagues** (18 archives)
- `ipl_json` — Indian Premier League
- `bbl_json` — Big Bash League (AU men)
- `wbb_json` — Women's Big Bash League
- `psl_json` — Pakistan Super League
- `cpl_json` — Caribbean Premier League
- `bpl_json` — Bangladesh Premier League
- `lpl_json` — Lanka Premier League
- `ilt_json` — International League T20 (UAE)
- `mlc_json` — Major League Cricket (US)
- `sat_json` — SA20 (South Africa)
- `wpl_json` — Women's Premier League (India)
- `wsl_json` — Women's Super League
- `hnd_json` — The Hundred (men)
- `ntb_json` — T20 Blast (NatWest, England)
- `ssm_json` — Super Smash (NZ men)
- `sma_json` — Super Smash (NZ women)
- `ctc_json` — CSA T20 Challenge (SA domestic)
- `npl_json` — Nepal Premier League

### Registry CSVs

- **`people.csv`** — canonical player roster. One row per player:
  `identifier, name, unique_name, key_cricinfo, key_bcci, key_opta, ...`
  Imported into the `person` table. Includes cross-reference keys to
  ~20 external systems.
- **`names.csv`** — alias index. Many rows per player:
  `identifier, name` listing every variant (initials, full name,
  nicknames). Imported into the `personname` table and joined by
  `/api/v1/players` so search is forgiving of name variants.

The two CSVs update on independent schedules — check both.

## Scripts

### Building from scratch

```bash
# 1. Download all archives + CSVs (idempotent — skips existing)
uv run python download_data.py

# Force re-download:
uv run python download_data.py --force

# 2. Drop and rebuild cricket.db (~15 min)
uv run python import_data.py
```

`import_data.py` deletes any existing `cricket.db`, recreates the
schema, and imports everything in `data/`. The schema is created from
`models.py` via deebase. At the end of the import, it automatically
populates two denormalized tables:

1. `fielding_credit` (~118K rows) via
   `scripts/populate_fielding_credits.py:populate_full()`.
2. `keeper_assignment` (~25.8K rows, one per regular innings) via
   `scripts/populate_keeper_assignments.py:populate_full()`. This is
   Tier 2 of fielding analytics — see `internal_docs/spec-fielding-tier2.md`.
   Manual resolutions live in `docs/keeper-ambiguous/*.csv` partitions
   (gitted) and are re-applied on every full rebuild so corrections
   survive.

### Incremental updates

`update_recent.py` pulls cricsheet's "recently added" bulk zip,
filters to T20/IT20 (international + club), dedupes against
`match.filename`, and imports only what's new. After importing, it
automatically adds fielding credits AND keeper assignments for the
new matches only (via `populate_incremental()` on each denormalized
table) — no separate step needed. New ambiguous keeper innings get
appended to today's partition CSV under `docs/keeper-ambiguous/`.

```bash
uv run python update_recent.py --dry-run --days 7   # check status
uv run python update_recent.py --days 7              # actually import
```

**Flags**

| Flag | Default | Notes |
|---|---|---|
| `--days N` | 30 | How far back. Cricsheet only publishes 2/7/14/30-day bundles, so the smallest one covering `N` is used. |
| `--dry-run` | off | Report what *would* happen without writing anything. Also checks `people.csv` and `names.csv` freshness. |
| `--keep` | off | Keep the temp directory of extracted JSON after running. |

**Dedup key:** `match.filename` (cricsheet match IDs are stable, e.g.
`1234567.json`), so re-running with overlapping windows is safe.

### Sample dry-run output

```
Downloading https://cricsheet.org/downloads/recently_added_7_json.zip
Extracted 33 files
T20 matches in window: 22 (international=7, club=15, other=0)

  Today:                        2026-04-06
  Latest match in DB:           2026-04-02
  Latest match in 7-day bundle: 2026-04-02
  Status: IN SYNC with cricsheet — cricsheet itself is 4 day(s) behind today.

Already in DB: 22
New to import: 0

People/names CSVs:
  people.csv: up to date (1130810 bytes, Last-Modified Thu, 02 Apr 2026 18:25:09 GMT)
  names.csv: up to date (161462 bytes, Last-Modified Wed, 25 Mar 2026 18:08:14 GMT)

[dry-run] No changes written.
```

How to read it:

1. **Bundle stats** — how many T20s cricsheet has published in the window,
   split by international vs club.
2. **Three dates** — today / latest in DB / latest in the bundle. The
   *Status* line tells you which side is behind:
   - `IN SYNC with cricsheet` — DB matches the bundle. Any remaining
     gap to today is cricsheet's processing lag (1-3 days is normal).
   - `DB is BEHIND cricsheet by N day(s)` — drop `--dry-run` and import.
3. **Dedup counts** — how many of the bundle's T20s are new.
4. **CSVs** — server's `Last-Modified` and `Content-Length` vs your
   local copies. If either is `STALE`, run `download_data.py --force`
   to refresh, then `import_data.py` to rebuild.

### After importing

The DB on plash persists in plash's `data/` directory. To push the
updated DB live you must use the first-time deploy flag:

```bash
bash deploy.sh --first   # uploads the 435 MB cricket.db along with code
```

A plain `bash deploy.sh` only redeploys code and leaves the DB on plash
untouched.

### Canonicalization on insert

`import_match_file()` in `import_data.py` — shared by the full-rebuild
and incremental paths — applies three canonicalization passes before
writing each match:

- `team_aliases.canonicalize()` on `team1`, `team2`, `toss_winner`,
  `outcome_winner`. Collapses franchise renames (Kings XI Punjab →
  Punjab Kings, RCB → RCBengaluru, etc.) into a single current name.
- `event_aliases.canonicalize()` on `event_name`. Collapses sponsor
  rebrands (NatWest T20 Blast → Vitality Blast, Ram Slam → CSA T20
  Challenge, etc.).
- `api.venue_aliases.resolve_or_raw()` on `(venue, city)`. Returns
  `(canonical_venue, canonical_city, country)` on hit; on miss, applies
  `_strip_city_suffix` as a display-tidy fallback — if the raw venue
  ends with `", <raw_city>"` and the stripped result is non-empty,
  returns `(stripped, raw_city, None)`. Otherwise passes raw values
  through. Either way, unknown venues get `venue_country=NULL` and are
  added to the module-level `UNKNOWN_VENUES` set. At end of run,
  `write_unknown_venues()` appends them to
  `docs/venue-worklist/unknowns-<date>.csv` so the next review cycle
  can fold them into `api/venue_aliases.py`. **Unknown venues never
  block import** (soft-fail). Because `update_recent.py` imports
  `import_data.import_match_file`, the resolver and its fallback fire
  identically on both full rebuild and incremental paths — one hook
  in `resolve_or_raw` covers both.

The venue pass is the only one that also fills a new column
(`match.venue_country`, added by the Match model; existing DBs gain it
via `scripts/fix_venue_names.py`'s idempotent `ALTER TABLE ADD COLUMN`
block).

For DBs that predate these aliases, run the matching `scripts/fix_*_names.py`
once — each is idempotent, so re-running is a no-op. Re-run
`fix_venue_names.py` whenever `venue_aliases.py` grows new entries so
previously-raw rows get retrofitted.

**Venue punctuation-collision sweep.** The initial canonicalization
matches on token-level prefix/suffix and will miss pairs that differ
only by punctuation (e.g. `M.Chinnaswamy Stadium` vs
`M Chinnaswamy Stadium, Bengaluru`). Run
`scripts/sweep_venue_punctuation_collisions.py` after every big
incremental import — it slugifies each canonical venue (strip
punctuation, lowercase, strip city suffix), groups by slug + country,
and prints candidates with match counts. Human edits
`api/venue_aliases.py` to remap losers → winners, then
`fix_venue_names.py` retrofits the DB. Because canonical-venue growth
requires new stadiums, which is rare, this sweep should rarely fire.

### Indexes + ANALYZE (automatic)

Both `import_data.py` (full rebuild) and `update_recent.py`
(incremental, when there are new matches) idempotently ensure two
composite covering indexes exist and re-run `ANALYZE`:

- `ix_delivery_batter_agg (batter_id, extras_wides, extras_noballs, runs_batter)`
- `ix_delivery_bowler_agg (bowler_id, extras_wides, extras_noballs, runs_total)`

These power the Batting/Bowling/Fielding landing-page leader boards —
without them, unfiltered aggregates over the 2.95M-row `delivery`
table take 3+ seconds; with them, sub-second. `CREATE INDEX IF NOT
EXISTS` is a no-op when the index is already there, so these lines
are safe to keep in both pipelines. See `internal_docs/perf-leaderboards.md`
for the diagnosis.

### Smoke-testing `update_recent.py` against a prod snapshot

Before pushing a DB update to prod, it's worth running the
incremental pipeline against a copy of the live DB to confirm the
import path works on real data (schema quirks in fresh cricsheet
files, populate-script regressions on specific matches, etc).
`update_recent.py --db /tmp/cricket-prod-test.db` routes the import
at a custom DB path without touching `./cricket.db`. See
`internal_docs/testing-update-recent.md` for the copy-to-tmp workflow and
what not to do (never run against `~/Downloads/` directly — keep that
copy pristine).

## Caveats

- **Cricsheet lag is normal.** Matches are typically published 1-3 days
  after they finish (longer for smaller leagues). A "4 days behind today"
  reading on the dry-run, with status `IN SYNC with cricsheet`, just
  means cricsheet itself hasn't released anything newer.
- **People.csv updates are not automatic on incremental runs.**
  `update_recent.py` only imports match files; it does not refresh
  `person` or `personname`. New players in newly-imported matches will
  be inserted into the `matchplayer`/`delivery` tables with their
  `person_id` (cricsheet ships the registry inline in each match JSON),
  but their roster entry and alias variants won't appear until you
  re-run `download_data.py --force` for the CSVs and re-import people.
  The dry-run's CSV freshness check is there to remind you when this
  matters.
- **Recent-window cap.** `--days 60` is treated as `--days 30` (largest
  available bundle) with a warning. For anything older, do a full
  rebuild via `download_data.py` + `import_data.py`.
