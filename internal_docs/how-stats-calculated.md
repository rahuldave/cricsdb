# How stats are calculated

Reference for every non-trivial formula in the codebase. Maintain
this when adding new metrics or changing existing semantics.

The formulas live in code; this doc is the human-readable companion.
Each section gives the **formula**, **why it's that formula and not
something else**, and **where it's implemented**.

For broader convention rationale (e.g. why we chose concatenated
over per-innings means), see `internal_docs/design-decisions.md`.
For the chip-baseline alignment story, see
`internal_docs/perf-bucket-baselines.md`.

---

## Aggregation primitives

Three transforms in parallel. Pick the right one for your metric:

### Pool (raw sum)

`SUM` over rows in scope. Used when the answer IS the count: "how
many matches in this scope" → 870. Returned by team-side endpoints
for the team's own counts (Australia's 22 matches in scope).

### Per-INNINGS

`pool ÷ innings_count`. Applied to batting/bowling/fielding count
metrics on the avg col so "the average team's catches in scope" =
"catches per innings × innings_count_per_team". Used for fours,
sixes, catches, total_runs, legal_balls, etc.

Implementation: `_apply_batting_per_innings`,
`_apply_bowling_per_innings`, `_apply_fielding_per_innings`,
`_apply_partnerships_per_innings` in `api/routers/teams.py`.

### Per-TEAM

`pool × multiplier ÷ unique_teams_in_scope`. Multiplier 2 when each
match generates 2 team-instances (matches, ties, no_results — both
sides share the outcome), 1 when each match generates 1 instance
(wins, losses, toss_wins, bat_first_wins, field_first_wins).

Used for team-level RESULTS metrics on the avg col so "the average
team's matches in scope" = `pool × 2 / unique_teams`, not the pool
total.

Implementation: `_apply_results_per_team` +
`_unique_teams_in_scope` in `api/routers/teams.py`. Documented in
`internal_docs/spec-avg-col-per-team-transform.md`.

### Concatenated rates

`SUM(numerator) × multiplier / SUM(denominator)`. Used for
run_rate, economy, boundary_pct, dot_pct. Treats the entire scope
as one giant innings — sum runs, sum balls, divide. NOT a mean of
per-innings rates.

Why: per-innings means weight 5-ball cameos and 120-ball anchor
innings equally, distorting the answer. The concatenated rate
weights each ball equally, which matches what "scoring rate" means
intuitively. Tradeoff: a few outlier high-scoring innings pull the
number up. Documented + revisit-flag in
`design-decisions.md` "Run rate: concatenated, not per-innings
averaged".

---

## Batting

### Run rate

```
run_rate = SUM(runs_total in legal balls) × 6 / SUM(legal balls)
```

The 6 is overs-conversion (6 balls per over). `legal balls` =
deliveries with `extras_wides = 0 AND extras_noballs = 0`. Wides
and no-balls give the bowling team a runs penalty but don't count
as a ball faced by the batter — excluding them keeps the rate
honest.

Same formula at every level (innings, match, season, scope), just
the SUM range changes.

### Strike rate (batter)

```
strike_rate = SUM(runs_batter on legal balls) × 100 / COUNT(legal balls)
```

The 100 is the conventional scaling. `runs_batter` is the runs
attributed to the batter on the strike (excludes byes/leg byes).
Identical to a single-innings SR averaged across all the batter's
innings, weighted by balls faced — the concatenated-rate property.

### Batting average

```
average = SUM(runs_batter on legal balls) ÷ dismissals
```

`dismissals` = wickets where this person is in `wicket.player_out_id`,
EXCLUDING `('retired hurt', 'retired out')`. Note `retired not out`
is also excluded — the batter wasn't dismissed, just couldn't continue.

If `dismissals == 0`, return `null` (don't divide by zero, don't
inflate to "infinity not out").

### Boundary %

```
boundary_pct = (SUM(fours) + SUM(sixes)) × 100 / COUNT(legal balls)
```

`fours` = `runs_batter = 4 AND COALESCE(runs_non_boundary, 0) = 0`.
The `runs_non_boundary` check distinguishes "ran 4" (3 + a
mis-throw) from "boundary 4". `sixes` = `runs_batter = 6` (no
non-boundary sixes possible — the ball can't be hit far enough on
the ground for a running 6).

### Dot %

```
dot_pct = COUNT(dots) × 100 / COUNT(legal balls)
```

`dots` = `runs_total = 0 AND extras_wides = 0 AND extras_noballs = 0`.
Notes: a leg-bye 0 still counts as a dot (no run scored, batter
took strike); a wide is NOT a dot (it's an illegal ball, not faced
by the batter).

