# Spec — `team_class` on the FilterBar

Promote `team_class=full_member` from a per-slot avg-picker control
on the Compare tab to a first-class FilterBar field. Today it's an
opt-in narrowing on a single avg slot; users want a global
"international, full-members only" mode that applies to every tab —
match list, batters/bowlers/fielders leaders, partnership records,
venue dossier, etc.

## Why

User flagged this 2026-04-27 after the per-slot Compare-tab fix
shipped:

> Add it to the overall filterbar as well if international is
> chosen … wide ranging and you must think of its impacts.

Concrete examples that need it:
- Batting > Leaders, men_intl 2024-25: today the top-10 shows
  Suryakumar / Yashasvi / Dasun Shanaka / Pathum Nissanka mixed in
  with associate-team players who pile up runs against weaker
  attacks (USA's Andries Gous, etc.). With `team_class=full_member`
  the leader board reflects "performances against full-member
  attacks" only.
- Series tab landing for ICC Men's T20 World Cup: the FM-only filter
  excludes group-stage matches against associates, leaving the
  Super-8 / knockout stage "real cricket" subset.
- Teams > Match List for Australia: 22 matches (vs everyone) becomes
  16 matches (vs FM only). The per-discipline numbers shift.

## Scope of the change

`team_class` becomes the **9th FilterBar key**:

```ts
export const FILTER_KEYS = [
  'gender', 'team_type', 'tournament', 'season_from', 'season_to',
  'filter_team', 'filter_opponent', 'filter_venue',
  'team_class',           // NEW — international-only narrowing
] as const
```

Backend already has `AuxParams.team_class` (shipped 2026-04-27).
Migration path:
1. **Move** the field from `AuxParams` to `FilterBarParams`.
2. Update `filters.build()` to handle it inside the main clause
   builder (the body is identical — `if self.team_class == 'full_member': clauses.append(full_member_clause(...))`).
3. Drop `aux.team_class` references in `_league_aux` (no longer
   needed — when team_class is on filters, both team-side AND
   league-side queries get the clause for free via `filters.build()`).
4. Keep `aux.chip_team_class` for the asymmetric per-slot case
   (avg slot wants FM-only without imposing it on team data) —
   it's still useful for Compare-tab "Aus vs everyone" + "FM avg"
   workflow when team_class isn't set on the FilterBar.

## UI surface

### FilterBar widget

A new chip-toggle pill, **rendered only when `team_type === 'international'`** (full-member is an international classification — no-op for clubs). Sits between the Tournament dropdown and the Venue typeahead so the international-shape locality is obvious.

```
[Gender ▾] [Type ▾] [Tournament ▾] [📋 Full members only]  [📍 Venue …] [Season range …]
                                    ↑ when team_type=international
```

Toggle states:
- **off** (default): `team_class` not set, query string omits the param.
- **on**: `team_class=full_member`, query string carries it through.

The toggle is hidden when `team_type !== 'international'` (also when team_type is empty/all). When the user changes team_type away from international, any active `team_class` is auto-cleared (mirror of how `tournament` is auto-cleared when its scope changes).

### Status strip

`ScopeStatusStrip` gains a row entry for the active filter:

> `Show:` Full members only

Same line styling as the existing `series_type` show-pill.

### Scope-link URLs

`team_class` rides through every scope-link URL automatically because it's in `FILTER_KEYS`. No per-component changes needed in `TeamLink` / `PlayerLink` / `SeriesLink` — the loop in `scopeLinks.ts:111` does it.

### Per-tab semantic

| Tab / surface | What `team_class=full_member` does |
|---|---|
| Teams > Match List | Drops Aus's matches vs Scotland/Namibia. Aus 22→16, India 34→31, etc. |
| Teams > Compare | Both team-side AND avg-side data narrow to FM matches. Chip baseline auto-aligns (no `chip_team_class` hint needed). |
| Teams > vs Opponent | If both teams are FM, pair clause already implies FM. If one is associate, narrowing produces empty rows — handle as "no FM matches in scope". |
| Teams > Records | Highest totals etc. computed only over FM-vs-FM matches. |
| Series > Landing | Tournament tile counts narrow. Bilateral rivalry tiles hide pairs that involve associates (e.g. Scotland vs Ireland still shows since both are FM). |
| Series > Dossier | All inner stats narrow. ICC Men's T20 WC narrows from 55→fewer matches (Super-8s + knockouts). |
| Head-to-Head | Player-vs-player narrows to FM-side innings only. Team-vs-team narrows the rivalry to FM-vs-FM matches. |
| Batting / Bowling / Fielding leaders | Excludes runs/wickets accumulated against associates. |
| Matches list | Hides matches against associates. |
| Venues | Narrows venue stats to FM-vs-FM matches at that venue. |

## Backend changes (~8 small edits)

1. `api/filters.py::FilterBarParams.__init__` — add `team_class: Optional[str] = Query(None)`.
2. `api/filters.py::FilterBarParams.build()` — fold the `full_member_clause()` call (currently in the AuxParams branch) into the main clause builder.
3. `api/filters.py::AuxParams` — remove `team_class` field. Keep `chip_team_class` as-is.
4. `api/routers/teams.py::_league_aux` — drop the `aux.team_class` propagation step (filters.build() handles it now).
5. `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope` — change the rejection from `aux.team_class` to `filters.team_class`.
6. `api/routers/scope_averages.py` — no changes needed; it already passes filters through.
7. Reference endpoints (`/api/v1/tournaments`, `/api/v1/seasons`) — they iterate FilterBar fields when building their narrowing clauses; they auto-pick up `team_class` once it's in `FilterBarParams`.

## Frontend changes (~15 edits, biggest is the toggle widget)

1. `frontend/src/types.ts::FilterParams` — `team_class` already exists. No change needed; just stops being annotated as "per-slot only".
2. `frontend/src/components/scopeLinks.ts::FILTER_KEYS` — append `'team_class'`.
3. `frontend/src/components/FilterBar.tsx` — add the toggle pill (intl-only). Auto-clear on team_type change.
4. `frontend/src/components/ScopeStatusStrip.tsx` — render `Show: Full members only` when active.
5. `frontend/src/hooks/useFilters.ts` — the iterator over FILTER_KEYS picks it up automatically; no manual addition.
6. `frontend/src/components/teams/TeamCompareGrid.tsx::chipAlignmentFor` — when `team_class` is on the FilterBar primary scope, the chip already aligns by construction (filters.build covers both sides). The `chip_team_class` hint stays only for the asymmetric per-slot case (FilterBar off, slot avg has team_class on). No code change needed but add a comment explaining the dual mechanism.
7. `frontend/src/components/teams/AddCompareSlot.tsx` — when FilterBar already has `team_class=full_member`, the per-slot "+ Full-member avg" quick-pick becomes redundant. Hide it (the displayed avg col is already FM-only).
8. `frontend/src/components/teams/SlotScopeEditor.tsx` — keep the Class dropdown for the per-slot override use case (e.g. user wants their primary col without team_class but the avg col with it — uncommon but valid).
9. `frontend/src/components/teams/teamUtils.ts::scopeAvgLabel` — already handles `team_class` in the label string. No change.
10. `frontend/src/components/teams/SlotHeaderChip.tsx` — already renders "full members only" sub-line. No change.

## Test impact — the load-bearing list

### Tests that EXPECT NEW NUMBERS when team_class is on FilterBar

The integration test `tests/integration/compare_avg_chips.sh` and the
sanity test `tests/sanity/test_avg_baseline_numbers.py` both compute
expected numbers under the assumption that the team-side scope is
NOT filtered by team_class (Aus = 22 matches, India = 34 matches,
etc.). After this spec ships, when run with `team_class=full_member`
on the FilterBar, the numbers shift:

| Cell | Before (filterbar-no-team_class) | After (filterbar-team_class=fm) |
|---|---|---|
| Aus matches in Anchor A' | 22 | **16** |
| India matches in Anchor A' | 34 | **31** |
| Aus run rate | 9.91 (across all opponents) | **? need DB ground truth** |
| India run rate | 9.39 | **? need DB ground truth** |
| Avg col matches | 140 (already FM) | 140 (unchanged) |
| Avg col run rate | 8.50 | 8.50 (unchanged) |
| Aus chip delta | +16.6% | computed from new Aus RR / 8.50 |
| India chip delta | +10.5% | computed from new India RR / 8.50 |

The spec INCLUDES a sub-task to:

1. Compute new ground-truth numbers via the same DB-only subagent
   harness (no API source read).
2. Add a NEW test variant: `tests/integration/compare_avg_chips_fm_filterbar.sh`,
   anchored at the same URL but with `&team_class=full_member` in the
   FilterBar query string. This becomes the "filtered Aus" anchor.
3. Update `tests/sanity/test_avg_baseline_numbers.py` to add a third
   scope: `INTL_2024_25_FM` with team_class on the FilterBar; pin the
   new Aus 16-match figure + new RR.
4. Update `tests/sanity/test_chip_direction_invariant.py`'s scope
   matrix — add `aus_ind_men_intl_2024_2025_fm` so the invariant
   holds on the new path. The test's `make_filters(**kwargs)` already
   accepts `team_class` after the FilterBar promotion (it's a
   FilterBarParams field).

### Tests to ADD (new shell scripts)

Per the agent-browser eval pattern:

1. **`tests/integration/dom/teams_compare_intl_fm_filterbar.sh`** —
   anchor on `?team=Australia&...&team_class=full_member`. Asserts:
   - Aus column shows 16 matches (not 22).
   - Aus column run rate = ? (TBD, DB-grounded).
   - India column shows 31 matches.
   - Avg col displays Men's T20I full-member 2024-2025 avg = 140
     matches, RR 8.50.
   - Status strip shows `Show: Full members only`.
   - URL `team_class=full_member` survives navigation between tabs
     (proves it's a real FilterBar field, not a Compare-tab quirk).

2. **`tests/integration/dom/teams_compare_intl_fm_per_slot.sh`** —
   anchor on `?team=Australia&...&compare1_team_class=full_member`
   (per-slot, FilterBar OFF). Asserts:
   - Aus column shows 22 matches (full record).
   - Avg col displays FM-only 140 matches, RR 8.50.
   - Aus chip's scope_avg = 8.50 (chip alignment via chip_team_class hint).
   - This is the EXISTING `compare_avg_chips.sh` Anchor A'.

These two scripts together prove the dual mechanism: FilterBar
team_class narrows team data; per-slot team_class narrows only the
avg col + (via hint) the chip baseline. Both produce a chip ↔ avg
agreement, but with DIFFERENT team data. That distinction must be
testable.

3. **`tests/integration/dom/series_landing_intl_fm.sh`** — anchor on
   `/series?gender=male&team_type=international&team_class=full_member`.
   Asserts:
   - The bilateral-rivalry tiles for FM-vs-FM pairs show the
     correct narrowed match count.
   - ICC events tile for T20 WC narrows from 55→fewer matches.
   - Pairs involving associates (Scotland vs Namibia) are HIDDEN
     entirely (zero matches in scope — the existing
     filter-sensitive landing already drops zero-row entries).

4. **`tests/integration/dom/batting_leaders_intl_fm.sh`** — anchor
   on `/batting?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member`.
   Asserts:
   - The top-10 by runs in this scope.
   - Spot-check 3 player names — DB-grounded "who's #1 by total
     runs scored against FM-only attacks in 2024-25?".

### Regression tests to flip

`tests/regression/scope-averages/urls.txt` and
`tests/regression/teams/urls.txt` — every URL that runs against a
team-type=international scope without a tournament will produce
DIFFERENT responses when team_class is set. Specifically:

- `team_summary_india_men_intl` — diverges (now scoped to FM).
- `team_batting_summary_india` — diverges.
- `team_bowling_by_phase_india` — diverges.
- All scope-averages URLs pass team_class through; existing entries
  WITHOUT team_class stay stable.

Add NEW entries to both urls.txt files for the team_class=fm
variants:

```
NEW team_summary_india_men_intl_fm /api/v1/teams/India/summary?gender=male&team_type=international&team_class=full_member
NEW team_batting_summary_india_fm  /api/v1/teams/India/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member
... etc
```

Run `./tests/regression/run.sh scope-averages` to lock in the new
hashes. Then flip them to REG once stable in HEAD.

### Cross-cutting integration test

`tests/integration/cross_cutting_aux_filters.sh` already exists for
`series_type` end-to-end. Mirror that for `team_class`:

```
tests/integration/cross_cutting_team_class.sh
```

Asserts the FilterBar toggle:
1. URL pin: setting team_class=full_member writes to URL, reload
   preserves it.
2. Cross-tab persistence: navigate /teams → /series → /batting,
   team_class survives in URL.
3. Auto-clear on team_type change: switching to club clears
   team_class (mirror of how tournament clears).
4. Status strip render: `Show: Full members only` appears, COPY
   LINK preserves the param.
5. Hidden when team_type=club: the toggle pill DOM node should not
   render.
6. Numerical end-to-end: Aus matches drop 22→16, India 34→31 when
   team_class is toggled on. Asserts on a known tab (e.g.
   `/teams?team=Australia` Match List count).

## Migration sequence (3-commit rollout)

1. **Backend move** — `team_class` migrates from `AuxParams` to
   `FilterBarParams`. `_league_aux` drops the propagation step.
   `is_precomputed_scope` updated. Old `aux.team_class` request
   query param becomes a no-op (silent — accept and ignore for one
   release for backward-compat with existing per-slot URLs, log a
   deprecation note in the docstring).
2. **Frontend FilterBar widget + scope-link wiring** —
   `FILTER_KEYS` extended, FilterBar pill added, status strip
   updated, auto-clear on team_type change wired.
3. **Tests** — DB-grounded new ground truth, sanity tests
   updated, regression urls.txt entries flipped, integration
   shell scripts added, cross-cutting test added. Browser-agent
   walkthrough on each anchor URL.

Each commit independently passes type-check + sanity tests. Commit 3
is the only one that touches the regression suite — flip REG→NEW
in commit 3 BEFORE the final spec change, per the
`feedback_regression_before_shape` discipline.

## Open questions

- **Default state**: should team_class default to off (current
  proposal) or to "full members only" when team_type=international?
  Lean: off — too easy to confuse a user who expects all
  internationals; off matches the FilterBar's other defaults
  (no narrowing).
- **Composability with `series_type`**: a user can set
  `series_type=icc&team_class=full_member` to get "FM-only ICC
  events" (i.e. Super-8s + knockouts at WCs). The clauses are
  independent and AND together cleanly via `filters.build()` —
  no special handling.
- **`AuxParams.team_class` removal vs deprecation**: keeping it
  for backward-compat means a per-slot URL with
  `compare1_team_class=full_member` still works. Removing it
  forces all callers onto the FilterBar. Lean: deprecate with
  a 2-week notice (FilterBar is new, per-slot URLs may be
  bookmarked).
