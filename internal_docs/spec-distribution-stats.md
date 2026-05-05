# Spec — Distribution-shaped statistics on the API

> **Status:** DRAFT — inventory phase. Captures the conceptual surface
> we want to expose (per-discipline distributions, recurring shapes,
> form windows) so we can iterate on the API design. Wire format,
> sampling-unit pinning per stat, and sample-size floors are open
> questions; see §6.

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

Out of scope here (deferred to a follow-up spec): wire format,
endpoint shape, sample-size floors per metric, histogram
bucketing strategy, and any frontend work.

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
| Strike rate (concatenated) | innings → balls-faced-weighted SR | Per-innings SR weighted by balls. Reveals tempo bimodality (anchor vs aggressor) hidden by the pool. |
| Average (runs / dismissals) | innings → (runs, dismissed?) | Two coupled distributions: runs-per-innings + Bernoulli(dismissed). Average is a ratio of expectations; conflates "didn't bat long" with "got out for 5". |
| Boundary % | innings → boundaries / balls | Per-innings boundary-fraction distribution, balls-weighted. Maps directly to risk profile. |
| Dot % | innings → dots / balls | Same shape, opposite signal (low-risk anchoring). |
| Highest score | max order statistic over innings runs | The per-innings runs distribution already implies this — quantiles (P95, P99) are richer than max alone. |
| 50s, 100s | thresholded counts on innings runs | CDF readouts of the same distribution: `P(runs ≥ 50) × innings_count`. Free if the distribution is exposed. |
| Fours, Sixes | innings → boundaries thrown | Counts; per-innings distribution ≈ Poisson-ish; useful for "explosive innings" classification. |
| Not outs | innings → 1[notout] | Bernoulli per innings; coupled with runs (notouts cluster at innings end → small runs). |

**Natural primary unit: the innings.** Almost every batting summary
is a transform of `(runs_batter, balls_faced, dismissed_flag, fours,
sixes, dots)` per innings.

### 3.2 Bowling (per bowler)

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Total wickets | innings → wickets taken | Per-innings wickets distribution: usually 0–1, fat zero-inflation, long right tail. Shows whether wickets cluster (5-fers) or spread evenly. |
| Economy | innings → runs / legal-balls × 6 | Per-innings economy distribution, balls-weighted. Distinguishes "always 7" from "5/5/5/15". |
| Average | innings → (runs conceded, wickets) | Coupled like batting average. **Hard case**: many innings have wickets=0 — average-per-innings is undefined or inf. Distribution-of-runs-per-innings + distribution-of-wickets-per-innings is cleaner than ratio-per-innings. |
| Strike rate (balls/wkt) | wicket event → balls bowled until next wicket | **Survival distribution**: time-to-event with right-censoring (innings ends before next wicket). Mean vs Kaplan–Meier matters here. |
| Best figures (e.g. 5/20) | innings | Order statistic; quantiles of (wkts, runs) per innings give richer view. |
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
| Highest team total / Lowest all-out | max/min order statistics over innings totals | Distribution of innings totals, and the all-out subset, encodes both. P5 / P95 more informative than min/max. |
| Phase RR / phase economy | innings × phase → balls-weighted RR/econ | Per-innings-per-phase distributions; six new distributions per team (3 phases × bat/bowl). |
| Fielding aggregates | match → events | Same as per-fielder fielding, rolled to team. |
| Partnership counts (50+, 100+) | partnership → runs | CDF readouts of partnership-runs distribution. |
| Best pair / highest partnership | order statistic over partnerships | Order-stat on the partnership distribution. |

A team distribution payload would expose all four grains (match,
innings, partnership, fielding-event-per-match) with pointers to
which sample produced each.

### 3.5 Partnerships

| Current stat | Unit | What the distribution adds |
|---|---|---|
| Partnership runs | partnership → runs | Per-partnership runs distribution. Heavily right-skewed. |
| Avg partnership per wicket position | partnership × wicket_number → runs | Already a split — distributional view = histogram per wicket position (1–10). The shape is what makes "openers vs lower order" comparable. |
| Best partnership | order statistic | Quantiles of the per-wicket distribution. |
| 50+ / 100+ counts | thresholded counts | CDF readouts. |

---

## 4. Six recurring distribution shapes

Six shapes show up across all disciplines. Naming them up front lets
the API expose a uniform descriptor; per-stat metadata then says
"this stat is shape N, here is its sample."

1. **Per-innings continuous, balls-weighted.** Batter SR, batter
   boundary %, RR, economy, dot %. Mean ≠ pool when innings vary in
   balls; honest summary is balls-weighted mean + quantiles.
2. **Per-innings count, zero-inflated.** Wickets/innings,
   catches/match, fours/innings. Mean is misleading; want median,
   P75, P90, fraction-of-innings ≥ 1.
3. **Per-innings runs (skewed continuous).** Batter runs, team
   innings totals, partnership runs. Right-skewed, long tail;
   quantile-friendly.
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

These are the design calls before this spec becomes build-ready.
Each is worth its own conversation.

1. **Sampling-unit pinning per stat.** Bowling SR's survival shape
   (§4 shape 5) is non-trivial — do we expose K–M curves, or
   simplify to "per-innings balls/wkt where wkt > 0" with the
   censored sample dropped?
2. **Histogram primitive.** Fixed-bucket vs adaptive bucketing vs
   raw observations. Direct cost / payload-size implications.
   Probably fixed-bucket per shape, with shape-specific defaults.
3. **Quantile vector.** A common quantile set (P5, P25, P50, P75,
   P95) for all continuous shapes, or shape-specific?
4. **Sample-size floor.** Below what *n* do we suppress the
   distribution and return only the pool? Different by shape (10
   innings might be enough for batting; 30 matches for fielding
   counts).
5. **Form windows.** Three candidates, each cheap if per-innings /
   per-match data is exposed:
   - **Last N innings/matches** (e.g. last 10): no calendar
     dependence, fair across active vs sparse-touring players.
     Cricket convention.
   - **Last K days** (e.g. 90 days): "current form" reading.
     Sensitive to inactivity.
   - **Current season / current tournament**: snaps to the
     FilterBar's existing scope tools. Distribution view inherits
     the filter — no new endpoint contract.

   Recommendation: expose all three as windowing options on the
   same distribution endpoint, with the window stamp returned in
   the response so the client can label correctly.
6. **Bucket-baseline implications.** The denormalised
   `bucketbaseline_*` tables (see `perf-bucket-baselines.md`) hold
   per-cell pool aggregates today. A distribution payload needs
   either (a) live aggregation always, or (b) precomputed
   per-innings sketches. Not yet decided.
7. **Cross-cutting Compare-tab integration.** Compare slots
   currently surface a single number per cell with a chip envelope.
   Distribution-aware Compare is a UI question — small inline
   spark-histogram per cell, or a separate "distribution view"
   tab? Out of scope here; flagged.

---

## 7. Where to drill in next

Three paths that all build on this inventory:

1. **Pick one discipline (batter feels richest) and design the
   actual response payload** — quantile vector + balls-weighted
   moments + identity sidecar + window stamp. Strawman API shape.
2. **Decide the per-stat sampling unit explicitly.** For the
   Bowling SR survival case, the math is non-trivial; pin that
   before designing the wire format.
3. **Talk about the histogram primitive.** Fixed-bucket vs
   adaptive vs raw observations. Has direct cost implications
   and surfaces sample-size policy.

---

*Started 2026-05-04 from a remote-control session asking for
distribution-shaped richer statistics. Inventory captured before
any implementation — wire format and DB-side decisions in a
follow-up.*
