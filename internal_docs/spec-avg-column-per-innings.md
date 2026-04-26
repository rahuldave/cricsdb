# Spec: Avg-column per-innings semantic + chip baseline alignment

Status: build-ready (pending implementation).

Surfaces a class of pre-existing bugs in the Compare-tab avg
column made visible by Phase 1 (auto-scope-team) + Phase 2
(bucket_baseline) work:

1. Avg column displays POOL totals + POOL per-match rates. Pool
   per-match rates count both fielding/bowling sides per match in
   the numerator → ~2x the per-team-per-match rate. Confusing
   visually when a team's rate is then shown alongside.
2. Chip's `scope_avg` (computed inside team summary endpoints)
   uses a DIFFERENT scope than the avg column displays. Avg column
   is auto-narrowed to the team's tournament universe (Phase 1);
   chip's `scope_avg` is not. So chip says "+2%" while a naive
   visual comparison of team value vs avg-column value says "way
   worse".

Reported case (2026-04-26): `?team=RCB&...&compare1=__avg__&compare2=
SRH&season_from=2025&season_to=2025`. RCB shows `Catches/match 4.60
↑+2.0%` next to avg column showing `8.42`. User reads "RCB way
below average" but chip says green. Both bugs are present.

## The new semantic — "average innings"

The avg column represents what a typical INNINGS yields in scope.
NEVER pool aggregates. Where "innings" means:

| Metric family | Innings unit | Cardinality per match |
|---|---|---|
| Batting (per-team perspective) | one batting innings | 2 per match (one per team) |
| Bowling (per-team perspective) | one bowling innings | 2 per match (one per team) |
| Fielding (per-team perspective) | one fielding innings | 2 per match (= bowling innings — same act) |
| Partnerships (per-team perspective) | one batting innings | 2 per match |
| Match-level (results, toss) | one match | 1 per match |

For per-X rates already keyed on the right unit (RR per ball, econ
per over, etc.) the pool == per-innings — no change. For absolute
counts and per-match rates that aggregate both sides per match,
divide by the appropriate innings count.

## Per-metric table — what the avg endpoint returns now vs what it should return

Reads "POOL → PER-INNINGS" as: today's pool value → new per-innings
value. "Same" means no change needed (rate is already per-innings
because numerator and denominator both scale linearly with innings
count).

### `/scope/averages/summary` (match-level)

| Field | Direction | Today (pool) | New | Notes |
|---|---|---|---|---|
| matches | None | scope total | **same** | Match-level, scope-wide context |
| decided | None | scope total | **same** | |
| ties | None | scope total | **same** | |
| no_results | None | scope total | **same** | |
| toss_decided | None | scope total | **same** | |
| bat_first_wins | None | scope total | **same** | |
| field_first_wins | None | scope total | **same** | |
| bat_first_win_pct | (no direction in metadata) | rate | **same** | Already per-match |

Match-level metrics stay as-is. Scope-context counters; user expects
"74 matches in IPL 2025" not "1 match per match".

### `/scope/averages/batting/summary`

Innings unit: batting innings. Pool divisor: `innings_batted`.

