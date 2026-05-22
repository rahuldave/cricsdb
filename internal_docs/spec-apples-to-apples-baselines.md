# Apples-to-Apples Baseline Audit + Fix Spec

**Status:** SHIPPED + DEPLOYED 2026-05-21 (21 commits
`f68a7dc → 9119fe7`). All 6 tiers landed. New tables: bowling_innings
on parent + 4 milestones on position child + innings_bowled/4fers on
over child + new batting_over + new batting_phase_position. T2
dimensional fix uses per_innings_scale = cohort_attendances /
cohort_unique_innings. 0 REG drift across 6 families. Memory:
`project_apples_to_apples_shipped.md`.
**Triggered by:** user feedback on Kohli IPL 100s/Inn 0.033 vs scope-flat
baseline 0.006 → +450%. The dimensional-discipline spec
(`spec-rate-vs-volume-audit.md`) fixed the unit mismatch but did NOT
fix the cohort-denominator mismatch: per-innings batting rates
(milestones, runs/inn, boundaries/inn) compare a top-order specialist
against the average of ALL batters in scope, including #11 tail-enders.

This spec audits every cohort baseline shipped across the player
endpoints, identifies every metric where the baseline ignores the
player's deployment-mix, and lays out the schema + endpoint + UI work
to fix them.

---

## 1. The principle

> A cohort baseline should be drawn from the **deployment-matched peer
> cohort**, not the scope-wide pool. The matching axis depends on the
> metric:
>
> - **Batting per-innings rates** vary strongly by batting position.
>   Cohort baseline ⇒ convex-combine per-bucket (position) rates by
>   the player's per-season **position mix**.
> - **Bowling per-innings rates** vary by deployment phase. Cohort
>   baseline ⇒ over-mix-weighted (the existing convex-combine path on
>   balls-denominator rates extends here for innings-denominator rates).
> - **Fielding per-match rates** vary by role (keeper vs outfielder).
>   Cohort baseline ⇒ keeper-binary partition. **Already correct.**

Per-balls batting rates (SR, dot %, boundary %, B/4, B/Bndry) already
use position-weighted convex combination via the `playerscopestats_
position` child table. Per-balls bowling rates use over-mix convex
combination via `playerscopestats_over`. **These are fine.**

The problem is the per-INNINGS rates, which fall through a separate
code path that aggregates scope-wide totals from the parent
`playerscopestats` table.

---

## 2. Audit findings

### 2.0 Full chart + sparkline inventory across player pages

Updated 2026-05-21 after the audit gap on sparklines was flagged. Every
chart and reference-line surface on `/players`, `/batting`, `/bowling`,
`/fielding` classified end-to-end:

#### `/players` (subject profile)

| Surface | Cohort source | Status |
|---|---|---|
| Batting band chips | `/batters/{id}/summary` per-innings envelopes | **⚠ scope-flat** on runs/inn, milestones, boundaries/inn |
| Bowling band chips | `/bowlers/{id}/summary` per-innings envelopes | **⚠ scope-flat** on wkts/inn, maidens/inn, 4-fers/inn |
| Fielding band chips | `/fielders/{id}/summary` per-match envelopes | ✓ keeper-binary partition |
| Distribution sparklines (batting/bowling/fielding tabs) | Hardcoded gender-tier constants from `globalBaselines.ts` | **⚠ gender-only**, not position/over-aware |

#### `/batting` (deep-dive)

| Tab | Chart | Cohort overlay | Status |
|---|---|---|---|
| By Season | Runs by Season | (none — volume) | ✓ C1 |
| By Season | Runs/Inn by Season | `seasonBaseline.runs_per_innings` | ✓ position-weighted (B2) |
| By Season | Strike Rate by Season | `seasonBaseline.strike_rate` | ✓ position-weighted (cv) |
| By Over | Strike Rate by Over | (none — A7 deferred) | **⚠ MISSING** (T4 + T5) |
| By Phase | Per-phase chips (SR, dots, boundary, runs/inn, etc.) | `phaseBaseline` from position-FLAT child | **⚠ position-flat** (T3) |
| vs Bowlers | SR vs Average scatter | (per-bowler dots; no cohort framing) | N/A |
| Dismissals | Dismissals donut + Dismissals by Over | (proportional / volume) | N/A |
| Inter-Wicket | SR by Wickets Down + Runs by Wickets Down | (no cohort axis) | N/A |

