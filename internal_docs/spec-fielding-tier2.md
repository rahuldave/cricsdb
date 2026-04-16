# Spec: Wicketkeeper Identification (Fielding Tier 2)

Status: build-ready.
Depends on: Tier 1 (`fielding_credit` table, already shipped).

## Overview

Cricsheet has **no keeper designation** anywhere — not in match JSON,
not in `people.csv`, not in delivery data. This spec identifies the
wicketkeeper for each innings by layering four signals over cricsheet's
existing fielder attribution data, stores the result in a
`keeper_assignment` table, and exposes it across the site.

**Expected coverage (current DB, 25,846 regular innings):**

| Layer | Method | Innings | Cum | Label |
|---|---|---:|---:|---|
| A | Stumping in this innings, fielder_id resolved | 4,706 | 18.2% | `definitive` |
| B | Exactly 1 season-candidate in XI | 11,156 | 61.4% | `high` |
| C | Exactly 1 career N≥3 keeper-capable in XI | 4,504 | 78.8% | `medium` |
| D | Exactly 1 team-ever-keeper in XI | 875 | 82.2% | `low` |
| — | **Ambiguous** (2+ candidates or none) | 4,605 | 17.8% | NULL |

The **keeper_assignment** table is one row per regular innings with an
explicit `keeper_id` (possibly NULL), a `confidence` enum, a `method`
tag, and — for the NULL rows — an `ambiguous_reason` so the worklist
is self-describing.

The table is intended to be consumed by any page in the site:
- **Fielding player page** — new "Keeping" sub-tab with keeper-specific stats
- **Match scorecard** — "Keeper: X" label per innings
- **Team page** — keepers used across seasons
- **Player page** — keeping career stats if they ever kept

## Scope

- **New table**: `keeper_assignment` — one row per regular innings.
- **New population script**: `scripts/populate_keeper_assignments.py`
  with `populate_full()` and `populate_incremental(new_match_ids)`
  (same pattern as `populate_fielding_credits.py`). Called
  automatically by `import_data.py` and `update_recent.py`.
- **New API endpoints** + additions to existing fielding endpoints for
  keeper stats.
- **Frontend changes**: "Keeping" sub-tab on `/fielding`, keeper label
  on match scorecards, keeper info on team and player pages.
- **Ambiguous worklist export**: `docs/keeper-ambiguous.csv` regenerated
  on each full rebuild — a ready-made targets list for manual or
  Cricinfo-sourced disambiguation.

## Data layer

### `keeper_assignment` table

```
keeper_assignment
  id                INTEGER PK
  innings_id        INTEGER FK → innings  (unique; one row per innings)
  keeper_id         VARCHAR FK → person   (NULL when ambiguous)
  method            VARCHAR  (see below, NULL when ambiguous)
  confidence        VARCHAR  (see below, NULL when ambiguous)
  ambiguous_reason  VARCHAR  (NULL when assigned; set when keeper_id is NULL)
  candidate_ids_json JSON     (for ambiguous rows: JSON array of the
                              competing candidate person_ids — helpful
                              for the worklist CSV, and for any future
                              UI that wants to show the competing
                              keepers)
```

**Indexes**: `keeper_id`, `innings_id` (unique), `confidence`,
`ambiguous_reason`.

**`method` enum** (nullable — NULL only when `keeper_id` is NULL):

| Value | Meaning |
|---|---|
| `stumping` | Layer A — a stumping occurred and we credited the stumper |
| `season_single` | Layer B — exactly one season-candidate was in the XI |
| `career_single` | Layer C — exactly one career N≥3 keeper was in the XI |
| `team_ever_single` | Layer D — exactly one player who's ever stumped for this team was in the XI |
| `manual` | Resolved via a partition CSV (Cricinfo scrape or hand-edit) — always overrides algorithmic assignment |

**`confidence` enum** (nullable):

