# Spec: Team Statistics — Batting, Bowling, Fielding, Partnerships

Status: build-ready.
Depends on: `fielding_credit` (shipped), `keeper_assignment` (shipped).

## Overview

The current Teams page is match-outcome-focused: wins/losses, by season, vs
opponent, match list. This spec adds **ball-level team statistics** —
batting, bowling, fielding, and partnerships — at two granularities:
lifetime and per-season.

The centerpiece is a new `partnership` table that serves both sides of the
same fact: when Team A made a 56-run opening stand, Team B conceded 56 runs
for the 1st wicket. One table, two filters.

Everywhere else in this spec the aggregate metrics come from SQL aggregates
over the existing `delivery` / `wicket` / `fielding_credit` / `keeper_assignment`
tables — **no new tables for batting, bowling, or fielding rollups**.

**New tab structure on `/teams`:**

```
Overview | By Season | vs Opponent | Matches | Batting | Bowling | Fielding | Partnerships
```

All tabs honour the existing FilterBar params (`gender`, `team_type`,
`tournament`, `season_from`, `season_to`). When a single season is in
scope (`season_from = season_to`), by-season charts collapse naturally.

**Design precedent for `/tournaments` (enhancement M):** if these tabs
drill into a season via the FilterBar rather than via the URL path, then
`/tournaments/:slug` should do the same — a single slug level with season
as a filter, not `/tournaments/:slug/:season`. Two route levels, not
three.

## Scope

- **New table**: `partnership` — one row per on-field batting partnership.
- **New population script**: `scripts/populate_partnerships.py` with
  `populate_full()` and `populate_incremental(new_match_ids)`,
  auto-called from `import_data.py` and `update_recent.py` (same pattern
  as `fielding_credit` and `keeper_assignment`).
- **New API endpoints** on the teams router covering batting, bowling,
  fielding, and partnerships — lifetime and by-season.
- **Frontend changes**: four new tabs on `/teams` plus a Semiotic-based
  season × wicket heatmap component.

Explicitly **not in scope** (kept as future work): batter-level
"partnerships with X" view on player pages; bowler-level "most
partnerships broken" stat; partnership-on-scorecard visualization.

## Data layer

### `partnership` table

```
partnership
  id                 INTEGER PK
  innings_id         INTEGER FK → innings
  wicket_number      INTEGER       (1..11+; cricsheet running wicket count.
                                    NULL iff unbroken.)
  batter1_id         VARCHAR FK → person   (earlier-arriver; NULL if name unresolved)
  batter2_id         VARCHAR FK → person   (later-arriver; NULL if name unresolved)
  batter1_name       TEXT          (display fallback when person_id is NULL)
  batter2_name       TEXT
  batter1_runs       INTEGER       (runs off the bat for batter1 while batter1 was on strike)
  batter1_balls      INTEGER       (legal balls faced by batter1 — wides/noballs excluded)
  batter2_runs       INTEGER
  batter2_balls      INTEGER
  partnership_runs   INTEGER       (SUM(delivery.runs_total) — includes all extras)
  partnership_balls  INTEGER       (legal balls only — wides/noballs excluded)
  start_delivery_id  INTEGER FK → delivery  (first delivery of the partnership)
  end_delivery_id    INTEGER FK → delivery  (last delivery of the partnership)
  unbroken           BOOLEAN       (TRUE iff the innings ended before a wicket ended this partnership)
  ended_by_kind      VARCHAR       (wicket.kind of the terminating wicket;
                                    NULL when unbroken)
```

**Indexes**: `innings_id`, `batter1_id`, `batter2_id`, `wicket_number`,
`unbroken`, and a composite `(innings_id, wicket_number)` for the
common "get all partnerships for an innings in order" query.

**Expected row count**: ~25,880 non-super-over innings × ~6 partnerships
avg ≈ **150K rows**. Tiny by SQLite standards, no disk-size concern.

**Key modelling decisions:**

- **`partnership_runs` includes extras.** `SUM(delivery.runs_total)`, not
  `SUM(delivery.runs_batter)`. This makes the innings total reconcile
  exactly with `SUM(partnership_runs) + penalty_runs` and makes the
  bowling-conceded view honest (you conceded those wides, they count).
  Per-batter `batter1_runs` / `batter2_runs` are off-the-bat only — bat
  stats stay clean.
