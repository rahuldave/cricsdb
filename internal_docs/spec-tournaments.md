# Spec: Tournaments tab (enhancement M)

Status: build-ready.
Depends on: existing `match`, `innings`, `delivery`, `wicket`,
`fielding_credit`, `keeper_assignment`, `partnership` tables.
No new tables required.

## Overview

Cricket has two collective scopes that FilterBar already captures but
that have no home on the site today:

1. **Tournaments** — IPL, T20 World Cup, Vitality Blast, etc. A
   competition with its own life: editions, champions, all-time
   records, evolution of the run rate.
2. **Bilateral rivalries** — India vs Australia, Ashes (T20). A team
   pair viewed across all their international meetings.

Both are **rollups of matches** and are related: a tournament is a
bag of matches grouped by event; a rivalry is a bag of matches
grouped by team-pair. This spec gives them a shared home at
`/tournaments`, with two dossier types underneath.

The page is filter-sensitive end-to-end. The FilterBar params
(`gender`, `team_type`, `tournament`, `season_from`, `season_to`)
reshape what's listed on the landing AND what's shown on every
dossier. Narrowing `tournament` on the FilterBar while on the
tournaments landing immediately drills into that tournament's
dossier. Setting `season_from = season_to` collapses any dossier to
single-edition view (and reveals the Points Table tab — see below).

## What this spec does NOT cover

- **Team-to-team head-to-head dossier** (enhancement B, polymorphic
  `/head-to-head`). Rivalry entries on the tournaments landing link
  to `/teams?team=X&tab=vs%20Opponent&vs=Y` today; when polymorphic
  H2H ships they'll re-point to `/head-to-head?team1=X&team2=Y`.
  This spec does build one endpoint (`/rivalries/summary`) that
  polymorphic H2H will reuse.
- **Tournament baselines overlay** (enhancement O) on Teams / Batting
  / Bowling / Fielding pages. Not built here, but the endpoints in
  this spec are designed so baselines drop in without reshape.

## Scope

- **New router**: `api/routers/tournaments.py`.
- **New endpoints**: landing, per-tournament summary/by-season/
  points-table/records, per-rivalry summary.
- **Reused endpoints**: existing `/batters/leaders`, `/bowlers/leaders`,
  `/fielders/leaders` (already filter-aware via `tournament` param).
- **Two small config maps** in the new router module:
  - `TOURNAMENT_CANONICAL` — merges cricsheet name variants.
  - `BILATERAL_TOP_TEAMS` — the 9-team list for the default rivalry grid.
- **Frontend**: new `/tournaments` route with landing + per-tournament
  dossier + per-rivalry dossier. Reuses existing chart components.

## Data layer

No new tables. All queries aggregate over existing data.

### Canonical tournament map

Cricsheet's `event_name` has historical drift. The Men's T20 World
Cup is split across three names and the Women's across three. A
Python `dict` in `api/routers/tournaments.py` merges them:

```python
TOURNAMENT_CANONICAL = {
    "T20 World Cup (Men)": [
        "ICC World Twenty20",       # 2007/08 – 2012/13
        "World T20",                # 2013/14 – 2015/16
        "ICC Men's T20 World Cup",  # 2021/22 – present
    ],
    "T20 World Cup (Women)": [
        "ICC Women's World Twenty20",
        "Women's World T20",
        "ICC Women's T20 World Cup",
    ],
    # Everything else passes through with its cricsheet name unchanged
    # (one entry per canonical name; single-variant tournaments are
    # absent from this dict and resolved by identity).
}
```

Helpers:

```python
def canonicalize(event_name: str) -> str:
    """Return display name; identity if not in the map."""

def variants(canonical: str) -> list[str]:
    """Return cricsheet variants for a canonical name."""
```

SQL scoping uses `variants()` to build `event_name IN (...)` clauses.

**Qualifier events stay separate.** "ICC Men's T20 World Cup
Qualifier", regional qualifiers, and sub-regional qualifiers each
keep their own cricsheet name. Different teams, different meaning.

### Series-type classification

Each canonical tournament gets tagged `series_type ∈ {icc_event,
franchise_league, domestic_league, women_franchise, bilateral_tour,
other}` for landing-page grouping. Stored in a second dict:

```python
TOURNAMENT_SERIES_TYPE = {
    "T20 World Cup (Men)":       "icc_event",
    "T20 World Cup (Women)":     "icc_event",
    "Women's Asia Cup":          "icc_event",
    "Indian Premier League":     "franchise_league",
    "Big Bash League":           "franchise_league",
    # ...
    "Vitality Blast":            "domestic_league",
    "Syed Mushtaq Ali Trophy":   "domestic_league",
    # ...
    # Bilateral tours ("England tour of West Indies", etc.) are
    # NOT listed individually as tournaments; they're resolved to
    # rivalries instead (see below).
}
```

Items not in the dict default to `other` — they show up in a misc
bucket on the landing for now; future PRs can classify more.

### Bilateral rivalries — synthesized from team pairs

Bilateral series are **not** shown as tournaments on the landing.
Cricsheet fragments a rivalry across many event_names ("India tour
of Australia" / "Australia tour of India" / NULL / …). We aggregate
by unordered team pair instead.

**Default grid = all 36 pairs among the 9 full-member men's teams:**

```python
BILATERAL_TOP_TEAMS = [
    "India", "Pakistan", "Bangladesh", "South Africa",
    "England", "Australia", "New Zealand", "Sri Lanka", "West Indies",
]
# C(9,2) = 36 pairs. Every pair has ≥ 4 IT20s in the current DB.
```

Note: the original discussion mentioned "25 rivalries"; the actual
count among the 9 teams is 36. Going with 36 — every pair has a
real match history and dropping any subset would be arbitrary.
Zimbabwe was dropped vs. the original 10 because several ZIM pairs
have ≤ 5 IT20s and clutter the grid.

**Other rivalries** — an expandable section lists:
- Pairs involving at least one team NOT in `BILATERAL_TOP_TEAMS` but
  in an international match (Afghanistan, Ireland, Netherlands,
  Scotland, USA, UAE, Nepal, Oman, Namibia, Zimbabwe, etc.).
- Threshold: show any pair with ≥ 5 matches in the filtered scope.
- Collapsed by default; click "Show other rivalries" to expand.

**Women's rivalries** — under gender=female filter, same 9-team list
applies (women's national teams match men's full-member set for the
most part). If gender=male or no gender filter, default to men's
pairs. FilterBar's gender pill handles the narrowing.

**Rivalry scope** — a rivalry aggregates ALL international T20
matches between the two teams, including those in ICC events (WC
meetings count as part of the rivalry). A FilterBar `tournament`
param narrows to "IND vs AUS within the IPL" (semantic edge: no club
overlap unless both teams are franchise-level; the filter just
applies naturally). A `series_type` split on the rivalry dossier
separates "bilateral-tour matches" from "ICC-event matches".

### Points-table reconstruction

Fully derivable from `match` + `innings` + `delivery`. No stored data.

**Eligibility**: a match contributes to a points table if it's a
league match in the tournament-season scope. League matches are:

```sql
WHERE event_name IN (:variants)
  AND season = :season
  AND (event_stage IS NULL             -- pure round-robin (IPL, etc.)
       OR event_stage IN ('Group', 'League', 'Round 1', 'Super League'))
  -- explicit knockout stages are excluded:
  -- 'Final', 'Semi Final', 'Eliminator', 'Qualifier 1', 'Qualifier 2',
  -- 'Qualifier', 'Quarter Final', '3rd Place Play-Off', etc.
```

If `event_group` is populated (e.g. T20 World Cup has groups 1, 2, A,
B), we emit **one points table per group**. If NULL (e.g. IPL's
single round-robin), one table for the whole tournament.

**Points**:
- Win (`outcome_winner = team`): **2**
- Tie (`outcome_result = 'tie'`): **1** each (super-over eliminator is
  shown separately as "super-over win" but does not change points)
- No result (`outcome_result = 'no result'`): **1** each
- Loss: **0**

**Net Run Rate**: `(runs_for / legal_balls_for) − (runs_against /
legal_balls_against)`, where:
- `runs_for` = `SUM(delivery.runs_total)` in innings where
  `innings.team = team` and `innings.super_over = 0`, across the
  eligible matches.
- `legal_balls_for` = `SUM(1) WHERE extras_wides=0 AND extras_noballs=0`
  on those same innings.
- `runs_against` / `legal_balls_against` = same over innings where
  `innings.team != team AND (m.team1 = team OR m.team2 = team)`.
- NRR is computed per-team across the season's eligible matches, not
  per-match averaged. Matches the ICC/BCCI convention.
- No-result matches are **excluded** from NRR calculation (convention).

**Output shape**: one row per team per group (or tournament-wide if
no groups), ordered by (points DESC, NRR DESC, wins DESC).

### Champion / runner-up detection

```sql
WITH final AS (
  SELECT * FROM match
  WHERE event_name IN (:variants) AND season = :season
    AND event_stage = 'Final'
)
SELECT outcome_winner AS champion,
       CASE WHEN team1 = outcome_winner THEN team2 ELSE team1 END AS runner_up,
       id AS match_id
FROM final
LIMIT 1
```

If no Final row exists (season incomplete, or tournament has no final
stage), champion is NULL. Some older tournament formats may have
Finals under different `event_stage` values; we fallback to the
latest knockout match by `dates` if `event_stage='Final'` returns
nothing AND knockout stages exist.

### Records queries

All use existing tables. Each is one SQL query:

- **Highest team total**: `SELECT MAX(team_total) FROM (SELECT
  innings_id, SUM(runs_total) total FROM delivery GROUP BY
  innings_id) …` joined to innings + match + event_name filter.
- **Lowest all-out**: same but filtered to innings where 10 wickets
  fell.
- **Largest partnership**: `SELECT MAX(partnership_runs) FROM
  partnership JOIN innings …` scoped by tournament variants.
- **Best bowling figures**: per-bowler per-match aggregate of
  wickets + runs conceded, ordered by (wickets DESC, runs ASC).
- **Biggest win by runs / wickets**: `ORDER BY outcome_by_runs DESC`
  etc. on `match`.
- **Closest win**: `MIN(outcome_by_runs) WHERE outcome_by_runs > 0`
  and `MIN(outcome_by_wickets) WHERE outcome_by_wickets = 1` (or 2).
- **Most 6s in a match**: `SELECT match_id, SUM(runs_batter=6)
  FROM delivery …`.

## API layer

New router: `api/routers/tournaments.py`. All endpoints take the
standard `FilterParams` via `Depends()`. Responses use `ORJSONResponse`
like the other routers.

### `GET /api/v1/tournaments/landing`

The sectioned home-page payload. Honours FilterBar (`gender`,
`team_type`, `tournament`, `season_from`, `season_to`).

```json
{
  "international": {
    "icc_events": [
      {"canonical": "T20 World Cup (Men)", "editions": 9, "matches": 334,
       "most_titles": {"team": "West Indies", "titles": 2},
       "latest_edition": {"season": "2024", "champion": "India"}},
      {"canonical": "T20 World Cup (Women)", "editions": 8, "matches": 180, ...},
      {"canonical": "Asia Cup", "editions": 2, "matches": 26, ...},
      ...
    ],
    "bilateral_rivalries": {
      "top": [
        {"team1": "New Zealand", "team2": "Pakistan", "matches": 49,
         "team1_wins": 19, "team2_wins": 28, "no_result": 2, "ties": 0,
         "latest_match": {"match_id": 12834, "date": "2025-11-09",
                          "winner": "Pakistan"}},
        {"team1": "England",    "team2": "West Indies", "matches": 39, ...},
        // ... 36 entries total among the 9 top teams
      ],
      "other_count": 78,       // number of pairs in the expandable section
      "other_threshold": 5     // min matches to appear
    }
  },
  "club": {
    "franchise_leagues": [
      {"canonical": "Indian Premier League", "editions": 18, "matches": 1190,
       "most_titles": {"team": "Chennai Super Kings", "titles": 5},
       "latest_edition": {"season": "2025", "champion": "Royal Challengers Bengaluru"}},
      {"canonical": "Big Bash League", "editions": 14, "matches": 662, ...},
      ...
    ],
    "domestic_leagues": [
      {"canonical": "Vitality Blast", "editions": 22, "matches": 1455, ...},
      ...
    ],
    "women_franchise": [
      {"canonical": "Women's Big Bash League", ...},
      {"canonical": "Women's Premier League", ...},
      {"canonical": "The Hundred Women's Competition", ...},
      ...
    ],
    "other": [
      // tournaments not yet classified (series_type = 'other')
      {"canonical": "Kwibuka Women's Twenty20 Tournament", "matches": 82, ...},
      ...
    ]
  }
}
```

### `GET /api/v1/tournaments/other-rivalries`

Lazy-loaded payload for the "Show other rivalries" expander. Honours
the same FilterBar scope.

```json
{
  "rivalries": [
    {"team1": "Afghanistan", "team2": "Ireland", "matches": 28, ...},
    ...
  ],
  "threshold": 5
}
```

### `GET /api/v1/tournaments/summary?tournament=X`

Headline numbers for one tournament. Filter-sensitive: narrowing
`season_from/to` or `gender` reshapes everything.

```json
{
  "canonical": "Indian Premier League",
  "editions": 18,
  "matches": 1190,
  "total_runs": 350120,
  "total_wickets": 15680,
  "total_sixes": 12740,
  "run_rate": 8.48,
  "boundary_pct": 17.6,
  "dot_pct": 38.1,
  "most_titles": {"team": "Chennai Super Kings", "titles": 5},
  "champions_by_season": [
    {"season": "2024", "champion": "Kolkata Knight Riders", "match_id": 12834},
    {"season": "2023", "champion": "Chennai Super Kings", "match_id": 12103},
    ...
  ],
  "top_scorer_alltime":   {"person_id": "...", "name": "V Kohli", "runs": 8017},
  "top_wicket_taker_alltime": {"person_id": "...", "name": "YS Chahal", "wickets": 215},
  "highest_team_total": {"team": "Sunrisers Hyderabad", "total": 287,
                          "match_id": 12640, "opponent": "RCB", "date": "2024-03-25"},
  "largest_partnership": {"runs": 229, "match_id": 8391, ...},
  "best_bowling":         {"person_id": "...", "name": "AB Agarkar", "figures": "6/14",
                           "match_id": 3421, "date": "2009-05-17"}
}
```

Reusable for enhancement O: call with the team's primary tournament
and overlay the numbers as a baseline on the Teams tab.

### `GET /api/v1/tournaments/by-season?tournament=X`

Per-edition rollup. Same filter params (tournament, gender, etc.).
Excludes seasons outside `season_from`/`season_to` when set.

```json
{
  "seasons": [
    {"season": "2024", "matches": 74,
     "champion": "Kolkata Knight Riders", "runner_up": "Sunrisers Hyderabad",
     "final_match_id": 12834,
     "run_rate": 8.81, "boundary_pct": 18.4, "total_sixes": 1214,
     "top_scorer":      {"person_id": "...", "name": "V Kohli",       "runs": 741},
     "top_wicket_taker":{"person_id": "...", "name": "Harshal Patel", "wickets": 24}},
    ...
  ]
}
```

### `GET /api/v1/tournaments/points-table?tournament=X&season=Y`

Only returns a meaningful response when `season` is a single value.
If `season_from != season_to`, return `{"tables": [], "reason":
"multi_season"}` — frontend hides the tab in that case.

```json
{
  "canonical": "ICC Men's T20 World Cup",
  "season": "2024",
  "tables": [
    {"group": "1",
     "rows": [
       {"team": "India",       "played": 4, "wins": 4, "losses": 0, "ties": 0, "nr": 0,
        "points": 8, "runs_for": 634, "balls_for": 458, "runs_against": 479,
        "balls_against": 458, "nrr": 0.338,
        "advance": "semi_final"},
       {"team": "Australia",   "played": 4, "wins": 3, "losses": 1, ..., "nrr": 1.875,
        "advance": null},
       ...
     ]},
    {"group": "2", "rows": [...]}
  ]
}
```

For IPL-shape tournaments (no groups), one table entry with
`"group": null`.

`advance` is `"semi_final"`, `"final"`, `"qualifier_1"`, etc. —
derived by looking up the team's next knockout-stage appearance in
the same season. NULL if they didn't advance.

### `GET /api/v1/tournaments/records?tournament=X`

```json
{
  "highest_team_totals": [
    {"runs": 287, "team": "SRH", "opponent": "RCB", "match_id": 12640, "date": "2024-03-25"},
    {"runs": 277, ...}, ... up to 5
  ],
  "lowest_all_out_totals": [...],
  "biggest_wins_by_runs": [
    {"winner": "RCB", "loser": "PBKS", "margin": 146, "match_id": 9812, "date": "2017-04-24"},
    ...
  ],
  "biggest_wins_by_wickets": [...],
  "largest_partnerships": [
    {"runs": 229, "batter1": {"person_id": "...", "name": "CH Gayle"},
     "batter2": {"person_id": "...", "name": "V Kohli"},
     "match_id": 8391, "date": "2016-05-14", "teams": "RCB v PWI"},
    ...
  ],
  "best_bowling_figures": [
    {"person_id": "...", "name": "AB Agarkar", "wickets": 6, "runs": 14,
     "balls": 24, "match_id": 3421, "date": "2009-05-17"},
    ...
  ],
  "most_sixes_in_a_match": [
    {"match_id": 12834, "sixes": 39, "teams": "RCB v CSK", "date": "2024-05-18"},
    ...
  ]
}
```

Each sub-array capped at 5 entries.

### `GET /api/v1/rivalries/summary?team1=X&team2=Y`

Synthesized bilateral rivalry dossier. Unordered (`team1`/`team2` are
normalized alphabetically internally; response uses whatever order
the query used for display).

```json
{
  "team1": "India",
  "team2": "Australia",
  "matches": 37,
  "team1_wins": 18,
  "team2_wins": 17,
  "ties": 1,
  "no_result": 1,
  "last_match": {"match_id": 12834, "date": "2025-11-09",
                 "winner": "Pakistan", "by": "5 wickets"},
  "by_series_type": {
    "bilateral_tour": 30,
    "icc_event":       6,
    "other":           1
  },
  "top_scorer_in_rivalry":      {"person_id": "...", "name": "V Kohli",   "runs": 820},
  "top_wicket_taker_in_rivalry":{"person_id": "...", "name": "A Zampa",   "wickets": 22},
  "highest_individual": {"person_id": "...", "name": "G Maxwell", "runs": 113,
                          "match_id": 12210, "date": "2023-11-14"},
  "largest_partnership":{"runs": 154, ...},
  "closest_match":      {"margin": "1 run", "match_id": 8214, ...},
  "biggest_win":        {"winner": "Australia", "margin": "66 runs", "match_id": 4821, ...}
}
```

Polymorphic `/head-to-head` will reuse this endpoint.

## URL / routing scheme

- `/tournaments` — landing (default view).
- `/tournaments?tournament=Indian Premier League` — per-tournament
  dossier (all-time if no season filter).
- `/tournaments?tournament=Indian Premier League&season_from=2024&season_to=2024`
  — single-edition view. Points Table tab becomes visible.
- `/tournaments?rivalry=India,Australia` — rivalry dossier
  (team names comma-separated in `rivalry` param, normalized
  alphabetically server-side).
- FilterBar's `tournament` pill on other pages navigates here when
  clicked, passing current filters.

Two route params only — `tournament` and `rivalry` are mutually
exclusive. When both are set, `tournament` wins (narrow the rivalry
by picking a tournament instead — done via FilterBar).

**Tab param** inside the dossier:
`/tournaments?tournament=X&tab=overview|editions|points|batters|bowlers|fielders|records`
default `overview`. Points tab hidden when multi-season.

## Frontend layer

New page `frontend/src/pages/Tournaments.tsx`. Reuses existing
`FilterBar`, `DataTable`, `BarChart`, `LineChart`, chart palette.

### Landing layout

```
┌──────────────────────────────────────────────────────────────────┐
│  [FilterBar]                                                     │
├────────────────────────────────┬─────────────────────────────────┤
│  INTERNATIONAL                 │  CLUB                           │
│                                │                                 │
│  ICC Events                    │  Franchise Leagues              │
│  ┌──────────────────────────┐  │  ┌────────────────────────────┐ │
│  │ T20 World Cup (Men)      │  │  │ Indian Premier League      │ │
│  │ 9 editions · 334 matches │  │  │ 18 editions · 1190 matches │ │
│  │ Most titles: WI (2)      │  │  │ Most titles: CSK (5)       │ │
│  │ Latest: 2024 – India     │  │  │ Latest: 2025 – RCB         │ │
│  └──────────────────────────┘  │  └────────────────────────────┘ │
│  [Women's WC] [Asia Cup] ...   │  [BBL] [PSL] [CPL] ...          │
│                                │                                 │
│  Bilateral Rivalries           │  Domestic Leagues               │
│  ┌──────────────────────────┐  │  ┌────────────────────────────┐ │
│  │ NZ vs PAK · 49 matches   │  │  │ Vitality Blast · 1455 m    │ │
│  │ 28-19-2                  │  │  │ Syed Mushtaq Ali · 695 m   │ │
│  └──────────────────────────┘  │  └────────────────────────────┘ │
│  ... (36 tiles total)          │                                 │
│  [▸ Show other rivalries]      │  Women's Franchise              │
│    (78 more when expanded)     │  [WBBL] [WPL] [Hundred Women]…  │
│                                │                                 │
│                                │  Other                          │
│                                │  [Kwibuka T20] ...              │
└────────────────────────────────┴─────────────────────────────────┘
```

Each tile is a link. Clicking a tournament tile navigates to
`/tournaments?tournament=X` carrying current FilterBar state.
Clicking a rivalry tile navigates to `/tournaments?rivalry=A,B`.

Mobile: two columns collapse to one. International first, then Club.

**FilterBar interaction on landing**:
- `season_from/to` narrows matches counted everywhere.
- `gender=female` shows only women's tournaments + women's rivalries.
- `team_type=club` hides the international column entirely; same for
  `international` hiding club.
- `tournament=X` set on FilterBar → auto-navigate to that dossier
  (avoids ambiguous "I filtered to IPL but I'm still on the
  landing" state).

### Per-tournament dossier

Tab bar underneath the header:
`Overview | Editions | Points Table | Batters | Bowlers | Fielders | Records`

Points Table tab is **hidden unless single-season in scope**
(`season_from === season_to` and both set). This is the cleanest
signal that the user wants one edition.

**Overview tab**:
```
[Headline StatCards: Matches · Editions · Total Runs · Run Rate · 6s]
[StatCards: Most titles · Highest team total · Largest partnership · Best bowling]
<LineChart> Run rate by season
<LineChart> Boundary % by season
[Champions list — compact table]
```

**Editions tab**:
```
DataTable columns:
  Season | Matches | Champion | Runner-up | Top Scorer | Top Wicket-Taker | Final
```
Clicking a season row sets `season_from=season_to=that` on FilterBar
(narrows the whole page).

**Points Table tab** (single-season only):
```
One <DataTable> per group (or single table for league-shape):
  Team | P | W | L | T | NR | Pts | NRR | Advance
```
`Advance` column rendered as a small pill: "→ Semi Final", "→ Final",
"→ Qualifier 1". NULL = blank.

**Batters / Bowlers / Fielders tabs**:
Reuse existing leader views. Each tab renders three mini-tables:
- by runs / by average / by strike rate (batters)
- by wickets / by economy / by strike rate (bowlers)
- by dismissals / by catches / by keeper dismissals (fielders)

All hit existing `/{batters,bowlers,fielders}/leaders?tournament=X`
endpoints.

**Records tab**:
```
[Highest team totals — top 5]
[Lowest all-out totals — top 5]
[Biggest wins by runs / by wickets — top 5 each]
[Largest partnerships — top 5]
[Best bowling figures — top 5]
[Most sixes in a match — top 5]
```
Each entry links to its match scorecard / player page.

### Per-rivalry dossier

Simpler than tournament dossier. No editions/points-table (there's no
edition concept for bilaterals).

```
Header: [Team1 flag/logo] vs [Team2 flag/logo]
         [StatCards: Matches · Team1 wins · Team2 wins · NR · Ties]
[StatCards: Top scorer · Top wicket-taker · Highest individual · Largest partnership]
<BarChart> Wins by series-type (bilateral vs ICC event vs other)
<LineChart> Meetings per year (count) with wins tinted
[Match list — last 20 meetings, oldest at bottom]
  Date · Tournament/Series · Venue · Result
```

When polymorphic H2H ships (enhancement B), this page REDIRECTS to
`/head-to-head?team1=X&team2=Y` (same endpoint, better home).

## Filter semantics — complete matrix

| FilterBar setting        | Landing                                | Tournament dossier              | Rivalry dossier                |
|--------------------------|----------------------------------------|---------------------------------|--------------------------------|
| `gender=male`            | Shows men's tournaments + men's pairs  | Filters events to male gender   | Scopes to men's IT20s          |
| `gender=female`          | Shows women's + women's pairs          | Filters events to female gender | Scopes to women's IT20s        |
| `team_type=international`| Hides club column                      | (no effect if already int'l)    | (no effect — always int'l)     |
| `team_type=club`         | Hides international column             | (no effect if already club)     | Rivalry column hidden entirely |
| `tournament=X`           | Auto-navigates to X's dossier          | Redundant — silently stripped   | Narrows rivalry to that tournament |
| `season_from/to`         | Narrows "matches" counts per tile      | Narrows all stats + editions    | Narrows rivalry to seasons     |
| `season_from = season_to`| Same as above                          | Reveals Points Table tab        | Narrows to single season       |

## Baseline-readiness (for enhancement O, later)

The endpoints in this spec are designed so adding baseline overlays on
Teams / Batting / Bowling / Fielding tabs is a frontend-only change.

**Pattern for Teams tab**: when a team is viewed with `tournament=X`
set, fetch `/tournaments/summary?tournament=X` in parallel with the
existing team queries. Overlay the tournament's run rate, boundary %,
dot % as translucent lines / backgrounds on the team's charts. The
shape of the summary response matches the team summary 1:1 in those
columns, so the overlay component is a straight comparison.

**Pattern for batter page**: baseline = `/tournaments/summary.
top_scorer_alltime` and season aggregates from `/tournaments/by-season`.
A batter's season score compared to the season's average.

**No DB schema change** required for baselines. If performance
demands it later, a `tournament_season_stats` summary table can be
added (Option 2 from next-session-ideas.md) — but that's an
optimization for later.

## Implementation order

1. **Router scaffold + canonical map** — `api/routers/tournaments.py`
   with `TOURNAMENT_CANONICAL`, `TOURNAMENT_SERIES_TYPE`,
   `BILATERAL_TOP_TEAMS`, and helper functions.
2. **`/tournaments/landing`** — sectioned payload. Verify all rows
   appear correctly; confirm variant-merging produces one row for
   T20 World Cup (Men) with 9 editions.
3. **`/tournaments/summary`** — per-tournament headline numbers.
4. **`/tournaments/by-season`** — per-edition rollup.
5. **`/tournaments/points-table`** — league-stage reconstruction.
   Validate against IPL 2024 (already verified in pre-flight) and
   T20 WC 2022 (group stage).
6. **`/tournaments/records`** — records queries.
7. **`/tournaments/other-rivalries`** — expandable rivalry list.
8. **`/rivalries/summary`** — bilateral rivalry dossier endpoint.
9. **Frontend types** + API client additions.
10. **Landing page UI** — the two-column layout.
11. **Per-tournament dossier UI** — all 7 tabs.
12. **Per-rivalry dossier UI** — simpler, single-page.
13. **Nav integration** — add "Tournaments" to the top nav.
14. **Docs pass** — `docs/api.md`, `internal_docs/codebase-tour.md`, CLAUDE.md
    "Landing pages" section, `internal_docs/enhancements-roadmap.md` (mark M
    done).
15. **Deploy + verify in browser** per CLAUDE.md UI-verification rule.

## Test cases

### Canonicalization
- `canonicalize("ICC World Twenty20")` → `"T20 World Cup (Men)"`.
- `canonicalize("Indian Premier League")` → `"Indian Premier League"`.
- `variants("T20 World Cup (Men)")` → 3-element list.

### Landing payload
- `/tournaments/landing` with no filters returns both columns populated.
- With `gender=female`: no `T20 World Cup (Men)`, no men's rivalries
  in `bilateral_rivalries.top`.
- With `team_type=club`: `international` key absent or empty.
- With `season_from=2023&season_to=2024`: all "matches" counts drop;
  `editions` counts drop for tournaments that didn't run both years.

### Rivalries
- `bilateral_rivalries.top` has exactly 36 entries under default
  (men's, all filters off).
- `New Zealand vs Pakistan` is the top entry (49 matches).
- `other_count` > 50 under no filters.

### Points table
- IPL 2024 reconstruction exactly matches the committed snapshot in
  `tests/fixtures/ipl_2024_standings.json` (to create from the known
  final table).
- T20 WC 2022 produces 2 group tables (groups 1, 2) + 2 super-12
  group tables (A, B). Team ordering within each matches published.
- NRR sign is correct: a team that won big has positive NRR.
- No result / tie matches contribute 1 pt each, not 2.

### Per-tournament dossier
- `/tournaments/summary?tournament=Indian Premier League` returns
  `editions=18`, matches≈1190, `most_titles.team="Chennai Super Kings"`
  with `titles=5`.
- With `season_from=2024&season_to=2024`, same endpoint returns only
  2024 aggregates, matches≈74, editions=1.
- Variant-merged request: `/tournaments/summary?tournament=T20 World
  Cup (Men)` returns `editions=9`, matches sums across 3 event_names.

### Rivalry dossier
- `/rivalries/summary?team1=India&team2=Australia` returns matches
  count matching raw query (`COUNT(*) FROM match WHERE {team1,team2}
  = {IND,AUS} AND international AND T20`).
- Swapped params: `team1=Australia&team2=India` returns same payload
  (order-normalized internally).
- `by_series_type` sums equal `matches`.

### Frontend
- Landing: all 36 rivalry tiles render; "Show other rivalries"
  toggles a second grid.
- Tournament dossier: Points Table tab appears only when single
  season is in scope.
- Setting `tournament=X` on FilterBar while on landing navigates to
  `/tournaments?tournament=X`.
- All FilterBar params persist across tab switches within a dossier.
- All record-list entries link to valid scorecard / player pages.

## Out of scope (v1)

- **Team-to-team H2H polymorphic route** — separate enhancement B.
  Rivalry dossier from this spec will be folded into it then.
- **Tournament baseline overlays** on Teams / Batting / Bowling /
  Fielding — enhancement O, uses endpoints from this spec.
- **Precomputed tournament summary tables** — optimization for later
  if query latency demands it.
- **Bilateral series as their own "tournament" entries** (e.g.,
  "India tour of Australia 2024") — we aggregate by team-pair
  instead. Individual tour metadata is still reachable via the
  match list with `event_name=X` filter.
- **Group-stage "super 6" / "super 10" advanced structures** — we
  label `event_stage` values verbatim in the `advance` column
  without trying to normalize them.
- **Season incomplete handling** — if a tournament season is
  mid-progress (no Final yet), champion is NULL; frontend shows
  "(in progress)".
- **Historical canonicalization drift** — if cricsheet renames a
  tournament tomorrow, we update `TOURNAMENT_CANONICAL` in code.
  No auto-detection.

## Estimated effort

- Router scaffold + canonicalization (step 1): ~1 hour
- Landing endpoint (2): ~2 hours
- Summary + by-season endpoints (3–4): ~2 hours
- Points table endpoint (5): ~3 hours (group-stage handling + NRR)
- Records endpoint (6): ~2 hours
- Other-rivalries + rivalry-summary (7–8): ~2 hours
- Frontend types + API client (9): ~1 hour
- Landing page UI (10): ~3 hours
- Per-tournament dossier (11, 7 tabs): ~5 hours
- Per-rivalry dossier (12): ~2 hours
- Nav + docs + deploy (13–15): ~1.5 hours

Total: ~24–25 hours. Split across sessions as needed; landing +
per-tournament dossier is the MVP slice and ships independently.

## Open questions to resolve during build

1. **Series-type classification coverage** — there are ~200 cricsheet
   event_names. Classifying each into the series_type enum is manual.
   First pass covers the top 40 by match count (≥ 80% of matches);
   everything else defaults to `other` and can be classified in
   follow-ups.
2. **Tournament tile click with `tournament` already set on FilterBar**
   — auto-nav or silent strip? Spec says auto-nav; double-check
   that feels right when testing.
3. **Rivalry tile "other_threshold"** — currently 5 matches. Verify
   the expanded list is manageable; raise to 10 if it balloons.
4. **Champions-by-season with old tournaments where `event_stage`
   isn't 'Final'** — may need per-tournament overrides. Confirm by
   checking Vitality Blast + Syed Mushtaq Ali structure before
   shipping.
