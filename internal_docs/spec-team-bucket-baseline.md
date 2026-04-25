# Spec: Team / Bucket Avg Baselines (Phase 2 of Compare-tab perf)

Status: SHIPPED 2026-04-25 (commits 614b309, 8bf1151, 9c812ef, 501b23e).
Depends on: `spec-team-compare-scoped-slots.md` Phase 1 (commit `6c5b416`).

End-to-end speedup measured on `?team=RCB&gender=male&team_type=club&tab=Compare&compare1=__avg__`:
prod build went from **~4s → 1.7s** (2.4x). Dev (with StrictMode
double-mount) went from ~5s → 2.9s.

What shipped vs spec:
- 8 of 12 `/scope/averages/*` endpoints dispatch via baseline.
  Skipped: `/batting/summary`, `/partnerships/summary`,
  `/partnerships/by-wicket`, `/partnerships/by-season` — first three
  return identity-bearing payloads (highest_total / best_pair) needing
  schema additions; last needs `count_50_plus` / `count_100_plus`
  cell counters.
- 2 of ~12 `/teams/{team}/*` endpoints dispatch (the by-phase pair).
  Per-team summary + by-season endpoints stay live for the same
  identity-payload reasons.
- These cover the heaviest endpoints (3+ second by-phase queries).
  The deferred endpoints are <600ms each and don't dominate the
  page-load.

Future work to push prod < 1s: extend BucketBaselineBatting with
identity columns (`highest_inn_match_id`, `highest_inn_team`,
`highest_inn_innings_number`) + analogous additions for
partnerships → swap the remaining 4 scope-avg + 4 team endpoints.
Then async-deebase connection pooling (note in this spec) for
parallel SQLite reads.

## Why

Phase 1 (auto-scope-to-team) brought parallel `/scope/averages/*`
fetches for unbounded scope from 4.3s → 0.8s. But the user-facing
Compare-tab page-load for a wide scope (e.g.
`/teams?team=RCB&gender=male&team_type=club&tab=Compare`) is still
~4s in prod because:

- The page issues 27 API requests (12 team-profile + 12 avg + 3
  reference). SQLite's connection model in deebase serializes them
  through one writer/many-readers, but in practice they queue up.
- Both the team side AND the avg side aggregate live over thousands
  of deliveries. `RCB unbounded` = 275 matches; `IPL all-time` =
  1193 matches. Each of the 24 endpoints touches the same delivery
  table.

The fix is to denormalize: store per-`(gender, team_type, tournament,
season, team)` aggregates so the request becomes a row-fetch + a
SUM-over-cells, not a live aggregation over deliveries.

This is structurally identical to the `playerscopestats` table that
already exists for player-level work (Spec 2 of
`outlook-comparisons.md`).

## Goals

1. Drop unbounded auto-fill page-load from ~4s → <1s.
2. Speed up every other Teams-tab fetch too (by-season, by-phase,
   summary, partnerships) — the same precomputed rows serve them.
3. Keep the live-query path as a fallback for any scope combination
   we don't precompute (filter_venue, filter_team / filter_opponent
   rivalry, series_type, custom season ranges spanning partial
   seasons).
4. Stay correct — pool-weighted aggregations from cell-level sums
   must equal the live-query result byte-for-byte where the live
   path is available.

## Non-goals

- **Not** precomputing every filter combination. Filter_venue,
  series_type, rivalry filter_team+filter_opponent, and any future
  page-local aux filter stay live. Roughly 90% of fetches are in
  the precomputed regime; that's enough.
- **Not** unifying with `playerscopestats`. They share architecture
  but different join graph; distinct tables stay separate.
- **Not** fixing async-deebase serialization (see "Future work"
  section).

## Scope

### Filter combinations covered by precomputed lookups

All of:
- gender (always set)
- team_type (always set)
- tournament (optional, single value)
- season range (optional, contiguous range — covered by SUM over
  cells, gaps OK)

