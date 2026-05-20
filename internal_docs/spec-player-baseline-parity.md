# Player Baseline Parity Spec

**Status:** Draft for review, 2026-05-20.
**Sibling specs:** `spec-player-compare-average.md` (Phase 1, shipped 2026-05-20 — three child tables + four cohort `/summary` endpoints + three-tier inline visual on `/players` + `/batting` + `/bowling` + `/fielding`), `spec-team-compare-average.md`, `spec-team-bucket-baseline.md`, `spec-team-compare-scoped-slots.md` (the reference model on the Teams side).

## 1. Context

The original player-compare spec (shipped 2026-05-20) wired up **lifetime cohort baselines** at the tile grain for the four player pages — every rate / percentage tile in the summary row now shows the three-tier visual against a position-mix (batting), over-mix (bowling), or keeper-binary (fielding) cohort, narrowing with every `FilterParams` axis.

The reference model for the next step is the **Teams** tab. Teams' scope-baseline surface is symmetric across three granularities:

| Granularity | Teams endpoint | Player endpoint |
|---|---|---|
| Lifetime aggregate | `/api/v1/scope/averages/batting/summary` (and bowling, fielding) | `/api/v1/scope/averages/players/batting/summary?position_mix=…` (and bowling, fielding, keeping) ✓ shipped |
| By season | `/api/v1/scope/averages/batting/by-season` (and bowling, fielding) | **missing** |
| By phase | `/api/v1/scope/averages/batting/by-phase` (and bowling, fielding) | **missing** |

Every Teams chart that renders a green forest reference line is backed by one of these endpoints, and every endpoint accepts the full `FilterParams + AuxParams` surface so the reference line narrows when the user clicks `filter_venue`, `toss_outcome`, `inning`, etc.

**The gap:** every chart on the four player pages renders the player's own bars (Runs by Season, Wickets by Season, Economy by Over, Dismissals by Season, …) with **no reference line**, because no cohort `by-season` / `by-phase` endpoint exists yet on the player side. This violates the [chip ↔ chart baseline symmetry](../CLAUDE.md#chip--chart-baseline-symmetry) rule that Teams already honours.

## 2. Goal

Extend the player-cohort baseline surface from `summary`-only to `summary + by-season + by-phase`, all accepting the same `FilterParams + AuxParams + mix` arguments as the existing `summary` endpoint. Wire each new endpoint into the corresponding chart on `/batting` / `/bowling` / `/fielding` so every player-side rate chart carries a forest-green reference line and every per-phase rate tile carries a base chip, mirroring the Teams pattern.

`/players` doesn't render time-series charts (it's profile-dense), so the spec adds work to the three deep-dive pages plus a chip-extension pass on `/players` that widens the cohort-chip coverage past the current handful. The Keeping sub-tab is explicitly **out of scope** — the keeping cohort baseline hasn't been designed yet (current `/players/keeping/summary` returns `cohort=null`).

## 2.5 Locked decisions (review 2026-05-20)

The six §6 design questions were resolved as follows. The rest of the spec assumes these.

| # | Decision | Implication |
|---|---|---|
| Q1 | **Strict position-mix cohort** on player by-season + by-phase charts (chip↔chart symmetry). | Six new cohort endpoints (§3.1) are required; using the team-side `/scope/averages/batting/by-season` as a substitute is rejected. |
| Q2 | **Per-season mix.** At each season, the cohort baseline is computed under the player's actual position-mix for that season's innings (not career mix). | By-season endpoints take `person_id` (not a caller-supplied mix vector); the endpoint derives per-season mix server-side by joining `playerscopestats_position` on `(person_id, scope_key)`. By-phase endpoints take `person_id` similarly. Lifetime `/summary` endpoints keep their existing `position_mix=…` vector input — caller still supplies for compare-grid use. |
| Q3 | **Precompute via new child tables.** Add `playerscopestats_batting_phase` and `playerscopestats_fielding_phase` populates parallel to the existing `_position` / `_over` / `_fielding_position` triple. Bowling by-phase derives directly from `playerscopestats_over` (overs bucket → phase). | New tables + new populate scripts + new sanity tests, all wired into `import_data.py` (full) and `update_recent.py` (incremental) following the touched-scope-recompute pattern already in use. |
| Q4 | **Render a gap (no segment) for null-baseline seasons AND a tooltip on hover** explaining why ("cohort sample too small at this season — bucket X had only N innings, threshold M"). | `LineChart`'s `referenceData` must handle null entries by breaking the line; a hoverable invisible region or marker at the gap surfaces the tooltip. |
| Q5 | **Reference-line label is `base`**, matching the existing player-tile chip wording (`MetricDelta.tsx:32` already passes `label='base'` on the player side; team-side stays `avg`). The tooltip carries the full description of how the base is computed — and per the user's note, **the tile chip subtitle gets the same tooltip** so the explanation is one-source. | `MetricDelta` and the LineChart's `referenceData` legend both render `base`; a shared `<BaselineTooltip>` component renders the position-mix vector + sample sizes + threshold semantics on hover. |
| Q6 | **Widen `/players` chip coverage past the original three Fielding-band tiles.** Add cohort chips to additional rate-style tiles on the Batting band (Boundaries/Innings, Sixes/Innings, Fours/Innings, plus the milestone-grade per-innings rates 30s/Innings, 50s/Innings, 100s/Innings) and the Bowling band (Wickets/Innings, Maidens/Innings) — wherever the underlying `playerscopestats*` child table already has the numerator data and the denominator is innings-in-scope. | The `/players/{batting,bowling,fielding}/summary` cohort response shape grows new envelope fields (`boundaries_per_innings`, `sixes_per_innings`, `fours_per_innings`, `thirties_per_innings`, `fifties_per_innings`, `hundreds_per_innings`, `wickets_per_innings`, `maidens_per_innings`). The corresponding `/{batters,bowlers}/{id}/summary` player endpoints must also return the same fields under the existing envelope wrapper so `MetricDelta` has both sides of the comparison. |

## 3. API surface

### 3.1. New child tables (Q3 Option A — precompute)