---

## Bowling

### Economy

```
economy = SUM(runs_total on ALL deliveries) × 6 / COUNT(legal balls)
```

CRITICAL ASYMMETRY: numerator counts ALL runs conceded (including
runs from wides + no-balls + extras), denominator counts only
legal balls. This matches how cricket boards display economy —
your overs total goes up only on legal deliveries, but every run
the bowler concedes counts against them.

`runs_total` includes byes / leg-byes (the bowler is debited those).

### Bowling average

```
average = SUM(runs_total on ALL deliveries) ÷ wickets
```

Where `wickets` = wickets attributed to this bowler EXCLUDING
`('run out', 'retired hurt', 'retired out', 'obstructing the field')`.
Run-outs aren't the bowler's wicket; the latter three aren't
attributable wicket types in the conventional sense.

### Bowling strike rate

```
strike_rate = COUNT(legal balls) ÷ wickets
```

Balls per wicket. Lower is better. Same wickets exclusion rule as
average.

### Wides per match / no-balls per match

```
wides_per_match = SUM(wides) ÷ matches_played
```

Where `wides` = `SUM(extras_wides)` — the run-count attributed as
wides, NOT the count of wide deliveries. (A 5-wide because of a
boundary off the wide is one delivery, five runs.)

### Phase boundaries

API responses use 1-20 over numbering:
- **Powerplay**: overs 1–6
- **Middle**: overs 7–15
- **Death**: overs 16–20

DB stores 0-19 (matching cricsheet). Each router's response adds
+1 before returning. SQL clauses internally use 0-5 / 6-14 / 15-19.

---

## Fielding

### Catches / Stumpings / Run-outs

Counts from `fieldingcredit` rows joined to `delivery` → `innings`
→ `match`. The `kind` column stores underscored literals — the
multi-word kinds use `_`, NOT spaces:

- **catches**: `kind = 'caught'`, fielder = `fc.fielder_id`.
  INCLUDES `caught_and_bowled` per Conventions 2 + 3 (see
  `perf-bucket-baselines.md`).
- **caught_and_bowled**: `kind = 'caught_and_bowled'` — separate
  sub-count when bowler == fielder. Consumers MUST NOT add
  `catches + caught_and_bowled` (double-counts).
- **stumpings**: `kind = 'stumped'`, fielder = the keeper.
- **run_outs**: `kind = 'run_out'`, fielder credited via
  `fieldingcredit` (handles cases where multiple fielders share
  credit on a single run-out — each gets its own row).

The four canonical values in the schema are `'caught'`, `'stumped'`,
`'run_out'`, `'caught_and_bowled'`. Any audit SQL that pins these
must use the underscored form — `'run out'` / `'caught and bowled'`
silently match zero rows.

### Per-match rates

```
catches_per_match    = SUM(catches) ÷ matches_played
stumpings_per_match  = SUM(stumpings) ÷ matches_played
run_outs_per_match   = SUM(run_outs) ÷ matches_played
```

For the avg col, `matches_played` is the per-team match count
(see "Per-team" transform above), so the rate is comparable
team-to-team.

### Keeper identification

There's no keeper field in cricsheet — we infer it via a 4-layer
algorithm:
1. Stumping in this innings → that fielder.
2. Exactly one career-N≥3 keeper in the XI → that person.
3. Exactly one team-ever-keeper in the XI → that person.
4. Otherwise NULL with `ambiguous_reason` + `candidate_ids_json`.

Stored in `keeper_assignment` table per innings. Fully documented in
`internal_docs/spec-fielding-tier2.md`.

---

## Team-level (results) metrics

### Win rate (per-team average)

```
win_pct = decided × 100 / (matches × 2)
```

Where `decided` = matches with an `outcome_winner`, `matches` =
total matches in scope.

Why this formula: think of every match as 2 team-perspectives
(`matches × 2` total team-matches in scope). Each decided match
contributes 1 win + 1 loss to those team-perspectives. Tied
matches contribute 2 ties; no-results contribute 2 NRs. The
average team's win rate = `total wins ÷ total team-matches`.

Equivalently: `50% × decided_rate`. With 95% decided you get ~47.5%.

NOT the same as `bat_first_win_pct` (see below). Pre 2026-04-28
the code mistakenly used `bat_first_win_pct` as `win_pct.scope_avg`.
Fixed in `spec-avg-col-per-team-transform.md`.

### Bat-first win %

```
bat_first_win_pct = bat_first_wins × 100 / decided
```

A tactical bias measure: of decided matches, what fraction were
won by the team that batted first? Useful for venue/condition
analysis (dew-affected day-night matches favor chasing → bat-first
% drops). Surfaced as a separate informational field — NOT
substituted for `win_pct`.

