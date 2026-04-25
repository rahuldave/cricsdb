# Spec: Teams Compare — Scoped Slots (Per-Column Filter Override)

Status: build-ready.
Depends on: `spec-team-compare-average.md` (the avg-column + envelope
infrastructure this builds on top of). All Phases 1, 2A, 2B, 3 of
that spec are shipped.

## Overview

Teams Compare today renders up to 3 team columns + an optional
"League average" column, all 4 sharing the same FilterBar scope. The
chips on each cell compare against the same in-scope league baseline.
This is sufficient for "MI vs CSK in IPL 2024" but blocks the
genuinely interesting class of questions:

- **Temporal compare**: "RCB IPL 2024 vs RCB IPL 2025 — what changed?"
  (Same team, different season range. Why did they not win in 2024?)
- **Cross-event compare**: "Australia bilaterals vs Australia at the
  T20 World Cup" (Same team, different tournament + series_type.)
- **Trajectory compare against a moving baseline**: "MI IPL 2024 vs
  IPL 2025 league average" (Same team's snapshot vs where the
  league is heading next year — gauges whether the team is
  *structurally* keeping up.)
- **Mixed**: "RCB 2024 + RCB 2025 + IPL 2025 league avg" — three
  columns, each with its own scope, telling the full story of a
  team's evolution against a moving baseline.

This spec makes the compare grid's columns independently scoped:
each column is a "slot" with its own `(kind, entity, scope)` tuple.
gender + team_type are bound across all slots from the primary
(comparing men's vs women's, or club vs international, is a category
error in this UI). Tournament + season_from + season_to +
filter_venue + series_type can be overridden per-slot.

The cap drops to **3 columns total** (primary + 2 compare slots)
because adding a per-column scope-override panel widens each column's
header — 4 columns crowd a wide laptop screen.

## Scope

**In scope:**

- 3-column cap: primary + up to 2 compare slots.
- Each compare slot is a `team` (named team) or an `avg` (league
  baseline) with its own scope.
- gender + team_type bound across slots; primary's values always
  apply.
- Per-slot scope override on tournament, season_from, season_to,
  filter_venue, series_type (5 fields).
- New URL params: `compare1`, `compare2`, `compareN_<filter>` for
  N ∈ {1, 2} and filter ∈ the 5 overridable fields.
- Legacy URL migration: `compare=A,B` + `avg_slot=1` → new params,
  drop the now-impossible 4-column case.
- Picker: unified "+ Add column" affordance that lets the user pick
  team OR league-avg AND optionally override scope at add-time.
- Per-slot scope editor: inline panel reachable from a column's
  header so the user can adjust scope after adding.
- Column header decoration: when a slot's scope differs from the
  primary, surface the diff under the column name as a one-line
  scope chip (e.g. `RCB · IPL 2025`).
- Legend update: "in the active FilterBar scope" → "in each
  column's scope".

**Not in scope:**

- Cross-gender or cross-team_type comparison. The few users who
  want it can use two browser tabs.
- More than 3 columns. The width budget on a 13" laptop is the
  bottleneck.
- Backend changes. Zero new endpoints, zero new SQL, zero envelope
  changes. The endpoints already accept `FilterParams` per-request
  and compute their own scope_avg from whatever scope each call
  carries — chips on each column will naturally re-baseline against
  that column's scope.
- "Save scoped compare as preset". Future enhancement — captured in
  open questions.
- Comparing two avg slots scoped differently in 2-column mode (the
  2 compare slots can both be avgs with different scopes — that's
  free out of the box, no extra UI work needed).

## UX

### The 3-column model

```
┌─ Primary ────────┬─ Compare slot 1 ─┬─ Compare slot 2 ─┐
│ Team chosen via  │ Team or avg,     │ Team or avg,     │
│ FilterBar above. │ default = same   │ default = same   │
│ Filters bind     │ scope as primary,│ scope as primary,│
│ everything.      │ overridable per  │ overridable per  │
│                  │ slot.            │ slot.            │
│                  │ ✕ removes.       │ ✕ removes.       │
└──────────────────┴──────────────────┴──────────────────┘
                  + Add column ▾
```