Two new playerscopestats child tables, populated parallel to the existing trio (`_position` / `_over` / `_fielding_position`). Bowling by-phase derives directly from `playerscopestats_over` (cheap GROUP BY mapping over_number → phase) — no new table.

#### 3.1.1. `playerscopestats_batting_phase`

| Column | Type | Notes |
|---|---|---|
| `person_id` | TEXT | FK person(id) |
| `scope_key` | TEXT | FK playerscopestats(scope_key) — encodes tournament/season/gender/team_type |
| `phase_bucket` | INTEGER | 1=powerplay (overs 1-6), 2=middle (7-15), 3=death (16-20) |
| `innings_in_phase` | INTEGER | innings where the player faced ≥1 ball in this phase |
| `balls_in_phase` | INTEGER | legal balls faced in this phase |
| `runs_in_phase` | INTEGER | runs scored in this phase |
| `dots_in_phase` | INTEGER | dot balls faced in this phase |
| `fours_in_phase` | INTEGER | 4s hit in this phase |
| `sixes_in_phase` | INTEGER | 6s hit in this phase |
| `boundaries_in_phase` | INTEGER | fours + sixes |
| `dismissals_in_phase` | INTEGER | times out in this phase |
| PRIMARY KEY | `(person_id, scope_key, phase_bucket)` | – |

**Size estimate:** ~150K rows (~50K active (person, scope_key) cells × ≤3 phases the player touched). Each cell sparse on phases the player didn't bat in.

**Populate:** `scripts/populate_playerscopestats_batting_phase.py` with `populate_full(db)` (one-shot during `import_data.py`) + `populate_incremental(db, new_match_ids)` (touched-scope-recompute, per the existing convention). Reuses `api/innings_positions.py::derive_positions` outputs already threaded into the position populate — extends the per-innings ball-stream walk to credit balls to phase buckets.

#### 3.1.2. `playerscopestats_fielding_phase`

| Column | Type | Notes |
|---|---|---|
| `person_id` | TEXT | FK person(id) |
| `scope_key` | TEXT | FK playerscopestats(scope_key) |
| `phase_bucket` | INTEGER | same 1/2/3 mapping |
| `innings_in_phase_credited` | INTEGER | matches where the player was on the field in this phase (proxy: matchplayer + matches with ≥1 delivery in the phase) |
| `catches_in_phase` | INTEGER | `kind IN ('caught','caught_and_bowled')` AND `is_substitute=0` in this phase |
| `run_outs_in_phase` | INTEGER | `kind='run_out' AND is_substitute=0` in this phase |
| `stumpings_in_phase` | INTEGER | `kind='stumped' AND is_substitute=0` in this phase |
| `dismissals_in_phase` | INTEGER | catches + run_outs + stumpings |
| PRIMARY KEY | `(person_id, scope_key, phase_bucket)` | – |

**Size estimate:** ~120K rows (~40K active (person, scope_key) fielder cells × ≤3 phases credited).

**Convention 3 applies:** `catches_in_phase` includes caught_and_bowled (`kind IN ('caught','caught_and_bowled')`). Substitute exclusion follows the existing fielding-distribution rule (CLAUDE.md "Substitute fielders — INCLUDED in /leaders, EXCLUDED in /distribution").

**Populate:** `scripts/populate_playerscopestats_fielding_phase.py`. Same `populate_full` / `populate_incremental` shape. Phase is derived from each fieldingcredit's `delivery.over_number`.

#### 3.1.3. Wire-in to existing pipeline

`import_data.py` end-of-import block grows two more `populate_full()` calls (after the existing three). `update_recent.py` similarly grows two more `populate_incremental()` calls in the incremental block. Both must follow the same touched-scope recompute strategy as `_position` / `_over` / `_fielding_position` (identify scope_keys touched by the new matches, recompute the entire (person, scope_key, phase) cells from scratch over those scopes, delete + reinsert).

### 3.2. New cohort endpoints

