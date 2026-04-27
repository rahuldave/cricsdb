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

## What "average" means in this codebase (CRITICAL)

The avg column on the Compare tab and every chip's `scope_avg`
field represents the **per-innings average** in scope — what one
innings (one team's batting / bowling / fielding stint) typically
yields. NOT a pool aggregate.

This was changed 2026-04-26 (spec: `spec-avg-column-per-innings.md`)
after a user-reported bug where the avg column showed pool catches
per match (= 2x the per-team-per-match rate because each match has
2 fielding sides) while chips compared against a different
per-team baseline. After the fix, both the displayed avg column
value and the chip's `scope_avg` express the same per-innings
quantity.

### Per-innings-by-context table

| Metric family | Innings unit | Cardinality per match | Notes |
|---|---|---|---|
| Batting (per-team) | one batting innings | 2 per match | Per-innings = `pool_field / SUM(innings_batted)` |
| Bowling (per-team) | one bowling innings | 2 per match | Per-innings = `pool_field / SUM(innings_bowled)` |
| Fielding (per-team) | one fielding innings | 2 per match | Same as bowling — fielding innings == bowling innings (same physical event) |
| Partnerships | one batting innings | 2 per match | Per-innings = `total_partnerships / SUM(innings_batted)` |
| Match-level (results, toss) | one match | 1 per match | Pool == per-match-equivalent; no division needed |

### When the fields are stored vs computed per-innings

The `bucketbaseline_*` tables themselves still store **cell-level
pool sums** at populate time (this is the right atomic granularity
for SUM-over-cells composition). The per-innings transformation
happens at READ time inside the `_xxx_from_baseline` helpers in
`api/routers/scope_averages.py` and the equivalent in
`api/routers/teams.py`.

So: schema = pool. Response = per-innings. Don't confuse them.

### When pool == per-innings (no transformation needed)

Rates whose numerator and denominator both scale linearly with
innings count are ALREADY per-innings:

- `run_rate` = `SUM(runs) × 6 / SUM(legal_balls)` — both halve when
  you divide by innings count.
- `economy` = `SUM(runs_conceded) × 6 / SUM(balls)` — same.
- `strike_rate` = `SUM(balls) / SUM(wickets)` — same.
- `boundary_pct`, `dot_pct` — ratios.
- `avg_runs` (partnership) — already a per-partnership average.
- `avg_1st_innings_total` — already a per-batting-innings average
  (computed as `SUM(first_inn_runs) / SUM(first_inn_count)` which
  is `pool_runs / pool_innings_in_first_position`).

These return the same value whether you frame them as pool or
per-innings. No transformation needed in the read-side.

### When per-innings ≠ pool (transformation needed)

1. **Absolute counts** (catches, total_runs, fours, sixes, dots,
   wickets, wides, noballs, etc.) — divide by the appropriate
   innings_count.

2. **Per-match rates that aggregate both fielding/bowling sides**
   per match in the numerator while the denominator counts each
   match once: `catches_per_match`, `stumpings_per_match`,
   `run_outs_per_match`, `wides_per_match`, `noballs_per_match`.
   Each match has 2 fielding sides and 2 bowling sides; pool /
   matches = ~2x what a single team contributes per match. Halve
   at the read-side (= divide by 2).

### Chip-baseline scope alignment (the OTHER half of the invariant)

The Compare-tab chip and the avg column are wired through SEPARATE
code paths:

- **Avg column** (`/scope/averages/*`): the avg-slot fetch passes
  `aux.scope_to_team = primaryTeam` so the league baseline auto-
  narrows to the primary team's tournament universe (RCB → IPL
  only).
- **Chip envelope** (`/teams/{team}/*/summary` etc.): the team-side
  endpoint computes `scope_avg` by calling its OWN league-side
  helper `_xxx_aggregates(team=None, …)`. The frontend doesn't pass
  `scope_to_team` to the team endpoint, so naïvely the league call
  baselines against the BROAD pool (all men's club, not just RCB's
  leagues) — diverging from the avg column's auto-narrowed pool.

**Mechanism: `_league_aux(team, aux, filters)` in `api/routers/teams.py`**
synthesizes a copy of `aux` with `scope_to_team` set to `team`,
then passes it to the league-side helper:

```python
# api/routers/teams.py — _compute_xxx_summary, by-phase, by-wicket
t = await _xxx_aggregates(team, filters, aux)
s = await _xxx_aggregates(None, filters, _league_aux(team, aux, filters))
```

This makes the chip's `scope_avg` baseline against the same scope
the avg endpoint displays — so `chip_scope_avg == displayed_avg`
holds (ASSERT 1 of the chip-direction invariant).