#### `/bowling` (deep-dive)

| Tab | Chart | Cohort overlay | Status |
|---|---|---|---|
| By Season | Wickets by Season | (none — volume) | ✓ C1 |
| By Season | Wkts/Inn by Season | `seasonBaseline.wickets_per_innings` = `cv(wkts/over) × 4` | **⚠ heuristic** (T2 refine) |
| By Season | Bowling Strike Rate by Season | `seasonBaseline.strike_rate` | ✓ over-mix-weighted (cv) |
| By Season | Economy by Season | `seasonBaseline.economy` | ✓ over-mix-weighted (cv) |
| By Over | Economy by Over | Text strip from over-mix cohort | ✓ data, ⚠ presentation (T5) |
| By Phase | Per-phase chips (econ, SR, dots) | over-mix-aware via per-over child × phase | ✓ |
| vs Batters | Econ vs Avg scatter | (per-batter dots; no cohort) | N/A |
| Wickets | Wicket Types donut + Wickets by Phase | (proportional / volume) | N/A |

#### `/fielding` (deep-dive)

| Tab | Chart | Cohort overlay | Status |
|---|---|---|---|
| By Season | Dismissals by Season | (none — volume) | ✓ C1 |
| By Season | Dis/Match by Season | `seasonBaseline.dismissals_per_match` | ✓ keeper-binary |
| By Over | Dismissals by Over | (no overlay; volume, no cohort axis) | ✓ |
| By Phase | Per-phase Total/Match chip | `phaseBaseline.dismissals_per_match` | ✓ keeper-binary phase-matched |
| Dismissal Types | Donut | (proportional) | N/A |
| Keeping | Dismissals + Byes by Season | (no cohort yet — keeping cohort deferred) | N/A |

#### Net new issues vs the original audit (§2.1)

The chart inventory adds **two surfaces** not previously listed:
- **`/bowling` Wkts/Inn by Season overlay** uses a `wickets_per_over × 4`
  heuristic (`scope_averages.py:2853`). Over-mix-aware but coarse —
  Tier 2's `innings_bowled` denominator will replace it with the
  exact per-bucket rate.
- **`/players` sparkline reference lines** — the gray gender-tiered
  line is hardcoded across all positions/over-buckets; the green
  `leagueReferenceValue` prop exists in `DistributionSparkline.tsx`
  but is **NEVER wired through** by `BatterDistributionPanel`,
  `BowlerDistributionPanel`, or `FielderDistributionPanel`. Tier 6
  fixes both.

### 2.1 Definite issues — scope-flat baselines on rates that vary by position/over

#### A. /summary

**Batting `compute_players_batting_cohort`** — 8 fields scope-flat:

| Field | Computed via |
|---|---|
| `runs_per_innings` | `SUM(runs) / SUM(innings_batted)` parent |
| `boundaries_per_innings` | `SUM(fours+sixes) / SUM(innings_batted)` parent |
| `fours_per_innings` | parent |
| `sixes_per_innings` | parent |
| `thirties_per_innings` | parent |
| `fifties_per_innings` | parent |
| `hundreds_per_innings` | parent |
| `ducks_per_innings` | parent |

**Impact:** Kohli IPL 100s/Inn delta is +450% (scope-flat) vs ~+104%
(top-order). Same magnitude error on milestones and boundaries; smaller
but still significant on runs_per_innings.

**Bowling `compute_players_bowling_cohort`** — 3 fields scope-flat:

| Field | Computed via |
|---|---|
| `wickets_per_innings` | `SUM(wickets) / (SUM(balls)/24)` heuristic |
| `maidens_per_innings` | `SUM(maidens) / (SUM(balls)/24)` heuristic |
| `four_wicket_hauls_per_innings` | `SUM(fwh) / (SUM(balls)/24)` |

**Impact:** powerplay/death specialists take more 4-fers, more maidens
than middle-overs spinners. Bumrah IPL 4-fers/Inn +45% (scope-flat) is
likely overstated against same-archetype bowlers.