Six new endpoints. The by-season variants take `person_id` (not a caller-supplied mix vector) so they can derive **per-season** mix server-side (Q2 decision). The by-phase variants also take `person_id` for symmetry. The existing `/summary` endpoints stay as-is, still accepting `position_mix=…` / `over_mix=…` / `is_keeper=…` directly for the compare-grid use cases (where there's no `person_id` — averaged team or hypothetical-cohort).

| Endpoint | Identity arg | Returns |
|---|---|---|
| `GET /api/v1/scope/averages/players/batting/by-season` | `person_id` (required) | `{ by_season: [{ season, total_runs.scope_avg, run_rate.scope_avg, strike_rate.scope_avg, boundary_pct.scope_avg, dot_pct.scope_avg, balls_per_four.scope_avg, balls_per_boundary.scope_avg, sixes_per_innings.scope_avg, fours_per_innings.scope_avg, boundaries_per_innings.scope_avg, mix: [10-element position-mix used at this season], n_players, n_innings }, …] }`. `season` rows where the per-season cohort sample fails any bucket threshold return `scope_avg=null` on every metric. |
| `GET /api/v1/scope/averages/players/bowling/by-season` | `person_id` | `{ by_season: [{ season, wickets.scope_avg, economy.scope_avg, strike_rate.scope_avg, bowling_avg.scope_avg, dot_pct.scope_avg, balls_per_boundary.scope_avg, wickets_per_innings.scope_avg, maidens_per_innings.scope_avg, mix: [20-element over-mix], n_players, n_innings }, …] }` |
| `GET /api/v1/scope/averages/players/fielding/by-season` | `person_id` | `{ by_season: [{ season, dismissals_per_match.scope_avg, catches_per_match.scope_avg, run_outs_per_match.scope_avg, stumpings_per_match.scope_avg, is_keeper, n_players, n_matches }, …] }` |
| `GET /api/v1/scope/averages/players/batting/by-phase` | `person_id` | `{ by_phase: [{ phase: 'powerplay'\|'middle'\|'death', strike_rate.scope_avg, dot_pct.scope_avg, balls_per_four.scope_avg, sixes_per_innings.scope_avg, runs_per_innings_in_phase.scope_avg, mix: [10-element], n_players, n_innings }, …] }`. Backed by `playerscopestats_batting_phase`. |
| `GET /api/v1/scope/averages/players/bowling/by-phase` | `person_id` | `{ by_phase: [{ phase, economy.scope_avg, strike_rate.scope_avg, dot_pct.scope_avg, wickets_per_innings_in_phase.scope_avg, mix: [20-element], n_players, n_innings }, …] }`. Derived from `playerscopestats_over` via GROUP BY phase mapping (no new table). |
| `GET /api/v1/scope/averages/players/fielding/by-phase` | `person_id` | `{ by_phase: [{ phase, dismissals_per_match.scope_avg, catches_per_match.scope_avg, run_outs_per_match.scope_avg, is_keeper, n_players, n_matches }, …] }`. Backed by `playerscopestats_fielding_phase`. |

**All six MUST accept the full `FilterParams + AuxParams` Depends-pair** — same surface as the existing `/players/batting/summary?position_mix=…` (`scope_averages.py:1869`). Every FilterBar axis (`gender`, `team_type`, `tournament`, `filter_venue`, `filter_team`, `filter_opponent`, `team_class`, `series_type`, `season_from`, `season_to`) plus every aux (`toss_outcome`, `inning`, `result`, `batting_position`, …) narrows the cohort baseline at every granularity. The reference line on the chart tracks the FilterBar without an extra prop, identical to Teams.

The `drop=` axis-masking arg carries over verbatim from `compute_players_batting_cohort` (`scope_averages.py:1881-1908`).

### 3.3. Existing endpoint response-shape extensions (Q6)

To back the additional `/players` band chips, four existing endpoints grow new envelope fields. None of these are new endpoints — just response-shape additions.

#### 3.3.1. `/api/v1/batters/{id}/summary`

Add envelope-wrapped fields:
- `boundaries_per_innings` — boundaries / innings_total (existing volume / existing denominator)
- `sixes_per_innings`
- `fours_per_innings`
- `thirties_per_innings` — count of innings with 30 ≤ runs < 50
- `fifties_per_innings` — 50 ≤ runs < 100
- `hundreds_per_innings` — runs ≥ 100

Each one carries `value + scope_avg + delta_pct + direction + sample_size`. Numerators already in the response (volume fields); denominator is `n_innings_total` already in `MetricEnvelope.sample_size`.

#### 3.3.2. `/api/v1/scope/averages/players/batting/summary`

Mirror the same six new envelope fields under the cohort surface. Derivation joins on `playerscopestats_position` aggregates (boundaries totals are already in the table; milestone counts may need a new aggregate column on `playerscopestats` — see §3.3.5).

#### 3.3.3. `/api/v1/bowlers/{id}/summary`

Add envelope-wrapped fields:
- `wickets_per_innings`
- `maidens_per_innings` (numerator: maiden-over count; existing volume field)

#### 3.3.4. `/api/v1/scope/averages/players/bowling/summary`

Mirror under the cohort surface. `wickets_per_innings` derives from `playerscopestats_over.wickets` summed across over-buckets / `playerscopestats.n_innings`. `maidens_per_innings` needs a `maidens` column on `playerscopestats_over` if not already present — verify; add if missing.

#### 3.3.5. Schema additions to existing tables (if missing)

- `playerscopestats` may need: `thirties INTEGER`, `fifties INTEGER`, `hundreds INTEGER` columns to back milestone-per-innings derivations. Check current schema; if absent, add via the populate script's CREATE TABLE block and backfill via `populate_full` (one-shot during `import_data.py`).
- `playerscopestats_over` may need: `maidens INTEGER` for maiden-overs-per-innings derivation. Check; add if absent.

### 3.4. Endpoint behaviour at thresholds

The sliding-scale cliff thresholds from `spec-player-compare-average.md` §6 carry over: if any bucket the player has non-zero mix-weight on falls below its per-bucket sample minimum, the response field's `scope_avg` is null. At by-season + by-phase granularity, per-bucket samples shrink so many cells null out for narrow scopes. The chart MUST render those cells with no reference-line segment (Q4: gap + tooltip on hover explaining why); the tile chip subtitle MUST render with no chip and a tooltip "cohort sample below threshold at this granularity."

## 4. Per-page inventory + proposed baselines

Reference format: every chart and every tile gets a row. **bl now** = baseline shipped today; **bl proposed** = what this spec adds; **source** = which cohort endpoint backs the proposed baseline.

### 4.1. `/players` (single-player profile — no sub-tabs)

`PlayerSummaryRow.tsx` renders three discipline bands plus an optional Keeping band when `innings_kept > 0`. The lifetime cohort chip is already on the headline rate tiles; this spec adds chips to several remaining tiles so the at-a-glance view carries the same baseline framing as the deep-dive pages.

| Band | Tile | file:line | Stat type | bl now | bl proposed | Source |
|---|---|---|---|---|---|---|
| Batting | Matches | `PlayerSummaryRow.tsx:258` | volume | – | – | none (volume) |
| Batting | Innings | `:259` | volume | – | – | none |
| Batting | Runs | `:260` | volume | – | – | none |
| Batting | Average | `:261-263` | rate | ✓ position-mix | ✓ keep | – |
| Batting | Strike Rate | `:265-267` | rate | ✓ position-mix | ✓ keep | – |
| Batting | Boundaries | `:279` | volume | – | – | none |
| Batting | B/Four | `:280-282` | rate | ✓ position-mix | ✓ keep | – |
| Batting | B/Boundary | `:284-286` | rate | ✓ position-mix | ✓ keep | – |
| Batting | Dot % | `:288-290` | rate | ✓ position-mix | ✓ keep | – |
| Batting | 30s/50s/100s | `:292` | volume | – | – | none |
| Bowling | Matches/Innings/Wickets/Overs/Best | `:237-239,:258,:263` | volume/identity | – | – | none |
| Bowling | Average | `:240-242` | rate | ✓ over-mix | ✓ keep | – |
| Bowling | Economy | `:244-246` | rate | ✓ over-mix | ✓ keep | – |
| Bowling | Strike Rate | `:259-261` | rate | ✓ over-mix | ✓ keep | – |
| Bowling | Dot % | `:264-266` | rate | ✓ over-mix | ✓ keep | – |
| Bowling | B/Boundary | `:268-270` | rate | ✓ over-mix | ✓ keep | – |
| Fielding | Catches | `:279` | volume | – | – | none |
| Fielding | Stumpings | `:280` | volume | – | – | none |
| Fielding | Run Outs | `:281` | volume | – | – | none |
| Fielding | Total | `:282` | volume | – | – | none |
| Fielding | Matches | `:283` | volume | – | – | none |
| Fielding | Dis/Match | `:284-288` | rate | ✓ keeper-binary | ✓ keep | – |
| Fielding | Catches/Match | – | rate (derived) | – | **ADD chip** | `/players/fielding/summary` (Q6) |
| Fielding | Run-Outs/Match | – | rate (derived) | – | **ADD chip** | same |
| Fielding | Stumpings/Match | – | rate (derived, keeper-relevant) | – | **ADD chip** | same |
| **Batting (extension — Q6 (ii))** | Boundaries/Innings | new tile | rate (derived) | – | **ADD tile + chip** | `/players/batting/summary` (Q6 §3.3.2) |
| Batting | Sixes/Innings | new tile | rate (derived) | – | **ADD tile + chip** | same |
| Batting | Fours/Innings | new tile | rate (derived) | – | **ADD tile + chip** | same |
| Batting | 30s/Innings | new tile (or replace milestone count) | rate (derived) | – | **ADD chip** | same |
| Batting | 50s/Innings | new tile | rate (derived) | – | **ADD chip** | same |
| Batting | 100s/Innings | new tile | rate (derived) | – | **ADD chip** | same |
| **Bowling (extension — Q6 (ii))** | Wickets/Innings | new tile | rate (derived) | – | **ADD tile + chip** | `/players/bowling/summary` (Q6 §3.3.4) |
| Bowling | Maidens/Innings | new tile | rate (derived) | – | **ADD tile + chip** | same |
| Keeping | Stumpings/Keep Catches/Byes Conceded/Innings Kept | `:423-427` | volume | – | – | none (no keeping cohort yet) |

**Records summary** (`PlayerRecordsSummary.tsx`) — no baselines (identity records). No change.

### 4.2. `/batting?player=X` — 8 sub-tabs

#### Shared (above tabs)

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Stat row 1 (5 tiles) | `Batting.tsx:257-269` | Matches · Innings · Runs · **Average** · **Strike Rate** | rate tiles ✓ position-mix | keep | – |
| Stat row 2 (5 tiles) | `:278-293` | Boundaries · **B/Four** · **B/Boundary** · **Dot %** · Milestones | rate tiles ✓ position-mix | keep | – |
| Distribution panel — Runs sparkline | `BatterDistributionPanel.tsx` per-innings runs scrollable bar | dual ref (scope-mean black + gender-global gray) | ✓ shipped 2026-05-20 | keep | – |
| Distribution panel — SR sparkline | per-innings SR | dual ref | ✓ shipped | keep | – |
| Distribution panel — RunsHistogram / SRHistogram | binned distribution of innings | – | – | none (descriptive, not comparative) |
| Distribution panel — StatStrip (Mean/Median/Std + milestone chips) | – | – | – | none |
| Distribution panel — FormDeltaLine | rolling-N vs scope lifetime | ✓ oxblood form delta | ✓ keep | – |

#### Tab: **By Season**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Runs by Season | `Batting.tsx:313-315` | bars, height = total runs per season | – | **ADD LineChart referenceData overlay (forest green)**, per chip↔chart symmetry | new `/players/batting/by-season?position_mix=…` returning `total_runs.scope_avg` per season |
| BarChart — Strike Rate by Season | `:316-319` | bars, height = SR per season, phase-coloured | – | **ADD referenceData overlay (forest green)** | new endpoint, `strike_rate.scope_avg` per season |

#### Tab: **By Over**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Strike Rate by Over (1–20) | `:338-346` | bars per over, height = SR, phase-coloured | – | **ADD referenceData overlay** — per-over cohort SR, derivable directly from `playerscopestats_position` aggregates at the population-mean position (or omit and use `over_mix=cohort-uniform` if that's the right framing) | new sub-endpoint or in-process derivation from `playerscopestats_over` aggregated under `position_mix=uniform` |

#### Tab: **By Phase**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Phase blocks: PPly / Middle / Death — 6 tiles each (Runs, Balls, SR, Dots, 4s, 6s) | `:356-370` | per-phase player aggregates | – | **ADD chip on SR, Dots, B/4** per phase | new `/players/batting/by-phase?position_mix=…` returning per-phase `strike_rate.scope_avg`, `dot_pct.scope_avg`, `balls_per_four.scope_avg` |
| Phase blocks — Runs, Balls, 4s, 6s | – | volume | – | – | none |

#### Tab: **vs Bowlers**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| ScatterChart — SR vs Avg (per bowler) | `:435-448` | dot per bowler, x=SR, y=Avg, size=balls | – | – | none (matchup is inherently paired; no singleton cohort baseline is meaningful) |
| Bowler matchups table | `:450-457` | transactional rows | – | – | none |

#### Tab: **Dismissals**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| DonutChart — Dismissals by Kind | `:469-472` | proportional pie | – | – | none (proportional, not rate) |
| BarChart — Dismissals by Over | `:473-478` | dismissal count per over | – | – | none (volume per over too granular) |

#### Tab: **Inter-Wicket**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| LineChart — SR by Wickets Down | `:489-493` | x=wickets lost, y=SR | – | – | none (no wicket-state cohort exists) |
| BarChart — Runs by Wickets Down | `:494-498` | – | – | – | none |

#### Tab: **Innings List**

Transactional table. No baselines.

#### Tab: **Records**

Identity records. No baselines.

### 4.3. `/bowling?player=X` — 7 sub-tabs

#### Shared (above tabs)

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Stat row 1 (5 tiles) | `Bowling.tsx:236-248` | Matches · Innings · Wickets · **Average** · **Economy** | rate tiles ✓ over-mix | keep | – |
| Stat row 2 (5 tiles) | `:257-272` | Overs · **Strike Rate** · Best · **Dot %** · **B/Boundary** | rate tiles ✓ over-mix | keep | – |
| Distribution panel — Wickets / Economy / Runs-Conceded sparklines | `BowlerDistributionPanel.tsx` | dual ref (scope-mean + gender-global) | ✓ shipped | keep | – |
| Distribution panel — FormDeltaLine | – | ✓ oxblood form delta | keep | – |

#### Tab: **By Season**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Wickets by Season | `Bowling.tsx:292-294` | bars, height = wickets per season | – | **ADD referenceData overlay** | new `/players/bowling/by-season?over_mix=…` returning `wickets.scope_avg` per season (renormalised to per-match for chart symmetry) |
| BarChart — Strike Rate by Season | `:295-298` | bars, height = SR per season | – | **ADD referenceData overlay** | new endpoint, `strike_rate.scope_avg` per season |

#### Tab: **By Over**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Economy by Over | `:317-326` | bars per over (1–20), height = economy, phase-coloured | – | **ADD referenceData overlay** — per-over cohort economy, derivable directly from `playerscopestats_over` | new sub-endpoint or in-process derivation, naturally per-over since the child table is already keyed on over_number |

#### Tab: **By Phase**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Phase blocks: PPly (with 1-3 / 4-6 nested) / Middle / Death — 6 tiles each (Balls, Runs, Wickets, Economy, SR, Dots) | `:334-371` | per-phase player aggregates | – | **ADD chip on Economy, SR, Dots** per phase | new `/players/bowling/by-phase?over_mix=…` returning per-phase `economy.scope_avg`, `strike_rate.scope_avg`, `dot_pct.scope_avg`. Bowling phase rollups are clean GROUP BYs on `playerscopestats_over.over_number` → no new table |
| Phase blocks — Balls, Runs, Wickets | – | volume | – | – | none |

#### Tab: **vs Batters**

Scatter + matchup table — no baselines (paired matchup).

#### Tab: **Wickets**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| DonutChart — Wicket Types | `:473-476` | proportional pie | – | – | none |
| BarChart — Wickets by Phase | `:477-481` | wicket count per phase | – | – | none (volume, not rate) |

#### Tab: **Innings List** / **Records**

Transactional / identity. No baselines.

### 4.4. `/fielding?player=X` — 7 base tabs + Keeping (conditional)

#### Shared (above tabs)

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Stat row (6 tiles) | `Fielding.tsx:278-289` | Catches · Stumpings · Run Outs · Total · Matches · **Dis/Match** | rate tile ✓ keeper-binary | keep — **plus ADD chips on Catches/Match, Run-Outs/Match, Stumpings/Match** | `/players/fielding/summary?is_keeper=…` (already returns the derivation; UI just needs new tiles) |
| Distribution panel — Catches sparkline | `FielderDistributionPanel.tsx:237-242` | per-match catches | scope-mean only (gender-global hardcoded to 1) | **UPGRADE** — add real gender-global reference matching batting/bowling pattern | extend `globalBaselines.ts` with `FIELDING_GLOBAL_*` |
| Distribution panel — Run-Outs sparkline | same | per-match run-outs | scope-mean only | **UPGRADE** — add real gender-global reference | same |
| Distribution panel — Stumpings sparkline | same | per-match stumpings | dual ref (scope-mean + lifetime) | keep | – |
| FormDeltaLine | `:286` | – | ✓ oxblood form delta | keep | – |

#### Tab: **By Season**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Dismissals by Season | `Fielding.tsx:315-317` | bars, height = total dismissals (catches + stumpings + run-outs) per season | – | **ADD referenceData overlay** | new `/players/fielding/by-season?is_keeper=…` returning `dismissals_per_match.scope_avg` per season |

#### Tab: **By Over**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| BarChart — Dismissals by Over | `:335-343` | bars per over, height = dismissals, phase-coloured | – | **ADD referenceData overlay** (low priority — fielding by-over data is sparse) | derivation from `playerscopestats_fielding_position` (currently position-keyed not over-keyed — may need new child table or `delivery` live join) |

#### Tab: **By Phase**

| Element | file:line | Description | bl now | bl proposed | Source |
|---|---|---|---|---|---|
| Phase blocks: PPly / Middle / Death — 5 tiles each (Catches, Stumpings, Run Outs, C&B, Total) | `:352-366` | per-phase player aggregates | – | **ADD chip on Total/Match per phase** | new `/players/fielding/by-phase?is_keeper=…`. Note: `playerscopestats_fielding_position` is position-keyed not phase-keyed; phase rollup needs either a new child table or live derivation against `delivery` join `fieldingcredit` |

#### Tab: **Dismissal Types**

DonutChart proportional. No baseline.

#### Tab: **Victims** / **Innings List** / **Records**

Transactional / identity. No baselines.

#### Tab: **Keeping** (conditional)

Out of scope. Current `/players/keeping/summary` returns `cohort=null`. Defer until a keeping cohort baseline is designed (separate spec).

## 5. UI plumbing

The Teams side already implements the pattern this spec adapts. Reference reading:

- `frontend/src/pages/Teams.tsx:678` — `scopeBaseline = useFetch<{ by_season: ScopeBattingSeason[] }>` of `/scope/averages/batting/by-season?<FilterParams>`.
- `Teams.tsx:826` — `<LineChart … referenceData={scopeBaseline.data?.by_season} />`.
- `LineChart`'s `referenceData` prop auto-derives the legend label via `abbreviateScope(filters, { discipline }) + " avg"` so the label tracks the FilterBar without an explicit prop.
- `MetricDelta` chip uses `MetricEnvelope.scope_avg` directly off the existing `/summary` response — no new fetch needed.

Per the locked decisions: `LineChart`'s `referenceData` legend label is `base` (not `avg`) on player pages — `MetricDelta.tsx:32` already passes `label='base'` for player-side tile chips; the LineChart legend resolver gets a parallel branch (`discipline.startsWith('player_')` or equivalent → suffix `base` not `avg`).

```tsx
// Batting.tsx — sketch
const scopeBaseline = useFetch<{ by_season: ScopePlayerBattingSeason[] } | null>(
  () => playerId && activeTab === 'By Season'
    ? getScopePlayersBattingBySeason(playerId, filters, aux)  // person_id is the identity arg (Q2)
    : Promise.resolve(null),
  [...filterDeps, activeTab],
)
// then:
<LineChart
  data={season.by_season}
  referenceData={scopeBaseline.data?.by_season}
  referenceKey="run_rate"
  referenceLabel="base"
/>
```

### 5.1. `<BaselineTooltip>` — shared component (Q5)

Both the tile chip subtitle and the chart reference-line legend get the same hover tooltip explaining what `base` means at the current scope. The tooltip body renders:

- the position-mix vector (or over-mix / is_keeper for bowling/fielding) used for the cohort at this granularity
- the `n_players` count and `n_innings` (or `n_matches`) drawn from
- the per-bucket sample minimums (cliff threshold) and which buckets currently meet them — when any failed, surface the failing bucket
- a one-line explanation: "Position-mix cohort baseline — average performance of players who batted in similar positions at this scope."

`<BaselineTooltip>` is added as a shared component under `frontend/src/components/baseline/BaselineTooltip.tsx`. Both `MetricDelta`'s subtitle render and `LineChart`'s reference-line hover render call it with a `BaselineMeta` payload returned in the envelope (each `scope_avg`-bearing field gains a sibling `scope_avg_meta: BaselineMeta` carrying the mix / sample counts / threshold-detail).

### 5.2. Chart-type gotchas

1. **`scopeBaseline` follows EVERY scope axis** — naming is `scopeBaseline`, not `tournamentBaseline` (CLAUDE.md "Chip ↔ chart baseline symmetry" rule). The fetch deps must include every FilterBar dep so the line moves when the user clicks `filter_venue` / opponent / inning, identical to how the chip moves.
2. **`BarChart` doesn't currently accept `referenceData`** — only `LineChart` does. Switch the player by-season charts from `BarChart` to `LineChart`; keeps the chart-type convention symmetric with Teams. Verify the visual still reads well with one mark per season.
3. **Null-baseline gaps (Q4).** `LineChart` MUST drop segments where `referenceData[i][key] === null` (no interpolation). An invisible hover region at the gap surfaces a `<BaselineTooltip>` carrying the "sample too small" message + the specific failing bucket(s).

## 6. Tests

The new tables and endpoints get sanity tests (Python, SQL-anchored); the new endpoints get regression tests (URL-diff anchored); the new chips and chart overlays get integration tests (DOM-anchored). Three layers per CLAUDE.md "Integration tests anchor against `/summary`'s scope_avg" + "Tests must cover EVERY call site of a shared abstraction."

### 6.1. Sanity tests (Python)

New under `tests/sanity/`:

- `test_playerscopestats_batting_phase.py` — for each (person, scope_key) in the parent `playerscopestats`, the sum of `playerscopestats_batting_phase` rows across the 3 phase buckets equals the parent's total counts (pool conservation, parallel to `test_playerscopestats_position.py`). Also asserts: phase_bucket ∈ {1,2,3}, no orphan rows (every scope_key in the child table also exists in the parent).
- `test_playerscopestats_fielding_phase.py` — analogous pool conservation against `playerscopestats_fielding_position` (the existing fielding parent). Also asserts the Convention-3 catches-include-cb predicate held at populate.
- `test_player_baseline_by_season.py` — for each new `/players/{batting,bowling,fielding}/by-season` endpoint:
  - Asserts the per-season cohort baseline at season=`S` matches an SQL-derived reference computed from the appropriate child table at that season (joined under the player's actual per-season mix).
  - Asserts threshold-cliff semantics: at a scope where a bucket the player touches has fewer than the threshold sample size, the season's `scope_avg` is null on every metric (not partial).
  - Asserts FilterBar-axis responsiveness: setting `filter_venue=Wankhede` changes the cohort baseline vs no narrowing (basic non-tautology check).
- `test_player_baseline_by_phase.py` — same trio of assertions for the `/by-phase` endpoints, against the new (or derived) phase child tables.
- `test_q6_extension_envelopes.py` — asserts the new per-innings rate fields on `/batters/{id}/summary` and `/bowlers/{id}/summary` match SQL-derived references, and their cohort sibling on `/scope/averages/players/*/summary` matches SQL-derived references from the relevant playerscopestats child table.

### 6.2. Regression tests (URL-diff)

New URLs under `tests/regression/player-baseline-parity/urls.txt`:

- One URL per new endpoint × 3 representative scope shapes: (a) unconstrained (e.g. `gender=male&team_type=club`); (b) tournament-narrowed (`tournament=IPL&season_from=2016&season_to=2016` — closed historical scope per the stable-scope feedback memory); (c) aux-narrowed (`tournament=IPL&season=…&filter_venue=Wankhede&toss_outcome=won`).
- The Q6 envelope-extension responses on `/batters/<id>/summary`, `/bowlers/<id>/summary`, `/scope/averages/players/{batting,bowling,fielding}/summary` at the same three scope shapes.
- 18 endpoint × 3 scope = ~60 new captured payloads.

Follow the CLAUDE.md REG→NEW flip-order convention: the flip lands in a commit ahead of the shape change; the NEW capture lands in the commit that introduces the new fields/endpoints. The flip is in a separate preceding commit so HEAD carries the NEW tag (feedback memory `feedback_regression_before_shape`).

### 6.3. Integration tests (DOM-anchored)

New under `tests/integration/`:

- `player_baseline_chip_extensions.sh` — for each new tile chip (Q6 extensions on /players band + the existing /batting /bowling /fielding chip surface), use `agent-browser` to load the URL, query `/summary` for the expected `scope_avg`, assert the rendered chip subtitle contains `base <expected>` and the `MetricDelta` direction arrow matches the sign of `delta_pct`. SQL-anchored expecteds, per CLAUDE.md "integration tests must self-anchor against SQL" — but anchor against `/summary` (not raw SQL) since the dual-query is already covered by sanity tests.
- `player_baseline_chart_overlays.sh` — for each by-season LineChart on /batting + /bowling + /fielding:
  - Load page with a stable historical scope (e.g. `?player=…&tournament=IPL&season_from=2016&season_to=2018`).
  - Query `/scope/averages/players/{batting,bowling,fielding}/by-season?person_id=…&<scope>` and assert: rendered SVG reference line has same number of segments as non-null seasons in the API response; bars have same number as non-null seasons in player's own response; legend text contains "base".
  - Click a FilterBar narrowing (e.g. `filter_venue=Wankhede`), wait for refetch, re-query the cohort endpoint, re-assert the reference line shifted accordingly.
  - At a scope where the threshold-cliff nulls some seasons, assert the chart has gaps in the reference line at the correct seasons (count `g.recharts-reference-line` or equivalent segment count). Hover one gap, assert tooltip text contains "cohort sample below threshold".
- `player_baseline_by_phase_chips.sh` — for the /batting, /bowling, /fielding "By Phase" tabs, click into each, assert each rate tile that gained a chip (per the §4 inventory updates) carries a `vs base N.NN` subtitle, anchored against the corresponding `/by-phase` endpoint.
- `player_baseline_filter_matrix.sh` — exercise the filter-combination testing matrix CLAUDE.md requires for any change touching `FilterParams`. At minimum: 3 player pages × 4 narrowing combos (no narrowing / venue / venue+opponent / venue+toss) × 2 (chart + tile assertion) = 24 click-after-mount assertions.

### 6.4. Existing tests to extend

- `test_player_scope_stats.py`, `test_playerscopestats_position.py`, `test_playerscopestats_over.py`, `test_playerscopestats_fielding_position.py` — extend with cross-table consistency checks against the new phase children where they share scope_key.
- `tests/integration/inning_per_page_refetch.sh` — already covers click-after-mount on every InningToggle mount site (10 sites per the memory `feedback_test_every_call_site`). Add the new chart-overlay refetch sites to the same harness or to a parallel `chart_baseline_refetch.sh` that mirrors its structure.

## 7. Phasing

Phase progression mirrors `spec-player-compare-average.md`:

1. **Phase A — New child tables + populate scripts.** `scripts/populate_playerscopestats_batting_phase.py` + `_fielding_phase.py`. Wire `populate_full` into `import_data.py` and `populate_incremental` into `update_recent.py`. Sanity tests (§6.1) land in the same commit per CLAUDE.md.
2. **Phase B — Six new cohort endpoints + Q6 envelope extensions.** All six `/by-season` + `/by-phase` endpoints accepting `FilterParams + AuxParams + person_id`. Q6 response-shape extensions on `/{batters,bowlers}/{id}/summary` + their cohort summary mirrors. Regression captures (§6.2). One commit per endpoint or per coherent endpoint-group; not batched.
3. **Phase C — Frontend wire-up, /batting.** `scopeBaseline` fetch, LineChart referenceData on By Season, by-phase chip extensions on By Phase tab, integration tests (§6.3) for /batting in same commit.
4. **Phase D — Frontend wire-up, /bowling.** Same shape as Phase C.
5. **Phase E — Frontend wire-up, /fielding.** Same, plus three new chips on the shared stat row, plus `FIELDING_GLOBAL_*` constants for the sparklines.
6. **Phase F — /players band chip extensions.** Q6 (ii) tile additions: Boundaries/Innings, Sixes/Innings, Fours/Innings, milestone-per-innings on Batting band; Wickets/Innings, Maidens/Innings on Bowling band; Catches/Match, Run-Outs/Match, Stumpings/Match on Fielding band.
7. **Phase G — `<BaselineTooltip>` shared component + label-base resolver.** Cross-cutting UI plumbing; both the chip subtitle hover and the chart reference-line hover route through it. Lands after Phases C-E so a real consumer exists; before Phase F if /players-band design wants the same tooltip.
8. **Phase H — Filter-matrix integration tests.** `player_baseline_filter_matrix.sh` + extended `inning_per_page_refetch.sh` coverage on the new chart sites.

Phases A-B are backend; C-G are frontend; H is the test-coverage capstone. Each phase ships as one or two commits per CLAUDE.md commit cadence (one feature, one commit, immediately).

## 8. Out of scope

- Keeping cohort baselines (`/players/keeping/summary` still returns `cohort=null`; separate spec).
- Records pages baselines (identity records by design).
- Matchup scatterplots / matchup tables on `/batting` `vs Bowlers` / `/bowling` `vs Batters` (paired-comparison data; no singleton cohort applies).
- By-Phase volume tiles (Runs, Balls, Wickets, Catches per phase) — no rate framing.
- Per-phase weighting variant on Fielding (the original player-compare spec §5.4 rejected position-weighted catches-per-match by dimensional analysis; keeps fielding keeper-binary).
- Fielding impact-weighted spec (`spec-fielding-impact.md` territory).

---

## 9. Session 1 implementation log (2026-05-20)

The backend half of this spec — Phase A (tables) + Phase B (endpoints
+ Q6 envelopes) — landed in one session. Commits in order:

| # | Commit | Subject |
|---|---|---|
| 1 | `0e7e7eb` | playerscopestats(over): milestone + maidens columns (Q6 §3.3.5) |
| 2 | `f65f019` | playerscopestats_batting_phase: per-phase batting cohort child table |
| 3 | `2e0f9b9` | playerscopestats_fielding_phase: per-phase fielding cohort child table |
| 4 | `521260d` | scope_averages: `/players/batting/by-season` |
| 5 | `85b3b11` | scope_averages: `/players/batting/by-phase` |
| 6 | `607fda8` | scope_averages: `/players/bowling/by-season` |
| 7 | `f1a5255` | scope_averages: `/players/bowling/by-phase` |
| 8 | `c640250` | scope_averages: `/players/fielding/by-season` |
| 9 | `8490b91` | scope_averages: `/players/fielding/by-phase` |
| 10 | `55c890a` | summaries + cohort: Q6 per-innings rate envelopes |
| 11 | `5209c6b` | regression: 18 NEW URL captures for the six new endpoints |

DB state at end of session:
- `playerscopestats` rebuilt with 4 new milestone columns: 67,217 rows
- `playerscopestatsover` rebuilt with 1 new maidens column: 282,822 rows
- `playerscopestats_batting_phase` (NEW): 112,220 rows
- `playerscopestats_fielding_phase` (NEW): 72,053 rows

Sanity totals: 24,121 thirties · 14,571 fifties · 806 hundreds ·
20,308 ducks · 5,701 maidens. Two new sanity tests pass; existing
playerscopestats family sanity tests still pass.

### What's left for next session — §5 UI plumbing

Spec sections §5 (UI plumbing) and §6.3 (integration tests) are the
next-session work. Phases C–G from §7 of this spec map to:

- **Phase C — Frontend wire-up, `/batting`.** `scopeBaseline` fetch
  for the two new endpoints (`by-season` + `by-phase`), `<LineChart
  referenceData=…>` on the By Season tab (switching `BarChart →
  LineChart`), per-phase chip extensions on the By Phase tab.
- **Phase D — `/bowling`.** Same shape as C.
- **Phase E — `/fielding`.** Same, plus the Catches/Match,
  Run-Outs/Match, Stumpings/Match chips on the shared stat row + the
  `FIELDING_GLOBAL_*` constants for the sparklines.
- **Phase F — `/players` band Q6 chip extensions.** Surface the seven
  batting per-innings rate tiles (Boundaries/Innings, Sixes/Innings,
  Fours/Innings, 30s/50s/100s/Innings, Ducks/Innings) and two bowling
  per-innings rate tiles (Wickets/Innings, Maidens/Innings) on
  `PlayerSummaryRow.tsx`. The new envelope fields are already in
  `/batters/{id}/summary` and `/bowlers/{id}/summary` responses (Q6
  envelope commit `55c890a`) — frontend just needs to render.
- **Phase G — `<BaselineTooltip>` shared component.** Both the
  `MetricDelta` chip subtitle hover and the LineChart reference-line
  hover route through this component. Q5 decision says label is
  `base` (already in `MetricDelta.tsx:32` for player tiles) — extend
  to LineChart legend resolver.

### Endpoint quick-reference for the UI side

Sample fetch pattern (mirrors how Teams plumbs its `scopeBaseline`):

```tsx
// Batting.tsx — sketch
const scopeBaseline = useFetch<{ by_season: ScopePlayerBattingSeason[] } | null>(
  () => playerId && activeTab === 'By Season'
    ? getJSON(`/api/v1/scope/averages/players/batting/by-season?person_id=${playerId}&${qs(filters, aux)}`)
    : Promise.resolve(null),
  [...filterDeps, activeTab],
)
// then on the chart:
<LineChart
  data={season.by_season}
  referenceData={scopeBaseline.data?.by_season}
  referenceKey="run_rate"        // or "strike_rate" etc.
  referenceLabel="base"          // Q5 — not "avg"
/>
```

Response shape per row (batting by-season):

```json
{
  "season": "2016",
  "mix": [0.9375, 0.0625, 0, 0, 0, 0, 0, 0, 0, 0],
  "n_players": 140,
  "n_innings": 883,
  "below_support": false,
  "cliff_buckets": [],
  "total_runs": 239.61,
  "run_rate": 8.0,
  "strike_rate": 133.3,
  "boundary_pct": 18.0,
  "dot_pct": 34.9,
  "balls_per_four": 7.23,
  "balls_per_boundary": 5.56,
  "sixes_per_innings": 0.963,
  "fours_per_innings": 3.211,
  "boundaries_per_innings": 4.174
}
```

A row with `below_support: true` has every metric `null` and
populates `cliff_buckets: [<integer>...]` — the chart's
`referenceData` row should drop that season's segment (Q4 gap
behaviour) and the hover tooltip on the gap should surface the
failing bucket label.

### Key files / functions to consult when starting §5

- `frontend/src/pages/Teams.tsx:678 + :826` — the reference pattern
  for `scopeBaseline = useFetch + LineChart referenceData`. Mirror
  on the three player pages.
- `frontend/src/components/MetricDelta.tsx:32` — `label='base'` is
  already passed on the player side. The new chart-legend resolver
  should branch on player-discipline and produce `base` instead of
  the team-side default `avg`.
- `frontend/src/components/players/PlayerSummaryRow.tsx:194-` —
  where the new Phase F per-innings tile rows land.
- `frontend/src/types.ts` — when adding TypeScript types for the new
  endpoint payloads, mirror the `Scope{Batting,Bowling,Fielding}Season`
  shapes already there (used by the Teams chart) but rename to
  `ScopePlayer{Batting,Bowling,Fielding}{Season,Phase}` and add the
  new mix / cliff_buckets / per-innings fields.
- `tests/integration/` — `chart_baseline_refetch.sh` (new) +
  `player_baseline_chip_extensions.sh` (new) + `player_baseline_
  filter_matrix.sh` (new) per §6.3.

### Known asymmetries flagged during implementation

These weren't blockers but should be revisited in the spec or a
follow-up commit:

1. **By-phase batting is position-flat** (commit `85b3b11`). The new
   `playerscopestats_batting_phase` table is keyed by phase only;
   true position × phase weighting would need a (person × scope ×
   position × phase) precompute. Bowling-by-phase IS over-mix-weighted
   per-phase because over IS the bowling cohort identity.
2. **Q6 per-innings rate baselines are scope-flat**, not position-
   mix-weighted (commit `55c890a`). The position child table doesn't
   carry milestone counts, so a true position-weighted milestone-per-
   innings baseline isn't derivable without a new child column.
   Acceptable because milestones aren't position-mix-weighted in the
   player's value either.
3. **Bowling per-innings denominator is approximated** as 24 legal
   balls per bowling innings (commit `55c890a`). Exact would need
   an `innings_bowled` column on `playerscopestats` (not currently
   present) or a separate per-innings table.

Both points #2 and #3 are flagged in spec §3.3 / §3.4 as accepted
trade-offs for the chip purpose; revisit if user feedback surfaces
discrepancies between the chip baseline and intuition.
