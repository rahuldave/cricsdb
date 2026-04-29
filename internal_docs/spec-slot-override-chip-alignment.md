# Spec — Slot override expressiveness + chip alignment

> **Status:** build-ready. Architectural fix; affects every
> overridable axis on the Compare tab.

The Compare-tab per-slot override system has two real but
parked limitations from the v3 audit (2026-04-28). Both apply
to **every** overridable axis (`tournament` / `season_from` /
`season_to` / `filter_venue` / `series_type` / `team_class`),
not just team_class. This spec proposes a unified fix.

Today's `chip_team_class` aux hint (added 2026-04-27) is a
narrow point-fix for one axis in one direction. This spec
generalises it.

---

## 1. The two limitations

### 1.1 Override-to-empty URL serialization

A slot can override a value to a different value. It cannot
override to **empty/all-time/any** while the FilterBar still has
a value set.

**Concrete scenario.** FilterBar has `season=2025` (because the
user is looking at RCB 2025). They want column 2 to be "RCB
all-time" (no season filter at all, lifetime stats for
comparison). Today they can't write that URL:

- `compare2_season_from=` (empty) → URL machinery deletes the
  param → reader sees "no override" → slot inherits primary's
  2025.
- `compare2_season_from=anything-but-empty` overrides to a
  different season, but still narrowing.

There's no way to express "explicit empty, do not inherit." Same
limitation applies to:
- `compare2_tournament=` — can't explicitly clear when primary
  has tournament set.
- `compare2_filter_venue=` — same.
- `compare2_series_type=` — same.
- `compare2_team_class=` — same (post-v3, when FilterBar fm is
  on, can't set the avg slot to "show unbounded baseline
  regardless").

### 1.2 Chip alignment under bidirectional override

Each chip on a team column shows `value vs. scope_avg → delta_pct`.
The `scope_avg` should match what the avg COLUMN displays —
otherwise the chip says "Aus is +12% above league" while the
league number visible one column over reads something different.

Today the system has a **one-way** alignment hint
(`chip_team_class`): when an avg slot is **narrower** than primary
(e.g. primary unbounded, avg slot FM-only), the hint flows through
and the chip's baseline narrows to match.

The reverse case doesn't work. If primary is on `tournament=IPL`
and you override the avg slot to `tournament=` (broader, all
clubs), the chip on column 1 still uses IPL's narrower league as
its baseline. The avg column shows "all-club avg = X", the chip's
scope_avg is "IPL avg = Y", and the user sees disagreement.

**Same shape applies to `season_from` / `tournament` / `filter_venue`
/ `series_type` overrides** — narrower-direction hints don't
generalise to broader-direction.

---

## 2. Why these matter

Both limitations bite on a real workflow: **"compare team's
narrowed-scope view to a broader baseline"** (e.g. RCB 2025 vs
RCB all-time, or Aus FM-pool vs unbounded league).

Today's UI either silently drops the user's intent (override-to-
empty silently inherits) or shows a chip that contradicts the avg
col (broaden-direction misalignment).

Fixing makes the override system **symmetric** — narrowing and
broadening overrides both work the same way, and chip baselines
always align to what's displayed.

---

## 3. Mental model — current vs proposed

### Current (broken)

```
FilterBar = primary scope
    ↓
Per-slot override (compareN_<key>=value):
    if value is non-empty → slot[key] = value
    if param missing or value is empty → slot[key] = primary[key]   ← can't escape here
```