**Fielding** — keeper-binary partition. **OK.** ✓

#### B. /by-season

**Batting** — 4 milestone fields scope-flat per season (`hundreds_per_
innings`, `fifties_per_innings`, `thirties_per_innings`, `ducks_per_
innings`). `runs_per_innings` is already position-weighted (B2 shipped).

**Bowling** — `four_wicket_hauls_per_innings` scope-flat per season.
`wickets_per_innings` + `maidens_per_innings` use the `wickets_per_
over × 4` heuristic — over-mix-aware but coarse.

**Fielding** — keeper-binary. OK.

#### C. /by-phase

**Batting `compute_players_batting_by_phase` — entire function is
position-FLAT.** Per-phase child table `playerscopestats_batting_phase`
is keyed by (person, scope, phase). No position bucket. So an opener's
powerplay SR / dot / boundary / runs-in-phase metrics get compared to
ALL players' powerplay metrics, including #11 specialists who barely
face PP.

**Bowling** — uses per-over child × phase boundary, over-mix-aware. OK.

**Fielding** — keeper-binary. OK.

### 2.2 Missing-overlay items (out-of-scope of rate-vs-volume spec)

| Item | Status | Fix path |
|---|---|---|
| /batting SR-by-Over chart overlay | No cohort source exists | New `playerscopestats_batting_over` fact + endpoint + LineChart |
| /bowling Econ-by-Over chart overlay | Text strip (C3) | BarChart referenceData prop + replace text strip |

### 2.3 Already correct

These cohort baselines are properly mix-weighted, **no fix needed**:

- **Batting /summary** per-balls rates: average, strike_rate, dot_pct, boundary_pct, balls_per_four/six/boundary
- **Bowling /summary** per-balls rates: economy, average, strike_rate, dot_pct, boundary_pct, wickets_per_over, balls_per_boundary
- **Fielding /summary** + **/by-season** + **/by-phase**: keeper-binary
- **Batting /by-season**: runs_per_innings, fours/sixes/boundaries_per_innings, all per-balls rates
- **Bowling /by-season**: economy, bowling_avg, strike_rate, dot_pct, boundary_pct, wickets_per_over, balls_per_boundary
- **Bowling /by-phase**: all rates (over-mix-aware via per-over child)

---

## 3. Design — 5 tiers of work

### Tier 1 — Batting per-innings rates → position-weighted

**Schema additions on `playerscopestatsposition`:**

```sql
ALTER TABLE playerscopestatsposition ADD COLUMN thirties INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsposition ADD COLUMN fifties  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsposition ADD COLUMN hundreds INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsposition ADD COLUMN ducks    INTEGER NOT NULL DEFAULT 0;
```

(Per the existing idempotent-ALTER pattern in `populate_player_scope_
stats.py`.) The boundaries / per-innings fields the cohort needs are
derivable from existing columns (`fours`, `sixes`, `innings`).

**Populate extension (`populate_playerscopestatsposition.py`):**

For each (person, innings) tuple already tracked, bucket by:
- `30 ≤ runs < 50` → thirties[position] += 1
- `50 ≤ runs < 100` → fifties[position] += 1
- `runs ≥ 100` → hundreds[position] += 1
- `runs == 0 AND was_dismissed` → ducks[position] += 1

Position derivation already happens for the existing fours/sixes/runs.

**Endpoint changes:**

In `compute_players_batting_cohort` (`scope_averages.py:1730`):

1. Add the 4 milestone columns to the `main_sql` per-bucket aggregate
   alongside `fours`, `sixes`, `runs`.
2. Compute per-bucket per-innings rates inside the `by_position` loop:
   - `runs_per_innings = runs / innings`
   - `fours_per_innings = fours / innings`
   - `sixes_per_innings = sixes / innings`
   - `boundaries_per_innings = (fours+sixes) / innings`
   - `hundreds_per_innings = hundreds / innings`
   - etc.
3. Replace the 8 `_pi_rate(...)` scope-flat values with `cv("...")`
   convex-combination calls. The `cv()` helper already exists.