### Per-team match count

```
matches_per_team = SUM(matches) × 2 ÷ unique_teams_in_scope
```

Each match seen from 2 sides; divide by distinct teams in scope.
For FM 2024-25: 140 × 2 / 11 = 25.45 matches per team on average.

### Per-team toss-win rate (informational)

```
toss_wins_per_team = SUM(toss_decided) ÷ unique_teams_in_scope
```

Each match has 1 toss winner attributed to one team, so divisor is
1× (not 2×). Equilibrium expectation ≈ matches/teams (each team
has equal toss probability), and the rate per team's matches is
≈50% by symmetry.

---

## Partnerships

### Partnership runs

`partnership.partnership_runs` is precomputed at populate time:
sum of `runs_total` from the deliveries between the partnership's
start (previous wicket fell) and end (next wicket fell or innings
ended). EXCLUDES extras that don't credit to either batter — wait,
actually INCLUDES all `runs_total` (the team's runs scored in the
partnership), because partnerships are attributed to both batters
together regardless of who hit the ball.

### Partnership thresholds

```
count_50_plus  = COUNT(partnerships where partnership_runs >= 50)
count_100_plus = COUNT(partnerships where partnership_runs >= 100)
```

Both EXCLUDE `ended_by_kind IN ('retired hurt', 'retired not out')`
— a partnership ended by a retired-hurt isn't a "completed" stand
in the conventional sense. Note `count_100_plus` is a SUBSET of
`count_50_plus` (every 100+ partnership is also 50+).

### By-wicket aggregations (Series Partnerships tab)

`/api/v1/series/partnerships/by-wicket` returns one row per
`wicket_number` with `n`, `avg_runs`, `avg_balls`, `best_runs`. The
same `ended_by_kind NOT IN ('retired hurt', 'retired not out')`
exclusion applies (see `api/routers/tournaments.py:2664`), AND
`p.wicket_number IS NOT NULL` is required (drops unbroken /
carry-over partnerships with no fallen wicket).

