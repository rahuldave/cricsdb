# Mix-and-Performance Charts (Player Distribution Panels)

**Status:** SHIPPED + DEPLOYED 2026-05-21 (17 commits `0de8510 → 03ffea4`). M1 Bowling (/bowling By Over: Mix + Econ + Wkts/Inn) + M2 Batting (new /batting By Position tab: Mix + SR) + M3 Fielding (new /fielding By Dismissed Position tab: Mix + Catches/match, keeper-binary cohort partition). Generic `MixHistogram` + `PerformanceVsCohort` primitives in `frontend/src/components/distribution-charts/` reused across all three disciplines. Memory: `project_mix_perf_charts_m1_shipped.md`. **Originally triggered by:** user follow-up after the COHORT-line UX shipped (`d9a7bc0`) — the cohort line said "weighted to this player's position mix / over mix" but the mix itself was invisible. This spec surfaced it.

Three deferred follow-up specs from `spec-player-compare-average.md §"Follow-up specs"` consolidated into one. The visual + interaction patterns are identical across batting / bowling / fielding (different bucket axes only).

---

## 1. Two charts per discipline (same skeleton)

### Chart A — Mix histogram ("where does this player operate?")

Bar chart, one bar per bucket. Bar height = the player's share of the discipline-specific unit at that bucket.

Display unit is **percentage** of the player's career-in-scope total. Raw count revealed on hover (tooltip). Percentage normalises across career length — an 8-innings player and a 397-innings Kohli render comparably.

Phase tint banded as background:
- Batting + Fielding: top-order (positions 1-3, `WISDEN_TIER_TINTS.sage` 8% opacity) / middle (4-6, no tint) / lower (7-11, `WISDEN_TIER_TINTS.indigo` 8% opacity).
- Bowling: powerplay (overs 1-6, sage) / middle (7-15, no tint) / death (16-20, ochre).

### Chart B — Performance vs cohort ("how does this player perform there?")

Same X-axis as Chart A. Player's per-bucket rate as a bar; cohort's per-bucket rate as a **forest-green reference tick** at the matching X position (matches the existing `colors.md` reference-line convention — same green as the LineChart `referenceData` overlays on the By-Season charts).

Buckets where the player's mix is exactly zero render at 50% opacity (cohort tick still drawn). Buckets where the player has any presence render full-color.

No min-N threshold gating — show the data the API returns, including thin-sample buckets. The cohort tick is the meaningful comparison anchor; the reader judges thin-sample noise themselves.

---

## 2. Per-discipline specifics

### 2.1 Batting — `/batting?player=X`

**Mount:** new tab `By Position` in the existing `Batting.tsx` tab strip. Mount alongside `By Season`, `By Over`, etc.

**Bucket axis:** 10 buckets per `api/innings_positions.py::derive_positions`. Bucket labels: `"Opener"` (positions 1+2 merged), `"#3"`, `"#4"`, … `"#11"`.

**Mix chart unit:** % of player's innings batted at that bucket. Hover → "{bucket}: {innings} innings ({pct}%)".