4. Drop the now-unused `pi_sql` query.

Apply identically to `compute_players_batting_by_season` for the 4
milestone fields (the other 4 are already position-weighted in B2).

### Tier 2 — Bowling per-innings rates → over-weighted

**Schema additions on `playerscopestatsover`:**

```sql
ALTER TABLE playerscopestatsover ADD COLUMN innings_bowled    INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN four_wicket_hauls INTEGER NOT NULL DEFAULT 0;
```

- `innings_bowled` = distinct innings where the bowler delivered ≥ 1
  legal ball in that over bucket. Needed as the per-bucket denominator
  for wickets/innings, maidens/innings, four-wicket-hauls/innings.
- `four_wicket_hauls` = count of 4-fers attributed to this over bucket
  by the over in which the 4th wicket was taken (one row per 4-fer in
  the over that capped it). Lets cohort 4-fers/inn be convex-combined.

**Populate extension (`populate_playerscopestatsover.py`):**

For each (bowler, innings, over) tuple already tracked, set
`innings_bowled = 1` for any over the bowler delivered in. For 4-fers,
walk the wickets pass: when a bowler reaches 4 wickets in an innings,
attribute +1 to the over the 4th wicket happened in.

**Endpoint changes:**

`compute_players_bowling_cohort` (`scope_averages.py:2459`):

1. Per `by_over` row, derive `innings_bowled` from the new column
   (SUM across players per over bucket).
2. Add per-bucket per-innings rates inside the existing `by_over` loop:
   - `wickets_per_innings = wickets / innings_bowled`
   - `maidens_per_innings = maidens / innings_bowled`
   - `four_wicket_hauls_per_innings = four_wicket_hauls / innings_bowled`
3. Replace the scope-flat `cc_wickets_per_innings`, etc. with
   `cv("wickets_per_innings")`, etc.

Apply identically to `compute_players_bowling_by_season` — drops the
`× 4` heuristic for wickets/innings and maidens/innings, replaces
with proper over-mix-weighted per-bucket rates.

### Tier 3 — Position × phase batting cohort

**New child table `playerscopestatsbattingphaseposition`** — 30 rows
per (player, scope) = 3 phases × 10 position buckets:

```python
class PlayerScopeStatsBattingPhasePosition:
    person_id: ForeignKey[str, "person"]
    scope_key: str
    phase_bucket: int   # 1=PP, 2=mid, 3=death
    position_bucket: int  # 1=opener (pos 1+2), 2=#3, ..., 10=#11
    innings_in_phase: int = 0
    balls_in_phase: int = 0
    runs_in_phase: int = 0
    dots_in_phase: int = 0
    fours_in_phase: int = 0
    sixes_in_phase: int = 0
    boundaries_in_phase: int = 0
    dismissals_in_phase: int = 0
```

**New populate script** `populate_playerscopestatsbattingphaseposition.py`.
Extends the existing phase populate to track per-position. Re-uses
`derive_positions(deliveries)` already in
`api/innings_positions.py`.

**Endpoint changes — `compute_players_batting_by_phase`:**

1. Add a `player_sql` query that returns the player's per-(phase, position)
   innings distribution at the requested scope.
2. Add a `cohort_sql` query that aggregates per (phase, position) over
   all players at scope.
3. For each phase, derive the player's position mix WITHIN THE PHASE
   (some batters drop a position when slotted in death), build per-
   bucket rates, convex-combine with the player's per-phase mix.

This is the heaviest tier — new table, new populate, new endpoint
shape. Frontend already consumes by-phase chips so the contract is
the same (scope_avg only changes).

### Tier 4 — Per-over batting cohort (closes A7)

**New child table `playerscopestatsbattingover`** — 20 rows per (player,
scope) = 1 per over bucket:

```python
class PlayerScopeStatsBattingOver:
    person_id: ForeignKey[str, "person"]
    scope_key: str
    over_number: int  # 1..20
    legal_balls_faced: int = 0
    runs: int = 0
    dots: int = 0
    fours: int = 0
    sixes: int = 0
    dismissals: int = 0
    innings_faced: int = 0  # distinct innings where the batter faced ≥1 ball at this over
```