A "slot" is a compact, self-describing column with:

- A `kind`: `'team'` or `'avg'`.
- An `entity`: team name (for `kind='team'`) or null (for `'avg'`).
- A `scope`: the 5 overridable filters, defaulting to inherited
  from primary.
- A header that surfaces all of the above + an edit affordance.

The primary is conceptually slot 0 — same shape, just sourced from
the FilterBar above instead of `compareN_*` params.

### Default first-load (auto-fill same-scope avg)

Landing on `/teams?team=RCB&tab=Compare` with no `compare1` /
`compare2` params: **auto-fill `compare1=__avg__`** on mount so the
user immediately sees primary + same-scope league average — two
columns visible, the most-asked comparison rendered without any
clicks.

Implementation discipline:

- Auto-fill **fires once per mount, gated by a `useRef`**. After
  the first render, user state is law: clicking ✕ on the auto-
  filled avg slot does NOT bring it back on the next render. Only
  a fresh page load with no `compareN_*` params at all triggers the
  auto-fill again.
- The first-render URL update uses `replace: true` so the back
  button doesn't accumulate auto-fill steps. Share URLs that
  someone copies after first-load capture the avg slot explicitly.
- Aus men's no-tournament case (and analogous): the auto-filled
  avg's scope inherits primary's bound axes (`gender=male`,
  `team_type=international`) plus whatever else primary has set.
  `scopeAvgLabel` renders "Men's T20I avg" for that case — already
  correct today.

The picker only shows up when the user wants to ADD a 3rd column or
REPLACE a removed slot. Default-mode users see 2 columns and may
never click the picker.

### Adding a slot

The picker is one logical UI with **quick-picks above + custom
form below** so casual users get one-click value AND advanced users
have full freedom:

```
+ Add a column ▾

  ┌─────────────────────────────────────────┐
  │  Quick add (1 click):                   │
  │   » League avg in current scope         │
  │   » Same team, previous season          │
  │   » Different team — current scope      │
  │   » Same team, all-time                 │
  │                                         │
  │  ─── or build a custom column ───       │
  │                                         │
  │  Type:    ◉ Team   ○ League avg         │
  │  Team:    [search teams …]              │
  │  Scope (defaults inherit from primary): │
  │    Tournament:  [Indian Premier L…]     │
  │    Season:      [ 2024 ] – [ 2024 ]     │
  │    Venue:       [—]                     │
  │    Series type: [—]                     │
  │  [ Reset scope ]              [ Add ]   │
  └─────────────────────────────────────────┘
```

Quick-picks fire on a single click — the URL writes the slot's
params directly, the column appears, the picker closes. The user
sees what changed (new column rendered with appropriate scope
chip below the team name) and learns the affordance.

The custom panel is the escape hatch — type toggle (team/avg) +
the same 5-field scope editor used at slot-edit time. Defaults
inherit from primary; user overrides what they want.

#### Quick-pick semantics

| Quick-pick | Slot kind | Slot entity | Scope override | Hidden when |
|---|---|---|---|---|
| **League avg in current scope** | `avg` | null | none (inherit) | already an avg slot with same scope present |
| **Same team, previous season** | `team` | `<primary>` | `season_from = season_to = <previous>` (see below) | primary has no season set, OR no preceding season exists in scope |
| **Different team — current scope** | `team` | (opens team picker on click) | none | both compare slots are filled |
| **Same team, all-time** | `team` | `<primary>` | clears tournament + season_from + season_to | primary has neither tournament nor season set (no diff) |

**Definition of "previous season"** — the season immediately
before `primary.season_from` in the **bound scope's seasons list**:

```ts
// On click of "Same team, previous season":
const seasons = await getSeasons({
  team: primary.team,
  gender: primary.gender,
  team_type: primary.team_type,
  tournament: primary.tournament,  // empty for no-tournament internationals
})
// seasons is sorted ascending, e.g. ["2016", "2017", …, "2024"]
const idx = seasons.indexOf(primary.season_from)
const prev = idx > 0 ? seasons[idx - 1] : null
if (prev == null) return  // no previous; quick-pick should have been hidden
setUrlParams({
  compare1: primary.team,
  compare1_season_from: prev,
  compare1_season_to: prev,
})
```