| Field | Direction | Pool formula | New formula |
|---|---|---|---|
| innings_batted | None | scope total batting innings | **drop** (always = scope's innings_batted; meaningless when avg-column shows per-innings) |
| total_runs | None | SUM(runs) | SUM(runs) / innings_batted (= avg innings score) |
| legal_balls | None | SUM(legal_balls) | SUM(legal_balls) / innings_batted (= avg balls per innings) |
| run_rate | higher_better | SUM(runs) × 6 / SUM(balls) | **same** (per-ball rate; pool = per-innings) |
| boundary_pct | higher_better | SUM(bdy) / SUM(balls) | **same** |
| dot_pct | lower_better | SUM(dots) / SUM(balls) | **same** |
| fours | None | SUM(fours) | SUM(fours) / innings_batted |
| sixes | None | SUM(sixes) | SUM(sixes) / innings_batted |
| avg_1st_innings_total | higher_better | already per-innings | **same** |
| avg_2nd_innings_total | higher_better | already per-innings | **same** |
| highest_total | (identity) | MAX | **same** |

### `/scope/averages/bowling/summary`

Innings unit: bowling innings. Pool divisor: `innings_bowled`.

| Field | Direction | Pool formula | New formula |
|---|---|---|---|
| innings_bowled | None | scope total | **drop** (same reason as innings_batted) |
| matches | None | distinct match count | **same** (scope context) |
| runs_conceded | None | SUM | SUM / innings_bowled |
| legal_balls | None | SUM | SUM / innings_bowled |
| overs | None | balls/6 | (legal_balls / innings_bowled) / 6 |
| wickets | None | SUM | SUM / innings_bowled |
| economy | lower_better | SUM(runs)×6/SUM(balls) | **same** |
| strike_rate | lower_better | SUM(balls)/SUM(wickets) | **same** |
| average | lower_better | SUM(runs)/SUM(wickets) | **same** |
| dot_pct | higher_better | rate | **same** |
| fours_conceded | None | SUM | SUM / innings_bowled |
| sixes_conceded | None | SUM | SUM / innings_bowled |
| wides | None | SUM | SUM / innings_bowled |
| noballs | None | SUM | SUM / innings_bowled |
| wides_per_match | lower_better | SUM(wides)/matches | SUM(wides) / matches / 2 (per bowling side per match) |
| noballs_per_match | lower_better | SUM(noballs)/matches | SUM(noballs) / matches / 2 |

### `/scope/averages/fielding/summary`

Innings unit: fielding innings (= bowling innings = matches × 2).

| Field | Direction | Pool formula | New formula |
|---|---|---|---|
| matches | None | distinct match count | **same** (scope context) |
| catches | None | SUM | SUM / fielding_innings |
| caught_and_bowled | None | SUM | SUM / fielding_innings |
| stumpings | None | SUM | SUM / fielding_innings |
| run_outs | None | SUM | SUM / fielding_innings |
| total_dismissals_contributed | None | sum of above | sum of new above |
| catches_per_match | higher_better | (catches+cnb)/matches | (catches+cnb) / matches / 2 |
| stumpings_per_match | higher_better | stumpings/matches | stumpings / matches / 2 |
| run_outs_per_match | higher_better | run_outs/matches | run_outs / matches / 2 |

### `/scope/averages/partnerships/summary`

Innings unit: batting innings (each partnership belongs to one).

| Field | Direction | Pool formula | New formula |
|---|---|---|---|
| total | None | total partnerships in scope | total / innings_batted (= avg partnerships per innings) |
| count_50_plus | None | SUM | SUM / innings_batted (= avg 50+ partnerships per innings) |
| count_100_plus | None | SUM | SUM / innings_batted |
| avg_runs | higher_better | already per-partnership | **same** |
| highest | (identity) | MAX | **same** |

### `/scope/averages/{batting,bowling,fielding,partnerships}/by-season`

Same per-row transformations as the corresponding `summary` —
divide each season's absolute counts by that season's innings
count; halve the per-match rates.

### `/scope/averages/{batting,bowling}/by-phase`

Per-phase aggregates. Innings unit: batting innings (powerplay
innings, middle innings, death innings — but conventionally 1 per
batting innings since every batting innings touches all 3 phases).

| Field | Pool | New |
|---|---|---|
| runs / runs_conceded | SUM | SUM / innings (= avg phase runs per innings) |
| balls | SUM | SUM / innings |
| run_rate / economy | rate | **same** |
| wickets / wickets_lost | SUM | SUM / innings |
| boundary_pct / dot_pct | rate | **same** |
| fours / sixes | SUM | SUM / innings |

### `/scope/averages/partnerships/by-wicket`

Per-wicket-position. Innings unit: batting innings.

| Field | Pool | New |
|---|---|---|
| n | SUM | SUM / innings_batted (= avg partnerships at this wicket per innings) |
| avg_runs | per-partnership | **same** |
| avg_balls | per-partnership | **same** |
| best_runs | MAX | **same** |
| best_partnership | identity | **same** |

## Chip-baseline alignment (the OTHER bug)

Independent of the per-innings change: the team-summary endpoints
compute `scope_avg` for the chip via:

```python
# api/routers/teams.py — _compute_xxx_summary
t = await _xxx_aggregates(team, filters, aux)
s = await _xxx_aggregates(None, filters, aux)   # ← AUX has no scope_to_team
```

The frontend doesn't pass `scope_to_team` to the team-summary
endpoint (only to the avg-slot endpoint), so `aux.scope_to_team` is
None on this code path. The league-side call returns the BROAD
league baseline (e.g., "all men's club 2025") instead of the
auto-narrowed scope (e.g., "RCB's tournaments 2025 = IPL 2025").

Fix: synthesize the auto-scope-team for the league-side call:

```python
from copy import copy
league_aux = copy(aux)
league_aux.scope_to_team = team
s = await _xxx_aggregates(None, filters, league_aux)
```

Apply in `_compute_batting_summary`, `_compute_bowling_summary`,
`_compute_fielding_summary`, and inside the per-by-phase endpoint
handlers that call `_xxx_by_phase_aggregates(None, ...)`.

After this fix:
- Chip's `scope_avg` matches the avg column's data scope.
- Combined with the per-innings semantic above, chip's `scope_avg`
  numerically equals the avg column's displayed value for that
  metric.

## The chip-direction invariant test (NEW sanity test)

A unit-test-style assertion that runs against the live API for a
matrix of (team, scope, metric) combos and verifies for every
chip-bearing metric:

```
INVARIANT (per metric M with direction D):

  let team_value     = chip envelope's `value` for M on the team-
                       summary response
  let chip_scope_avg = chip envelope's `scope_avg` for M
  let displayed_avg  = the same field M on the matched avg-slot
                       response (i.e. /scope/averages/* with the
                       same scope + scope_to_team=team)
  let direction      = chip envelope's `direction` for M

  ASSERT 1 — chip_scope_avg == displayed_avg (the chip and the avg
            column must read the SAME baseline value, modulo
            float-rounding ε).
  ASSERT 2 — chip's delta_pct sign matches direction:
            • direction='higher_better' AND team_value > scope_avg
              ⇒ delta_pct positive
            • direction='higher_better' AND team_value < scope_avg
              ⇒ delta_pct negative
            • direction='lower_better' AND team_value < scope_avg
              ⇒ delta_pct positive (team is BETTER → green)
            • direction='lower_better' AND team_value > scope_avg
              ⇒ delta_pct negative (team is WORSE → red)
  ASSERT 3 — visual sanity of "improvement":
            If chip would render GREEN (better-than-baseline):
              • team_value > displayed_avg if direction='higher_better'
              • team_value < displayed_avg if direction='lower_better'
            If chip would render RED:
              symmetric inverse.

After the per-innings + scope-alignment fix, ASSERT 1 trivially
implies ASSERT 3 (since chip_scope_avg == displayed_avg).
```

### Test matrix

For each scope in:
- IPL 2024 (single season, single tournament)
- IPL 2020-2024 (multi-season)
- RCB unbounded (no season — exercises auto-scope-to-team)
- Aus T20 WC 2024 (international, single tournament+season)
- Aus unbounded internationals (no tournament)
- WPL 2024 (women's club)
- BBL 2024/25 (slash-format season)

For each scope × team in {primary team, league avg slot}:

For every chip-bearing metric in:
- run_rate, boundary_pct, bat_dot_pct, avg_1st_innings_total, avg_2nd_innings_total (batting summary)
- economy, strike_rate, average, bowl_dot_pct, wides_per_match, noballs_per_match, avg_opposition_total (bowling summary)
- catches_per_match, stumpings_per_match, run_outs_per_match (fielding summary)
- avg_runs (partnerships summary + by-wicket)
- per-phase rates: run_rate, boundary_pct, bat_dot_pct, economy, etc.
- per-season rates: run_rate, economy, etc.

Run all three asserts. Total combos: ~7 scopes × ~3 teams × ~25
chip-bearing metrics = ~525 assertions per run. Sub-second.

### Failure modes the test catches

- Chip baseline scope ≠ avg-column scope (today's main bug).
- Chip uses pool rate but avg column shows per-innings (or vice
  versa).
- Direction tag on a metric is wrong (e.g., dot_pct flipped to
  higher_better when it should be lower_better — would silently
  mislead users).
- delta_pct sign wrong (math bug in `wrap_metric`).
- Future schema additions where someone adds a new chip-bearing
  metric without checking the invariant.

### File location

`tests/sanity/test_chip_direction_invariant.py`. Same shape as the
other sanity scripts:
- `--db` flag for prod-snapshot validation.
- Exits 0 on all-pass, 1 on any failure.
- Prints PASS/FAIL line per (scope, team, metric) combo.

## Implementation plan — 5 commits

### Commit 1 — flip REG → NEW

`tests/regression/{teams,scope-averages}/urls.txt` — every URL
hitting an affected endpoint:

- All `/scope/averages/*` `summary` and `by-season` and `by-phase`
  and `by-wicket` URLs.
- All `/teams/{team}/*/summary` and `by-season` and `by-phase` URLs
  (chip values change).

Standalone commit so HEAD carries the NEW tag when the runner
captures it for the value-change commit (CLAUDE.md regression-
workflow rule).

### Commit 2 — backend: per-innings semantic in /scope/averages/*

Touch `api/routers/scope_averages.py` only. Each endpoint's
`_xxx_from_baseline` AND `_xxx_live` paths:
- Compute innings_count (or fielding_innings_count) from the same
  WHERE clause.
- Divide every absolute count by innings_count.
- Halve every per-match rate.
- Drop `innings_batted` / `innings_bowled` from the response (or
  set to 1 — TBD; cleaner to drop and document the change).
- Rates (RR, SR, econ, dot_pct, boundary_pct, avg_runs, avg_1st_inn)
  unchanged.

Identity-bearing fields (highest_total, best_partnership) unchanged.

### Commit 3 — backend: chip baseline alignment

Touch `api/routers/teams.py`:
- In `_compute_{batting,bowling,fielding}_summary`: build
  `league_aux = copy(aux); league_aux.scope_to_team = team` and
  pass to the league-side `_xxx_aggregates(None, filters, league_aux)`
  call.
- Same in `team_batting_by_phase`, `team_bowling_by_phase`,
  `team_partnerships_by_wicket` for their `_xxx_aggregates(None,
  ...)` calls.
- Remove `_half(s["..._per_match"])` calls in `wrap_metric` since
  the avg endpoint now halves at source. Otherwise it'd
  double-halve.

### Commit 4 — chip-direction invariant sanity test

`tests/sanity/test_chip_direction_invariant.py` per the spec
above. Validates the previous 2 commits' joint correctness.

### Commit 5 — flip NEW → REG + docs sync

After the regression suite shows `0 REG drifted, N NEW changed,
0 NEW unchanged`:
- Flip the NEW URLs back to REG (locked baseline).
- Update `internal_docs/perf-bucket-baselines.md` with the new
  semantic (the "Conventions" section grows from 5 to 6 entries —
  add "Convention 6: avg endpoint returns per-innings averages,
  never pool").
- Update `tests.md` to mention the new sanity test.

## Validation gates between commits

After each backend commit:
1. `tests/sanity/test_bucket_baseline.py` — pool conservation
   should still pass (the underlying counters don't change; only
   how they're rendered).
2. `tests/sanity/test_dispatch_equivalence.py` — should still
   PASS (both baseline and live paths transform the same way; the
   dispatch contract holds).
3. `tests/regression/run.sh teams` and `scope-averages` — expect
   `N NEW changed, 0 REG drifted`. Spot-check a few NEW diffs to
   confirm direction (avg-column values DROP for absolute counts,
   per-match rates HALVE, rates UNCHANGED).
4. `tests/integration/team-compare-average.sh` — re-target any
   hard-coded value assertions that change.
5. Browser smoke on the user's reported URL: avg column shows
   ~per-innings values, chip shows correct direction.

After all 5 commits:
- `test_chip_direction_invariant.py` — ALL PASS across the matrix.
- The user's URL: avg column shows ~4.21 catches/innings (was
  8.42), chip shows RCB 4.60 vs 4.21 = +9.3% green ↑ (was the
  misleading +2.0%).

## What this fix is NOT

- **Not a frontend change.** Backend response values change; the
  frontend reads them as-is. Field NAMES stay the same. If the
  user wants a label change ("Catches" → "Catches/inn") that's
  a follow-up frontend tweak, separate from this spec.
- **Not a populate change.** `bucket_baseline_*` tables still store
  cell-level pool sums (correct atomic granularity). Only the
  read-side aggregator endpoints divide by innings_count to
  present per-innings averages. The dispatch contract is
  untouched.
- **Not a `wrap_metric` change.** The envelope shape stays the
  same. Only the input values to `wrap_metric` (the league side)
  change.

## Open questions

1. **Should `innings_batted` / `innings_bowled` be dropped from
   `/scope/averages/*/summary` response?** Spec says drop. But
   the team-side endpoint returns them in the envelope. If the
   frontend renders both columns symmetrically, dropping breaks
   the symmetry. Alternative: keep but set to 1 (per-innings = 1
   innings). Still confusing. **Recommended decision: drop them
   from the avg endpoint entirely; the avg-column doesn't need to
   show "1 innings per innings".** Frontend update: the
   `AvgSummaryRow` skips the row if the field is missing.

2. **Match-level metrics on `/scope/averages/summary`:** stay as
   absolute totals? Yes — they're scope-context not "per
   something". Confirm.

3. **`avg_opposition_total` on bowling/by-season:** today live
   computes `SUM(opp_runs) / COUNT(opp_innings)`. That IS already
   per-innings (one opposition innings per bowling-team-side per
   match). Keep as-is. Same direction (lower_better) — bowling
   side wants opposition score low.

4. **Identity-bearing payloads (`highest`, `best_partnership`)**
   unchanged. They aren't averages; they're a single observation.
   No semantic change.
