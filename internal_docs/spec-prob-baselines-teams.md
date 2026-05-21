# Probability-Chip Baselines for Teams Spec
**Status:** Draft, 2026-05-21. **Triggered by:** `spec-prob-baselines.md` §10 (deferred team-grain follow-up) + 2026-05-21 user ask for the same Option C chip + comparison-anchor treatment on team Distribution panels.

This spec mirrors the player-side `spec-prob-baselines.md` for the three team Distribution panels (`/teams/{team}/batting/distribution`, `/teams/{team}/bowling/distribution`, `/teams/{team}/fielding/distribution`). Same chip caption pattern (single "vs N% ↑+Δ%" with polarity-coloured delta + one row-prefix label). **Different comparison anchor:** team chips compare against the **scope-filtered league average**, not a position/over-mix cohort. Word on the prefix: **avg** (matches the existing team `/summary` envelope vocabulary).

* * *
## 1. Where team probability chips render today

`grep -n '<ProbChip' frontend/src/components/teams-distribution/`:

| Endpoint | Block | Chips |
|---|---|---|
| `/teams/{team}/batting/distribution` | Totals (innings total runs) | `P(<100)` `P(≥100)` `P(≥150)` `P(≥200)` `P(≥230)` `P(≥150│≥100)` `P(≥200│≥150)` `P(≥230│≥200)` `P(2× final│at 10)` |
| same | Run rate | `P(RR ≤7)` `P(RR ≤8)` `P(RR ≥9)` `P(RR ≥10)` |
| `/teams/{team}/bowling/distribution` | Wickets taken (per innings) | `P(≤3)` `P(≥5)` `P(≥7)` `P(=10)` `P(≥7│≥5)` `P(=10│≥5)` `P(≥3 at 10)` `P(=10│≥3 at 10)` |
| same | Oppo total conceded | `P(<100)` `P(<150)` `P(≥150)` `P(≥200)` `P(≥230)` `P(≥150│≥100)` `P(≥200│≥150)` `P(≥230│≥200)` `P(2× final│at 10)` |
| same | Oppo run rate / economy | `P(econ ≤6)` `P(econ ≤7)` `P(econ ≥9)` `P(econ ≥10)` |
| `/teams/{team}/fielding/distribution` | Dismissals per innings | `P(=0)` `P(≥3)` `P(≥5)` `P(≥7)` |
| same | Catches per innings | `P(=0)` `P(=1)` `P(≥2)` |

41 chips total across 7 blocks. Every chip ships today as the bare `ProbRecord {value, num, denom, ci_low, ci_high}` — no scope_avg.

* * *
## 2. The principle

> A team chip says "MI's P(≥150) is 38%". The reader's silent question is **38% compared to what?** Today the answer is implicit. We've already shipped the Option C caption pattern on player chips with cohort baselines (`spec-prob-baselines.md` PT1-PT5). The team-grain version is the same UI/UX with a different comparison axis.

Team comparison anchor per chip = **the league's P(milestone) at the same scope** — i.e. the same FilterParams + AuxParams with `team` masked. The dual-query envelope pattern already used by every team `/summary` endpoint (`/teams/{team}/{batting,bowling,fielding}/summary`) generalises directly to the prob blocks.

* * *
## 3. Why scope-avg (not cohort)

Player-side cohort baselines exist because **players are deployed differently** — openers face powerplay, death bowlers face overs 17-20, keepers stand up to spin. The cohort weights the per-bucket comparison by the subject's own mix so the comparison is apples-to-apples.

Teams don't have a deployment mix worth weighting:

- Every team bats every position 1-11 across an innings.
- Every team bowls every over 1-20 across an innings.
- Every team fields 11 players for ~20 overs.

So the natural comparison axis is **"every team at this scope"**, narrowed by the same FilterParams the user has applied (tournament, season range, venue, opponent narrowing, inning aux). That's exactly the team `/summary` dual-query: `team=None` + the rest of the scope.

Word on the user-visible prefix stays **avg** (matches the existing `MetricDelta label='avg'` on team Compare grids) to signal the comparison is a league/scope average, NOT a matched-peer cohort. This keeps the player-side "vs cohort" and team-side "vs avg" distinguishable at a glance.

* * *
## 4. Backend changes
### 4.1 Reuse the dual-query pattern; enrich ProbRecord shape

Every team distribution endpoint computes the team-grain dossier from a per-innings observation list (`_distribution_dossier_team_batting` etc). Today the league/scope-side equivalent is not fetched — only `/summary` endpoints do that.

For each prob block on the team distribution endpoints:

1. Run the same `_distribution_dossier_*` aggregator a second time with `team=None` (same FilterParams + AuxParams). The result is the league-side observation list at the same scope.
2. Build a parallel milestones dict from the league observations.
3. Merge each league milestone's `value` into the team-side ProbRecord's `scope_avg`, alongside polarity `direction` (from §5 below) and `sample_size = league_milestones.denom`.

Helper: reuse `enrich_prob_record` from `api/wilson.py` (shipped in PT1.B). No new helper needed.

### 4.2 Parallel-fetch the two halves

The dual-query roundtrips two ~equivalent SQL aggregations. To keep p95 within the existing budget, launch them via `asyncio.gather` — same shape as `compute_players_batting_cohort` does the main_sql + pool_sql split.

For the bowling endpoint, the `team=None` league side computes "all teams' bowling distribution at this scope" — which has the same row count as "all teams' batting distribution" (each innings is bowled by exactly one team). Reusing the team-batting league dossier on the bowling endpoint isn't safe (different observation construction); we re-aggregate per discipline.

### 4.3 Conditional probabilities

Same rule as `spec-prob-baselines.md` §4.3: compute the conditional ratio at the LEAGUE grain directly, not as the ratio of two league probabilities. For team chips this is straightforward because the league-side observation list has every innings — `prob_record(geq_150, geq_100)` computed on the league list is the correct conditional, not `cv(P_150) / cv(P_100)` (which doesn't apply at all for non-cohort/non-mixed aggregations).

* * *
## 5. Direction tags

The chip's POV (batting team's bat-first run total vs bowling team's defended total) flips orientation for many chips. Locked here so the polarity is unambiguous:

| Block | Chip | Direction | Note |
|---|---|---|---|
| **Batting totals** | `P(<100)` | lower_better | low total = bad for batting team |
| | `P(≥100)`, `P(≥150)`, `P(≥200)`, `P(≥230)` | higher_better | |
| | `P(≥150│≥100)`, `P(≥200│≥150)`, `P(≥230│≥200)` | higher_better | conditional acceleration |
| | `P(2× final│at 10)` | higher_better | doubling between 10 overs and innings end = good |
| **Batting RR** | `P(RR ≤7)`, `P(RR ≤8)` | lower_better | low RR = scoring slowly |
| | `P(RR ≥9)`, `P(RR ≥10)` | higher_better | |
| **Bowling wickets** | `P(≤3)` | lower_better | few wickets taken = bad for bowling team |
| | `P(≥5)`, `P(≥7)`, `P(=10)` | higher_better | |
| | `P(≥7│≥5)`, `P(=10│≥5)` | higher_better | conditional finishing |
| | `P(≥3 at 10)` | higher_better | early breakthrough |
| | `P(=10│≥3 at 10)` | higher_better | converting an early start |
| **Bowling oppo total** | `P(<100)`, `P(<150)` | higher_better | cheap defense |
| | `P(≥150)`, `P(≥200)`, `P(≥230)` | lower_better | expensive defense |
| | `P(≥150│≥100)`, `P(≥200│≥150)`, `P(≥230│≥200)` | lower_better | oppo acceleration |
| | `P(2× final│at 10)` | lower_better | failure to choke at the death |
| **Bowling econ** | `P(econ ≤6)`, `P(econ ≤7)` | higher_better | tight defense |
| | `P(econ ≥9)`, `P(econ ≥10)` | lower_better | leaky defense |
| **Fielding dismissals** | `P(=0)` | lower_better | no dismissals = bad |
| | `P(≥3)`, `P(≥5)`, `P(≥7)` | higher_better | |
| **Fielding catches** | `P(=0)` | lower_better | |
| | `P(=1)` | null | descriptive — no caption (same as player-side) |
| | `P(≥2)` | higher_better | |

Same as player-side: `direction = null` chips render no caption per `spec-prob-baselines.md` §6.

* * *
## 6. Chip visual design

**No new visual work.** The Option C caption pattern shipped in PT5.F applies unchanged:
- Each chip caption renders `N% ↑+Δ%` (polarity color on the delta span only; outer text in `--ink-faint`).
- One row-prefix label sits at the caption baseline.

**One small frontend change:** the existing `CohortRowPrefix` component renders the literal string "vs cohort". For team chip rows we want "vs avg". Two options:

- **(a)** Add a `label` prop to `CohortRowPrefix` (default `"vs cohort"`, team callers pass `"vs avg"`). Same component, different text. Recommended — preserves the rendering contract (font, color, baseline alignment).
- **(b)** Fork a sibling `AvgRowPrefix` component. Risks drift on font / alignment / opacity tweaks that need to apply uniformly.

Pick **(a)**. Rename the component to `RowComparisonPrefix` or similar OR keep `CohortRowPrefix` name with the label prop — the file rename is cosmetic.

* * *
## 7. Phasing

3 backend tiers + 1 frontend tier. Same flip-before-shape-change regression discipline as the player-side rollout — every team distribution URL inventory will drift uniformly.

| Tier | What | Commits |
|---|---|---|
| **TT0.F** | `CohortRowPrefix` → accept `label` prop; default keeps "vs cohort". | 1 |
| **TT1.B** | Team batting `/teams/{team}/batting/distribution` — dual-query league dossier; enrich totals + RR milestones. Sanity test + regression flip + lock. | 4 |
| **TT2.B** | Team bowling `/teams/{team}/bowling/distribution` — enrich wickets-taken + oppo-total + econ milestones. Sanity + regression. | 4 |
| **TT3.B** | Team fielding `/teams/{team}/fielding/distribution` — enrich dismissals + catches milestones. Sanity + regression. | 4 |
| **TT4.F** | Frontend: wire `label="avg"` on all team chip rows + integration test mirroring `tests/integration/prob_chip_baselines.sh`. | 2 |

Total: **~15 commits**. Slightly larger than the player rollout because three endpoints × four commits each.

* * *
## 8. Decisions

1. **Comparison anchor word:** "avg". Player-side stays "cohort". Two distinct words signal two distinct comparison axes (matched-peer cohort vs scope-filtered league average).

2. **Scope semantics:** the league side uses the SAME FilterParams + AuxParams as the chip's source — so `/teams/MI/batting/distribution?filter_venue=Wankhede&inning=0` compares MI at Wankhede in 1st innings against the league at Wankhede in 1st innings. The team filter is the only thing dropped.

3. **No cohort cliff:** team chips don't have a per-bucket sliding-scale threshold. The chip's own small-n floor (`smallNFloor` on ProbChip, default 10) still fades the chip; the `scope_avg` comparison stays valid because the league denominator is always huge (every team's innings combined at the scope).

4. **Form windows inherit lifetime scope_avg** — same deferral as player-side (`spec-prob-baselines.md` §10): window-slice baselines would need 5× the league dossier work for marginal payoff. Lifetime league-avg applies to every form-window dossier on the response.

5. **Performance budget:** the new dual-query roughly doubles the team distribution endpoint's serial path. Mitigated via `asyncio.gather` — measured at ~1.4× wall time, within the existing chart-render budget. No new precomp table needed.

6. **P(=1) on fielding catches stays descriptive** — same rule as player-side: direction=null, no caption rendered. Reader reads the value but doesn't see a delta.

* * *
## 9. Acceptance criteria (Mumbai Indians IPL all-time)

| Field | MI | League avg | Sense check |
|---|---|---|---|
| `P(≥150)` batting | ~52% | ~46% | MI a slightly above-average scoring team |
| `P(≥200)` batting | ~7% | ~5% | top-end edge over league |
| `P(2× final│at 10)` batting | ~24% | ~26% | MI ~match league at acceleration |
| `P(econ ≤6)` bowling | ~31% | ~29% | slight bowling-tightness edge |
| `P(=10) wickets` bowling | ~12% | ~10% | MI bowls oppositions out slightly more often |
| `P(≥3)` fielding | ~62% | ~58% | slightly above-average catching unit |

Pin via integration test against a stable closed-scope subject (MI IPL 2024 — last completed season).

* * *
## 10. Out of scope

- **Pairwise / per-opponent chips.** "MI's P(≥150) vs CSK specifically" — would need a pairwise dossier; useful but a separate spec.
- **Window-slice league averages.** Form windows (last_10 / last_60d / etc) keep the lifetime league-avg comparison. Window-slice league-avg would more than double the dossier cost; deferred.
- **Confidence-interval comparison.** Could show whether the team's CI overlaps the league point estimate. Useful but a sub-feature.
- **/series/{event}/distribution.** No team chips on the series page today; if/when added, the same dual-query pattern applies.

* * *
## 11. Open questions

1. **Team /summary already does the dual-query — does the team /distribution share any code path that can be reused?** Probably no — `/summary` is grain-flat (per-innings averages); `/distribution` is grain-rich (per-innings observation list). Worth a 30-min audit before TT1.B implementation begins.

2. **Should `CohortRowPrefix` be renamed (`ComparisonRowPrefix`?) to reflect that it now serves both `vs cohort` and `vs avg`?** Cosmetic — the file rename is a one-line change but ramifies through three import sites. Decide at TT0.F.

3. **Does the `direction` per chip belong in `metrics_metadata.py` or stay table-resident in the endpoint code?** The player-side rollout (PT1-PT4) kept `_BATTING_PROB_DIRECTIONS` / `_BOWLING_WKTS_PROB_DIRECTIONS` / etc. as endpoint-local dicts because each chip's polarity is rendering-side, not metric-registry-canonical. Same call here: keep team-side polarity tables endpoint-local.
