# Spec: Avg-column per-innings semantic + chip baseline alignment

Status: SHIPPED 2026-04-26. All 6 commits landed + 2 fix-ups
(`_scope_to_team_clause` NULL-event_name, Convention 2+3 unification).
End-to-end mechanism + helper map: `internal_docs/perf-bucket-baselines.md`
sections "What 'average' means" / "Chip-baseline scope alignment" /
"Read-side mechanism — end-to-end data flow" / "Per-innings transform
helpers". Session log: `internal_docs/enhancements-roadmap.md`
"Shipped 2026-04-26".

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

## Compare-tab display semantics — two-row layout for absolute counts

Per user direction (2026-04-26): a count and an average must NEVER
share the same row. Counts have one role (a fact about a specific
team — "Gujarat played 12 matches, took 41 catches" carries scale
information) and per-innings averages have another (the comparable
quantity against the league baseline).

Render absolute-count metrics on TWO rows:

| Row label             | Team col                        | Avg col                         |
|-----------------------|---------------------------------|---------------------------------|
| `<Metric>` (pool)     | team's pool count               | "—" (blank)                     |
| `<Metric>/inn`        | team's pool count / innings     | scope's per-innings average     |

The team col always carries both rows (so the user sees both the raw
fact AND the per-innings rate). The avg col is blank on the count
row (no scale-bearing fact to display — pool league counts at
"4096 catches" are not a baseline anyone can read against the team's
"69"); the avg col carries only the per-innings row.

Per-X rates (run rate, economy, strike rate, dot %, boundary %,
avg_runs, avg_1st_innings_total) and identity payloads (highest,
best_pair) stay on a single row in both columns — they're
inherently comparable across columns.

### Affected metrics — pool row + `/inn` row

**Bowling summary**
- `Wickets` (pool, team-only) + `Wickets/inn` (both)

**Fielding summary**
- `Catches` (pool, team-only) + `Catches/inn` (both)
- `Stumpings` (pool, team-only) + `Stumpings/inn` (both)
- `Run-outs` (pool, team-only) + `Run-outs/inn` (both)
- The existing single-row `Catches/match` (per-match rate) is
  REPLACED by `Catches/inn`. Mathematically identical on the team
  side (each team has 1 fielding innings per match), but the
  label aligns with the new convention.

**Partnerships summary**
- `50+` (pool, team-only) + `50+/inn` (both)
- `100+` (pool, team-only) + `100+/inn` (both)

### Substats inside other rows (phase bands, by-wicket)

The phase-band `· w {wickets}` substat and the by-wicket `· n {n}`
substat are NOT given a separate row. They follow a single
"per-innings everywhere" rule on substats: both team and avg cols
render the per-innings rate (e.g. `· w 1.4/inn`, `· n 0.4/inn`).
Two-row treatment is reserved for top-level rows; substats stay
one-line.

The team col's pool count for these substats (e.g. RCB's 28
phase-wickets in scope) is not lost — it's available on the
underlying team page. The Compare tab's role is comparison; the
absolute fact is a click away.

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

**Scope alignment alone is not sufficient for the chip-direction
invariant to hold.** The team-side helper `_xxx_aggregates(None, …)`
also has to return per-innings values when `team=None` — otherwise
`chip_scope_avg` (computed from the team-side helper) ≠
`displayed_avg` (computed from `scope_averages`'s per-innings
helper) and ASSERT 1 fails. See Commit 2 below — the per-innings
transform must be applied in BOTH `api/routers/scope_averages.py`
AND the team-side `_xxx_aggregates_*(team=None, …)` paths.

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
- **IPL 2025 with primary=RCB, compare2=SRH (CANONICAL REPRODUCER —
  the scope where the bug was first reported; must stay in the
  matrix as a permanent regression marker)**
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
- catches_per_match (= catches_per_inn after Commit 5), stumpings_per_match, run_outs_per_match (fielding summary)
- avg_runs (partnerships summary + by-wicket)
- per-phase rates: run_rate, boundary_pct, bat_dot_pct, economy, etc.
- per-season rates: run_rate, economy, etc.

