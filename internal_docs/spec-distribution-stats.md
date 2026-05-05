# Spec — Distribution-shaped statistics on the API

> **Status:** Inventory + cross-discipline framing remain DRAFT.
> §8 (batter v1 backend distribution dossier) is **IMPLEMENTED** —
> shipped 2026-05-05 across 5 commits. Endpoint live at
> `GET /api/v1/batters/{id}/distribution`. 126/126 sanity
> invariants pass; 19/19 regression URLs return 200; 11/11
> scope-splits lockstep fixtures pass.
> §9 (batter v1 frontend — Distribution panel on `/batting`) is
> **build-ready** — layout, panel anatomy, types, fetcher, components,
> empty-state handling, integration test plan, and 5-commit ordering
> all pinned. Awaiting implementation.
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

CDF readouts of the runs distribution, normalised by `n_innings`:

| Field | Formula | Reading |
|---|---|---|
| `milestones.p_failure_10` | `count(o.runs ≤ 10) / n_innings` | "got out cheap" |
| `milestones.p_25_plus` | `count(o.runs ≥ 25) / n_innings` | "got going" |
| `milestones.p_50_plus` | `count(o.runs ≥ 50) / n_innings` | "match-shaping" |
| `milestones.p_100_plus` | `count(o.runs ≥ 100) / n_innings` | "match-winning" |

Thresholds pinned at 10 / 25 / 50 / 100 for v1. **Not** a
configurable axis — keeps API surface small and makes cross-player
comparison clean. 50s and 100s as raw counts go away — `p_50_plus
× n_innings` and `p_100_plus × n_innings` recover the count.

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

Two windows, **same dossier shape as lifetime** — the entire `runs`,
`milestones`, and `phase` blocks recompute on the windowed sample:

| Window | Definition |
|---|---|
| `form.last_10` | `ORDER BY date DESC, innings_number DESC LIMIT 10` over the active filter |
| `form.last_60d` | `WHERE date >= today() − 60 days` over the active filter; no `LIMIT` — sample size varies |

Plus a `form.delta` block — one-glance reads:

```jsonc
"form": {
  "delta": {
    "last_10_mean_minus_lifetime":   <float>,
    "last_10_median_minus_lifetime": <float>,
    "last_60d_mean_minus_lifetime":   <float>,
    "last_60d_median_minus_lifetime": <float>
  }
}
```

Sparkline data is implicit — frontend reads
`lifetime.runs.observations[]` (date-asc), takes the tail, overlays
rolling-N mean. No separate endpoint.

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

> **Status:** build-ready. Consumes the §8 endpoint
> `GET /api/v1/batters/{id}/distribution`. Lands a new
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

**Render rule** — show bins from `[0,9]` through the bin containing
`max(window.observations.runs)`, inclusive. The `200+` terminal
bin only renders if a 200+ score exists in scope (not yet, but the
bin is defined for forward-compatibility).

The "always render through the max" rule means **interior empty
bins still draw** (preserves the distribution shape — a player
with 5 innings 0-9, 0 innings 10-19, 8 innings 20-29 still sees
the gap at 10-19), while the **empty upper tail vanishes** (a
batter with max 30 sees four bars, not 22). Per-player chart
width auto-fits the data.

For most batters this resolves to ~6–14 bars; tail batters 3–4;
century-rich batters 12–18.

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

URL key: `dist_window`. Values: `lifetime` (default — absent
param) | `last_10` | `last_60d`. Read via `useSearchParams`
(NOT `useFilters` — `dist_window` is panel-local, not a FilterBar
field; adding it to FILTER_KEYS would pollute the link-builder
contract).

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

*Started 2026-05-04. Inventory + framing drafted first; batter v1
backend (§8) drafted + IMPLEMENTED 2026-05-05 across 5 commits.
Batter v1 frontend (§9) drafted 2026-05-05 — build-ready, awaiting
implementation. Bowler / fielder / team distribution dossiers
remain as sibling specs; no work done.*
