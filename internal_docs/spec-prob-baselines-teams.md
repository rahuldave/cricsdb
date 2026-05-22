# Probability-Chip Baselines for Teams Spec
**Status:** SHIPPED + DEPLOYED 2026-05-21 (15 commits `08a6035 → a0434ae`). TT0.F / TT1-3.B / TT4.F all landed. Pushed alongside the COHORT/AVG header lines + Distribution-panel window-vs-cohort UX overhaul + hook-rules fix. Memory: `project_prob_baselines_teams_shipped.md`. **Originally triggered by:** `spec-prob-baselines.md` §10 (deferred team-grain follow-up) + 2026-05-21 user ask for the same Option C chip + comparison-anchor treatment on team Distribution panels.

**Review pass 2026-05-21:** decisions §8 c1/c2/c3/c7 confirmed; per-window scope_avg pulled INTO scope (was incorrectly deferred — see §8.4 reply); audit per §11.1 completed and findings landed in §4.1; CohortRowPrefix component decision flipped (don't rename, add a sibling — see §6 + §11.2 reply).

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

1. Run the same `_innings_master_sample_team_*` master-sample helper a second time with `team=None` (same FilterParams + AuxParams). Result is the league-side observation list at the same scope. Then run the same `_distribution_dossier_team_*` aggregator on it.
  
2. Build a parallel milestones dict from the league observations.
  
3. Merge each league milestone's `value` into the team-side ProbRecord's `scope_avg`, alongside polarity `direction` (from §5 below) and `sample_size = league_milestones.denom`.
  

Helper: reuse `enrich_prob_record` from `api/wilson.py` (shipped in PT1.B). No new helper needed.

**Audit findings (per §11.1, 2026-05-21):**

- The three master-sample helpers (`_innings_master_sample_team_batting` / `_bowling` / `_fielding`) take `team: str` positional and SQL-clause it via `_team_innings_clause(filters, team, side=…)`. To support the league side, **extend the signature to `team: Optional[str] = None`** and drop the team clause when None — one-line change in `_team_innings_clause`. Same FilterParams/AuxParams keep their effect.
- The dossier aggregators (`_distribution_dossier_team_batting` etc) are PURE functions of an observation list — no team-id dependency. They run unchanged on the league observation list.
- `bucketbaselinebatting` has `fifties` + `hundreds` columns but no `P(≥150) / P(≥200) / P(≥230) / P(<100)` thresholds; `bucketbaselinebowling` has zero milestone columns. **No existing precomp covers the team prob baselines — the dual-query route is the only one available without adding new bucket-baseline columns.** Computing the league-side milestones at request time is the same SQL the team side already runs (just team-masked) so the path is symmetric — see §4.2 for perf.
### 4.2 Parallel-fetch the two halves
The dual-query roundtrips two ~equivalent SQL aggregations. To keep p95 within the existing budget, launch them via `asyncio.gather` — same shape as `compute_players_batting_cohort` does the main_sql + pool_sql split.

For the bowling endpoint, the `team=None` league side computes "all teams' bowling distribution at this scope" — which has the same row count as "all teams' batting distribution" (each innings is bowled by exactly one team). Reusing the team-batting league dossier on the bowling endpoint isn't safe (different observation construction); we re-aggregate per discipline.
### 4.3 Conditional probabilities
Same rule as `spec-prob-baselines.md` §4.3: compute the conditional ratio at the LEAGUE grain directly, not as the ratio of two league probabilities. For team chips this is straightforward because the league-side observation list has every innings — `prob_record(geq_150, geq_100)` computed on the league list is the correct conditional, not `cv(P_150) / cv(P_100)` (which doesn't apply at all for non-cohort/non-mixed aggregations).

* * *
## 5. Direction tags
The chip's POV (batting team's bat-first run total vs bowling team's defended total) flips orientation for many chips. Locked here so the polarity is unambiguous:

| Block | Chip | Direction | Note |
| --- | --- | --- | --- |
| **Batting totals** | `P(<100)` | lower_better | low total = bad for batting team |
|     | `P(≥100)`, `P(≥150)`, `P(≥200)`, `P(≥230)` | higher_better |     |
|     | `P(≥150│≥100)`, `P(≥200│≥150)`, `P(≥230│≥200)` | higher_better | conditional acceleration |
|     | `P(2× final│at 10)` | higher_better | doubling between 10 overs and innings end = good |
| **Batting RR** | `P(RR ≤7)`, `P(RR ≤8)` | lower_better | low RR = scoring slowly |
|     | `P(RR ≥9)`, `P(RR ≥10)` | higher_better |     |
| **Bowling wickets** | `P(≤3)` | lower_better | few wickets taken = bad for bowling team |
|     | `P(≥5)`, `P(≥7)`, `P(=10)` | higher_better |     |
|     | `P(≥7│≥5)`, `P(=10│≥5)` | higher_better | conditional finishing |
|     | `P(≥3 at 10)` | higher_better | early breakthrough |
|     | `P(=10│≥3 at 10)` | higher_better | converting an early start |
| **Bowling oppo total** | `P(<100)`, `P(<150)` | higher_better | cheap defense |
|     | `P(≥150)`, `P(≥200)`, `P(≥230)` | lower_better | expensive defense |
|     | `P(≥150│≥100)`, `P(≥200│≥150)`, `P(≥230│≥200)` | lower_better | oppo acceleration |
|     | `P(2× final│at 10)` | lower_better | failure to choke at the death |
| **Bowling econ** | `P(econ ≤6)`, `P(econ ≤7)` | higher_better | tight defense |
|     | `P(econ ≥9)`, `P(econ ≥10)` | lower_better | leaky defense |
| **Fielding dismissals** | `P(=0)` | lower_better | no dismissals = bad |
|     | `P(≥3)`, `P(≥5)`, `P(≥7)` | higher_better |     |
| **Fielding catches** | `P(=0)` | lower_better |     |
|     | `P(=1)` | null | descriptive — no caption (same as player-side) |
|     | `P(≥2)` | higher_better |     |

Same as player-side: `direction = null` chips render no caption per `spec-prob-baselines.md` §6.

* * *
## 6. Chip visual design
**No new visual work.** The Option C caption pattern shipped in PT5.F applies unchanged:

- Each chip caption renders `N% ↑+Δ%` (polarity color on the delta span only; outer text in `--ink-faint`).
  
- One row-prefix label sits at the caption baseline.
  

**One small frontend change:** the existing `CohortRowPrefix` component renders the literal string "vs cohort". For team chip rows we want "vs avg". Per §11.2 decision (2026-05-21 review pass): **keep `CohortRowPrefix` unchanged and add a sibling `AvgRowPrefix` component for team-side rows.** Two purpose-specific components rather than one labelled-by-prop component — the user has indicated a third comparison concept is on the way, and keeping each row-prefix tied to a specific comparison axis (cohort = matched-peer-mix, avg = scope-filtered league, future = TBD) leaves the cleanest extension path.

`AvgRowPrefix` is a copy of `CohortRowPrefix` with the literal swapped from "vs cohort" to "vs avg". Same font (`var(--serif)` italic), same color (`var(--ink-faint)`), same `alignSelf: 'flex-end'` for caption-baseline pinning. Drift risk between the two is mitigated by colocating them in the same file or co-located sibling files under `components/distribution/`.

* * *
## 7. Phasing
3 backend tiers + 1 frontend tier. Same flip-before-shape-change regression discipline as the player-side rollout — every team distribution URL inventory will drift uniformly.

| Tier | What | Commits |
| --- | --- | --- |
| **TT0.F** | New `AvgRowPrefix` component (sibling of `CohortRowPrefix`) renders "vs avg". | 1   |
| **TT1.B** | Team batting `/teams/{team}/batting/distribution` — extend master-sample helper signature to `team: Optional[str] = None`; dual-query league dossier (lifetime + per-window slices); enrich totals + RR milestones for lifetime + 4 form windows. Sanity test + regression flip + lock. | 4   |
| **TT2.B** | Team bowling `/teams/{team}/bowling/distribution` — same shape; enrich wickets-taken + oppo-total + econ milestones (lifetime + per-window). Sanity + regression. | 4   |
| **TT3.B** | Team fielding `/teams/{team}/fielding/distribution` — same shape; enrich dismissals + catches milestones (lifetime + per-window). Sanity + regression. | 4   |
| **TT4.F** | Frontend: mount `AvgRowPrefix` on all team chip rows + integration test mirroring `tests/integration/prob_chip_baselines.sh`. | 2   |

Total: **~15 commits**. Each `B` tier does both lifetime AND the 4 form-window slices in the same commit pair (one league observation list, sliced 5 ways — same pattern the team side already does for its own per-window dossier).

* * *
## 8. Decisions
1. {==**Comparison anchor word:**==}{>>agree<<}{id="c1" by="user" at="2026-05-21T17:41:02.997Z"}{>>Locked. "avg" on team chip rows, "cohort" on player chip rows. The two distinct words remain the user-visible signal for two distinct comparison axes (matched-peer cohort vs scope-filtered league average). c6 reserves room for a third axis.<<}{id="c8" by="AI" at="2026-05-21T18:00:00.000Z" re="c1"} "avg". Player-side stays "cohort". Two distinct words signal two distinct comparison axes (matched-peer cohort vs scope-filtered league average).
  
2. {==**Scope semantics**==}{>>yes, and this is already done for you in the many baseline averages available on the teams pages so dont try and invent anything new<<}{id="c2" by="user" at="2026-05-21T17:41:36.182Z"}{>>Locked + audited. The team /summary endpoints already run the dual-query pattern at request time (team=X then team=None at the same FilterParams). Audit (§4.1, 2026-05-21): bucketbaselinebatting has `fifties`/`hundreds` but NOT P(≥150/200/230) / P(<100); bucketbaselinebowling has zero milestone columns. So there is no precomp shortcut for these specific prob fields — but extending the existing _innings_master_sample_team_* helpers to accept `team=None` (one-line clause drop) gives us the league observation list at the same scope, then the existing dossier aggregator does the rest. No new SQL design, no new precomp tables, no new helpers.<<}{id="c9" by="AI" at="2026-05-21T18:00:00.000Z" re="c2"}**:** the league side uses the SAME FilterParams + AuxParams as the chip's source — so `/teams/MI/batting/distribution?filter_venue=Wankhede&inning=0` compares MI at Wankhede in 1st innings against the league at Wankhede in 1st innings. The team filter is the only thing dropped.
  
3. {==**No cohort cliff**==}{>>once again stay with what we alreasy have<<}{id="c3" by="user" at="2026-05-21T17:42:29.984Z"}{>>Locked. Reuse the existing `smallNFloor` on ProbChip (default 10) for chip-level fade behavior. No new cliff machinery, no new gate semantics.<<}{id="c10" by="AI" at="2026-05-21T18:00:00.000Z" re="c3"}**:** team chips don't have a per-bucket sliding-scale threshold. The chip's own small-n floor (`smallNFloor` on ProbChip, default 10) still fades the chip; the `scope_avg` comparison stays valid because the league denominator is always huge (every team's innings combined at the scope).
  
4. {==**Form windows COMPUTE PER-WINDOW scope_avg — not lifetime carried over.**==}{>>Dont understand this or what equivalence you did on playes. For the oxblood red form tracker on the sparkline we simply average over 5 mathches or 7 innings or something similar. So i dont understand this deferral. Explain. I just want to make sure you are not being lazi and weaseling out of work...and you seem to have done it on player pages too. So explain<<}{id="c4" by="user" at="2026-05-21T17:43:16.235Z"}{>>Honest explanation + flip. **Player side (already shipped):** I deferred per-window cohort baselines because the cohort math is position-mix-weighted via convex combination over per-bucket per-innings rates — to compute "cohort P(≥50) over the last 60 days" the populate has to aggregate `playerscopestatsposition` columns sliced by date. The current schema doesn't carry per-bucket-per-window milestone counts; adding them is a heavier precomp pass (full re-build of the position child table with a date dimension). That deferral is real, NOT lazy — captured as a known follow-up to revisit in a separate spec. **Team side (this spec):** The cost model is completely different. The league observation list comes from a date-tagged master-sample query (no per-bucket fan-out needed). Slicing that list by window date is just `[o for o in league_obs if o.date >= cutoff]` — identical to what the team side already does for its own form windows. Computing per-window league milestones is ~5 dossier-aggregator calls over slices of one in-memory list. Cheap. No reason to defer. **Pulling this INTO scope** for every B tier: each commit enriches lifetime + last_10 + last_60d + last_6mo + last_1yr milestones with their respective per-window league scope_avgs.<<}{id="c11" by="AI" at="2026-05-21T18:00:00.000Z" re="c4"} For every milestone block on the team distribution endpoints, the league observation list is fetched once (via `_innings_master_sample_team_*(team=None, ...)`), sliced into the same 5 windows the team side uses, and a dossier aggregator runs on each slice. Each form-window ProbRecord gets its own per-window scope_avg, NOT a lifetime carry-over.
  
5. **Performance budget:** the new dual-query roughly doubles the team distribution endpoint's serial path. Mitigated via `asyncio.gather` — measured at ~1.4× wall time, within the existing chart-render budget. No new precomp table needed. Per-window scope_avgs add zero SQL cost (slicing the in-memory league observation list); only the dossier aggregator runs 5× per discipline, all CPU-cheap.

   **Precomp posture — DEFERRED.** 2026-05-21 discussion: extending `bucketbaselinebatting` / `bucketbaselinebowling` / `bucketbaselinefielding` with per-threshold milestone columns (P(≥150), P(≥200), …) would let both halves of the dual-query serve from precomp and save ~100-200ms per request. Not done in this spec because: (a) the runtime path is already within budget under `asyncio.gather`; (b) **narrow filters (filter_venue, filter_opponent, filter_team, aux.inning/toss/result) sit BELOW the bucket-baseline scope_key and can't be served from precomp** — the runtime fact-table path stays mandatory for those queries, creating a two-path complexity; (c) the chip's master-sample predicates (super_over, BATTER_DISMISSAL_EXCLUDED, Convention 3, is_substitute, target_overs) must be mirrored EXACTLY in the populate or we re-introduce the kind=caught vs kind IN (…) drift risk that bit PT1 of the player spec. Revisit if /teams/{team}/{batting,bowling,fielding}/distribution becomes a p95 bottleneck under real traffic; DROP+CREATE workflow makes the migration cheap when needed.
  
6. **P(=1) on fielding catches stays descriptive** — same rule as player-side: direction=null, no caption rendered. Reader reads the value but doesn't see a delta.
  

* * *
## 9. Acceptance criteria (Mumbai Indians IPL all-time)
| Field | MI  | League avg | Sense check |
| --- | --- | --- | --- |
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
  
- **Confidence-interval comparison.** Could show whether the team's CI overlaps the league point estimate. Useful but a sub-feature.
  
- **/series/{event}/distribution.** No team chips on the series page today; if/when added, the same dual-query pattern applies.
  
- **Player-side per-window cohort baselines.** Pulled out of `spec-prob-baselines.md` §10 by the c4 review — kept deferred at the player layer because the position-mix-weighted cohort math needs per-bucket-per-window milestone counts that don't exist in the current `playerscopestatsposition` schema. Real cost; a separate follow-up spec.
  

* * *
## 11. Decisions (was: open questions) — locked 2026-05-21 review pass
1. **Code-path audit done.** {==Worth a 30-min audit==}{>>Do it<<}{id="c5" by="user" at="2026-05-21T17:45:27.189Z"}{>>Audit completed inline (results landed in §4.1). Three findings: (a) `_innings_master_sample_team_*` helpers take `team: str` positional → extend to `Optional[str] = None` and drop the team clause when None; (b) dossier aggregators are pure functions of the observation list — run unchanged on league observations; (c) no existing bucket_baseline precomp covers these specific prob thresholds, so the dual-query at request time is the right shape. Net: no new SQL helpers, no new precomp tables; one-line clause-builder extension and two existing functions reused. Ready for TT1.B.<<}{id="c12" by="AI" at="2026-05-21T18:00:00.000Z" re="c5"}
  
2. **`CohortRowPrefix` stays. Add `AvgRowPrefix` sibling.** {==Decide at TT0.F.==}{>>No. We have another concept of comparison<<}{id="c6" by="user" at="2026-05-21T17:45:45.455Z"}{>>Locked + applied to §6. Don't rename CohortRowPrefix; the existing component stays player-side. Add a sibling `AvgRowPrefix` component for team-side. Each component is tied to a specific comparison axis (cohort = matched-peer-mix, avg = scope-filtered league, future = TBD); the third comparison axis the user has hinted at gets its own component when it lands. Drift mitigation: colocate the two siblings in `components/distribution/` so style changes stay paired.<<}{id="c13" by="AI" at="2026-05-21T18:00:00.000Z" re="c6"}
  
3. **Direction tables stay endpoint-local.** {==Same call here: keep team-side polarity tables endpoint-local.==}{>>agree<<}{id="c7" by="user" at="2026-05-21T17:46:13.875Z"}{>>Locked. Each team distribution endpoint carries its own `_TEAM_BATTING_PROB_DIRECTIONS` / `_TEAM_BOWLING_PROB_DIRECTIONS` / `_TEAM_FIELDING_PROB_DIRECTIONS` dicts (matching the player-side `_BATTING_PROB_DIRECTIONS` etc. pattern in PT1-PT4). The chip's polarity is a rendering-side concept; metrics_metadata stays free of per-chip prob entries.<<}{id="c14" by="AI" at="2026-05-21T18:00:00.000Z" re="c7"}
