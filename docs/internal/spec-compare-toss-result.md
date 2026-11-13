# Spec — toss_outcome + result on the Teams Compare tab

**Status:** SHIPPED 2026-05-26 (commits 4482d9f regression · 2c4f2d0
backend cohort · 90733d6 frontend · docs). Not pushed/deployed.
Decision date 2026-05-26. Emerged from the U11
inning-unify work (`spec-inning-unify-option-b.md`): fixing the Compare
primary column to honor `inning` surfaced that `toss_outcome`/`result`
are dropped on Compare entirely, AND that the league-average column
silently no-ops them server-side.

## 1. The decision

On the Teams Compare tab the three aux filters must be respected
symmetrically across **every** column (primary + team slots + the
league-average column):

| aux | team columns today | league-avg column today | target |
|---|---|---|---|
| `inning` | honored (slots) / FIXED primary (fda37c1) | honored (per-event) | ✓ done |
| `toss_outcome` | honored on `/teams/{t}/…` but DROPPED by Compare | **no-op** | honor everywhere |
| `result` | honored on `/teams/{t}/…` but DROPPED by Compare | **no-op** | honor everywhere |

**Why the league baseline is NOT tautological** (the crux — corrected
2026-05-26): the *count* of toss-winners is ~50% and match-winners ~50%,
but the *stats* differ sharply. CSK bowling economy: 8.25 overall, 8.08
when they won the toss, 8.43 when they lost it; 7.71 in wins, 9.02 in
losses. So "league average bowling economy among toss-winners" is a
real, distinct baseline — exactly what a team column filtered to
won-toss games should be compared against. The old code dropped it on
the cohort with the rationale "can't filter on outcome-vs-self when
there's no self" — wrong: each innings row HAS a self (`i.team`).

## 2. Backend — cohort (league-side) toss/result narrowing

`is_precomputed_scope` already returns False when `result`/`toss_outcome`
is set (bucket_baseline_dispatch.py:54-59) ⇒ the cohort always runs the
LIVE path ⇒ the fix lives in the two live cohort clause builders:

- `teams.py::_team_innings_clause(filters, team=None, side, aux)`
- `teams.py::_partnership_filter(filters, team=None, side, aux)`

Both currently gate result/toss on `team is not None` and drop them for
the cohort. Add a shared helper and apply it on the `team is None` branch
too:

```python
def _cohort_outcome_clause(side, aux) -> (str, dict):
    # Per-row subject for the league side: i.team is the batting team.
    # Discipline-aware, mirror of _option_b_team_inning:
    #   batting       → subject = i.team
    #   fielding/bowl → subject = the OTHER match team (winner/toss != i.team)
    # result: won/lost/tied ; toss_outcome: won/lost.
```

Truth table (A = i.team batting team, B = bowling team):

| side | filter | clause |
|---|---|---|
| batting | result=won | `m.outcome_winner = i.team` |
| batting | result=lost | `m.outcome_winner IS NOT NULL AND m.outcome_winner != i.team` |
| any | result=tied | `m.outcome_winner IS NULL` |
| fielding | result=won | `m.outcome_winner IS NOT NULL AND m.outcome_winner != i.team` |
| fielding | result=lost | `m.outcome_winner = i.team` |
| batting | toss=won | `m.toss_winner IS NOT NULL AND m.toss_winner = i.team` |
| batting | toss=lost | `m.toss_winner IS NOT NULL AND m.toss_winner != i.team` |
| fielding | toss=won | `m.toss_winner IS NOT NULL AND m.toss_winner != i.team` |
| fielding | toss=lost | `m.toss_winner IS NOT NULL AND m.toss_winner = i.team` |

`m` + `i` are already joined in every cohort query (the team-set
result/toss clauses already use `m.outcome_winner`). Covers
summary / by-season / by-phase for all four disciplines + partnerships
(batting-subject for the pooled partnership cohort; side passed through).

A12-equivalent: no precompute recompute — live path only.

## 3. Frontend — carry toss/result into every Compare column

`hooks/useCompareSlots.ts`:
- `ResolvedSlotScope`: add `'toss_outcome' | 'result'` to the Pick.
- `inheritedScope`: add `toss_outcome` + `result` from primary.
- NOT added to `OVERRIDABLE_SLOT_KEYS` — inherited-only (no per-slot
  override; the SlotScopeEditor has no toss/result row). The Splits
  Mosaic is page-level (above the tab bar) and renders on the Compare
  subtab too, so clicking won-toss / won-match there sets the page
  `?toss_outcome=`/`?result=` and the whole comparison narrows. Per-slot
  toss/result = possible future editor addition, out of scope here.

`components/teams/TeamCompareGrid.tsx::primarySlotOf`: add `toss_outcome`
+ `result` from filters (the primary column was already fixed to carry
`inning`; same treatment).

`components/teams/ColumnScopeStrip.tsx::buildSlotSegments`: add Toss +
Result segments so each column's scope strip shows them and the strips
AGREE across columns (the readout that proved the inning bug).

`api.ts`: no change — `getTeamProfile`/`getScopeAverageProfile` spread
`slot.scope` as filters; the new keys forward automatically.

## 4. Tests
- Backend: extend curl/regression — cohort bowling econ MUST differ
  across no-aux / toss=won / result=won (was flat 8.24). SQL-anchor the
  league-among-winners number.
- Integration: extend `inning_unify_compare.sh` OR new
  `compare_toss_result.sh` — DOM vs API: team column + avg column both
  narrow under toss=won/result=won; scope strips show + agree; chip
  baseline (scope_avg) flips too. Red against HEAD (cohort flat / Compare
  drops). 390px mobile.

## 5. Docs
- `docs/api.md` + `user-help.md`: Compare honors toss/result (note the
  league baseline is among-winners, not all-games).
- `inning-controls-mount-sites.md`: aux coverage on Compare.
