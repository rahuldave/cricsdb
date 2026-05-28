# Plan — Phase 3c: batting by-season + by-phase live cohort under the six filters

**Spec:** `internal_docs/spec-player-baseline-aux-fallback.md` Phase 3c
(picks up after 3b shipped clean in commit `00ef3d1`).

**Goal:** extend the live-fallback dispatch from 3b's
`compute_players_batting_cohort` (summary chip + distribution) to the
two adjacent cohort surfaces:

- `compute_players_batting_by_season` — per-season cohort baseline,
  used by /batters/{id}/by-season's chart overlay.
- `compute_players_batting_by_phase` — per-phase cohort baseline,
  used by /batters/{id}/by-phase's chip baselines.

Today both still read the precomputed scope-key tables only
(`playerscopestatsposition` for by-season, `playerscopestatsbattingphaseposition`
for by-phase) and silently ignore venue / opponent / team / inning /
toss / result. Same bug as 3b on the summary path.

---

## 1. The two functions, where they live

| Surface | Function | Source today | Source under 3c |
|---|---|---|---|
| /scope/averages/players/batting/by-season | `api/routers/scope_averages.py:2235` `compute_players_batting_by_season` | `playerscopestatsposition` GROUP BY scope_key+season | precomputed fast path unchanged; live path joins `inningsbatterperf` → `innings` → `match` with the six filters applied per row, GROUP BY `m.season`, position_bucket |
| /scope/averages/players/batting/by-phase | `api/routers/scope_averages.py:2527` `compute_players_batting_by_phase` | `playerscopestatsbattingphaseposition` GROUP BY scope_key+phase+position | precomputed fast path unchanged; live path aggregates `delivery` → `innings` → `match` with the six filters, classifies the over into a phase bucket per row, GROUP BY phase, position_bucket. Uses the shared `batting_delivery_contrib` helper (`api/batting_convention.py`) so the convention stays identical to the precompute |

Both functions are called from the discipline-router pages
(`api/routers/batting.py`) via the `/scope/averages/players/batting/*`
endpoints. The router's call signatures don't change.

## 2. Dispatch shape (mirror 3b)

```python
async def compute_players_batting_by_season(db, person_id, filters, aux, drop_set=None):
    if is_precomputed_scope(filters, aux):
        return await _by_season_precomputed(db, person_id, filters, drop_set)
    return await _by_season_live(db, person_id, filters, aux)
```

Same for `compute_players_batting_by_phase`. The current function body
becomes `_by_season_precomputed` / `_by_phase_precomputed` (no change).

## 3. Live by-season — `inningsbatterperf` + match.season

Shape mirrors `_batting_cohort_live` from 3b (the function shipped in
3b is the model — see `api/routers/scope_averages.py` around the
3b dispatch). Add `m.season` to the GROUP BY:

```sql
SELECT m.season,
       ib.position_bucket,
       COUNT(*)                                                       AS innings,
       SUM(ib.runs)                                                   AS runs,
       SUM(ib.balls)                                                  AS legal_balls,
       SUM(CASE WHEN ib.not_out = 0 THEN 1 ELSE 0 END)                AS dismissals,
       SUM(ib.fours)                                                  AS fours,
       SUM(ib.sixes)                                                  AS sixes,
       SUM(ib.dots)                                                   AS dots,
       SUM(CASE WHEN ib.runs >= 30 AND ib.runs < 50  THEN 1 ELSE 0 END) AS thirties,
       SUM(CASE WHEN ib.runs >= 50 AND ib.runs < 100 THEN 1 ELSE 0 END) AS fifties,
       SUM(CASE WHEN ib.runs >= 100                  THEN 1 ELSE 0 END) AS hundreds,
       SUM(CASE WHEN ib.runs  = 0 AND ib.not_out = 0 THEN 1 ELSE 0 END) AS ducks,
       COUNT(DISTINCT ib.batter_id)                                   AS n_players
FROM inningsbatterperf ib
JOIN innings i ON i.id = ib.innings_id
JOIN match   m ON m.id = i.match_id
WHERE i.super_over = 0
  AND <FilterParams.build clauses>
  AND <_option_b_team_inning(None, 'batting', aux)>
  AND <_cohort_outcome_clause('batting', aux)>
GROUP BY m.season, ib.position_bucket
```

Plus the player-side query (per-season per-position innings for mix
derivation) needs the same WHERE so the player's mix matches the
narrowed cohort's pool — this is the apples-to-apples requirement
3b already established for the summary.

Plus the per-season pool query (`n_players`, `n_innings_total`) at the
narrowed scope.

The downstream `by_season` row builder + cliff gate + convex-combine
is identical to the precomputed shape — same fields, same renames.
Extract the row-building loop into a helper so both paths call it.

## 4. Live by-phase — delivery-level aggregation

The per-innings table doesn't carry phase info. The precomputed
`playerscopestatsbattingphaseposition` writes via a per-ball populate
that classifies each delivery's over into a phase. Mirror that
classification live.