**Synthesis is gated** on:
- `filters.team_type == 'club'` (added 2026-04-27, mirrors the
  frontend `TeamCompareGrid.fetchSlot` gate). For internationals,
  a single team's "tournament universe" contains that team in every
  match — narrowing the avg baseline against it produces a self-
  centered mirror that flatters the team's chips by construction
  (Australia 2024-25 in 6 events ⇒ 67-match avg pool, all featuring
  Australia). The frontend defaults to the full pool (e.g. Men's
  T20I 2024-25 = 870 matches) for internationals; the chip baseline
  must agree, so synthesis no-ops.
- `filters.tournament` not set (per `_scope_to_team_clause` and
  `baseline_where`) — explicit tournament filter takes precedence
  on both sides.
- `aux.scope_to_team` not already set (request-supplied scope
  overrides synthesis).

Applied at every league-side call site:
- `_compute_batting_summary`, `_compute_bowling_summary`,
  `team_fielding_summary`
- `team_batting_by_phase`, `team_bowling_by_phase`
- `team_partnerships_by_wicket`, `team_partnerships_summary` (the
  inline league-side query uses `_partnership_filter(filters,
  None, side, aux=_league_aux(team, aux))`).

### Read-side mechanism — end-to-end data flow

For one chip-bearing metric (say `catches_per_match`) on the team
column:

```
1. Frontend → GET /teams/{team}/fielding/summary
2. team_fielding_summary route fn calls:
   a. t = await _fielding_aggregates(team, filters, aux)
        → _fielding_aggregates_baseline(team, …)
          → SUM bucketbaselinefielding rows for cell (team, gender,
            team_type, tournament, season)
          → returns flat dict with team's POOL counts
            { catches: 69, matches: 15, catches_per_match: 4.6, … }
   b. s = await _fielding_aggregates(None, filters, _league_aux(team, aux))
        → _fielding_aggregates_baseline(None, league_aux)
          → SUM bucketbaselinefielding LEAGUE rows narrowed by
            scope_to_team=team via baseline_where()
          → flat dict, BUT with team=None branch → applies
            _apply_fielding_per_innings(out, matches*2):
              divide counts by fielding_innings, halve per-match rates
          → returns per-innings averages for the league
            { catches: 4.21, catches_per_match: 4.21, matches: 74, … }
   c. wrap_metric(t["catches_per_match"], s["catches_per_match"], …)
      → envelope { value: 4.6, scope_avg: 4.21, delta_pct: +9.3,
                   direction: 'higher_better', sample_size: 15 }
3. Frontend MetricDelta renders: value 4.6, ↑+9.3% green
   (because direction='higher_better' AND value > scope_avg)
```

The avg column on the same Compare tab fetches:
```
GET /scope/averages/fielding/summary?…&scope_to_team=team
  → _fielding_summary_from_baseline(filters, aux)
    → SUM bucketbaselinefielding LEAGUE rows narrowed by scope_to_team
    → _format_fielding_summary(...) which calls
      _apply_fielding_per_innings(out, matches*2)
    → returns { catches_per_match: 4.21, … }
```

**Both paths converge on the same per-innings value because they
share the per-innings transform** (`_apply_fielding_per_innings`
in `api/routers/teams.py`, imported by `scope_averages.py`). One
helper, two routers.

### Per-innings transform helpers (shared between routers)

Defined in `api/routers/teams.py` (near `_safe_div` / `_half`),
imported by `api/routers/scope_averages.py`:

| Helper | Used by | What it does |
|---|---|---|
| `_apply_batting_per_innings(d, innings_batted, drop_divisor)` | batting summary / by-season formatters; team-side `_batting_aggregates_*(team=None, …)` | Divides `total_runs`, `legal_balls`, `fours`, `sixes`, `fifties`, `hundreds` by innings_batted. Optionally drops `innings_batted` from response. |
| `_apply_bowling_per_innings(d, innings_bowled, drop_divisor)` | bowling summary / by-season; team-side `_bowling_aggregates_*(team=None, …)` | Divides count fields by innings_bowled, halves `wides_per_match`/`noballs_per_match`, recomputes `overs` from per-innings `legal_balls`. |
| `_apply_fielding_per_innings(d, fielding_innings)` | fielding summary / by-season; `_fielding_aggregates_*(team=None, …)` | Divides counts by `fielding_innings = matches × 2`, halves per-match rates. |
| `_apply_partnerships_per_innings(d, innings_batted)` | partnerships summary / by-wicket / by-season; inline league query in `team_partnerships_summary` | Divides `total`, `count_50_plus`, `count_100_plus` by innings_batted. |
| `_phase_dict_per_innings(by_phase, innings_count)` | `_xxx_by_phase_aggregates_*(team=None, …)` | Per-phase analogue — divides phase-row counts. |

Divisor sources:
- Baseline path: `_baseline_innings_batted/bowled/matches` query
  the corresponding `bucketbaseline*` table once with `baseline_where`.
- Live path: `_live_innings_batted/bowled/match_count` /
  `_innings_count_for_phase` run a small `COUNT(DISTINCT i.id)` /
  `COUNT(DISTINCT m.id)` against the delivery + innings + match
  tables.