This handles all team types uniformly without special cases:

- **RCB IPL 2024** → seasons `[…, 2022, 2023, 2024]` → previous =
  `2023`. ✓
- **India men's T20I, no tournament, primary 2024** → seasons
  `[…, 2022, 2023, 2024, 2025]` → previous = `2023`. ✓ (calendar-
  year continuity for unbound-tournament internationals.)
- **Australia at T20 World Cup, primary 2024** → seasons
  `[…, 2016, 2021, 2022, 2024]` (no 2023 — no WC that year) →
  previous = `2022`. ✓ (the actual previous World Cup, NOT the
  calendar-prior year.)
- **Cricsheet's `2024/25` BBL format** → the `/seasons` endpoint
  returns these as strings; `indexOf` on the string works. ✓
- **Primary has no season filter** → `primary.season_from` is null,
  the quick-pick is hidden. ✓
- **Associate team (Nepal, USA) with sparse data** → the seasons
  list returns only seasons where they actually have matches; if
  the previous season exists, the lookup works; if not, hidden.

The algorithm doesn't care about tournament binding, calendar
continuity, or string format — it walks the actual seasons list
backward by one. Pure index arithmetic on whatever the scope-
narrowing endpoint already returns.

#### Validation gates (unchanged from today)

When `kind=team` and the user hasn't touched scope: candidate's
in-scope match-count is probed against the inherited scope. Zero
matches in scope → refuse with the existing "no matches in current
filter scope" message. (Matches today's `AddTeamComparePicker`
gate.)

When `kind=team` and the user HAS overridden scope: probe against
the overridden scope.

When `kind=avg`: no probe needed; "league avg" always exists in
scope (worst case zero matches → empty column, but the avg slot
itself is valid).

### Editing an existing slot's scope

Each compare-slot column header gets a small pencil icon next to
the ✕:

```
[ ✎ ] [ ✕ ]
```

Click ✎ → an inline panel slides down beneath the column header
(or a popover anchored to the icon) showing the same 5-field scope
editor as add-time, pre-filled with the slot's current values:

- Edit one or more fields → "Apply" → URL updates with the
  appropriate `compareN_*` params, refetch fires.
- "Reset to primary" → clears every `compareN_*` param for that
  slot, slot inherits primary again.

### Column header decoration