Run all three asserts. Total combos: ~8 scopes × ~3 teams × ~25
chip-bearing metrics = ~600 assertions per run. Sub-second.

### Integration-test layer (browser-level, complements sanity test)

The sanity test hits the API directly. A separate integration test
at `tests/integration/team-compare-average.sh` exercises the same
invariant through the rendered page — catches frontend bugs
(wrong field plumbed to chip, label mismatch, two-row layout
breakage) that the API-only sanity test can't see.

Targets the canonical reproducer URL:

```
/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club
  &tab=Compare&compare1=__avg__&compare2=Sunrisers+Hyderabad
  &season_from=2025&season_to=2025
```

Browser-agent script:
1. Load the URL.
2. For each metric in the screenshot's chip-bearing rows, parse
   the team's displayed value (`team_value`), the avg col's value
   on the same row (`displayed_avg`), and the chip's sign + colour
   (`chip_sign`, `chip_colour`).
3. Look up the metric's direction from the response (or hardcode
   the direction map per the test).
4. Assert:
   - `team_value > displayed_avg` ⇒ chip sign positive (for
     higher_better) OR negative (for lower_better).
   - chip colour green ⇔ team on the better side of avg per
     direction.
5. Run for both compare2=SRH (peer team) and compare1=avg-column
   chips. Walk the absolute-count rows too — assert the avg col
   shows "—" on the pool row and a number on the `/inn` row.

This is the user-facing version of the chip-direction invariant
and is the test that would have caught the original bug
end-to-end.

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

## Implementation plan — 6 commits

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

### Commit 2 — backend: per-innings semantic in BOTH avg + team-side league helpers

Touch `api/routers/scope_averages.py` AND `api/routers/teams.py`.
The per-innings transform must apply on TWO code paths:

**A. `api/routers/scope_averages.py`** — every endpoint's
   `_xxx_from_baseline` AND `_xxx_live` paths:
- Compute innings_count (or fielding_innings_count) from the same
  WHERE clause.
- Divide every absolute count by innings_count.
- Halve every per-match rate.
- Drop `innings_batted` / `innings_bowled` from the response (or
  set to 1 — TBD; cleaner to drop and document the change).
- Rates (RR, SR, econ, dot_pct, boundary_pct, avg_runs, avg_1st_inn)
  unchanged.

**B. `api/routers/teams.py`** — `_xxx_aggregates_baseline` and
   `_xxx_aggregates_live` when called with `team=None` (the league-
   side call inside `_compute_xxx_summary` for the chip's
   `scope_avg`). Same per-innings transform as path A. Without
   this, `chip_scope_avg` (path B output) ≠ `displayed_avg` (path A
   output) and the chip-direction invariant fails.

Recommended factoring: extract the per-innings transform to a
shared helper (e.g. `_apply_per_innings(row, innings_count,
half_keys=(...))`) that both routers' `team=None` branches call.
Keeps the math in one place and makes Commit 4 (the invariant
test) trivial to keep green when new metrics are added.

Identity-bearing fields (highest_total, best_partnership) unchanged.

### Commit 3 — backend: chip baseline scope alignment + drop double-halve

**Order matters: must land AFTER Commit 2.** This commit removes
`_half(s["..._per_match"])` wrappers in `wrap_metric` calls. Those
wrappers exist today because the team-side helper returns pool
per-match rates (which double-count both fielding/bowling sides per
match) and `_half` corrects them at the call site. Once Commit 2
makes `_xxx_aggregates(None, …)` return halved-and-per-innings
values, `_half` would double-halve. Commit 3 drops the wrapper.

If Commit 2 has not yet made the team-side helper per-innings
aware, Commit 3 produces nonsense — pool team values compared to
half-of-pool league values. Don't reorder.

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

### Commit 5 — frontend: two-row layout for absolute-count metrics

Touch `frontend/src/components/teams/AvgSummaryRow.tsx` and
`frontend/src/components/teams/TeamSummaryRow.tsx` (and
`PartnershipByWicketRows.tsx` / `PhaseBandsRow.tsx` for the
substat conversion).

Per the "Compare-tab display semantics" section above:

