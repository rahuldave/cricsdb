# Spec: Players — Position-Adaptive Scope-Average Baselines (Surface 1)

Status: build-ready.
Depends on: `playerscopestats` table + populate scripts (shipped under
`spec-team-compare-average.md` Path A as a parallel workstream — present
and incrementally maintained, never yet read from).
Originates: `internal_docs/outlook-comparisons.md` Surface 1 (Player
compare with position-matched average). Design hardened across a single
session on 2026-05-19 — the resolution log is preserved in the open-
questions section.

## Overview

The Players page (`/players?player=X` and `/players?player=X&compare=Y`)
renders four discipline bands (Batting → Bowling → Fielding → Keeping)
with raw values only. A user sees Kohli's IPL average of 42.38 but has
no anchor for whether that's high or low for a player who batted his
position mix in that scope. Teams Compare has already shipped the
inline-baseline lens (`MetricEnvelope` —
`value` / `scope_avg` / `delta_pct` / `direction` / `sample_size`); this
spec extends the same lens to player pages with **position-adaptive**
cohort baselines.

The math: each metric's `scope_avg` is a **convex combination of
per-bucket cohort metrics**, weighted by the player's own bucket-mix
in scope:

```
scope_avg(metric) = Σ_b  (player_mix[b] × cohort_metric[b])

where  player_mix[b]  = player's share of innings/overs/dismissals at bucket b
       cohort_metric[b] = aggregate metric across all in-scope players at bucket b
```

The three disciplines share that shape, differing only in their bucket
definitions:

| Discipline | Bucket | # of buckets | Mix source |
|---|---|---:|---|
| Batting   | Position (1+2 merged opener; 3-11 individual) | 10 | `playerscopestats_position`, `innings_at_position / total_innings` |
| Bowling   | Over of delivery (1-20 individual) | 20 | `playerscopestats_over`, `balls_in_over / total_balls` |
| Fielding  | (keeper / outfielder) — single binary, **no position weighting** | 2 | `playerscopestats.matches_as_keeper / matches` |