| Value | Meaning |
|---|---|
| `definitive` | We saw the stumping. Cannot be wrong unless cricsheet data is wrong. |
| `high` | Season-level signal specific to this team. Rare failure mode: keeper rotation mid-season where the rotator didn't stump. |
| `medium` | Career-level signal. Failure mode: a second keeper-capable player kept instead of the one we picked. |
| `low` | Team-ever signal for minor/associate teams. Failure mode: the keeper really is someone in the XI who has never stumped in cricsheet data. |

**`ambiguous_reason` enum** (non-NULL only when `keeper_id` is NULL):

| Value | Meaning |
|---|---|
| `multi_stumpers_same_innings` | Stumping had 2+ distinct fielders credited (data anomaly) |
| `stump_fielder_unresolved` | Stumping happened but the `fielders` name didn't resolve to a person_id |
| `multi_season` | 2+ season-candidates in the XI — classic IPL/India two-keeper case |
| `multi_career` | No season signal, but 2+ career-keepers in the XI |
| `multi_team_ever` | Layers B and C failed, 2+ team-ever-keepers in the XI |
| `no_candidate` | Nobody in the fielding XI has ever stumped in cricsheet data (typical for minor teams) |

### Population logic (`scripts/populate_keeper_assignments.py`)

Mirrors `populate_fielding_credits.py` in shape, with two additions
unique to keeper assignment: (1) a **partitioned ambiguous worklist**
and (2) a **resolution-reload step**.

```python
async def populate_full(db):
    # 1. Build the candidate sets in-memory:
    #    - career_N3 = {pid : stumping_count >= 3}
    #    - season_candidates[(fielding_team, tournament, season)]
    #    - team_ever_keeper[fielding_team]
    #    - stumpers_by_innings[innings_id]
    #    - xi[match_id][team]

    # 2. Truncate keeper_assignment.

    # 3. For each regular innings: apply layers A-D; insert one row
    #    — either assigned (keeper_id, method, confidence set) or
    #    ambiguous (all NULL except ambiguous_reason, candidate_ids_json).

    # 4. Load all existing resolutions from docs/keeper-ambiguous/*.csv
    #    (see "Partitioned worklist" below). For each row with a non-empty
    #    `resolved_keeper_id`, UPDATE the corresponding keeper_assignment
    #    row: set keeper_id, method='manual', confidence='definitive',
    #    clear ambiguous_reason. Manual resolutions always override
    #    algorithmic assignments — they represent external authority.

    # 5. Find all innings that are STILL ambiguous (NULL keeper_id) and
    #    are NOT already listed in any existing partition CSV. Write
    #    them to a fresh partition file docs/keeper-ambiguous/YYYY-MM-DD.csv
    #    where YYYY-MM-DD is today's date (the run date). If today's file
    #    already exists, append (with innings_id dedup).

async def populate_incremental(db, new_match_ids):
    # 1. Same candidate-set build, but scoped enough to cover the new
    #    matches. In practice we rebuild the full in-memory structures
    #    — they're cheap (<1s), and matches span seasons so a scoped
    #    build is only marginally faster.

    # 2. Run the 4-layer algorithm ONLY for innings in new_match_ids.
    #    Insert new keeper_assignment rows; do not touch existing ones.

    # 3. Load resolutions from all partition CSVs (same as full). Apply
    #    any that match new_match_ids' innings.

    # 4. Any newly-ambiguous innings from the new matches get written to
    #    today's partition file (docs/keeper-ambiguous/YYYY-MM-DD.csv).
    #    Append if the file already exists; dedup on innings_id.

    # NOTE: incremental does NOT retrofit older ambiguous innings when
    # new matches introduce new candidates. A full rebuild is the
    # authoritative path for retroactive improvements.
```

**Why the incremental path is less powerful than full**: a match played
today might introduce a new season keeper-candidate for `(Team, 2025)`
that would retroactively resolve some older 2025 innings previously
marked ambiguous. The incremental path doesn't chase that — full rebuild
does. In practice the full rebuild runs as part of `import_data.py`
(~15 min) and is authoritative; incremental keeps the site current
for daily updates.