Plus the per-team option:
- team (optional — when set, fetch per-team rows; when unset, fetch
  league-baseline rows)

The Phase 1 `scope_to_team` becomes "team is unset AND we want the
universe narrowed to this team's tournaments" — handled at the
query side by selecting league-baseline rows whose tournament IN
(team's tournaments). Same table, same row layout.

### Filter combinations NOT covered (fall back to live)

- `filter_venue` set
- `filter_team` + `filter_opponent` (rivalry context)
- `series_type` set (bilateral_only / tournament_only / icc / club —
  the bucket is per-tournament so series_type can't refine within
  it without storing separate rows)
- Partial-season filters that don't align with cricsheet's season
  strings (we precompute per-cricsheet-season; ranges sum cells)

When ANY of these is set, the endpoint short-circuits to live-query.
Detection is a single `if` in each endpoint.

## Schema

One table per "discipline group", each at the same primary-key
granularity. Discipline split keeps per-row width manageable and
lets columnar ops scan less data.

```sql
-- Match-level totals (drives /scope/averages/summary).
CREATE TABLE bucket_baseline_match (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,           -- team name OR '__league__' for the
                                -- pool-weighted league-baseline row
  matches INTEGER NOT NULL,
  decided INTEGER NOT NULL,
  ties INTEGER NOT NULL,
  no_results INTEGER NOT NULL,
  toss_decided INTEGER NOT NULL,
  bat_first_wins INTEGER NOT NULL,
  field_first_wins INTEGER NOT NULL,
  PRIMARY KEY (gender, team_type, tournament, season, team)
);

-- Batting overall (drives /scope/averages/batting/summary).
CREATE TABLE bucket_baseline_batting (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,
  innings_batted INTEGER,
  total_runs INTEGER,
  legal_balls INTEGER,
  fours INTEGER,
  sixes INTEGER,
  dots INTEGER,
  dismissals INTEGER,           -- for batting average
  -- Per-innings extremities (combine via MAX/MIN).
  highest_inn_runs INTEGER,     -- MAX of per-innings totals
  lowest_all_out_total INTEGER, -- MIN of per-innings totals where 10 wickets
  -- Per-innings sums (for avg 1st-inn / 2nd-inn).
  first_inn_runs_sum INTEGER,
  first_inn_count INTEGER,
  second_inn_runs_sum INTEGER,
  second_inn_count INTEGER,
  PRIMARY KEY (gender, team_type, tournament, season, team)
);

-- Bowling overall (drives /scope/averages/bowling/summary).
CREATE TABLE bucket_baseline_bowling (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,
  innings_bowled INTEGER,
  runs_conceded INTEGER,        -- ALL deliveries (incl. wides/noballs)
  legal_balls INTEGER,           -- legal balls only
  total_balls INTEGER,           -- all balls (for econ)
  wickets INTEGER,               -- bowler-credited wickets only
  dots INTEGER,
  fours_conceded INTEGER,
  sixes_conceded INTEGER,
  PRIMARY KEY (gender, team_type, tournament, season, team)
);

-- Fielding overall.
CREATE TABLE bucket_baseline_fielding (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,
  matches INTEGER,               -- innings the team fielded
  catches INTEGER,
  stumpings INTEGER,
  run_outs INTEGER,
  PRIMARY KEY (gender, team_type, tournament, season, team)
);

-- Per-phase batting + bowling (PP / Mid / Death).
CREATE TABLE bucket_baseline_phase (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,
  phase TEXT NOT NULL,           -- 'powerplay' / 'middle' / 'death'
  side TEXT NOT NULL,            -- 'batting' / 'bowling'
  runs INTEGER,
  legal_balls INTEGER,
  total_balls INTEGER,           -- bowling econ uses all balls
  fours INTEGER,
  sixes INTEGER,
  dots INTEGER,
  wickets INTEGER,               -- only meaningful when side='bowling'
  PRIMARY KEY (gender, team_type, tournament, season, team, phase, side)
);

-- Per-wicket-position partnerships (drives /partnerships/by-wicket).
CREATE TABLE bucket_baseline_partnership (
  gender TEXT NOT NULL,
  team_type TEXT NOT NULL,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team TEXT NOT NULL,
  wicket_number INTEGER NOT NULL, -- 0..9 (cricsheet) → API exposes 1..10
  n INTEGER,                       -- partnership count
  total_runs INTEGER,
  total_balls INTEGER,
  best_runs INTEGER,               -- MAX
  PRIMARY KEY (gender, team_type, tournament, season, team, wicket_number)
);
```

### Table sizes (sanity)

Cells in the DB today (per `SELECT COUNT(DISTINCT ...)`):

- (gender, team_type, tournament, season): **1,114** rows for
  `team='__league__'` league-baseline rows.
- + per-team appearances: **4,575** rows (sparse — only team-cell
  combinations that actually played).
- Combined per discipline-table: **~5,700 rows**.
- 6 tables → **~34K rows total**, each row narrow (≤16 columns).
  Trivial — fits in OS page cache.

By-season (for `/by-season` endpoints) is naturally satisfied by
querying the per-cell rows grouped by season — no separate table.

By-phase: 6 tables with 3 phases × 2 sides = 6 sub-rows per cell →
~34K rows for `bucket_baseline_phase`.

By-wicket: 10 wicket positions per cell → ~57K rows.

## Aggregation rules — cell sums + post-divide

The single principle: **store sums and counts; compute rates after
SUM-ing over cells**.

| Metric | Cell-level columns | Aggregation | Post-divide |
|---|---|---|---|
| Run rate (RR) | runs, legal_balls | SUM(runs), SUM(legal_balls) | × 6 / SUM(legal_balls) |
| Strike rate (SR) | total_runs, legal_balls | SUM(total_runs), SUM(legal_balls) | × 100 / SUM(legal_balls) |
| Bat avg | total_runs, dismissals | SUM(total_runs), SUM(dismissals) | / SUM(dismissals) |
| Economy | runs_conceded, total_balls | SUM(runs), SUM(total_balls) | × 6 / SUM(total_balls) |
| Bowl avg | runs_conceded, wickets | SUM(runs), SUM(wickets) | / SUM(wickets) |
| Bowl SR | total_balls, wickets | SUM(balls), SUM(wickets) | / SUM(wickets) |
| Boundary % | fours+sixes, legal_balls | SUM(fours+sixes), SUM(legal_balls) | / SUM(legal_balls) |
| Dot % | dots, legal_balls | SUM(dots), SUM(legal_balls) | / SUM(legal_balls) |
| Avg 1st-inn | first_inn_runs_sum, first_inn_count | SUM, SUM | first/count |
| Highest single innings | highest_inn_runs | MAX(MAX) — natural | (passthrough) |
| Lowest all-out total | lowest_all_out_total | MIN(MIN) — natural | (passthrough) |
| Bat-first win % | bat_first_wins, decided | SUM, SUM | / decided |
| Toss-win = win % | (need joint counter) | (see below) | |

**Bat avg note.** T20 batting average traditionally uses dismissals
as denominator (not innings - not_outs). Cricsheet's `delivery`
table marks the dismissed batter (when `player_out IS NOT NULL`);
that's already what `_batting_aggregates` counts. Storing
`dismissals` as a sum gives correct combined averages.

**Joint counters not currently stored.** "Toss-win = match-win %" is
a joint property (toss winner AND outcome winner correlate). It
requires storing an extra counter `toss_win_match_win` per cell —
trivial to add. Same for any "X AND Y" probability.

**Pool weighting falls out.** The user's correctness concern about
"properly weighted averages" is satisfied by the SUM-then-divide
pattern: a SUM over cells is the same as aggregating the underlying
deliveries. RR for "RCB IPL 2020-2024" = SUM(runs across 5 cells)
× 6 / SUM(balls across 5 cells) = identical to the live query
SELECT SUM/SUM FROM delivery WHERE tournament=IPL AND season IN
(...).

**Per-innings stats** (highest, lowest, avg 1st-inn) need extra
care — they're per-innings, not per-delivery. Storing them as
(MAX, MIN, sum + count) at cell-level handles MAX/MIN naturally
and lets `avg_first_inn = SUM(first_inn_runs_sum) / SUM(first_inn_count)`
work cleanly across cells.

**Where the equivalence breaks** (and we accept it):
- A median (e.g. P50 first-innings score) cannot be combined from
  cell summaries. We currently don't expose medians in /scope/avg.
- An outlier-trimmed mean — same. Not currently exposed.

If we ever add median or trimmed metrics, they stay live-only.

## Population

### Pipeline

New script `scripts/populate_bucket_baseline.py` mirroring
`populate_player_scope_stats.py`:

- `populate_full(db)` — drops + rebuilds all 6 tables. Called by
  `import_data.py` at the end of every full rebuild, alongside the
  other `populate_*` calls.
- `populate_incremental(db, new_match_ids)` — for `update_recent.py`.
  Recomputes only the (gender, team_type, tournament, season) cells
  touched by new matches, plus their per-team rows. Implementation:
  enumerate the affected `(g, tt, t, s)` set from new_match_ids,
  DELETE those rows, recompute via the same SQL as full.

The full-rebuild SQL for each table is one INSERT … SELECT …
GROUP BY — same shape as the existing live aggregations, just
grouped by (gender, team_type, tournament, season, team) instead of
filtered by them.

For league-baseline rows: aggregate with `team='__league__'` over
matches without grouping by mp.team (i.e., one row per cell that
sums over the whole tournament-season).

For per-team rows: GROUP BY mp.team additionally.

### Indexes

```sql
CREATE INDEX ix_bucket_baseline_match_lookup
  ON bucket_baseline_match (gender, team_type, tournament, season, team);
-- (matches the PK; SQLite uses the PK as a covering index for these
-- patterns, so the explicit index is redundant. Listed for parity
-- with patterns in `populate_player_scope_stats`.)
```

ANALYZE after population (already in the import path).

### Population time budget

Per discipline table: ~1 SELECT scanning the underlying table
(delivery / wicket / partnership) once. Whole population should
take 30–90s — comparable to `populate_player_scope_stats` which
takes ~30s for 66K rows.

This runs once per full rebuild (every few weeks) and incrementally
during `update_recent.py` (daily). Cost is amortized.

## Query-side dispatch

Each `/scope/averages/*` endpoint gets a small wrapper:

```python
@router.get("/batting/summary")
async def scope_batting_summary(filters: ..., aux: ...):
    if _is_precomputed_scope(filters, aux):
        return await _batting_summary_from_baseline(filters, aux)
    return await _batting_summary_live(filters, aux)  # today's path
```

`_is_precomputed_scope` returns True iff:
- `filters.filter_venue` is None
- `filters.filter_team` is None and `filters.filter_opponent` is None
- `aux.series_type` is None (or 'all')
- The season range, if set, has well-formed `season_from`/`season_to`
  (not partial)

For the team-side endpoints (`/teams/{team}/batting/summary` etc.),
the same dispatch applies but with `team=path` instead of
`team='__league__'`.

The live-path is preserved for safety + for filter combinations not
in the precomputed regime.

### Same-table for team + league rows

The dispatch query filters by `team = :team` (path team) OR
`team = '__league__'` (avg slot). Same table, one indexed lookup.
The auto-scope-to-team case (Phase 1) becomes:

```sql
SELECT ... FROM bucket_baseline_batting
WHERE gender=:g AND team_type=:tt AND team='__league__'
  AND tournament IN (
    SELECT DISTINCT tournament FROM bucket_baseline_match
    WHERE gender=:g AND team_type=:tt AND team=:scope_to_team
  )
  AND (:season_from IS NULL OR season >= :season_from)
  AND (:season_to IS NULL OR season <= :season_to)
```

Note: `bucket_baseline_match` is the natural place to enumerate
"tournaments this team has played in" — one COUNT query against the
denormalized table replaces the matchplayer subquery from Phase 1.

## Tests

- **Sanity test** `tests/sanity/bucket_baseline_consistency.py`:
  for ~20 sampled (gender, team_type, tournament, season, team)
  combinations, run the live query AND the baseline-table query;
  assert byte-identical numeric results to the precision the API
  exposes. This is the same shape as
  `tests/sanity/player_scope_stats.py`.
- **Regression**: NO `urls.txt` updates needed — the response
  shape is unchanged; only the source of the numbers changes. Run
  `tests/regression/run.sh scope-averages` to confirm 0 drifted.
- **Integration**: extend `tests/integration/team-compare-average.sh`
  with a "scope_to_team unbounded" case that asserts the column
  renders in <2s wall-clock (sloppy timing but catches regressions
  past Phase 2).

## Rollout

Three commits, each ships green:

1. **Schema + populate script** (no endpoint changes). Sanity test
   verifies population correctness against live queries. Tables
   exist but no endpoint reads them.
2. **Read path for `/scope/averages/*`** — wrapper dispatch with
   live-query fallback. Each endpoint individually flipped. Compare
   regression suite stays 0-drifted because shape is unchanged and
   numbers are byte-identical.
3. **Read path for `/teams/{team}/*`** — same dispatch but with
   path team. Integration smoke runs Compare-tab unbounded scenario
   end-to-end and asserts <2s.

Each commit ships independently runnable.

## Future work — async deebase serialization

User flagged 2026-04-25: deebase is built on async SQLAlchemy but
parallel requests appear to serialize through one connection.
SQLAlchemy with `aiosqlite` driver SHOULD support concurrent reads
in WAL mode via a connection pool. Investigation needed:

- Does deebase open a single shared connection or a pool?
- If single, why? (FastAPI request handler pattern, global state,
  configuration default?)
- Is the bottleneck even SQLite, or is it Python's GIL in a
  thread-pool executor wrapping sqlite3 calls?
- Can we add a small read-only connection pool without disturbing
  the write path?

This is a separate effort. Phase 2 reduces wall-clock by reducing
work, not by parallelizing. Future async-pool work would compose
with Phase 2 multiplicatively.

## Resolved (2026-04-25 review)

1. **Synthetic intl bucket — SKIPPED.** With per-cell SUM, summing
   31 single-row cells is fast. The bucket idea was a workaround
   for live-aggregation cost, not for data shape.
2. **Per-team `/teams/{team}/*` endpoints — INCLUDED in this spec.**
   Same table, same dispatch logic, path team replaces
   `'__league__'`. Bigger net speedup (every Teams tab page-load
   faster, not just Compare). Lands as Commit 3.
3. **Joint counters for toss/result correlation** — deferred. Cheap
   to add when we want it.

## Schema drift discipline

When we add a metric to `/scope/avg`, the corresponding cell-level
counter has to land in `populate_bucket_baseline.py` AND the
read-side query helper. Forgetting means the live path returns the
metric and the baseline path omits it. Mitigated by the sanity
test, which samples responses and diffs them — catches drift on
next run.

## Decision summary

- **Granularity**: per (gender, team_type, tournament, season, team)
  including a `'__league__'` row for the pool-weighted baseline.
- **Six tables**, one per discipline group, narrow rows.
- **~34K rows total**. Negligible storage.
- **Sums + counts** stored at cell level; rates computed by
  SUM-then-divide at query time. Pool-weighted by construction.
- **Live-query fallback** preserved for filter_venue / rivalry /
  series_type / partial-season filters.
- **Sanity test** locks correctness against the live path.
- **Three-commit rollout**: populate → read scope-avg → read team.
- **Async-deebase** logged as separate follow-up.