**Performance chart metric:** Strike Rate (SR). Bar height = player's per-position SR. Reference tick = cohort's per-position SR. SR over Average because SR is most diagnostic at position grain (Avg is dominated by not-outs at #5+).

**Data source — player:** `position_distribution: BattingPositionDistributionEntry[]` already on `/batters/{id}/summary`. Per-bucket `innings / runs / legal_balls / dismissals / fours / sixes / dots` ship today.

**Data source — cohort:** extend each entry with `cohort_innings_share: number` (the cohort's mix-share at this bucket) and `cohort_strike_rate: number`. Computed via `playerscopestatsposition` aggregated over all players in scope, grouped by `position_bucket`. Same SQL as the existing scope_avg path, returned per-bucket instead of folded.

### 2.2 Bowling — `/bowling?player=X`

**Mount:** new tab `By Over` if not present; if a `By Over` tab exists, extend its content.

**Bucket axis:** 20 buckets, 1-indexed overs 1..20. Bucket labels: `"Over 1"`, `"Over 2"`, … `"Over 20"`.

**Mix chart unit:** % of player's legal balls bowled at that over. Hover → "{label}: {balls} balls ({pct}%)".

**Performance chart layout:** **stacked panel** — economy bars on top, wickets-per-innings bars below, shared X axis. Both with their own forest-green cohort reference ticks.

- **Top panel:** per-over economy = `runs_conceded × 6 / legal_balls`. Cohort = same calc aggregated over all bowlers at scope.
- **Bottom panel:** per-over wickets/innings = `wickets / n_innings_bowled`. Cohort = same.

Both panels share the bowling-phase background tint.

**Data source — player:** `over_distribution: BowlingOverDistributionEntry[]` already on `/bowlers/{id}/summary`. Per-bucket `runs_conceded / legal_balls / wickets / dots / boundaries`. **Need to verify** `n_innings_bowled` per bucket — if not present, add to the entry (one INTEGER column denormalised at populate time).

**Data source — cohort:** extend each entry with `cohort_balls_share: number`, `cohort_economy: number`, `cohort_wickets_per_innings: number`. Same shape as batting — aggregate `playerscopestatsover` over all bowlers in scope, grouped by `over_number`.

### 2.3 Fielding — `/fielding?player=X`

**Mount:** new tab `By Dismissed Position` in `Fielding.tsx`.

**Bucket axis:** 10 buckets, same shape as batting (`Opener`, `#3`, ..., `#11`).

**Mix chart unit:** % of player's dismissals-credited at that bucket. Hover → "{label}: {catches} catches + {run_outs} run-outs + {stumpings} stumpings = {total} dismissals ({pct}%)".

**Performance chart metric:** catches-per-match. Bar height = player's catches-per-match at that bucket. Reference tick = cohort's catches-per-match.

**Cohort partition is keeper-binary**, automatic from the player's `is_keeper` flag (already on `FieldingSummary.is_keeper`). No UI toggle:
- If the player is a keeper (`is_keeper === 1`), the cohort tick draws the keeper population's average at scope.
- Otherwise, the outfielder population.

**Data source — player:** `dismissal_position_distribution: FieldingDismissalPositionEntry[]` already on `/fielders/{id}/summary`. Per-bucket `catches / stumpings / run_outs / dismissals`.

**Data source — cohort:** extend each entry with `cohort_dismissals_share: number` and `cohort_catches_per_match: number`. Computed from `playerscopestatsfieldingposition` aggregated by `is_keeper` partition, grouped by `position_bucket`. Substitute catches EXCLUDED at populate (already the case). Convention 3 applied (catches includes c&b).

**Out of scope (explicit):** per-over fielding. We do not have `(fielder, scope, over_number)` precomp. Adding it would mean a new child table populated from `fieldingcredit × delivery.over_number` — that's a separate spec if/when needed.

---

## 3. Backend extensions

Three commits, one per discipline. Each adds `cohort_*` fields to the per-bucket distribution entries on the existing `/summary` endpoint and extends the sanity test.

### 3.1 Batting backend

**File:** `api/routers/batting.py`

Modify `_position_distribution(db, person_id, filters)` (the existing helper at line ~35) to compute cohort aggregates in the same query OR via a sibling query, returning extended rows:

```python
{
  "bucket": int,
  "innings": int, "runs": int, "legal_balls": int, "dismissals": int,
  "fours": int, "sixes": int, "dots": int,
  # NEW
  "cohort_innings_share": float | None,    # cohort's share at this bucket (0-1)
  "cohort_strike_rate":   float | None,    # cohort's SR at this bucket
}
```

Cohort SQL:
```sql
SELECT pssp.position_bucket AS bucket,
       SUM(pssp.innings) AS cohort_innings,
       SUM(pssp.runs)    AS cohort_runs,
       SUM(pssp.legal_balls) AS cohort_balls
FROM playerscopestatsposition pssp
JOIN playerscopestats pss USING (person_id, scope_key)
WHERE {scope_clauses on pss}
GROUP BY pssp.position_bucket
```

Then `cohort_innings_share[b] = cohort_innings[b] / SUM(cohort_innings)` and `cohort_strike_rate[b] = cohort_runs[b] × 100 / cohort_balls[b]`.

**Type extension:** `BattingPositionDistributionEntry` in `frontend/src/types.ts` (line ~362) gains the two `cohort_*` fields, both `number | null`.

**Sanity:** `tests/sanity/test_player_scope_stats.py` extended — assert `cohort_innings_share` sums to 1.0 ± 0.0001 across the 10 buckets at marquee scope.

### 3.2 Bowling backend

**File:** `api/routers/bowling.py`. Same pattern, `playerscopestatsover`-based, grouped by `over_number`. Add to entry:

```python
"cohort_balls_share": float | None,
"cohort_economy":     float | None,
"cohort_wickets_per_innings": float | None,
```

**Watch:** verify `playerscopestats_over` has the columns to compute wickets/innings. Per `internal_docs/data-pipeline.md`, the schema has `maidens` (added in `spec-player-baseline-parity.md`); needs check whether `n_innings_bowled` is per-bucket or only per-parent. If only per-parent, the `wickets_per_innings` denominator falls back to parent `playerscopestats.n_innings_bowled` divided proportionally by bucket balls — note this and add a clear comment, OR add a populate-script field if cleaner.

**Type extension:** `BowlingOverDistributionEntry` gains the three `cohort_*` fields.

### 3.3 Fielding backend

**File:** `api/routers/fielders.py`. Aggregate `playerscopestatsfieldingposition` partitioned by `is_keeper` (join via `playerscopestats.is_keeper` derived from `keeper_assignment` table — verify the column path; if not directly available, derive via `EXISTS` against keeper_assignment).

Add to entry:
```python
"cohort_dismissals_share":    float | None,
"cohort_catches_per_match":   float | None,
```

The catches/match denominator is `playerscopestats.n_matches` summed across the cohort partition (keepers or outfielders) at scope.

**Type extension:** `FieldingDismissalPositionEntry` gains the two `cohort_*` fields.

---

## 4. Frontend components

One reusable component family in `frontend/src/components/distribution-charts/`:

### 4.1 `MixHistogram.tsx`

Props:
```tsx
interface Props {
  entries: { bucket: number; share: number; raw: number; tooltip: string }[]
  bucketLabel: (bucket: number) => string
  phaseTint?: (bucket: number) => string | null    // background tint per bucket
  totalLabel: string                                // "innings" / "balls" / "dismissals" — for hover prefix
}
```

Vanilla bar chart, no Semiotic if simple flexbox is enough. Each bar: height = share×100 (CSS percent), tooltip = passed `tooltip` string. Phase-tint band rendered as a background `div` sibling with absolute positioning.

### 4.2 `PerformanceVsCohort.tsx`

Props:
```tsx
interface Props {
  entries: { bucket: number; playerValue: number | null; cohortValue: number | null; faded: boolean }[]
  bucketLabel: (bucket: number) => string
  phaseTint?: (bucket: number) => string | null
  yLabel: string                                    // "SR" / "Econ" / "Catches/Match"
  yFmt: (v: number) => string                       // formatter for tick labels
}
```

Bar chart with per-bar height = `playerValue`. Cohort drawn as a 2px horizontal forest-green tick (`#3F7A4D` per `colors.md`) at `cohortValue` height, spanning the bar's width plus 4px overhang.

Faded entries render at 50% opacity — cohort tick still drawn so the reader sees what the comparison would be IF the player operated there.

### 4.3 Per-discipline wrappers

One thin component per page, composing `MixHistogram` + `PerformanceVsCohort`:

- `frontend/src/components/batting/PositionDistributionTab.tsx`
- `frontend/src/components/bowling/OverDistributionTab.tsx`
- `frontend/src/components/fielding/DismissedPositionDistributionTab.tsx`

Each fetches its `/summary` data (already fetched by the parent page; may need to pass down via prop OR re-fetch with deduped cache via `useFetch`).

Mount as new tab in the respective page's tab strip.

---

## 5. Phasing

Single discipline ships in ONE PR. Tier M1 (bowling) ships fully before M2 starts so the visual pattern is locked in before extending.

### M1 — Bowling (~5 commits)

1. Backend: extend `over_distribution` entry with `cohort_balls_share` / `cohort_economy` / `cohort_wickets_per_innings`. Sanity test extended.
2. Type extension: `BowlingOverDistributionEntry` gains the three fields.
3. Components: `MixHistogram.tsx` + `PerformanceVsCohort.tsx` (built generic for reuse in M2 + M3).
4. Mount: `OverDistributionTab.tsx` in `Bowling.tsx` tab strip.
5. Integration test + regression flip: `tests/integration/over_distribution_chart.sh` — load `/bowling?player=462411b3&tournament=IPL`, click `By Over`, verify 20 bars rendered, verify mix sums to ~100%, verify econ tick at over 20 matches API's `cohort_economy[20]`. Regression flip on `tests/regression/bowler_distribution/urls.txt` for the shape change on `/summary`.

### M2 — Batting (~5 commits)

Same shape. `playerscopestatsposition` source, 10 buckets, SR-only performance chart.

### M3 — Fielding (~5 commits, +1 if keeper-detection needs derived column)

Same shape but cohort partitioned by `is_keeper`. Single-rate performance chart (catches/match).

**Total:** ~15 commits across three tiers.

---

## 6. Acceptance criteria (lock by integration test per tier)

### M1 — Bowling, Bumrah IPL all-time

- Mix histogram renders **bimodal**: powerplay (overs 1-2, ~15% each) + death (overs 18-20, ~10% each), middle overs near-zero.
- Performance chart top panel (economy): powerplay bars ~6-7 with cohort tick ~7-8 (Bumrah below cohort = tight); death bars ~7-8 with cohort tick ~9-10 (Bumrah well below cohort = elite at death).
- Performance chart bottom panel (wickets/innings): death overs spike noticeably above cohort.

### M2 — Batting, Kohli IPL all-time

- Mix histogram renders a single-tall-bar at #3 (~60-70%), opener bar ~15-20% (early career), tail bars near-zero.
- Performance chart: per-position SR at #3 within ~5pp of cohort #3 SR.

### M3 — Fielding, Kohli IPL all-time

- Mix histogram tilts toward middle/lower-order (boundary fielding patterns; openers go mostly to keepers + slips).
- Performance chart: catches/match at middle-order positions matches outfielder cohort within typical variance; opener bar near-zero with cohort tick visible.

---

## 7. Out of scope

- **Impact-weighted fielding score** (originally proposed in `spec-fielding-impact.md`) — needs a weighting-scheme design decision orthogonal to the histogram visualisation. Separate spec.
- **Per-over fielding** — no existing precomp; new child table would be required.
- **N-way compare-grid mini-histograms** — the compare-tab shows aggregates today; adding per-bucket sparks is its own design call.
- **Phase-banded aggregates** (powerplay vs cohort, etc.) — already exists via `/players/{id}/by-phase` endpoints. Different surface.

---

## 8. Related work

- `spec-player-compare-average.md` (shipped) — original deferral source.
- `spec-player-baseline-parity.md` (shipped) — established per-bucket cohort tables this spec consumes.
- `spec-prob-baselines.md` (shipped) — same mix-weighted pattern at probability grain.
- `d9a7bc0` (ScopedPageHeader COHORT line) — surfaced the mix as a claim; this spec surfaces it as a chart.