**New populate script** `populate_playerscopestatsbattingover.py`.

**New endpoint** `compute_players_batting_by_over(person_id, filters)`
returning a 20-element `by_over` array with cohort SR, dot %, boundary %,
balls_per_four, balls_per_boundary, etc. — mirrors the bowling
`by_over` shape.

**Frontend wiring:** /batting By Over tab fetches the cohort's
`by_over` and renders the SR-per-over overlay. Pending Tier 5 for
proper line overlay; until then can ship as a text strip à la C3.

### Tier 6 — Sparkline reference lines → position/over-mix-weighted

`DistributionSparkline.tsx` already accepts three reference-line props:

| Prop | Color | Source today | Status |
|---|---|---|---|
| `playerReferenceValue` | Black (`WISDEN.ink`) | Player's own scope-lifetime mean | ✓ |
| `globalReferenceValue` | Gray (`WISDEN.faint`) | `globalBaselines.ts` gender-tier constant | **⚠ scope-flat / gender-only** |
| `leagueReferenceValue` | Forest green (`WISDEN.forest`) | (unwired — prop exists, no caller plumbs it) | **⚠ MISSING** |

`globalBaselines.ts` ships hardcoded centres:
```
BATTING_GLOBAL_MEN  = { runs: 18, sr: 125 }       // pool of ALL men's innings
BOWLING_GLOBAL_MEN  = { wickets: 1, runs: 26, rpo: 8 }
```
Pool of every men's innings = ~18 runs/inn — but a #11 specialist's
~3 runs/inn and an opener's ~30 runs/inn both get the same gray line.

**Fix — wire the green league line to the `/summary` envelope's
position/over-weighted `scope_avg`.**

Once Tiers 1–3 land, `summary.runs_per_innings.scope_avg` is
position-weighted; `summary.wickets_per_innings.scope_avg` is
over-mix-weighted; `summary.dismissals_per_match.scope_avg` is
keeper-binary. The same envelope the band chip reads — wire it
straight to the sparkline's `leagueReferenceValue`. The green line
then re-narrows in lockstep with the FilterBar (chip ↔ chart symmetry).

Frontend changes (no backend needed — Tier 6 just consumes Tiers 1–3):

| Panel | Sparkline tab | `leagueReferenceValue` source |
|---|---|---|
| BatterDistributionPanel | Runs per innings | `summary.runs_per_innings.scope_avg` (Tier 1) |
| BatterDistributionPanel | SR per innings | `summary.strike_rate.scope_avg` (already position-weighted) |
| BowlerDistributionPanel | Wickets per spell | `summary.wickets_per_innings.scope_avg` (Tier 2) |
| BowlerDistributionPanel | Runs conceded per spell | derive: `economy.scope_avg × balls/spell` — or surface a new `runs_conceded_per_innings` envelope |
| BowlerDistributionPanel | Economy per spell | `summary.economy.scope_avg` (already over-mix-weighted) |
| FielderDistributionPanel | Catches per match | `summary.catches_per_match.scope_avg` (keeper-binary) |
| FielderDistributionPanel | Run-outs per match | `summary.run_outs_per_match.scope_avg` |
| FielderDistributionPanel | Dismissals per match | `summary.dismissals_per_match.scope_avg` |

**Gray line decision (keep / drop / re-source):** the hardcoded gray
line is still useful as a stable "all T20" anchor that does NOT
narrow with the FilterBar — it's the wide-population context line.
Keep it (with a tooltip clarifying scope: "all men's T20 cricket")
so the green line ("comparable cohort at the active scope") and gray
line ("all T20 cricket") form a meaningful dual reference. The
hardcoded constants in `globalBaselines.ts` stay where they are.

Tier 6 commits:

| # | What |
|---|---|
| T6.1 | Plumb `leagueReferenceValue` through `BatterDistributionPanel` from `summary.{runs,strike_rate}_per_innings.scope_avg` |
| T6.2 | Same for `BowlerDistributionPanel` (wickets/spell, runs/spell, econ/spell) |
| T6.3 | Same for `FielderDistributionPanel` (catches/match, run-outs/match, dismissals/match) |
| T6.4 | Sparkline tooltip clarifies which line is which (player / scope-cohort / all-T20) + integration test asserting the green line appears on all three panels |

