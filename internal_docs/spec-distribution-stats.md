# Spec — Distribution-shaped statistics on the API

> **Status:** Inventory + cross-discipline framing remain DRAFT.
> §8 (batter v1 distribution dossier) is **build-ready** —
> per-innings observation row, aggregate calculations, milestone
> probabilities, phase decomposition (per-innings obs + rollup),
> form windows (last-10 + last-60d), suggested-splits decision
> table, endpoint shape, implementation pointers, and sanity /
> regression test plan all pinned. Wire format and sampling-unit
> pinning resolved for batter; remaining open questions in §6 apply
> to the bowler / fielder / team slices.

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

## 8. Batter v1 — distribution dossier (build-ready)

> First concrete slice. Batter only, runs/innings only. Phase
> decomposition stored on every per-innings observation even though
> we are not surfacing strike-rate-by-phase yet, so future SR /
> dot% / boundary% by-phase work is a pure derivation — no schema
> or endpoint change. Frontend (semiotic histograms with mean +
> median overlays, sparklines) is **out of scope for this spec** —
> API only.

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
| `dismissed` | boolean — exists a `wicket` with `player_out_id = id` AND `kind NOT IN ('retired hurt', 'retired out', 'retired not out')` |
| `fours` | `COUNT(legal balls WHERE runs_batter = 4 AND COALESCE(runs_non_boundary, 0) = 0)` — excludes "ran 4" |
| `sixes` | `COUNT(legal balls WHERE runs_batter = 6)` |
| `dots` | `COUNT(legal balls WHERE runs_total = 0)` |
| `runs_pp`, `balls_pp` | as `runs`/`balls` plus `WHERE delivery.over_idx BETWEEN 0 AND 5` |
| `runs_mid`, `balls_mid` | `WHERE over_idx BETWEEN 6 AND 14` |
| `runs_death`, `balls_death` | `WHERE over_idx BETWEEN 15 AND 19` |

All conventions match `internal_docs/how-stats-calculated.md` —
legal-balls restriction, dismissal exclusion list, fours
non-boundary-flag check, phase boundaries on the DB-side 0–19
numbering.

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

### 8.9 Implementation pointers

- **New endpoint** in `api/routers/batters.py` — mirrors siblings
  `/batters/{id}/summary`, `/batters/{id}/by-innings`, etc.
- **New helper** `_innings_master_sample(person_id, filters, aux)`
  returning the per-innings observation rows. Reuses
  `FilterBarParams.build()` for the WHERE clause, the existing
  phase-boundary constants, and the existing dismissal-exclusion
  list from the batting-average code path.
- **New helper** `_distribution_dossier(observations)` computing
  the aggregate stats from a list of obs rows. Pure function, no
  DB access; used for lifetime + both windows.
- **New helper** `_form_windows(observations)` slicing the
  observation list into last-10 / last-60d windows and running the
  dossier on each.
- **Server-side `suggested_splits(scope)`** — new module
  `api/scope_links.py` (or alongside batter router), Python mirror
  of `frontend/src/components/scopeLinks.ts::suggestedSplits`.

### 8.10 Tests

**Sanity** (`tests/sanity/test_batter_distribution_invariants.py`):

- `n_innings == len(observations)` for `lifetime`, `last_10`,
  `last_60d`.
- `last_10.n_innings ≤ 10`; `last_10.observations` is the date-DESC
  tail of `lifetime.observations` (modulo ordering convention).
- `phase.powerplay.runs_total + phase.middle.runs_total +
  phase.death.runs_total == runs.total` (phase decomposition is a
  partition of the legal-balls runs). Same for `balls_total`.
- `runs.mean_per_innings × n_innings ≈ runs.total` (within
  rounding).
- `runs.average × n_dismissals ≈ runs.total` when `n_dismissals
  > 0`; `runs.average == null` when `n_dismissals == 0`.
- `milestones.p_X_plus × n_innings == count(o.runs ≥ X)` for each
  threshold (denominator-correctness).
- `form.delta.last_10_mean_minus_lifetime ==
  form.last_10.runs.mean_per_innings −
  lifetime.runs.mean_per_innings` (delta-consistency).
- TS / Python `suggestedSplits` lockstep: same scope input → same
  split output (same labels, same params), pinned via a small
  JSON fixture used by both test runners.

**Regression** (`tests/regression/batter_distribution/urls.txt`):

- Inventory of ~20 URLs covering the cross-product of
  `(player ∈ {Kohli, Mandhana, Bumrah-as-batter,
  retired-batter}) × scope ∈ {all-time, IPL, IPL 2024, vs
  Australia, at Wankhede, women_intl, season_only,
  gender_flip}`. Per the existing regression-harness convention
  (`internal_docs/regression-testing-api.md`).

**No agent-browser integration test in v1** — this spec ships
API only; the integration test arrives with the frontend slice.

---

*Started 2026-05-04. Inventory + framing drafted first; batter v1
spec (§8) added 2026-05-05 after a focused conversation pinning
runs/innings as the master sample, no quantiles, milestone
probabilities, notout convention, phase decomposition (per-innings
obs + rollup), last-10 + last-60d form windows, and scope-derived
suggested splits. Bowler / fielder / team specs to follow.*
