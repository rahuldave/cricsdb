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
`models.py` via deebase.

### Incremental updates

`update_recent.py` pulls cricsheet's "recently added" bulk zip,
filters to T20/IT20 (international + club), dedupes against
`match.filename`, and imports only what's new.

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