T6.4 also locks `assert_eq "green-ref-value matches /summary cohort scope_avg"` on each sparkline so future drift between chip ↔ sparkline values is caught at integration time.

### Tier 5 — BarChart referenceData prop (closes A8)

Frontend chart component change. `BarChart.tsx` accepts a new prop:

```ts
interface BarChartProps<T> {
  ...existing...
  referenceData?: { category: string; value: number }[]
  referenceLabel?: string
}
```

Renders a horizontal-line overlay (dashed, forest green per existing
overlay convention) at each category's reference value. Updates the
legend to name both series.

Once shipped, the C3 text strip on /bowling Econ by Over and the new
Tier 4 SR-by-Over chart upgrade from text strip to proper line
overlay.

---

## 4. Implementation sequencing

Same flip-before-shape regression discipline as the rate-vs-volume
spec. Each tier ≈ 4-6 commits (schema → populate → endpoint → sanity →
regression flip / lock).

| Phase | Commits | What lands |
|---|---|---|
| **T1.S** | 1 | Schema migration: 4 milestone columns on `playerscopestatsposition` |
| **T1.P** | 1 | Populate extension + full rebuild |
| **T1.B** | 3 | REG→NEW flip + endpoint switch to convex-combine on /summary + /by-season for batting per-innings rates + sanity tests + NEW→REG lock |
| **T2.S** | 1 | Schema: `innings_bowled` + `four_wicket_hauls` on `playerscopestatsover` |
| **T2.P** | 1 | Populate extension + rebuild |
| **T2.B** | 3 | Flip + endpoint switch + sanity + lock for bowling per-innings rates |
| **T3.S** | 1 | New `playerscopestats_batting_phase_position` table + model |
| **T3.P** | 1 | New populate script + full populate |
| **T3.B** | 3 | Flip + endpoint switch on `compute_players_batting_by_phase` + sanity + lock |
| **T4.S** | 1 | New `playerscopestats_batting_over` table |
| **T4.P** | 1 | New populate script + full populate |
| **T4.B** | 2 | New `/scope/averages/players/batting/by-over` endpoint + sanity |
| **T4.F** | 1 | Frontend: wire /batting SR-by-Over overlay via Tier 5's BarChart prop (or temporary text strip if Tier 5 lands later) |
| **T5.F** | 2 | BarChart.tsx accepts `referenceData` prop + render overlay; replace C3 text strip with native overlay |
| **T6.1** | 1 | Plumb `leagueReferenceValue` on BatterDistributionPanel from /summary scope_avg |
| **T6.2** | 1 | Same for BowlerDistributionPanel |
| **T6.3** | 1 | Same for FielderDistributionPanel |
| **T6.4** | 1 | Tooltip clarification + integration test |

Total: **25 commits** across 6 tiers.

### Tier dependency graph

- T1, T2, T3 are independent (each touches a different child table /
  endpoint). Can ship in any order.
- T4 is independent at the backend but the frontend overlay (T4.F)
  benefits from T5 shipping first (so it can use the native overlay
  instead of a text strip).
- T5 is independent — chart-component refactor.
- **T6 consumes T1 + T2** — the sparkline green line reads
  `/summary.{runs_per_innings,wickets_per_innings,...}.scope_avg`.
  Until T1/T2 land those values are still scope-flat and the green
  line would carry the same bug it's supposed to fix. **Ship T6 after
  T1 and T2.**

Recommended order: T1 → T2 → T6 → T5 → T4 → T3. T6 batches naturally
right after T1/T2 because it's pure frontend plumbing that needs the
upstream fixes.

---

## 5. Tests

### Sanity (Python, hits running API)

For each tier, new assertions in `tests/sanity/test_q6_extension_
envelopes.py` (or a new file `test_position_weighted_baselines.py`):

1. **Weighted ≠ flat** — for each fixed rate (e.g.
   `hundreds_per_innings`), assert player.scope_avg AT this scope
   differs from the scope-flat parent-table aggregate. The flag the
   fix is doing something. Specifically: Kohli IPL hundreds_per_innings
   scope_avg should be ~0.016 (top-order), not 0.006 (scope-flat).