- **`partnership_balls` excludes wides and no-balls.** Consistent with
  how legal balls are counted everywhere else in the codebase.
- **`batter1` = earlier-arriver.** For the 1st-wicket partnership both
  batters arrive simultaneously; by convention `batter1` = striker on
  the partnership's first delivery. For subsequent partnerships,
  `batter1` is the survivor of the previous partnership.
- **`wicket_number`** follows cricsheet's running wicket count. Retired
  hurt / retired not out **do** increment the wicket count in cricsheet
  data, so they'll appear as terminating wickets here too. Queries that
  want "avg runs before the Nth real dismissal fell" filter
  `ended_by_kind NOT IN ('retired hurt', 'retired not out')`.
- **Unbroken partnership always emitted.** If the innings ends with the
  two batters still together (chased successfully, overs expired, declared),
  one row with `unbroken = TRUE`, `wicket_number = NULL`, `ended_by_kind = NULL`.
- **Super-over innings excluded.** `WHERE innings.super_over = 0` at
  populate time. (Super-over partnerships are structurally different
  and of little stats interest.)

### Population logic (`scripts/populate_partnerships.py`)

Simpler than `populate_keeper_assignments.py` — no candidate sets,
purely a function of the ordered delivery stream within each innings.

```python
async def populate_full(db):
    # 1. Truncate partnership.
    # 2. For each innings WHERE super_over = 0, ORDER BY id:
    #    scan its deliveries in (over_number, delivery_index) order,
    #    emit one partnership row per partnership ended (by wicket or
    #    by end of innings). See algorithm below.

async def populate_incremental(db, new_match_ids):
    # 1. DELETE FROM partnership WHERE innings_id IN
    #    (SELECT id FROM innings WHERE match_id IN :new_match_ids).
    # 2. Run the same per-innings scan for the new innings only.
```

Both called automatically at the end of `import_data.py` (full) and
`update_recent.py` (incremental), after the existing
`populate_fielding_credits` + `populate_keeper_assignments` steps.

#### Per-innings scan

```
partnership_open(striker_id, nonstriker_id, start_delivery_id):
    # batter1 = earlier-arriver. For the first partnership of an innings,
    # convention: batter1 = striker on first delivery.
    # For subsequent partnerships, caller passes the survivor as striker_id.
    (batter1_id, batter2_id) = (striker_id, nonstriker_id)
    batter1_runs = batter1_balls = 0
    batter2_runs = batter2_balls = 0
    partnership_runs = partnership_balls = 0
    start = start_delivery_id
    return State(...)

for innings in innings_ordered:
    deliveries = SELECT * FROM delivery
                 WHERE innings_id = :inn
                 ORDER BY over_number, delivery_index
    if not deliveries: continue

    state = partnership_open(
        striker_id=deliveries[0].batter_id,
        nonstriker_id=deliveries[0].non_striker_id,
        start_delivery_id=deliveries[0].id)
    wicket_count = 0

    for d in deliveries:
        legal = (d.extras_wides == 0 AND d.extras_noballs == 0)
        state.partnership_runs += d.runs_total
        if legal: state.partnership_balls += 1

        # Per-batter: striker gets off-bat runs + legal balls
        if d.batter_id == state.batter1_id:
            state.batter1_runs += d.runs_batter
            if legal: state.batter1_balls += 1
        else:
            state.batter2_runs += d.runs_batter
            if legal: state.batter2_balls += 1

        # Wicket?
        w = wicket for this delivery (if any)
        if w:
            wicket_count += 1
            emit_partnership(state, innings_id=innings.id,
                             wicket_number=wicket_count,
                             end_delivery_id=d.id,
                             unbroken=False,
                             ended_by_kind=w.kind)
            # Survivor: the batter NOT out. If player_out_id matches neither
            # (rare — unresolved person), fall back to player_out name match.
            out_id = w.player_out_id
            survivor = state.batter2_id if out_id == state.batter1_id else state.batter1_id
            # Next delivery tells us the new batter. We don't know it yet,
            # so mark "partnership pending" and fill batter1_id=survivor,
            # batter2_id from next delivery's striker/non_striker (whichever
            # is new).
            pending_survivor = survivor

        elif pending_survivor and d is first delivery after a wicket:
            new_pair = {d.batter_id, d.non_striker_id}
            new_arriver = (new_pair - {pending_survivor}).pop()
            state = partnership_open(
                striker_id=pending_survivor,      # earlier-arriver
                nonstriker_id=new_arriver,
                start_delivery_id=d.id)
            # Now fall through and process this delivery's runs as above.
            # (Rewind: we already skipped the runs processing on this
            #  delivery above; re-apply it once state is reset.)

    # Innings ended without a final wicket — emit unbroken partnership.
    if state.partnership_runs > 0 or state.partnership_balls > 0:
        emit_partnership(state, innings_id=innings.id,
                         wicket_number=NULL, end_delivery_id=deliveries[-1].id,
                         unbroken=True, ended_by_kind=NULL)
```

