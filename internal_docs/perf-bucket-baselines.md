# Perf — bucket_baseline_* tables (Compare-tab Phase 2)

Sibling of `perf-leaderboards.md`. This is the runbook for the
denormalized per-cell baseline tables that drive the Teams Compare
tab + every per-team Teams page.

Spec (with all design decisions): `spec-team-bucket-baseline.md`.
End-to-end perf result: prod page-load on the canonical URL went
from **~4s to 0.81s (5x)**. See the spec for the latency table per
phase.

## What's stored

Six narrow tables — one per discipline group — at the granularity
of `(gender, team_type, tournament, season, team)`. The `team`
column is either a real team name OR the literal `'__league__'`
(constant `LEAGUE_TEAM_KEY`) for pool-weighted league baseline rows.
A SUM-over-cells at query time produces the same numbers as the
live aggregator running over `delivery` / `wicket` /
`fieldingcredit` / `partnership`.

Total ~96K rows across the 6 tables on the current DB. Trivial vs
the 2.95M-delivery / 160K-wicket source tables.

### Table-by-table

| Table | Grain | Drives | Notable cols beyond counters |
|---|---|---|---|
| `bucketbaselinematch`        | one row per cell | `/scope/averages/summary` + match-count denominator everywhere | `bat_first_wins` / `field_first_wins` |
| `bucketbaselinebatting`      | one row per cell | `*/batting/summary` + `*/batting/by-season` | `highest_inn_*` (4-col identity), `lowest_all_out_*` (4-col identity), `first_inn_runs_sum` / `_count`, `second_inn_*`, `fifties`, `hundreds` |
| `bucketbaselinebowling`      | one row per cell | `*/bowling/summary` + `*/bowling/by-season` | `wickets` (5-kind exclusion — see Convention 1), `wide_runs` / `noball_runs` (Convention 2), `worst_inn_runs` |
| `bucketbaselinefielding`     | one row per cell | `*/fielding/summary` + `*/fielding/by-season` | `catches` (kind=`'caught'`), `caught_and_bowled` (split — see Convention 3) |
| `bucketbaselinephase`        | one row per (cell, phase, side) — 6 sub-rows per cell | `*/{batting,bowling}/by-phase` | `wickets` only meaningful on `side='bowling'` rows |
| `bucketbaselinepartnership`  | one row per (cell, wicket_number) — 10 sub-rows per cell | `*/partnerships/{summary,by-wicket,by-season}` | `count_50_plus`, `count_100_plus`, `best_pair_partnership_id` (FK to `partnership.id`) |

### What's NOT stored (read-side falls back to live)

- **Per-pair partnership aggregates.** `/teams/{team}/partnerships/summary`
  returns `best_pair` (top pair by total runs together) — this needs
  per-`(batter1_id, batter2_id)` aggregation that doesn't fit the
  per-cell shape. Endpoint stays live. To swap it: add a
  `bucket_baseline_top_pairs(cell-key, batter1_id, batter2_id, n,
  total_runs, best_runs)` sidecar table (~50K rows).
- **`worst_inn_runs` identity** (`/teams/{team}/bowling/by-season`'s
  `worst_conceded`). The schema stores the runs value but not the
  match identity; reader does ONE small live SELECT to find the
  match_id. Cheap.
- **`best_partnership` identity** (`/scope/averages/partnerships/by-wicket`
  + `/teams/{team}/partnerships/by-wicket`). Schema stores the
  `partnership_id`; reader does ONE SELECT against `partnership`
  table for the full identity payload. Cheap.

## Conventions baked into the schema

These are non-obvious decisions that future contributors would
otherwise try to "fix" — please read before changing.

### Convention 1 — Bowler-credited wickets exclude 5 kinds

Both populate AND every consumer use:

```
w.kind NOT IN (
  'run out', 'retired hurt', 'retired out',
  'obstructing the field', 'retired not out'
)
```

The previous (pre-Phase-2) `/scope/averages/bowling/*` live SQL
omitted `'retired not out'` (4-kind exclusion), making it
inconsistent with `/teams/{team}/bowling/*`. Fixed in commit
`a02c11b` so all bowler-credit consumers agree.

If you add a new bowler-wickets consumer: use `BOWLER_WICKET_EXCLUDE`
in `api/routers/teams.py` (5-kind tuple) — never hand-type the
list.

### Convention 2 — `wides` is a count; `wide_runs` is the run total