2. **Convex-combine identity** — for each weighted field, assert
   player.scope_avg equals SUM(mix[i] * per_bucket_rate[i]) computed
   from the same /scope/averages/players/.../by-position data the
   endpoint uses. Same math, exposed both ways.
3. **Cliff handling** — if any weighted-bucket is below support
   threshold (cliff), scope_avg is null. Existing pattern.

### Integration (bash, agent-browser)

Extend `tests/integration/player_band_q6_chips.sh` to assert the new
scope_avg numbers on the rendered DOM (replacing the scope-flat
expectations).

Extend `tests/integration/player_baseline_chart_overlays.sh` for the
T4 + T5 chart overlay additions.

### Regression

Flip REG → NEW on every URL whose response shape changes:
- /batters/{id}/summary, /by-season, /by-phase
- /bowlers/{id}/summary, /by-season
- /scope/averages/players/batting/summary, /by-season, /by-phase
- /scope/averages/players/bowling/summary, /by-season
- New /scope/averages/players/batting/by-over

All flip in a preceding commit; new shape captured; flip-back to REG
in a following commit. Same dance as the rate-vs-volume spec.

---

## 6. Headline expected numbers (Kohli IPL all-time)

To set acceptance criteria for sanity tests:

| Field | Before (scope-flat) | After (position-weighted top-order) |
|---|---|---|
| 30s/Inn baseline | 0.140 | ~0.191 |
| 50s/Inn baseline | 0.103 | ~0.189 |
| 100s/Inn baseline | 0.006 | ~0.016 |
| Ducks/Inn baseline | 0.078 | ~0.060 |
| Runs/Inn baseline | 19.84 | ~28-30 (top-order avg) |

Kohli's delta-pct's all shrink commensurately but stay positive — he
remains elite even when judged against same-position peers.

For Bumrah IPL bowling:

| Field | Before (scope-flat) | After (over-mix-weighted) |
|---|---|---|
| 4-fers/Inn baseline | 0.022 | TBD (likely 0.025-0.035 for PP+death specialists) |
| Wkts/Inn baseline | 1.13 | TBD |
| Maidens/Inn baseline | 0.024 | TBD |

These are validated by the sanity-test assertions.

---

## 7. Risks + open questions

- **Cliff thresholds** — convex-combine over per-bucket rates can null
  out the whole scope_avg if any weighted bucket is below the
  sample-size threshold. The strict-cliff invariant already established
  in `spec-player-compare-average.md` §6 holds — but the FREQUENCY of
  cliffs may rise on narrow scopes (e.g. one season × one team).
  Acceptable per existing pattern; document in chip tooltip.
- **4-fer-attributed-to-over choice** — attributing each 4-fer to the
  over the 4th wicket fell in is one of three options. Alternatives:
  (a) duplicate the 4-fer across every over the bowler delivered in
  that innings (overcounts), (b) attribute to the predominant over
  bucket. (a) gets the right TOTAL but wrong per-over distribution; the
  4th-wicket-over option matches "this is where the milestone happened"
  semantics.
- **By-phase position derivation** — within a phase, "the player's
  position" can be ambiguous if they were not-out at end of phase or
  came in mid-phase. The simplest fix: per innings, count the player's
  position-at-first-ball-faced (already what `derive_positions` does
  for whole innings); apply same to per-phase first-ball-in-phase.

---

## 8. Out of scope

- **Distribution panels** — already use scope-mean + gender-global
  dual-reference framework; not cohort-dependent.
- **Compare grid** — chips show same envelope.scope_avg as the player
  summary; gets fixed automatically.
- **/head-to-head, /matches, /teams, /series** — separate cohort
  systems (team-grain). Not in this audit.
- **Player by-season chart overlays** — already C2'd at the
  weighted-where-data-exists level. T3+T1 will improve the scope_avg
  values these charts overlay; no UI changes needed.
- **Fielding** — keeper-binary partition is the right axis;
  `spec-fielding-impact.md` (deferred) would add position-weighting if
  the codebase decides catches-per-position is the right framing.