When a slot's scope matches primary entirely → just the team / avg
name in the header (today's display).

When at least one scope field differs → render a small italic
sub-line below the team name showing the diff. Format rules:

- Tournament differs: include `tournament` (full name).
- Season differs: include `<season_from>` or `<season_from>-<season_to>`.
- Venue differs: include `@ <venue>`.
- Series_type differs: include `· bilaterals` / `· tournaments`.

Examples:

- Same team, different season: `RCB · 2025`
- Different tournament: `Australia · ICC Men's T20 World Cup`
- Different venue: `MI · @ Wankhede`
- Multiple differences combined: `RCB · IPL 2025 · @ Chinnaswamy`

The chip is small (`fontSize: 0.85em`, italic, opacity ~0.7) so it
doesn't compete with the team name's visual weight.

### Legend update

The chip-explanation legend currently says:

> ↑/↓ ±X% = team value vs league baseline in the **active FilterBar
> scope** …

With per-slot scope, this is technically inaccurate when the user
overrides a slot. Update to:

> ↑/↓ ±X% = team value vs league baseline **in each column's
> scope** …

The tooltip already explains scope inheritance; expand it slightly
to mention per-column overrides:

> Each chip is the team's value vs the league baseline computed for
> that COLUMN's scope. Slots that don't override scope inherit from
> the FilterBar above; slots that do (look for the scope chip below
> the team name) baseline against their own narrower scope.

### Sample share URLs

```
# Default mode — RCB IPL 2024 + same-scope avg (today's default):
/teams?team=RCB&tab=Compare&tournament=Indian+Premier+League
       &season_from=2024&season_to=2024&team_type=club&gender=male
       &compare1=__avg__

# RCB 2024 vs RCB 2025:
/teams?team=RCB&tab=Compare&tournament=Indian+Premier+League
       &season_from=2024&season_to=2024&team_type=club&gender=male
       &compare1=RCB
       &compare1_season_from=2025&compare1_season_to=2025

# RCB 2024 + RCB 2025 + IPL 2025 league avg:
/teams?team=RCB&tab=Compare&tournament=Indian+Premier+League
       &season_from=2024&season_to=2024&team_type=club&gender=male
       &compare1=RCB
       &compare1_season_from=2025&compare1_season_to=2025
       &compare2=__avg__
       &compare2_season_from=2025&compare2_season_to=2025

# Australia all matches vs Australia at T20 World Cup:
/teams?team=Australia&tab=Compare&team_type=international&gender=male
       &compare1=Australia
       &compare1_tournament=ICC+Men%27s+T20+World+Cup
```

## URL state

### New params

| Param | Values | Meaning |
|---|---|---|
| `compare1` | team name OR `__avg__` | Slot 1 entity. Absent = slot empty. |
| `compare2` | team name OR `__avg__` | Slot 2 entity. Absent = slot empty. |
| `compare1_tournament` | string | Slot 1 tournament override. Absent = inherit. |
| `compare1_season_from` | year | Slot 1 season-from override. |
| `compare1_season_to` | year | Slot 1 season-to override. |
| `compare1_filter_venue` | canonical venue | Slot 1 venue override. |
| `compare1_series_type` | `bilateral_only`/`tournament_only`/`all` | Slot 1 series_type override. |
| (`compare2_*` mirror the above for slot 2.) | | |

### Resolution rule

For each compare slot N ∈ {1, 2}, the slot's effective scope is
computed field-by-field:

```ts
slot[N].scope.tournament = url.compareN_tournament ?? primary.tournament
slot[N].scope.season_from = url.compareN_season_from ?? primary.season_from
…  // same for season_to, filter_venue, series_type
slot[N].scope.gender = primary.gender         // bound, no override
slot[N].scope.team_type = primary.team_type   // bound, no override
```

The bound fields (`gender`, `team_type`) come from primary
unconditionally; there's no `compareN_gender` URL param.

### Slot contiguity normalization

Share URLs in the wild may carry `compare2=X` without `compare1`
(e.g. user removed slot 1 but the URL captured slot 2 first). On
mount, normalize so the leftmost compare slot is always slot 1:

- If `compare1` is empty/absent AND `compare2` is set → rewrite
  `compare2_*` keys to `compare1_*`, drop `compare2*`. Use
  `replace: true` so back button stays clean.
- If both `compare1` and `compare2` are set → no normalization
  (already contiguous).
- If both empty → auto-fill triggers (default first-load).

This is part of the same self-correcting `useEffect` that handles
legacy migration; both run on mount.

### Legacy migration

Existing share URLs use `compare=A,B` (CSV) + `avg_slot=1`. A
self-correcting useEffect in `Teams.tsx` reads these on mount, maps
them to the new params, and rewrites the URL with `replace: true`:

```
?team=RCB&compare=CSK             → ?team=RCB&compare1=CSK
?team=RCB&compare=CSK,MI          → ?team=RCB&compare1=CSK&compare2=MI
?team=RCB&avg_slot=1              → ?team=RCB&compare1=__avg__
?team=RCB&compare=CSK&avg_slot=1  → ?team=RCB&compare1=CSK&compare2=__avg__
?team=RCB&compare=CSK,MI&avg_slot=1
                                  → ?team=RCB&compare1=CSK&compare2=MI
                                    (drops avg — would be 4 cols, exceeds cap)
```

The 3-cap drop case logs a one-time `console.warn` so we can spot
it in the wild.

### `useFilters` and `useCompareSlots`

`useFilters()` (existing) keeps returning the FilterBar's primary
filter state.

New `useCompareSlots(): { slot1: SlotState | null, slot2: SlotState | null, … }`
returns the resolved per-slot state with the following shape:

```ts
interface SlotState {
  kind: 'team' | 'avg'
  entity: string | null      // team name when kind='team', null for avg
  scope: ResolvedScope        // 7 fields (5 overridable + 2 bound)
  overrides: PartialScope     // which of the 5 fields are overridden
}
```

`overrides` is the inverse — what the user actually set in the URL,
so the column-header decoration knows which fields differ from
primary.

Setters for each slot's entity / scope-field, all atomic via
`useSetUrlParams()` (no two-write race conditions).

## Frontend changes

### Components — refactor

- **`TeamCompareGrid.tsx`** — drop `t2` slot (cap reduction).
  Iterate over `[primary, slot1, slot2]`, render each column. Each
  column gets its own useFetch with the resolved per-slot scope.
- **`AddTeamComparePicker.tsx`** → become **`AddCompareSlot.tsx`**
  — single picker with type toggle (team / avg) + optional scope
  override panel.
- **`CompareColumn` + `AvgCompareColumn`** (today: two
  components in `TeamCompareGrid.tsx`) → **single
  `CompareSlotColumn`** that handles both kinds based on
  `slot.kind`.
- **`TeamSummaryRow.tsx`** + **`AvgSummaryRow.tsx`** — unchanged
  internally, but the column wrapper passes per-slot filters down
  for use in deep-link URLs (the "→ Open Batting tab" link should
  carry the SLOT's scope, not primary's).

### Components — new

- **`SlotScopeEditor.tsx`** — inline panel showing the 5
  overridable filters, with form bindings, "Apply" + "Reset to
  primary" actions. Used both at add-time (inside
  `AddCompareSlot`) and at edit-time (anchored to a column's ✎
  icon). Reusable.