`bucketbaselinebowling` stores BOTH:
- `wides`     — count of wide deliveries (`SUM(CASE WHEN extras_wides > 0 THEN 1 ELSE 0 END)`)
- `wide_runs` — sum of wide runs (`SUM(extras_wides)`)

Same pattern for `noballs` / `noball_runs`. The two have always had
different semantics in different endpoints:
- `/scope/averages/bowling/summary` returns count.
- `/teams/{team}/bowling/summary` returns runs.

Pre-existing inconsistency (not invented by Phase 2). Schema
supports both so dispatchers can pick the matching semantic.

### Convention 3 — `catches` excludes `caught_and_bowled` in the team helper

`bucketbaselinefielding.catches` is the count where
`fc.kind = 'caught'` only. `caught_and_bowled` is a separate column.
Two response shapes consume this:
- `/teams/{team}/fielding/summary` returns `catches` =
  `bucketbaselinefielding.catches` (excludes c_a_b).
- `/scope/averages/fielding/summary` returns `catches` =
  `catches + caught_and_bowled` (includes c_a_b).

Both endpoints' formatters handle their own combination — the
schema stores the split so callers can choose. Pre-existing
inconsistency.

### Convention 4 — `tournament=''` represents NULL `event_name`

Cricsheet has bilateral matches with `event_name IS NULL`. We store
those as `tournament=''` (empty string) for SQL convenience —
exact-match WHERE clauses work without `IS NULL` handling. The
populate uses `COALESCE(m.event_name, '')` consistently; the read
side does the same via `baseline_where()`.

### Convention 5 — Empty-fielding cells get a row with counters=0

If `fieldingcredit` table is empty (e.g. a stale prod-snapshot
copy from before the fielding-populate pipeline was added), the
populate would normally yield zero `bucketbaselinefielding` rows
because the original SQL started `FROM fieldingcredit`.

`_populate_fielding` drives row emission from `match` (with
`LEFT JOIN delivery + LEFT JOIN fieldingcredit`) so cells with no
credits still get a row with `matches=actual_count, catches=0,
stumpings=0, run_outs=0`. Critical for the `/scope/averages/fielding/summary`
endpoint where `catches_per_match = catches / matches` needs the
real matches denominator.

The reader side complements this: `_fielding_by_season_from_baseline`
adds `HAVING SUM(catches+cnb+stumpings+run_outs) > 0` to the
GROUP BY so byte-identity with live's "no row when no data" holds.

## How rows are populated

Single script: `scripts/populate_bucket_baseline.py`.

### Two modes

```python
populate_full(db)                          # rebuild every cell
populate_incremental(db, new_match_ids)    # rebuild affected cells only
```

`populate_full` is called by `import_data.py` after the other
populate scripts (fielding_credits, keeper_assignments, partnerships,
player_scope_stats). `populate_incremental` is called by
`update_recent.py` with the list of just-imported match ids.

### Standalone CLI

```bash
# Local DB
uv run python scripts/populate_bucket_baseline.py

# Different DB (e.g. /tmp prod-snapshot copy)
uv run python scripts/populate_bucket_baseline.py --db /tmp/cricket-prod-test.db
```

### Implementation pattern

For each table, populate splits the work:

1. **Build temp tables** of per-innings (or per-partnership /
   per-batter-innings) data once. Reused by INSERT + identity
   UPDATE statements so we don't re-aggregate `delivery` for every
   identity column.
2. **INSERT league rows** (`team='__league__'`) — cell-wide
   aggregates.
3. **INSERT per-team rows** — same shape, GROUP BY adds team.
4. **UPDATE identity columns** (`highest_inn_*`, `lowest_all_out_*`,
   `worst_inn_runs`, `best_pair_partnership_id`) via `ROW_NUMBER()
   OVER (PARTITION BY cell ORDER BY ...) AS rn` then `WHERE rn=1`.
5. **UPDATE secondary aggregates** like `fifties` / `hundreds` /
   bowling phase wickets that need a separate per-(batter, innings)
   or per-(phase) GROUP BY.
6. **DROP temp tables**.

Rationale: SQLite's window functions handle the identity picks
cleanly; the alternative (correlated subqueries inside SELECT) is
10x slower because the planner doesn't materialize.

### Total time

- Full rebuild on local DB: **~115 s** (was ~93s before identity
  columns added — UPDATE passes added ~22s).
- Incremental on a single cell: **<1 s** (DELETE + reINSERT a
  handful of rows).

### Indexes

