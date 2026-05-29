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
populates four denormalized tables:

1. `fielding_credit` (~118K rows) via
   `scripts/populate_fielding_credits.py:populate_full()`.
2. `keeper_assignment` (~25.8K rows, one per regular innings) via
   `scripts/populate_keeper_assignments.py:populate_full()`. This is
   Tier 2 of fielding analytics — see `internal_docs/spec-fielding-tier2.md`.
   Manual resolutions live in `docs/keeper-ambiguous/*.csv` partitions
   (gitted) and are re-applied on every full rebuild so corrections
   survive.
3. `partnership` (~250K rows, one per on-field batting partnership)
   via `scripts/populate_partnerships.py:populate_full()`. Drives the
   Teams > Partnerships tab — see `internal_docs/spec-team-stats.md`.
4. `player_scope_stats` (~65K rows, one per `(person, scope_key)`
   where scope_key encodes tournament/season/gender/team_type) via
   `scripts/populate_player_scope_stats.py:populate_full()`. Now
   consumed by the player-baseline rollout (`spec-player-compare-
   average.md`) — was originally landed as infrastructure for that
   work. Sanity tests: `tests/sanity/test_player_scope_stats.py`.
5. `playerscopestats_position` (~97K rows, one per (person,
   scope_key, position_bucket) — 10 batting position buckets,
   opener=1+2 merged) via
   `scripts/populate_playerscopestats_position.py:populate_full()`.
   Per-bucket batting aggregates; backs the per-position cohort
   baseline endpoint + the per-player position-distribution
   histogram. **As of `spec-batting-allball-runs-single-source.md`
   (D2) this is a pure rollup of the records table `inningsbatterperf`
   — a `GROUP BY` on person × position_bucket × scope fields — NOT a
   delivery rescan, so the records-aggregates populate
   (`populate_records_aggregates`, which builds `inningsbatterperf`)
   is moved to run BEFORE this step in both `import_data.py` and
   `update_recent.py`. Runs are all-ball + the cohort includes
   non-striker innings by construction, identical to the live (3b)
   aggregation over the same table.** Sanity:
   `tests/sanity/test_playerscopestats_position.py` (pool conservation
   against the parent) + `test_playerscopestatsposition_rollup.py`
   (exact-integer parity against the inningsbatterperf rollup).
   Batting runs everywhere on the player side now follow the all-ball
   convention via `api/batting_convention.batting_delivery_contrib`
   (the parent + per-over/phase children) and `inningsbatterperf` (the
   records source) — see `how-stats-calculated.md` "All-ball batting-
   runs convention".
6. `playerscopestats_over` (~282K rows, one per (person, scope_key,
   over_number) — 20 buckets, 1-indexed overs 1..20) via
   `scripts/populate_playerscopestats_over.py:populate_full()`.
   Per-over bowling aggregates. Sanity:
   `tests/sanity/test_playerscopestats_over.py`.
