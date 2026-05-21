# Probability-Chip Cohort Baselines Spec
**Status:** Draft, 2026-05-21. **Triggered by:** Kohli IPL audit on 2026-05-21 — under the new position-weighted batting cohort (T1 of `spec-apples-to-apples- baselines.md`), Kohli's strike-rate sat ~at cohort (−0.3% delta) but his 50s/Inn was +43.8%. User noted: "he wins on 50s/inn vs this cohort, and maybe even P(≥50│≥30)." Probability chips today render the player's prob with NO cohort comparison — making them the next natural surface for the apples-to-apples treatment.

This spec adds **the same position-weighted (batting), over-weighted (bowling), keeper-binary (fielding) cohort baselines we already use everywhere else** (`spec-apples-to-apples-baselines.md` Tiers 1-3) — applied to every ProbChip on the Distribution panels. **No new cohort definitions.** Kohli's `P(≥50)` gets compared to other top-order batters at the same scope (his position-mix-weighted peers), not the all-batters pool.

The spec also lays out the chip layout for showing `value · base · Δ` inside a pill without crowding. {>>Re c7: clarified — same cohorts as apples-to-apples, no redefinition. The position/over/keeper-mix weighting is the standard one from Tiers 1-3.<<}{id="c8" by="AI" at="2026-05-21T15:22:49.000Z" re="c7"}

* * *
## 1. Where probability chips render today
`grep -rn ProbChip frontend/src/components/`:

| Page | Chip group | Chips | Probability axis |
|---|---|---|---|
| `/batting` (BatterDistributionPanel) | Runs milestones | `P(≤10)` `P(≥30)` `P(≥50)` `P(≥100)` `P(≥50│≥30)` `P(≥70│≥50)` | per-innings runs |
| `/bowling` (BowlerStatStrips) | Wickets | `P(0)` `P(≥1)` `P(≥2)` `P(≥3)` `P(≥4)` `P(≥5)` `P(≥3│≥2)` `P(≥4│≥2)` `P(≥5│≥2)` | per-spell wickets |
| `/bowling` (BowlerStatStrips) | Economy | `P(econ≤6)` `P(≤7)` `P(≥9)` `P(≥10)` | per-spell economy |
| `/bowling` (BowlerStatStrips) | Runs conceded | `P(≤15)` `P(≤25)` `P(≥40)` `P(≥50)` | per-spell runs conceded |
| `/fielding` (FielderChipsRow) | Catches per match | `P(=0)` `P(=1)` `P(≥2)` | per-match catches |
| `/teams/...` (team Distribution panels) | Mirrors above | **Deferred to follow-up spec** (see §10) | per-innings (team), per-bowl, per-match |

All three player-discipline panels are mounted on `/players` indirectly via the dossier-context sparkline (Tier 6 wiring) — but the chips themselves render on the deep-dive pages.

* * *
## 2. The principle
> A probability chip says "Kohli's P(≥50) is 28%". The reader's silent question is **28% compared to what?** Today the answer is implicit — the chip shows a percentage with no reference. We've already committed to position-weighted comparisons everywhere else (Tier 1-6). Probability chips are the same comparison applied to a different metric family.

Cohort baseline per chip = the **expected probability for a position/over/keeper-matched peer at the same scope** — NOT the all-batsmen / all-bowlers / all-fielders pool.