The sibling `/series/partnerships/top` endpoint (the top-N list on
the same DOM page) does NOT apply either filter — top-N reports the
biggest stands across the entire pool, including unbroken ones.
That's why an unbroken 205 (no wicket fallen, `wicket_number IS
NULL`) can appear at row 0 of the top-N table while being absent
from every row of the by-wicket grid.

### Best pair

For Compare-tab "best pair" / "highest partnership," sorted by
`partnership_runs DESC`. Identity-bearing field — only computed
on team-side requests, not the avg col (a "league average pair"
has no identity).

---

## Scope conventions

### Legal balls vs all deliveries

- **Batting metrics** use legal balls (excludes wides + no-balls).
- **Bowling `runs_conceded`** uses ALL deliveries.
- **Bowling `economy denominator`** uses legal balls (overs basis).
- **Bowling `strike_rate denominator`** uses legal balls.

This is THE most common gotcha for new contributors. Documented
in `design-decisions.md`. The `_safe_div` helper takes mul/ndigits
arguments to handle the various scaling factors.

### Bowler wicket attribution

Bowlers get credit for wickets EXCEPT:
- run out (no bowler skill — fielder caused it)
- retired hurt (no dismissal)
- retired out (rare, conventionally not bowler-credited)
- obstructing the field (rare, not bowler-credited)

`obstructing the field` was excluded 2026-04-something; check git
log if it predates the doc.

### Tie / no-result handling

- A **tie** = match decided with equal scores. Counts in `ties`,
  not `decided`. Both teams "tied" for the team-perspective view.
- A **no-result** = abandoned match (rain, etc.). Counts in
  `no_results`, not `decided`.
- Both contribute to `matches` total but not to `decided`.

### Super-over deliveries

Most metrics EXCLUDE super-over deliveries via `i.super_over = 0`
in the WHERE clause. Some endpoints intentionally include them
(check the SQL — see `bowling.py`'s comment about leaderboards).

### Phase boundaries

See "Bowling/Phase boundaries" above. Identical for batting.

---

## Inning split (1st innings / 2nd innings)

Page-local 1st-innings / 2nd-innings filter — NOT a FilterBar field.
Lives in `AuxParams.inning` (`int 0|1`); UI surface is the
`InningToggle` pill on player and team Batting/Bowling/Fielding/
Partnerships pages, plus the per-slot `compareN_inning=` override on
the Compare tab. URL param `?inning=`.

### Partition invariant

For every additive metric (counts and sums — runs, balls, wickets,
catches, stumpings, partnerships, fielding events) and every closed
scope:

```
metric(inning=0) + metric(inning=1) == metric(unfiltered)
```

Tested on every commit by `tests/sanity/test_inning_split_partition.
py` across IPL 2025, T20 WC Men 2024, BBL 2024/25, and all-men-intl
2024 — 4 scopes × 4 teams × 3 disciplines × N metrics, plus
identity-bearing fields (`highest_total` reconstructs as max of
inning-0 and inning-1 maxes), plus an API-level smoke that catches
helper bugs the SQL-only path misses.

### Two semantic mechanisms

The inning narrowing applies via two distinct mechanisms depending
on the endpoint shape:

1. **Innings-joined endpoints** (every player / team /by-phase /
   /by-inning / /summary that JOINs `innings`): the central clause
   `i.innings_number = :inning` lands in `FilterBarParams.build()`,
   gated on `has_innings_join=True`. Composes naturally with the
   existing `i.team = :team` discriminator already in the SQL.
   Slot `inning=0` reads:
   - **Batting side** (`i.team = :team`): matches where this team
     batted in inning 0 = matches where this team batted first.
   - **Bowling/Fielding side** (`i.team != :team`): matches where
     this team's opposition batted in inning 0 = matches where
     this team bowled first.
   These are COMPLEMENTARY match subsets — together they describe
   the team's "first-up activity across whatever role they were in"
   (the §3.4 dual-meaning). The SlotScopeEditor's "Innings"
   tooltip surfaces this for users.

2. **Match-level endpoints** (`/teams/{team}/{summary,by-season,
   vs-opponent,match-list}` — `has_innings_join=False`): the
   central clause can't apply (no `i` alias). Instead, the
   `_inning_match_filter(team, aux)` helper (api/routers/teams.py)
   emits a derived match-id subquery committing to the "team
   batted in inning X" reading:
   ```sql
   m.id IN (SELECT i2.match_id FROM innings i2
             WHERE i2.team = :im_team
               AND i2.innings_number = :im_inn
               AND i2.super_over = 0)
   ```
   Reading: `inning=0` → matches where team batted first;
   `inning=1` → matches where team batted second / chased.

### Per-innings divisor

Every league-side baseline that divides a count by an
"innings-count" divisor MUST compute that divisor from the same
`aux.inning`-narrowed query that produced the numerator. A divisor
pulled from a non-narrowed sibling query produces a per-innings
rate that silently halves (numerator narrows, denominator doesn't),
breaking the chip-alignment math invariant. Helpers:

- `_innings_count_per_inning(filters, aux, side)` — innings count
  GROUPED BY innings_number for the given side (batting / fielding).
  Used by `/by-inning` aggregators' team=None branch to compute the
  per-row divisor.
- `_apply_fielding_per_innings(out, fielding_innings, halve_per_match)`
  — fielding has a special multiplier flip under inning narrowing:
  `mult=1` (not 2) and `halve_per_match=False`, since each match
  contributes only ONE fielding innings to the inning-X scope.

### Match-role axis (`bat_first=true|false`) is a SEPARATE concept

A possible future filter for "matches where this team batted first"
(regardless of which inning the data was generated in) is
match-level, not innings-level — different SQL clause, different
semantic. Composes orthogonally with `inning`. Not in this spec.
See design-decisions.md "Match-role axis is separate from
per-innings" for the differentiation.

### Out of scope

`/matches` list, `/head-to-head`, `bucket_baseline_*` precomputation,
"chasing" derived from D/L target — see spec §1 + §9. Live
aggregation handles the inning narrowing without precomputed help;
revisit if measured hot.

Spec: `internal_docs/spec-inning-split.md`.
Convention doc: `internal_docs/design-decisions.md` "Inning-split
labelling: frame by match, not by side of the ball" + "Match-role
axis is separate from per-innings".

---

## Maintenance rule

**When you add a metric:**
1. Pick the right transform (pool / per-innings / per-team /
   concatenated).
2. Mirror the team and avg endpoints — call the same `_apply_*`
   helper on both so chip envelope and avg col agree.
3. Add an entry here. Include the formula, the WHY, and the impl
   pointer.
4. Add a chip-direction invariant test if the metric has a
   chip envelope (`tests/sanity/test_chip_direction_invariant.py`).

**When you change a metric:**
1. Update the formula here.
2. Re-pin any sanity-test anchors that key on the metric.
3. Flip affected REG URLs to NEW in a separate, earlier commit
   (workflow in CLAUDE.md / `regression-testing-api.md`).

---

*Started 2026-04-28 after a user question revealed the avg col was
displaying pool totals where it should display per-team averages
for results metrics. Grow this doc whenever a new "wait, how is
that calculated?" question surfaces.*
