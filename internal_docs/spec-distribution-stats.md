# Spec — Distribution-shaped statistics on the API

> **Status:** Inventory + cross-discipline framing remain DRAFT.
> §8 + §9 (batter v1 backend + frontend) **IMPLEMENTED** 2026-05-05.
> v2 extension shipped 2026-05-06: 4-window form (added 6mo + 1y
> alongside 10 + 60d), conditional milestones (p_50_given_30,
> p_70_given_50, p_30_plus), "Scope" rename (was "Lifetime"),
> two-row milestone chip layout, sparkline grey 20-run reference
> line + labelled caption, stat row 2 "30s / 50s / 100s".
> 258/258 sanity invariants pass; 21/21 integration assertions
> pass against cricket.db.
> Remaining open questions in §6 apply to the bowler / fielder /
> team slices.

---

## 1. What this is

Today the API returns **point summaries**: batting average 45,
strike rate 130, economy 7.2. A point summary is a one-number
projection of an underlying event stream (per delivery, per
innings, per match, per partnership). For most stats, the
distribution carries information the point estimate loses:

1. **Variance / consistency.** SR=130 from `{200, 200, 60, 60}`
   reads identical to `{130, 130, 130, 130}` pooled — the per-
   innings distribution distinguishes them.
2. **Recency / form.** A 90-day rolling slice of the same
   distribution shows trajectory, not just lifetime.
3. **Splits as conditional distributions.** By phase, opponent,
   venue, season — same machinery, narrower SQL filter. Some splits
   are already supported as filtered point estimates (Compare slots,
   FilterBar); the distribution view generalises.

This spec inventories every stat we currently expose for
**batters / bowlers / fielders / teams / partnerships**, identifies
the underlying distribution unit per stat, and groups stats by the
six recurring distribution shapes that show up across disciplines.
Naming the shapes up front lets the API expose a uniform descriptor.

§8 lands the first concrete slice — batter v1, runs/innings.

---

## 2. The unit-of-observation question

A distribution-aware API needs to commit per-stat to **what one
observation is**. Possible units in this codebase:

- **Delivery** (`delivery` row): finest grain. Rarely the unit for
  a player-summary distribution because deliveries within an
  innings are not independent samples.
- **Innings** (`innings` row, scoped to a player via `delivery`):
  natural unit for batting and most bowling stats.
- **Match** (`match` row): natural unit for fielding events
  (catches, stumpings) and team results.
- **Partnership** (`partnership` row): natural unit for stand-
  related stats.
- **Spell** (consecutive overs by one bowler): conceptually the
  bowler's natural unit but the schema does not atomise spells —
  treat innings as the proxy.
- **Season / tournament**: the natural unit when the user wants to
  compare seasons against each other; the distribution-of-
  distributions case. Already supported as filter scope; out of
  scope for the per-stat distribution payload.

Wherever the inventory below names a "unit," it is fixing this
choice for that stat.

---

## 3. Inventory by discipline

### 3.1 Batting (per batter)

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Total runs | innings → runs scored | Per-innings runs distribution. Heavily right-skewed, long tail; median ≪ mean. Distinguishes "consistent 30s" from "two ducks + a 120". |
| Strike rate (concatenated) | innings → balls-faced-weighted SR | Per-innings SR weighted by balls. Reveals tempo bimodality (anchor vs aggressor) hidden by the pool. *Out of v1 — see §8.1.* |
| Average (runs / dismissals) | innings → (runs, dismissed?) | Two coupled distributions: runs-per-innings + Bernoulli(dismissed). Average is a ratio of expectations; conflates "didn't bat long" with "got out for 5". |
| Boundary % | innings → boundaries / balls | Per-innings boundary-fraction distribution, balls-weighted. Maps directly to risk profile. |
| Dot % | innings → dots / balls | Same shape, opposite signal (low-risk anchoring). |
| Highest score | max order statistic over innings runs | Identity-bearing — see §5. |
| 50s, 100s | thresholded counts on innings runs | CDF readouts of the same distribution. Replaced by milestone probabilities in §8.4. |
| Fours, Sixes | innings → boundaries thrown | Counts; per-innings distribution ≈ Poisson-ish; useful for "explosive innings" classification. |
| Not outs | innings → 1[notout] | Bernoulli per innings; coupled with runs (notouts cluster at innings end → small runs). |

**Natural primary unit: the innings.** Almost every batting summary
is a transform of `(runs_batter, balls_faced, dismissed_flag, fours,
sixes, dots)` per innings. v1 (§8) builds on exactly this row.

### 3.2 Bowling (per bowler)

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Total wickets | innings → wickets taken | Per-innings wickets distribution: usually 0–1, fat zero-inflation, long right tail. Shows whether wickets cluster (5-fers) or spread evenly. |
| Economy | innings → runs / legal-balls × 6 | Per-innings economy distribution, balls-weighted. Distinguishes "always 7" from "5/5/5/15". |
| Average | innings → (runs conceded, wickets) | Coupled like batting average. **Hard case**: many innings have wickets=0 — average-per-innings is undefined or inf. Distribution-of-runs-per-innings + distribution-of-wickets-per-innings is cleaner than ratio-per-innings. |
| Strike rate (balls/wkt) | wicket event → balls bowled until next wicket | **Survival distribution**: time-to-event with right-censoring (innings ends before next wicket). Mean vs Kaplan–Meier matters here. |
| Best figures (e.g. 5/20) | innings | Identity-bearing — see §5. |
| 5-fers / 4-fers | innings | CDF readouts of wickets-per-innings. |
| Wides / no-balls per match | match → extras count | Discrete distribution per match; high zero-inflation; distribution shows "occasional spray vs chronic" different from the per-match mean. |
| Dot % bowled | innings → dots / balls | Same shape as batter's dot %. |
| Boundary % conceded | innings → boundaries / balls | Sibling stat. |

**Natural primary unit: the innings** (a "spell" is messier — multiple
spells per innings exist but our schema does not atomise them).
Bowling has more zero-inflated stats than batting; choice of summary
(median, mode, % of innings with ≥ 1 wicket) often more honest than
mean for wickets/match etc.

### 3.3 Fielding (per fielder)

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Catches | match → catches taken | Per-match count distribution: heavy zero-inflation, tail at 2–3. |
| Stumpings | match → stumpings taken | Same shape, even sparser (only keepers). |
| Run-outs | match → run-outs participated | Same. |
| C&B (caught-and-bowled) | match → c&b | Sparse; mostly bowlers in small numbers. |
| Per-match rates | match → events/match | These are already at unit level; distribution work means showing the histogram, not the mean. |

**Fielding is the simplest case** — events are rare, distributions
are basically discrete count distributions. The interesting stat is
"what fraction of matches did they take ≥ 1 catch", not "average
catches per match" (which the long tail of 0s makes meaningless).

### 3.4 Team