**Edge cases handled:**

- **Wicket on the final delivery**: partnership emitted with `unbroken=False`;
  no "unbroken" row is appended. Detected by checking if the last emit was
  for the last delivery.
- **Unresolved `player_out_id`**: fall back to matching `w.player_out`
  (name string) against `state.batter1_name` / `state.batter2_name`. If
  still ambiguous, emit with `batter1_id = NULL`, `batter2_id = NULL`
  so the row is still counted in totals but doesn't corrupt per-batter
  leaderboards. Expected to be <0.1% of rows.
- **Retired hurt followed by return**: cricsheet emits two separate
  wicket rows with the same `player_out`. Each ends a partnership. When
  the player returns, a new partnership opens with them as `batter2`
  (the new arriver). Their aggregate runs across both stints are
  derivable via `SUM(batter2_runs) WHERE batter2_id = :pid AND innings_id = :inn`.
- **`obstructing the field` / `hit the ball twice`**: treated like any
  other dismissal.
- **Non-striker run out**: the non-striker is out; striker survives.
  Algorithm handles this naturally via `out_id` comparison.

### Team-aggregate queries (no new tables needed)

All team batting / bowling / fielding stats are SQL aggregates over
existing tables, scoped by `innings.team` (batting) or by
`match.team1/team2 AND innings.team != :team` (bowling/fielding). Below
are the canonical query shapes — each endpoint takes standard
`FilterParams` and adds its own team clauses.

**Team batting totals** (one value per metric, lifetime or filtered):
```sql
SELECT
    COUNT(DISTINCT i.id) as innings_batted,
    SUM(d.runs_total) as total_runs,
    SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
    SUM(CASE WHEN d.runs_batter = 4 AND NOT d.runs_non_boundary THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE i.team = :team AND i.super_over = 0 {filters}
```

Run rate = `total_runs * 6.0 / legal_balls`. Dot % = `dots * 100.0 / legal_balls`.

**Team bowling totals**: swap `i.team = :team` → `i.team != :team AND
(m.team1 = :team OR m.team2 = :team)`, and add `JOIN wicket w ON
w.delivery_id = d.id` for wicket counts. Standard bowler-wicket
exclusions apply (`w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')`).