Both paths are called automatically from `import_data.py` and
`update_recent.py` — no separate script invocation needed, same
pattern as `fielding_credit`.

### Partitioned ambiguous worklist

The ambiguous list lives as a set of date-partitioned CSV files under
`docs/keeper-ambiguous/`, Hive-style:

```
docs/keeper-ambiguous/
  README.md          — format + how to resolve
  2026-04-13.csv     — first full rebuild: all ambiguous innings at that point
  2026-04-20.csv     — incremental on 4/20: new ambiguous discovered then
  2026-04-27.csv     — further incremental
  ...
```

**Partition invariants:**

- Each `innings_id` appears in **exactly one** partition — the file
  written by the run that first discovered it as ambiguous. It does
  NOT migrate to a newer partition on later full rebuilds.
- Partition files are **append-only in practice**: once a row is
  written, only its `resolved_keeper_id`/`resolved_source`/`notes`
  columns ever change (when someone resolves it).
- A full rebuild on `2026-05-01` creates (or appends to)
  `docs/keeper-ambiguous/2026-05-01.csv`, but only for innings that
  were not already listed in an earlier partition. Older partitions
  are untouched — their existing rows and resolutions persist.

**Partition file format (CSV):**

```
innings_id,match_id,date,tournament,season,fielding_team,innings_number,
ambiguous_reason,candidate_ids,candidate_names,
resolved_keeper_id,resolved_source,notes
```

| Column | Populated by system? | Editable? |
|---|---|---|
| `innings_id`, `match_id`, `date`, `tournament`, `season`, `fielding_team`, `innings_number` | Yes | No |
| `ambiguous_reason` | Yes | No |
| `candidate_ids` (comma-separated person IDs) | Yes | No |
| `candidate_names` (comma-separated names, parallel to IDs) | Yes | No |
| `resolved_keeper_id` | Empty on creation | Yes — fill with a person_id |
| `resolved_source` | Empty | Yes — `cricinfo` \| `manual` \| `scraper:<date>` |
| `notes` | Empty | Yes — free text |

The first 10 columns are the system's output (do not edit). The last 3
are the resolution — populated either by a human editing the CSV in
Excel/VS Code or by a Cricinfo scraping script (see below).

### Resolution application (`scripts/apply_keeper_resolutions.py`)

Standalone, idempotent:

```
uv run python scripts/apply_keeper_resolutions.py
```

**Two use cases, one mechanism:**

1. **Filling in an ambiguous row** — edit an existing row in a
   partition CSV, set `resolved_keeper_id` to the person_id of the
   actual keeper. On apply, the matching `keeper_assignment` row
   flips from NULL to that person with `method='manual'`,
   `confidence='definitive'`.