- **`SlotHeaderChip.tsx`** — the small italic line under a team
  name showing the slot's scope diff. Reads the slot's `overrides`
  and emits the formatted one-liner.

### Hooks — new

- **`useCompareSlots()`** — described above. Replaces the existing
  ad-hoc parsing of `compare=A,B` + `avg_slot=1`.
- **`useScopeOverrides(n: 1 | 2)`** — narrower hook used inside
  `SlotScopeEditor` for binding form fields to URL params.

### Plumbing

- **`api.ts`**: `getTeamProfile` and `getScopeAverageProfile`
  already accept arbitrary `FilterParams`. No changes — they're
  called per-slot with the slot's resolved scope.
- **Teams.tsx** legacy-migration useEffect (described in URL state).
- **`teamUtils.ts`**: `scopeAvgLabel(scope)` already exists for the
  avg column header. Reused for slot header chips with one
  extension — accept a "diff against primary" option to render
  only the differing fields.

## Backend

Zero changes. Stress-tested by reasoning:

- The 5 compare endpoints + 11 scope-averages endpoints all take
  `FilterParams` via `Depends` per-request.
- Each column's fetch is independent — the frontend builds the
  filter dict from the slot's resolved scope and calls the same
  endpoint.
- Envelope's `scope_avg` is computed PER REQUEST against whatever
  scope the request carries. No global state, no cross-request
  coupling. The chip on slot 1's "RCB 2025" cell will naturally
  show the delta vs IPL 2025 league avg, because slot 1's request
  was scoped to 2025.

## Tests

### Integration

`tests/integration/team-compare-average.sh` is updated:

- Existing 16 asserts continue to pass after URL migration (the
  `avg_slot=1` legacy path now maps to `compare1=__avg__` via the
  self-correcting effect; the test's URLs work either way).
- Add club-team asserts for scoped-slot behaviour:
  - Default first-load: navigate to `/teams?team=RCB&tab=Compare`
    with no compare params; verify URL self-corrects to
    `compare1=__avg__` AND grid renders with 2 columns (primary +
    avg).
  - ✕ the auto-filled avg slot; reload page; verify URL re-auto-
    fills (fresh load is a fresh mount). ✕ again WITHOUT reload;
    verify it stays gone (useRef gate holds within session).
  - Same-team scoped slot via the "Same team, previous season"
    quick-pick (RCB 2024 → RCB 2023); verify the column header
    shows "RCB · 2023" diff chip; verify chips on the slot column
    compare against IPL 2023 avg (number-spot-check).
  - Edit a slot's scope via the ✎ panel; verify URL updates with
    `compareN_*` params.
  - Reset a slot to primary; verify `compareN_*` params drop.
  - 3-column scenario: primary + RCB 2025 + IPL 2025 avg; verify
    all three render.
  - Legacy URL: `?team=RCB&compare=CSK&avg_slot=1` → verify
    self-correcting redirect lands at
    `?team=RCB&compare1=CSK&compare2=__avg__`.
  - Slot contiguity: `?team=RCB&compare2=CSK` → verify URL
    rewrites to `?team=RCB&compare1=CSK`.

#### International team scenarios (failure-mode hunting)

Internationals exercise edge cases that club teams hide because
international "season" semantics aren't tournament-bound. Test
each in agent-browser:

- **India men's T20I, no tournament, primary 2024** → "Same team,
  previous season" quick-pick → expect compare slot resolves to
  India 2023 (calendar-prior year). Chips compute against
  international men's T20I 2023 avg.
- **Australia at T20 World Cup, primary 2024** → "Same team,
  previous season" → expect 2022 (the actual previous WC, NOT
  2023 which doesn't exist for that tournament). This is the load-
  bearing test for the lookup-against-scoped-seasons-list
  algorithm; calendar-prior-year would give the wrong answer
  here.
- **New Zealand women's, no tournament/season set** → "Same team,
  previous season" link should be **hidden** (no season to be
  previous to).
- **Pakistan at Asia Cup with primary at the latest cycle** → "Same
  team, previous season" → expect the cycle before, which may not
  be the calendar-prior year (Asia Cup is biennial-ish).
- **Associate team — Nepal at Asia Cup or USA at T20 WC** with
  sparse historical data: navigate to a season the team played in,
  click "Same team, previous season". If a previous season exists
  in scope, expect it to render. If not, the link is hidden — no
  empty-column ghost.
- **BBL `2024/25` season string** → on a club view (Sydney Sixers
  primary), "Same team, previous season" should resolve to
  `2023/24` via string-match indexOf on the seasons list. Verify
  the slot's URL params carry the slash-format string verbatim.
- **"Different team — current scope" with bound team_type=
  international** → typeahead surfaces only internationals (today's
  auto-narrow). Confirm club teams don't slip in.
- **Cross-mode: India men's T20I primary + IPL 2024 avg slot** —
  this would require team_type override which we've explicitly
  disallowed. The picker's "Custom" path doesn't expose
  team_type as an editable field; verify the cross-type compare
  is impossible to construct via the UI.

Run all of these via agent-browser with screenshots captured for
spot-checks. Surfacing a single broken case in any of these is
worth more than 50 club-team asserts.

### Regression

- No backend shape changes → existing `tests/regression/teams/` and
  `tests/regression/scope-averages/` URL inventories don't need
  flipping. The new per-slot URLs the frontend generates use the
  same endpoints with different filter dicts; backend response
  shapes are unchanged.
- Add a small smoke entry to `tests/regression/teams/urls.txt`:
  one URL each for `compare1_*` style filter combinations to
  document that the same endpoint handles overridden scopes
  byte-identically to manual filter construction. All REG.

### Sanity

No new sanity tests. The `player_scope_stats` invariants are
unaffected.

## Docs sync

Per CLAUDE.md "Keeping docs in sync":

- **`CLAUDE.md`** "Compare tab — average-team column" entry:
  rewrite to describe the slot model + per-column scope override.
  3-column cap. Bound fields. URL params.
- **`docs/api.md`**: no new endpoints, but add a one-line note in
  the Team ball-level section that "the same endpoint serves
  arbitrary FilterParams; the Compare tab's per-column scope
  override is purely a frontend pattern."
- **`internal_docs/codebase-tour.md`**: note the new components
  (`AddCompareSlot`, `SlotScopeEditor`, `SlotHeaderChip`) and the
  `useCompareSlots` hook. Drop `AvgCompareColumn` (folded into
  unified `CompareSlotColumn`).