Chip baseline is computed from REQUEST filters (the team's
filters, not the avg slot's). Hint mechanism (`chip_team_class`)
copies one specific narrowing forward. No general way to push
arbitrary scope.

### Proposed

```
FilterBar = primary scope
    ↓
Per-slot override (compareN_<key>=value):
    if value == '__any__' → slot[key] = null (explicit empty)
    if value is non-empty → slot[key] = value
    if param missing → slot[key] = primary[key]   (default flow)
```

Chip baseline is computed from the AVG SLOT'S RESOLVED SCOPE.
When team col fetches `_compute_batting_summary`, it passes a new
`baseline_scope` parameter (or filters object) that the
league-side aggregate uses. The team-side aggregates still use
the team's scope.

---

## 4. Surface changes

### 4.1 URL grammar — `__any__` sentinel

**Sentinel value.** `compareN_<key>=__any__` decodes as "explicit
empty." Encoded literally in the URL as `__any__` (URL-safe).

**Read site** (`useCompareSlots`):

```ts
function readSlot(params, n, primary): SlotState | null {
  ...
  for (const k of OVERRIDABLE_SLOT_KEYS) {
    const v = params.get(`compare${n}_${k}`)
    if (v === '__any__') {
      overrides[k] = ''      // sentinel for explicit-empty
      scope[k] = undefined   // no narrowing
    } else if (v != null && v !== '') {
      overrides[k] = v
      scope[k] = v
    }
    // else: param missing → default inheritance from primary, no override.
  }
  ...
}
```

**Write site** (`SlotScopeEditor.handleApply`):

```ts
if (cmp(seasonFrom, primary.season_from)) {
  o.season_from = seasonFrom || '__any__'    // explicit-empty when user cleared
}
```

A user clearing a field that primary HAS narrowed gets `__any__`.
A user clearing a field that primary doesn't narrow gets nothing
(no override needed).

**Backend.** `__any__` arrives as a query param. Backend should
treat it as "no narrowing" (same as not present). Implementation:
the API filter helpers check `if v and v != '__any__'` instead
of `if v`. Touch every router that consumes per-slot URL params
(today: only `_team_innings_clause` etc. via the FilterParams
flow on team-side requests). Detail in §5.2.

### 4.2 Chip baseline — slot-resolved scope

Today `_compute_batting_summary` uses `filters` for both team
and league sides. League side calls `_league_aux(team, aux,
filters)` to synthesize narrowings.

After this spec, the team request carries an explicit
`baseline_scope` (a FilterParams-shaped subset, possibly via a
new aux field `chip_baseline_scope_json`). Frontend computes the
peer avg slot's resolved scope and serializes it. League-side
aggregate uses `baseline_scope` filters instead of synthesizing
from `team` + `aux`.

**Data flow.**

```
Frontend TeamCompareGrid:
    avg_slot_scope = avgSlot ? avgSlot.scope : primaryFilters
    chipAlign = encodeScope(avg_slot_scope)    // base64-JSON

Frontend fetchSlot(team_slot):
    return getTeamProfile(team, {...slot.scope, chip_baseline: chipAlign})

Backend team_summary:
    aux.chip_baseline_scope = parse(chipAlign)
    league_filters, league_aux = _league_aux(team, aux, filters)
    # _league_aux now: if aux.chip_baseline_scope, use it as
    # league_filters. Otherwise fall back to current logic.
    s = await _batting_aggregates(None, league_filters, league_aux)
```

This generalises `chip_team_class` — that hint becomes a special
case ("just narrow team_class on league filters") of the broader
"use this entire scope on league filters" mechanism.

`chip_team_class` aux field can stay as a backwards-compat
shortcut for clients that haven't migrated, OR be removed when
the new mechanism is live.

### 4.3 Frontend — `SlotScopeEditor` UX for explicit-empty

The editor today shows a "Reset to primary" button that clears
all overrides. After this spec, also let the user **clear an
INDIVIDUAL field** to "(any)". Pattern: each field gains a small
✕ button next to the dropdown that toggles to `__any__`. Or: the
dropdown gains an "(any — show all)" option above the inherited
default.

UI mockup:
```
Tournament  [ Indian Premier League ▾ ]      ← inherited from primary
Tournament  [ (any — show all)        ▾ ] ← clicked, slot now has team_class=__any__
```

### 4.4 ScopeStatusStrip + SlotHeaderChip

`SlotHeaderChip` (the per-column sub-line under the team name in
Compare) needs to render `__any__` overrides as
"any season" / "any tournament" / "all teams" — visible to user
that this is an explicit broaden, not an inherited default.

ScopeStatusStrip is unchanged (it shows primary FilterBar state
only — slot-level overrides don't surface there).

---

## 5. Backend changes

### 5.1 `api/filters.py::FilterBarParams.build()`

Treat `__any__` as no-narrowing. Touch every clause that consumes
a FilterParams field — change `if self.tournament:` to
`if self.tournament and self.tournament != '__any__'`. Same for
`season_from`, `season_to`, `venue`, `team`, `opponent`,
`team_class`, `series_type`.

Edits: ~10 lines, one per field.

### 5.2 `api/routers/teams.py::_league_aux`

Refactor to take an explicit `baseline_scope` (a
FilterBarParams object) when the request carries one. When set,
return that as the league-side filters. Otherwise current logic.

```python
def _league_aux(team, aux, filters):
    ...
    if aux.chip_baseline_scope_json:
        league_filters = parse_filter_params(aux.chip_baseline_scope_json)
        # scope_to_team synthesis still applies to league_aux
        return league_filters, ...
    # Else: existing chip_team_class + scope_to_team path.
```

Decision: keep `chip_team_class` as a back-compat optional
shortcut for the next 1-2 releases, with a deprecation note
in the field's docstring. Remove later.

### 5.3 Hand-rolled filter helpers

`tournaments.py::_build_filter_clauses`, `reference.py::_reference_clauses`,
`reference.py::list_teams` — each gets the `__any__` skip per
field. Mechanical pass.

---

## 6. Frontend changes

### 6.1 `useCompareSlots.ts::readSlot`

Decode `__any__` per §4.1.

### 6.2 `useUrlState.ts::useSetUrlParams`

Currently deletes a key on falsy value. Add an exception: if the
caller writes `__any__`, keep the literal string. Implementation
might be: rename the contract — caller writes `__any__` for
explicit-empty, empty string for "delete from URL." Distinct
semantics.

### 6.3 `SlotScopeEditor.tsx`

UI for explicit-empty per §4.3. Determine whether to use the
✕-button pattern or an "(any)" dropdown option per axis.

`handleApply` writes `__any__` when the user cleared a field
that primary had narrowed.

### 6.4 `TeamCompareGrid.tsx::chipAlignmentFor`

Replace the narrow `chip_team_class`-only logic with serializing
the avg slot's full scope:

```ts
function chipAlignmentFor(slots: CompareSlots): { chip_baseline?: string } {
  const avg = slots.slot1?.kind === 'avg' ? slots.slot1
            : slots.slot2?.kind === 'avg' ? slots.slot2 : null
  if (!avg) return {}
  return { chip_baseline: btoa(JSON.stringify(avg.scope)) }
}
```

Or use a more compact serialization (base64-JSON is fine for a
URL param; ~150 bytes typical).

---

## 7. SQL + test plan

### 7.1 Anchor numbers (5+ scenarios)

Pre-flight subagent derives ground truth for each scenario:

- **Scenario A**: FilterBar tournament=IPL + season=2025; avg slot
  override `compare1_tournament=__any__`. Expectation: avg col
  reads "all-club average" matches a much broader pool.
- **Scenario B**: FilterBar season=2024-2025 + team_class=fm;
  avg slot override `compare1_team_class=__any__`. Expectation:
  avg col reads "International average" (unbounded) = 17.4 per-team.
- **Scenario C**: Compare RCB 2025 (primary) vs RCB all-time
  (compare1=Royal Challengers Bengaluru + override season). RCB
  all-time match count visible.
- **Scenario D**: Chip alignment under override-to-broader. Avg
  col displayed value === team col chip's scope_avg.
- **Scenario E**: Round-trip — open editor with `__any__` override
  active; the field reads "(any)"; "Reset to primary" restores
  inheritance.

Save anchors to `internal_docs/slot-override-anchor-numbers.md`.

### 7.2 Sanity test

`tests/sanity/test_slot_override_alignment.py` — for each
scenario, hit team and avg endpoints and assert
`team.chip.scope_avg == avg.displayed_avg` for at least 2
metrics per scenario.

### 7.3 Regression

The `__any__` sentinel arrival in URLs is a NEW behaviour. NEW
URLs can be added with explicit `__any__` overrides; existing
REG URLs without `__any__` are byte-identical (no shape change
on those).

### 7.4 Integration

Browser test: Compare tab on /teams?team=RCB&...&season_from=2025
&season_to=2025 — open slot 1's ✎ editor, click "(any)" on
season, Apply. URL gains `compare1_season_from=__any__`,
`compare1_season_to=__any__`. Slot 1's match count shifts to
RCB all-time.

`tests/integration/slot_override_any.sh` (NEW) — anchor-driven.

---

## 8. Migration sequence

5 commits:

1. **Backend `__any__` decoding.** `FilterBarParams.build()` +
   hand-rolled helpers + `_league_aux` baseline_scope plumbing.
   Existing URLs unchanged (no `__any__` in any current URL).
2. **Frontend `__any__` reader/writer.** `useCompareSlots`
   decode; `useUrlState` exception. `SlotScopeEditor` UI for
   explicit-empty. `TeamCompareGrid::chipAlignmentFor`
   serializes avg slot's full scope.
3. **Backend chip-baseline mechanism.** `_league_aux` honors
   `aux.chip_baseline_scope` when set. Falls back to existing
   chip_team_class + scope_to_team path otherwise. Update
   `_compute_batting_summary` etc. to pass through.
4. **Tests.** Sanity (5 scenarios) + integration (1 script)
   + regression URL additions.
5. **Deprecation.** Add a deprecation comment to
   `aux.chip_team_class` pointing to `chip_baseline_scope`.
   Remove `chip_team_class` 1-2 releases later in a separate
   commit.

Estimated effort: ~16h. The mechanism is general (so wider
than v3 or per-team), the URL grammar change touches multiple
read/write sites, and the chip baseline plumbing crosses 4-5
endpoints.

Risk: medium-high. The `__any__` decoding affects every
overridable axis at every endpoint — easy to miss a call site.
The chip baseline plumbing changes a load-bearing helper
(`_league_aux`) that 7 call sites depend on. Pre-flight should
include a regression sweep across all 11 suites.

---

## 9. Out of scope

- **Override-to-empty in the FilterBar itself.** The FilterBar
  is the user's primary source of truth — clearing a field there
  always means "don't narrow." No `__any__` needed at FilterBar
  level. Only slots need the sentinel.
- **Multi-slot transitive override** (slot 2 inheriting from
  slot 1 instead of primary). Today slot 2 inherits from
  primary; this spec preserves that. Transitive inheritance
  would be a separate feature.
- **Custom chip baselines without an avg slot.** Today chip
  baselines align to the avg slot. If neither compare slot is
  an avg, the chip baseline falls back to the team's own scope
  (existing behaviour). Out of scope here.

---

## 10. Why this is the architectural fix

The narrow `chip_team_class` hint (2026-04-27) was a point-fix
for ONE limitation in ONE direction. This spec generalises it
so the override system is symmetric and the chip math is
correct under any combination of primary + slot scopes.

After this lands, future overridable-axis additions (the next
`spec-filterbar-X.md`) can rely on:
- The URL grammar (with `__any__`) handles their axis without
  per-axis hint code.
- The chip baseline aligns automatically when used.

This eliminates the recurring "we shipped a new FilterBar field
but missed wiring the chip alignment" failure mode.

---

## 11. Pre-flight checklist

1. Green run all existing tests + spec drift check.
2. Subagent traces every consumer of every overridable URL param
   per axis. Document the fan-out — there will be more call
   sites than v3's 7.
3. Decide UI pattern for explicit-empty (✕ button vs dropdown
   "(any)" option) — recommend mocking both and getting user
   feedback.
4. Decide on `chip_baseline_scope_json` encoding (base64-JSON
   recommended; alternatives: query param per field
   `&compareN_baseline_<key>=...`, but that explodes URL length).

---

*Spec written 2026-04-28 alongside team_class v3 + per-team
transform. Pick up next session per §11 — recommend doing
`spec-filterbar-series-type.md` first since it's mostly mechanical,
then this spec second since it unblocks broader future work.*