**Team fielding totals**: aggregate `fielding_credit` joined to
`innings` and filter `i.team != :team AND (m.team1 = :team OR m.team2 = :team)`
(fielder's side was bowling). Plus keeper counts from `keeper_assignment`
(same filter) for stumping totals.

**Partnership queries — batting (`side=batting`)**:
```sql
SELECT
    p.wicket_number,
    COUNT(*) as n,
    AVG(p.partnership_runs) as avg_runs,
    AVG(p.partnership_balls) as avg_balls,
    MAX(p.partnership_runs) as best_runs
FROM partnership p
JOIN innings i ON i.id = p.innings_id
JOIN match m ON m.id = i.match_id
WHERE i.team = :team
  AND i.super_over = 0
  AND p.wicket_number IS NOT NULL                    -- only ended partnerships
  AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
  {filters}
GROUP BY p.wicket_number
ORDER BY p.wicket_number
```

**Partnership queries — bowling (`side=bowling`)**: replace
`i.team = :team` with `i.team != :team AND (m.team1 = :team OR m.team2 = :team)`.

**By season × wicket heatmap**: add `m.season` to `SELECT` and `GROUP BY`.

**Top N partnerships**: `ORDER BY p.partnership_runs DESC LIMIT :n`,
no `wicket_number` filter; join to `person` for batter names; include
`match_id` for scorecard linking.

## API layer

All endpoints live in `api/routers/teams.py` (extending the existing
router — no new file). All take the standard `FilterParams` via
`Depends()`.

### Batting endpoints

#### `GET /api/v1/teams/{team}/batting/summary`

```json
{
  "team": "Mumbai Indians",
  "innings_batted": 278,
  "total_runs": 45234,
  "legal_balls": 32456,
  "run_rate": 8.36,
  "boundary_pct": 17.8,
  "dot_pct": 37.2,
  "fours": 3840,
  "sixes": 1720,
  "fifties": 312,
  "hundreds": 24,
  "avg_1st_innings_total": 178.4,
  "avg_2nd_innings_total": 152.1,
  "highest_total": {"runs": 235, "match_id": 12834, "opponent": "..."},
  "lowest_all_out_total": {"runs": 66, "match_id": 8422, "opponent": "..."}
}
```

#### `GET /api/v1/teams/{team}/batting/by-season`

```json
{
  "seasons": [
    {"season": "2023", "innings_batted": 17, "total_runs": 2870,
     "run_rate": 8.65, "boundary_pct": 18.2, "fours": 240, "sixes": 112},
    ...
  ]
}
```

#### `GET /api/v1/teams/{team}/batting/by-phase`

```json
{
  "phases": [
    {"phase": "powerplay", "overs_range": [1, 6],
     "runs": 8120, "balls": 6520, "run_rate": 7.47,
     "wickets_lost": 234, "boundary_pct": 15.1, "dot_pct": 42.0},
    {"phase": "middle", "overs_range": [7, 15], ...},
    {"phase": "death",  "overs_range": [16, 20], ...}
  ]
}
```

#### `GET /api/v1/teams/{team}/batting/top-batters?limit=5`

Top run-scorers for the team (filtered scope), linked to player pages.

### Bowling endpoints

Mirror batting with bowling metrics:

- `GET /api/v1/teams/{team}/bowling/summary` — balls bowled, runs conceded,
  wickets, economy, strike rate, average, dot %, boundaries conceded,
  wides/no-balls per match.
- `GET /api/v1/teams/{team}/bowling/by-season`
- `GET /api/v1/teams/{team}/bowling/by-phase`
- `GET /api/v1/teams/{team}/bowling/top-bowlers?limit=5`

### Fielding endpoints

- `GET /api/v1/teams/{team}/fielding/summary` — catches, stumpings,
  run-outs (direct / assisted), dropped-catch placeholder (not in data —
  omit field), per-match rates.
- `GET /api/v1/teams/{team}/fielding/by-season`
- `GET /api/v1/teams/{team}/fielding/top-fielders?limit=5` — by catches;
  includes keepers from `keeper_assignment`.

The existing `GET /api/v1/teams/{team}/summary`'s `keepers` sub-object
stays where it is (already shipped in Tier 2). It's duplicated on the
Fielding tab for discoverability.

### Partnership endpoints

#### `GET /api/v1/teams/{team}/partnerships/by-wicket?side=batting`

```json
{
  "team": "Mumbai Indians",
  "side": "batting",
  "by_wicket": [
    {"wicket_number": 1, "n": 256, "avg_runs": 43.2, "avg_balls": 31.1,
     "best_runs": 184, "best_partnership": {
       "match_id": 8391, "date": "2013-05-05", "opponent": "RCB",
       "batter1": {"person_id": "...", "name": "SR Tendulkar"},
       "batter2": {"person_id": "...", "name": "DR Smith"}
     }},
    {"wicket_number": 2, ...},
    ...
    {"wicket_number": 10, ...}
  ]
}
```

For `side=bowling`, same shape but values are runs **conceded** by this
team before that opposition wicket fell.

#### `GET /api/v1/teams/{team}/partnerships/heatmap?side=batting`

Season × wicket matrix for the Semiotic heatmap.

```json
{
  "seasons": ["2018", "2019", ..., "2024"],
  "wickets": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "cells": [
    {"season": "2018", "wicket_number": 1, "avg_runs": 42.1, "n": 16},
    {"season": "2018", "wicket_number": 2, "avg_runs": 28.4, "n": 16},
    ...
  ]
}
```

Cell value = `avg_runs`; `n` is for hover tooltip (sample size).
Cells with `n < 2` are returned but flagged so the frontend can dim
them (low confidence).

#### `GET /api/v1/teams/{team}/partnerships/top?side=batting&limit=10`

```json
{
  "partnerships": [
    {
      "partnership_id": 78234,
      "match_id": 8391,
      "date": "2013-05-05",
      "season": "2013",
      "tournament": "Indian Premier League",
      "opponent": "Royal Challengers Bangalore",
      "wicket_number": 1,
      "runs": 184,
      "balls": 77,
      "batter1": {"person_id": "...", "name": "SR Tendulkar", "runs": 76, "balls": 41},
      "batter2": {"person_id": "...", "name": "DR Smith",     "runs": 94, "balls": 33},
      "unbroken": false,
      "ended_by_kind": "caught"
    },
    ...
  ]
}
```

Match_id links to scorecard. Person IDs link to batter pages.

## Frontend layer

### New `<HeatmapChart>` wrapper

`frontend/src/components/charts/HeatmapChart.tsx` — thin Semiotic v3
`XYFrame` wrapper with `summaryType="tiles"`. Props: `cells` (array of
`{x, y, value, n}`), `xCategories`, `yCategories`, `colorRange`
(oxblood light → oxblood dark for positive metrics, inverted for
economy-style "low is good"), `onCellHover`.

Reused by both the partnership heatmap and the phase × season heatmaps
on the batting/bowling tabs.

### Team page — four new tabs

#### Batting tab

```
┌──────────────────────────────────────────────────────┐
│  [summary cards: Run Rate | Boundary % | Dot % |     │
│                  Fours | Sixes | 50s | 100s]         │
├──────────────────────────────────────────────────────┤
│  [Avg 1st-inn total | Avg 2nd-inn chase |            │
│   Highest total | Lowest all-out]                    │
├──────────────────────────────────────────────────────┤
│  <LineChart> Run rate by season                      │
│  <LineChart> Boundary % by season                    │
├──────────────────────────────────────────────────────┤
│  Phase split (PP / Middle / Death)                   │
│  <BarChart> runs + <BarChart> run rate               │
├──────────────────────────────────────────────────────┤
│  Top 5 batters — table, linked to batter pages       │
└──────────────────────────────────────────────────────┘
```

#### Bowling tab

Same shape, bowling metrics. Economy by season line chart; phase-split
economy bars; top 5 wicket-takers.

#### Fielding tab

Summary cards (catches, stumpings, run-outs, per-match rate); by-season
line chart for catches-per-match; top 5 fielders table; existing keepers
rollup moved here (duplicated from Overview — same data, different
home).

#### Partnerships tab

```
┌──────────────────────────────────────────────────────┐
│  [Toggle: Our Partnerships | Partnerships Conceded]  │
├──────────────────────────────────────────────────────┤
│  By Wicket table (1..10)                             │
│  wkt | n | avg | best | best opponent / date         │
├──────────────────────────────────────────────────────┤
│  <HeatmapChart> Season × Wicket (avg runs)           │
│  (hidden when FilterBar season range = 1 season)     │
├──────────────────────────────────────────────────────┤
│  Top 10 partnerships — table                         │
│  linked: match → scorecard, batters → batter pages   │
└──────────────────────────────────────────────────────┘
```

The toggle is a URL param (`?partnership_side=batting|bowling`,
default `batting`) so deep links work and the choice survives a
refresh.

### FilterBar interaction

All four tabs honour `gender`, `team_type`, `tournament`, `season_from`,
`season_to`. When a single season is in scope:
- By-season line charts collapse to a single point (or the tab's
  summary cards show only that season's numbers; the line chart
  component detects `dataPoints.length === 1` and renders a single-stat
  card instead).
- Partnership heatmap hides itself (single-column heatmap is pointless)
  and the by-wicket table shows season-specific averages.

## Implementation order

1. **`partnership` model** in `models/tables.py` (~20 lines).
2. **`scripts/populate_partnerships.py`** — per-innings scan +
   `populate_full` / `populate_incremental`.
3. **Hook into `import_data.py` and `update_recent.py`** — one line each,
   after the `keeper_assignment` populate call.
4. **Run full populate on the existing DB** — verify row count
   ~150K; spot-check 5–10 known partnerships against Cricinfo.
5. **Batting endpoints** (`/batting/summary`, `/by-season`, `/by-phase`,
   `/top-batters`).
6. **Bowling endpoints** (mirror).
7. **Fielding endpoints** — summary + by-season + top-fielders.
8. **Partnership endpoints** — by-wicket, heatmap, top.
9. **Frontend types** + API client additions.
10. **`<HeatmapChart>` component** (reusable).
11. **Batting tab** on Teams page.
12. **Bowling tab.**
13. **Fielding tab** (move keeper rollup over).
14. **Partnerships tab** — toggle, by-wicket table, heatmap, top 10.
15. **Deploy + verify** against test cases.

## Test cases

### Data population

- **Row count sanity**: after full populate,
  `SELECT COUNT(*) FROM partnership` should be between 120K and 180K.
  `SELECT COUNT(*) FROM partnership WHERE unbroken` should equal the
  number of innings where the batting side wasn't all out.
- **Innings reconcile**: for 10 random non-super-over innings,
  `SUM(partnership_runs) + penalty_runs` should equal the innings total
  computed from `SUM(delivery.runs_total)`. (Exact match — both include
  extras.)
- **Known partnership spot-check**: e.g., Tendulkar + Smith 163
  opening partnership vs RCB in IPL 2013 (adjust to a real partnership
  from the DB) — verify `partnership_runs`, `batter1_runs`,
  `batter2_runs` match Cricinfo scorecard.
- **Retired hurt roundtrip**: find an innings with a known retired-hurt
  batter who returned; verify two partnership rows for them and the
  batter_id appears as `batter2_id` in the second row.
- **Incremental idempotence**: run `populate_incremental` twice for the
  same match_ids; row count unchanged, no duplicates.

### Batting/bowling/fielding queries

- **Mumbai Indians lifetime run rate** ~8.3–8.5 (sanity).
- **CSK lifetime catches per match** should be in a reasonable cricket
  range (5–7).
- **Filter round-trip**: Mumbai Indians batting summary with
  `tournament=IPL&season_from=2023&season_to=2023` should match the
  hand-computed 2023 IPL season stats.
- **Gender-breakdown guard**: team that appears in both men's and
  women's matches (e.g., Mumbai Indians / WPL) — summary without a
  gender filter returns combined numbers; FilterBar's gender pill
  corrects it (existing behaviour on Overview, mirrored here).

### Partnership queries

- **By-wicket ordering**: `by-wicket` returns exactly 10 rows (one per
  wicket) or fewer if a wicket number has zero partnerships in scope.
- **Batting vs bowling sum**: the total partnership_runs in a given
  match-set, queried from the batting side for team A should equal
  the total queried from the bowling side for team A's opponents in
  the same matches.
- **Heatmap coverage**: heatmap cells × seasons should roughly equal
  `sum(by_season.innings_batted)` per wicket-number row. Missing
  (wicket, season) cells (no partnership yet at that wicket in that
  season) are omitted from `cells`, not zero-filled.
- **Top 10 consistency**: `best_runs` from the `by-wicket` response for
  any wicket_number should appear as the top partnership for that
  wicket in the `top?limit=10` list (for a large enough limit).

### Frontend

- **Partnerships toggle**: switching batting↔bowling updates the URL
  param and all three widgets (by-wicket table, heatmap, top 10).
- **Heatmap responsive sizing**: heatmap fills its container width on
  desktop, scrolls horizontally on narrow mobile (min 600px).
- **Season filter collapses heatmap**: setting
  `season_from=2023&season_to=2023` hides the heatmap, keeps the
  by-wicket table.

## Out of scope (for v1)

- **Batter-level partnership stats** ("best partnerships with X" on a
  batter's page). Table supports it; just needs endpoints + UI.
- **Bowler-level partnership stats** ("partnerships broken by X").
  Requires joining `partnership.end_delivery_id → delivery → wicket →
  bowler`. Natural follow-on.
- **Partnership visualisation on the match scorecard** (a mini worm
  chart of the partnership's runs+balls, or a partnership strip
  annotated with wicket markers). Useful but more design work.
- **Dropped catches**: not in cricsheet data, ever. No placeholder,
  no faking.
- **Per-over run-rate heatmap** (season × over). Doable with the same
  `<HeatmapChart>`, but batting/bowling tabs already have phase-split
  coverage.
- **Win-probability-adjusted partnership value** — interesting, but
  requires a model we don't have.

## Estimated effort

- Data layer (steps 1–4): ~4 hours
- Batting + bowling endpoints (5–6): ~3 hours
- Fielding endpoints (7): ~1.5 hours
- Partnership endpoints (8): ~2 hours
- Frontend types + heatmap component (9–10): ~3 hours
- Four tabs (11–14): ~6 hours
- Testing + polish + deploy (15): ~2 hours

Total: ~21–22 hours.