```sql
CREATE INDEX IF NOT EXISTS ix_bucketbaselinematch_lookup
  ON bucketbaselinematch (gender, team_type, tournament, season, team);
-- + analogous on the other 5 tables; phase + partnership get
-- (phase, side) / (wicket_number) appended.
```

Created idempotently by `_ensure_tables()` on each populate call.

### Phase 1 dependency: `ix_matchplayer_team`

Before bucket_baseline existed, Phase 1 added a backend
`scope_to_team` aux param + a covering index on `matchplayer.team`
to make the avg slot's "narrow to primary team's tournaments"
subquery fast. With bucket_baseline, the subquery now reads from
`bucketbaselinematch` (no matchplayer JOIN at request time) but
populate still uses `matchplayer.team` so the index stays
worthwhile. Created in `import_data.py` + `update_recent.py`
alongside the leaderboard indexes.

## How rows are read

Dispatch helper module: `api/routers/bucket_baseline_dispatch.py`.

### `is_precomputed_scope(filters, aux)`

Returns `True` iff this scope is fully covered by bucket_baseline
(roughly: gender + team_type + optional tournament + optional
season range + optional `scope_to_team`; venue / rivalry /
series_type / partial-season filters all fall back to live). Single
function call at the top of every dispatched endpoint.

### `baseline_where(filters, aux, team=LEAGUE_TEAM_KEY, table_alias='')`

Builds the WHERE clause that selects rows for a given scope. Returns
`(where_str, params_dict)`. Handles:
- `team='__league__'` for league rows; team=path-team for per-team.
- `tournament` exact match or, when unset and `aux.scope_to_team`
  is set, narrows via subquery against `bucketbaselinematch` to
  the team's tournament universe (Phase 1's "RCB → IPL only"
  semantic, now cached in the baseline match table).
- `season_from` / `season_to` range.

### Per-endpoint dispatch shape

Every dispatched endpoint follows this pattern:

```python
@router.get("/.../path")
async def my_endpoint(filters, aux):
    if is_precomputed_scope(filters, aux):
        return await _my_endpoint_from_baseline(filters, aux)
    return await _my_endpoint_live(filters, aux)
```

The `_from_baseline` function reads from one or more
`bucketbaseline_*` tables via SUM-over-cells; the `_live` function
is the original aggregator (preserved unchanged). Identity-bearing
fields read the row holding `MAX(highest_inn_runs)` or
`MAX(best_runs)` and follow the FK to fetch full identity from
`partnership` when needed.

For helper-level dispatch (`_batting_aggregates` etc. — called by
multiple endpoints with envelope wrapping), the dispatch lives
inside the helper itself; callers don't change.

### Currently dispatched

All 12 `/scope/averages/*` endpoints + 11 of 12 `/teams/{team}/*`
endpoints. The lone holdout is `/teams/{team}/partnerships/summary`
(needs the `bucket_baseline_top_pairs` sidecar mentioned above).

## Validation

Three layers — see `tests.md` for invocation:

1. **Cell-level pool conservation** (`tests/sanity/test_bucket_baseline.py`):
   SUM-over-cells from baseline rows equals the live aggregator's
   output for the whole DB and per-cell samples. Catches schema /
   populate bugs that show up as off-by-N.
2. **Endpoint dispatch equivalence** (`tests/sanity/test_dispatch_equivalence.py`):
   For 22 endpoints × 11 scopes = 212 pair-comparisons, calls
   `_xxx_from_baseline` AND `_xxx_live` with the same FilterParams +
   AuxParams and diffs the JSON. Proves the two implementations
   produce identical responses — not just that the dispatch is
   stable.
3. **URL-level regression** (`tests/regression/run.sh`):
   HEAD vs patched md5-diff across 264 URLs in 9 suites. 50 in
   `scope-averages/` cover bucket_baseline directly (incl. 14
   live-fallback URLs that force `is_precomputed_scope=False`); the
   other 214 catch incidental breakage elsewhere.

All three layers must be green before shipping any backend change
that touches the baseline schema, populate logic, or dispatch
helpers.

## Known follow-ups

- Add `bucket_baseline_top_pairs` sidecar to swap the last endpoint.
- Async-deebase connection pool — backend 24-endpoint parallel sum
  is ~610 ms today (still serialized through one SQLite connection
  behind aiosqlite). With N=4 readers in WAL mode, projected
  ~150 ms. Composes multiplicatively with bucket_baseline.
