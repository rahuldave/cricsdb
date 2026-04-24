# Spec: Teams Compare — Average-Team Column, Phase Bands, Season-by-Season

Status: build-ready.
Depends on: nothing new in the data layer for the user-visible feature.
Parallel workstream (not consumed by this spec): `player_scope_stats`
table and its populate script — landed alongside this spec under Path A
so the next spec (cross-app comparisons, `outlook-comparisons.md`) starts
with schema in place.

## Overview

The Teams > Compare tab today places up to three real teams side-by-side
across five disciplines (Results, Batting, Bowling, Fielding,
Partnerships). The comparison is valuable but answers a narrow question:
"how does Team A compare to Team B?" — not "how does Team A compare to
the field?"

This spec adds an **Average-Team column** (the pool-weighted
league-scope baseline, filtered identically to the rest of the compare
grid) and extends the existing summary rows with two deeper lenses:

1. **Phase bands** — PP / Middle / Death sub-rows under Batting and
   Bowling so deltas at specific phases become visible.
2. **Season-by-season trajectory** — compact line charts below the
   grid, one per discipline-phase, team lines + an average-team line,
   so "is our powerplay worse this year than last year vs the field"
   is a single glance.

The core computation is cheap: every existing Compare endpoint is
already a scope-filtered aggregation with `WHERE team = :team` on top.
Strip the team clause and the same SQL computes the league-scope
average. No schema changes for the user-visible feature; existing
covering indexes (`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`)
carry it.

## Scope

**In scope:**

- Five new API endpoints under `/api/v1/scope/averages/*` — mirror the
  five team-compare endpoints but with no team filter.
- Extended response contract on compare endpoints: each metric carries
  `{value, scope_avg, delta_pct, direction, sample_size}` — backend
  computes the normalization once, every UI consumer reads the same
  fields. Within Spec 1 the Teams Compare UI renders only `value` and
  `scope_avg`; the other three fields are shipped in the API now so
  future surfaces (Spec 2) consume them without an endpoint migration.
- "Add league average" slot in `AddTeamComparePicker`.
- `FlagBadge` null-render for the average slot.
- Phase-band expansion rows (PP / Middle / Death) for Batting and
  Bowling, backed by existing `/teams/{team}/batting/by-phase` and
  `/bowling/by-phase` endpoints + two new scope-avg siblings.
- Per-wicket expansion for Partnerships (1st through 10th wicket),
  backed by existing `/teams/{team}/partnerships/by-wicket` + a new
  scope-avg sibling.
- Season-by-season line charts below the grid, driven by existing
  `by-season` endpoints + new scope-avg siblings.
- One new endpoint: `/teams/{team}/partnerships/by-season` (does not
  exist today) + its scope-avg sibling.