Identity-bearing fields (`highest_total`, `worst_conceded`,
`best_pair`, `lowest_all_out_total`) are NOT touched — they're
single-observation payloads, not averages.

### The "chip-direction invariant" — what tests enforce

For every chip-bearing metric M (and every field on the team-summary
envelope, since Convention 2+3 unification):

- **ASSERT 1**: `chip_scope_avg == displayed_avg` — the chip and
  the avg column share the same numeric baseline.
- **ASSERT 2**: `delta_pct == round((value - scope_avg) / scope_avg
  × 100, 1)` — `wrap_metric`'s math is RAW signed; direction is
  informational, NOT a sign-flip.
- **ASSERT 3**: chip color (green/red) matches `direction × side-of-
  baseline` — green when `(higher_better and value > avg) or
  (lower_better and value < avg)`.

Validated by `tests/sanity/test_chip_direction_invariant.py`
(~460 assertions per run across 11 (scope, team) combos including
the canonical RCB+SRH+IPL 2025 reproducer). If this test fails,
either the chip's baseline scope diverges from the avg column's,
the metric's direction tag is wrong, `wrap_metric`'s math has
drifted, or one of the conventions has silently un-unified.
Don't ship a Compare-tab change without a green run.

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

### Convention 2 — `wides` and `noballs` are delivery COUNTS on every endpoint

`bucketbaselinebowling` stores BOTH columns:
- `wides`     — count of wide deliveries (`SUM(CASE WHEN extras_wides > 0 THEN 1 ELSE 0 END)`)
- `wide_runs` — sum of wide runs (`SUM(extras_wides)`)

Same pattern for `noballs` / `noball_runs`. **Every API endpoint
returns the COUNT** (delivery count). Unified 2026-04-26 — the
team-side endpoint previously returned wide-runs, diverging from
the avg endpoint and producing a chip-direction invariant failure
on `wides_per_match`. Now both endpoints return count, matching
the standard cricket convention ("team conceded 23 wides" = 23
wide deliveries, not 23 wide-runs).

The `wide_runs` column is still populated for any future caller
that genuinely wants a run-total (none today). Schema-level the
split is preserved; only the response semantic is uniform.

### Convention 3 — `catches` includes caught-and-bowled on every endpoint

`bucketbaselinefielding.catches` is the count where
`fc.kind = 'caught'` only; `caught_and_bowled` is a separate
column. **Every API endpoint returns the inclusive total**:

- `/teams/{team}/fielding/summary`: `catches` = `catches_only + cnb`
- `/scope/averages/fielding/summary`: `catches` = `catches_only + cnb`
- `/teams/{team}/fielding/by-season`: `catches` = `catches_only + cnb`
- All response shapes mirror this.

`caught_and_bowled` is exposed as a separate sub-count for callers
that need the breakdown — but consumers SHOULD NOT add catches +
caught_and_bowled (that double-counts). Unified 2026-04-26 — the
team-side endpoint previously excluded c_a_b in `catches`,
producing a chip-direction invariant failure for fielding catches.
Cricket convention: a catch is a catch regardless of who took it.

### Convention 4 — `tournament=''` represents NULL `event_name`

Cricsheet has bilateral matches with `event_name IS NULL`. We store
those as `tournament=''` (empty string) for SQL convenience —
exact-match WHERE clauses work without `IS NULL` handling. The
populate uses `COALESCE(m.event_name, '')` consistently; the read
side does the same via `baseline_where()`.

**Live-path scope narrowing must also COALESCE.** When
`_scope_to_team_clause` builds the `m.event_name IN (…)` subquery
for live-fallback paths, both sides of the IN-comparison are
wrapped in `COALESCE(event_name, '')`. Without this, SQL's
`value IN (NULL, …)` evaluates to UNKNOWN (not TRUE) and silently
EXCLUDES bilateral matches from the team's tournament universe —
diverging from the baseline path which includes them as `''` cells.

Caught 2026-04-26 on Aus unbounded internationals (565 matches via
baseline vs 503 via pre-fix live, ratio ~1.12). The fix is in
`api/routers/teams.py::_scope_to_team_clause` — see the docstring
there. Any new live-path narrower must do the same COALESCE dance.

### Convention 6 — Avg endpoint returns per-innings averages, NEVER pool

The `bucketbaseline_*` tables store cell-level pool sums (correct
atomic granularity for cross-cell SUM composition). The read-side
`_xxx_from_baseline` helpers in `api/routers/scope_averages.py`
divide every absolute count by innings_count and halve every
per-match rate that aggregates both sides per match. See "What
'average' means" section above for the per-metric table.

Same applies to `_xxx_aggregates_baseline` in `api/routers/teams.py`
when the helper is called with team=None (the league-side call
inside `_compute_xxx_summary` for the chip's `scope_avg`).

Don't reintroduce pool returns. The `test_chip_direction_invariant.py`
sanity test catches direct bypasses; `test_dispatch_equivalence.py`
catches divergence between the live and baseline paths (both must
return per-innings).

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
