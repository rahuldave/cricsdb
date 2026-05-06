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
| `form.last_60d` | `WHERE date >= today() − 60 days` | calendar-anchored current form |
| `form.last_6mo` | `WHERE date >= today() − 180 days` | medium-term arc |
| `form.last_1yr` | `WHERE date >= today() − 365 days` | annual / loss-of-form gauge |

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
- **Tier-coloured sparkline bars** (revised 2026-05-06): each
  per-innings/per-spell bar is colored by its milestone tier
  matching the histogram bins. Lets users scan the chronological
  sparkline and answer "in how many great innings was he poor?"
  / "of his good spells, how many were 5-fers?" at a glance.
  - Batter Runs tab: `WISDEN_RUN_TIERS` (failure indigo / building
    slate-tan / fifty sage / century ochre / rare deeper gold).
  - Batter SR tab: continuous, no tiering (single neutral color).
  - Bowler Wickets tab: `WISDEN_WICKET_TIERS` (wicketless slate-
    tan / building indigo / threefer sage / fourfer ochre /
    fivefer deeper gold).
  - Bowler Economy + Runs Conceded tabs: `WISDEN_LOWER_IS_BETTER_TIERS`
    — same five colors as the wicket ladder but reversed polarity
    (sage at the LOW end = good; ochre/gold at the HIGH end = bad).
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

Reuse the §8.6 mechanism verbatim. Same four windows:

| Window | Definition |
|---|---|
| `form.last_10` | `ORDER BY date DESC, innings_number DESC LIMIT 10` |
| `form.last_60d` | `WHERE date >= today() − 60 days` |
| `form.last_6mo` | `WHERE date >= today() − 180 days` |
| `form.last_1yr` | `WHERE date >= today() − 365 days` |

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

## 13. Wilson-CI retrofit on batter conditionals (DRAFT)

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
§13 Wilson-CI batter retrofit). Pending implementation.
Fielder / team distribution dossiers remain to be done.*