Teams are the trickiest because metrics live at three different
units (innings, match, partnership).

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Matches / wins / losses / ties / no-results | match → outcome | Multinomial per match. Distribution = win-rate trajectory over season / opponent / venue. |
| Win % | match → 1[won] | Bernoulli; distribution = rolling win-rate or sliced (by venue, by toss-decision, day vs night). |
| Bat-first win % | match → 1[won \| bat first] | Conditional Bernoulli — already a distributional split on one condition. Generalise. |
| Run rate (concatenated) | innings → balls-weighted RR | Per-innings RR distribution by team. Reveals "always 8-an-over" vs "4 then 12". |
| Economy (team's bowling) | innings (oppo batting) → balls-weighted econ | Mirror of RR. |
| Highest team total / Lowest all-out | max/min order statistics over innings totals | Identity-bearing — see §5. Distribution of innings totals (and the all-out subset) carries the variance. |
| Phase RR / phase economy | innings × phase → balls-weighted RR/econ | Per-innings-per-phase distributions; six new distributions per team (3 phases × bat/bowl). |
| Fielding aggregates | match → events | Same as per-fielder fielding, rolled to team. |
| Partnership counts (50+, 100+) | partnership → runs | CDF readouts of partnership-runs distribution. |
| Best pair / highest partnership | order statistic over partnerships | Identity-bearing — see §5. |

A team distribution payload would expose all four grains (match,
innings, partnership, fielding-event-per-match) with pointers to
which sample produced each.

### 3.5 Partnerships

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Partnership runs | partnership → runs | Per-partnership runs distribution. Heavily right-skewed. |
| Avg partnership per wicket position | partnership × wicket_number → runs | Already a split — distributional view = histogram per wicket position (1–10). The shape is what makes "openers vs lower order" comparable. |
| Best partnership | order statistic | Identity-bearing — see §5. |
| 50+ / 100+ counts | thresholded counts | CDF readouts. |

---

## 4. Six recurring distribution shapes

Six shapes show up across all disciplines. Naming them up front lets
the API expose a uniform descriptor; per-stat metadata then says
"this stat is shape N, here is its sample."

1. **Per-innings continuous, balls-weighted.** Batter SR, batter
   boundary %, RR, economy, dot %. Mean ≠ pool when innings vary in
   balls; honest summary is balls-weighted mean.
2. **Per-innings count, zero-inflated.** Wickets/innings,
   catches/match, fours/innings. Mean is misleading; want median +
   fraction-of-innings ≥ 1 + milestone probabilities.
3. **Per-innings runs (skewed continuous).** Batter runs, team
   innings totals, partnership runs. Right-skewed, long tail. **This
   is the shape batter v1 (§8) ships.**
4. **Bernoulli per match.** Won, bat-first won, toss-won. Rolling
   fraction; slices by condition.
5. **Survival / time-to-event.** Bowling SR, "balls per wicket".
   Right-censored at innings end; needs Kaplan–Meier, not arithmetic
   mean of innings ratios.
6. **Bernoulli-coupled-with-magnitude.** Average = runs / dismissals,
   where the dismissed flag couples with runs. Two distributions;
   ratio of means is what we currently surface; exposing both lets
   clients compose alternatives (e.g. notout-aware).

---

## 5. Identity-bearing stats are NOT distributions

`highest_score`, `best_figures`, `best_pair`, `lowest_all_out`,
`keepers` are not summaries of a distribution — they are **specific
events with carrier identity** (the match, the partner, the venue).
They are the *argmax* of an order statistic over a distribution,
plus metadata. A distribution-shaped API should keep these as a
sibling field, not try to fold them in.

This was already a Compare-tab decision (see
`how-stats-calculated.md` "Best pair": *only computed on team-side
requests, not the avg col — a "league average pair" has no
identity*).

---

## 6. Open questions

These are the design calls that need resolution per discipline. The
batter v1 slice (§8) resolves several for the batter case; bowler /
fielder / team specs will revisit.

1. **Sampling-unit pinning per stat.** Bowling SR's survival shape
   (§4 shape 5) is non-trivial — do we expose K–M curves, or
   simplify to "per-innings balls/wkt where wkt > 0" with the
   censored sample dropped?
   *Batter v1: per-innings, notouts treated as completed (§8.3.1).*
2. **Histogram primitive.** Fixed-bucket vs adaptive bucketing vs
   raw observations.
   *Batter v1: raw observations, integer runs (§8.2). Cricket runs
   are integer 0–~250; ~150 obs/career is bounded payload — no
   bucketing needed. Bowler and fielder slices may differ.*
3. **Quantile vector.** **RESOLVED project-wide:** no quantile
   vector. Variance + std + mean + median + milestone CDF readouts
   cover the consistency story without quantiles.
4. **Sample-size floor.** Below what *n* do we suppress the
   distribution and return only the pool? Different by shape (10
   innings might be enough for batting; 30 matches for fielding
   counts). *STILL OPEN — batter v1 returns the dossier at any n;
   frontend can apply a confidence overlay later.*
5. **Form windows.**
   *Batter v1: last-10 innings + last-60 days (§8.6). Hard windows,
   not exponential decay. Career-percentile-of-window deferred to
   v1.5.*
6. **Bucket-baseline implications.** *STILL OPEN — batter v1
   computes live (no precomputation). Cost analysis pending; if hot,
   a per-innings sketch in `bucketbaseline_*` is the natural next
   step.*
7. **Cross-cutting Compare-tab integration.** *STILL OPEN — UI
   question; deferred.*

---

## 7. Next slices

Batter v1 (§8) ships first. The remaining slices reuse the same
machinery (per-discipline observation row → aggregate dossier →
form windows → suggested splits) but each pins its own answers to
§6.1 / §6.2 / §6.4 / §6.6.

- **Bowler.** Hardest case — survival shape on bowling SR (§4 shape
  5), zero-inflation on wickets/innings (§4 shape 2). Likely two
  parallel sub-slices: "wickets/innings" dossier (zero-inflated
  count), "runs conceded/innings" dossier (skewed continuous).
  Strike rate as a derived field over the latter two.
- **Fielder.** Simplest. Per-match count distribution; "fraction of
  matches with ≥ 1 catch" replaces "catches per match" as the
  honest summary.
- **Team.** Multi-grain — match (results, fielding), innings (RR,
  totals), partnership (stands). Three sibling sub-dossiers under
  one endpoint, or three endpoints? Open.

---

## 8. Batter v1 — distribution dossier (IMPLEMENTED)

> First concrete slice. Batter only, runs/innings only. Phase
> decomposition stored on every per-innings observation even though
> we are not surfacing strike-rate-by-phase yet, so future SR /
> dot% / boundary% by-phase work is a pure derivation — no schema
> or endpoint change. Frontend (semiotic histograms with mean +
> median overlays, sparklines) is **out of scope for this spec** —
> API only.
>
> **Shipped 2026-05-05** across 5 commits:
> 1. `scope_links: suggested_splits — Python + TS lockstep mirror`
> 2. `batting: /batters/{id}/distribution endpoint`
> 3. `sanity: batter distribution invariants — 126 assertions`
> 4. `regression: batter_distribution urls.txt — 19-URL inventory`
> 5. `docs: api.md + spec corrections`

### 8.1 Scope pinning

**In v1:**

- Endpoint: `GET /api/v1/batters/{id}/distribution?{FilterParams}`.
- Master sample: per-innings tuple, runs the focal metric.
- Phase columns (PP / Mid / Death) on every per-innings observation
  AND aggregated rollup.
- Form windows: last-10 innings + last-60 days, both same dossier
  shape as lifetime.
- Suggested splits embedded in the response (scope-derived).
- Every existing `FilterParams` axis honoured (gender, team_type,
  tournament, season range, opponent, venue, team_class).

**Explicitly out of v1** (settled in discussion):

- Strike rate. Phase columns are stored so SR-by-phase ships later
  without re-querying.
- Quantiles (P5/P25/P50/P75/P95). Variance + std + mean + median +
  milestone CDF readouts cover the consistency story.
- Frontend / UI work. Spec covers calculations + API only.
- Career-percentile of the form window (rolling-medians distribution
  over the player's career). High-value, harder math; deferred to
  v1.5.
- Bowler / fielder / team distribution dossiers. Sibling specs.

### 8.2 Per-innings observation row

For batter `id` under `FilterParams F`, materialise one row per
batting innings (one row per `(match, innings, batting_team includes
batter)`). Columns:

| Column | Definition |
|---|---|
| `innings_id` | `innings.id` |
| `match_id` | `innings.match_id` |
| `date` | `match.date` (used for ordering + form windows) |
| `runs` | `SUM(runs_batter)` over **legal balls** (`extras_wides = 0 AND extras_noballs = 0`) where `delivery.batter_id = id` |
| `balls` | `COUNT(legal balls)` faced by `id` |
| `dismissed` | boolean — exists a `wicket` with `player_out_id = id` AND `kind NOT IN ('retired hurt', 'retired out')` (see §8.3.0 below) |
| `fours` | `COUNT(legal balls WHERE runs_batter = 4 AND COALESCE(runs_non_boundary, 0) = 0)` — excludes "ran 4" |
| `sixes` | `COUNT(legal balls WHERE runs_batter = 6)` |
| `dots` | `COUNT(legal balls WHERE runs_total = 0)` |
| `runs_pp`, `balls_pp` | as `runs`/`balls` plus `WHERE delivery.over_number BETWEEN 0 AND 5` |
| `runs_mid`, `balls_mid` | `WHERE over_number BETWEEN 6 AND 14` |
| `runs_death`, `balls_death` | `WHERE over_number BETWEEN 15 AND 19` |

All conventions match `internal_docs/how-stats-calculated.md` —
legal-balls restriction, dismissal exclusion list, fours
non-boundary-flag check, phase boundaries on the DB-side 0–19
numbering. Column is `delivery.over_number` (was misnamed
`over_idx` in the original spec draft; corrected post-implementation).

#### 8.3.0 'retired not out' — convention drift

`how-stats-calculated.md` says the dismissed-flag exclusion list
should be `('retired hurt', 'retired out', 'retired not out')`
(three values). Existing batting endpoints (`/summary`,
`/by-innings`, `/vs-bowlers`, `/by-phase`, `/leaders`) all use the
2-element list `('retired hurt', 'retired out')` only. 'retired
not out' is 13 rows out of 162k wickets (0.008%) — materially
irrelevant.

**The implementation matches the existing 2-element convention**
for cross-endpoint consistency. A project-wide sweep to align doc
+ code on the 3-element list (or reject the 3-element doc) is
out of scope for this slice; flagged as a follow-up.

Ordered `match.date ASC, innings.innings_number ASC` — date-asc
ensures `observations[]` doubles as the sparkline data without an
extra sort.

### 8.3 Aggregate calculations

Compute these from the observation list `obs[]`:

| Field | Formula | Note |
|---|---|---|
| `n_innings` | `len(obs)` | sample size |
| `n_dismissals` | `sum(o.dismissed for o in obs)` | for `average` denom |
| `n_notouts` | `n_innings − n_dismissals` | informational |
| `runs.total` | `sum(o.runs)` | pool runs |
| `runs.balls_total` | `sum(o.balls)` | for downstream SR derivation |
| `runs.mean_per_innings` | `runs.total / n_innings` | "runs per innings" — denominator is innings, **not** dismissals |
| `runs.median` | `median([o.runs for o in obs])` | notouts treated as completed (§8.3.1) |
| `runs.variance` | sample variance, `n−1` denominator | |
| `runs.std` | `sqrt(runs.variance)` | display-friendly |
| `runs.average` | `runs.total / n_dismissals` if `n_dismissals > 0` else `null` | conventional cricket avg, **kept** alongside `mean_per_innings` (§8.3.2) |
| `runs.observations` | full per-innings tuple list, date-asc | see §8.5.1 for shape |

#### 8.3.1 Notout convention

Median uses **raw `runs` values** without right-censoring. This
matches the existing `average` convention (which treats notouts as
completed by reducing the `dismissals` denominator, NOT by
truncating runs). Right-censoring would be the "balls until next
dismissal" reading; we are modelling "runs scored in this innings",
which IS fully observed regardless of notout status.

Document this at the SQL site so future contributors don't "fix"
it to a Kaplan–Meier-style censored median.

#### 8.3.2 `mean_per_innings` vs `average` — keep both

Two different numbers, both useful, both surfaced:

- `mean_per_innings = total runs / n_innings` — what an opponent
  expects you to score next innings.
- `average = total runs / n_dismissals` — conventional cricket avg;
  rewards not-getting-out.

UI work to label these unambiguously belongs in the follow-up
frontend spec.

### 8.4 Milestone probabilities

Two groups: **simples** (unconditional CDF readouts of the runs
distribution, normalised by `n_innings`) and **conditionals**
("going-on" probabilities — among innings that reached threshold A,
what fraction reached the higher threshold B).

**Simples** — denominator `n_innings`:

| Field | Formula | Reading |
|---|---|---|
| `milestones.p_failure_10` | `count(runs ≤ 10) / n_innings` | "got out cheap" |
| `milestones.p_25_plus` | `count(runs ≥ 25) / n_innings` | (kept for API back-compat; UI dropped 2026-05-06 in favor of p_30_plus) |
| `milestones.p_30_plus` | `count(runs ≥ 30) / n_innings` | T20 "got going" baseline |
| `milestones.p_50_plus` | `count(runs ≥ 50) / n_innings` | "match-shaping" |
| `milestones.p_100_plus` | `count(runs ≥ 100) / n_innings` | "match-winning" |

**Conditionals** — denominator is the *count of innings that
reached the conditioning threshold*. Null when that count is 0
(undefined ratio).

| Field | Formula | Reading |
|---|---|---|
| `milestones.p_50_given_30` | `count(runs ≥ 50) / count(runs ≥ 30)` | of his "got going" innings, how often he pushed to a fifty |
| `milestones.p_70_given_50` | `count(runs ≥ 70) / count(runs ≥ 50)` | of his fifties, how often he pushed past 70 |

Conditionals carry a subset invariant: `count(≥A) ≤ count(≥B)` for
A > B → ratio always in [0, 1]. Pinned in
`tests/sanity/test_batter_distribution_invariants.py`.

### 8.5 Phase decomposition

#### 8.5.1 Per-innings phase observations

Every observation in `runs.observations` carries phase columns:

```jsonc
{
  "match_id": 13095, "date": "2026-04-30", "innings_id": 26194,
  "runs": 47, "balls": 33, "dismissed": true,
  "fours": 5, "sixes": 1, "dots": 8,
  "runs_pp": 22, "balls_pp": 17,
  "runs_mid": 18, "balls_mid": 13,
  "runs_death": 7, "balls_death": 3
}
```

Decision (settled in discussion): **include per-innings phase obs in
the response**, not just the rollup. Cost is ~6 ints per
observation; payload remains bounded for typical scopes (a 142-
innings career adds ~3.4 KB). Lets phase-share-over-time
visualisations work without a separate endpoint, and lets future
SR/dot/boundary-by-phase derivations skip a re-query.

#### 8.5.2 Phase rollup

```jsonc
"phase": {
  "powerplay": { "runs_total": 178, "balls_total": 142, "innings_active": 14 },
  "middle":    { "runs_total": 234, "balls_total": 198, "innings_active": 14 },
  "death":     { "runs_total": 135, "balls_total":  92, "innings_active": 11 }
}
```

`innings_active` = innings where this phase had ≥ 1 ball faced.
The right denominator for "his Death-overs form" — don't penalise
an opener who never reaches Death.

Invariant: `powerplay.runs_total + middle.runs_total +
death.runs_total == runs.total` (within phase boundaries; sanity
check in §8.10). Same partition holds for `balls_total`.

### 8.6 Form windows

Four windows, **same dossier shape as lifetime** — the entire
`runs`, `milestones`, and `phase` blocks recompute on the windowed
sample:

| Window | Definition | Use |
|---|---|---|
| `form.last_10` | `ORDER BY date DESC, innings_number DESC LIMIT 10` | cricket-conventional "current form" |
| `form.last_60d` | `WHERE date >= anchor − 60 days` | scope-anchored current form |
| `form.last_6mo` | `WHERE date >= anchor − 180 days` | medium-term arc |
| `form.last_1yr` | `WHERE date >= anchor − 365 days` | annual / loss-of-form gauge |

**`anchor` (revised 2026-05-07)** — `min(today, max_obs_date)`.
For active players in unconstrained scopes the anchor IS today,
so the windows mean the same as the original "today minus N days."
For retired players (Gayle, ABdV) and tightly-scoped subjects
(IPL 2016 only), the anchor follows the data — the windows then
mean "the last N calendar days OF SCOPE," producing meaningful
form readings instead of empty windows. Aligns with the
scope-anchored philosophy already used by `last_10` (a count
window over the master sample) and the FilterBar `last-3` /
`prev-3` / `first-3` season buttons.

Empty observations → anchor = today (windows trivially empty).

60 days is short enough to gauge current form but too short to
detect a loss-of-form arc; the 6mo + 1y windows added 2026-05-06
fill that gap.

Plus a `form.delta` block — one-glance reads, two metrics × four
windows = 8 entries:

```jsonc
"form": {
  "delta": {
    "last_10_mean_minus_lifetime":    <float>,
    "last_10_median_minus_lifetime":  <float>,
    "last_60d_mean_minus_lifetime":    <float>,
    "last_60d_median_minus_lifetime":  <float>,
    "last_6mo_mean_minus_lifetime":    <float>,
    "last_6mo_median_minus_lifetime":  <float>,
    "last_1yr_mean_minus_lifetime":    <float>,
    "last_1yr_median_minus_lifetime":  <float>
  }
}
```

Sparkline data is implicit — frontend reads the active window's
`runs.observations[]` (date-asc), overlays a rolling-N mean line on
the Scope window only. No separate endpoint.

### 8.7 Suggested splits

`response.suggested_splits` — array of `(label, params)` pairs
derived from the **incoming filter scope**. Frontend renders each
as a `PlayerLink` to `/players?player={id}` with `params` applied
to the URL (per `internal_docs/links.md`).

The principle: **for every narrowed axis, offer one-click broaden;
for every absent narrowable axis on a hot scope, offer one-click
narrow.** Always trying to get ahead of the user's "but how does
this compare to..." question.

Decision table — for each set of axes set on the incoming scope,
the splits to emit:

| Incoming scope axes | Splits offered |
|---|---|
| `tournament + season` (e.g. IPL 2024) | "All `<tournament>`" (drop season); "All cricket in `<season>`" (drop tournament); "All-time" (drop both) |
| `tournament` only (no season) | "Latest `<tournament>` edition" (set season range to `[latest, latest]`); "All-time" (drop tournament) |
| `season` only (no tournament) | "All-time" (drop season) |
| `filter_opponent` set | "vs `<opponent>`, all-time" (drop temporal, keep opponent); "vs all opponents" (drop opponent) |
| `filter_venue` set | "at `<venue>`, all-time" (drop temporal, keep venue); "at all venues" (drop venue) |
| `gender = female` (with any other narrowing) | "Switch to men's" (flip gender) |

Empty / single-entry split lists are valid — some scopes have
nothing useful to suggest. Frontend renders nothing in that case;
the field is always present, never absent.

#### 8.7.1 Implementation home

A new helper in `frontend/src/components/scopeLinks.ts`:

```ts
export function suggestedSplits(scope: ScopeContext): SplitSuggestion[]
```

Walks the active filter, emits the splits per the table above. The
distribution endpoint calls a Python mirror (location TBD by
implementer — `api/scope_links.py` is the natural new home; could
also live alongside the batter router if scope is small).

The Python and TypeScript versions stay in lockstep — a sanity
test pins this (§8.10).

`suggestedSplits` is **reusable on every scoped page** that wants
"always-ahead" navigation hints — not specific to the distribution
endpoint. Future Series, Teams, Venues pages can call it.

### 8.8 Endpoint shape

```
GET /api/v1/batters/{id}/distribution?{FilterParams}
```

Response:

```jsonc
{
  "scope": { "tournament": "IPL", "season_from": "2024", "season_to": "2024", ... },
  "lifetime": {
    "n_innings": 14,
    "n_dismissals": 11,
    "n_notouts": 3,
    "runs": {
      "total": 547,
      "balls_total": 432,
      "mean_per_innings": 39.07,
      "median": 33,
      "variance": 1124.3,
      "std": 33.53,
      "average": 49.73,
      "observations": [
        { "match_id": 12876, "date": "2024-03-22", "innings_id": ...,
          "runs": 21, "balls": 19, "dismissed": true,
          "fours": 2, "sixes": 0, "dots": 5,
          "runs_pp": 8, "balls_pp": 6,
          "runs_mid": 13, "balls_mid": 13,
          "runs_death": 0, "balls_death": 0 },
        ...
      ]
    },
    "milestones": { "p_failure_10": 0.21, "p_25_plus": 0.57, "p_50_plus": 0.43, "p_100_plus": 0.07 },
    "phase": {
      "powerplay": { "runs_total": 178, "balls_total": 142, "innings_active": 14 },
      "middle":    { "runs_total": 234, "balls_total": 198, "innings_active": 14 },
      "death":     { "runs_total": 135, "balls_total":  92, "innings_active": 11 }
    }
  },
  "form": {
    "last_10":  { "n_innings": 10, "n_dismissals": 8, "n_notouts": 2,
                  "runs": {...}, "milestones": {...}, "phase": {...} },
    "last_60d": { "n_innings": 6,  "n_dismissals": 5, "n_notouts": 1,
                  "runs": {...}, "milestones": {...}, "phase": {...} },
    "delta": {
      "last_10_mean_minus_lifetime":   -2.1,
      "last_10_median_minus_lifetime": -5,
      "last_60d_mean_minus_lifetime":   8.4,
      "last_60d_median_minus_lifetime": 12
    }
  },
  "suggested_splits": [
    { "label": "All IPL",          "params": { "tournament": "IPL" } },
    { "label": "All cricket 2024", "params": { "season_from": "2024", "season_to": "2024" } },
    { "label": "All-time",         "params": {} }
  ]
}
```

### 8.9 Implementation pointers (as shipped)

- **New endpoint** at `batting_distribution` in
  `api/routers/batting.py` (file is `batting.py`, not `batters.py`
  as the original spec draft said — the URL prefix `/batters/` is a
  separate naming choice). Mirrors siblings `/batters/{id}/summary`,
  `/batters/{id}/by-innings`, etc.
- **`_innings_master_sample(db, person_id, filters, aux)`** in
  `batting.py` — async SQL query returning the per-innings
  observation rows. Reuses `_batting_filter` (which calls
  `FilterBarParams.build(has_innings_join=True, aux=aux)`) for the
  WHERE clause, the existing phase-boundary constants, and the
  existing 2-element dismissal-exclusion list (§8.3.0).
- **`_distribution_dossier(observations)`** in `batting.py` — pure
  function computing the aggregate stats. Used for lifetime + both
  form windows. Empty samples return a sane null-shape (no
  exceptions on n=0).
- **`_form_windows(observations, today)`** in `batting.py` —
  slices the observation list into last-10 / last-60d windows;
  runs the dossier on each; emits the `delta` block.
- **`api/scope_links.py`** — new module. `suggested_splits(scope)`
  + `scope_dict_from_filters(filters)` helpers. Python mirror of
  `frontend/src/components/scopeLinks.ts::suggestedSplits`. Lockstep
  enforced via `tests/sanity/scope_splits_fixtures.json` + the
  Python sanity test (TS implementation: manual review).

### 8.10 Tests (as shipped)

**Sanity** (`tests/sanity/test_batter_distribution_invariants.py` —
126 assertions across 4 scopes pass):

- `n_innings == len(observations)` for `lifetime`, `last_10`,
  `last_60d`.
- `last_10.n_innings ≤ 10`; `last_10.observations` is the
  contiguous date-asc tail of `lifetime.observations`.
- `phase.powerplay.runs_total + phase.middle.runs_total +
  phase.death.runs_total == runs.total` (phase decomposition is a
  partition of the legal-balls runs). Same for `balls_total`.
- `runs.mean_per_innings × n_innings ≈ runs.total` (within
  rounding).
- `runs.average × n_dismissals ≈ runs.total` when `n_dismissals
  > 0`; `runs.average == null` when `n_dismissals == 0`.
- `milestones.p_X_plus × n_innings == count(o.runs ≥ X)` for each
  threshold (denominator-correctness).
- `form.delta.last_10_(mean|median)_minus_lifetime ==
  form.last_10.runs.(mean_per_innings|median) −
  lifetime.runs.(mean_per_innings|median)` (delta-consistency).
- **SQL anchor** — lifetime `n_innings`, `runs.total`,
  `runs.balls_total` match a direct sqlite3 aggregation against
  `cricket.db` for the same filter scope (per the SQL-anchored-
  tests rule from CLAUDE.md).

**Sanity** (`tests/sanity/test_scope_links_lockstep.py` — 11
fixtures pass): TS / Python `suggestedSplits` lockstep, fixture-
driven.

**Regression** (`tests/regression/batter_distribution/urls.txt`):
19-URL inventory covering Kohli (busy), Samson (IPL-only),
Mandhana (women's), Bumrah (tail-batter stress) × multiple scopes
(all-time, IPL, IPL by season, vs CSK, at Chinnaswamy, season
only, inning aux 0/1, empty scope). All 19 return 200 against
the live endpoint. `as_of_date=2025-01-01` pinned for md5-diff
stability.

**No agent-browser integration test in v1 backend** — the API-only
slice ships without one. The integration test arrives with the
frontend (§9.10).

---

## 9. Batter v1 frontend — Distribution panel on `/batting?player=X`

> **Status:** IMPLEMENTED 2026-05-05 across 5 commits.
> Panel live at `/batting?player=X`. 21/21 integration assertions
> pass. Consumes the §8 endpoint
> `GET /api/v1/batters/{id}/distribution`. Lands the new
> "Distribution panel" between the existing stat row 1 and stat
> row 2 on `frontend/src/pages/Batting.tsx`. No backend changes
> required.
>
> **In scope:** window toggle (Lifetime / Last 10 / Last 60d),
> per-innings runs histogram (semiotic-backed, 6 fixed bins),
> stat strip (Mean / Median / Std / CV / Average), milestone
> chips, chronological sparkline of the observations list, form
> delta line, suggested-splits link row.
>
> **Out of v1 frontend:** phase decomposition UI (data is in the
> response for future SR-by-phase work but the existing By Phase
> tab covers the visual need today); per-innings phase obs
> visualisations; Compare-tab integration; sample-size confidence
> overlays.

### 9.1 Layout

The current `/batting?player=X` page renders:

```
PlayerSearch + InningToggle
─────────────────────────────────────────────────
Title (name + flag) + ScopeIndicator
Stat row 1  · Matches · Innings · Runs · Average · SR    ← AVG SITS HERE
Stat row 2  · Boundaries · B/Four · B/Boundary · Dot% · 50s/100s
Tabs        · By Season | By Over | By Phase | vs Bowlers | …
```

The Distribution panel inserts **between row 1 and row 2** so it
visually anchors to the Average tile (row 1, col 4). Median +
CV + std live in the panel's stat strip — adjacent reading,
single eye-sweep. Row 2 stays unchanged; tabs unchanged.

### 9.2 Distribution panel anatomy

```
┌────────────────────────────────────────────────────────────┐
│ Distribution                          [Lifetime | 10 | 60d]│  window toggle (chip-style)
│                                                            │
│ ┌─────────────────────────────┬───────────────────────┐    │
│ │ histogram (6 bins)          │ Mean         49.4     │    │
│ │ + mean line ─ + median line │ Median       42       │    │
│ │                             │ Std          31.3     │    │
│ │                             │ CV           0.63     │    │
│ │                             │ Average      61.75    │    │
│ │                             │                       │    │
│ │                             │ P(≥50)   ┃   P(≥100)  │    │
│ │                             │  40%     ┃    7%      │    │
│ │                             │ P(≤10)                │    │
│ │                             │  7%                   │    │
│ └─────────────────────────────┴───────────────────────┘    │
│                                                            │
│ ▁▃▂▅▁▇▂▁▃▆▅▁▂  ← chronological sparkline (observations[])  │
│                                                            │
│ Form: Last 10 mean −7.0 · median 0  vs lifetime            │
│                                                            │
│ Compare to:  All IPL  ·  All cricket in 2024  ·  All-time  │
└────────────────────────────────────────────────────────────┘
```

#### 9.2.1 Window toggle — what it does

**Mechanism.** The §8 API returns all three dossiers in one
payload — `lifetime`, `form.last_10`, `form.last_60d`, each with
the identical shape (n_innings, runs stats, milestones, phase,
observations). The window toggle is a **pure presentational
selector**: clicking does NOT refetch; it just swaps which of the
three pre-fetched dossiers drives the histogram + stat strip +
milestone chips + sparkline. Switching is instant.

Three chip buttons in the panel header — `Lifetime` / `Last 10` /
`Last 60d`. Default `lifetime`.

**Window-dependent** (redraw on toggle):
- Histogram (different binned counts)
- Stat strip (different mean / median / std / CV / average)
- Milestone chips (different probabilities)
- Sparkline (different observation slice)

**Window-independent** (do NOT redraw on toggle):
- Form delta line — always reads `response.form.delta`, which
  reports BOTH windows' deltas vs lifetime. The toggle doesn't
  change "is this player hot or cold right now."
- Suggested-splits row — always reads `response.suggested_splits`,
  which is keyed off the FilterBar scope, not the window.

#### 9.2.1a URL state — `?dist_window=`

The window selection is **encoded in the URL** as
`?dist_window=lifetime|last_10|last_60d`. Default = absent →
`lifetime`. Toggling rewrites the URL via `useSearchParams`
(`replace: false` — toggle clicks should land in browser history,
so back-button restores the prior window).

Why URL state — share-link reproducibility (per
`feedback_state_location.md`): if you send someone a link looking
at Kohli's last-10 form, the receiver should land on the same view.
The window choice is meaningful enough to share.

This differs from the existing wisden-tab convention (active tab
on Players is local state). The tab choice on Players is more
"what am I currently inspecting" than "what view do I want my
correspondent to see"; for the distribution panel, the window IS
the view's identity.

Cross-page persistence: `dist_window` is a panel-local URL key
(prefix `dist_`) so it doesn't bleed into other pages' URL
contracts. If a Bowler distribution panel ships later (§7), it
reuses the same `dist_window` key — both panels are bound to the
same toggle semantics.

Empty-window handling: if the selected window has `n_innings == 0`,
the panel renders the dossier-empty placeholder (§9.3) instead of
the histogram. The toggle button is still clickable; user can
switch back. URL keeps the chosen window even when empty (so
sharing a link to `?dist_window=last_60d` honestly reproduces the
"no recent innings" view).

#### 9.2.2 Histogram

**Width-10 fixed bins** all the way through the runs range — gives
useful resolution above 100 (where a Gayle 175 should not look the
same as a Kohli 102). Bin definition (22 bins total):

```
[0,9], [10,19], [20,29], [30,39], [40,49], [50,59], [60,69],
[70,79], [80,89], [90,99], [100,109], [110,119], [120,129],
[130,139], [140,149], [150,159], [160,169], [170,179],
[180,189], [190,199], [200+]
```

**Render rule** — show bins from `[0,9]` through whichever is
greater of:
- `[90,99]` (the floor — always render the first 10 bins through 99)
- the bin containing `max(window.observations.runs)`

The `200+` terminal bin only renders if a 200+ score exists in
scope (not yet, but the bin is defined for forward-compatibility).

**Why the always-through-[90,99] floor:** so a tail batter
(Bumrah, max ~30) renders the full 0-99 span — 10 bars, 7 of
them zero-height after his max — and the empty right side reads
"this is a bowler" at a glance. Without the floor, Bumrah's
chart would auto-shrink to 4 bars filling the panel width and
visually look like a real batter who happened to peak at 30 — a
qualitative misread.

Above 99, the render-through-max rule kicks in: Kohli (max ~120)
renders 13 bars, Gayle (max 171) renders 18.

**Interior empty bins still draw** — preserves distribution shape
(a player with 5 innings 0-9, 0 innings 10-19, 8 innings 20-29
still sees the gap at 10-19). The **empty upper tail above max
vanishes** only when max ≥ 100 (above the 0-99 floor).

Bar counts: tail batters 10 (the floor); typical batters 10–13;
century-rich batters 13–18.

Fixed bin edges (not adaptive) keep the histogram **comparable
across players** — Kohli's `[50,59]` bar and Mandhana's `[50,59]`
bar mean the same thing. Adaptive bucketing would maximize
within-player resolution at the cost of cross-player legibility.

**Bin color coding** by milestone tier:

| Range | Tier | Visual |
|---|---|---|
| `[0,9]` | failure | muted red |
| `[10,49]` | building | neutral light |
| `[50,99]` | fifty range | neutral medium |
| `[100,149]` | century range | gold tint |
| `[150,200+]` | rare | gold highlight |

Built on the existing `frontend/src/components/charts/BarChart.tsx`
wrapper (semiotic-backed). `data` = `[{bin: '0-9', count: N, ...},
...]`; `categoryAccessor='bin'`, `valueAccessor='count'`,
`colorBy='tier'` (the new four-tier coloring) with the palette
extension in `frontend/src/components/charts/palette.ts` (add
`WISDEN_RUN_TIERS`).

**Mean + median markers**: vertical dashed lines overlaid at the
position proportional to the continuous mean / median values
(NOT bin-snapped). Implementation: Semiotic's `XYFrame`
annotations or a thin custom SVG overlay on the chart container —
implementer's call. The labels render in the stat strip alongside
their colored dot, so the marker doesn't need its own legend.

Hover state: bar shows `{bin label}: N innings ({pct%})`.

#### 9.2.3 Stat strip

Right of the histogram, a label/value list. Two sections:

**Group 1 — point summaries** (vertical stack):
```
Mean       49.4         ← total runs / n_innings
Median     42           ← median(runs across innings)
Std        31.3         ← sqrt(sample variance)
CV         0.63         ← std / mean (unitless; renders to 2dp)
Average    61.75        ← total runs / n_dismissals (cricket convention)
```

**Group 2 — milestone chips** (horizontal row of small colored
chips):
```
P(≥50)  40%   P(≥100)  7%   P(≤10)  7%
```

Color coding for the chips: green for ≥50 / ≥100 (positive
milestones), red for ≤10 (failure marker). `null` values (no
data — empty window) render as `—` not `0%`.

CV is computed client-side (`std / mean_per_innings`). No
backend change. Skipped if `mean_per_innings` is `null` or 0.

#### 9.2.4 Sparkline

A tiny chronological line/bar chart — full panel width, ~30px
high — showing per-innings runs in date order from the observations
list. Built on `frontend/src/components/charts/LineChart.tsx`
or a dedicated minimal renderer (implementer's call).

Window-dependent: sparkline data is `currentWindow.runs.observations`
mapped to runs only. Lifetime shows the full history; Last 10
shows 10 marks; Last 60d shows however many fall in the window
(can be 0–N).

Optional overlay for the Lifetime window: a rolling-10 mean line.
Skipped on Last 10 / Last 60d (rolling-N over a 10-element sample
is degenerate).

#### 9.2.5 Form delta line

Single text line below the sparkline, rendered window-independent:

```
Form: Last 10 mean −7.0 · median 0   vs lifetime
       Last 60d mean +8.4 · median +12   vs lifetime
```

Both deltas always shown. Color the delta numbers by sign: green
if positive (in form), red if negative. `null` deltas render as
"insufficient data" (e.g., last_60d with n=0).

Reads `response.form.delta` directly; never recomputed client-side.

#### 9.2.6 Suggested-splits row

Bottom of the panel:

```
Compare to:  All IPL  ·  All cricket in 2024  ·  All-time
```

Each split rendered via the existing `PlayerLink` contract from
`internal_docs/links.md` (`name` link + per-split scope override).
The link target is the same `/batting?player=X` page with the
split's `params` applied to the URL. `subscriptSource` (per
links.md) carries the split-specific scope so the rendered phrase
matches.

If `response.suggested_splits` is empty (e.g., user has no
narrowing axes set — already at all-time), the row is hidden.

### 9.3 Empty / sparse states

Three cases:

1. **Player not selected** (`!playerId`) — panel does not render at
   all. Page falls back to `BattingLandingBoard` per existing logic.
2. **Lifetime sample has `n_innings == 0`** — entire panel renders
   a single helper line in place of the histogram + stat strip:
   "No innings under this filter — try widening the scope."
   The suggested-splits row still renders (it lets the user pick a
   broader scope). Window toggle hidden.
3. **Window has `n_innings == 0` but lifetime is non-empty** — the
   selected window pane shows "No innings in the last 10 / 60 days
   under this filter" while the toggle remains active so the user
   can switch back to Lifetime. Form delta line shows "insufficient
   data" for that window.

### 9.4 Types — `frontend/src/types.ts`

Add a new `BatterDistribution` interface mirroring the API response
shape from §8.8. Sketch:

```ts
export interface InningsObservation {
  innings_id: number
  match_id: number
  date: string
  runs: number
  balls: number
  dismissed: boolean
  fours: number
  sixes: number
  dots: number
  runs_pp: number
  balls_pp: number
  runs_mid: number
  balls_mid: number
  runs_death: number
  balls_death: number
}

export interface DistributionDossier {
  n_innings: number
  n_dismissals: number
  n_notouts: number
  runs: {
    total: number
    balls_total: number
    mean_per_innings: number | null
    median: number | null
    variance: number | null
    std: number | null
    average: number | null
    observations: InningsObservation[]
  }
  milestones: {
    p_failure_10: number | null
    p_25_plus: number | null
    p_50_plus: number | null
    p_100_plus: number | null
  }
  phase: {
    powerplay: { runs_total: number; balls_total: number; innings_active: number }
    middle:    { runs_total: number; balls_total: number; innings_active: number }
    death:     { runs_total: number; balls_total: number; innings_active: number }
  }
}

export interface BatterDistribution {
  scope: Record<string, string>
  lifetime: DistributionDossier
  form: {
    last_10: DistributionDossier
    last_60d: DistributionDossier
    delta: {
      last_10_mean_minus_lifetime: number | null
      last_10_median_minus_lifetime: number | null
      last_60d_mean_minus_lifetime: number | null
      last_60d_median_minus_lifetime: number | null
    }
  }
  suggested_splits: { label: string; params: Record<string, string> }[]
}
```

Keep types tight — `tsc -b` catching the next consumer is the
defense against drift between API and frontend (per CLAUDE.md
"API-frontend type contract" rule).

### 9.5 Fetching — `frontend/src/api.ts`

Add a single function, mirroring the existing batter fetchers:

```ts
export const getBatterDistribution = (id: string, filters?: F) =>
  fetchApi<BatterDistribution>(
    `/api/v1/batters/${id}/distribution`,
    filters as Record<string, string>,
  )
```

In `Batting.tsx`, fetch alongside the existing `summaryFetch` —
same `useFilterDeps()` dependency array (so it refetches on every
FilterBar change AND on `inning` aux change, per the post-`be4d755`
discipline rule). Mount unconditional on `playerId` (not gated by
the active tab — the panel is always visible when a player is
selected).

```ts
const distFetch = useFetch<BatterDistribution | null>(
  () => playerId
    ? getBatterDistribution(playerId, filters)
    : Promise.resolve(null),
  filterDeps,
)
const distribution = distFetch.data
```

The fetch is a single roundtrip; lifetime + both form windows + all
splits arrive in one payload. No incremental loading.

### 9.6 Components

**New** (under `frontend/src/components/batting/`):

- `BatterDistributionPanel.tsx` — top-level panel orchestrating
  the layout. Props: `dossier: BatterDistribution | null`,
  `loading: boolean`, `error: string | null`.
- `RunsHistogram.tsx` — fixed-bin histogram with mean / median
  markers. Wraps `BarChart`. Bin computation is a pure function
  here so it's testable.
- `DistributionStatStrip.tsx` — the right-hand stat list + the
  milestone chips row. Pure presentational.
- `RunsSparkline.tsx` — tiny chronological line/bar chart. Wraps
  `LineChart` or hand-rolled SVG.
- `FormDeltaLine.tsx` — the "Last 10 mean ±X · median ±Y"
  presentational line. Color signing.
- `SuggestedSplitsRow.tsx` — rendering the splits via
  `PlayerLink`. Hidden when splits are empty.

**Reused:**

- `PlayerLink` (existing) — for suggested-splits navigation.
- `BarChart` — histogram primitive.
- `LineChart` — sparkline primitive.
- `useFilterDeps()` — fetch dep array (post-be4d755 idiom).
- `useFetch` — fetch wrapper.
- `Spinner` / `ErrorBanner` — loading + error states.

### 9.7 Window toggle state — URL-encoded (revised 2026-05-05)

URL key: `dist_window`. Values: `scope` (default — absent param) |
`last_10` | `last_60d` | `last_6mo` | `last_1yr`. Read via
`useSearchParams` (NOT `useFilters` — `dist_window` is panel-local,
not a FilterBar field; adding it to FILTER_KEYS would pollute the
link-builder contract).

The toggle label was renamed from "Lifetime" to "Scope" 2026-05-06.
"Lifetime" was misleading on filtered scopes — IPL 2024 isn't a
player's lifetime when that filter is active. The internal API
field on the response stays named `lifetime` for backward compat;
only the UI label and URL value changed.

```ts
const [searchParams, setSearchParams] = useSearchParams()
const distWindow = (searchParams.get('dist_window') ?? 'lifetime') as DistWindow

function setDistWindow(next: DistWindow) {
  const sp = new URLSearchParams(searchParams)
  if (next === 'lifetime') sp.delete('dist_window')
  else sp.set('dist_window', next)
  setSearchParams(sp)  // replace: false — toggle clicks land in history
}
```

Note: `lifetime` is the default and is encoded by **omitting** the
param (not `?dist_window=lifetime`) so URLs without the param read
as the canonical default. Saves one URL noise param on the common
case.

Toggle clicks DO land in browser history (back-button works to
restore previous window). This matches the user's "all state
encoded in URL" principle — the receiver of a shared link sees
exactly what the sender was looking at.

Per `feedback_urlstate.md` (useSearchParams race condition): when
multiple URL writes happen near-simultaneously (e.g. user toggles
the window AND the filter refetch resolves), use the
`useSearchParams` setter form that takes a function (or compute
the next state from `searchParams` synchronously inside the
handler). The pattern above is safe because the handler reads
`searchParams` once and writes once; React batches the update.

### 9.8 Sparkline rolling overlay (Lifetime only)

For the Lifetime window with `n_innings ≥ 10`, overlay a rolling-10
mean line on the sparkline. Computed client-side from
`observations.map(o => o.runs)`. Skipped on Last 10 / Last 60d (the
window is short enough that rolling-N is degenerate).

For lifetime samples below 10 innings, skip the overlay (sparkline
still renders the bare runs sequence).

### 9.9 Out of scope (explicit deferral list)

- **Phase decomposition UI in the Distribution panel.** Data is in
  the response (per-innings phase obs + rollup) so future SR-by-
  phase / dot-by-phase / boundary-by-phase work is purely a render
  layer above the same payload. The existing `By Phase` tab
  already covers the v1 visual need.
- **Per-innings sparkline annotations** (e.g. dots colored by
  dismissal type, shape coded by phase share). Reserved for v1.5.
- **Confidence overlays on the histogram** (e.g. a faded bar
  showing bootstrapped confidence at small n). Tied to the
  sample-size floor decision in §6.4 — out of v1.
- **Compare-tab integration.** The Distribution dossier on the
  Teams Compare tab is a separate spec slice (§6.7).
- **Bowler / fielder distribution dossiers** — the entire endpoint
  + UI for those is a separate slice; their APIs aren't built yet.

### 9.10 Tests

**Integration** (`tests/integration/batter_distribution.sh`) — the
agent-browser end-to-end. Per the CLAUDE.md "browser-agent run
mandatory for frontend work" rule + "integration tests must self-
anchor against SQL" rule:

- Load `/batting?player=ba607b88&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024`.
- Assert the Distribution panel renders with the histogram, stat
  strip, milestone chips, sparkline, form-delta line, and splits
  row visible.
- For each window button, click it and assert the histogram + stat
  strip + milestone chips redraw to the new window's values. The
  form-delta line MUST NOT change between clicks (window-independent).
  The suggested-splits row MUST NOT change.
- After each window-toggle click, assert the URL updated to
  `?dist_window=last_10` / `last_60d` (and that toggling back to
  Lifetime DELETES the param, not sets it to `lifetime`). Hit
  browser back-button; assert the previous window is restored.
- Deep-link with `?dist_window=last_10` directly; assert the panel
  renders that window selected on first paint (no flash of
  Lifetime).
- Numeric anchors derived from `cricket.db` at runtime via
  `sqlite3` per the SQL-anchored-tests rule:
  - Lifetime `Mean` and `Median` text must match
    `(SUM(runs)/COUNT(*)` and SQL median of the per-innings
    aggregation for the same scope.
  - `P(≥50)` chip text must match `count(o.runs ≥ 50)/n_innings`.
  - Phase rollup: not displayed in v1 UI; not asserted at the DOM
    level. Sanity test in §8.10 already covers the partition.
- Click a suggested-split link; assert the URL updates to the
  emitted `params` and the page re-fetches with the new scope.
- Inning aux: with `?inning=0`, assert the panel re-fetches and
  numbers change (the click-after-mount test must include
  InningToggle interaction since the §8 endpoint honours
  AuxParams; per the post-`be4d755` rule).

**Coverage discipline:** the integration test must exercise the
panel at multiple PlayerSearch entry points (search-and-pick AND
deep-link) since `useFilterDeps` is shared across batting
endpoints. Per the "tests must cover EVERY call site of a shared
abstraction" rule.

**Type-check** — `tsc -b` from project root must pass with the new
types in `types.ts` (per the `feedback_typecheck_use_build` memory
note: cricsdb's root `tsconfig.json` has `files:[]`; `tsc --noEmit`
checks nothing — use `tsc -b`).

**Browser-agent verification** mandatory before claiming done:
load each of the 19 regression URLs from §8 in a real browser via
the `agent-browser` skill, exercise the window toggle, hover the
histogram bars, and click each suggested-split link. Verify the
panel doesn't break on the empty-scope URL or the inning-aux
URLs.

### 9.11 Implementation order

Five atomic commits matching the §8 ordering pattern:

1. **Types + fetcher** — `BatterDistribution` types in
   `types.ts`; `getBatterDistribution` in `api.ts`. tsc-clean.
2. **Histogram + stat strip** — `RunsHistogram.tsx`,
   `DistributionStatStrip.tsx`, palette extension. Standalone-
   testable from a Storybook-style page or a temporary test mount.
3. **Sparkline + form delta + splits row** — `RunsSparkline.tsx`,
   `FormDeltaLine.tsx`, `SuggestedSplitsRow.tsx`.
4. **Panel orchestration + Batting.tsx integration** —
   `BatterDistributionPanel.tsx`; mount in `Batting.tsx` between
   stat row 1 and stat row 2; window toggle state.
5. **Integration test + docs** —
   `tests/integration/batter_distribution.sh`;
   `internal_docs/codebase-tour.md` mention; spec post-impl pass.

After commit 4, run agent-browser through the 19 regression URLs
from §8 to verify rendering before commit 5.

---

## 10. Patterns established for bowler / fielder / team slices

The batter v1 slice (§8 + §9, plus the v2/v3/v4 follow-up commits
2026-05-05 → 2026-05-06) settled a stack of conventions that the
sibling specs should reuse. Don't re-decide these per discipline
unless there's a concrete reason — that's how parallel helpers
drift.

### 10.1 Backend conventions

- **Single-payload + window-toggle.** Return lifetime + every form
  window (last_10 / last_60d / last_6mo / last_1yr) in ONE
  response. Frontend toggle redraws from the in-memory payload;
  no refetch on toggle. Same shape for every window — caller
  picks the dossier by key.
- **Pure aggregation function.** Separate the SQL master-sample
  query from the aggregate-the-list pure function. The same pure
  function powers lifetime AND each form window, AND falls cleanly
  to a `null`-shape on n=0 (no exceptions on empty samples).
  Reference: `_innings_master_sample` + `_distribution_dossier` +
  `_form_windows` in `api/routers/batting.py`.
- **Hard form windows, not exponential decay.** Last-10 (count-
  bound, no calendar), last-60d / 6mo / 1yr (calendar-anchored).
  Decay weighting is harder to communicate and not what users
  mean by "form".
- **`as_of_date` query param** for deterministic regression tests
  on calendar-anchored windows. Production callers omit it
  (defaults to today).
- **Phase columns on every per-innings observation.** Even when
  the discipline doesn't surface SR-by-phase yet, store the
  per-phase (runs, balls) on each observation row so future
  by-phase work is a pure derivation — no re-query, no schema
  change.
- **Conditional probabilities — null when denominator is 0.**
  `p_50_given_30 = count(≥50) / count(≥30)` is undefined when
  no innings reached 30. Subset invariant `count(≥A) ≤ count(≥B)`
  for A > B keeps ratios in [0, 1]; pin in sanity tests.
- **Match existing convention even when docs disagree.** The
  'retired not out' exclusion in `how-stats-calculated.md` is
  3-element, but every batting endpoint uses 2-element — new
  endpoints follow the 2-element convention for cross-endpoint
  consistency. Don't fork the rule for one new endpoint; fix
  the doc-vs-code drift in a separate sweep if needed.
- **Verify column names against schema.** `delivery.over_number`
  is 0–19 (not `over_idx`); `wicket.kind` literals use
  `'caught'` / `'run_out'` / `'caught_and_bowled'` (underscored
  for multi-word). One sqlite3 query saves a half-hour of
  debugging.

### 10.2 Regression workflow

When intentionally changing the response shape of an existing
endpoint with a `urls.txt` inventory:

1. Commit A: flip affected URLs `REG → NEW` (separate, earlier
   commit — the runner keys on HEAD's `kind`).
2. Commit B: backend shape change.
3. Commit C: flip URLs `NEW → REG` (locks in new shape as the new
   ground truth).

Established 2026-05-06 on the v2 form-windows extension.

### 10.3 Frontend / UX conventions

- **`ScopedPageHeader`** is the canonical page header. Pass
  `omit={[...]}` on dossier pages where the page subject would
  duplicate a scope axis.
- **URL state for window-toggle**. `?dist_window=lifetime|last_10|
  last_60d|last_6mo|last_1yr`, default = absent param. Toggle
  clicks land in browser history. Per-panel keys use a panel-
  specific prefix (e.g. `dist_window` for Distribution panel) to
  avoid collision.
- **Histogram bin width-10, fixed edges, milestone-aligned.** Bins
  comparable across players; render rule "always show through bin
  [90,99] floor; above 99 truncate to bin containing max obs"
  preserves distribution shape AND makes tail batters' empty
  right side a recognizable bowler signal.
- **Color tiers for runs distribution**: failure (0–9 muted red)
  / building (10–49 neutral) / fifty (50–99 sage) / century
  (100–149 ochre) / rare (150+ deeper gold). Defined as
  `WISDEN_RUN_TIERS` in `palette.ts`.
- **Probability chips in a single full-width flex row that wraps**
  on narrow viewports. Not a stacked 2-row grid (vertically
  asymmetric). Order: simples (P(≤10) P(≥30) P(≥50) P(≥100))
  followed by conditionals (neutral slate polarity).
- **Sparkline conventions** (revised 2026-05-06): two reference
  lines per metric tab — **solid black thicker** for the player's
  scope baseline (`distribution.lifetime.X`, NOT the active form
  window) + **gray thinner** for the gender-tiered global anchor
  (`globalBaselines.ts`). Plus a **red oxblood** rolling-N mean
  overlay on the Scope window when n ≥ 10 (skipped on form
  windows because the sample is too short for smoothing to be
  meaningful). Color reservations: red is **only** for the
  rolling-mean overlay (NOT for tier coloring or reference lines);
  the failure/wicketless histogram tier was flipped from muted
  red to muted indigo (`#7090A8`) accordingly. Legend swatches:
  solid 14×1.5–2px rectangles, NOT em-dash glyphs.
- **Tier-coloured sparkline bars + matching histograms** (revised
  2026-05-06): each per-innings/per-spell bar is colored by its
  milestone tier matching the histogram bins. Lets users scan
  the chronological sparkline and answer "in how many great
  innings was he poor?" / "of his good spells, how many were
  big bags?" at a glance.

  **3-tier unified palette** (revised 2026-05-06) — every metric
  uses **3 tiers max** AND the same 3 colors are shared across
  histogram bars, sparkline bars, and probability chips. The bin
  label still conveys the exact range; the color tells you which
  tier — and a chip about a particular threshold uses the same
  color as the histogram bar at that threshold.

  Three semantic tier colors:
  - **INDIGO** (`#7090A8`) — poor outcome for the player
  - **SAGE**   (`#7A8E6A`) — regular / typical
  - **OCHRE**  (`WISDEN.ochre`) — really good ("hot")

  Polarity convention — colors are tied to OUTCOME for the player,
  not to bin index. So the same color means "good for player" on
  every tab:
  - Higher-is-better (runs / wickets / SR): low = indigo (poor),
    mid = sage (typical), high = ochre (good)
  - Lower-is-better (economy / runs conceded): low = ochre (good),
    mid = sage (typical), high = indigo (poor)

  Chip-tint helper: `WISDEN_TIER_TINTS` exports
  `{indigo, sage, ochre}` → `{bg: rgba, fg: hex}` pairs. Each chip
  caller picks the tier its threshold falls in (e.g.
  `<ProbChip tint={T_OCHRE} ...>` for `P(≥3)` on the wickets tab,
  matching the strike-tier histogram bar).

  Tier breaks:
  | Metric | low | mid | high |
  |---|---|---|---|
  | Batter Runs       | 0-9 (failure indigo)   | 10-49 (building) | 50+ (impact sage)      |
  | Batter SR         | <100 (slow indigo)     | 100-149 (mid)    | 150+ (explosive sage)  |
  | Bowler Wickets    | 0 (wicketless indigo)  | 1-2 (building)   | 3+ (strike gold)       |
  | Bowler Economy    | <7 (tight sage)        | 7-9 (mid)        | ≥9 (loose ochre)       |
  | Bowler Runs Conc. | ≤25 (tight sage)       | 25-40 (mid)      | >40 (loose ochre)      |

  Both the histogram (BarChart `colorBy="tier"` + 3-color
  scheme) AND the sparkline (per-bar `color` from the matching
  tier helper) use the same palette per metric — the visual
  encoding is consistent whichever chart you scan first.

- **Sparkline bar opacity 0.5** so the reference lines (black
  scope baseline + gray gender-global) and the rolling-mean
  overlay (red) read clearly above the bar mass. Earlier
  iterations at 0.85-0.95 made the lines harder to spot above
  the dense bar texture on long careers.
- **Sparkline interaction model** (revised 2026-05-06): desktop
  bars are wrapped in `<a href="/matches/:matchId">` with hover
  tooltip (date + key value). On mobile (< 720px), the bar
  `<a>` elements get `pointer-events: none` via CSS — sparkline
  is purely impressionistic; the season-tick axis below carries
  date context. Reason: bar widths vary 26px → 1.5px depending
  on observation count, and hover doesn't exist on touch.
- **Season-tick axis** below the sparkline. For each unique
  calendar year in the date-asc obs, place a tick + 2-digit-year
  label (`'14`) at the percentage offset of the year's first obs.
  Render as plain HTML with absolute positioning at percentage
  offsets (NOT inside the SVG) — the SVG's
  `preserveAspectRatio="none"` stretches foreignObject children
  horizontally and overlaps labels at wide widths.
- **Form-delta line is window-INDEPENDENT.** Reads from
  `dossier.form.delta`; doesn't redraw when window toggle changes.
  All windows shown side-by-side as a single flex-wrap line that
  drops to multi-row on narrow viewports.
- **Suggested-splits 4-tier ladder** (`scopeLinks.ts::suggestedSplits`,
  Python mirror in `api/scope_links.py`):
  T1 specific (drop season; keep tournament+type+series),
  T2 type-only (drop tournament+series; keep type+season),
  T3 all-cricket (drop type+tournament+series; keep season),
  T4 all-time. Skip a tier when its drop is a no-op or the
  result equals a later tier's params. Lockstep-tested via
  `tests/sanity/scope_splits_fixtures.json`.
- **`team_type` is a NARROWING axis, not identity.** Identity is
  `gender` only across broaden splits. Opponent / venue isolation
  links use a separate `_identity_with_type` helper that DOES
  preserve team_type (so "vs Australia" reads in international
  context).
- **Mobile viewport check is mandatory** before commit. Inline
  `style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(220px, 320px)' }}`
  passes desktop verification but ZEROES the histogram on a 390-
  wide phone. Use a `wisden-*` CSS class with a `@media
  (max-width: 720px)` fallback to stack to single column.
  `agent-browser set viewport 390 844 && reload` is the test.

### 10.4 Test conventions

- **Sanity invariants self-anchor against SQL.** Every numeric
  assertion (n_innings, runs.total, mean, median, P(≥50)) must
  derive from sqlite3 at runtime, never hardcoded.
- **Lockstep fixtures for cross-language helpers.** A shared
  JSON fixture drives BOTH the Python and TypeScript implementations
  (e.g. `tests/sanity/scope_splits_fixtures.json` for
  `suggested_splits` + `suggestedSplits`).
- **Integration test exercises every entry point** (deep-link,
  search-and-pick, click-after-mount on every shared toggle —
  per the post-`be4d755` rule).
- **Empty-scope marker** as a dedicated regression URL (e.g.
  `?filter_venue=Nonexistent%20Ground`) catches the n=0 null-shape
  branch.

---

## 11. Bowler v1 — distribution dossier (DRAFT)

> Sibling of §8. Bowler-only, single endpoint, three sibling
> distribution blocks under one master sample. Reuses every §10.1
> backend convention; the bowler-specific design calls (master
> sample shape, qualifying-spell threshold, anchored conditional
> ladder, Wilson confidence intervals on every probability,
> derived strike-rate / average) are settled below before any
> code is written.
>
> **Status: DRAFT — not yet implemented.** Pending build per the
> §11.10 implementation order.

### 11.1 Scope pinning

**In v1:**

- Endpoint: `GET /api/v1/bowlers/{id}/distribution?{FilterParams}&min_balls=12&as_of_date=YYYY-MM-DD`.
- Master sample: per-innings tuple — one row per `(match, innings
  the bowler bowled in)` clearing the `min_balls` qualifying-spell
  threshold.
- **Three sibling distribution blocks** under one payload:
  - `wickets` — zero-inflated discrete count (§4 shape 2).
  - `runs_conceded` — skewed continuous, absolute runs per innings
    (§4 shape 3).
  - `economy` — continuous, per-over rate per innings (§4 shape 1).
- Phase columns (PP / Mid / Death) on every per-innings observation
  AND aggregated rollup. Stores `runs`, `balls`, `wickets` per
  phase so future "death-overs SR / economy / wicket rate" work
  is a pure derivation — no re-query, no schema change.
- Form windows: last_10 / last_60d / last_6mo / last_1yr — same
  dossier shape as lifetime (single-payload + window-toggle, §10.1).
- Suggested splits embedded in the response — calls existing
  `api/scope_links.py::suggested_splits` (no change to the helper).
- Every existing `FilterParams` axis honoured (gender, team_type,
  tournament, season range, opponent, venue, team_class).
- **Wilson 95% CI** computed server-side on every probability
  (simples + conditionals) — every `p_*` field ships as
  `{ value, num, denom, ci_low, ci_high }`.

**Explicitly out of v1** (settled in discussion 2026-05-06):

- **Kaplan–Meier survival curve for bowling SR.** Censoring in T20
  is structural (4-over cap / captain rotation), not informative.
  Under a constant-hazard assumption the K–M MLE collapses to
  `total_balls / total_wickets`, which we ship as a derived scalar
  `pool_strike_rate`. K–M is the right tool for an experimental
  modeling stage / downloadable dataset, not the descriptive
  dossier; deferred.
- **Empirical-Bayes / hierarchical shrinkage on rare-event chips**
  (e.g. P(≥5│≥2) shrunk toward a league prior). The whole point
  of the dossier is to surface bowler-specific signal; shrinkage
  toward the league mean erases it. Wilson CIs cover the small-n
  honesty story without pooling. Population-prior shrinkage is a
  use case for the future "league-baseline distributions" slice.
- **Quantile vector** (P5/P25/…/P95). Same project-wide decision
  as batter — variance + std + mean + median + milestone CDF
  readouts cover the consistency story.
- **Per-innings strike-rate distribution / per-innings average
  distribution.** Both have undefined values in zero-wicket
  innings (and >40% of T20 spells are wicketless). The per-innings
  ratios are dominated by zero-divisions; the pool ratio is the
  honest summary. SR and average ship as scalar pool stats only.
- **Confidence overlays beyond Wilson** (bootstrap / Bayesian
  credible intervals). Wilson is the closed-form one-line answer;
  Jeffreys would add a numerical-methods dependency for sub-pp
  improvement at our sample sizes.
- **Frontend / UI** — covered separately in §12.
- **Fielder / team distribution dossiers** — sibling specs.

### 11.2 Per-innings observation row

For bowler `id` under `FilterParams F` and `min_balls=M` (default
12), materialise one row per innings where the bowler bowled at
least `M` legal balls. Columns:

| Column | Definition |
|---|---|
| `innings_id` | `innings.id` |
| `match_id` | `innings.match_id` |
| `date` | `match.date` (used for ordering + form windows) |
| `balls` | `COUNT(legal balls)` bowled by `id` (`extras_wides = 0 AND extras_noballs = 0`) |
| `runs_conceded` | `SUM(d.runs_total)` over **all deliveries** (includes wides + no-balls runs) — matches existing `/bowlers/.../summary` convention |
| `wickets` | `COUNT(wicket WHERE delivery.bowler_id = id AND wicket.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field'))` — bowler-credited only, mirrors existing endpoints' 4-element exclusion list |
| `dots` | `COUNT(legal balls WHERE runs_total = 0)` |
| `boundaries_conceded` | `COUNT(legal balls WHERE (runs_batter = 4 AND COALESCE(runs_non_boundary,0)=0) OR runs_batter = 6)` |
| `wides` | `COUNT(deliveries WHERE extras_wides > 0)` |
| `noballs` | `COUNT(deliveries WHERE extras_noballs > 0)` |
| `runs_pp` / `balls_pp` / `wickets_pp` | as `runs_conceded` / `balls` / `wickets` plus `WHERE delivery.over_number BETWEEN 0 AND 5` |
| `runs_mid` / `balls_mid` / `wickets_mid` | `WHERE over_number BETWEEN 6 AND 14` |
| `runs_death` / `balls_death` / `wickets_death` | `WHERE over_number BETWEEN 15 AND 19` |

Master-sample SQL filter uses `_bowling_legal_filter` (already
present in `api/routers/bowling.py`) which calls
`FilterParams.build_side_neutral(has_innings_join=True, aux=aux)`
— bowlers' team is the **opposite** side of the batting innings,
so side-neutral team filtering is required (NOT the side-aligned
`build()` used by batters).

**Qualifying threshold applied at master-sample time**: `HAVING
balls >= :min_balls` after the GROUP BY. Every downstream
aggregate, every form window, every milestone is computed over
the qualifying-spell sample — there is no "all spells including
cameos" view at v1. Cameo cricket (1-over fillers) is tracked by
existing endpoints; it's deliberate noise here.

`min_balls` default `12` (= 2 legal overs). The API accepts 0 (no
filter) for completeness; `agent-browser` and `tests/integration`
exercise both default and `min_balls=0`. UI default and the
documented "qualifying spell" definition stay at 12. Bumping to
18 (3 overs) is a UX call for v2 if the noise floor still bothers
us; the param is the knob.

Ordered `match.date ASC, innings.innings_number ASC` — date-asc
ensures `observations[]` doubles as the sparkline data without an
extra sort.

### 11.3 Wilson 95% CI helper

New module `api/wilson.py`:

```python
import math

def wilson_ci(num: int, denom: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson 95% confidence interval for a binomial proportion.
    Returns (None, None) when denom == 0 (undefined). Bounded in
    [0, 1] always; non-degenerate at num == 0 or num == denom.
    """
    if denom <= 0:
        return (None, None)
    p = num / denom
    z2 = z * z
    den = 1.0 + z2 / denom
    center = (p + z2 / (2.0 * denom)) / den
    half = z * math.sqrt(p * (1.0 - p) / denom + z2 / (4.0 * denom * denom)) / den
    return (max(0.0, center - half), min(1.0, center + half))


def prob_record(num: int, denom: int) -> dict:
    """Standard probability shape: value + num + denom + Wilson CI.
    `value` is None when `denom == 0` (undefined ratio); CI bounds
    likewise. Uniform across simples (denom = n_innings) and
    conditionals (denom = count(≥anchor))."""
    if denom <= 0:
        return {"value": None, "num": num, "denom": 0,
                "ci_low": None, "ci_high": None}
    lo, hi = wilson_ci(num, denom)
    return {"value": round(num / denom, 4), "num": num, "denom": denom,
            "ci_low": round(lo, 4), "ci_high": round(hi, 4)}
```

Single import site for both bowler v1 (this section) and the
batter retrofit (§13). No scipy dependency; closed-form math, no
edge-case branches needed beyond `denom == 0`.

### 11.4 Aggregate calculations — three sibling blocks

Each block is a self-contained dossier computed by a pure function
over `obs[]`. The same `_form_windows` slicer reused from §8.6
runs each window through the same aggregator.

#### 11.4.1 `wickets` block (zero-inflated count)

| Field | Formula | Note |
|---|---|---|
| `total` | `sum(o.wickets)` | pool wickets |
| `mean_per_innings` | `total / n_innings` | what to expect next match |
| `median` | `median([o.wickets for o in obs])` | usually 0 or 1 — the zero-inflation tell |
| `variance` | sample variance, `n−1` | |
| `std` | `sqrt(variance)` | |
| `observations` | full per-innings tuple list (date-asc) | |

**Milestones — simples** (denom = `n_innings`), in `wickets.milestones`:

| Field | Formula |
|---|---|
| `p_zero` | `count(w == 0) / n_innings` |
| `p_geq_1` | `count(w ≥ 1) / n_innings` |
| `p_geq_2` | `count(w ≥ 2) / n_innings` ← anchor for conditionals |
| `p_geq_3` | `count(w ≥ 3) / n_innings` |
| `p_geq_4` | `count(w ≥ 4) / n_innings` |
| `p_geq_5` | `count(w ≥ 5) / n_innings` |

**Milestones — conditionals**, **all anchored at ≥2** (denom =
`count(w ≥ 2)` for every conditional — stable denominator across
the chain, avoids the cascading-noise problem of a chained ladder
P(≥k│≥k−1) where each rung's denom shrinks geometrically):

| Field | Formula | Reading |
|---|---|---|
| `p_3_given_2` | `count(w ≥ 3) / count(w ≥ 2)` | of his impactful spells, how often a 3-fer |
| `p_4_given_2` | `count(w ≥ 4) / count(w ≥ 2)` | how often did the 2-wicket spell climb to a 4-fer |
| `p_5_given_2` | `count(w ≥ 5) / count(w ≥ 2)` | the rare 5-fer rate, conditioned on a real spell |

Anchored ladder rationale: with denom held at `count(≥2)` the
binomial SE is a function of `n` (the anchor) and `p` (the
upper-rung rate). At small `p` the SE shrinks, so the upper-rung
conditionals are *less* noisy than they would be in a chain
(P(≥5│≥4) chain on 1/4 → ±22pp; P(≥5│≥2) anchored on 1/35 →
±~6pp). Chain conditionals are the right shape for batter
"conversion" narrative (continuous milestones, dense at all
levels); bowler upper rungs are rare events on a discrete count,
and the magnitude framing — "of his real spells, what fraction
became big bags?" — matches cricket vocabulary better.

Every probability ships via `prob_record(num, denom)` from §11.3
— uniform `{value, num, denom, ci_low, ci_high}` shape.

#### 11.4.2 `runs_conceded` block (skewed continuous)

| Field | Formula |
|---|---|
| `total` | `sum(o.runs_conceded)` |
| `mean_per_innings` | `total / n_innings` |
| `median` | `median([o.runs_conceded for o in obs])` |
| `variance` / `std` | sample variance / its sqrt |
| `observations` | already on master sample |

**Milestones — simples only**, denom = `n_innings`:

| Field | Reading |
|---|---|
| `p_leq_15` | "tight in absolute" — under 15 runs in a qualifying spell |
| `p_leq_25` | "decent" |
| `p_geq_40` | "expensive" |
| `p_geq_50` | "leaked" — career-bad spell |

No conditionals (continuous data; "given he leaked >25, did he
leak >40" doesn't carry the cricket narrative weight that the
discrete-count climb does).

#### 11.4.3 `economy` block (continuous, per-over rate)

| Field | Formula | Note |
|---|---|---|
| `pool` | `(total_runs_conceded × 6) / total_balls` | balls-weighted; the "career economy" number |
| `mean_per_innings` | `mean([o.runs_conceded × 6 / o.balls for o in obs])` | unweighted mean of per-innings economies — different number, useful for histogram center-of-mass |
| `median_per_innings` | `median(per-innings economies)` | |
| `variance` / `std` | sample variance of per-innings economies | |
| `per_innings` | `[round(o.runs_conceded × 6 / o.balls, 2) for o in obs]` | derived from observations[]; does NOT live on master sample (computed once at dossier-build time) |

**Milestones — simples only**, denom = `n_innings`:

| Field | Reading |
|---|---|
| `p_econ_leq_6` | "tight spell" |
| `p_econ_leq_7` | "decent" |
| `p_econ_geq_9` | "expensive" |
| `p_econ_geq_10` | "leaked" |

Both `pool` AND `mean_per_innings` are surfaced — they answer
different questions. Pool is the conventional career-economy
number opponents quote; mean-of-per-innings-economy is the
distribution's center of mass and is what the histogram axis
needs labelled. Document both in the API docs.

#### 11.4.4 Pool-derived scalars (cross-block)

At the top of every dossier (alongside `n_innings`), compute:

| Field | Formula | Note |
|---|---|---|
| `pool_strike_rate` | `total_balls / total_wickets` if `total_wickets > 0` else `null` | balls per wicket, the conventional career SR |
| `pool_average` | `total_runs_conceded / total_wickets` if `total_wickets > 0` else `null` | runs per wicket — same exposure as batter `average`, kept as an honest scalar |

These replace per-innings SR / average distributions (out of v1,
§11.1). They sit at the dossier level, not under any of the three
blocks, because they cross-link wickets + runs.

#### 11.4.5 Phase rollup

```jsonc
"phase": {
  "powerplay": { "runs_total": 78, "balls_total": 96, "wickets_total": 4, "innings_active": 12 },
  "middle":    { "runs_total": ..., "balls_total": ..., "wickets_total": ..., "innings_active": ... },
  "death":     { ... }
}
```

`innings_active` = innings where the bowler bowled ≥ 1 ball in
that phase. The right denominator for "his death-overs economy"
— don't penalise an opener-spell bowler who never bowls death.

**Invariant**: `powerplay.runs_total + middle.runs_total +
death.runs_total == runs_conceded.total` (within phase
boundaries; sanity check in §11.7). Same partition holds for
`balls_total` and `wickets_total`.

### 11.5 Form windows

Reuse the §8.6 mechanism verbatim, including the scope-anchored
cutoff `anchor = min(today, max_obs_date)`:

| Window | Definition |
|---|---|
| `form.last_10` | `ORDER BY date DESC, innings_number DESC LIMIT 10` |
| `form.last_60d` | `WHERE date >= anchor − 60 days` |
| `form.last_6mo` | `WHERE date >= anchor − 180 days` |
| `form.last_1yr` | `WHERE date >= anchor − 365 days` |

Each window has the **full dossier shape** — `wickets`,
`runs_conceded`, `economy`, `phase`, and the cross-block scalars.

`form.delta` block — for each window × two metrics, ship 8
entries on the **focal** stat per block:

```jsonc
"form": {
  "delta": {
    "last_10_wickets_mean_minus_lifetime":   <float>,
    "last_10_economy_pool_minus_lifetime":   <float>,
    "last_60d_wickets_mean_minus_lifetime":  <float>,
    "last_60d_economy_pool_minus_lifetime":  <float>,
    "last_6mo_wickets_mean_minus_lifetime":  <float>,
    "last_6mo_economy_pool_minus_lifetime":  <float>,
    "last_1yr_wickets_mean_minus_lifetime":  <float>,
    "last_1yr_economy_pool_minus_lifetime":  <float>
  }
}
```

Wickets-mean delta uses `wickets.mean_per_innings`; economy delta
uses `economy.pool` (the conventional one) so the form line reads
"is he taking more wickets right now? going for fewer runs an
over right now?" — the two questions cricket actually asks.

### 11.6 Suggested splits

No change to `api/scope_links.py`. The `suggested_splits(scope)`
helper from §8.7 is generic — it walks any `FilterParams`-shaped
scope and emits the 4-tier broaden ladder. Bowler endpoint
includes the same `suggested_splits` field in its response.

### 11.7 Endpoint shape

```
GET /api/v1/bowlers/{id}/distribution?{FilterParams}&min_balls=12&as_of_date=YYYY-MM-DD
```

`min_balls` (int, default 12, ge=0) — qualifying-spell threshold.
`as_of_date` (ISO date, optional) — anchors the calendar form
windows for deterministic regression tests.

Response sketch (single window shown; lifetime + each form window
have identical shape):

```jsonc
{
  "scope": { "tournament": "IPL", "season_from": "2024", ... },
  "thresholds": { "min_balls": 12 },
  "lifetime": {
    "n_innings": 87,
    "pool_strike_rate": 18.4,
    "pool_average": 22.1,
    "wickets": {
      "total": 102,
      "mean_per_innings": 1.17,
      "median": 1,
      "variance": 1.41,
      "std": 1.19,
      "observations": [
        { "innings_id": ..., "match_id": ..., "date": "2024-04-12",
          "balls": 24, "runs_conceded": 28, "wickets": 3,
          "dots": 11, "boundaries_conceded": 2, "wides": 1, "noballs": 0,
          "runs_pp": 0, "balls_pp": 0, "wickets_pp": 0,
          "runs_mid": 6, "balls_mid": 6, "wickets_mid": 1,
          "runs_death": 22, "balls_death": 18, "wickets_death": 2 },
        ...
      ],
      "milestones": {
        "p_zero":     { "value": 0.31, "num": 27, "denom": 87, "ci_low": 0.22, "ci_high": 0.42 },
        "p_geq_1":    { "value": 0.69, "num": 60, "denom": 87, "ci_low": 0.58, "ci_high": 0.78 },
        "p_geq_2":    { "value": 0.40, "num": 35, "denom": 87, "ci_low": 0.30, "ci_high": 0.51 },
        "p_geq_3":    { "value": 0.14, "num": 12, "denom": 87, "ci_low": 0.08, "ci_high": 0.23 },
        "p_geq_4":    { "value": 0.05, "num":  4, "denom": 87, "ci_low": 0.02, "ci_high": 0.11 },
        "p_geq_5":    { "value": 0.01, "num":  1, "denom": 87, "ci_low": 0.00, "ci_high": 0.06 },
        "p_3_given_2":{ "value": 0.34, "num": 12, "denom": 35, "ci_low": 0.21, "ci_high": 0.51 },
        "p_4_given_2":{ "value": 0.11, "num":  4, "denom": 35, "ci_low": 0.05, "ci_high": 0.26 },
        "p_5_given_2":{ "value": 0.03, "num":  1, "denom": 35, "ci_low": 0.01, "ci_high": 0.14 }
      }
    },
    "runs_conceded": {
      "total": 1842, "mean_per_innings": 21.17, "median": 20,
      "variance": 87.4, "std": 9.35,
      "milestones": {
        "p_leq_15":  { "value": ..., "num": ..., "denom": 87, "ci_low": ..., "ci_high": ... },
        "p_leq_25":  { ... },
        "p_geq_40":  { ... },
        "p_geq_50":  { ... }
      }
    },
    "economy": {
      "pool": 6.81,
      "mean_per_innings": 7.04,
      "median_per_innings": 6.75,
      "variance": 4.12, "std": 2.03,
      "per_innings": [7.0, 5.25, 9.75, ...],
      "milestones": {
        "p_econ_leq_6": { ... },
        "p_econ_leq_7": { ... },
        "p_econ_geq_9": { ... },
        "p_econ_geq_10":{ ... }
      }
    },
    "phase": {
      "powerplay": { "runs_total": 412, "balls_total": 540, "wickets_total": 28, "innings_active": 71 },
      "middle":    { ... },
      "death":     { ... }
    }
  },
  "form": {
    "last_10":  { /* full lifetime-shape dossier */ },
    "last_60d": { ... },
    "last_6mo": { ... },
    "last_1yr": { ... },
    "delta": {
      "last_10_wickets_mean_minus_lifetime": +0.3,
      "last_10_economy_pool_minus_lifetime": -0.4,
      ...
    }
  },
  "suggested_splits": [
    { "label": "All IPL",          "params": { "tournament": "IPL" } },
    { "label": "All cricket 2024", "params": { "season_from": "2024", "season_to": "2024" } },
    { "label": "All-time",         "params": {} }
  ]
}
```

### 11.8 Implementation pointers

- **New endpoint** at `bowling_distribution` in
  `api/routers/bowling.py`. Mirrors siblings
  `/bowlers/{id}/summary`, `/bowlers/{id}/by-innings`, etc.
- **`_innings_master_sample_bowler(db, person_id, filters, aux,
  min_balls)`** in `bowling.py`. Reuses `_bowling_legal_filter`
  (which calls `FilterParams.build_side_neutral(...)`), the
  existing 4-element `wicket.kind` exclusion list, and the same
  phase boundaries as the batter master sample.
- **`_distribution_dossier_bowler(observations)`** — pure function
  computing the three sibling blocks + phase rollup + pool
  scalars. Empty samples return a sane null shape (no exceptions
  on n=0).
- **`_form_windows_bowler(observations, today)`** — slices the
  observation list into the four windows, runs the aggregator on
  each, emits the bowler-specific delta block (wickets-mean +
  economy-pool, not batter's mean+median).
- **`api/wilson.py`** — new module. `wilson_ci(num, denom)` +
  `prob_record(num, denom)` helpers. Used by both bowler v1 and
  the batter retrofit (§13).
- **No frontend changes in this scope** — §12 covers the panel.

### 11.9 Tests

**Sanity** (`tests/sanity/test_bowler_distribution_invariants.py`)
— mirrors the batter sanity layout. ~150 assertions across 4–5
scopes (Bumrah / Rashid / Boult / a part-time bowler like Kohli /
empty scope). Each assertion derives expected values from
sqlite3 against `cricket.db` at runtime per the SQL-anchored
rule.

- `n_innings == len(observations)` for `lifetime`, `last_10`,
  `last_60d`, `last_6mo`, `last_1yr`.
- `last_10.observations` is the contiguous date-asc tail.
- Phase partition: `powerplay.X + middle.X + death.X ==
  runs_conceded.total / wickets.total / balls_total` respectively
  (X ∈ {runs_total, wickets_total, balls_total}).
- `pool_strike_rate × wickets.total ≈ sum_balls` (within rounding).
- `pool_average × wickets.total ≈ runs_conceded.total`.
- `economy.pool == runs_conceded.total × 6 / sum_balls` (exact
  to 2 dp).
- For every milestone field: `value × denom ≈ num` (rounding-tol);
  `ci_low ≤ value ≤ ci_high`; `0 ≤ ci_low`; `ci_high ≤ 1`.
- Subset invariant: `count(w ≥ k) ≤ count(w ≥ k−1)` for k = 1..5.
- Conditional anchor invariant: `p_3_given_2.denom ==
  p_4_given_2.denom == p_5_given_2.denom == count(w ≥ 2)`.
- Wilson sanity: pin a known-input row (num=1, denom=35) against
  the analytic Wilson formula computed in the test (independent
  reproduction; catches an off-by-one in the helper).
- `min_balls=0` vs `min_balls=12`: `n_innings` strictly increases
  (or stays equal); when equal, every aggregate is identical.

**Sanity** (`tests/sanity/test_wilson_ci.py`) — table-driven
fixtures: (0, 0) → all-None; (0, 10) → [0, ~0.31]; (10, 10) →
[~0.69, 1]; (1, 35) → [~0.005, ~0.15]; pinned to 4-dp.

**Regression** (`tests/regression/bowler_distribution/urls.txt`)
— ~20-URL inventory: same 4 marquee bowlers × scopes (all-time,
IPL, IPL by season, vs-team, at-venue, season-only, inning aux
0/1, empty scope, default `min_balls` AND `min_balls=0`).
`as_of_date=2025-01-01` pinned for md5-diff stability.

**No agent-browser integration test in v1 backend** — API-only
slice. Integration arrives with the frontend (§12.10).

### 11.10 Implementation order — five atomic backend commits

1. `wilson: api/wilson.py + sanity test` — helper module shipped
   independently so the retrofit (§13) and v1 share one source.
2. `scope_links: no-op confirmation` — verify
   `suggested_splits(scope)` already produces correct output for
   the bowler endpoint test scopes; no code change expected.
3. `bowling: /bowlers/{id}/distribution endpoint` —
   `_innings_master_sample_bowler` + `_distribution_dossier_bowler`
   + `_form_windows_bowler` + the route.
4. `sanity: bowler distribution invariants` — ~150-assertion
   test suite per §11.9.
5. `regression: bowler_distribution urls.txt` — 20-URL inventory,
   all 200 against the live endpoint.

After commit 5, run `./tests/regression/run.sh bowler_distribution`
and confirm `0 REG drifted, 20 NEW changed, 0 NEW unchanged`.
Then flip `NEW → REG` in a separate commit to lock the shape.

---

## 12. Bowler v1 frontend — Distribution panel on `/bowling?player=X` (DRAFT)

> Sibling of §9. Lands the new "Distribution panel" on
> `frontend/src/pages/Bowling.tsx`. Consumes the §11 endpoint.
> Reuses every §10.3 frontend convention; bowler-specific extensions
> are the **two histograms** (discrete wickets + continuous economy)
> and the **CI rendering** on probability chips.
>
> **In scope:** window toggle (Scope / Last 10 / Last 60d / Last
> 6mo / Last 1yr); **metric tabs** (Wickets / Economy / Runs
> conceded — only one histogram + stat-strip + milestone-chip set
> visible at a time); per-metric histogram styling (discrete bars
> for wickets, continuous bins for economy + runs); milestone
> chips with Wilson CI tooltips; chronological sparkline (wickets
> per innings — always visible, doesn't switch with the metric
> tab); form delta line; suggested-splits link row.
>
> **Out of v1 frontend:** phase decomposition UI (data is in the
> response for future SR-by-phase work but the existing By Phase
> tab covers the visual need today); per-innings phase obs
> visualisations; Compare-tab integration; rendering K–M curves.

### 12.1 Layout

The current `/bowling?player=X` page renders:

```
PlayerSearch + InningToggle
─────────────────────────────────────────────────
ScopedPageHeader (name + flag + abbreviated scope)
Stat row 1  · Matches · Innings · Wickets · Average · SR · Economy
Stat row 2  · Dot% · Boundary% · Best · 4-fers · 5-fers
Tabs        · By Season | By Over | By Phase | vs Batters | …
```

The Distribution panel inserts **between row 1 and row 2** —
visually anchors to the SR/Economy/Wickets tiles in row 1.

### 12.2 Distribution panel anatomy

```
┌────────────────────────────────────────────────────────────────────────┐
│ Distribution                  [Scope | 10 | 60d | 6mo | 1y]  min=12    │  window toggle + threshold readout
│ [ Wickets ] [ Economy ] [ Runs conceded ]                              │  metric tabs
│                                                                        │
│ ┌─────────────────────────────────┬──────────────────────────────┐     │
│ │  (active-tab histogram)         │ (active-tab stat strip)      │     │
│ │  Wickets per innings (0..max)   │ Mean wkts        1.17        │     │
│ │  ▆ ▇ ▅ ▃ ▁ ▁                    │ Median wkts      1           │     │
│ │  0 1 2 3 4 5+                   │ Strike Rate      18.4        │     │
│ │                                 │ Economy           6.81        │     │
│ │                                 │ Average          22.1        │     │
│ │                                 │                              │     │
│ │                                 │ (active-tab milestone chips) │     │
│ │                                 │ P(0) 31% · P(≥1) 69%         │     │
│ │                                 │ P(≥2) 40% · P(≥3) 14%        │     │
│ │                                 │ P(≥4) 5% · P(≥5) 1%          │     │
│ │                                 │ ── conditionals (anchor ≥2) ─│     │
│ │                                 │ P(≥3│≥2) 34% · P(≥4│≥2) 11%  │     │
│ │                                 │ P(≥5│≥2) 3% [n=35]           │     │
│ └─────────────────────────────────┴──────────────────────────────┘     │
│                                                                        │
│ ▁▃▂▅▁▇▂▁▃▆▅▁▂  ← chronological sparkline (wickets per innings)         │  always visible (NOT tab-switched)
│                                                                        │
│ Form: 10 wkts +0.3 · econ −0.4   60d ... · 6mo ... · 1y ...            │
│                                                                        │
│ Compare to:  All IPL  ·  All cricket 2024  ·  All-time                 │
└────────────────────────────────────────────────────────────────────────┘
```

**Tab semantics.** The metric tabs swap the **histogram + stat
strip + milestone chips** as a single unit. Each tab presents its
metric's complete view:

| Tab | Histogram | Stat strip | Milestones |
|---|---|---|---|
| **Wickets** | discrete bars 0..max(5+), `WISDEN_WICKET_TIERS` color | mean / median wkts + pool SR + pool average | 6 simples (P(0)…P(≥5)) + 3 conditionals anchored at ≥2 |
| **Economy** | continuous bins 1 RPO across [3, 13+], pool reference line | pool econ + mean per innings + median per innings + std | 4 simples (P(econ ≤ 6 / ≤ 7 / ≥ 9 / ≥ 10)) |
| **Runs conceded** | continuous bins 5 runs across [0, max], floored at [0, 60] | runs total + mean + median + std | 4 simples (P(≤15 / ≤25 / ≥40 / ≥50)) |

**What stays visible across tabs** (window-dependent but
metric-independent): the wickets-per-innings sparkline, the
form-delta line, the suggested-splits row. These read the same
data regardless of which metric tab is active — the sparkline is
the bowler's signature wicket-rhythm timeline (wickets is the
headline stat); the form-delta combines wickets+economy in one
line; splits are scope-keyed not metric-keyed.

**Mobile.** One histogram on screen at a time + the stat strip
beneath it (single column below 720px via `wisden-*` media query)
keeps the panel readable on phones. The previous "two stacked
histograms" design forced both into a single mobile column, halved
each, and made neither legible.

#### 12.2.0 Metric tab URL state — `?dist_metric=`

Encoded in the URL: `?dist_metric=wickets|economy|runs`. Default
= absent → `wickets` (the headline metric — bowler's identity is
wicket-taking first).

```ts
const distMetric = (searchParams.get('dist_metric') ?? 'wickets') as DistMetric

function setDistMetric(next: DistMetric) {
  const sp = new URLSearchParams(searchParams)
  if (next === 'wickets') sp.delete('dist_metric')
  else sp.set('dist_metric', next)
  setSearchParams(sp)  // toggle clicks land in browser history
}
```

Same idiom as `dist_window` (§9.7). Default encoded by absence
keeps share-link URLs clean. Tab clicks land in history so
back-button restores the prior tab.

Cross-tab persistence: if a future page also uses metric tabs,
each panel uses a panel-local prefix (`dist_metric` for the
Distribution panel) to avoid collisions.

#### 12.2.1 Window toggle — same mechanism as §9.2.1

URL key `dist_window`, values `scope` (default; absent param) |
`last_10` | `last_60d` | `last_6mo` | `last_1yr`. Same key as
the batter panel — there's only ever one Distribution panel
mounted on a page. Per `feedback_state_location.md`, share-link
reproducibility is the contract.

The threshold readout (`min=12`) renders next to the toggle as a
small italic. Reflects `response.thresholds.min_balls`. Not
toggleable in v1 — bumping it is a URL-edit operation
(`?min_balls=18`); fine for power users, fine to defer a UI
control.

#### 12.2.2 Wickets histogram — discrete bars

Bin-width 1 across the integer range `[0, max(observations.wickets)]`,
floored at 5+ minimum (always render bars 0..5, even when nobody
in scope took more than 3, so a non-strike bowler's empty right
side reads "this isn't a wicket-taker" at a glance — same logic
as the batter [0,9]–[90,99] floor in §9.2.2). Above 5, render
through `max(observations.wickets)` (rare for one bowler to top 6
in a T20 innings; 7-fer terminal bin defined for forward
compatibility).

Bin color coding (new constant `WISDEN_WICKET_TIERS` in
`palette.ts`):

| Bin | Tier | Visual |
|---|---|---|
| 0 | wicketless | muted slate |
| 1, 2 | building | neutral |
| 3 | 3-fer | sage |
| 4 | 4-fer | ochre |
| 5+ | 5-fer+ | gold highlight |

Hover: `{wickets}: N innings ({pct%})`. Mean / median markers as
vertical thin lines (NOT bin-snapped — they sit at fractional
positions between bars).

#### 12.2.3 Economy histogram — continuous

Bin-width 1 RPO across `[3, 13]` (10 bins) with a `13+` terminal
bin for the far-right tail. Always-render-floor at `[3, 13]` so
every bowler's chart spans the same x-axis — comparable across
players, mirroring the batter histogram convention.

Color: a single neutral palette (no tiers — economy is continuous,
the milestone chips carry the threshold reading; tiering the
histogram bars would double-encode and clutter).

Pool-economy reference line (vertical solid black, like the batter
sparkline 20-run line in §9.2.4) at `economy.pool`.

#### 12.2.4 Runs-conceded tab

Continuous histogram, bin-width 5 runs across `[0,
max(observations.runs_conceded)]`, floored at `[0, 60]` so
parsimonious bowlers' empty right side is recognizable at a
glance. No tier coloring — neutral palette like the economy
histogram (continuous metric; milestone chips carry the threshold
reading).

Stat strip shows `runs_conceded` block fields (total / mean /
median / std). Milestone chips: P(≤15) / P(≤25) / P(≥40) /
P(≥50).

Less prominent than wickets/economy in narrative weight (runs
conceded is a derived consequence of economy × balls), so it sits
in the **third tab position** — clicked into when the user wants
to see "did he leak in absolute terms" rather than "what's his
RPO shape". Power-user view, but a peer view.

#### 12.2.5 Stat strip

Right of the wickets histogram, label/value list:

**Group 1 — point summaries** (vertical, Wickets-tab labels shown):

```
Mean wkts       1.17          ← wickets.mean_per_innings
Median wkts     1             ← wickets.median
Total wkts      102           ← wickets.total
Strike Rate     18.4          ← lifetime.pool_strike_rate (balls / wicket)
Economy         6.81          ← economy.pool (runs × 6 / balls)
Average         22.1          ← lifetime.pool_average (runs / wicket)
```

**Label convention (revised 2026-05-06).** The cricket-conventional
career numbers — strike rate, economy, average — render under the
plain cricket names, NOT prefixed with "Pool" (internal jargon).
"Pool" / `lifetime.pool_*` is the API field name describing the
implementation (balls-weighted aggregate of all qualifying-spell
deliveries) and stays in the spec + types; the user-facing
labels are just `Strike Rate` / `Economy` / `Average`. Each row
carries a hover tooltip spelling out the formula + unit so a
new-to-cricket user gets the unit ("balls per wicket", "runs per
over", "runs per wicket") without needing the label to do that
work.

On the Economy tab, where we surface BOTH the career number and
the per-innings statistics in the same strip, the labels keep
the distinction explicit: `Economy` (career, balls-weighted) /
`Mean / spell` (unweighted mean of per-spell economies — the
histogram's centre of mass) / `Median / spell` (per-spell median).
Tooltips spell out the difference.

**Group 2 — milestone chips, two rows** (single flex container,
flex-wrap, separator between simples and conditionals):

```
P(0) 31%  ·  P(≥1) 69%  ·  P(≥2) 40%  ·  P(≥3) 14%  ·  P(≥4) 5%  ·  P(≥5) 1%
─── conditionals (anchor ≥2) ───
P(≥3│≥2) 34%  ·  P(≥4│≥2) 11%  ·  P(≥5│≥2) 3%
```

Each chip renders the value as `XX%`. **Hover** (or tap on touch)
reveals `[lo, hi] (n=denom)` — e.g. `P(≥5│≥2) 3% [1-14] (n=35)`.
Below a sample-size floor (`denom < 10`) the chip styling fades
to a low-opacity treatment that signals "small n, read with
caution"; the value stays visible. `null` denom (impossible by
construction for simples; possible for conditionals when no
innings hit the anchor) renders as `—` not `0%`.

#### 12.2.6 Sparkline (per-tab) + season-tick axis

Per-spell sparkline rendered chronologically across full panel
width. Bar value depends on the active **metric tab**:

| Metric tab | Bar value | Bar color |
|---|---|---|
| Wickets       | `o.wickets` (0..6+, discrete) | wicket-tier (`WISDEN_WICKET_TIERS`) |
| Economy       | `o.runs_conceded × 6 / o.balls` (RPO) | neutral slate |
| Runs conceded | `o.runs_conceded` (absolute) | neutral slate |

**Two reference lines per metric** (revised 2026-05-06; v1 had a
single mean line which was uninformative because every bar
clusters around it):

| Line | Color | Reads | Source |
|---|---|---|---|
| Scope baseline | green (`WISDEN.forest` `#3F7A4D`) | "where this bowler usually sits under the active filter scope" | `distribution.lifetime.X` (the lifetime block of the filter scope, NOT the active form window — stays put across window toggles, only moves when a FilterBar narrowing changes the scope) |
| Gender-global   | black (`WISDEN.ink` `#1A1714`)    | "where any bowler usually sits at this tier" | gender-tiered constants in `components/bowling/globalBaselines.ts` (`gender=male` → men's bucket; `gender=female` → women's; unset → all-T20) |

Y-axis max is bumped to `max(data_max, player_ref, global_ref)`
so the global anchor is always on-chart even when the player has
been way below it across the whole window.

**Global constants** (whole numbers, derived from `cricket.db`
2026-05-06 across all qualifying spells ≥ 12 legal balls):

```
                wkts/spell  runs/spell  RPO
Men   bucket    1           26          8
Women bucket    1           20          6
Unset bucket    1           25          7
```

Refresh the SQL yearly (the constants drift over time as the
women's tier-2 game normalizes upward, etc.). The single SQL
query lives in commit 6343779 and the values get updated in
`globalBaselines.ts`.

(Revised 2026-05-06; the original v1 spec had the sparkline
metric-INDEPENDENT — always wickets — but the per-tab data is
the more honest "what happened in each game" signal under the
metric the reader is currently inspecting.)

**Below the sparkline: season-tick axis.** For each unique
calendar year in the date-asc observation list, place a small
tick + label (`'14`, `'24`, etc. — compact 2-digit year) at the
x-position of that year's first observation. Adds calendar-anchor
context to a sparkline that would otherwise be just "values over
a sequence" — readers can locate a slump or hot streak in real
cricket time. Renders as plain HTML with absolutely-positioned
labels at percentage offsets (NOT inside the SVG), avoiding the
`preserveAspectRatio="none"` foreignObject horizontal-stretch
problem.

**Desktop interaction** (≥ 720px viewport):

- Hover any bar → native `<title>` tooltip: `2024-04-12 · 3 wkts
  (24b, 15r)` (Wickets tab) or `2024-04-12 · econ 3.75 (15r in
  24b, 3 wkts)` (Economy tab) etc.
- Click any bar → navigate to `/matches/:matchId`. The bar is
  wrapped in a React Router `<a>` with `onClick` calling
  `useNavigate()`.

**Mobile interaction** (< 720px viewport):

- **None.** The bar `<a>` elements get `pointer-events: none` via
  the `.wisden-dist-sparkline a { pointer-events: none }` rule
  inside the `@media (max-width: 720px)` block.
- Sparkline is purely impressionistic on mobile. Reasoning:
  bar widths range from 26px (sparse bowler scopes, 13 spells)
  down to 1.5px (career batter scopes, 250+ obs); inconsistent
  tap targets are worse than no tap targets, and hover doesn't
  exist on touch.
- The season-tick axis carries the date-context affordance on
  mobile; navigation to specific matches happens via the existing
  By Innings tab.

#### 12.2.7 Form delta line

Window-INDEPENDENT (per §10.3). Reads from `response.form.delta`,
renders all four windows side-by-side as a flex-wrap line:

```
Form: Last 10 wkts +0.3 · econ −0.4   Last 60d wkts ... · econ ...   ...
```

Color delta numbers by sign — positive wickets-mean = green
(taking more), negative = red. For economy the polarity flips:
positive economy delta = red (going for more), negative = green.
Document in the legend under the form line.

#### 12.2.8 Suggested-splits row

Identical to §9.2.6. Reads `response.suggested_splits`; renders
each via existing `PlayerLink` per `internal_docs/links.md`.

### 12.3 Empty / sparse states

Three cases (mirrors §9.3):

1. **No player selected** → panel doesn't render; `BowlingLandingBoard`.
2. **Lifetime `n_innings == 0`** → "No qualifying spells (≥ 12
   balls) under this filter — try widening the scope, or add
   `min_balls=0` to include cameos." Suggested-splits row still
   renders.
3. **Window `n_innings == 0` but lifetime non-empty** → window
   pane shows "No qualifying spells in the last 10 / 60d / 6mo /
   1y under this filter"; toggle stays active.

### 12.4 Types — `frontend/src/types.ts`

```ts
export interface ProbRecord {
  value: number | null
  num: number
  denom: number
  ci_low: number | null
  ci_high: number | null
}

export interface BowlerInningsObservation {
  innings_id: number
  match_id: number
  date: string
  balls: number
  runs_conceded: number
  wickets: number
  dots: number
  boundaries_conceded: number
  wides: number
  noballs: number
  runs_pp: number; balls_pp: number; wickets_pp: number
  runs_mid: number; balls_mid: number; wickets_mid: number
  runs_death: number; balls_death: number; wickets_death: number
}

export interface BowlerWicketsBlock {
  total: number
  mean_per_innings: number | null
  median: number | null
  variance: number | null
  std: number | null
  observations: BowlerInningsObservation[]
  milestones: {
    p_zero: ProbRecord
    p_geq_1: ProbRecord
    p_geq_2: ProbRecord
    p_geq_3: ProbRecord
    p_geq_4: ProbRecord
    p_geq_5: ProbRecord
    p_3_given_2: ProbRecord
    p_4_given_2: ProbRecord
    p_5_given_2: ProbRecord
  }
}

export interface BowlerRunsConcededBlock {
  total: number
  mean_per_innings: number | null
  median: number | null
  variance: number | null
  std: number | null
  milestones: {
    p_leq_15: ProbRecord
    p_leq_25: ProbRecord
    p_geq_40: ProbRecord
    p_geq_50: ProbRecord
  }
}

export interface BowlerEconomyBlock {
  pool: number | null
  mean_per_innings: number | null
  median_per_innings: number | null
  variance: number | null
  std: number | null
  per_innings: number[]
  milestones: {
    p_econ_leq_6: ProbRecord
    p_econ_leq_7: ProbRecord
    p_econ_geq_9: ProbRecord
    p_econ_geq_10: ProbRecord
  }
}

export interface BowlerDossier {
  n_innings: number
  pool_strike_rate: number | null
  pool_average: number | null
  wickets: BowlerWicketsBlock
  runs_conceded: BowlerRunsConcededBlock
  economy: BowlerEconomyBlock
  phase: {
    powerplay: { runs_total: number; balls_total: number; wickets_total: number; innings_active: number }
    middle:    { runs_total: number; balls_total: number; wickets_total: number; innings_active: number }
    death:     { runs_total: number; balls_total: number; wickets_total: number; innings_active: number }
  }
}

export interface BowlerDistribution {
  scope: Record<string, string>
  thresholds: { min_balls: number }
  lifetime: BowlerDossier
  form: {
    last_10: BowlerDossier
    last_60d: BowlerDossier
    last_6mo: BowlerDossier
    last_1yr: BowlerDossier
    delta: {
      last_10_wickets_mean_minus_lifetime: number | null
      last_10_economy_pool_minus_lifetime: number | null
      last_60d_wickets_mean_minus_lifetime: number | null
      last_60d_economy_pool_minus_lifetime: number | null
      last_6mo_wickets_mean_minus_lifetime: number | null
      last_6mo_economy_pool_minus_lifetime: number | null
      last_1yr_wickets_mean_minus_lifetime: number | null
      last_1yr_economy_pool_minus_lifetime: number | null
    }
  }
  suggested_splits: { label: string; params: Record<string, string> }[]
}
```

### 12.5 Components

**New** under `frontend/src/components/bowling/`:

- `BowlerDistributionPanel.tsx` — top-level orchestrator. Owns
  the metric-tab + window-toggle URL state. Renders the active
  tab's metric panel below the tab strip.
- `WicketsMetricPanel.tsx` — composite of `WicketsHistogram` +
  the wickets-specific stat strip (mean wkts, median wkts, pool
  SR, pool average) + wickets milestone chips (6 simples + 3
  ≥2-anchored conditionals).
- `EconomyMetricPanel.tsx` — composite of `EconomyHistogram` +
  economy stat strip (pool, mean per innings, median per innings,
  std) + economy milestone chips (4 simples).
- `RunsConcededMetricPanel.tsx` — composite of
  `RunsConcededHistogram` + runs-conceded stat strip (total,
  mean, median, std) + runs-conceded milestone chips (4 simples).
- `WicketsHistogram.tsx` / `EconomyHistogram.tsx` /
  `RunsConcededHistogram.tsx` — pure chart wrappers (each
  histogram primitive with its own bin scheme, color palette,
  reference line).
- `ProbChip.tsx` — **shared with batter retrofit** (§13). Renders
  a `ProbRecord` as `value%` with hover tooltip `[lo, hi] (n=denom)`,
  fades when `denom < 10`, shows `—` for null. Lives at
  `frontend/src/components/distribution/ProbChip.tsx` so both
  panels import from the same file.
- `WicketsSparkline.tsx` — per-innings wicket count over time.
  Always visible below the active metric panel; reads
  `currentWindow.wickets.observations` regardless of metric tab.
- `BowlerFormDeltaLine.tsx` — bowler-specific form line (wkts
  delta + economy delta polarities differ from batter).

**Reused:**

- `PlayerLink`, `BarChart`, `LineChart`, `useFilterDeps`,
  `useFetch`, `Spinner`, `ErrorBanner`.
- `WISDEN_RUN_TIERS` palette extended with `WISDEN_WICKET_TIERS`.
- The shared `ProbChip` component (§13 makes the existing batter
  panel adopt it too).

### 12.6 Tests

**Integration** (`tests/integration/bowler_distribution.sh`) —
agent-browser end-to-end. SQL-anchored numeric assertions.
Mirror the §9.10 layout:

- Load `/bowling?player=<bumrah>&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024`.
- Assert all sub-panels render (wickets histogram, economy
  histogram, stat strip, sparkline, form-delta, splits row).
- For each window button (Scope / 10 / 60d / 6mo / 1y), click and
  assert active-tab histogram + stat strip + milestone chips
  redraw; sparkline + form-delta line + splits row do NOT change.
- After each window click, assert URL state matches `?dist_window=...`
  (and absent param for Scope). Browser back-button restores
  prior window.
- For each metric tab (Wickets / Economy / Runs conceded), click
  and assert the histogram swaps to the metric-specific binning,
  the stat strip swaps fields, and the milestone chips swap to
  the metric-specific list. Sparkline does NOT change. URL state
  matches `?dist_metric=...` (absent for the default `wickets`
  tab). Browser back-button restores prior tab.
- Deep-link with `?dist_metric=economy&dist_window=last_60d`:
  panel renders the economy tab on the last_60d window on first
  paint (no flash of default).
- Hover P(≥5│≥2) chip — assert tooltip text `[ci_low%-ci_high%]
  (n=<denom>)` matches the API response exactly.
- Below sample-size floor (denom < 10): assert chip has the
  fade styling class.
- Numeric anchors via `sqlite3 cricket.db`:
  - `Mean wkts` text matches
    `SUM(wickets)/COUNT(*)` over the qualifying-spell sample.
  - `P(≥3) NN%` chip matches
    `count(w ≥ 3)/n_innings × 100`.
  - `Economy` (career, on the Economy tab) text matches
    `SUM(runs_total) × 6.0 / SUM(legal_balls)`.
- Inning aux: with `?inning=0` and `?inning=1`, panel re-fetches;
  numbers change.
- Mobile viewport: `set viewport 390 844 && reload` on the live
  panel — assert the histogram + stat strip stack vertically, the
  metric tabs and window-toggle chips wrap onto two rows if
  needed, and the active-tab content remains legible at that
  width.

**Browser-agent verification**: load each of the 20 regression
URLs from §11 in `agent-browser`; verify panel renders for each.
Mobile viewport check (`set viewport 390 844 && reload`) on a
representative URL — assert both histograms remain visible
(grid stacks below 720px per the `wisden-*` media-query
convention).

### 12.7 Implementation order — five atomic frontend commits

1. **Types + fetcher** — `BowlerDistribution` types in
   `types.ts`; `getBowlerDistribution` in `api.ts`. tsc-clean.
2. **Histograms + metric panels + ProbChip** — three histogram
   wrappers (`WicketsHistogram`, `EconomyHistogram`,
   `RunsConcededHistogram`), three composite metric panels
   (`WicketsMetricPanel`, `EconomyMetricPanel`,
   `RunsConcededMetricPanel`), shared `ProbChip.tsx` at
   `frontend/src/components/distribution/`, `WISDEN_WICKET_TIERS`
   palette extension.
3. **Sparkline + form-delta + splits row** — `WicketsSparkline.tsx`,
   `BowlerFormDeltaLine.tsx`. Reuse `SuggestedSplitsRow.tsx`
   if compatible; else trivial fork.
4. **Panel orchestration + Bowling.tsx integration** —
   `BowlerDistributionPanel.tsx` with metric-tab + window-toggle
   URL state; mount in `Bowling.tsx` between row 1 and row 2.
5. **Integration test + docs** —
   `tests/integration/bowler_distribution.sh`;
   `internal_docs/codebase-tour.md` mention; spec post-impl
   pass.

After commit 4, browser-agent through the 20 regression URLs.

---

## 13. Fielder v1 — distribution dossier (IMPLEMENTED)

> Sibling of §8 (batter) and §11 (bowler). Single endpoint, three
> sibling distribution blocks — catches / run-outs /
> (stumpings, keeper-only). The simplest of the three discipline
> dossiers per §3.3 + §7: per-match discrete counts dominated by
> zeros, tiny range (≤5 catches, ≤3 stumpings, ≤2 run-outs / match
> in T20). Reuses every §10.1 backend convention; the fielder-
> specific design calls (per-match unit, three milestones —
> `P(=0)` / `P(=1)` / `P(≥2)`, conditional stumpings tab, no phase
> decomposition, no per-innings ratios) are settled below before
> any code is written.
>
> **Status: DRAFT — not yet implemented.** Pending build per the
> §13.9 implementation order.

### 13.1 Scope pinning

**In v1:**

- Endpoint: `GET /api/v1/fielders/{id}/distribution?{FilterParams}&as_of_date=YYYY-MM-DD`.
- **Master sample: per-match tuple** — one row per match the
  player appears on the team sheet (`matchplayer.person_id = id`)
  under the filter scope. **Not per-innings.** Fielding events
  span both opponent-batting innings; the natural unit is the
  match itself (per spec §3.3). One bar per match on the
  sparkline; one per-match tuple in the histogram sample.
- **Three sibling distribution blocks** under one payload:
  - `catches` — per-match catch count (§4 shape 2, extreme
    zero-inflation).
  - `run_outs` — per-match run-out count, same shape, sparser
    tail.
  - `stumpings` — per-match stumping count, **only emitted when
    `innings_kept > 0`** (Tier-2 keeper detection per
    `keeperassignment`). Field is `null` for non-keepers.
- **Substitute catches excluded** from the `catches` sample.
  Surfaced separately as a top-level `substitute_catches` scalar
  for reconciliation against `/fielders/{id}/summary`. Subs field
  partial innings; including them inflates the per-match count
  for matches the player wasn't really on.
- **Caught-and-bowled excluded entirely** — it's bowler-credited
  and lives on the bowling dossier.
- Form windows: last_10 / last_60d / last_6mo / last_1yr — same
  dossier shape as the lifetime block (single-payload + window-
  toggle, §10.1). Unit is **matches**, not innings —
  `last_10 = ten most recent matches`.
- Suggested splits embedded — calls
  `api/scope_links.py::suggested_splits` unchanged.
- Every existing `FilterParams` axis honoured. Side-neutral team
  filtering at match grain (reuses the existing `_fielding_filter`
  pattern, dropping `has_innings_join`).
- **Wilson 95% CI** on every probability via `prob_record(num,
  denom)` from §11.3. No new helper.

**Explicitly out of v1:**

- **Phase decomposition.** A catch *has* a phase (the over the
  wicket fell), but the dossier unit is the match, and "P(catch
  in death overs)" is mostly position-dependent (slip vs deep)
  which the existing By-Phase tab already covers volumetrically.
- **Per-innings observation row.** A single match can produce
  catches across both opponent innings; bucketing into per-innings
  makes the keeper sample asymmetric (only the bowling-team
  innings). Per-match is the honest unit.
- **Conditional milestones.** No `P(≥2│≥1)` ladder. Three
  simples (`P(=0)`, `P(=1)`, `P(≥2)`) cover the discrete count
  exhaustively; conditioning on `≥1` shrinks denom by ~3× without
  adding signal a simple already exposes.
- ~~Mean-per-match hidden on catches / run-outs tabs.~~ Initial
  draft hid the mean on non-keeper tabs (it sits at ~0.3 and looks
  uninformative on its own), but quoting Std in the same strip
  without a Mean to anchor it is incoherent. **Revised 2026-05-07:
  uniform schema — Matches / Total / Mean per match / Median / Std
  on all three tabs.** Spread of a count distribution still needs
  a centre.
- **Frontend / UI** — covered separately in §14.
- **Team distribution dossier** — sibling spec.

### 13.2 Per-match observation row

For fielder `id` under `FilterParams F`, materialise one row per
match the player appeared on the team sheet, in scope.

| Column | Definition |
|---|---|
| `match_id` | `matchplayer.match_id` |
| `date` | `match.date` (used for ordering + form windows) |
| `catches` | `COUNT(fieldingcredit WHERE kind = 'caught' AND COALESCE(is_substitute, 0) = 0 AND fielder_id = id AND innings.match_id = match_id)` |
| `run_outs` | same shape, `kind = 'run_out'` (substitute-exclusion still applies) |
| `stumpings` | same shape, `kind = 'stumped'` (no substitute filter — sub keepers are not a thing) |
| `is_keeper` | `1` if any `keeperassignment.keeper_id = id` for any innings of this match; `0` otherwise |

Master-sample SQL filter uses `_fielding_filter` adapted to
match-grain (drop `has_innings_join=True`). Side-neutral team
filtering — fielder credits live on opposite-side innings.

Ordered `match.date ASC, match_id ASC` — date-asc ensures
`observations[]` doubles as the sparkline data without a sort.

**No qualifying-spell threshold.** Bowler v1 used `min_balls=12`
to drop cameo overs; the fielder analogue would be "did the
player field in at least one innings of the match", but
`matchplayer` membership already encodes that. A non-keeper who
plays the full match and takes zero catches is the *typical*
case, not a cameo.

### 13.3 Aggregate calculations — three sibling blocks

Each block is a self-contained dossier computed by a pure function
over `obs[]`. The three blocks have **identical shape** (only the
source column differs); a single `_count_block(obs, key)` helper
produces all three.

#### 13.3.1 `catches` / `run_outs` / `stumpings` block

| Field | Formula | Note |
|---|---|---|
| `total` | `sum(o[key])` | pool count over the window |
| `median` | `median([o[key] for o in obs])` | usually 0 |
| `variance` / `std` | sample variance / sqrt | |
| `mean_per_match` | `total / n_matches` | computed always; only surfaced in the stat strip on the stumpings tab (§14.2.4) |

`observations[]` lives at the dossier level (one shared list with
`catches` / `run_outs` / `stumpings` / `is_keeper` columns), not
duplicated per block.

**Milestones — three simples, denom = `n_matches`:**

| Field | Formula | Reading | Tier color |
|---|---|---|---|
| `p_zero` | `count(x == 0) / n_matches` | "blanked" | INDIGO |
| `p_one` | `count(x == 1) / n_matches` | "ticked over" | SAGE |
| `p_geq_2` | `count(x ≥ 2) / n_matches` | "multi-event match" | OCHRE |

**Three simples sum to 1** within rounding (sanity invariant in
§13.8). The three colors map directly to the histogram bars of
the same name.

No conditionals. No upper-rung milestones — counts cap at ~5/match
for catches and ~2/match for run-outs in T20; `P(≥3)` on
non-keepers would be < 1% with denom = career n_matches.

Every probability ships via `prob_record(num, denom)` from §11.3.

#### 13.3.2 Top-level scalars

At the dossier level (alongside `n_matches`):

| Field | Formula | Note |
|---|---|---|
| `n_matches` | `len(observations)` | denom for all three blocks' simples |
| `innings_kept` | sum of `keeperassignment` rows for the player in scope | drives the conditional-tab decision: stumpings block is emitted only when `> 0` |
| `substitute_catches` | `COUNT(fieldingcredit WHERE kind = 'caught' AND is_substitute = 1)` in scope | footnote — surfaced for full reconciliation against `/fielders/{id}/summary`; not part of any distribution block |

### 13.4 Form windows

Reuse the §8.6 mechanism, including the scope-anchored cutoff
`anchor = min(today, max_obs_date)`. Same four windows,
**match-grain**:

| Window | Definition |
|---|---|
| `form.last_10` | `ORDER BY date DESC, match_id DESC LIMIT 10` over observations |
| `form.last_60d` | `WHERE date >= anchor − 60 days` |
| `form.last_6mo` | `WHERE date >= anchor − 180 days` |
| `form.last_1yr` | `WHERE date >= anchor − 365 days` |

Each window has the **full dossier shape** — `catches`,
`run_outs`, `stumpings` (when applicable), and the top-level
scalars. `innings_kept` recomputes per window (a keeper who
stops keeping mid-career sees the stumpings block disappear in
recent windows — correct behaviour).

`form.delta` block — three deltas per window, on `mean_per_match`:

```jsonc
"form": {
  "delta": {
    "last_10_catches_mean_minus_lifetime":  +0.05,
    "last_10_run_outs_mean_minus_lifetime": -0.01,
    "last_10_stumpings_mean_minus_lifetime": +0.20,
    "last_60d_catches_mean_minus_lifetime":  ...,
    ...
  }
}
```

Stumpings deltas are `null` when lifetime `innings_kept == 0`.
The form delta line is the one place the small means surface for
non-keeper tabs — "is he in form?" is exactly what the form line
exists to answer.

### 13.5 Suggested splits

No change to `api/scope_links.py`. Same `suggested_splits(scope)`
helper from §8.7.

### 13.6 Endpoint shape

```
GET /api/v1/fielders/{id}/distribution?{FilterParams}&as_of_date=YYYY-MM-DD
```

`as_of_date` (ISO date, optional) — anchors the calendar form
windows for deterministic regression tests.

Response sketch (single window shown; lifetime + each form window
have identical shape):

```jsonc
{
  "scope": { "tournament": "IPL", ... },
  "lifetime": {
    "n_matches": 142,
    "innings_kept": 0,
    "substitute_catches": 3,
    "observations": [
      { "match_id": "...", "date": "2024-04-12",
        "catches": 2, "run_outs": 0, "stumpings": 0, "is_keeper": 0 },
      ...
    ],
    "catches": {
      "total": 71,
      "mean_per_match": 0.50,
      "median": 0,
      "variance": 0.62,
      "std": 0.79,
      "milestones": {
        "p_zero":  { "value": 0.61, "num": 87, "denom": 142, "ci_low": 0.53, "ci_high": 0.69 },
        "p_one":   { "value": 0.30, "num": 42, "denom": 142, "ci_low": 0.23, "ci_high": 0.38 },
        "p_geq_2": { "value": 0.09, "num": 13, "denom": 142, "ci_low": 0.05, "ci_high": 0.15 }
      }
    },
    "run_outs": {
      "total": 8, "mean_per_match": 0.06, "median": 0,
      "variance": 0.07, "std": 0.26,
      "milestones": {
        "p_zero":  { ... },
        "p_one":   { ... },
        "p_geq_2": { ... }
      }
    },
    "stumpings": null
  },
  "form": {
    "last_10":  { /* full lifetime-shape dossier */ },
    "last_60d": { ... },
    "last_6mo": { ... },
    "last_1yr": { ... },
    "delta": {
      "last_10_catches_mean_minus_lifetime":   +0.05,
      "last_10_run_outs_mean_minus_lifetime":  -0.01,
      "last_10_stumpings_mean_minus_lifetime": null,
      ...
    }
  },
  "suggested_splits": [ ... ]
}
```

### 13.7 Implementation pointers

- **New endpoint** at `fielding_distribution` in
  `api/routers/fielding.py`. Mirrors siblings.
- **`_match_master_sample_fielder(db, person_id, filters, aux)`**
  — reuses `_fielding_filter` adapted to match-grain.
- **`_distribution_dossier_fielder(observations)`** — pure
  function. Returns `null` for the stumpings block when
  `innings_kept == 0`. Empty samples return a sane null shape.
- **`_count_block(obs, key)`** — single helper used three times
  (`'catches'`, `'run_outs'`, `'stumpings'`).
- **`_form_windows_fielder(observations, today)`** — slices the
  observation list into the four windows, runs the aggregator on
  each, emits the delta block (stumpings-mean nullable).
- **`api/wilson.py`** — already shipped via §11.3.

### 13.8 Tests

**Sanity** (`tests/sanity/test_fielder_distribution_invariants.py`)
— ~80 assertions across 4 scopes (a non-keeper outfielder /
slip / a keeper like Dhoni / a keeper-only window for a
mostly-non-keeper player). Each assertion derives expected
values from sqlite3 against `cricket.db` at runtime per the
SQL-anchored rule.

- `n_matches == len(observations)` for `lifetime` and every form
  window.
- `last_10.observations` is the contiguous date-asc tail.
- **Three-simples-sum-to-1 invariant**: for each block,
  `p_zero.value + p_one.value + p_geq_2.value == 1.0` (within
  rounding).
- For every milestone: `value × denom ≈ num`; `ci_low ≤ value ≤
  ci_high`; `0 ≤ ci_low`; `ci_high ≤ 1`.
- `catches.total == sum(o.catches for o in observations)` (and
  for run_outs, stumpings).
- `mean_per_match × n_matches ≈ total` per block.
- `stumpings is null` ⟺ `innings_kept == 0`. Both sides tested.
- **Substitute reconciliation**: `catches.total +
  substitute_catches == /fielders/{id}/summary.catches` for the
  same scope.
- Form-window monotonicity: `last_10.n_matches ≤ 10`.

**Regression** (`tests/regression/fielder_distribution/urls.txt`)
— ~16-URL inventory: 4 marquee fielders × scopes (all-time, IPL,
IPL by season, vs-team, at-venue, season-only, empty scope —
keeper AND non-keeper present). `as_of_date=2025-01-01` pinned.

**No agent-browser integration test in v1 backend** — API-only
slice. Integration arrives with the frontend (§14.6).

### 13.9 Implementation order — three atomic backend commits

1. `fielding: /fielders/{id}/distribution endpoint` —
   `_match_master_sample_fielder` + `_distribution_dossier_fielder`
   + `_count_block` + `_form_windows_fielder` + the route.
2. `sanity: fielder distribution invariants` — ~80-assertion
   suite per §13.8.
3. `regression: fielder_distribution urls.txt` — 16-URL
   inventory, all 200 against the live endpoint.

After commit 3, run `./tests/regression/run.sh
fielder_distribution` and confirm `0 REG drifted, 16 NEW
changed, 0 NEW unchanged`. Then flip `NEW → REG` to lock the
shape. (One fewer commit than bowler — no Wilson helper, no
suggested_splits validation step.)

---

## 14. Fielder v1 frontend — Distribution panel on `/fielding?player=X` (IMPLEMENTED)

> Sibling of §9 (batter) and §12 (bowler). Lands the new
> Distribution panel on `frontend/src/pages/Fielding.tsx`.
> Consumes the §13 endpoint. Reuses every §10.3 frontend
> convention; fielder-specific extensions are the **discrete
> 3-bar histogram** (`0 / 1 / ≥2` per tab), the **conditional
> stumpings tab** (only rendered for keepers), and the
> **tab-dependent stat-strip schema** (drop mean for non-stumpings
> tabs).
>
> **In scope:** window toggle (Scope / Last 10 / Last 60d / Last
> 6mo / Last 1yr); **metric tabs** (Catches / Run-outs /
> Stumpings* — last is keeper-only); per-tab 3-bar histogram in
> the §10.3 INDIGO/SAGE/OCHRE palette; milestone chips with
> Wilson CI tooltips; chronological per-match sparkline (switches
> with the metric tab — height = events of that metric in the
> match); **horizontal reference line at y=1** on Catches and
> Run-outs tabs; **mean overlay** on Stumpings tab; form delta
> line; suggested-splits row.
>
> **Out of v1 frontend:** phase decomposition UI (no phase data
> in the §13 response); Compare-tab integration; "league
> baseline fielder" overlay (future league-baseline slice).

### 14.1 Layout

The Distribution panel inserts **between row 1 and the Tabs row**
on `/fielding?player=X` — anchored to the count tiles in row 1.

### 14.2 Distribution panel anatomy

```
┌────────────────────────────────────────────────────────────────────────┐
│ Distribution                  [Scope | 10 | 60d | 6mo | 1y]            │  window toggle
│ [ Catches ] [ Run-outs ] [ Stumpings* ]                                │  metric tabs (* keeper only)
│                                                                        │
│ ┌─────────────────────────────────┬──────────────────────────────┐     │
│ │  (active-tab histogram, 3 bars) │ (active-tab stat strip)      │     │
│ │   ▆                              │ Matches          142         │     │
│ │   ▇                              │ Total catches    71          │     │
│ │   ▆     ▃     ▁                  │ Median            0          │     │
│ │   0     1    ≥2                  │   (no avg/match shown)       │     │
│ │                                 │                              │     │
│ │                                 │ (milestone chips, single row)│     │
│ │                                 │ P(=0) 61%  P(=1) 30%  P(≥2)9%│     │
│ └─────────────────────────────────┴──────────────────────────────┘     │
│                                                                        │
│ ▁▁▆▁▁▆▆▁▁▁▆▆▁▆▁▁▁▆▁  ← per-match sparkline (heights = catches/match)  │
│ ───────────────────  ← reference line at y=1                          │
│                                                                        │
│ Form: 10  cat +0.05  ro −0.01    60d ...    6mo ...    1y ...          │
│                                                                        │
│ Compare to:  All IPL  ·  All cricket 2024  ·  All-time                 │
└────────────────────────────────────────────────────────────────────────┘
```

The Stumpings tab variant differs in three ways: stat strip adds
**Mean stumpings/match**; sparkline reference line is the player's
mean (red overlay, like batter/bowler); form line includes the
stumpings-mean delta.

#### 14.2.1 Metric tab URL state — `?dist_metric_f=`

Param name `dist_metric_f` (suffixed `_f` for fielder, parallel
to `dist_metric` for bowler — prevents cross-page bleed when the
user moves between Bowling and Fielding tabs in one session).
Values: `catches` (default, encoded by absence) | `run_outs` |
`stumpings`. Selecting `stumpings` on a non-keeper falls back to
`catches` silently (the tab isn't rendered).

#### 14.2.2 Window toggle — same mechanism as §9.2.1

URL state `?dist_window_f=`. Same five values as batter/bowler.

#### 14.2.3 Histogram — discrete 3 bars

Three bars at `0`, `1`, `≥2`, x-axis labels `0 / 1 / ≥2`, y-axis
auto-scaled to the tallest bar (`p_zero` is almost always
tallest). Bar tints: INDIGO / SAGE / OCHRE per spec §10.3.
Bar opacity 0.8 default with INDIGO at 1.0 (matches sparkline
override convention to keep the worst tier visible at 0.8).

**Linear y-axis.** Log scale was discussed and rejected: the
3-bar histogram has only three values to compare and the
visual contrast at linear scale is already informative ("the
zero bar dwarfs everything" IS the story). Log toggle deferred
to v2 if multi-discipline log support lands across all panels.

Each bar's tooltip: `"<count> matches (<percentage>%)"` —
mirrors the bowler-wickets discrete bars.

#### 14.2.4 Stat strip — uniform schema (revised 2026-05-07)

All three tabs render the same row set:
`Matches`, `Total <metric>`, `Mean per match`, `Median`, `Std`.

Earlier draft hid `Mean per match` on catches / run-outs (~0.3 looks
uninformative for a non-keeper outfielder), but the Std row is
incoherent without a centre to anchor it. Spread of a count
distribution still needs a mean — even when the mean itself reads
"this fielder takes a catch every third match." Uniformity wins
over per-tab schema variation.

Below the strip, **milestone chips** in a single flex row:

| Chip | Tint | Reading |
|---|---|---|
| `P(=0)` | INDIGO | "blanked" rate |
| `P(=1)` | SAGE | "ticked over" rate |
| `P(≥2)` | OCHRE | "multi-event" rate |

Hover/tap reveals Wilson CI: `61% (53–69%)`. Same `ProbChip`
component as bowler (§12.4).

#### 14.2.5 Sparkline — per-tab, per-match grain

One bar per match in chronological order. Height = events of
the active metric in that match (`o.catches`, `o.run_outs`, or
`o.stumpings`). Reuses `DistributionSparkline.tsx` with a new
`granularity="match"` prop (string label only — no behaviour
change beyond the season-tick axis hover text reading
"Match #X on YYYY-MM-DD" instead of "Innings #X").

**Reference line:**

| Tab | Reference line | Rationale |
|---|---|---|
| Catches | horizontal at **y=1** (gray, 1.5px) | "did anything happen this match?" — mean too low to anchor |
| Run-outs | horizontal at **y=1** (gray, 1.5px) | same |
| Stumpings | mean overlay (red, 1.2px) — same as batter/bowler rolling | keeper means are 1.5–2.5/match; informative |

**Bar opacity** — same 0.8 default with INDIGO override to 1.0
to keep zero-height bars visible (rendered in the 4px stub-zone
per the existing convention). Without the stub zone, the most
common match outcome (zero events) silently disappears from
the DOM-visible count — exactly the bug class flagged in the
bowler/batter sparkline rollout.

**Mobile:** `pointer-events: none` on the bar `<a>`s below
720px, mirroring the bowler/batter convention.

#### 14.2.6 Form delta line (revised 2026-05-07)

Two lines. The first shows the absolute scope-lifetime mean per
match so the deltas on the second line are self-anchoring — a
first-time reader doesn't have to remember or derive the baseline:

```
Scope baseline / match · cat 0.51 · ro 0.11 · st 0.08
Form (Δ vs baseline): last 10 cat −0.11 ro −0.01 st +0.02 · last 60d ... · last 6mo ... · last 1y ...
```

Stumpings entries omitted entirely (both baseline and delta) for
non-keeper players (`lifetime.stumpings === null`). The Δ symbol
on the second line carries the math; the baseline row above
defines what "vs baseline" means for each axis.

**Color discipline:** delta values render in **oxblood** (`#7A1F1F`)
regardless of sign. Form is a rolling concept; oxblood is the
codebase's established hue for it (sparkline rolling-mean overlay
uses the same value). Sign (`+`/`−`) carries direction. **No
green/red polarity** — that would conflate "above baseline" with
"good," and the form delta dossier doesn't make that value
judgment for fielders. The `—` sentinel renders in faint when the
window has no qualifying matches in scope.

#### 14.2.7 Suggested-splits row

Identical to §9.2.6 / §12.2.8.

### 14.3 Empty / sparse states

- `n_matches == 0` → placeholder card "No matches in scope" with
  a link back to "All IPL" / "All-time" splits.
- `n_matches < 10` → still render the dossier; chips show Wilson
  CIs, which carry the small-n honesty story without suppression.
- Stumpings tab on non-keeper → tab not in DOM; selecting via
  URL falls back to Catches.

### 14.4 Types — `frontend/src/types.ts`

```typescript
export type FielderCountBlock = {
  total: number
  median: number
  variance: number
  std: number
  mean_per_match: number
  milestones: {
    p_zero: ProbRecord
    p_one: ProbRecord
    p_geq_2: ProbRecord
  }
}

export type FielderObservation = {
  match_id: string
  date: string
  catches: number
  run_outs: number
  stumpings: number
  is_keeper: 0 | 1
}

export type FielderDistributionWindow = {
  n_matches: number
  innings_kept: number
  substitute_catches: number
  observations: FielderObservation[]
  catches: FielderCountBlock
  run_outs: FielderCountBlock
  stumpings: FielderCountBlock | null  // null when innings_kept == 0
}

export type FielderDistribution = {
  scope: ScopeRecord
  lifetime: FielderDistributionWindow
  form: {
    last_10: FielderDistributionWindow
    last_60d: FielderDistributionWindow
    last_6mo: FielderDistributionWindow
    last_1yr: FielderDistributionWindow
    delta: Record<string, number | null>  // 12 entries: 4 windows × 3 metrics
  }
  suggested_splits: SplitSuggestion[]
}
```

`tsc -b` catches consumers who try to read `stumpings.total` on
a non-keeper.

### 14.5 Components

| Component | File | Reuse from |
|---|---|---|
| `<FielderDistributionPanel/>` | `frontend/src/components/distribution/FielderDistributionPanel.tsx` | new — top-level container |
| `<FielderHistogram/>` | `frontend/src/components/distribution/FielderHistogram.tsx` | new — discrete 3-bar primitive |
| stat strip + milestone chips | inline in panel | new |
| `<DistributionSparkline/>` | already shipped | extend `granularity` prop to accept `"match"` |
| `<ProbChip/>` | already shipped (§12.4) | direct reuse |
| `<WindowToggle/>` | already shipped (§9.2.1) | direct reuse |

### 14.6 Tests

**Integration** (`tests/integration/fielder_distribution.sh`) —
SQL-anchored per §10.4.

1. Bar count == 3 always (the histogram has fixed bins).
2. **Bar height sums to `n_matches`** — the three bars partition
   the match sample exhaustively; sanity check that the DOM bars
   match the SQL counts.
3. Stumpings tab present iff `innings_kept > 0`. Two fixtures:
   keeper player (tab present, click reveals stumpings histogram)
   + outfielder (tab absent, no DOM node).
4. **Sparkline bar count == `n_matches`** from SQL — codified
   per-item-chart rule (CLAUDE.md "Sparkline / per-item chart bar
   count must match SQL"). Per-tab: the active metric's bar
   count must match the corresponding SQL count.
5. Reference line: y=1 visible on Catches/Run-outs tabs;
   mean-overlay visible on Stumpings tab.
6. Window toggle URL: `?dist_window_f=last_10` reproduces from
   share-link.
7. Metric tab URL: `?dist_metric_f=run_outs` reproduces from
   share-link.
8. Mobile viewport (390×844): histogram + sparkline + chips
   render without overflow; pointer-events disabled on sparkline
   bars below 720px.

**Sanity** assertions extend §13.8 with the three-simples-sum-
to-1 check at the API layer; integration covers the DOM side.

### 14.7 Implementation order — four atomic frontend commits

1. `fielding: types + api fetcher` — `FielderDistribution` types
   and `fetchFielderDistribution()` in `api.ts`. `tsc -b` clean.
2. `fielding: <FielderHistogram/> + <FielderDistributionPanel/>`
   — discrete 3-bar primitive + container with metric-tab +
   window-toggle wiring + stat strip + chips + sparkline.
3. `fielding: panel mounted on /fielding?player=X` — paste the
   panel between row 1 and the tabs row; conditional stumpings
   tab visibility wired off `innings_kept > 0`.
4. `tests: integration/fielder_distribution.sh` — 8-test
   SQL-anchored assertion script per §14.6.

After commit 4, run `agent-browser` against `/fielding?player=`
for a known keeper (Dhoni) and a known outfielder (Kohli) at
both desktop (1280×800) and mobile (390×844) viewports per the
verification rule.

---

## 15. Wilson-CI retrofit on batter conditionals (DRAFT)

Adding Wilson confidence intervals to bowler probabilities (§11.3)
makes the existing batter `milestones` shape — bare scalars — the
inconsistent one. Retrofit the batter endpoint so every probability
across the project uses the same `prob_record(num, denom)` shape.

**Affected endpoint:** `GET /api/v1/batters/{id}/distribution`.

**Affected fields** (every milestone in every dossier — lifetime +
4 form windows):

- Simples: `p_failure_10`, `p_25_plus`, `p_30_plus`, `p_50_plus`,
  `p_100_plus` — denom = `n_innings`.
- Conditionals: `p_50_given_30`, `p_70_given_50` — denom =
  `count(≥30)` and `count(≥50)` respectively.

**Shape change:** every field flips from `number | null` to
`ProbRecord` (per §11.3 / §12.4).

**Sequencing — strict per the regression-harness rule** (§10.2):

1. **Commit A**: flip all batter regression URLs `REG → NEW` in
   `tests/regression/batter_distribution/urls.txt`. Earlier than
   the shape change so the runner's `kind, hh = head[k]` reads
   the NEW tag from HEAD.
2. **Commit B**: shape change in `api/routers/batting.py` —
   replace the inline rounded-scalar emissions with calls to
   `prob_record(num, denom)`. Run `./tests/regression/run.sh
   batter_distribution`; expect `0 REG drifted, 19 NEW changed,
   0 NEW unchanged`.
3. **Commit C**: flip URLs `NEW → REG` to lock the new shape.
4. **Commit D — frontend retrofit**: update
   `BatterDistribution` types (`number | null` → `ProbRecord`);
   update the `MilestoneChips` render to use the shared
   `ProbChip` component. `tsc -b` then catches any consumer that
   still expects scalar.
5. **Commit E — sanity test update**: invariants in
   `test_batter_distribution_invariants.py` re-target the
   `.value` field; add Wilson CI + denom assertions matching
   the §11.9 bowler list.

**Why ship this in the bowler v1 arc, not a separate release:**
the cross-cutting `ProbChip` component lands once; otherwise we
ship the bowler panel with one chip component and a duplicate
batter chip with a different shape. The retrofit is small (~50
LOC across both sides) and the regression flip is the only
ceremony.

**Out of scope for this retrofit:** changing any batter milestone
threshold (still `failure_10`, `25_plus`, `30_plus`, `50_plus`,
`100_plus`, `50_given_30`, `70_given_50` — only the *shape* of
each value changes), or moving the batter conditionals to an
anchored ladder (the chain `P(≥50│≥30)` → `P(≥70│≥50)` is the
right cricket-conversion narrative for batting; bowler anchors
at ≥2 because rare events on a discrete count behave differently
— see §11.4.1).

---

## 16. Team v1 — distribution dossiers (IMPLEMENTED)

> Sibling of §8 (batter), §11 (bowler), §13 (fielder). Three
> separate per-discipline endpoints under the existing
> `/api/v1/teams/{team}/<discipline>/...` nesting:
> `/batting/distribution`, `/bowling/distribution`,
> `/fielding/distribution`. One per Teams-page tab; each tab's
> Distribution panel fetches only its own discipline's payload.
>
> Three endpoints, NOT one combined endpoint. API consistency
> demands it — every existing team analytic is split per
> discipline (`/batting/summary`, `/bowling/summary`, etc.; see
> `api/routers/teams.py`). The panel-per-tab mount on the
> frontend matches that split exactly: each tab fetches what it
> needs.
>
> Reuses every §10.1 backend convention — Wilson 95% CI via
> `prob_record(num, denom)` from §11.3, single-payload + window-
> toggle (§10.1), pure-aggregator-over-observations pattern
> shared with lifetime + form windows. The team-specific design
> calls (wider 50-run milestone gaps, over-aware doubling /
> finishing probabilities at the 10-over checkpoint) are
> settled below before any code is written.
>
> **Status: IMPLEMENTED 2026-05-08** across 9 commits (3 per
> discipline — endpoint + sanity + regression). 8936 SQL-anchored
> sanity assertions across 5 scopes per discipline; 48 regression
> URLs locked at REG. See dated session log at the foot of this
> file.

### 16.1 Common conventions across all three endpoints

**Endpoint URLs.** Three siblings:

```
GET /api/v1/teams/{team}/batting/distribution
GET /api/v1/teams/{team}/bowling/distribution
GET /api/v1/teams/{team}/fielding/distribution
```

All three accept the same query string: `{FilterParams}` plus
optional `as_of_date=YYYY-MM-DD` to anchor the calendar form
windows for deterministic regression. `team` is the team's
canonical name as it appears in the FilterBar team-search.

**Master-sample grain.** All three are per-innings:
- Team batting: one row per innings the team batted.
- Team bowling: one row per innings the team bowled (= the
  opponent's batting innings).
- Team fielding: one row per innings the team fielded (= the
  opponent's batting innings; identical to bowling). T20 has
  one batting innings per team per match, so "per-innings"
  collapses to "per-match" for the team-fielding case but the
  observation row stays innings-keyed for consistency with
  team bowling.

**Filter scope.**  The team's name itself is a path-param, NOT
a FilterParams field — use `m.team1 = :team OR m.team2 = :team`
at match level, then narrow the innings to the relevant side
per discipline:
- Batting: `i.team = :team` (team is batting in the innings).
- Bowling / Fielding: `i.team != :team` AND match-level pair
  matches (the opp is batting; team is fielding/bowling).

`FilterParams.filter_team` must be IGNORED on these endpoints
(the team-path-param IS the subject; FilterParams.filter_team
would either duplicate it or constrain to a different team).
`FilterParams.filter_opponent` works as expected (narrows to
matches against that opponent). Other axes (gender, team_type,
tournament, season, venue, team_class, series_type) all apply
verbatim.

**Form windows.** Same four as §10.1: `last_10`, `last_60d`,
`last_6mo`, `last_1yr`. `last_10` is the team's 10 most recent
innings (NOT 10 most recent matches; for batting + bowling the
distinction matters when the team played both sides on
back-to-back days). For the team-fielding endpoint the
distinction collapses (1 fielding innings per match).

**Wilson 95% CI.** Every probability ships via
`prob_record(num, denom)` from §11.3. No new helper.

**Suggested splits.** Same `api/scope_links.py::suggested_splits`
helper. The scope record passed in is the FilterParams-derived
scope dict; the team-path-param is NOT included in the splits
(splits broaden filter axes; the team itself is the dossier
subject).

**Out of v1 across all three:**

- Toss-decision conditional matrix (bat-first vs field-first
  win % across (toss-won, toss-lost) × (chose-bat, chose-bowl)).
  Sibling slice; not part of the Distribution panel. Tracked
  separately (`project_team_form_toss` in user memory).
- Identity-bearing sibling fields (`highest_total`,
  `lowest_all_out`, `best_pair`) — already on the existing
  `/teams/{team}/batting/summary` etc. endpoints; not folded
  into the distribution dossier (per §5).
- Home/away/neutral split. Future v2.
- Won/lost conditional probabilities (e.g. "P(≥180│won)") —
  conditioning on outcome is a different question shape;
  defer.

### 16.2 Team batting — `/api/v1/teams/{team}/batting/distribution`

#### 16.2.1 Per-innings observation row

| Column | Definition |
|---|---|
| `innings_id` | `innings.id` |
| `match_id` | `innings.match_id` |
| `innings_number` | 1 or 2 (first or second batting innings of the match) |
| `date` | `match.date` (used for ordering + form windows) |
| `runs` | `SUM(d.runs_total)` for the innings (final score) |
| `balls` | `COUNT(legal balls)` faced |
| `wickets` | `COUNT(wickets fallen in the innings)` (any kind) |
| `runs_at_10` | cumulative `SUM(d.runs_total)` over the first 60 legal balls (over-number 0 to 9 inclusive) |
| `wickets_at_10` | cumulative wickets fallen over the first 60 legal balls |
| `reached_10_overs` | `1` if the innings included at least 60 legal balls; `0` otherwise |
| `runs_pp` / `balls_pp` / `wickets_pp` | overs 1-6 (over_number 0-5) — phase rollup, mirrors batter §8.5 |
| `runs_mid` / `balls_mid` / `wickets_mid` | overs 7-15 (over_number 6-14) |
| `runs_death` / `balls_death` / `wickets_death` | overs 16-20 (over_number 15-19) |

**`reached_10_overs` definition rationale.** Innings curtailed
by rain / D-L / chase ending before 10 overs are excluded from
every "at 10" probability denom (see §16.2.3). All-out before
10 overs is also `reached_10_overs = 0` — the snapshot doesn't
exist; the all-out itself is captured as the regular `runs`
final and surfaces in the absolute-bin milestones.

Filtered + grouped per the FilterParams scope; ordered
`match.date ASC, innings.innings_number ASC`.

#### 16.2.2 Aggregate calculations — two sibling blocks

`runs` (skewed continuous) and `run_rate` (continuous, per-over).
Each is a self-contained dossier computed by a pure function.

**`runs` block:**

| Field | Formula |
|---|---|
| `total` | `sum(o.runs)` |
| `mean_per_innings` | `total / n_innings` |
| `median` | `median([o.runs])` |
| `variance` / `std` | sample variance / sqrt |
| `escalation_ratio_median` | median of `final_runs / runs_at_10` over innings with `reached_10_overs=1 AND runs_at_10 > 0` (paired stat for the doubling chip; §16.2.3) |
| `observations` | full per-innings tuple list |

**Milestones — `runs` block, simples (denom = `n_innings`):**

| Field | Reading | Tier color |
|---|---|---|
| `p_lt_100`  | "collapse" | INDIGO |
| `p_geq_100` | "got there" | SAGE |
| `p_geq_150` | "par-plus" | SAGE |
| `p_geq_200` | "explosive" | OCHRE |
| `p_geq_230` | "elite" | OCHRE |

**Conditional chain ladder** (each rung's denom = the rung
below — matches the batter §8 conversion narrative; the natural
cricket reading is "got past N → kicked on past M"):

| Field | Formula |
|---|---|
| `p_150_given_100` | `count(≥150) / count(≥100)` |
| `p_200_given_150` | `count(≥200) / count(≥150)` |
| `p_230_given_200` | `count(≥230) / count(≥200)` |

**Over-aware doubling** (denom = innings with
`reached_10_overs = 1 AND runs_at_10 > 0`; the latter avoids
0/0 division when a team is 0 at 10):

| Field | Formula | Reading |
|---|---|---|
| `p_double_at_10` | `count(final_runs ≥ 2 × runs_at_10) / denom` | "given X at halfway, doubled" |

`escalation_ratio_median` (above) is the paired magnitude stat —
"how big is the typical escalation?" Pairs with `p_double_at_10`
on the chip strip.

**`run_rate` block** (continuous, per-over):

| Field | Formula | Note |
|---|---|---|
| `pool` | `(total_runs × 6) / total_balls` | balls-weighted; the conventional career RR |
| `mean_per_innings` | `mean([o.runs × 6 / o.balls])` | unweighted mean of per-innings RR |
| `median_per_innings` | `median(per-innings RR)` | |
| `variance` / `std` | sample variance of per-innings RR | |
| `per_innings` | `[o.runs × 6 / o.balls for o in obs if o.balls > 0]` |

**Milestones — `run_rate` block, simples** (high RR is good for
batting — polarity FLIPPED relative to bowler economy):

| Field | Reading | Tier color |
|---|---|---|
| `p_rr_leq_7` | "slow" | INDIGO |
| `p_rr_leq_8` | "par-low" | SAGE |
| `p_rr_geq_9` | "fast" | OCHRE |
| `p_rr_geq_10`| "explosive" | OCHRE |

#### 16.2.3 Phase rollup

Same shape as bowler v1 §11.4.5:

```jsonc
"phase": {
  "powerplay": { "runs_total": ..., "balls_total": ..., "wickets_total": ..., "innings_active": ... },
  "middle":    { ... },
  "death":     { ... }
}
```

`innings_active` always equals `n_innings` for batting (every
innings has at least one ball in PP for batting teams) — kept
for shape symmetry with bowling.

#### 16.2.4 Form windows + delta

Same four windows. Delta block surfaces:

```jsonc
"form": {
  "delta": {
    "last_10_runs_mean_minus_lifetime":         <float>,
    "last_10_run_rate_pool_minus_lifetime":     <float>,
    "last_60d_runs_mean_minus_lifetime":        <float>,
    "last_60d_run_rate_pool_minus_lifetime":    <float>,
    /* ... 8 entries total: 4 windows × 2 metrics */
  }
}
```

#### 16.2.5 Endpoint shape

```
GET /api/v1/teams/{team}/batting/distribution?{FilterParams}&as_of_date=YYYY-MM-DD
```

Response shape mirrors §11.7 (bowler) but with the team-batting
blocks. Single-payload + window-toggle pattern.

### 16.3 Team bowling — `/api/v1/teams/{team}/bowling/distribution`

#### 16.3.1 Per-innings observation row

Same shape as §16.2.1 but the innings is the OPPONENT's batting.
Side-neutral team filter — pair `(m.team1, m.team2)` includes
`:team`; innings table row is the OTHER side's batting.

| Column | Definition |
|---|---|
| `innings_id` | `innings.id` (the opp's batting innings) |
| `match_id` | `innings.match_id` |
| `innings_number` | 1 or 2 |
| `date` | `match.date` |
| `runs_conceded` | `SUM(d.runs_total)` over the innings (= opp's final score) |
| `balls` | legal balls bowled (= legal balls faced by opp) |
| `wickets` | TEAM-CREDITED wicket count — INCLUDES run-outs (the team caused them by fielding the ball). Excluded kinds: `'retired hurt'`, `'retired out'`, `'retired not out'`, `'obstructing the field'`. ⚠ This DIVERGES from `/teams/{team}/bowling/summary`, which uses the bowler-credited 5-element exclusion (`BOWLER_WICKET_EXCLUDE` — also drops `'run out'`). Both numbers are correct; they answer different questions ("wickets the team took" vs "wickets the team's bowlers took"). The distribution slice intentionally uses the broader team-credited count since it's a per-innings dossier of team performance, not bowler attribution. See `internal_docs/design-decisions.md` "Team-bowling distribution wicket count" for rationale. |
| `runs_at_10` | cumulative opp runs over first 60 legal balls |
| `wickets_at_10` | cumulative wickets (team's bowling-side total, including run-outs) over first 60 legal balls |
| `reached_10_overs` | `1` if opp innings included ≥ 60 legal balls; else `0` |
| `runs_pp` / `balls_pp` / `wickets_pp` | overs 1-6 |
| `runs_mid` / `balls_mid` / `wickets_mid` | overs 7-15 |
| `runs_death` / `balls_death` / `wickets_death` | overs 16-20 |

#### 16.3.2 Three sibling blocks

`wickets`, `runs_conceded`, `economy` — sibling of bowler v1
(§11.4) but at team grain.

**`wickets` block:**

| Field | Formula |
|---|---|
| `total` / `mean_per_innings` / `median` / `variance` / `std` | sample stats over `o.wickets` |
| `observations` | per-innings tuple list |

Milestones (denom = `n_innings_bowled`):

| Field | Reading | Tier color |
|---|---|---|
| `p_leq_3` | "got bashed" | INDIGO |
| `p_geq_5` | "broke the back" | SAGE |
| `p_geq_7` | "in command" | OCHRE |
| `p_eq_10` | "bowled them out" | OCHRE |

Conditional ladder anchored at `≥5`:

| Field | Formula |
|---|---|
| `p_7_given_5`  | `count(w ≥ 7) / count(w ≥ 5)` |
| `p_10_given_5` | `count(w = 10) / count(w ≥ 5)` |

Over-aware (denom = innings with `reached_10_overs = 1`):

| Field | Formula | Reading |
|---|---|---|
| `p_geq_3_at_10`        | `count(wickets_at_10 ≥ 3) / denom`              | "early breakthrough rate" |
| `p_eq_10_given_3_at_10`| `count(wickets=10 AND wickets_at_10≥3) / count(wickets_at_10≥3)` | "finishing rate after early breakthrough" |

**`runs_conceded` block** — mirror of team-batting `runs`, with
polarity flipped color-wise:

| Field | Formula |
|---|---|
| `total` / `mean_per_innings` / `median` / `variance` / `std` | sample stats |
| `escalation_ratio_median` | median of `runs_conceded / runs_at_10` over innings with `reached_10_overs=1 AND runs_at_10 > 0` |

Simples (denom = `n_innings_bowled`):

| Field | Reading | Tier color |
|---|---|---|
| `p_lt_100`  | "shut them down"      | OCHRE |
| `p_lt_150`  | "kept it tight"       | SAGE  |
| `p_geq_150` | "leaked some"         | SAGE  |
| `p_geq_200` | "got hit"             | INDIGO |
| `p_geq_230` | "blown apart"         | INDIGO |

Conditional chain ladder (the leakage chain — same shape as
team-batting's runs ladder, polarity flipped):

| Field | Formula |
|---|---|
| `p_150_given_100` | `count(≥150) / count(≥100)` |
| `p_200_given_150` | `count(≥200) / count(≥150)` |
| `p_230_given_200` | `count(≥230) / count(≥200)` |

Note: chip tooltips note that climbing here is BAD for the
team's bowling (INDIGO tinted across the chain). Wilson CI on
`p_230_given_200` will often render small-n styling; that's
honest.

Over-aware doubling (denom = innings with
`reached_10_overs=1 AND runs_at_10 > 0`):

| Field | Formula | Reading |
|---|---|---|
| `p_double_at_10` | `count(runs_conceded ≥ 2 × runs_at_10) / denom` | "opp doubled on us from halfway" — INDIGO |

**`economy` block** — sibling of bowler v1 (§11.4.3) but at
team grain. Same shape, same milestones (`p_econ_leq_6/7`,
`p_econ_geq_9/10`), tier colors per §11.4.3.

#### 16.3.3 Phase rollup

Same shape as bowler v1 §11.4.5; team-aggregate of bowling-
side runs/balls/wickets per phase.

#### 16.3.4 Form windows + delta

Three deltas per window (one per block focal stat):

```jsonc
"form": {
  "delta": {
    "last_10_wickets_mean_minus_lifetime":            <float>,
    "last_10_runs_conceded_mean_minus_lifetime":      <float>,
    "last_10_economy_pool_minus_lifetime":            <float>,
    /* ... 12 entries total: 4 windows × 3 metrics */
  }
}
```

### 16.4 Team fielding — `/api/v1/teams/{team}/fielding/distribution`

#### 16.4.1 Per-innings observation row

| Column | Definition |
|---|---|
| `innings_id` | `innings.id` (the opp's batting innings; team is fielding) |
| `match_id` | `innings.match_id` |
| `innings_number` | 1 or 2 |
| `date` | `match.date` |
| `catches` | `COUNT(fc WHERE kind='caught' AND COALESCE(is_substitute,0)=0 AND fielder_id ∈ team's matchplayers)` |
| `run_outs` | same shape, `kind='run_out'` |
| `stumpings` | same shape, `kind='stumped'` |
| `wickets_total` | wickets fallen in the innings (any kind) — denominator for fielder-ratio tooltip |
| `substitute_catches` | catches by sub-fielders for this team in this innings (footnote / tooltip stat) |

Master sample is per-innings of opponent batting where one of
the team's matchplayers was field-credited.

#### 16.4.2 Three sibling count blocks

Mirror of player-fielder §13.3 but at team grain. Tab structure
identical: Catches / Run-outs / Stumpings.

**Catches block:**

| Field | Formula |
|---|---|
| `total` / `mean_per_innings` / `median` / `variance` / `std` | sample stats over `o.catches` |
| `observations` | per-innings tuples |

Milestones (denom = `n_innings_fielded`):

| Field | Reading | Tier color |
|---|---|---|
| `p_eq_0`    | "no fielder catches" (rare for teams; usually 1+) | INDIGO |
| `p_geq_3`   | "fielders contributing"                          | SAGE |
| `p_geq_5`   | "catching well"                                  | OCHRE |
| `p_geq_7`   | "fielding masterclass"                           | OCHRE |

No conditional ladder for catches at team grain (the simples
already span the meaningful range; conditioning on `≥3` would
shrink denoms without adding signal).

**Run-outs block** — sparse even at team level:

| Field | Reading | Tier color |
|---|---|---|
| `p_eq_0`  | "no run-outs"                          | INDIGO |
| `p_eq_1`  | "athletic moment"                      | SAGE |
| `p_geq_2` | "sharp fielding match" (rare; ~5-10%)  | OCHRE |

Same three-simple shape as player-fielder §13.3. Sum-to-1
invariant.

**Stumpings block** — depends on whether team had a designated
keeper that match. Per existing keeper-assignment Tier 2:

| Field | Reading | Tier color |
|---|---|---|
| `p_eq_0`  | "no stumpings" | INDIGO |
| `p_eq_1`  | "one stumping" | SAGE |
| `p_geq_2` | "multi-stump"  | OCHRE |

UNLIKE player-fielder §13: the stumpings block is ALWAYS
emitted at team grain (every senior team has had at least one
keeper in their history; pruning the tab is unnecessary). For
emerging teams with `total = 0`, the block ships with all
zeros and Wilson CIs spanning [0, 1] — the chip styling
already handles small-n / zero-event cases.

#### 16.4.3 Top-level scalars

| Field | Formula |
|---|---|
| `n_innings_fielded` | `len(observations)` |
| `wickets_total` | `sum(o.wickets_total)` — denominator for fielder-ratio (tooltip / dismissal mix derivation) |
| `substitute_catches` | `sum(o.substitute_catches)` — footnote scalar |

Per-innings sparkline tooltip enrichment uses
`o.wickets_total` to read "vs MI · 4 catches of 7 wickets" —
the dismissal-ratio framing the user asked about, embedded in
the existing tooltip rather than as a separate widget.

#### 16.4.4 Form windows + delta

Same four windows. Delta block surfaces three means per
window (one per block):

```jsonc
"form": {
  "delta": {
    "last_10_catches_mean_minus_lifetime":   <float>,
    "last_10_run_outs_mean_minus_lifetime":  <float>,
    "last_10_stumpings_mean_minus_lifetime": <float>,
    /* ... 12 entries total: 4 windows × 3 metrics */
  }
}
```

No null-coercion (unlike player-fielder §13 — the team
stumpings block always ships).

### 16.5 Implementation pointers (backend)

- **Three new endpoints** in `api/routers/teams.py`. Slot
  alphabetically next to the existing per-discipline endpoints:
  - `team_batting_distribution` after `team_batting_summary`
    (line ~1664).
  - `team_bowling_distribution` after `team_bowling_summary`
    (line ~2579).
  - `team_fielding_distribution` after `team_fielding_summary`
    (line ~3399).
- **Helpers per discipline**, each colocated with its endpoint
  block:
  - `_innings_master_sample_team_batting(db, team, filters,
    aux)` — per-innings rows where `i.team = team`. Side-aligned
    filter (`build()`, not `build_side_neutral`).
  - `_innings_master_sample_team_bowling(db, team, filters, aux)`
    — per-innings rows of the OPP's batting where match is
    team's. Side-neutral filter (`build_side_neutral()`) PLUS
    explicit `i.team != :team`.
  - `_innings_master_sample_team_fielding(db, team, filters, aux)`
    — same as bowling but counts fielding events from the
    team's matchplayer list rather than wickets.
- **Pure aggregators**, three:
  - `_distribution_dossier_team_batting(observations)` — two
    sibling blocks (`runs`, `run_rate`) + phase rollup.
  - `_distribution_dossier_team_bowling(observations)` — three
    blocks (`wickets`, `runs_conceded`, `economy`) + phase
    rollup.
  - `_distribution_dossier_team_fielding(observations)` — three
    count blocks (`catches`, `run_outs`, `stumpings`) + scalars.
- **Form windows**: one slicer per discipline (mirrors
  bowler/fielder pattern). Uses the scope-anchored cutoff
  `anchor = min(today, max_obs_date)` from §8.6 — for inactive
  teams (Rising Pune Supergiants, Deccan Chargers) the windows
  follow the data, not today.
- **Wilson + suggested_splits**: existing modules (`api/wilson.py`,
  `api/scope_links.py`) — no new code.
- **Filter handling**: `FilterParams.filter_team` IGNORED on
  these endpoints (the team-path-param dominates). Document in
  each endpoint docstring.

### 16.6 Tests

**Sanity** — three new files mirroring the bowler/fielder
pattern:

- `tests/sanity/test_team_batting_distribution_invariants.py`
- `tests/sanity/test_team_bowling_distribution_invariants.py`
- `tests/sanity/test_team_fielding_distribution_invariants.py`

Each ~80-150 SQL-anchored assertions across 4-5 scopes:
- Marquee teams (Mumbai Indians / Chennai Super Kings / India men).
- An emerging team with sparse data.
- Empty scope (filter_venue = nonexistent).

Per-discipline invariants:

**Batting:**
- `n_innings == len(observations)` lifetime + every form window.
- `runs.total == sum(o.runs)`.
- `runs.mean_per_innings × n_innings ≈ runs.total`.
- For every milestone: `value × denom ≈ num`; CI bounds; chain
  ladder denom invariant: `p_150_given_100.denom == count(≥100)`,
  etc.
- `p_double_at_10.denom == count(reached_10_overs=1 AND runs_at_10 > 0)`.
- `escalation_ratio_median × runs_at_10` distribution matches the
  observation-derived ratio set.
- `run_rate.pool == runs.total × 6 / sum_balls` exact.
- Phase partition invariant.

**Bowling:**
- Mirror of batting + the bowler-specific bowled vs run-out
  attribution invariants.
- `wickets.total ≤ 10 × n_innings_bowled` (T20 ceiling).
- `p_geq_3_at_10` / `p_eq_10_given_3_at_10` numerator/denominator
  cross-check vs observation list.
- Subset invariant: `count(w ≥ k) ≤ count(w ≥ k−1)` for k = 1..10.

**Fielding:**
- Three-simples-sum-to-1 per block (catches sums to 1 across
  `p_eq_0 + p_geq_3 + ...`? No — these aren't a partition;
  catches simples are P(=0), P(≥3), P(≥5), P(≥7); they don't
  exhaust the space. ONLY the run_outs / stumpings blocks
  partition exhaustively at 0/1/≥2). Catches: subset
  monotonicity instead.
- Substitute reconciliation: `catches.total + substitute_catches`
  equals the existing `/teams/{team}/fielding/summary.catches`
  for the same scope.
- Wickets-total cross-check: `wickets_total ≥ catches + run_outs
  + stumpings + bowled-only` (catches ≤ wickets-fallen always).

**Regression** — three URL inventories:

- `tests/regression/team_batting_distribution/urls.txt`
- `tests/regression/team_bowling_distribution/urls.txt`
- `tests/regression/team_fielding_distribution/urls.txt`

~15 URLs each: 4 marquee teams × scopes (all-time, IPL, IPL by
season, vs-team, at-venue, season-only, empty scope). Same
`as_of_date=2025-01-01` pin.

**No agent-browser integration test in v1 backend** — API-only
slice. Integration arrives with the frontend (§17.6).

### 16.7 Implementation order — eight atomic backend commits

1. `team-batting: /teams/{team}/batting/distribution endpoint` —
   master sample + dossier + form-windows + route.
2. `sanity: team batting distribution invariants` — ~120
   assertions per §16.6.
3. `regression: team_batting_distribution urls.txt` — 15-URL
   inventory.
4. `team-bowling: /teams/{team}/bowling/distribution endpoint`.
5. `sanity: team bowling distribution invariants`.
6. `regression: team_bowling_distribution urls.txt`.
7. `team-fielding: /teams/{team}/fielding/distribution endpoint`.
8. `sanity: team fielding distribution invariants` +
   `regression: team_fielding_distribution urls.txt` (these
   two land together since the fielding endpoint reuses most
   of the count-block aggregator from §13).

After each regression run reports `0 REG drifted, N NEW
changed, 0 NEW unchanged`, flip `NEW → REG` in a separate
follow-up commit per regression-harness discipline (CLAUDE.md).

---

## 17. Team v1 frontend — Distribution panels on `/teams` (DRAFT)

> Sibling of §9 (batter), §12 (bowler), §14 (fielder). Three
> Distribution panels, one mounted at the TOP of each existing
> discipline tab content area on `frontend/src/pages/Teams.tsx`:
> Batting tab → `TeamBattingDistributionPanel`, Bowling tab →
> `TeamBowlingDistributionPanel`, Fielding tab →
> `TeamFieldingDistributionPanel`. Each panel fetches only its
> own discipline's endpoint (§16); the panel-per-tab placement
> matches the existing pattern (every team analytic — by-season,
> by-phase, top-batters, etc. — already lives inside its
> discipline's tab).
>
> Reuses every §10.3 frontend convention — INDIGO/SAGE/OCHRE
> 3-tier palette, Wilson CI tooltips on `ProbChip`, oxblood form
> deltas with self-anchoring scope-baseline row (per
> `feedback_form_color_oxblood` + `feedback_delta_lines_self_anchor`),
> uniform stat-strip schema with Mean ↔ Std together (per
> `feedback_std_needs_mean`), `DistributionSparkline` with
> per-innings/per-match bars and match-link mouseover.

### 17.1 Layout

The three panels mount independently at the top of their
respective Teams-page tab content areas:

```
┌────────────────────────────────────────────────────────┐
│ Teams page header (ScopedPageHeader)                   │
│ Stat row (Matches / Wins / Toss / etc.)                │
│ ────────────────────────────────────────────────────── │
│ Tabs: [Batting] [Bowling] [Fielding] [Partnerships]... │
│ ────────────────────────────────────────────────────── │
│                                                        │
│   <Active tab content>                                 │
│                                                        │
│   ┌──────────────────────────────────────────────┐     │
│   │ TeamXxxDistributionPanel (this slice)        │     │
│   │ — window toggle + metric tabs                │     │
│   │ — histogram + stat strip + chips             │     │
│   │ — sparkline + season-tick axis               │     │
│   │ — form-delta line (baseline + deltas)        │     │
│   │ — suggested-splits row                       │     │
│   └──────────────────────────────────────────────┘     │
│                                                        │
│   <Existing analytics — by-season, by-phase, top-N>    │
│                                                        │
└────────────────────────────────────────────────────────┘
```

The panel sits ABOVE the existing per-discipline analytics
inside the tab. Switching the top-level tab swaps the panel
along with the rest of the tab content (each panel is mounted
inside its tab's render branch).

### 17.2 Common conventions

**URL state — page-suffix `_t` to prevent cross-page bleed.**
The team page now shares the same panel pattern as
`/batting?player=`, `/bowling?player=`, `/fielding?player=`.
URL state keys are suffixed `_t` (team) so navigating between
player pages and team pages doesn't carry incompatible
metric/window states:

- `?dist_window_t=scope|last_10|last_60d|last_6mo|last_1yr`
- `?dist_metric_t_bat=runs|run_rate` (batting tab)
- `?dist_metric_t_bowl=wickets|runs_conceded|economy` (bowling tab)
- `?dist_metric_t_field=catches|run_outs|stumpings` (fielding tab)

Defaults are encoded by ABSENCE of the param. Only one
`dist_window_t` because a single window applies across all
three discipline tabs (the user's "form arc" is the same
question regardless of discipline).

**Palette & polarity:**

| Discipline / metric | INDIGO (poor) | SAGE (typical) | OCHRE (good) |
|---|---|---|---|
| Batting · Runs | <100 | 100-200 | ≥200 |
| Batting · Run Rate | ≤7 (slow) | 7-9 | ≥9 (explosive) |
| Bowling · Wickets | ≤3 | 4-6 | ≥7 |
| Bowling · Runs Conceded | ≥200 | 100-200 | <100 (FLIP — low is good) |
| Bowling · Economy | ≥9 (loose) | 7-9 | ≤7 (tight) |
| Fielding · Catches | 0 | 1-4 | ≥5 |
| Fielding · Run-outs | 0 | 1 | ≥2 |
| Fielding · Stumpings | 0 | 1 | ≥2 |

**Reference lines on every sparkline:**

- **Black solid 2px** — scope baseline (this team's lifetime
  mean in the active filter scope).
- **Gray 1.5px** — gender-global team baseline (whole-number
  rounded; e.g. men's IPL team innings ≈ 167 runs, women's
  ≈ 130). New constants in
  `frontend/src/components/distribution/globalBaselines.ts`
  (extend the existing per-bowler constants with team-level
  entries).
- **Oxblood 1.2px rolling-N mean overlay** — Lifetime/Scope
  window only, when `n_innings ≥ 10`. Same convention as
  bowler/batter.

**Sparkline mouseover linking to matches.** Each bar carries
the match link (`<a href="/matches/{match_id}">`) per existing
`DistributionSparkline` convention. Tooltip text is per-tab
(see each panel section below).

### 17.3 Team Batting panel (`TeamBattingDistributionPanel`)

Mounted at the top of the Batting tab in `Teams.tsx`. Two
metric tabs: **Runs** (default) and **Run Rate**.

**Runs tab anatomy:**

```
┌──────────────────────────────────────────────────────────────────┐
│ Per-innings team batting distribution  [Scope|10|60d|6mo|1y]     │
│ [ Runs ] [ Run Rate ]                                            │
│                                                                  │
│ ┌─────────────────────────────────┬──────────────────────────┐   │
│ │  (active-tab histogram)         │ Innings        178       │   │
│ │  Width-10 bars, 0..250+ floor   │ Mean / innings 162.4     │   │
│ │  INDIGO <100 / SAGE 100-199 /   │ Median         158       │   │
│ │  OCHRE ≥200                     │ Std             34.1     │   │
│ │                                 │                          │   │
│ │                                 │ Milestone chips:         │   │
│ │                                 │ P(<100) 12% · P(≥100) 88%│   │
│ │                                 │ P(≥150) 64% · P(≥200) 21%│   │
│ │                                 │ P(≥230)  6%              │   │
│ │                                 │ ── conversion (chain) ──│   │
│ │                                 │ P(≥150│≥100) 73%         │   │
│ │                                 │ P(≥200│≥150) 33%         │   │
│ │                                 │ P(≥230│≥200) 29%         │   │
│ │                                 │ ── doubling at 10 ──    │   │
│ │                                 │ P(≥2× final│x at 10) 31% │   │
│ │                                 │  median ratio  1.85×     │   │
│ └─────────────────────────────────┴──────────────────────────┘   │
│                                                                  │
│ ▁▃▂▅▁▇▂▁▃▆▅▁▂▆▇▅▁  ← per-innings sparkline (height = team runs) │
│ ──────  scope baseline 162.4   gender-global 156   rolling-10  │
│                                                                  │
│ Scope baseline / innings · runs 162.4 · RR 8.05                  │
│ Form (Δ vs baseline): last 10 runs +4.1 RR +0.20 · last 60d ...  │
│                                                                  │
│ Compare to:  All IPL  ·  All cricket 2024  ·  All-time           │
└──────────────────────────────────────────────────────────────────┘
```

**Histogram primitive — reuse `RunsHistogram.tsx`** from
`frontend/src/components/batting/`. The width-10 bins primitive
is identical for team-batting; the per-bar tier coloring
follows the team-batting palette above (INDIGO <100, SAGE
100-199, OCHRE ≥200). The `categoryAccessor`/`valueAccessor`/
`colorBy` props on `BarChart` already accept arbitrary
configurations; just pass team-tier-binning helpers from a new
`distributionBins.ts` colocated in
`frontend/src/components/teams-distribution/`.

**Run Rate tab** — discrete-ish bars at width-1 RPO from 4 to
13+. Reuse `EconomyHistogram.tsx` from
`frontend/src/components/bowling/` with the FLIPPED polarity
(`COLOR_SCHEME` reversed: ≤6 INDIGO, 7-9 SAGE, ≥9 OCHRE).
Stat strip: `Pool RR`, `Mean / innings`, `Median / innings`,
`Std`. Chips: `P(RR ≤7)`, `P(RR ≤8)`, `P(RR ≥9)`, `P(RR ≥10)`.

**Sparkline** — per-innings bars in chronological order, height
= team runs (for Runs tab) or team RR (for Run Rate tab). Bar
opacity 0.8 default, INDIGO override to 1.0 (matches existing
convention so under-100 bars stay visible at the small height).
Bar tooltip per tab:
- Runs: `"YYYY-MM-DD · 178/4 (20 ov, RR 8.9) — vs MI"` (rich;
  uses `o.wickets`, `o.balls`, opponent from match metadata).
- Run Rate: same content but lead with the RR value.

**Reference lines:** scope-baseline = `runs.mean_per_innings`
(black 2px); gender-global = `globalBaselines.team_innings_runs`
(gray 1.5px, whole-number per user spec); rolling-10 mean
oxblood overlay on Lifetime only.

### 17.4 Team Bowling panel (`TeamBowlingDistributionPanel`)

Mounted at the top of the Bowling tab. Three metric tabs:
**Wickets** (default), **Runs Conceded**, **Economy**.

**Wickets tab** — discrete bars at integer wicket counts 0..10
(team can take all 10). Reuse `WicketsHistogram.tsx` primitive
from bowling/, but extend the bin floor to 10 (player bowler
defaulted to 5+ catch-all; team bowler shows full 0..10 range).

Stat strip: `Innings bowled`, `Wickets total`, `Mean wickets`,
`Median`, `Std`, `Pool SR (balls/wkt)`.

Chips:
- Simples (denom = `n_innings_bowled`): `P(≤3)`, `P(≥5)`,
  `P(≥7)`, `P(=10)`.
- Conditionals (anchor `≥5`): `P(≥7│≥5)`, `P(=10│≥5)`.
- Over-aware: `P(≥3 at 10)`, `P(=10│≥3 at 10)` ("early
  breakthrough" + "finishing rate").

**Runs Conceded tab** — same width-10 histogram primitive as
team-batting Runs but FLIPPED polarity (low conceded = OCHRE,
high = INDIGO). Stat strip mirrors batting's Runs strip.

Chips:
- Simples: `P(<100)`, `P(<150)`, `P(≥150)`, `P(≥200)`,
  `P(≥230)` — flipped tints (`<` = OCHRE, `≥` = INDIGO).
- Conditional chain: `P(≥150│≥100)`, `P(≥200│≥150)`,
  `P(≥230│≥200)` — INDIGO across (climbing here is bad).
- Over-aware: `P(opp ≥2× final│x at 10)` + `median ratio` —
  the leakage version of doubling. INDIGO.

**Economy tab** — same as bowler v1 §12.2.3, just at team
grain. Reuse `EconomyHistogram.tsx` directly; chip thresholds
identical (`p_econ_leq_6/7`, `p_econ_geq_9/10`).

**Sparkline** — per-innings bars; height = wickets-taken (for
Wickets tab) / runs-conceded (for Runs Conceded tab) / RPO
(for Economy tab). Tooltip per tab:
- Wickets: `"YYYY-MM-DD · 7/120 (oppo all out 16.4 ov) — vs RCB"`
  (carries dismissal-mix subtotal in tooltip as deferred-v2
  tease: `"  (5 caught · 1 bowled · 1 LBW)"`. Hidden behind a
  `dismissal-mix` data attribute initially; surface in v2 when
  the donut sibling lands).
- Runs Conceded: leads with conceded total + opp's wickets-lost.
- Economy: leads with RPO + (runs/balls) detail.

### 17.5 Team Fielding panel (`TeamFieldingDistributionPanel`)

Mounted at the top of the Fielding tab. Three metric tabs:
**Catches** (default), **Run-outs**, **Stumpings**.

Mirrors player-fielder §14 anatomy with two team-grain
adjustments:

1. **Histogram bins** — Catches uses bars 0..7 (continuous-ish
   discrete; team typically catches 3-5 per match). Run-outs
   and Stumpings keep the player-fielder 3-bar `0/1/≥2` shape
   (still rare at team grain).
2. **Stumpings tab is ALWAYS rendered** (every senior team
   has had a keeper at some point). For zero-stumping windows
   the tab still mounts; chips show 0% with [0, 0] CIs and
   small-n styling — honest, not hidden.

**Stat strip** — uniform schema across all three tabs (per
`feedback_std_needs_mean`): `Innings fielded`, `Total {metric}`,
`Mean / innings`, `Median`, `Std`. Plus on Catches tab only:
`+ N substitute catches (excluded)` footnote when
`substitute_catches > 0`.

**Chips per tab:**

| Tab | Chips |
|---|---|
| Catches  | `P(=0)` INDIGO · `P(≥3)` SAGE · `P(≥5)` OCHRE · `P(≥7)` OCHRE |
| Run-outs | `P(=0)` INDIGO · `P(=1)` SAGE · `P(≥2)` OCHRE |
| Stumpings| `P(=0)` INDIGO · `P(=1)` SAGE · `P(≥2)` OCHRE |

**Sparkline tooltip — fielder-ratio enrichment.** Per-bar
tooltip on the Catches tab shows the dismissal-ratio context
the user asked about, embedded in the existing tooltip rather
than as a separate widget:

`"YYYY-MM-DD · 4 catches of 7 wickets — vs RCB"`

Reads from the per-innings observation's `wickets_total` and
`catches`. The "X of Y" framing answers the dismissal-mix
question without crowding the visual. Run-outs and Stumpings
tooltips stay simpler (`"YYYY-MM-DD · 1 run-out — vs RCB"`).

**Reference line at y=1** for Catches and Run-outs tabs (same
as player-fielder); mean overlay for Stumpings (keepers-mean
informative at team grain since teams with established keepers
hit ~0.3 stumpings/match).

### 17.6 Components inventory

New directory: `frontend/src/components/teams-distribution/`.

| Component | File | Reuse from |
|---|---|---|
| `TeamBattingDistributionPanel` | `teams-distribution/TeamBattingDistributionPanel.tsx` | new top-level container |
| `TeamBowlingDistributionPanel` | `teams-distribution/TeamBowlingDistributionPanel.tsx` | new top-level container |
| `TeamFieldingDistributionPanel`| `teams-distribution/TeamFieldingDistributionPanel.tsx` | new top-level container |
| Stat strips + chips rows       | inline in each panel; conditional schema per tab | new |
| `RunsHistogram` (width-10)     | already shipped at `batting/RunsHistogram.tsx` | direct reuse via prop config |
| `WicketsHistogram` (discrete 0..10) | already shipped at `bowling/WicketsHistogram.tsx`; extend bin-floor to 10 | extend |
| `EconomyHistogram` (width-1 RPO) | already shipped at `bowling/EconomyHistogram.tsx` | direct reuse |
| `CountHistogram` (3 bars 0/1/≥2) | already shipped at `fielding/CountHistogram.tsx` | direct reuse for run_outs/stumpings; new variant for team-catches (0..7 bars) |
| `DistributionSparkline`        | already shipped at `distribution/DistributionSparkline.tsx` | direct reuse |
| `SeasonTickAxis`               | already shipped at `distribution/SeasonTickAxis.tsx` | direct reuse |
| `ProbChip`                     | already shipped at `distribution/ProbChip.tsx` | direct reuse |
| `WindowToggle`                 | already shipped (inline buttons in §9.2.1) | direct reuse via copy |
| `globalBaselines.ts`           | already shipped at `distribution/globalBaselines.ts`; ADD `pickTeamBattingBaseline`, `pickTeamBowlingBaseline`, `pickTeamFieldingBaseline` | extend |
| Form-delta line + suggested-splits row | per-discipline new components (sibling of `FielderFormDeltaLine`) | new but small |

**`distributionBins.ts` colocated in
`teams-distribution/`** — pure helpers for tier mapping at
team-batting (`teamRunsBin`, `teamRunsTier`, etc.).

### 17.7 Tests

**Integration** — three SQL-anchored shell scripts:

- `tests/integration/team_batting_distribution.sh`
- `tests/integration/team_bowling_distribution.sh`
- `tests/integration/team_fielding_distribution.sh`

Each ~25 assertions. Common pattern:

1. Panel section exists (per `aria-label`).
2. Stat-strip headline numbers match SQL anchors (innings count,
   total runs/wickets/catches).
3. Histogram bar count matches the expected bin count
   (width-10: variable; team-wickets: 11; fielding-catches: 8;
   fielding-run-outs/stumpings: 3).
4. **Sparkline bar count == n_innings** from SQL — codified
   per-item-chart rule (CLAUDE.md "Sparkline / per-item chart
   bar count must match SQL"). No height=0 bars hidden.
5. Chip percentages match SQL-derived `count(condition) /
   denom × 100`. Test all simples + 1-2 conditionals + 1
   over-aware probability per tab.
6. Chip tier-color coordination (INDIGO/SAGE/OCHRE matches the
   threshold band).
7. Window toggle URL state: `?dist_window_t=last_10` reproduces
   from share-link.
8. Metric tab URL state per discipline: `?dist_metric_t_bat=run_rate`
   etc.
9. Mobile viewport (390×844) — panel renders without overflow.
10. **Doubling probability cross-check** — the chip's
    `value × denom = num` invariant on the over-aware
    probability, computed via direct SQL on the master sample.
11. Match-link on sparkline bar — first bar's `<a href>`
    contains `/matches/<id>` matching the SQL-derived
    chronologically-first match.

**Sanity** — three new files (§16.6).

**Regression** — three new URL inventories (§16.6).

### 17.8 Implementation order — twelve atomic frontend commits

Per discipline (4 commits each × 3 disciplines = 12):

1. `team-batting-frontend: types + api fetcher` — 
   `TeamBattingDistribution` types + `getTeamBattingDistribution()`
   in `api.ts`. `tsc -b` clean.
2. `team-batting-frontend: TeamBattingDistributionPanel` —
   primitive composition: panel container + window toggle +
   metric tabs + stat strip + chips + sparkline + form-delta
   line + suggested-splits row. Reuse `RunsHistogram` and
   `EconomyHistogram` via prop config.
3. `team-batting-frontend: panel mounted on Teams.tsx Batting
   tab` — paste at top of the tab content.
4. `tests: team_batting_distribution integration` — SQL-anchored
   per §17.7.

Repeat for bowling (commits 5-8) and fielding (commits 9-12).

After each integration test passes, run `agent-browser` against
`/teams?team=Mumbai%20Indians&tab=Batting` (etc.) at both
desktop (1280×800) and mobile (390×844) viewports per the
verification rule.

`globalBaselines.ts` extension lands in commit 1 (or a
preceding standalone commit if the team baselines need a
populate-script first; check `bucket_baseline_dispatch.py` for
the existing per-team computation pipeline).

---

*Started 2026-05-04. Inventory + framing drafted first.
2026-05-05: batter v1 backend (§8) + frontend (§9) IMPLEMENTED
across 10 atomic commits.
2026-05-05 → 06: v2/v3/v4 follow-ups — extra form windows
(6mo + 1y), conditional milestones (P≥50│≥30, P≥70│≥50),
"Scope" rename, single-flex-row probabilities, suggested-splits
4-tier ladder fix (was buggy on team_type and season ranges),
sparkline solid 20-run line + 1.5px legend swatches,
ScopedPageHeader rolled to all 8 scoped pages, mobile media-query
fix.
Patterns codified in §10 for sibling slices.
2026-05-06: bowler v1 spec drafted (§11 backend + §12 frontend +
§15 Wilson-CI batter retrofit, originally numbered §13).
Pending implementation.
2026-05-07: fielder v1 spec drafted AND implemented end-to-end
(§13 backend + §14 frontend). Three sibling count blocks
(catches / run-outs / stumpings*), per-match unit, three-simples
histogram (P=0/P=1/P≥2) in the 3-tier palette, conditional
stumpings tab via `innings_kept > 0`, mean-per-match in stat strip
only on stumpings tab, sparkline reference line at y=1 except
stumpings (mean overlay). Sanity (1510 assertions across 4 fielder
+ empty scopes), regression (15-URL inventory locked at REG),
integration (27 assertions including SQL-anchored chip values,
keeper/non-keeper tab visibility, mobile viewport). Renumbered
existing Wilson-CI retrofit §13 → §15.
2026-05-07 (later): team v1 spec drafted (§16 backend + §17
frontend). Three sibling endpoints — batting / bowling / fielding
distribution — one panel mounted inside each existing Teams-page
tab. Wider milestone ladder (100/150/200/230 anchors at 50-run
gaps), over-aware probabilities (`P(≥2x | x at 10)` doubling for
batting + bowling-conceded, `P(=10 | ≥3 at 10)` finishing for
bowling-wickets), oxblood form deltas with self-anchoring
baseline row, INDIGO/SAGE/OCHRE 3-tier palette throughout. Per-
innings observation row gains `runs_at_10` + `wickets_at_10`.
2026-05-08: team v1 BACKEND IMPLEMENTED (§16). Nine commits —
3 per discipline (endpoint + sanity + regression). Three new
endpoints registered at /api/v1/teams/{team}/{batting|bowling|
fielding}/distribution. 8936 SQL-anchored sanity assertions
total (2456 batting + 4165 bowling + 2315 fielding) across 5
scopes per discipline plus an empty-scope edge case. 48
regression URLs (16 per discipline) locked at REG with
as_of_date=2025-01-01. Spec §16.3.1 wicket-exclusion clause
clarified: team-bowling/distribution uses team-credited wickets
(includes run-outs; 4-kind exclusion list); team-bowling/summary
remains bowler-credited (BOWLER_WICKET_EXCLUDE — 5-kind list).
The earlier draft text claimed the distribution slice "mirrored
team-bowling/summary" — incorrect; the divergence is intentional
and codified in design-decisions.md.
Frontend (§17) pending — twelve atomic commits across three
panels per §17.8.*