Use the shared `batting_delivery_contrib(d)` helper from
`api/batting_convention.py` (the one the per-phase / per-over /
phase×position populates already use — `feedback_rebuild_downstream_precomputes`
recorded that this helper is the single source of truth for the
all-ball convention).

```sql
SELECT CASE
         WHEN d.over_no < 6  THEN 'powerplay'
         WHEN d.over_no < 16 THEN 'middle'
         ELSE                     'death'
       END AS phase,
       <position bucket derivation per innings>,
       ...aggregate runs/balls/dots/fours/sixes/dismissals using
          the same all-ball rules as batting_delivery_contrib...
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match   m ON m.id = i.match_id
WHERE i.super_over = 0
  AND <filters.build>
  AND <option_b inning + cohort outcome>
GROUP BY phase, <position_bucket>
```

**Open question Q4 (from spec):** confirm the phase/over live path
semantics under an innings filter aren't degenerate. Specifically:
when `inning=0` (team batted first) narrows the cohort pool to half
the matches, do all three phases still have meaningful n? The spec
flags this as a check, not a known failure. Verify with a probe query
before claiming complete.

Position bucket derivation per innings is the same logic as
`scripts/populate_playerscopestats_position.py` — pre-cache by joining
to `inningsbatterperf.position_bucket` (added in 3a) instead of
re-deriving per ball. That works because batting position is one
value per (batter, innings); the join is cheap.

```sql
... FROM delivery d
JOIN inningsbatterperf ib ON ib.innings_id = d.innings_id AND ib.batter_id = d.batter_id
JOIN innings i ON i.id = d.innings_id
JOIN match   m ON m.id = i.match_id
...
GROUP BY phase, ib.position_bucket
```

The all-ball convention applies: `SUM(d.runs_batter)` over ALL the
batter's deliveries (NO `extras_noballs=0` filter on runs), `SUM(...)
FILTER (WHERE legal=1)` on balls/dots. Matches `batting_delivery_contrib`.

## 5. Reuse 3b's clause helpers — no new narrowing logic

Same imports as 3b's `_batting_cohort_live`:

```python
from .teams import _option_b_team_inning, _cohort_outcome_clause
from .bucket_baseline_dispatch import is_precomputed_scope
```

Both already imported in `scope_averages.py` (added in 3b at
`api/routers/scope_averages.py:47-55`). No additional imports.

## 6. Tests (red-then-green)

Extend `tests/integration/player_baseline_aux_fallback.sh` (the 3b
test) with:

- by-season chip narrowing: pick Kohli at IPL 2014-2018 + `inning=0`.
  For two specific seasons (2015, 2016) anchor the cohort `strike_rate`
  against direct SQL over `inningsbatterperf` with the inning narrow.
  Assert the by-season chart's reference line carries the narrowed
  cohort values (the same 3b chart-overlay test pattern uses
  `data-test-line-reference-label`).
- by-phase chip narrowing: same fixture, narrow by `result=won`. For
  powerplay / middle / death, anchor the cohort SR against direct
  delivery-level SQL with the six filter applied. Assert the
  /batters/{id}/by-phase response's `by_phase[].strike_rate` matches.

Plus the parity tests for the 3a-style rollup invariant should be
re-run to confirm precomputed-path output is byte-identical at
none-of-six (the existing `tests/sanity/test_playerscopestatsposition_rollup.py`
covers by-season's underlying table; an analogous spot-check for
`playerscopestatsbattingphaseposition` may need to be written).

## 7. Sequencing

One commit each:
1. **by-season live + dispatch + tests** (cleaner, no delivery scan).
2. **by-phase live + dispatch + tests + Q4 verification** (delivery-
   level, slightly more involved).

Per CLAUDE.md commit cadence — one feature per commit.

## 8. Out of scope (deferred to 3d, 3e)

- 3d: bowling live — separate function family, different precomputed
  table (`playerscopestatsover`), no `inningsbatterperf` analog.
  Bowling aggregation is at the over grain so the live path reads
  `delivery` grouped by over_no.
- 3e: fielding / keeping live — keeper-binary; reads `matchfielderperf`
  with the six filters applied.

## 9. Regression annotations to flip

Any REG-baselined URL hitting `/scope/averages/players/batting/by-season`
or `/by-phase` with one of the six filters will drift. Grep
`tests/regression/*/urls.txt` for those endpoints + the six filter
params, flip REG→NEW in the commit BEFORE the dispatch change
(`feedback_regression_before_shape`).

Quick grep to run first thing in the 3c session:
```
grep -nE "(by-season|by-phase).*?(filter_venue|filter_opponent|filter_team|inning=|toss_outcome|result=)" tests/regression/*/urls.txt
```

The flip is one commit, the dispatch is the next commit per surface,
the docs go last (Phase 4 of the spec).

## 10. Where 3b's pattern lives — quick re-orientation

`api/routers/scope_averages.py`:
- `_batting_cohort_precomputed(db, filters, drop_set)` — the fast path
- `_batting_cohort_live(db, filters, aux)` — the live path, joins
  inningsbatterperf+innings+match with reused team-side clauses
- `compute_players_batting_cohort(...)` — the dispatch + downstream
  row-builder

Read those three first when picking 3c up — they are the model.