- **`internal_docs/design-decisions.md`**: new entry on the bind-
  axis rationale (gender + team_type bound; tournament + season +
  venue + series_type free) and the 3-column cap. Cross-reference
  outlook-comparisons.md.
- **`internal_docs/url-state.md`**: document the `compareN_*`
  pattern as the canonical way to encode per-slot scope overrides.
  This pattern may extend to Players Compare in the future
  (`outlook-comparisons.md` Surface 1) so the URL convention
  matters.
- **`frontend/src/content/user-help.md`**: user-facing description
  of scoped compare with the canonical example "RCB 2024 vs RCB
  2025 — what changed?". Worth a screenshot.

## Rollout phases

Three commits, staged so each lands runnable + greppable:

1. **`useCompareSlots` hook + URL parsing + legacy migration**
   (no UI rendering change yet). Existing `compare=A,B` /
   `avg_slot=1` URLs still work via the self-correcting effect;
   their resolved slot state matches today's behaviour. Browser
   smoke: navigate to a legacy URL, verify URL rewrites and grid
   renders identically.
2. **TeamCompareGrid refactor + unified `CompareSlotColumn` +
   3-column cap.** Drop `t2`. Add per-column header decoration
   (`SlotHeaderChip` always renders empty for now since slots
   inherit primary). Browser smoke: existing flows still work;
   `compare=A,B,C` URLs (rare) now show only A,B + the dropped C
   gets the one-time console.warn.
3. **`AddCompareSlot` + `SlotScopeEditor` + per-slot scope
   override end-to-end.** New picker, new edit-pencil affordance.
   The "RCB 2024 vs RCB 2025" + 3-column scenarios light up.
   Integration test additions land here.

Each commit ships green type-check + integration. Per CLAUDE.md
commit cadence — one logical change per commit.

## Open questions

1. **Avg slot label when scope-overridden.** `scopeAvgLabel(filters)`
   produces "Indian Premier League 2024 avg" today. When a slot is
   `kind='avg'` with overridden tournament=IPL + season=2025, the
   label becomes "Indian Premier League 2025 avg" — informative.
   When ONLY the season is overridden (primary has no tournament),
   label becomes "Men's club 2025 avg" — fine. Edge case: if the
   avg slot's overrides match primary's filters exactly, the label
   collapses to today's default. No special casing needed.
2. **Save scoped-compare presets.** "RCB 2024 vs RCB 2025 in IPL"
   is a multi-param URL the user might want to bookmark. The
   share-URL approach (copy link) already works — the URL
   captures everything. Explicit presets are deferred.
3. **Legend rewording when no slot has overrides.** The new
   "in each column's scope" phrasing is technically accurate even
   when no slot overrides — every column's scope just happens to
   equal primary's. Ship unconditionally — the 99% case where
   scopes match means "each column's scope" = "primary scope"
   anyway.
4. **Cross-format (T20 vs ODI vs Test) compare.** Out of scope —
   the platform is T20-only. Mentioned for completeness.

## Resolved decisions (2026-04-25 review)

- **Default first-load auto-fills `compare1=__avg__`** — primary +
  same-scope avg renders immediately, demonstrating the feature
  without requiring a click.
- **Auto-fill is once-per-mount via useRef gate** — ✕'ing the
  default avg slot does NOT bring it back on re-render. Fresh page
  load with no compareN params re-fires.
- **First-render URL update uses `replace: true`** — share URLs
  copied after first-load capture the avg slot explicitly, but the
  back button doesn't accumulate auto-fill steps.
- **Picker UX = quick-picks above + custom form below** — single
  picker with three (or four) one-click affordances and an escape
  hatch for advanced scope construction.
- **Quick-pick set v1**: League-avg-current / Same-team-previous-
  season / Different-team-current / Same-team-all-time. May extend
  later based on usage.
- **"Previous season" defined as lookup-against-bound-scope's-
  seasons-list** — uniform handling of club seasons, calendar
  internationals, biennial WCs, and BBL's `2024/25` strings; no
  per-team-type special cases.
- **Slot contiguity**: `?compare2=X` without `compare1` self-
  corrects to `?compare1=X` on mount.