Concretely for batting: for Kohli at IPL all-time (mix ≈ 52% opener, 34% #3, …), the cohort `P(≥50)` is **what the position-weighted average of opener/#3/#4 batters does at the same scope** (≈ 17%) — NOT what every IPL batter from #1 to #11 does (≈ 11%). Same logic for bowling over-mix and fielding keeper-binary.

Computation mirrors the existing rate path (the cv-on-per-bucket-rates pattern, same as `spec-apples-to-apples-baselines.md` Tier 1):

- Per-(person, scope, position-bucket) prob = milestone-count / innings-count, computed at the **bucket** grain. So per-bucket `P(≥50)` for openers = `(fifties + hundreds at bucket 1) / (innings at bucket 1)` across the cohort population.
- Aggregate cohort per-bucket prob = SUM(milestone) / SUM(innings) **across all peers who batted in that bucket**. One per-bucket rate per position.
- Convex-combine by the **subject's** position-mix → `scope_avg` for the chip. Kohli's mix heavily weights bucket 1 + bucket 2, so his baseline is dominated by opener + #3 cohort rates.
- Cliff: any bucket the player has mix > 0 on with cohort sample < threshold ⇒ `scope_avg = null` (strict cliff, same as Tier 1).

**The cohort never includes batters outside Kohli's deployment.** If Kohli has 0 innings at #8, the bucket-8 cohort rate enters the convex combination with weight 0 — its value doesn't matter.

**No new schema axis.** All position-bucketing reuses `playerscopestatsposition` (batting) / `playerscopestatsover` (bowling) / keeper-binary partition (fielding) — the same children that already drive Tier 1-6 cohort rates. **No comparing-to-all-batsmen anywhere.**
  

* * *
## 3. Data we have vs. data we need
### 3.1 Batting per-innings milestones (Tier 1 columns)
| Milestone | Have? | Source |
|---|---|---|
| `P(≥30)` | ✓ | `(thirties + fifties + hundreds) / innings` per (person, scope, position) |
| `P(≥50)` | ✓ | `(fifties + hundreds) / innings` |
| `P(≥100)` | ✓ | `hundreds / innings` |
| `P(≥50│≥30)` | ✓ | divide the two |
| `P(≤10)` | **✗** | no `single-digit-and-out` column |
| `P(≥70│≥50)` | **✗** | no `seventies` column |
| `P(duck)` | ✓ | already shipped as `ducks_per_innings` |

**Schema additions needed (T1-style ALTER on** `playerscopestatsposition`**):**

```sql
ALTER TABLE playerscopestatsposition ADD COLUMN single_digits INTEGER NOT NULL DEFAULT 0;
-- innings where runs <= 9 (ducks included; ducks AND non-ducks under 10)
ALTER TABLE playerscopestatsposition ADD COLUMN seventies     INTEGER NOT NULL DEFAULT 0;
-- innings where 70 <= runs < 100  (so the bucket "≥70" = seventies + hundreds)
```

Populate extension in `populate_playerscopestats_position.py` — extends the existing milestone post-pass:

```python
if runs >= 100:
    acc.hundreds += 1
elif runs >= 70:
    acc.seventies += 1
elif runs >= 50:
    acc.fifties += 1
elif runs >= 30:
    acc.thirties += 1
if runs <= 9:
    acc.single_digits += 1   # includes ducks
if runs == 0 and (pid, iid) in innings_dismissed:
    acc.ducks += 1
```

Same idempotent-ALTER + per-bucket conservation patterns as Tier 1.
### 3.2 Bowling per-spell milestones
The existing `playerscopestatsover` table carries `wickets`, `maidens`, `four_wicket_hauls`, `innings_bowled` per (person, scope, over). For the wicket-ladder probabilities we need per-spell milestone counts — innings where the bowler took ≥1, ≥2, ≥3 wickets.

| Milestone | Have? | Notes |
|---|---|---|
| `P(0)` / `P(≥1)` | derivable | `wickets_per_innings_at_bucket` from T2's per-bucket rate is *expected* wickets, not P(≥1). For probabilities we need per-spell event counts. |
| `P(≥3)`, `P(≥4)`, `P(≥5)` | **✗** | T2's `four_wicket_hauls` is the only milestone count we store; nothing for 3-fers, 5-fers. |
| `P(econ ≤ X)`, `P(econ ≥ X)` | **✗** | per-spell economy thresholds aren't aggregated; would require per-spell binning |

**Schema additions needed on** `playerscopestatsover`**:**

```sql
ALTER TABLE playerscopestatsover ADD COLUMN three_wicket_hauls    INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN five_wicket_hauls     INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_with_wicket   INTEGER NOT NULL DEFAULT 0;
-- P(≥1) per bucket = innings_with_wicket / innings_bowled
ALTER TABLE playerscopestatsover ADD COLUMN innings_with_two      INTEGER NOT NULL DEFAULT 0;
```

For economy/runs-conceded distributions, the design choice is:

- **Option A:** add fixed-bucket count columns (e.g. `innings_econ_leq_6`, `innings_econ_geq_9`). Cheap but locks the thresholds at populate time.
  
- **Option B (deferred):** new sibling table `playerscopestatsoverhist` keyed by (person, scope, over, econ_bucket) with arbitrary binning. Heavier; only worth it if we ever want user-adjustable thresholds.
  

**Pick A** for this spec — the four econ thresholds (≤6, ≤7, ≥9, ≥10) and four runs-conceded thresholds (≤15, ≤25, ≥40, ≥50) are stable across the codebase.

```sql
ALTER TABLE playerscopestatsover ADD COLUMN innings_econ_leq_6   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_econ_leq_7   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_econ_geq_9   INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_econ_geq_10  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_runs_leq_15  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_runs_leq_25  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_runs_geq_40  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE playerscopestatsover ADD COLUMN innings_runs_geq_50  INTEGER NOT NULL DEFAULT 0;
```

(`leq` thresholds also require `min_balls`-style qualifier — a 6-ball spell at 5 econ shouldn't count as "≤6 over a full spell". Defer the qualifier definition to the populate pass; spec section §7.)
### 3.3 Fielding per-match milestones
We already have `catches`, `run_outs`, `stumpings`, `caught_and_bowled` per (person, scope) in `PlayerScopeStats`. Per-match probabilities (P(=0), P(=1), P(≥2)) need per-(person, scope, match) milestone attribution — we don't currently store that. Today the chips are client-derived from the per-match observations array in `/fielders/{id}/distribution` (lifetime sample).

For the cohort cross-check we'd need to aggregate at population: "across all outfielders at this scope, what fraction of (player × match) cells had ≥2 catches?"

**Schema addition needed:** a `(person, scope) → catches-per-match distribution` aggregate. Since fielding distribution is heavy on zeros (P(=0) ≈ 60-65% for outfielders), a simple per-bucket count is fine:

```sql
-- New child table
CREATE TABLE playerscopestats_fielding_catch_dist (
  person_id      TEXT NOT NULL,
  scope_key      TEXT NOT NULL,
  matches_with_0 INTEGER NOT NULL DEFAULT 0,
  matches_with_1 INTEGER NOT NULL DEFAULT 0,
  matches_with_ge2 INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (person_id, scope_key)
);
```

Same for run-outs (much rarer — `matches_with_0` essentially equals total matches; `matches_with_1` and `_with_ge2` rare). Same for stumpings on keepers only.

* * *
## 4. Endpoint changes
### 4.1 Reuse existing envelopes; add `_baseline` fields on `ProbRecord`
`frontend/src/types.ts ProbRecord`:

```ts
// Current:
export interface ProbRecord {
  value: number | null
  num: number
  denom: number
  ci_low: number | null
  ci_high: number | null
}

// Proposed:
export interface ProbRecord {
  value: number | null
  num: number
  denom: number
  ci_low: number | null
  ci_high: number | null
  // Cohort baseline at the active scope (position-weighted batting,
  // over-weighted bowling, keeper-binary fielding). Null when
  // below-cliff. Mirrors MetricEnvelope.scope_avg.
  scope_avg?: number | null
  delta_pct?: number | null  // (value - scope_avg) / scope_avg × 100
  // direction tag for the chip:
  //   'higher_better' → P(≥50), P(≥100), P(econ ≤6)
  //   'lower_better'  → P(duck), P(econ ≥10)
  //   null            → P(=0), P(=1) (no orientation)
  direction?: 'higher_better' | 'lower_better' | null
  sample_size?: number  // cohort sample for the tooltip
}
```

Server-side: every endpoint that emits a ProbRecord today gets extended to fill the new fields from the position/over/keeper-weighted cohort path.

| Endpoint | Probabilities to enrich |
| --- | --- |
| `/batters/{id}/distribution` | runs milestones (lifetime + window slices) |
| `/bowlers/{id}/distribution` | wickets / economy / runs-conceded ladders |
| `/fielders/{id}/distribution` | catches / run-outs / stumpings per-match |

Team-grain endpoints (`/teams/{name}/{batting,bowling,fielding}/distribution`) carry the same ProbRecord shape and will receive the same treatment in the follow-up spec — see §10.
### 4.2 Computation pattern (shared helper)
In `api/routers/scope_averages.py`, add helpers:

```python
def prob_cohort_batting(db, filters, mix, milestone_pred, drop_set=None):
    """Position-weighted P(milestone) baseline.

    milestone_pred is a callable mapping a per-bucket row to (numerator,
    denominator). For P(≥50): num = fifties+hundreds, denom = innings.
    For P(≥50│≥30): two queries, divide cv(num/denom) pairs.

    Returns the convex-combined probability + cliff-buckets.
    """
```

Mirror for bowling (over-mix) and fielding (keeper-binary).
### 4.3 Conditional probabilities
`P(≥50│≥30)` = `P(≥50) / P(≥30)` for the player **but NOT for the cohort** — the cohort conditional must be computed at the cohort grain:

```
cohort_P(≥50│≥30) = SUM(fifties+hundreds) / SUM(thirties+fifties+hundreds)
                    at each bucket → cv by mix
```

i.e. compute `cohort_P(≥50│≥30)_at_bucket = (fifties+hundreds) / (thirties+fifties+hundreds)` per bucket, then convex-combine.

NOT cv(P(≥50)) / cv(P(≥30)) — the ratio of weighted averages is not the weighted average of ratios.

* * *
## 5. Chip visual design — fitting baseline into a pill
The current chip:

```
┌───────────────────────┐
│ P(≥50)         28%    │  ← serif label · bold number
└───────────────────────┘
```

The challenge: adding `base · Δ` text inside the pill makes it crowded — pills are ~7rem wide today. Three design options:
### Option A — `value · base · Δ` triplet inside the pill
```
┌─────────────────────────────────────┐
│ P(≥50)   28%  vs 17%  ↑+65%         │
└─────────────────────────────────────┘
```

**Pros:** all info in one place, scan-friendly. **Cons:** pill widens to ~12-14rem; row of 6 chips on /batting overflows on mobile (we already had to wrap them in `flex-wrap: wrap`); the arrow color (red/green polarity) inside a colored pill clashes with the chip's tier tint.
### Option B — value in pill, base + Δ on hover tooltip
```
┌───────────────┐
│ P(≥50)   28%  │  title="P(≥50) = 28% · cohort 17% (+65%) · 95% CI [22.4-34.8], n=272"
└───────────────┘
```

**Pros:** pill unchanged; preserves desktop + mobile layout. **Cons:** delta isn't glanceable — user must hover/long-press to compare. Critical info (the comparison) is hidden behind interaction.
### Option C — value in pill, base + Δ as small caption below pill
```
┌───────────────┐
│ P(≥50)   28%  │
└───────────────┘
   vs 17% ↑+65%        ← small caption, italic, faint
```

**Pros:** comparison glanceable; pill stays compact; tier tint unaffected. **Cons:** vertical density grows ~30% (each chip is now ~2 lines tall); chip-row height changes need a re-pass on Distribution panel layout.
### Option D — value in pill, polarity tint shift on the pill itself
```
┌───────────────┐        ┌───────────────┐
│ P(≥50)   28%  │   →    │ P(≥50)   28%  │   (greener border if above cohort)
└───────────────┘        └───────────────┘
```

**Pros:** zero layout change; delta encoded as visual saturation. **Cons:** loses the existing per-tier tint signal (chip color currently encodes the bucket's outcome tier, not the comparison); not discoverable for new readers.
### Decision: **Option C** (caption below pill) {>>Re c1: locked. Options A/B/D kept above as design context; implementation tracks C.<<}{id="c9" by="AI" at="2026-05-21T15:22:49.000Z" re="c1"}
Rationale:

- Preserves the **tier color** = bucket outcome contract (the chip pill already says "this metric is good/bad/neutral" via tint).
  
- Caption uses the existing **oxblood text** convention for inline deltas (matches `MetricDelta` on stat cards).
  
- The vertical-density cost is one-time; with `gap` already at `0.4rem` between rows the extra ~0.5rem per chip row reads comfortably.
  
- Glanceable comparison is the whole point of the spec — Option B fails that test.
  

**Visual mockup of Option C on the /batting milestone strip:**

```
P(≤10)       P(≥30)       P(≥50)       P(≥100)     P(≥50│≥30)   P(≥70│≥50)
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────┐  ┌─────────┐
│   24%  │  │   49%  │  │   28%  │  │    3%  │  │   56%   │  │   47%   │
└────────┘  └────────┘  └────────┘  └────────┘  └─────────┘  └─────────┘
 vs 31%      vs 39%      vs 18%      vs 1.2%     vs 46%       vs 39%
 ↓-22%       ↑+26%       ↑+56%       ↑+150%      ↑+22%        ↑+21%
```

Polarity rules for the arrow + color:

- `direction = 'higher_better'`: ↑ green, ↓ oxblood.
  
- `direction = 'lower_better'`: invert — ↓ green, ↑ oxblood.
  
- `direction = null`: no arrow, no color, just `± Δ%`.
  

Below-cliff (cohort sample too thin) → caption reads `vs — (below sample)` in faint italic, no arrow.

* * *
## 6. Direction tags
| Chip | Direction |
| --- | --- |
| Batting `P(≤10)`, `P(duck)` | lower_better |
| Batting `P(≥30)`, `P(≥50)`, `P(≥100)`, `P(≥50│≥30)`, `P(≥70│≥50)` | higher_better |
| Bowling `P(0)` | lower_better |
| Bowling `P(≥1)`, `P(≥2)`, `P(≥3)`, `P(≥4)`, `P(≥5)`, all `≥X│≥2` | higher_better |
| Bowling `P(econ ≤6)`, `P(econ ≤7)` | higher_better |
| Bowling `P(econ ≥9)`, `P(econ ≥10)`, `P(runs ≥40)`, `P(runs ≥50)` | lower_better |
| Bowling `P(runs ≤15)`, `P(runs ≤25)` | higher_better |
| Fielding `P(=0)` | lower_better |
| Fielding `P(=1)` | null (descriptive, not directional) |
| Fielding `P(≥2)` | higher_better |

* * *
## 7. Phasing
5 tiers, all independent of each other except T1 (the position child schema additions) is a precondition for T2-T5 to read clean cohort counts:

| Tier | What | Commits |
| --- | --- | --- |
| **PT1.S/P** | `playerscopestatsposition` + `single_digits` + `seventies` columns; populate extension | 1 + 1 |
| **PT1.B** | Cohort baseline fields in `ProbRecord` (server) for batting milestones + sanity tests + regression flip/lock | 3   |
| **PT2.SP** | `playerscopestatsover` wicket-ladder columns + populate | 2   |
| **PT2.B** | Bowling wicket-prob cohort + sanity + regression | 3   |
| **PT3.SP** | `playerscopestatsover` economy/runs-conceded threshold columns + populate | 2   |
| **PT3.B** | Bowling econ/runs-conceded prob cohort + sanity + regression | 3   |
| **PT4.SP** | New `playerscopestats_fielding_catch_dist` table + populate | 2   |
| **PT4.B** | Fielding per-match prob cohort + sanity + regression | 3   |
| **PT5.F** | Frontend: extend `ProbChip` props (`scopeAvg`, `deltaPct`, `direction`); render Option C caption; update consumers (4 panels × 3 disciplines) | 3   |
| **PT5.T** | Integration test asserting cohort caption renders on every chip row at a stable scope | 1   |

Total: **~24 commits**. Roughly the size of the apples-to-apples spec.

Same flip-before-shape-change regression discipline as the prior specs.

* * *
## 8. Decisions (was: open questions) {>>Re c2/c3/c4/c5/c6: all decided in review pass 2026-05-21. Promoted from "open question" to "decided". Teams explicitly deferred to a follow-up spec (see §10).<<}{id="c10" by="AI" at="2026-05-21T15:22:49.000Z" re="c3"}
1. **Min-balls qualifier on bowling econ probs —** `min_balls = 12`**.** "P(econ ≤ 6) over X overs" needs a per-spell minimum-overs cutoff or the prob is noise from 1-ball spells. The existing chip uses the distribution panel's `min_balls=12` qualifier (same threshold that gates the histogram). At cohort populate time we apply the same threshold — only count spells of ≥ 12 legal balls into the threshold-count columns.
  
2. **Cohort cliff threshold — reuse** `spec-player-compare-average.md §6` **per-bucket thresholds.** Same numbers, same semantics as Tiers 1-3.
  
3. `P(=1)` **direction — skip the caption.** Fielding `P(=1)` per match is descriptive (most non-keepers' matches are 0 or 1 catches); no orientation to compare against. `direction = null` → no caption rendered. All other chips render captions.
  
4. **Mobile layout — accept the ~30% row growth.** Option C's caption-below-pill design adds one short caption line per chip. Mandatory mobile-viewport check (390×844 per CLAUDE.md) is part of PT5.F acceptance. Worst-case fallback: smaller caption font (`0.65rem`) on mobile.
  
5. **Teams deferred — player-only this spec.** Team Distribution panel ProbChips use the same `ProbRecord` envelope, but the cohort source is team-grain (`bucket_baseline_*` vs `playerscopestats*`). Wiring teams adds ~6-8 commits (parallel populate + endpoint surfaces) without sharing the player-side work. Defer to a follow-up `spec-prob-baselines-teams.md` once the player path lands and the chip layout is validated in production. See §10.
  

* * *
## 9. Acceptance criteria (Kohli IPL all-time, last 3)
Mirror of `spec-apples-to-apples-baselines.md §6` — fix the SAME audit subject + scope so we can compare directly:

| Field | IPL all-time | IPL last 3 | Sense check |
| --- | --- | --- | --- |
| `P(≥50)` Kohli | 28% | 44% | Kohli's own |
| `P(≥50)` cohort | ~17% (top-order) | ~24% (opener) | Top-order P(50) ≈ 17% per IPL data; opener-only cohort tighter |
| `P(≥50)` delta | ~+65% | ~+85% | Confirms user's "wins on 50s/inn" observation |
| `P(≥100)` cohort | ~1.2% | ~3.3% | Position-weighted |
| `P(≥50│≥30)` cohort | ~46% | ~55% | Conditional cohort built at cohort grain (NOT cv ratio) |
| `P(≤10)` cohort | ~31% | ~21% | New column required |

User's "maybe even P(≥50│≥30)" check should resolve to: Kohli +20-30% on the conditional. If we ship and the number lands below +10% we should sanity-check the cohort denominator construction.

* * *
## 10. Out of scope
- **Team-grain prob chips.** Team Distribution panels (`/teams/.../{batting,bowling,fielding}/distribution`) carry the same `ProbRecord` shape, but the cohort source is team-grain (`bucket_baseline_*` aggregates, not `playerscopestats*` per-bucket children). Ship player-side first; once the chip layout is validated in production, follow up with `spec-prob-baselines-teams.md`. Estimated ~6-8 commits in the follow-up: parallel populate path + team endpoint surfaces + same Option C frontend pass.
  
- **Window-slice cohorts.** Today the player's prob is computed both for lifetime and for `last_10` / `last_60d` etc. Cohort baselines scale identically? Defer; ship lifetime cohort first, see if per-window cohort is worth the second roundtrip.
  
- **Confidence-interval comparison.** Could show whether the player's CI overlaps the cohort point estimate. Useful but a sub-feature; add later.
  
- **Compare-grid probs.** Compare-grid currently doesn't show prob chips; if added, the same envelope flows in. No work here.