Fielding is **not** position-weighted in the baseline math (the
dimensional analysis doesn't work the same way — see §5.4) but the
per-position-of-dismissed-batter histogram is still collected and
surfaced, so the follow-up viz spec can build impact-weighted analyses
on top.

Three child tables back this — `playerscopestats_position`,
`playerscopestats_over`, `playerscopestats_fielding_position` — all
denormalised, all incrementally maintained alongside the existing
`playerscopestats`. They serve **double duty**: cohort aggregation for
baselines (this spec) AND per-player histograms for the follow-up
visualisation spec.

## Scope

**In scope:**

- Three new child tables (§4) + their populate / incremental scripts.
- Four new endpoints under `/api/v1/scope/averages/players/*`:
  - `GET /scope/averages/players/batting/summary`
  - `GET /scope/averages/players/bowling/summary`
  - `GET /scope/averages/players/fielding/summary`
  - `GET /scope/averages/players/keeping/summary`
  Each accepts a discipline-appropriate mix parameter and returns the
  envelope-shape baseline + per-bucket sub-rates.
- Migration of the four player summary endpoints to the metric envelope:
  - `GET /batters/{id}/summary`
  - `GET /bowlers/{id}/summary`
  - `GET /fielders/{id}/summary`
  - `GET /fielders/{id}/keeping/summary`
  Each numeric field becomes `{value, scope_avg, delta_pct, direction,
  sample_size}` via backend-folded composition.
- Per-bucket sample-support thresholds + renormalisation rule (§6).
- Distribution arrays on the four player summary endpoints
  (`position_distribution`, `over_distribution`,
  `dismissal_position_distribution`) — present in the API in this spec,
  consumed by the next spec for visualisations.
- Extension of `METRIC_DIRECTIONS` (`api/metrics_metadata.py`) with the
  player-grain metric keys (audit + add).
- The `drop=` API plumbing — query parameter on every
  `/scope/averages/players/*` endpoint that masks one or more filter
  axes before SQL clause construction. **Not user-facing in this spec.**
  Lock the shape here so Surfaces 3a / 4 / 6 don't require retrofitting.
- Frontend pass on `/players`:
  - `PlayerSummaryRow` renders the inline-baseline three-tier visual
    (value, `~base N`, delta chip) matching the Teams Compare treatment.
  - Per-column auto-derivation of bucket mix from the response payload.

**Not in scope:**

- The "+ Add average batter in scope" slot from `outlook-comparisons.md`
  §Surface 1 — superseded by inline-everywhere per the 2026-05-19
  resolution.
- UI charts visualising the bucket-level distributions
  (position histogram on `/batting?player=X`, over distribution on
  `/bowling?player=X`, dismissed-position histogram on
  `/fielding?player=X`). **Three separate follow-up specs**, all pure
  UI work because the data lands here.
- Impact-weighted fielding metrics ("dismissing top-order batsmen is
  more valuable than dismissing tail"). The raw per-position
  dismissal counts ship here; the weighting and the chart that uses
  them is next-spec work.
- N-way compare grid changes beyond per-column envelope rendering —
  layout stays as `spec-players.md` defined it.
- Surfaces 2 / 3 / 4 / 5 / 6 from `outlook-comparisons.md` — separate
  future specs, each consuming the same endpoint family.
- Distribution-panel baseline overlays — see
  `project_baseline_distributions.md`. Different math (per-innings
  runs distribution), different surface.

## UX

### Inline baseline rendering (single-player view)

Each numeric stat cell in `PlayerSummaryRow` renders three tiers,
tightly stacked, matching the Teams Compare visual treatment:

```
Avg
42.38
vs base 28.7   ↑ +47.7%
```

- Bold value (existing).
- Faint "vs base N" line (`MetricDelta withScopeAvg={true}` with the
  label prop overridden to "base" — see Q5 resolution).
- Coloured delta chip — green when aligned with direction, red when
  not, neutral grey when `direction === null` (counts).

When `scope_avg` is null (player has no data in scope, or every bucket
fell below sample-support after renormalisation) — the second + third
tier hide, the bold value stays.

### Inline baseline rendering (compare columns)

In the compact `.wisden-player-compact` layout (the N-way compare
grid), the same three tiers render inside the right-hand value column
of the definition list. Each column's baseline is **derived
independently from that column's primary**:

- Bumrah's batting band → baseline weighted by his (mostly #10-#11)
  position mix.
- Kohli's batting band → baseline weighted by his (top-order) mix.
- No cross-discipline confusion: each band's mix lives within its
  own discipline's data.

### Identity line

Unchanged from `spec-players.md`. The role classifier output stays as-is.

### Band visibility

Unchanged. A band stays hidden when the player has no data in scope
(`innings > 0`, `balls > 0`, etc.). When hidden, no baseline is fetched
for that band.

### Tooltip on `vs base N`

Tooltip names the cohort using the player's actual mix vector. Two
phrasings depending on concentration:

- **Concentrated** (one bucket ≥ 0.70): `"Position-mix baseline —
  Opener (54% of innings); 287 players in cohort"`.
- **Spread** (no bucket ≥ 0.70): `"Position-mix baseline — Opener 54%,
  #3 28%, #4 12%, #5 6%; cohort: 412 players, 8,917 innings"`.

Phrasing uses the bucket labels (Opener, #3, ..., #11; PP 1, PP 2, ...,
Death 20; Keeper / Outfielder).

### Small-sample suppression

Per-bucket — see §6. If every bucket in the player's mix is below
support → the cell renders as `—` with tooltip "Cohort sample
insufficient at this scope." If some buckets are below support →
they're dropped from the convex combination AND the player's mix is
renormalised over the remaining buckets. Tooltip lists which buckets
were excluded.

## Data layer

### Schema bump on `playerscopestats` (existing table)

No structural change; the existing table continues serving as the
per-(person, scope) index for keeper status and matches_as_keeper.
**No new columns added here** — the per-position / per-over /
per-fielding-position aggregates live in dedicated child tables (§4.2)
rather than ballooning the parent.

### New child table — `playerscopestats_position` (batting, per position bucket)

```
playerscopestats_position
  person_id     VARCHAR  FK → person
  scope_key     VARCHAR  matches playerscopestats.scope_key
  position_bucket  INT   1=opener (pos 1+2), 2=#3, 3=#4, ..., 10=#11
  innings       INT      innings batted at this bucket
  runs          INT
  legal_balls   INT
  dismissals    INT
  fours         INT
  sixes         INT
  dots          INT
  PRIMARY KEY (person_id, scope_key, position_bucket)
  INDEX        (scope_key, position_bucket)
```

Rows expected: ~670K (67K parent × ~10 buckets, sparse). Index supports
the hot cohort query: "all batters at bucket b in scope" → straight
index scan + GROUP BY.

### New child table — `playerscopestats_over` (bowling, per over)

```
playerscopestats_over
  person_id      VARCHAR  FK → person
  scope_key      VARCHAR  matches playerscopestats.scope_key
  over_number    INT      1-20
  runs_conceded  INT
  legal_balls    INT
  wickets        INT
  dots           INT
  boundaries     INT
  PRIMARY KEY (person_id, scope_key, over_number)
  INDEX        (scope_key, over_number)
```

Rows expected: ~1.3M (67K × ~20 over buckets, sparse — many bowlers
only bowl 4 overs/match, so only 4-12 distinct over numbers per scope).

### New child table — `playerscopestats_fielding_position` (per dismissed-batter position)

```
playerscopestats_fielding_position
  person_id        VARCHAR  FK → person — the FIELDER
  scope_key        VARCHAR
  position_bucket  INT      1=opener, 2=#3, ..., 10=#11 (the DISMISSED batter's position)
  catches          INT
  stumpings        INT
  run_outs         INT
  dismissals       INT      = catches + stumpings + run_outs
  PRIMARY KEY (person_id, scope_key, position_bucket)
  INDEX        (scope_key, position_bucket)
```

Rows expected: ~670K. Position derivation reuses the
`_derive_positions` helper in `populate_player_scope_stats.py` —
positions are per-innings, computed by delivery order; the fielding
credit's innings_id resolves to that position vector.

### Populate scripts

Three new scripts, modelled on `populate_player_scope_stats.py`:

- `scripts/populate_playerscopestats_position.py`
- `scripts/populate_playerscopestats_over.py`
- `scripts/populate_playerscopestats_fielding_position.py`

Each provides:
- `populate_full(db)` — truncate + rebuild from every match.
- `populate_incremental(db, new_match_ids: list[int])` — delete +
  re-insert rows touched by the new matches (typically 22-30 rows per
  match per script — XI × 2 teams × ~1 scope, with sparse bucket
  coverage).

Auto-called from `import_data.py` (full) and `update_recent.py`
(incremental), wired in alongside the existing
`populate_player_scope_stats.py` calls. Same pattern we exercised in
yesterday's 2026-05-18 incremental run (4 matches × 3 scripts =
manageable).

Note: bowling per-over and fielding per-dismissed-position both need
the innings-level position vector. The populate scripts should compute
the vector ONCE per innings and share it across the three child
tables, not recompute three times. Shared helper:
`api/innings_positions.py::positions_for_innings(innings_id)` or
similar.

### Existing indexes carry the cohort queries

The `(scope_key, position_bucket)` / `(scope_key, over_number)` indexes
on the child tables drive the cohort query directly. No additional
delivery-table scans needed for cohort aggregation. Verified shape:

```sql
-- Cohort metric at bucket b in scope S
SELECT SUM(runs), SUM(legal_balls), SUM(dismissals)
FROM playerscopestats_position
WHERE scope_key = :scope_key
  AND position_bucket = :bucket;
```

Index scan, no table read beyond the rows in scope. Sub-50ms for any
narrow scope; sub-200ms for unfiltered.

### Filter composition

The endpoint family accepts every standard FilterBar axis:
`gender` / `team_type` / `tournament` / `season_from` / `season_to` /
`filter_venue` / `filter_team` / `filter_opponent` / `series_type` /
`team_class`. The filter clauses apply at the parent `playerscopestats`
row level (via `scope_key`), which transitively scopes the child table
rows.

### `drop=` mechanism

Query parameter on every `/scope/averages/players/*` endpoint: a
comma-separated list of filter axis names to mask before clause
construction. **Per-endpoint structural plumbing, not a user-facing
toggle.** Reserved for tautology-prone surfaces in later specs:

- Surface 3a (venue character strip): `drop=filter_venue` to compute
  the league baseline without the venue narrowing.
- Surface 4 (H2H baseline): `drop=filter_team,filter_opponent` to
  remove rivalry constraint from the baseline.
- Surface 6 (tournament era): `drop=season_from,season_to` to compute
  all-time baseline vs the in-season value.

For Surface 1 specifically, `drop=` is **unused** — the player-at-
venue / player-in-rivalry case wants both sides scoped identically
(home-specialist signal is preserved).

Recognised axis names: `gender`, `team_type`, `tournament`, `season`,
`filter_venue`, `filter_team`, `filter_opponent`, `team_class`,
`series_type`. Implementation: `FilterParams.build(drop=...)` masks
the named axes before clause construction. Mirrors the existing `aux=`
extension pattern.

### Surfacing distribution arrays on player summary endpoints

The four summary endpoints gain three new fields:

- `/batters/{id}/summary` adds `position_distribution: [{bucket: 1-10,
  innings, runs, legal_balls, dismissals, fours, sixes, dots}]`. Sourced
  from `playerscopestats_position` aggregated to the request's scope.
- `/bowlers/{id}/summary` adds `over_distribution: [{over: 1-20,
  runs_conceded, legal_balls, wickets, dots, boundaries}]`. Sourced
  from `playerscopestats_over`.
- `/fielders/{id}/summary` adds `dismissal_position_distribution:
  [{bucket: 1-10, catches, stumpings, run_outs, dismissals}]`. Sourced
  from `playerscopestats_fielding_position`.

These power the convex-combination weighting in this spec **and** the
follow-up histogram charts. Both consumers read the same array.

The mix vector itself (a 5/10/20-element fraction array) is derived
from these distributions at request time on the backend, and **passed
internally** to the scope-averages composer (backend folding — see
§5.2). Mix vectors are not exposed as a top-level response field
because they're a function of the distribution arrays which are
already there.

## API layer

### New endpoint family: `/api/v1/scope/averages/players/*`

```
GET /api/v1/scope/averages/players/batting/summary
    ?position_mix=opener_pct,3_pct,4_pct,5_pct,6_pct,7_pct,8_pct,9_pct,10_pct,11_pct
    &<FilterBarParams>
    &<AuxParams (series_type, team_class)>
    &drop=<axes>

GET /api/v1/scope/averages/players/bowling/summary
    ?over_mix=ov1_pct,ov2_pct,...,ov20_pct
    &<FilterBarParams>
    &<AuxParams>
    &drop=<axes>

GET /api/v1/scope/averages/players/fielding/summary
    ?is_keeper=0|1
    &<FilterBarParams>
    &<AuxParams>
    &drop=<axes>

GET /api/v1/scope/averages/players/keeping/summary
    ?<FilterBarParams>
    &<AuxParams>
    &drop=<axes>
```

Mix parameter format: comma-separated floats summing to 1.0 (with a
tolerance of ±0.001 for floating-point noise). Missing values default
to 0.0; trailing zeros may be omitted. Length must match the bucket
count (10 batting / 20 bowling). Server validates and returns 400 on
malformed input.

### Response shape — batting

```jsonc
{
  "cohort": {
    "match_dimension": "position_mix",
    "position_mix": [0.54, 0.38, 0.05, 0.03, 0, 0, 0, 0, 0, 0],
    "n_players": 412,
    "n_innings_total": 8917
  },
  "innings_batted":  { "value": 14.3,  "scope_avg": 14.3,  "delta_pct": 0, "direction": null, "sample_size": 8917 },
  "runs":            { "value": 412.7, ... },
  "average":         { "value": 28.7,  ..., "direction": "higher_better" },
  "strike_rate":     { "value": 131.4, ..., "direction": "higher_better" },
  "boundary_pct":    { "value": 18.2,  ..., "direction": "higher_better" },
  "dot_pct":         { "value": 35.1,  ..., "direction": "lower_better"  },
  "by_position": [
    { "bucket": 1,  "label": "Opener", "n_innings": 4521, "below_support": false,
      "runs": 482.1, "strike_rate": 138.7, "average": 31.2, ... },
    { "bucket": 2,  "label": "#3",     "n_innings": 3214, "below_support": false, ... },
    /* ... 10 entries total */
    { "bucket": 10, "label": "#11",    "n_innings":   12, "below_support": true,  ... }
  ]
}
```

`by_position` carries every bucket's metrics independently — drives
the renormalisation (frontend-visible: which buckets were excluded)
AND the next-spec drill-down ("at #3 specifically, Kohli vs cohort").

### Response shape — bowling

Same pattern with `over_mix` of length 20 and `by_over` of length 20.
Cohort metric per over: `economy`, `strike_rate`, `bowling_avg`,
`dot_pct`, `wickets_per_over`, etc.

### Response shape — fielding

```jsonc
{
  "cohort": {
    "match_dimension": "is_keeper",
    "is_keeper": 0,
    "n_fielders": 1247,
    "n_matches_total": 42891
  },
  "dismissals_per_match":  { "value": 0.45, "sample_size": 42891, "direction": "higher_better" },
  "catches_per_match":     { "value": 0.31, ... },
  "run_outs_per_match":    { "value": 0.14, ... },
  "by_dismissed_position": [
    { "bucket": 1,  "label": "Opener", "catches_per_match": 0.08, "sample_size": 4521, "below_support": false },
    /* ... 10 entries total */
    { "bucket": 10, "label": "#11",    "catches_per_match": 0.02, "sample_size":  187, "below_support": false }
  ]
}
```

`by_dismissed_position` is the data the **next spec** will use to:
1. Render the fielder's dismissed-position histogram (read from
   `/fielders/{id}/summary.dismissal_position_distribution`) overlaid
   against this cohort vector.