**`TeamSummaryRow.tsx`** — for each absolute-count metric (Catches,
Stumpings, Run-outs, Wickets, 50+, 100+), render TWO rows:
1. The pool count row (label as today, e.g. "Catches", value =
   `f.catches.value`, no chip).
2. The per-innings row (label "Catches/inn", value computed
   client-side as `f.catches.value / matches`, chip env constructed
   from the metric's existing envelope but with `value` and
   `scope_avg` divided by innings_count). Use direction tag from
   the existing `*_per_match` metric where one exists; otherwise
   inherit `null` (no arrow).

   Innings count source per discipline:
   - fielding: `summary.matches` (each team has 1 fielding innings/match)
   - bowling: `bowling.innings_bowled` envelope `.value`
   - partnerships / batting: `batting.innings_batted` envelope `.value`

**`AvgSummaryRow.tsx`** — for each absolute-count metric:
1. The pool row (label as today) renders "—" (blank).
2. The per-innings row (label "Catches/inn") renders the avg
   endpoint's value AS-IS (Commit 2 already returns per-innings).

**`PhaseBandsRow.tsx`** — convert `· w {wickets}` substat to
`· w {wickets/inn}/inn`. Compute team-side per-innings as
`p.wickets / innings_bowled`; avg-side per-innings already comes
through after Commit 2.

**`PartnershipByWicketRows.tsx`** — convert `· n {n}` substat to
`· n {n/inn}/inn`. Compute team-side per-innings as
`r.n / innings_batted`; avg-side already comes through.

The existing `Catches/match` row label flips to `Catches/inn`
(numerically identical on the team side; semantically clearer).
The `wides_per_match` / `noballs_per_match` envelopes stay as-is
(they're rendered on the underlying team-bowling page, not on the
Compare tab — unchanged surface).

### Commit 6 — flip NEW → REG + docs sync

After the regression suite shows `0 REG drifted, N NEW changed,
0 NEW unchanged`:
- Flip the NEW URLs back to REG (locked baseline).
- Update `internal_docs/perf-bucket-baselines.md` with the new
  semantic (Convention 6 already drafted in 5155306; verify it
  still describes what shipped).
- Update `tests.md` to mention the new sanity test.
- Update `CLAUDE.md` "Compare tab" landing-pages section if the
  two-row layout is worth a one-liner.

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

After Commit 5 (frontend):
6. Browser smoke via agent-browser on the canonical Compare URL —
   verify the two-row layout renders, the avg col shows "—" on
   the pool row + a number on the `/inn` row, and chip arrows
   point the right direction.

After all 6 commits:
- `test_chip_direction_invariant.py` — ALL PASS across the matrix.
- The user's URL: avg column shows ~4.21 catches/innings (was
  8.42), chip shows RCB 4.60 vs 4.21 = +9.3% green ↑ (was the
  misleading +2.0%).
- Compare-tab visual: each affected discipline has the new
  two-row layout; team col carries pool + per-inn, avg col
  carries "—" + per-inn.

## What this fix is NOT

- **Not a populate change.** `bucket_baseline_*` tables still store
  cell-level pool sums (correct atomic granularity). Only the
  read-side aggregator endpoints divide by innings_count to
  present per-innings averages. The dispatch contract is
  untouched.
- **Not a `wrap_metric` change.** The envelope shape stays the
  same. Only the input values to `wrap_metric` (the league side)
  change.
- **Not an API field-rename.** Response field names stay the same
  (`catches`, `wickets`, `count_50_plus`, `n`); only their numeric
  values change on the avg endpoint, and the frontend renames the
  ROW LABEL ("Catches" → "Catches/inn") on the avg col's per-innings
  row. The team col's pool row keeps the unsuffixed label
  ("Catches" → 69) because it's still a pool count.

## What this fix IS, on the frontend

- **Two-row layout for absolute counts on the Compare tab.** Pool
  count and per-innings rate get separate rows so a count and an
  average never share the same row. Affects fielding (Catches /
  Stumpings / Run-outs), bowling (Wickets), and partnerships (50+ /
  100+). Phase-band `w` substat and by-wicket `n` substat collapse
  to a single per-innings substat in both columns. See Commit 5.

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