- Small-sample suppression via returned `sample_size` per cell.
- `player_scope_stats` table + populate script (see "Parallel
  workstream" below) — **not consumed by any endpoint in this spec**.

**Not in scope:**

- Over-by-over (granularity deferred — phase gives 90% of the insight
  at 10% of the visual weight).
- Ratio-mode heatmap view (parked for v2 of this feature).
- Consuming the `player_scope_stats` table from any endpoint (that is
  Spec 2).
- Team summary tables (`team_scope_stats` etc.) — existing indexes
  handle the computational load.
- Cross-scope baselining (e.g. "IPL 2024 vs all-time IPL avg") —
  belongs in the tournament dossier, tracked in `outlook-comparisons.md`.

## UX

### The average-team column

A fourth slot on `TeamCompareGrid`, added via a new button in
`AddTeamComparePicker`: **"+ Add league average"**. Once added, it
renders as a normal compare column with:

- Label: scope-computed — e.g. "IPL 2024 avg", "T20 Men's avg", with a
  tooltip explaining exactly which scope is aggregated (respects every
  FilterBar field the comparison is currently using).
- `FlagBadge`: null-render (same treatment as franchise teams).
- Identity row (captain, home ground, etc.): blank / em-dash — the
  average has no identity.
- All stat rows populated from the scope-average endpoints.

The average slot is **subject to the same auto-narrow as team slots**:
when a primary team is set, gender + team_type are locked from the
primary (existing behaviour). The average inherits that lock — no
cross-gender or cross-team_type pollution of the baseline. No code
change needed here; the FilterBar constraints already gate the scope
that flows into the endpoint calls.

Only one average column allowed (hiding the button once added).

### Phase-band expansion

Under the Batting row group, indented sub-rows:

```
Batting
  Overall   RR         7.94  ·  8.52   ·  8.11
  PP        RR         8.12  ·  8.74   ·  8.30     bdry%  dot%
  Middle    RR         7.62  ·  7.88   ·  7.80     ...
  Death     RR         9.88  ·  10.12  ·  9.95     ...
```

Same pattern under Bowling (econ, SR, wickets/over, dot%).

Default expanded when at least one team is in Compare. A single "Show
phases" toggle collapses all three phase groups together — users rarely
want phase bands on one discipline but not another.

Phase ordering fixed: **PP → Middle → Death** everywhere. When season
trajectory charts arrive (below), they reuse the same vertical order.

### Per-wicket partnership expansion

Under Partnerships, 10 indented sub-rows (1st–10th wicket) with columns
for:

- Runs / partnership (avg)
- Partnership strike rate
- Frequency (% of innings where this wicket partnership forms)
- Count of 50+ stands in scope
- Best partnership (per team: with pair identity; for average column:
  the highest stand at that wicket anywhere in scope, with pair
  identity — the league record has a known holder)

Small-sample suppression kicks in hardest here (9th/10th wicket
partnerships are rare); see "Direction + sample size" below.

### Season-by-season trajectory

Below the grid, a compact small-multiples strip of line charts:

```
Batting RR by phase              Bowling econ by phase
  [ PP ]  [ Mid ]  [ Death ]       [ PP ]  [ Mid ]  [ Death ]
```

Each panel: X = season, Y = the metric, one line per team in Compare +
one line for the average. Average line rendered in a neutral colour
(e.g. grey), teams in their existing distinct colours, same legend as
the summary grid so there's no re-keying.

Filter interaction: the strip respects `season_from` / `season_to`. If
a single-season filter is in scope, the strip collapses to single points
and is hidden (no trajectory to draw).

### Delta column + direction metadata

Shipped in the API response (see "API layer"), **not rendered in the
Teams Compare UI in Spec 1**. The contract is in place so Spec-2
surfaces consume the same fields without an endpoint migration.

Rationale for not rendering in Spec 1: raw side-by-side columns are the
clearest UX for this feature; ratio-mode is a v2 heatmap lens whose
design we haven't settled. But the data is free to compute and ship, and
not having it in the API now means every future consumer (player
compare, leaderboard Δ columns, H2H baseline) has to either re-derive
it or we migrate the endpoint later. Easier to fix the contract once.

### Small-sample suppression

Each cell's `sample_size` drives a greying rule in the UI once it
renders deltas (v2). For Spec 1 the rule only applies to the Average
column's partnership-by-wicket rows: if fewer than 30 partnerships have
formed at that wicket in scope, render the Average cell as `—` with a
tooltip ("insufficient data at this wicket position for the selected
scope"). Teams cells never suppress — the user asked about *this* team,
so show what we have.

## Data layer

### No new consumption tables

All five compare endpoints today aggregate over `delivery`, `wicket`,
`fielding_credit`, `keeper_assignment`, and `partnership`. The
scope-average siblings aggregate over the same tables with the team
clause dropped. Existing covering indexes handle the scan cost.

Rough envelope (verified by delivery counts):

- "Average across IPL 2024" = ~18K delivery rows → sub-100ms.
- "Average across all T20Is men's 2024" = ~72K rows → sub-200ms.
- Season-by-season trajectory for a tournament × 15 seasons = ~200K
  rows grouped → sub-500ms.
- Full-scope (no filters) = 2.95M rows grouped → under ~1s with the
  covering indexes, hit rarely in practice.

If we ever see scope-avg response times cross ~800ms on prod, the
natural materialization is `team_scope_phase_stats(team, scope_key,
phase, innings_type, runs, legal_balls, dots, fours, sixes, wickets)`
— ~20K rows post-populate. **Not building it in this spec.** The
covering indexes earn their keep; add the summary table only when
measured perf demands it.

### Parallel workstream: `player_scope_stats` table

Built during the same calendar window as this spec under Path A, **not
consumed by any endpoint here**. The table exists so that Spec 2
(cross-app comparisons — especially position-matched player compare)
starts from a hot schema rather than a cold design.

Schema:

```
player_scope_stats
  person_id               VARCHAR FK → person
  scope_key               TEXT      (stable hash of tournament || season || gender || team_type)
  tournament              TEXT
  season                  INTEGER
  gender                  TEXT
  team_type               TEXT
  matches                 INTEGER   (distinct matches in XI)
  -- batting
  innings_batted          INTEGER
  runs                    INTEGER
  legal_balls             INTEGER
  dots                    INTEGER
  fours                   INTEGER
  sixes                   INTEGER
  dismissals              INTEGER
  avg_batting_position    REAL      (SUM(position × innings_at_position) / innings_batted)
  innings_by_position_json TEXT     (JSON array [0, n_pos1, n_pos2, ...] — length 12)
  -- bowling
  balls_bowled            INTEGER
  runs_conceded           INTEGER
  wickets                 INTEGER
  bowling_dots            INTEGER
  boundaries_conceded     INTEGER
  powerplay_overs         REAL
  middle_overs            REAL
  death_overs             REAL
  -- fielding
  catches                 INTEGER
  runouts                 INTEGER
  stumpings               INTEGER
  catches_as_keeper       INTEGER
  matches_as_keeper       INTEGER
  PRIMARY KEY (person_id, scope_key)
```

**Populate script**: `scripts/populate_player_scope_stats.py` with
`populate_full()` (rebuilt from scratch on import) and
`populate_incremental(new_match_ids)` (upserts the affected
(person, scope_key) rows only — typically 22 rows per new match: XI × 2
teams × 1 scope).

Auto-called from `import_data.py` (full rebuild) and `update_recent.py`
(incremental) — same pattern as `fielding_credit`, `keeper_assignment`,
`partnership`. Incremental cost per match is dozens of upserts,
negligible against existing `update_recent.py` budget.

**Indexes on the table**:

- Primary key `(person_id, scope_key)` — point lookups.
- `(scope_key, avg_batting_position)` — "all batters in this scope at
  position ~3" (Spec 2).
- `(scope_key)` — "all players in this scope" (Spec 2 baselines).

Explicitly: no endpoint in Spec 1 queries this table. A regression
test confirms the table exists, is populated, and matches hand-rolled
aggregations for a sample scope — nothing more.

## API layer

### New endpoint family: `/api/v1/scope/averages/*`

Mirrors the five team-compare endpoints:

- `GET /scope/averages/summary` — results/toss-style summary, scope-avg
- `GET /scope/averages/batting/summary`
- `GET /scope/averages/bowling/summary`
- `GET /scope/averages/fielding/summary`
- `GET /scope/averages/partnerships/summary`

Plus deep-lens siblings:

- `GET /scope/averages/batting/by-phase` — mirrors
  `/teams/{team}/batting/by-phase`
- `GET /scope/averages/bowling/by-phase` — mirrors
  `/teams/{team}/bowling/by-phase`
- `GET /scope/averages/partnerships/by-wicket` — mirrors
  `/teams/{team}/partnerships/by-wicket`
- `GET /scope/averages/batting/by-season`
- `GET /scope/averages/bowling/by-season`
- `GET /scope/averages/fielding/by-season`
- `GET /scope/averages/partnerships/by-season` *(new — sibling
  `/teams/{team}/partnerships/by-season` also to be added here since it
  doesn't exist)*

All take `FilterBarParams` (+ optional `AuxParams.series_type`) via
`Depends` — identical filter surface as their `/teams/{team}/*`
siblings.

Implementation: the existing team endpoints' SQL helpers
(`_team_innings_clause`, `_partnership_filter`) are refactored to
accept an optional `team: str | None` parameter. When `team=None`, the
team filter is dropped; all other filter injection remains identical.
This keeps the SQL in one place and guarantees the two code paths
agree.

### Response contract per metric

Every metric returned by both `/teams/{team}/*` and
`/scope/averages/*` carries:

```json
{
  "value":       8.52,
  "scope_avg":   7.94,
  "delta_pct":   7.3,
  "direction":   "higher_better",
  "sample_size": 3412
}
```

- `value` — the entity's raw value (for team endpoints). For
  `/scope/averages/*`, `value` equals `scope_avg` (the baseline is the
  value).
- `scope_avg` — the league-scope average in the same scope. Computed
  server-side alongside `value` via a single SQL that aggregates both
  (pooled) and (entity-filtered) in one pass where possible; otherwise
  a second query.
- `delta_pct` — `(value - scope_avg) / scope_avg × 100`, signed. For
  scope-avg endpoints, `delta_pct = 0`.
- `direction` — `higher_better` or `lower_better`. Per-metric constant,
  sourced from a single `METRIC_DIRECTIONS` map in
  `api/metrics_metadata.py` (new module).
- `sample_size` — the denominator that makes this cell defensible
  (legal balls for batting rates, balls bowled for bowling rates,
  partnerships for partnership stats, etc.).

### `METRIC_DIRECTIONS` map

Single source of truth in `api/metrics_metadata.py`:

```python
METRIC_DIRECTIONS = {
    # batting
    "batting_rr":          "higher_better",
    "batting_sr":          "higher_better",
    "boundary_pct":        "higher_better",
    "dot_pct_batting":     "lower_better",
    "batting_avg":         "higher_better",
    # bowling
    "bowling_econ":        "lower_better",
    "bowling_sr":          "lower_better",
    "bowling_avg":         "lower_better",
    "dot_pct_bowling":     "higher_better",
    "boundaries_conceded_pct": "lower_better",
    "wickets_per_over":    "higher_better",
    # fielding
    "catches_per_match":   "higher_better",
    "runouts_per_match":   "higher_better",
    "drops_per_match":     "lower_better",
    # partnerships
    "runs_per_partnership":  "higher_better",
    "partnership_sr":        "higher_better",
    "stands_50plus":         "higher_better",
    "partnership_frequency": "higher_better",
}
```

UIs read this map via the API response's `direction` field; no UI
re-enumerates.

### Scope-phrase consistency

Scope averages respect `ScopeContext` + `series_type` exactly as the
team endpoints do. When a user on `/teams?team=MI` with
`tournament=IPL` and `series_type=bilateral_only` clicks "Add league
average", the average is scoped to bilateral-only IPL matches — same
clause stack. The one-line scope strip above the grid already
communicates this; no new strip needed.

## Frontend

### `TeamCompareGrid` (`frontend/src/components/teams/TeamCompareGrid.tsx`)

Today: fixed `t0/t1/t2` team slots, three parallel `useFetch` calls to
`getTeamProfile`.

Changes:

- Introduce a fourth optional slot: `avgSlot: boolean`. When true, a
  parallel `getScopeAverageProfile` call is fired alongside the team
  fetches.
- `getScopeAverageProfile` (new in `frontend/src/api.ts`) — same
  parallel-5 composer pattern as `getTeamProfile`, but hits
  `/scope/averages/*`.
- Render order: team columns left-to-right, average column rightmost.
- Phase-band expansion: new `<PhaseBandsRow>` sub-component rendered
  beneath the Batting / Bowling summary rows, iterating PP / Middle /
  Death.
- Partnership per-wicket expansion: new `<PartnershipByWicketRows>`
  sub-component rendered beneath the Partnerships summary rows,
  iterating wickets 1-10.
- Season-by-season strip: new `<SeasonTrajectoryStrip>` sibling
  rendered below the grid. Internally six small `<LineChart>`
  instances (3 phases × Bat/Bowl) + optional Partnerships-by-wicket
  strip.

### `AddTeamComparePicker` (`frontend/src/components/teams/AddTeamComparePicker.tsx`)

Add a secondary button labeled **"+ Add league average"** next to the
existing team search:

- Enabled iff the average slot isn't already filled.
- Clicking sets `avg_slot=1` in the URL (so the compare state is
  shareable via URL — same principle as the rest of the compare
  picker).
- Disabled (with tooltip) when the primary team isn't set — the
  auto-narrow contract requires a primary team to lock scope.

### URL state

One new search param: `avg_slot=1`. Picked up by `TeamCompareGrid` via
`useUrlParam`. Default off (backwards-compatible with every existing
compare URL).

### Small-sample suppression UI

For Spec 1, only on Partnership-by-wicket rows in the Average column:
when `sample_size < 30`, render `—` with `title` tooltip. Future
consumers (delta column, ratio heatmap) extend this rule to more cells
when they land.

## Tests

### Regression

New file: `tests/regression/scope-averages/urls.txt`.

Every new `/scope/averages/*` endpoint gets 3-5 representative URL
entries covering: unfiltered, tournament-scoped, season-scoped, and
mixed-filter. All tagged `NEW` initially (the endpoints don't exist in
HEAD). After landing, they become `REG`.

Additions to `tests/regression/team-compare/urls.txt`:

- The five existing `/teams/{team}/*` compare endpoints with new
  response shape (raw + scope_avg + delta_pct + direction +
  sample_size) — flipped `REG → NEW` in a **separate, earlier commit**
  per the "regression harness — flip REG→NEW BEFORE shape change"
  convention. After landing, flipped back to `REG` once the new shape
  is proven stable.

### Integration (browser-agent)

New file: `tests/integration/team-compare-average.sh` exercising:

1. Load `/teams?team=MI&tab=Compare&compare=CSK&tournament=IPL`.
2. Verify the grid renders (MI, CSK columns).
3. Click "+ Add league average".
4. Verify URL updates with `avg_slot=1` and a third column appears,
   labelled "IPL avg" (scope-appropriate label).
5. Verify FlagBadge null-renders in the average column.
6. Expand phase bands; verify PP/Middle/Death sub-rows in Batting +
   Bowling populate in all three columns.
7. Expand partnership per-wicket; verify 10 rows with sensible data.
8. Scroll to season trajectory strip; verify a team line + average
   line render per phase.
9. Narrow to `season_from=2024&season_to=2024` — verify the
   trajectory strip hides (single-season = no trajectory) and grid
   numbers update.
10. Add `series_type=bilateral_only` — verify average label updates to
    include the scope change and numbers shift accordingly.

### Unit-ish (direct API)

Hand-rolled fixture test in `tests/fixtures/test_scope_averages.py`:
for a known small scope (one tournament × one season), verify that
`scope/averages/batting/summary.value` equals `SUM(runs) /
SUM(legal_balls) × 6` computed directly via raw SQL over the fixture
DB. One test per discipline.

### `player_scope_stats` sanity check

One test: for a sample scope (IPL 2024), verify
`player_scope_stats.runs` summed across all rows equals `SUM(runs)`
over `delivery` in the same scope (pool conservation). And one
round-trip test: incrementally ingest a new match, assert the 22
affected (person, scope_key) rows got upserted with correct values.

## Docs sync

Per CLAUDE.md "Keeping docs in sync":

- `docs/api.md`: new section for each of the ~11 new `/scope/averages/*`
  endpoints with curl + abbreviated response. Shape change on the 5
  existing compare endpoints also documented (new metric envelope).
- `internal_docs/codebase-tour.md`: note the new endpoints, the new
  `player_scope_stats` table, the new populate script, the
  `TeamCompareGrid` / `AddTeamComparePicker` changes,
  `api/metrics_metadata.py`.
- `internal_docs/enhancements-roadmap.md`: add entry under the next
  letter in sequence with the date shipped.
- `internal_docs/design-decisions.md`: add an entry documenting (a)
  why scope averages are pool-weighted rather than mean-of-team-means,
  (b) why `player_scope_stats` is populated but not consumed in Spec 1
  (Path A rationale), (c) the `METRIC_DIRECTIONS` single-source-of-truth
  convention.
- `internal_docs/data-pipeline.md`: add `populate_player_scope_stats`
  to the pipeline diagram + auto-call section.
- `internal_docs/spec-team-stats.md`: cross-link the new spec.
- `CLAUDE.md` "Landing pages" section: update the Teams > Compare
  description to mention the average slot + phase bands + trajectory.
- `frontend/src/content/user-help.md`: new user-facing section
  explaining the Average column, phase bands, trajectory strip. One
  paragraph + a `/social/*.png` screenshot.

## Rollout phases within Spec 1

Three commits, shipped and deployed separately so each can be tested in
isolation:

1. **Schema + populate** — `player_scope_stats` table + populate
   scripts + incremental update hook + sanity tests. No API endpoints,
   no UI. Deployable with `bash deploy.sh --first` (DB rebuild).
2. **API family + metric envelope** — 11 new `/scope/averages/*`
   endpoints, 5 existing compare endpoints migrated to the new envelope
   (raw + scope_avg + delta_pct + direction + sample_size), the
   REG→NEW flip commit precedes this. Regression tests must pass before
   merge. No UI changes.
3. **UI** — `AddTeamComparePicker` button, `TeamCompareGrid` fourth
   slot, phase-band expansion, partnership-by-wicket expansion,
   season-trajectory strip. Browser-agent integration test must pass
   before merge.

Each commit is runnable and ships green tests. Per CLAUDE.md commit
cadence: don't batch.

## Open questions

1. **Average column label**: scope-computed (e.g. "IPL 2024 avg") vs
   generic ("League avg") vs user-overridable? Recommend
   scope-computed with a tooltip; cheap to change later.
2. **Phase bands default expanded or collapsed?** Recommend expanded —
   the phase insight is the value-add. Revisit if the grid feels too
   tall in the browser-agent pass.
3. **Trajectory strip placement**: below the grid (as specified) vs a
   sub-tab of Compare? Recommend below — it's small-multiples, fits
   inline, no extra click cost.
4. **Partnerships trajectory**: include season trajectory for
   partnerships-by-wicket, or skip? Recommend skip in Spec 1 — the
   partnership trajectory is 10 wicket-lines × N teams × 1 metric, gets
   dense fast. Revisit if users ask.
5. **Partnership "best" cell for the average column**: scope-wide
   highest partnership at that wicket with pair identity (as proposed)
   vs blank. Recommend showing it with identity — it's the ceiling
   reference and has a known holder.
