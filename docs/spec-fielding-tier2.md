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

Mirrors `populate_fielding_credits.py`:

```python
async def populate_full(db):
    # 1. Build the candidate sets (cheap, mostly in-memory aggregations):
    #    - career_stumpings[person_id] = count
    #    - career_N3 = {pid: count >= 3}
    #    - season_candidates[(fielding_team, tournament, season)] = {person_id, ...}
    #    - team_ever_keeper[fielding_team] = {person_id, ...}
    #    - stumpers_by_innings[innings_id] = {person_id or None, ...}
    #    - xi[match_id][team] = {person_id, ...}  (from matchplayer)

    # 2. Truncate keeper_assignment.
    # 3. For each regular innings:
    #    - Determine fielding_team (team NOT batting this innings)
    #    - Apply layers A, B, C, D in order
    #    - Insert one row: either (keeper_id, method, confidence) or
    #      (NULL, NULL, NULL, ambiguous_reason, candidate_ids_json)
    # 4. Export docs/keeper-ambiguous.csv with one row per NULL.

async def populate_incremental(db, new_match_ids):
    # Only recompute assignments for innings in new_match_ids.
    # NOTE: this is subtler than populate_fielding_credits — a new match
    # can change `season_candidates` for an existing (team, tournament,
    # season), which could retroactively resolve ambiguous older innings.
    # For simplicity, incremental does NOT retrofit; a full rebuild is
    # needed to take advantage of new signals. Document this limitation.
```

**Why the incremental path is simpler than full**: incremental adds new
matches' innings with whatever signals are available *at that point*.
A match played today that introduces a new keeper candidate for
(Team, 2025) doesn't back-fill older 2025 innings where we already
wrote an assignment. In practice the full-rebuild path runs ~15 min
and is the authoritative one; incremental is just to keep the site
responsive for daily updates.

Both paths are called automatically — no separate script invocation
needed, same pattern as `fielding_credit`.

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

### Ambiguous worklist (`docs/keeper-ambiguous.csv`)

Generated at the end of `populate_full`. Columns:

```
match_id,date,tournament,season,fielding_team,ambiguous_reason,candidate_names,candidate_ids
1234567,2024-05-26,Indian Premier League,2024,Chennai Super Kings,multi_season,"MS Dhoni,WP Saha","4a8a2e3b,..."
```

One row per ambiguous innings. Sorted by `(ambiguous_reason, date DESC)`
so the highest-value targets (recent `multi_season` cases in major
leagues) float to the top. Committed to the repo so progress on
manual / Cricinfo-sourced disambiguation is visible in diffs.

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
   algorithm, plus the ambiguous CSV export. Full + incremental.
3. **Hook into `import_data.py` and `update_recent.py`** — one line
   each, after `populate_full` / `populate_incremental` for
   fielding_credit.
4. **Run full populate on the existing DB** — verify counts match
   this spec's expected ~82.2% assigned, 17.8% null.
5. **`api/routers/keeping.py`** — the four keeping endpoints.
6. **Changes to scorecard and teams endpoints** — add keeper info.
7. **Frontend types + API client additions.**
8. **"Keeping" sub-tab** on `/fielding`.
9. **Scorecard keeper label** on `/matches/:id`.
10. **Team-page "Keepers used" section.**
11. **Generate `docs/keeper-ambiguous.csv`** — commit the first
    authoritative copy.
12. **Deploy + verify** with known test cases.

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
  assignments aren't touched.

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