7. `playerscopestats_fielding_position` (~94K rows, one per
   (fielder, scope_key, dismissed-batter-position-bucket)) via
   `scripts/populate_playerscopestats_fielding_position.py:populate_full()`.
   Substitute catches EXCLUDED at populate (distribution-side
   semantics — CLAUDE.md "Substitute fielders — INCLUDED in
   /leaders, EXCLUDED in /distribution"). Convention 3 applied:
   `catches` includes caught_and_bowled. Position derivation reuses
   `api/innings_positions.py::derive_positions` shared with the
   parent + position child populates — computed ONCE per innings
   and threaded across the three downstream scripts. Sanity:
   `tests/sanity/test_playerscopestats_fielding_position.py`.
8. `playerscopestats_batting_phase` (~112K rows, one per
   (person, scope_key, phase_bucket) — 3 phase buckets:
   1=powerplay/2=middle/3=death, same boundaries as the parent's
   `_phase`) via
   `scripts/populate_playerscopestats_batting_phase.py:populate_full()`.
   Backs `/api/v1/scope/averages/players/batting/by-phase`. Sanity:
   `tests/sanity/test_playerscopestats_batting_phase.py` (ball-grain
   pool conservation against parent + upper-bound
   `innings_in_phase ≤ 3 × parent.innings_batted`).
9. `playerscopestats_fielding_phase` (~72K rows, one per
   (fielder, scope_key, phase_bucket)) via
   `scripts/populate_playerscopestats_fielding_phase.py:populate_full()`.
   Substitute fielders EXCLUDED. Convention 3 applied. Backs
   `/api/v1/scope/averages/players/fielding/by-phase`. Sanity:
   `tests/sanity/test_playerscopestats_fielding_phase.py`.

Steps 8-9 added 2026-05-20 by `spec-player-baseline-parity.md` §3.1.
Steps 1-7 also gained schema columns in that rollout:
`playerscopestats` got `thirties / fifties / hundreds / ducks` (per-
innings milestone counts) and `playerscopestatsover` got `maidens`
(per-(person, scope, over) maiden-over count). Idempotent
ALTER TABLE ADD COLUMN blocks in the populate scripts migrate
pre-existing DBs; new DBs created by `db.create` have the columns
from the start.

10. `playerscopestatsfieldingcatchdist` (one per (person, scope_key) —
    match-grain catch distribution: `matches_with_0 / _1 / _ge2`) via
    `scripts/populate_playerscopestats_fielding_catch_dist.py:populate_full()`.
    Backs the fielding catch-count ProbChip cohort baselines. Its master
    sample = FIELDED matches (changed from squad by 3e). Sanity:
    `tests/sanity/test_playerscopestats_fielding_catch_dist.py` (where present).

**Parent column `matches_fielded` (denominator B, 2026-05-28).**
`playerscopestats` gained `matches_fielded` = distinct matches where the
player was in the XI AND the opponent batted (actually fielded). It is the
denominator for every fielding per-match rate (catches/match etc.) and the
catch-distribution master sample, replacing squad `matches` — the activity-unit
convention (consistent with batting `innings_batted` / bowling `innings_bowled`).
Populated in `scripts/populate_player_scope_stats.py`. **Deploy note:** this is
a new parent column + a changed catch-dist sample, so a deploy to an existing
prod DB needs a full parent + catch-dist re-ingest (DROP+CREATE populate) or a
rebuilt-cricket.db upload — an incremental update on a fresh DB fills it
correctly (verified 2026-05-29 smoke test), but the column must exist first.

### Incremental updates

`update_recent.py` pulls cricsheet's "recently added" bulk zip,
filters to T20/IT20 (international + club), dedupes against
`match.filename`, and imports only what's new. After importing, it
automatically adds fielding credits, keeper assignments,
partnerships, player_scope_stats AND the six playerscopestats
child tables (`playerscopestats_position`, `playerscopestats_over`,
`playerscopestats_fielding_position`, `playerscopestats_batting_phase`,
`playerscopestats_fielding_phase`, `playerscopestatsfieldingcatchdist`)
plus `records` aggregates and `bucket_baseline` cells for the new matches
only (via `populate_incremental()` on each) — no separate step needed.
The records aggregates run BEFORE the position child because the position
child is now a rollup of `inningsbatterperf` (which the records step builds),
so the per-innings table must be current first (`update_recent.py`
sequencing). New ambiguous keeper innings get appended to today's
partition CSV under `docs/keeper-ambiguous/`. All six
playerscopestats-family incremental paths use the same touched-
scope recompute strategy: identify scope_keys touched by the new
matches, find ALL matches in those scopes, recompute the
`(person, scope_key, …)` cells from scratch over that set,
delete + reinsert. Exact and avoids in-place upsert drift.

**People-registry refresh (auto, since 2026-04-30):** Before any
match imports, `update_recent.py` does two things:

1. **CSV refresh in place.** HEADs cricsheet's people.csv +
   names.csv. If size or `Last-Modified` differs from local, GET +
   atomic-replace via a `.part` suffix. Skipped when CSV is
   up-to-date. Equivalent to a scoped `download_data.py --force`
   for just these two files.
2. **`refresh_people_registry(db)`.** INSERT-OR-IGNORE the local
   CSVs onto the `person` and `personname` tables. Existing rows
   preserved; newly-registered ids land. Pre-existing person.name
   values are kept (cricsheet's canonical-name registry is stable;
   for the rare legitimate rename, drop the table + run
   import_data.py). For names.csv, a NOT EXISTS guard prevents
   duplicate aliases.

Why this exists: pre-fix (before 2026-04-30), incremental match
imports inserted matchplayer rows referencing person_ids that
cricsheet had registered AFTER the initial `import_data.py` run.
The matchplayer ↔ person FK soft-broke; player-dossier-by-id pages
(`/batting?player=<id>`) rendered without a name. The refresh
closes that loop on every cycle. Surfaced 2026-04-30 by
`/bowling?player=f98481d3` (Muhammad Ismail, Multan Sultans, PSL
2026) — see `internal_docs/spec-filterbar-team-class-club.md`
session log + git commit `7506b9c`.

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
`update_recent.py --db tmp/cricket-prod-test.db` routes the import
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