2. Compute impact-weighted "Kohli takes more top-order catches per
   match than an average outfielder" framings — client-side weighting
   applied to both the player's distribution and this cohort vector,
   producing a single delta.

### Why fielding isn't position-mix weighted (math note)

Position-weighting for batting/bowling works because per-bucket cohort
metrics have **intrinsically distinct meanings**: a #3 batter's SR is
not the same kind of number as a #11's SR (different conditions,
different deliveries, different overs of innings). Weighting by a
player's position-mix produces a comparable single rate.

For fielding, the per-position cohort sub-rates (catches at opener
position per match, catches at #11 position per match) are **sub-
components of one overall rate** — they sum to total catches/match.
Weighting them by a fielder's dismissal-position-mix produces a
dimensionally-confused number (fraction × rate ≠ rate). The dimensional
analysis is in the resolution log; the answer is:

- **Fielding cohort baseline**: direct catches/match (keeper-flag
  matched, no position weighting).
- **Position-of-dismissal data**: collected (in `playerscopestats_
  fielding_position`) and returned in `by_dismissed_position`, but
  consumed by the next spec's impact-weighted analyses, not by this
  spec's headline baseline.

### Migration: envelope-wrap the four player summary endpoints

`/batters/{id}/summary`, `/bowlers/{id}/summary`,
`/fielders/{id}/summary`, `/fielders/{id}/keeping/summary` move from
flat scalars to the envelope. Identity-bearing fields stay flat. Per-
metric direction comes from the extended `METRIC_DIRECTIONS` map.

**Backend folding** (Q2 resolution): the summary endpoint internally
composes its existing player-grain SQL **plus** an in-process call to
the matching scope-averages-players endpoint's SQL helper. Mix vector
derived server-side from the player's distribution. Envelope assembled
at response-serialization time. Result: 1 round trip per discipline-
band; same fetch count as today.

Frontend type fan-out: `BattingSummary` / `BowlingSummary` /
`FieldingSummary` / `KeepingSummary` in `frontend/src/types.ts` switch
their numeric fields from flat numbers to `MetricEnvelope`. Mirrors the
team-side migration.

### `METRIC_DIRECTIONS` audit

Most keys already exist on `api/metrics_metadata.py` (the team-side
spec was thorough). Audit each player-grain summary's numeric fields
against the map; add missing keys. Suspect additions:

- `bat_innings`, `bat_not_outs` (counts → null direction)
- `bat_50s`, `bat_100s` (counts → null)
- `bat_highest` (identity-adjacent — stays flat, not envelope-wrapped)
- `bowl_overs` (count → null)
- `bowl_best_figures` (identity-bearing — stays flat)
- `field_innings_kept`, `field_substitute_catches` (counts → null)
- `keep_byes`, `keep_byes_per_innings` (latter → `lower_better`)

The audit happens in the first commit (extending `metrics_metadata.py`)
before any endpoint migration.

## Sample support + renormalisation

Per-bucket sample-support thresholds gate whether a bucket contributes
to the convex combination.

### Batting (10 buckets, linear scale)

```
threshold(bucket) = 27 - 2 × bucket
```

| Bucket | Label | Min innings in cohort |
|---:|---|---:|
| 1  | Opener | 25 |
| 2  | #3     | 23 |
| 3  | #4     | 21 |
| 4  | #5     | 19 |
| 5  | #6     | 17 |
| 6  | #7     | 15 |
| 7  | #8     | 13 |
| 8  | #9     | 11 |
| 9  | #10    |  9 |
| 10 | #11    |  7 |

### Bowling (20 buckets, U-shape)

| Over | Min balls in cohort | Cohort character |
|---:|---:|---|
| 1, 2 | 60 | New-ball specialists |
| 3-6 | 50 | PP continuation |
| 7-15 | 30 | Middle — diverse, lots of part-timers |
| 16-19 | 50 | Death-finisher specialists |
| 20 | 60 | Final-over specialists |

### Fielding (10 buckets, linear scale — used by next-spec impact-weighted analyses, not by the headline baseline)

```
threshold(bucket) = 13 - bucket    -- 12, 11, 10, 9, ..., 3
```

| Bucket | Label | Min dismissals in cohort |
|---:|---|---:|
| 1  | Opener | 12 |
| 2  | #3     | 11 |
| 3  | #4     | 10 |
| 4  | #5     |  9 |
| 5  | #6     |  8 |
| 6  | #7     |  7 |
| 7  | #8     |  6 |
| 8  | #9     |  5 |
| 9  | #10    |  4 |
| 10 | #11    |  3 |

### Renormalisation rule

When a bucket falls below threshold:

1. Drop that bucket from the player's mix.
2. Renormalise remaining bucket weights to sum to 1.0.
3. Compute the convex combination over the renormalised mix.
4. The response's `by_<axis>` array marks the dropped bucket with
   `below_support: true`; the tooltip on the frontend lists which
   buckets were excluded.

When ALL buckets are below threshold → response `scope_avg = null`,
delta_pct = null. Frontend renders the cell as `—`.

## Frontend

### `PlayerSummaryRow` (`frontend/src/components/players/PlayerSummaryRow.tsx`)

Switch each stat cell from a flat number to the three-tier stack when
`scope_avg` is present. Reuse `MetricDelta` with `withScopeAvg={true}`,
adding a `label?: string` prop (defaults to `"avg"`; player-page
callers pass `label="base"`).

Tooltip on the `vs base N` line reads from the cohort metadata
(`cohort.n_players` etc. + the cohort's position-mix or over-mix or
is_keeper flag, formatted per the phrasing rule in §3.4).

### `getPlayerProfile` (`frontend/src/api.ts`)

Unchanged at 4 parallel summary calls per player (Q2: backend
folding). Each summary call returns the envelope-shape response with
`scope_avg` already populated. No extra round trips.

### `bucketLabel` helper

Single source of truth for batting bucket labels:
```ts
function battingBucketLabel(b: number): string {
  return ['Opener', '#3', '#4', '#5', '#6', '#7', '#8', '#9', '#10', '#11'][b - 1]
}
```

Bowling: `Over ${b}`. Fielding: `${b === 1 ? 'Keeper' : 'Outfielder'}`.

### URL state

Zero new search params. The baseline is implicit per discipline band;
the mix auto-derives from the response payload. Share links carry the
same scope they always did and the baseline reproduces.

## Tests

### Regression

New file: `tests/regression/scope-averages-players/urls.txt`.

3-5 URLs per endpoint covering: unfiltered, single-tournament,
single-season, mixed-filter, `drop=` activation. All `NEW` initially.

`tests/regression/batters/urls.txt`, `bowlers/urls.txt`,
`fielders/urls.txt`, `keeping/urls.txt` get the REG→NEW flip **in a
preceding commit** (commit-cadence rule) before the shape migration
lands.

### Integration

New: `tests/integration/player_compare_baseline.sh`. Browser-agent walk:

1. Load `/players?player=ba607b88&tournament=Indian+Premier+League`.
2. Verify Batting band renders: value (42.38) + baseline (~28.7) +
   delta (+47.7%).
3. Verify the baseline tooltip names the cohort with position-mix
   phrasing.
4. Add `compare=462411b3` (Bumrah). Verify each column's batting band
   has its own position-mix-derived baseline; Bumrah's mostly weighted
   on #10/#11 cohort.
5. Narrow scope to a season where Bumrah didn't bat — verify his
   batting band hides AND no baseline fetch is fired.
6. Set scope to a thin tournament — verify the cell renders `—` for
   the baseline when all buckets are below support, with appropriate
   tooltip.
7. Verify renormalisation behaviour: a player whose mix includes a
   below-support bucket sees the tooltip flag exclusion.

### Sanity tests (SQL ↔ API)

New file: `tests/sanity/test_player_scope_averages.py`. Per discipline:

1. For a known scope, verify endpoint response's `scope_avg` matches a
   hand-rolled SQL convex combination over `playerscopestats_*` child
   tables.
2. Pool conservation: `Σ player_innings_at_position_i = SUM(innings)`
   from `playerscopestats_position` for the same filter scope.
3. `drop=` invariant: response with `drop=filter_team,filter_opponent`
   equals response without those filters set in the first place.
4. Renormalisation invariant: if bucket B is below threshold, the
   response `by_<axis>[B].below_support = true` AND the headline
   `scope_avg` equals the convex combination over buckets where
   `below_support = false`, with renormalised weights.

### Match-dimension derivation tests

In `tests/sanity/test_player_compare_baseline.py`:

1. For Kohli on IPL all-time, the position-mix derived from his
   `playerscopestats_position` rows sums to ≈ 1.0 (within 0.001) and
   matches the histogram of his innings positions.
2. For Bumrah on IPL all-time, the over-mix is death-weighted (sum of
   ov16-ov20 shares > 0.5).
3. For Dhoni vs Kohli, the fielding `is_keeper` flag is 1 vs 0.

## Docs sync

Per `internal_docs/docs-sync.md`:

- `docs/api.md` — new sections for the 4 `/scope/averages/players/*`
  endpoints with curl + abbreviated response. Shape-change documentation
  for the 4 player summary endpoints (envelope migration).
- `docs/tab-structure.md` — note that `/players` summary cards now
  carry the inline-baseline visual treatment.
- `frontend/public/llms.txt` — add a glossary entry under "How
  CricsDB models cricket" for the convex-combination cohort baseline
  concept.
- `frontend/src/content/user-help.md` — 1-paragraph section under the
  Players tab on what the `~base N` line + delta chip mean and how the
  cohort is chosen.
- `internal_docs/codebase-tour.md` — note the new endpoints, child
  tables, populate scripts, and the backend-folding pattern.
- `internal_docs/design-decisions.md` — three entries:
  1. "Inline baselines on /players are convex combinations over
     bucket-mix vectors. Naive flat-pool baseline rejected because it
     mixes structurally-distinct cohorts." Cite 2026-05-19.
  2. "Fielding baseline is keeper-flag binary, not position-weighted.
     Position-weighting fielding fails dimensional analysis."
     Cite 2026-05-19.
  3. "`drop=` is per-endpoint structural plumbing for tautology-prone
     cohort surfaces (3a/4/6), not a user-facing toggle."
- `internal_docs/enhancements-roadmap.md` — add an entry; mark
  Surface 1 from `outlook-comparisons.md` as in-flight then shipped.
- `internal_docs/outlook-comparisons.md` — Surface 1 entry gets a
  "→ promoted to spec-player-compare-average.md" pointer; the
  cross-cutting `drop=` section gets a note that the plumbing landed
  here.
- `internal_docs/data-pipeline.md` — add the three new populate
  scripts to the diagram + auto-call section.
- `CLAUDE.md` "Cricket invariants" — codify the bucket definitions
  (opener = pos 1+2 merged; remaining individual; bowling per-over;
  fielding keeper-binary) so future endpoints don't accidentally
  reinvent.

## Rollout phases

Mirroring `spec-team-compare-average.md`'s phased approach. **9 commits
total.** Each runnable + green. No batching.

### Phase 1 — `METRIC_DIRECTIONS` extension + `drop=` plumbing (1 commit)

`api/metrics_metadata.py` gains the player-grain keys (audit per §5.7).
`FilterParams.build(drop=...)` accepts the new parameter; no endpoint
consumes it yet. Unit tests confirm `drop=` masking works correctly.
No user-facing change.

### Phase 2 — Child tables + distribution arrays on /summary (3 commits)

One commit per discipline. Each commit bundles three things so the
new data layer ships **with** its read-channel on the matching summary
endpoint — next-spec UI can prototype against a stable `/summary`
response while Phases 3+ are in flight:

- `playerscopestats_position` — schema, populate-full, populate-
  incremental, wired into `import_data.py` + `update_recent.py`.
  Sanity test: pool conservation against `playerscopestats`.
  PLUS: add `position_distribution[10]` array to
  `/batters/{id}/summary`. Pure additive shape change — no envelope
  migration yet, regression URLs unchanged.
- `playerscopestats_over` — same shape; adds `over_distribution[20]`
  to `/bowlers/{id}/summary`.
- `playerscopestats_fielding_position` — same shape, plus reuses
  `_derive_positions` for dismissed-batter lookups; adds
  `dismissal_position_distribution[10]` to `/fielders/{id}/summary`.

Deploy each with `bash deploy.sh --first` (DB schema change). The
~2.6M total new rows add ~150MB to the DB size — sub-1GB total.

### Phase 3 — Scope-averages-players endpoints (4 commits)

One commit each for batting / bowling / fielding / keeping. Each:

- Adds the endpoint to `api/routers/scope_averages.py`.
- Adds 3-5 regression URLs (NEW).
- Adds the sanity test verifying SQL ↔ API (convex combination, pool
  conservation, drop= invariant, renormalisation invariant).

Frontend types added, not yet consumed.

### Phase 4 — Envelope-migrate the four player summary endpoints (separate flip commits + 4 migration commits = 8 commits)

For each of the 4 summary endpoints:

1. **Flip commit** (precedes the migration): regression URLs for that
   endpoint flip REG → NEW. This is the commit-cadence requirement
   from CLAUDE.md, codified in `feedback_regression_before_shape.md`.
2. **Migration commit**: handler refactored — SQL helper extracted,
   scope-averages call composed in-process, envelope assembled at
   response serialization. Sanity test extended to verify envelope
   shape. Regression URLs flipped back to REG after the shape stabilises.

4 endpoints × 2 commits = 8 commits in this phase.

Frontend type migrated to `MetricEnvelope`-based discriminated union;
existing consumers updated for compile.

### Phase 5 — Frontend inline-baseline rendering (1 commit)

`PlayerSummaryRow` switches to the three-tier stack. `MetricDelta`
gains the `label` prop. Tooltip wiring (phrasing per §3.4).
`bucketLabel` helper. `tests/integration/player_compare_baseline.sh`
written and passes.

Single-player and compare layouts both ship in the same commit.

### Total commit count

1 (Phase 1) + 3 (Phase 2) + 4 (Phase 3) + 8 (Phase 4) + 1 (Phase 5) =
**17 commits**.

Note: Phase 4 is doubled (flip + migration per endpoint). If we batched
the flips into one commit and the migrations into one per endpoint,
that's 1 + 4 = 5 commits in Phase 4 → 14 commits total. The original
team-side spec batched flips this way. Decide at the time which reads
cleaner.

## Open questions

1. **Where exactly does `dismissal_position_distribution` come from
   on `/fielders/{id}/summary`?** Two paths:
   (a) Aggregate from `playerscopestats_fielding_position` at request
       time (canonical, slightly slower).
   (b) Cache it on `playerscopestats` itself as a JSON column (faster
       reads, denormalised twice).
   Recommend (a) — same pattern as the batting / bowling distributions
   read from their child tables. The aggregation is one indexed query.

2. **Should we cap the per-bucket `by_<axis>` sub-rates at the same
   sample-support threshold the convex combination uses?** I.e. if
   bucket B is below_support for the cohort, do we still return its
   sub-rate in `by_<axis>[B]`, or set those numbers to null too? The
   sub-rates are used by next-spec for impact-weighted analyses;
   silently noisy sub-rates could be misread.
   Recommend: return them but mark `below_support: true`. Frontend in
   the next-spec is responsible for honoring the flag.

3. **Renormalisation when MOST buckets are below_support.** If a
   player's mix has 90% weight on a single below-support bucket and
   the remaining 10% spreads over a couple of supported buckets, the
   renormalised baseline is computed entirely from those 10%. The
   result is technically defensible (it's the supported part of the
   cohort) but it's misleading the user about what they're seeing.
   Suggest a secondary gate: if the supported mix-weight summed
   < 0.30 of the original mix, render `—`. Otherwise compute. Bake
   into §6 if you confirm.

4. **Backend folding latency cost.** Each player summary endpoint now
   composes a scope-averages call internally. For unfiltered scopes
   the cohort aggregation might be slower (~100K rows scan-style).
   Worst-case envelope: should still be <500ms per call, but verify
   with a benchmark in Phase 3 against the local DB before Phase 5
   commits land.

5. ~~**Whether to expose `position_distribution` etc. on the existing
   `/batters/{id}/summary` even before Phase 4** so the next-spec UI
   can prototype against an in-progress backend.~~ **Resolved 2026-05-19**:
   distribution arrays ship in Phase 2 alongside their child table
   (one commit per discipline bundles schema + populate + the
   `/summary` field). Next-spec UI can prototype against a stable
   `/summary` response while Phases 3+ are in flight. Phase 4
   (separate distribution-array commit) is collapsed; total commit
   count drops 18 → 17.

## Follow-up specs (deferred — data infrastructure lands here)

Three pure-UI specs unblocked by this spec:

1. **`spec-batting-position-chart.md`** — position-distribution
   histogram on `/batting?player=X`. Reads
   `position_distribution` + cohort `by_position` from the summary
   endpoint family. Per-bucket Δ pills, palette per `colors.md`.
2. **`spec-bowling-over-chart.md`** — per-over distribution on
   `/bowling?player=X`. Reads `over_distribution` + `by_over`.
3. **`spec-fielding-impact.md`** — impact-weighted fielding analysis
   on `/fielding?player=X`. Reads `dismissal_position_distribution` +
   `by_dismissed_position`. Defines the impact-weight scheme (e.g.
   `opener × 1.5`, `tail × 0.5`) and renders both the histogram + the
   single impact-weighted score.

All three are zero-schema, zero-endpoint specs at follow-up time —
purely visualisation work over the data this spec ships.

## What's deliberately deferred (parking lot)

- **"+ Add average <role> in scope" slot** — `outlook-comparisons.md`
  §Surface 1 originally proposed this as the surface. Q7 redirects to
  inline rendering instead. Slot mode revisited if users ask.
- **Position switcher / mix override** — letting a user say "show me
  Kohli vs openers" instead of the auto-derived mix. v2 toggle.
- **Position-mix weighted FIELDING** — explored in this spec, set aside
  because the dimensional analysis doesn't work. The richer fielding
  framings (impact-weighted, per-position drill-down) live in the
  follow-up `spec-fielding-impact.md`.
- **Distribution panel baselines** — see
  `project_baseline_distributions.md`. Different math, different
  surface, separate ~10-15-commit spec.
- **Surfaces 2 / 3 / 4 / 5 / 6** from `outlook-comparisons.md`. Each
  consumes the same endpoint family + the `drop=` plumbing landed
  here.

## Resolution log — design session 2026-05-19

Captured for posterity since the session reframed several aspects of
the original `outlook-comparisons.md` proposal:

1. **"Footgun" reframing**: `outlook-comparisons.md` posed the
   `drop=`-axis question as a general user-facing "in scope" ambiguity.
   Reframed: `drop=` is per-endpoint structural plumbing for tautology-
   prone surfaces (3a/4/6). The user-facing default everywhere else is
   the venue/rivalry/season-scoped baseline (apples-to-apples).
2. **Continuous position-band → bucketed position-mix**: original Q1
   answer was "continuous"; revised after the Kohli case study to
   "convex combination over bucketed mix", because aggregations over
   `avg_batting_position` flatten career-era splits.
3. **Bucket count for batting**: from 5 (opener / top / middle / late
   / tail) to 10 (opener + #3 through #11 individual). Lumping #5+#6
   and #7+#8 was rejected as information-destroying; per-position
   keeps the granularity. Positions 1+2 stay merged because
   `_derive_positions` makes the split arbitrary (whoever took strike
   on ball 1).
4. **Bowling buckets**: from 3 phases → 20 individual overs.
5. **Schema shape**: from "60 new columns on `playerscopestats`" to
   three child tables. Same denormalisation, cleaner relational shape.
6. **Sample-support thresholds**: per-bucket linear scale for batting
   (25→7, step −2), U-shape for bowling (60-50-30-50-60), linear for
   fielding (12→3, step −1). Renormalisation drops below-support
   buckets and resmooths the remaining weights.
7. **Fielding cohort baseline**: position-weighted approach
   investigated, rejected on dimensional grounds. Headline baseline is
   binary keeper/outfielder; per-position-of-dismissed-batter data is
   collected and surfaced for the next-spec impact analyses.
8. **Visual identity**: `vs base N` (not `vs avg`) on player pages to
   distinguish the position-mix-weighted cohort from the pool-weighted
   team baseline.