2. **Overriding a high-confidence (or any) existing assignment** —
   the algorithm assigned Kishan via Layer B but we've since learned
   Arora actually kept. **Append a row** to any partition CSV
   (simplest: today's) with the `innings_id` and `resolved_keeper_id`
   filled in. `resolved_source` should be e.g. `manual`, `cricinfo`,
   or `scraper:2026-05-12`. The system columns (`ambiguous_reason`,
   `candidate_ids`, etc.) can be left blank — they'll be re-denormalized
   from the DB at apply time. On apply, the `keeper_assignment` row's
   existing `keeper_id` is overwritten, `method='manual'`,
   `confidence='definitive'`, and `ambiguous_reason` cleared.

**Manual overrides always win.** The apply step runs AFTER the 4-layer
algorithm in both `populate_full` and `populate_incremental`, so even a
full rebuild preserves every manual correction (as long as the row
stays in the CSV). Git history of the partition CSVs is the audit
trail — no separate `previous_keeper_id` column is tracked.

**Apply script behavior:**
1. Reads every `docs/keeper-ambiguous/*.csv`.
2. For each row where `resolved_keeper_id` is non-empty:
   - Verifies the person_id exists in `person`.
   - Verifies the innings_id exists in `keeper_assignment`.
   - Updates the matching row: set `keeper_id`, `method='manual'`,
     `confidence='definitive'`, clear `ambiguous_reason` and
     `candidate_ids_json`.
3. Reports: X new resolutions, Y high-confidence overrides, Z skipped
   (invalid person_id, innings no longer in DB, no change needed).

**Called automatically** at the end of `populate_full` and
`populate_incremental` so all manual corrections persist across DB
rebuilds. Also **runnable standalone** — if you edit a partition CSV
between full rebuilds, run this script and the live DB picks up the
changes without a full 15-min rebuild.

### Admin interface for per-innings corrections

CricsDB has a deebase-provided admin at `/admin/` that exposes every
table (including the new `keeper_assignment`) as CRUD views. Full
details — including how to find a specific innings, the Python 3.14
compatibility fix, and the authentication story — are in
[`internal_docs/admin-interface.md`](admin-interface.md).

**Relevant for Tier 2:** once `keeper_assignment` exists, the admin
lets you list, filter, and edit any row (change `keeper_id`, save).
But **admin edits are NOT auto-mirrored into the partition CSVs** —
they'll be overwritten by the algorithm on the next full rebuild.

**Recommended workflow:** use the admin to find an `innings_id` and
explore context (who was in the XI via `matchplayer`), then commit the
correction to a partition CSV so it persists through rebuilds.

**Prerequisite:** admin must be authenticated before Tier 2 ships
(`keeper_assignment` becomes a write target). See the admin doc for
the Basic Auth setup.

### Cricinfo resolution scraper (optional, future)

`scripts/scrape_cricinfo_keepers.py` can run in two modes:

- **Resolve-ambiguous** (default): iterate rows in a partition CSV
  where `resolved_keeper_id` is empty, fetch the corresponding
  Cricinfo scorecard, extract the wicketkeeper designation (Cricinfo
  marks keepers with a dagger `†` next to their name in the batting
  card, or `(wk)` in some templates), map the name back to a
  `person.id` via `person.name` + `personname`, and write
  `resolved_keeper_id` + `resolved_source='cricinfo'` back to the CSV.
  Conservative mode: writes only when the scraped keeper is ONE of
  the `candidate_ids` on that row.

- **Audit-and-correct**: a later pass over the full DB (all 25K
  innings, not just ambiguous). For each innings, scrape Cricinfo,
  and if the Cricinfo keeper differs from `keeper_assignment.keeper_id`,
  append a new row to today's partition CSV with
  `resolved_keeper_id=<cricinfo keeper>`,
  `resolved_source='cricinfo:audit:<date>'`, and `notes='was <old
  keeper>, method <old method>'`. Next run of
  `apply_keeper_resolutions.py` then overrides the algorithm's guess.

The audit mode is what lets us correct high-confidence assignments
that turn out to have been wrong — e.g. the Kishan+Arora case where
Layer B confidently picked Kishan but Arora actually kept. No change
to the storage model is needed; the same override mechanism handles
both filling ambiguous rows and correcting assigned ones.

Not part of v1 build — the partition CSVs work fine for hand-editing
in Excel. Adding this is a follow-on project.

### Algorithm (detailed)

For each regular innings (super_over = 0):

```
fielding_team = innings.team ≠ innings ? match.team1 : match.team2
xi = matchplayer { match_id = match.id, team = fielding_team }
stumpers_here = { fc.fielder_id : fc.kind='stumped' AND fc.innings_id=this }

# Layer A — stumping in this innings
if stumpers_here has exactly one non-null member S:
    assign(keeper_id=S, method='stumping', confidence='definitive')
    continue
if stumpers_here is non-empty but 2+ distinct non-null:
    ambiguous('multi_stumpers_same_innings', candidates=stumpers_here)
    continue
if stumpers_here contains a null (stumping happened, fielder unresolved):
    ambiguous('stump_fielder_unresolved', candidates=[])
    continue

# Layer B — season candidates
S_cands = season_candidates[(fielding_team, tournament, season)] ∩ xi
if |S_cands| == 1:
    assign(keeper_id=only(S_cands), method='season_single', confidence='high')
    continue
if |S_cands| >= 2:
    ambiguous('multi_season', candidates=S_cands)
    continue

# Layer C — career N>=3
C_cands = career_N3 ∩ xi
if |C_cands| == 1:
    assign(keeper_id=only(C_cands), method='career_single', confidence='medium')
    continue
if |C_cands| >= 2:
    ambiguous('multi_career', candidates=C_cands)
    continue

# Layer D — team-ever-keeper
T_cands = team_ever_keeper[fielding_team] ∩ xi
if |T_cands| == 1:
    assign(keeper_id=only(T_cands), method='team_ever_single', confidence='low')
    continue
if |T_cands| >= 2:
    ambiguous('multi_team_ever', candidates=T_cands)
    continue

# Nothing found
ambiguous('no_candidate', candidates=[])
```

The algorithm is **order-dependent on purpose**: the stronger signal
wins. A, B, C, D are tried in order, and the first layer that yields a
clear answer (or an ambiguity) terminates the search. A player who
would be the single N≥3 keeper at Layer C but is in a team where
someone else stumped more this season is still assigned via Layer B
(so the context matters).

## API layer

### New router: `api/routers/keeping.py`

Nested under the existing fielding namespace. All endpoints take the
standard `FilterParams` (gender, team_type, tournament, season_from,
season_to) via `Depends()`.

#### `GET /api/v1/fielders/{person_id}/keeping/summary`

```json
{
  "person_id": "4a8a2e3b",
  "name": "MS Dhoni",
  "innings_kept": 302,
  "innings_kept_by_confidence": {
    "definitive": 154,
    "high": 120,
    "medium": 28,
    "low": 0
  },
  "stumpings": 81,
  "keeping_catches": 165,
  "run_outs_while_keeping": 12,
  "byes_conceded": 234,
  "byes_per_innings": 0.77,
  "dismissals_while_keeping": 258,
  "keeping_dismissals_per_innings": 0.85,
  "ambiguous_innings": 26,
  "ambiguous_innings_link": "/matches?player=4a8a2e3b&keeper_ambiguous=1"
}
```

`byes_conceded` is `SUM(delivery.extras_byes)` across all deliveries in
innings where `keeper_assignment.keeper_id = this_person`.
`keeping_catches` is catches/c&b attributed to this person in innings
where they're the assigned keeper. `run_outs_while_keeping` counts
run-outs the keeper was credited on while keeping.

`innings_kept_by_confidence` is the key transparency number. If the
user sees `low: 45` for a minor-team keeper, they know how much of
the attribution is speculative.

#### `GET /api/v1/fielders/{person_id}/keeping/by-season`

Per-season keeping stats with the same shape as the batting/bowling
by-season endpoints. Each row has stumpings, keeping_catches,
run_outs_while_keeping, byes_conceded, innings_kept.

#### `GET /api/v1/fielders/{person_id}/keeping/by-innings`

Paginated list of innings where this person was the assigned keeper.
One row per innings with confidence label, stumpings-this-innings,
catches-this-innings, byes-this-innings.

#### `GET /api/v1/fielders/{person_id}/keeping/ambiguous`

The list of ambiguous innings where this person is one of the
candidates. Lets the UI show *"26 innings where MS Dhoni might have
kept — see list"*.

### Changes to the existing scorecard endpoint

`GET /api/v1/matches/{match_id}/scorecard` gains a per-innings field:

```json
{
  "innings": [
    {
      "team": "Chennai Super Kings",
      ...
      "keeper": {
        "person_id": "4a8a2e3b",
        "name": "MS Dhoni",
        "confidence": "definitive",
        "method": "stumping"
      },
      ...
    }
  ]
}
```

When the innings is ambiguous, `keeper` is `{"person_id": null,
"confidence": null, "ambiguous_reason": "multi_season",
"candidate_ids": [...], "candidate_names": [...]}`.

### Changes to the existing team endpoint

`GET /api/v1/teams/{team}/summary` gains:

```json
{
  "keepers": [
    { "person_id": "4a8a2e3b", "name": "MS Dhoni", "innings_kept": 245 },
    { "person_id": "3e3b6b14", "name": "WP Saha", "innings_kept": 8 }
  ],
  "keeper_ambiguous_innings": 12
}
```

Ranked by innings kept. Helps the team page show "Who kept for this
team" without needing a separate endpoint.

## Frontend layer

### New sub-tab: "Keeping" on `/fielding`

Only shown when `keeping/summary.innings_kept > 0`. Position: after
"Innings List", or inserted before "Victims" — TBD during build.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [same player header + stat-row as existing page]    │
├──────────────────────────────────────────────────────┤
│  Tabs: [By Season] [By Over] [By Phase]              │
│        [Dismissal Types] [Victims] [Innings List]    │
│        [Keeping] ← new                                │
├──────────────────────────────────────────────────────┤
│  Keeping sub-tab:                                    │
│                                                      │
│  Summary row (6 cards):                              │
│  ┌─────────┬──────────┬──────────┬──────────────────┐│
│  │Stumpings│Keep Catches│Byes Conc│Inn as Keeper │ …││
│  │   81    │    165    │   234   │     302       │ ..│
│  └─────────┴──────────┴──────────┴──────────────────┘│
│                                                      │
│  Confidence breakdown (subtle, below cards):         │
│  ┌──────────────────────────────────────────────┐    │
│  │ Of 302 keeping innings: 154 definitive,       │    │
│  │ 120 high, 28 medium, 0 low confidence.        │    │
│  │ 26 additional innings ambiguous — link to     │    │
│  │ worklist.                                     │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  Charts:                                             │
│  [By Season: stumpings + catches stacked]            │
│  [Byes by season: bar chart]                         │
│                                                      │
│  Keeping innings list (paginated, 50/page):          │
│  date → scorecard link, opponent, tournament,        │
│  stumpings-this-inn, catches-this-inn,               │
│  byes-this-inn, confidence                           │
└──────────────────────────────────────────────────────┘
```

### Match scorecard: per-innings keeper label

Just above each InningsCard's batting table, a small italic line:

> **Keeper:** *MS Dhoni* (definitive)

Or when ambiguous:

> **Keeper:** *ambiguous — MS Dhoni or WP Saha*

The label is clickable to the keeper's `/fielding?player=...&tab=Keeping`
page.

### Team page: keepers used

A new section in the Teams page summary card:

> **Keepers used:** MS Dhoni (245), WP Saha (8), RD Gaikwad (3) · 12 innings ambiguous

Each name links to `/fielding?player=...&tab=Keeping`.

### Player page (Fielding): caveat banner

At the top of the Keeping sub-tab, a one-line notice when the player
has any `low` confidence innings or any ambiguous innings:

> *Keeping stats identified for 302 of 328 career keeping innings
> (92%). 26 innings ambiguous — see ambiguous list.*

## Implementation order

1. **`keeper_assignment` model** in `models/tables.py` (~15 lines).
2. **`scripts/populate_keeper_assignments.py`** — the 4-layer
   algorithm with `populate_full` and `populate_incremental`. Includes
   partition-CSV reading/writing and resolution application.
3. **`scripts/apply_keeper_resolutions.py`** — standalone resolution
   applier. Also used internally at the end of `populate_full` and
   `populate_incremental`.
4. **Hook into `import_data.py` and `update_recent.py`** — one line
   each, after the `fielding_credit` populate call.
5. **Run full populate on the existing DB** — verify counts match
   this spec's expected ~82.2% assigned, 17.8% null. Commit the
   resulting first partition file
   `docs/keeper-ambiguous/YYYY-MM-DD.csv`.
6. **`docs/keeper-ambiguous/README.md`** — partition format,
   how to resolve a row (edit `resolved_keeper_id`, `resolved_source`,
   then run `apply_keeper_resolutions.py`).
7. **`api/routers/keeping.py`** — the four keeping endpoints.
8. **Changes to scorecard and teams endpoints** — add keeper info.
9. **Frontend types + API client additions.**
10. **"Keeping" sub-tab** on `/fielding`.
11. **Scorecard keeper label** on `/matches/:id`.
12. **Team-page "Keepers used" section.**
13. **Deploy + verify** with known test cases.

## Test cases

- **Dhoni keeping summary** (IPL only) — stumpings should match
  his ~60-70 IPL stumpings; innings_kept should be ~260+ with
  `definitive` dominant.
- **KL Rahul keeping** (LSG 2022–2024) — should show him as keeper
  for most of those seasons via Layer B, even though Karthik has
  more total career stumpings.
- **Ishan Kishan keeping** — mixed signal expected; some innings
  attributed via B, some to the competing keeper (Pant for India,
  etc.).
- **KA Pollard keeping** — should be 0 innings kept (Tier 1 test
  said he had 0 stumpings; he shouldn't show up in the keeper_id
  column at all). Keeping sub-tab should NOT appear on his page.
- **A known minor-team match** — confirm `low` confidence attribution
  via Layer D.
- **IPL 2026 match with Kishan + Arora both in MI XI, no stumping** —
  should mark `multi_season` ambiguous (null); match should appear
  in `keeper-ambiguous.csv`.
- **Scorecard page** for a definitive match — keeper label renders.
- **Scorecard page** for an ambiguous match — "ambiguous — X or Y"
  renders, both names clickable.
- **Incremental update** — import one new match, verify the new
  innings get assignments (or NULL) without crashing; existing
  assignments aren't touched. If the new match has ambiguous innings,
  they appear in today's partition CSV file (appending if one
  already exists today).
- **Partition persistence** — run a full rebuild twice on consecutive
  days without any new data. Second day's partition CSV should NOT
  contain any of the same innings as day-1's (each `innings_id`
  appears in exactly one partition).
- **Resolution roundtrip** — pick a `multi_season` row from a
  partition CSV, fill in `resolved_keeper_id` with a valid person_id,
  run `apply_keeper_resolutions.py`, verify the matching
  `keeper_assignment` row is now (keeper_id=X, method='manual',
  confidence='definitive', ambiguous_reason=NULL). Run a full rebuild;
  verify the resolution persists (and is re-applied from the CSV).
- **Bad resolution rejected** — put an invalid person_id in a
  partition CSV, run `apply_keeper_resolutions.py`, verify that row
  is skipped with a warning and the keeper_assignment stays NULL.

## Out of scope (for Tier 2)

- **Back-filling older ambiguous innings** when a new match changes
  the season-candidate signal. Incremental path doesn't do this by
  design; full rebuild does. Consider a `--refresh-season` flag later.
- **Mid-innings keeper changes** (5 matches in the DB have 2+
  stumpers in one innings; flagged as `multi_stumpers_same_innings`).
- **External data integration** (Cricinfo scraping) to resolve
  ambiguous innings. Worklist CSV is the handoff point; actual
  resolution is a separate project.
- **Manual curation file** (`keeper_assignments_override.py`) that
  takes precedence over inference. Plausible future addition but
  not v1.
- **Keeping positions** (slip catches as keeper vs front-of-bat):
  not in cricsheet, never will be.

## Estimated effort

- Data layer (steps 1–4): ~3 hours
- API (steps 5–6): ~3 hours
- Frontend (steps 7–10): ~4 hours
- Worklist CSV + testing (steps 11–12): ~1 hour

Total: ~10–11 hours.
