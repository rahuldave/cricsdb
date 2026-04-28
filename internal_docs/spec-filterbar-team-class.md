# Spec — `team_class` on the FilterBar

Promote `team_class=full_member` from a per-slot avg-picker control on
the Compare tab to the **9th FilterBar key** — a global filter that
applies on every tab. Today (post-2026-04-27 work) it's an opt-in
narrowing on a single avg slot in Teams > Compare; users want a
"international, full-members only" mode that applies *everywhere*
(match list, leader boards, partnership records, venue dossier,
series tiles, …).

> **Status: build-ready. NOT implemented in 2026-04-27 session.**
> Pick up next session per the rollout plan in §10. Pre-flight test
> baseline (§7) MUST be captured FIRST — without it we cannot prove
> the migration left no behavioural regression on intl pages that
> didn't ask for `team_class`.

---

## 1. Why

User flagged this 2026-04-27 after the per-slot Compare-tab fix shipped:

> Add it to the overall filterbar as well if international is chosen
> … wide ranging and you must think of its impacts.

Concrete examples that need the global filter:

- **Batting > Leaders, men_intl 2024-25**: top-10 today mixes
  Suryakumar / Yashasvi (FM-only matches) with associate-team batters
  who pile up runs against weaker attacks (Andries Gous of USA,
  Sikandar Raza of Zimbabwe vs Singapore, etc.). With
  `team_class=full_member` the leader board reflects "performances
  against full-member attacks" only.
- **Series tab, ICC Men's T20 World Cup dossier**: the FM filter
  excludes group-stage minnow-matches (USA vs Canada, Scotland vs
  Namibia), leaving the Super-8 / knockout subset. Useful for the
  "real cricket" lens.
- **Teams > Match List for Australia (2024-25)**: 22 matches (all
  opponents) becomes 16 matches (vs FM only). The per-discipline
  numbers shift accordingly.
- **Head-to-head leaderboard discoverability**: today users can hit
  the FM pool only via the Compare tab's avg-slot picker. They can't
  share a "FM-only Batting leaders" link to a friend.

---

## 2. Status quo (what's already shipped — 2026-04-27)

Backend (`api/`):

- `api/filters.py::AuxParams.team_class` — accepts `'full_member'`. Per-
  endpoint via `aux: AuxParams = Depends()`. Folded into clauses by
  `FilterBarParams.build()` when `aux` is passed in.
- `api/filters.py::AuxParams.chip_team_class` — separate field; tells
  `_league_aux` to align the team-side chip baseline to the avg
  slot's `team_class`. Asymmetric Compare-tab use.
- `api/full_members.py::full_member_clause()` — emits
  `(m.team1 IN (…) AND m.team2 IN (…))` literal IN-list. Frozenset
  of 12 ICC full members (Afghanistan / Australia / Bangladesh /
  England / India / Ireland / New Zealand / Pakistan / South Africa /
  Sri Lanka / West Indies / Zimbabwe).
- `api/routers/teams.py::_league_aux` — when called with a
  `chip_team_class` aux hint, copies it onto the synthesized
  league-side aux's `team_class`. This is what makes "Aus vs FM-only
  avg" chip arrows numerically agree with the displayed avg col.
- `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope` —
  rejects precomputed dispatch when `aux.team_class` is set (bucket
  tables don't carry the team-class dimension). Fall back to live
  aggregation.

Frontend (`frontend/src/`):

- `types.ts::FilterParams.team_class` — string field; populated only
  in per-slot scope today.
- `types.ts::FilterParams.chip_team_class` — string field; passed to
  the team-side fetch when the peer avg slot has team_class set.
- `components/scopeLinks.ts::FILTER_KEYS` — **8 entries**, no
  `team_class`. (We're adding it.)
- `hooks/useCompareSlots.ts::OVERRIDABLE_SLOT_KEYS` — includes
  `'team_class'`. `useCompareSlots` resolves a slot's team_class as
  `urlOverride ?? primary.team_class`. Today primary is always
  `team_class: undefined` because team_class isn't on the FilterBar.
- `components/teams/SlotScopeEditor.tsx` — Class dropdown (intl-only,
  All / Full members only) + Apply / Reset.
- `components/teams/AddCompareSlot.tsx` — "+ Full-member avg in
  current scope" quick-pick (intl-only). Sets
  `compareN_team_class=full_member` on the avg slot.
- `components/teams/SlotHeaderChip.tsx` — renders "full members only"
  in the slot-diff sub-line when overridden.
- `components/teams/teamUtils.ts::scopeAvgLabel` — line 1 reads
  "Full-member average" when `team_class === 'full_member'`. Line 2
  picks the right qualifier.
- `components/teams/TeamCompareGrid.tsx::chipAlignmentFor` — extracts
  team_class from any peer avg slot and forwards as `chip_team_class`
  hint on the team-side fetcher.

Tests:

- `tests/sanity/test_avg_baseline_pools.py` — 5 anchors, 3 modes
  (UNBOUNDED / FULL-MEMBER / SCOPE-TO-TEAM). Pinned on a closed
  historical window (men_intl 2018) so counts don't drift. **PASSES
  TODAY.**
- `tests/sanity/test_avg_baseline_numbers.py` — Aus / India men_intl
  2024-25 cross-product. Includes the FM-avg + chip_team_class case.
  **PASSES TODAY.**
- `tests/sanity/test_chip_direction_invariant.py` — 13 metrics ×
  scopes. `aus_ind_men_intl_2024_2025` row covers chip + avg
  alignment under team_class=full_member. **PASSES TODAY.**
- `tests/integration/compare_avg_chips.sh` — 3 anchors × ~80 cell
  assertions, including Anchor A' (Aus + FM-only avg) at men_intl
  2024-25. **PASSES TODAY.**
- `tests/integration/compare_filters.sh` — Anchor 5 covers
  full_member intl avg via `compare1_team_class=full_member`. **PASSES
  TODAY.**

What works today:

- `?compare1_team_class=full_member` on a single avg slot ✓
- `?team_class=full_member` as an aux query param on any backend
  endpoint that takes `aux: AuxParams = Depends()` (most of them) —
  **but the frontend never sets it that way**, so this surface is
  effectively dead from the UI side.

What does NOT work today:

- Setting `team_class=full_member` on the FilterBar — there's no
  widget. The frontend's `useFilters` hook only knows about
  `FILTER_KEYS` (the 8 fields).
- Sharing a URL like `?team_type=international&team_class=full_member`
  with a friend — they'd land on the right backend behaviour for
  endpoints that route through the per-page aux, but the FilterBar
  wouldn't reflect the active filter, and most pages don't pass
  `team_class` through to their request. So they'd see a chrome
  mismatch (URL says one thing, UI shows another).

---

## 3. Surface-level changes (what the user sees)

### 3.1 FilterBar widget

A new chip-toggle pill labelled **"Full members only"**, visible only
when `team_type === 'international'`. Sits in the FilterBar to the
RIGHT of the Tournament dropdown:

```
[Gender ▾] [Type ▾] [Tournament ▾] [▢ Full members only]   [📍 Venue …]   [Seasons …]
                                    └── visible only when team_type=international
```

Toggle states:

- **Off** (default): no `team_class` URL param. `▢ Full members only`.
- **On**: URL gains `?team_class=full_member`. Pill shows checked
  (filled square ▣), `is-active` class.

Auto-clear behaviour:

- When the user changes `team_type` away from `international` (to
  `club` or `''`), any active `team_class` is auto-cleared. Mirror of
  how `tournament` is auto-cleared by FilterBar when its scope
  changes.
- When the user clicks "reset all" (existing button), `team_class`
  clears along with everything else.

Discoverability:

- The pill renders with a small ⓘ tooltip on hover: "Restricts to
  matches between the 12 ICC full-member nations (excludes associate
  teams like Scotland, Nepal, USA, …)."
- On mobile, the pill wraps to its own line below tournament/venue if
  the FilterBar runs out of horizontal space (existing flex-wrap
  behaviour).

Hidden states (no DOM):

- `team_type !== 'international'` — pill not rendered. If the URL
  somehow carries `team_class` while team_type is wrong, the
  auto-clear effect below removes it on mount.

### 3.2 ScopeStatusStrip

The strip already has a "Show:" sub-line for `series_type`. Add an
analogous chip:

```
SHOWING: gender: men's · type: international · team_class: full members only · …
```

Or as a "Show:" pill (consistent with `series_type`):

```
Show: Full members only
```

Decision: use the **chip-style** entry (`team_class: …`) on the
showing line so the FilterBar set is fully reflected. The "Show:"
sub-line stays reserved for page-local aux (`series_type`). This
keeps the chip → FilterBar pin invariant clean: if it's in the chip
strip, it's in the FilterBar.

### 3.3 Scope-link URLs

`team_class` rides through every scope-link URL automatically once
it's added to `FILTER_KEYS`. `scopeLinks.ts:111` and `:263` iterate
the registry. **Zero per-component edits in `TeamLink`/`PlayerLink`/
`SeriesLink`.**

### 3.4 Per-tab semantic — exhaustive list

Where `team_class=full_member` applies (gated on `team_type='international'`):

| Tab / surface | What FM mode does | Implementation effort |
|---|---|---|
| **Teams landing** | Filter-sensitive — `getTeamsLanding` already accepts `team_class` via FilterParams. Hides associate sides under "regular" if the toggle is on. | Already passes through. **Verify, don't change.** |
| **Teams > Match List** | Drops Aus's matches vs Scotland / Namibia / Oman. Aus 22→16 (men_intl 2024-25). | Already filters via `_team_innings_clause`. Verify. |
| **Teams > Compare** | Both team-side AND avg-side data narrow. Chip baseline auto-aligns by construction (no `chip_team_class` hint needed). The per-slot avg-picker quick-pick "+ Full-member avg" becomes redundant — hide it. | Filters already plumbed; UI hide-quick-pick logic to add. |
| **Teams > vs Opponent** | If both teams are FM, no-op. If one is associate, results in zero matches. UI must render "no FM-vs-FM matches in scope". | Verify zero-match path; add empty-state copy if absent. |
| **Teams > Records** | Highest totals, biggest wins — narrow to FM-vs-FM only. | Filters already plumbed via FilterParams. Verify. |
| **Teams > Players** | Players who appeared for THIS team in FM-only matches. | Verify (already accepts FilterParams). |
| **Series > Landing** | Tournament tile counts narrow. Bilateral rivalry tiles for FM-vs-FM pairs (India vs Australia, etc.) carry the new count. Pairs involving an associate (e.g. India vs Scotland) hide entirely — count becomes zero. | `series/landing` already accepts FilterParams; add `team_class` to query parameter list. **CHECK.** |
| **Series > Dossier** | Inner stats narrow. ICC Men's T20 WC narrows from 55→fewer matches (WC matches between only-FM sides). | Same as above; mostly works. |
| **Players landing** | Curated tile stat strips narrow. Profile-tile match counts shift. | Already filter-sensitive via FilterParams. Verify. |
| **Player profile (`?player=X`)** | Per-discipline bands narrow. If `X` is an associate-team player, every band shows zero in scope (the "no FM matches" empty state). | Already filter-sensitive. Verify zero-match path. |
| **Player compare** | Both columns narrow. Cross-class comparisons (FM player vs associate player with FM mode on) result in associate showing all-zeros. | Same. |
| **Head-to-Head (player mode)** | Batter-vs-bowler matchups — narrow to FM-vs-FM matches. If either player is associate-only, zero matchups. | Already accepts FilterParams. |
| **Head-to-Head (team mode)** | Team-vs-team rivalry — only FM-vs-FM matches. India-vs-Australia unchanged; India-vs-Scotland zero. | Already accepts FilterParams. |
| **Batting / Bowling / Fielding leaders** | Top-N rankings exclude runs/wickets accumulated against associates. | Filters already plumbed. **Verify**: `team_class` must be in the query string the frontend sends, AND the backend's `filters.build()` must apply it — true today via `aux.team_class` BUT only if the request carries `aux: AuxParams = Depends()`. Need to audit each endpoint: do all leader endpoints take aux? Probably yes; confirm. |
| **Player innings list** | Per-discipline innings table narrows. | Already filter-sensitive. |
| **Matches list (`/matches`)** | Hides matches involving associates. Aus vs Pakistan stays; Aus vs Oman drops. | `matches.py::list_matches` accepts FilterParams. Verify. |
| **Matches > Scorecard (`/matches/:id`)** | No FM filter applied — once you're on a specific scorecard, the match's identity is fixed. **No-op.** | No change. |
| **Venues landing** | Venue tile counts narrow (only matches where both teams are FM count). Mumbai 80→? (most international matches at MCG were FM-vs-FM anyway). | `venues/landing` accepts FilterParams. Verify. |
| **Venues > Dossier** | Per-venue stats narrow to FM-vs-FM matches at that venue. | Verify. |
| **Help / About** | No-op. | None. |

The work split:

- **Backend**: add `team_class` to `FilterBarParams`. ~8 endpoints
  need a quick audit but most are already correct because they take
  `aux: AuxParams` and route through `filters.build(aux=aux)`. Once
  team_class is on `FilterBarParams`, it lands in the same clause
  builder via `if self.team_class …` instead of `if aux.team_class …`.
- **Frontend**: ~5 components touched (FilterBar, ScopeStatusStrip,
  scopeLinks FILTER_KEYS, AddCompareSlot quick-pick gate, TeamCompareGrid
  chipAlignmentFor comment). Most pages auto-pick up the new key
  because they iterate `FILTER_KEYS`.

### 3.5 Cross-cutting interactions

- **`series_type` × `team_class`**: independent. Composable.
  `series_type=icc & team_class=full_member` = "FM-only ICC events"
  (= Super-8s + knockouts at WCs). Both clauses AND together via
  `filters.build()`.
- **`scope_to_team` × `team_class`**: `scope_to_team` is club-only
  (the `_league_aux` gate). `team_class` is intl-only (the FilterBar
  visibility gate). Mutually exclusive by team_type — never both
  active simultaneously.
- **`tournament` × `team_class`**: independent. ICC Men's T20 WC +
  FM-only = the canonical use-case.
- **`filter_team` / `filter_opponent` × `team_class`**: independent.
  If both teams set are FM, redundant. If one is associate, the FM
  filter narrows to zero matches.
- **Auto-narrowing FilterBar** (gender/team_type from team selection
  in Teams page): when team_class is set and the user navigates to a
  team, the auto-narrowing logic must NOT clear team_class. Today
  the auto-narrow only sets gender/team_type when unambiguous, and
  only when those fields are empty — won't touch team_class. **No
  change needed.**

---

## 4. Backend changes (~10 small edits, all in `api/filters.py` + 3 routers)

### 4.1 Move `team_class` from `AuxParams` → `FilterBarParams`

**File:** `api/filters.py`

1. Add `team_class: Optional[str] = Query(None, description=…)` to
   `FilterBarParams.__init__`. Description: "Restrict to matches
   between two ICC full-member teams. Currently supports
   `full_member`. No-op when team_type != 'international'."
2. Set `self.team_class = team_class` in `__init__`.
3. In `FilterBarParams.build()`, fold the team_class clause from the
   AuxParams branch into the main clause builder (after the
   season_to / venue / team blocks):

   ```python
   if self.team_class == "full_member":
       clauses.append(full_member_clause(table_alias=table_alias))
   ```
4. Remove `team_class` field from `AuxParams` (keep the field name
   reserved for backward-compat aux requests — accept the param,
   silently no-op, log a deprecation warning the first time it's
   seen). Or remove cleanly and break old per-slot URL bookmarks.
   **Decision: remove cleanly.** Per-slot URLs from the Compare tab
   are auto-rewritten by `useCompareSlots`'s migration (see frontend
   §5.6). Old `?team_class=…` aux requests become accidental
   no-ops — caught by tests.
5. Keep `AuxParams.chip_team_class` exactly as today. Asymmetric
   Compare-tab use is still valid: user wants their primary col on
   "Aus vs everyone" but the avg col FM-only.

### 4.2 Update `_league_aux` propagation

**File:** `api/routers/teams.py::_league_aux`

- Drop the `aux.team_class` propagation step (no longer exists on
  AuxParams). Keep the `aux.chip_team_class → new_aux.team_class`
  copy step for the asymmetric per-slot case (avg slot has team_class
  via per-slot override; team-side request needs chip baseline
  aligned).

### 4.3 Update bucket dispatch gate

**File:** `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope`

- Change the rejection check from `aux.team_class` to
  `filters.team_class`.
- Add a comment noting that this rejection is also load-bearing for
  performance: when `team_class=full_member` is on the FilterBar,
  ALL bucket-eligible endpoints fall back to live aggregation. See
  §11 for the perf budget.

### 4.4 Audit all endpoints — does each take `aux: AuxParams`?

Run:

```bash
grep -rn "filters: FilterBarParams\|filters: FilterParams" /Users/rahul/Projects/cricsdb/api/routers/ | grep -v "aux:"
```

If any endpoint takes `filters` but NOT `aux`, it currently ignores
`team_class` entirely. After the move to FilterBarParams, those
endpoints automatically respect it (since it's now in `filters`). But
some endpoints may then START respecting team_class where they
DIDN'T before — that's the migration's whole point, but each one
needs a verification pass.

**Pre-flight task in next session:**

```bash
# List all endpoints + which params they take
grep -A 3 "@router.get" api/routers/*.py | grep -B 1 "filters\|aux" | head -200
```

Build a checklist: every endpoint that takes filters and is reachable
from an intl-relevant page must respond to team_class. Add a sanity
test that asserts for each one:

```
GET <url>&team_type=international                     → response_A
GET <url>&team_type=international&team_class=full_member → response_B
assert response_B.matches < response_A.matches  (or equal if pool was already FM-only)
```

This is the most load-bearing pre-migration audit. Skipping it means
silently shipping pages that ignore the toggle.

### 4.5 Reference endpoints

`/api/v1/tournaments` and `/api/v1/seasons` — they iterate FilterBar
fields when building their narrowing clauses (per CLAUDE.md design
note "FilterBar dropdown narrowing respects every FilterBar field").
Once `team_class` is in `FilterBarParams`, both auto-pick it up.
**Verify:** `_reference_clauses` body — does it explicitly handle
each field? Pass-through via `filters.build()` may work; if not, add
the `team_class` branch explicitly.

---

## 5. Frontend changes (~6 components touched)

### 5.1 `frontend/src/components/scopeLinks.ts::FILTER_KEYS`

Append `'team_class'` to the array. **One line change.** Auto-rides
through every scope-link URL (TeamLink, PlayerLink, SeriesLink),
every `useFilters()` call, every `useFilterDeps()` array. This is
why the rest of the frontend is mostly free.

### 5.2 `frontend/src/components/FilterBar.tsx`

Add the toggle pill (~25 lines, including auto-clear effect):

```tsx
const teamClass = params.get('team_class') || ''
const setTeamClass = (v: string) => set('team_class', v)

// Auto-clear team_class when team_type leaves 'international'.
useEffect(() => {
  if (teamType !== 'international' && teamClass) {
    setUrlParams({ team_class: '' }, { replace: true })
  }
}, [teamType, teamClass])

// In render, AFTER the Tournament group, BEFORE Venue:
{teamType === 'international' && (
  <div className="wisden-filter-group">
    <button
      onClick={() => setTeamClass(teamClass ? '' : 'full_member')}
      className={segBtn(teamClass === 'full_member')}
      title="Restrict to matches between the 12 ICC full-member nations"
    >
      {teamClass ? '▣' : '▢'} Full members only
    </button>
  </div>
)}
```

`clearAll()` already resets via `setUrlParams({...all: ''})` —
extend the spread to include `team_class: ''`.

### 5.3 `frontend/src/components/ScopeStatusStrip.tsx`

Add a chip entry in the segs array when `filters.team_class === 'full_member'`:

```tsx
if (filters.team_class === 'full_member') {
  segs.push({ label: 'team class', value: 'full members' })
}
```

Sits alongside the existing gender / type / tournament / season / venue chips.

### 5.4 `frontend/src/hooks/useFilters.ts`

Auto-picks up `team_class` because it iterates `FILTER_KEYS`. **No
change needed.** Verify by inspection only.

### 5.5 `frontend/src/components/teams/TeamCompareGrid.tsx`

`chipAlignmentFor` stays as-is — it's the asymmetric per-slot
mechanism (FilterBar `team_class` off, avg slot `team_class` on).
With FilterBar `team_class` on, this code path is irrelevant because
both team-side AND avg-side fetches carry team_class via the
ambient FilterParams.

**Add a comment** to chipAlignmentFor explaining the dual mechanism:
> When team_class is on the FilterBar, both team-side and avg-side
> requests carry it via `filters.build()` — chip alignment is
> automatic. This function only matters when team_class is set
> per-slot (FilterBar off, slot-specific override) — uncommon but
> valid for "Aus vs everyone" + "FM-only avg" workflow.

### 5.6 `frontend/src/components/teams/AddCompareSlot.tsx`

When the FilterBar's `team_class === 'full_member'`, the per-slot
"+ Full-member avg in current scope" quick-pick is redundant (the
displayed avg col is ALREADY FM-only — adding the override does
nothing). **Hide it** when ambient team_class is set.

```tsx
const ambientFM = primaryFilters.team_class === 'full_member'
// In render:
{!ambientFM && (
  <button onClick={() => onAddSlot(AVG_SENTINEL, { team_class: 'full_member' })}>
    + Full-member avg in current scope
  </button>
)}
```

### 5.7 Migration of existing per-slot URLs

`useCompareSlots` already does a one-shot mount-time migration for
legacy `compare=A,B` / `avg_slot=1` URLs. Add a NEW migration step:

If the URL has `compareN_team_class=full_member` AND
`team_class=full_member` is NOT on the FilterBar, AND
`team_type=international`, prompt-rewrite: lift the per-slot
override onto the FilterBar:

```
?team=Aus&compare1=__avg__&compare1_team_class=full_member&team_type=international
  ↓
?team=Aus&compare1=__avg__&team_type=international&team_class=full_member
```

This isn't strictly required (per-slot overrides still work after
the spec ships), but it's a nicer-default for users who set the
per-slot way before the FilterBar existed. Decision: **don't ship
auto-rewrite** — let users opt in by toggling the FilterBar pill
themselves. Per-slot URLs continue to work for asymmetric cases.

### 5.8 `frontend/src/types.ts::FilterParams`

`team_class` already exists. Update its docstring: now a FilterBar
field, not a per-slot-only override.

---

## 6. Edge cases + decisions

### 6.1 Cross-class matches with non-FM partner

Cricsheet matches have two teams. `full_member_clause` requires
BOTH to be FM. If even one team is associate, the match is excluded.
A match like "India vs Scotland" (FM × associate) is fully excluded
under FM mode. India's stats from that match don't count in any
FM-mode aggregate.

**Decision:** correct. Mirror of how match-level filters work
elsewhere (e.g. season filter excludes both sides equally).

### 6.2 Women's internationals

Same FM list (12 nations — cricsheet uses identical country labels
across genders). The toggle works identically for women's intl.
Numbers are smaller (women's WC has more associate involvement
historically) so the FM filter prunes more matches proportionally.

### 6.3 `team_class` set, `team_type=club`

Auto-clear via the FilterBar useEffect (§5.2). Defensive: if the URL
arrives with that combination from an external link, the effect
clears it on mount with `{ replace: true }`. **Never** silently
ignore on the backend — produce zero rows or log + ignore would both
be confusing. Auto-clear is the cleanest UX.

### 6.4 `team_class` set, `team_type=''` (All)

Same as §6.3 — auto-clear. The toggle is only meaningful within an
international scope.

### 6.5 Empty result sets

When `team_class=full_member` produces zero matches (e.g. on a single
match scorecard scoped to an associate-vs-associate game), the page
should render an empty state. Most pages already handle this via
`anyHasData` / placeholder paths. **Verify each tab's empty state
copy is sane** when team_class is the cause:

- Compare: existing "no matches in scope" works.
- Match List: existing.
- Records: empty leaderboard.
- Series tile: tile drops out (count = 0).

### 6.6 Bookmark / share-link compatibility

Old shared URLs with `?compare1_team_class=full_member` keep working
(per-slot mechanism unchanged). New shared URLs with
`?team_class=full_member` work via the new FilterBar field. There's
no breakage in either direction.

### 6.7 RC interaction with `chip_team_class`

`chip_team_class` is the asymmetric Compare-tab hint. It's
orthogonal to FilterBar `team_class`. Both can be active
simultaneously in theory (FilterBar on, plus a per-slot avg with
some other narrowing). Define the intersection: chip_team_class
takes precedence on the team-side baseline because it's the
explicit slot-level alignment hint. FilterBar team_class on team
data stays. **Add a sanity-test row** to
`test_chip_direction_invariant.py` for this combination.

### 6.8 Performance: bucket-baseline opt-out

`is_precomputed_scope` rejects when `filters.team_class` is set, so
EVERY page that hits an FM-mode URL falls back to live aggregation.
The Compare grid was the canary that motivated the bucket tables in
the first place (4s → 0.81s). Live aggregation under FM mode means
~3-4s page load on Aus 2024-25 instead of <1s. Acceptable for a
narrowing filter (users opt in). See §11 for a measurement plan.

---

## 7. Pre-flight tests (BEFORE) — must pass before touching any code

This is the **load-bearing safety net**. Without these, the
migration ships a behavioural regression (page X used to ignore
team_class; now it respects it) and we don't catch it.

### 7.1 Sanity tests — already pass today

Run locally + on a closed historical window, lock in current
numbers. **MUST PASS:**

```bash
uv run python tests/sanity/test_chip_direction_invariant.py     # 13/13
uv run python tests/sanity/test_avg_baseline_pools.py           # 5/5
uv run python tests/sanity/test_avg_baseline_numbers.py         # all axes
```

If any are red BEFORE starting work, fix them first.

### 7.2 Regression suites — capture HEAD hashes

```bash
bash tests/regression/run.sh teams           # 38 REG / 0 drifted
bash tests/regression/run.sh scope-averages  # 50 REG / 0 drifted
bash tests/regression/run.sh batting         # all REG matched
bash tests/regression/run.sh bowling         # all REG matched
bash tests/regression/run.sh fielding        # all REG matched
bash tests/regression/run.sh players         # all REG matched
bash tests/regression/run.sh head_to_head    # all REG matched
bash tests/regression/run.sh matches         # all REG matched
bash tests/regression/run.sh venues          # all REG matched
bash tests/regression/run.sh filterbar_refs  # all REG matched
```

These all PASS today (per 2026-04-27 session log). **All 126 URLs
that hit `team_type=international`** are covered by REG entries that
will continue to match after the migration BECAUSE the existing
URLs don't carry `team_class`. The migration adds NEW behaviour
(team_class respected when set), without changing existing
behaviour (when team_class is unset, results identical).

Confidence: high. Run-once at the start of next session as the
"canary" that the dev environment is clean.

### 7.3 Integration tests — 18 + 80 assertions

```bash
bash tests/integration/compare_filters.sh       # 18/18
bash tests/integration/compare_avg_chips.sh     # 3/3 anchors, ~80 cells
bash tests/integration/cross_cutting_aux_filters.sh
bash tests/integration/cross_cutting_url_state.sh
bash tests/integration/cross_cutting_mount_unmount.sh
bash tests/integration/teams.sh
bash tests/integration/team-compare-average.sh
bash tests/integration/series.sh
bash tests/integration/head_to_head.sh
bash tests/integration/matches.sh
bash tests/integration/venues.sh
bash tests/integration/batting.sh
bash tests/integration/bowling.sh
bash tests/integration/fielding.sh
bash tests/integration/players.sh
bash tests/integration/players_hygiene.sh
```

**MUST PASS** before starting. Re-run at the end of EACH commit.

### 7.4 NEW pre-flight ground-truth capture (DB-only subagent)

Per the "test ground truth comes from a DB-only subagent that didn't
read api/ source" rule, derive these numbers from `cricket.db`
directly. **Add to a new file `tests/sanity/test_team_class_baseline_numbers.py`:**

```
Pinned closed-window scope: men_intl 2024-25 (matches with season IN
('2024', '2024/25', '2025/26')), team_type='international'.

== Match counts ==
B1: All teams in scope (no team_class)              → ?  matches
B2: team_class=full_member                          → ?  matches
B3: Australia (no team_class)                       → 22 matches  (currently locked in test_avg_baseline_numbers.py)
B4: Australia (team_class=full_member)              → 16 matches
B5: India     (no team_class)                       → 34 matches
B6: India     (team_class=full_member)              → 31 matches
B7: Scotland  (no team_class)                       → ?  matches  (FM-only filter zeros this out)
B8: Scotland  (team_class=full_member)              → 0  matches  (Scotland is associate)

== Batting top-10 by total_runs ==
B9:  No team_class — top 10 names + run totals
B10: team_class=full_member — top 10 names + run totals (subset of #B9, with associate-only batters dropped)

== Bowling top-10 by wickets ==
B11: No team_class
B12: team_class=full_member

== Series landing ==
B13: ICC Men's T20 World Cup (no FM)              → 55 matches
B14: ICC Men's T20 World Cup (team_class=fm)      → ?  matches
B15: India vs Scotland bilateral (no FM)          → ?  matches
B16: India vs Scotland bilateral (team_class=fm)  → 0  matches

== Venues ==
B17: Wankhede Stadium intl 2024-25 (no FM)        → ?  matches
B18: Wankhede Stadium intl 2024-25 (team_class=fm)→ ?  matches
```

These numbers become the ANCHOR set. Each gets a sanity-test
assertion. The migration must preserve B1, B3, B5 (no-FM cases) and
introduce/match B2, B4, B6, B8, B10, B12, B14, B16, B18.

### 7.5 Per-page audit — does the page send `team_class`?

For each tab listed in §3.4, capture a screenshot + DOM `eval`
output BEFORE the migration:

```js
// Capture the API request URL the page makes for its top-level
// data fetch.
performance.getEntries()
  .filter(e => e.name.includes('/api/v1/'))
  .map(e => e.name)
```

Save these as `tests/sanity/team_class_pre_audit.json`. After the
migration, repeat the capture and diff: every URL that doesn't
include `team_class` when team_class is set is a page that's
silently ignoring the filter (BUG to fix).

---

## 8. Post-migration tests (AFTER) — what we add to lock in new behaviour

### 8.1 NEW sanity test file

`tests/sanity/test_team_class_baseline_numbers.py` — per §7.4. Pin
all 18 anchor numbers. Run on every commit.

### 8.2 Update existing sanity tests

`tests/sanity/test_avg_baseline_numbers.py`:

- Add a third mode: `INTL_2024_25_FM` where team_class is on the
  FilterBar (filters.team_class='full_member'). Aus 22→16, India
  34→31. Pin new RR + Boundary % + Economy + SR for both teams.
- The existing `("team_class", "full_member")` mode_key (per-slot
  avg with chip_team_class) stays as a separate row. It tests the
  asymmetric per-slot path; the new mode tests the ambient path.

`tests/sanity/test_chip_direction_invariant.py`:

- Add row `aus_ind_men_intl_2024_2025_filterbar_fm` — team_class is
  on FilterBar. Both team and avg requests carry it. Chip
  alignment is automatic. Direction × side-of-baseline rule still
  must hold.

`tests/sanity/test_avg_baseline_pools.py`:

- The 5 anchors (men_intl 2018) gain a 4th column: ambient FM mode
  (filters.team_class instead of aux.team_class). Same pool counts
  as the FULL-MEMBER mode today (the result is the same; only the
  request shape differs).

### 8.3 NEW integration scripts

`tests/integration/teams_compare_intl_fm_filterbar.sh` — agent-browser
on `?team=Australia&...&team_class=full_member`. Asserts:

1. Aus column shows 16 matches.
2. Aus column run rate = ? (DB-grounded from §7.4).
3. India column shows 31 matches.
4. Avg col displays "International average" + line2 "Men's T20I ·
   2024–2025 · full members" and 140 matches.
5. Status strip shows `team class: full members`.
6. URL `team_class=full_member` survives navigation:
   - Click on "Open Bowling tab" → `/teams?team=Aus&...&tab=Bowling&team_class=full_member`
     persists.
   - Navigate to `/series` from nav → strip still shows `team class`.
7. The "+ Full-member avg" quick-pick in AddCompareSlot is HIDDEN
   (because ambient team_class is already on).

`tests/integration/teams_compare_intl_fm_per_slot.sh` — agent-browser
on `?team=Australia&...&compare1_team_class=full_member` (per-slot,
FilterBar OFF). Asserts:

1. Aus column shows 22 matches (full record).
2. Avg col displays FM-only 140 matches.
3. Aus chip's scope_avg matches the avg col's RR (chip alignment via
   `chip_team_class` hint).
4. Status strip does NOT show `team class` (it's per-slot, not
   FilterBar).

These TWO scripts together prove the DUAL mechanism works:
FilterBar narrows team data; per-slot narrows only the avg col. Both
produce chip ↔ avg agreement, with DIFFERENT team data. That
distinction must be testable.

`tests/integration/series_landing_intl_fm.sh`:

1. Anchor: `/series?gender=male&team_type=international&team_class=full_member`.
2. ICC Men's T20 WC tile narrows from 55 → ? (DB-grounded).
3. Bilateral rivalry tile India-vs-Scotland is HIDDEN (zero matches).
4. India-vs-Australia bilateral tile shows the same count as without
   FM (both teams are FM, so unchanged).
5. Status strip shows `team class: full members`.

`tests/integration/batting_leaders_intl_fm.sh`:

1. Anchor: `/batting?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member`.
2. Top-10 list (DB-grounded — derive in §7.4 step B10).
3. Spot-check 3 specific players' positions.
4. Click on a player tile → URL preserves `team_class=full_member`.

`tests/integration/cross_cutting_team_class.sh` — mirror of
`cross_cutting_aux_filters.sh`. Asserts:

1. Toggle on writes `team_class=full_member` to URL.
2. Toggle off removes the param.
3. Switching `team_type=club` auto-clears team_class (mount-time
   useEffect with replace: true).
4. Cross-tab persistence: `/teams` → `/series` → `/batting`,
   team_class survives in URL through nav.
5. Status strip render: chip appears + COPY LINK preserves the param.
6. Hidden when team_type=club: the toggle pill DOM node should not
   render.
7. Numerical end-to-end: `/teams?team=Australia` Match List count
   drops 22→16 when team_class is toggled on. Asserted via DOM `eval`
   reading the StatCard text.

### 8.4 Update existing integration scripts

- `tests/integration/compare_avg_chips.sh` — Anchor A' (Aus + FM-only
  avg) currently uses `compare1_team_class=full_member`. It must
  CONTINUE to pass after the migration. NO change — it tests the
  asymmetric per-slot path which still works.
- `tests/integration/compare_filters.sh` — Anchor 5 same. NO change.

### 8.5 Regression tests — flip workflow

For each regression suite that has `team_type=international` URLs:

1. **Capture HEAD hashes** before any code change (§7.2).
2. **Add NEW URLs** for the team_class variant of every intl URL,
   tagged `NEW`:

   ```
   NEW team_summary_india_men_intl_fm /api/v1/teams/India/summary?gender=male&team_type=international&team_class=full_member
   NEW team_batting_india_fm          /api/v1/teams/India/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member
   ... etc, one per existing intl URL
   ```

3. **In a separate, EARLIER commit** (before any code change), flip
   the relevant existing URLs to `NEW` if they will produce
   different responses. Per the "feedback_regression_before_shape"
   discipline.

   Actually: existing intl URLs WITHOUT team_class will produce
   IDENTICAL responses after the migration (the new field defaults
   to None). So they STAY as REG. The NEW additions are entirely
   new URLs.

4. After the migration, run `./tests/regression/run.sh <suite>` and
   confirm `0 REG drifted, N NEW changed, 0 NEW unchanged`.

5. Once stable, flip the NEW entries to REG in a separate commit.

Affected suites + URL counts (from current intl-URL audit):

- teams: 32 intl URLs → 32 new NEW entries
- scope-averages: 14 → 14 new
- batting: 10 → 10 new
- bowling: 9 → 9 new
- fielding: 13 → 13 new
- players: 21 → 21 new
- head_to_head: 9 → 9 new
- matches: 3 → 3 new
- venues: 7 → 7 new
- filterbar_refs: 8 → 8 new

**Total: 126 new regression URLs.** That's a lot of paste work but
mechanical — script the URL generation.

---

## 9. Ground truth (numbers to derive in next session pre-flight)

These MUST be derived via a DB-only subagent that does NOT read
`api/` source (mirror of the 2026-04-27 chip-baseline ground truth
discipline). Stored in §7.4's pinned anchors.

Closed historical window: men_intl, season IN ('2024', '2024/25',
'2025/26').

```sql
-- B1
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season >= '2024' AND season <= '2026';

-- B2
SELECT COUNT(*) FROM match
WHERE gender='male' AND team_type='international'
  AND season >= '2024' AND season <= '2026'
  AND team1 IN (<FM list>) AND team2 IN (<FM list>);

-- B3 / B5 — already match the API today (22 / 34)
-- B4 / B6 — derive
SELECT COUNT(*) FROM match
WHERE (team1='Australia' OR team2='Australia')
  AND gender='male' AND team_type='international'
  AND season >= '2024' AND season <= '2026'
  AND team1 IN (<FM list>) AND team2 IN (<FM list>);

-- B7 / B8
SELECT COUNT(*) FROM match
WHERE (team1='Scotland' OR team2='Scotland')
  AND gender='male' AND team_type='international'
  AND season >= '2024' AND season <= '2026';
-- B8 expected: 0 (Scotland is associate, FM filter zeros it)

-- B9 / B10 (batting)
SELECT d.batter_id, p.name, SUM(d.runs_batter) AS runs
FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN person p ON p.id=d.batter_id
WHERE m.gender='male' AND m.team_type='international'
  AND m.season >= '2024' AND m.season <= '2026'
  -- B10 adds: AND m.team1 IN (<FM>) AND m.team2 IN (<FM>)
GROUP BY d.batter_id ORDER BY runs DESC LIMIT 10;
```

… and so on for each anchor.

---

## 10. Migration sequence (4-commit rollout)

### Commit 1: BACKEND MOVE — `team_class` to FilterBarParams

- `api/filters.py`: add field to `FilterBarParams`, fold clause into
  `build()`, remove from `AuxParams`.
- `api/routers/teams.py::_league_aux`: drop `aux.team_class`
  propagation step (still keeps `chip_team_class → team_class` copy).
- `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope`:
  rejection check now reads `filters.team_class`.
- All sanity tests still pass (the `aus_ind_men_intl_2024_2025` row
  becomes a FilterBar mode behind the scenes — same numbers).
- Regression suites: 0 drift (no URL changes yet).

### Commit 2: FRONTEND FILTERBAR WIDGET

- `scopeLinks.ts::FILTER_KEYS` extended.
- `FilterBar.tsx`: pill widget (intl-only) + auto-clear effect.
- `ScopeStatusStrip.tsx`: chip entry.
- `useFilters.ts`: no change (auto-picks up via FILTER_KEYS).
- `AddCompareSlot.tsx`: hide quick-pick when ambient team_class.
- `TeamCompareGrid.tsx`: comment-only update on chipAlignmentFor.
- `types.ts`: docstring update.

Browser-verify: toggle pill renders, URL updates, status strip shows.
Sanity tests still pass.

### Commit 3: REGRESSION URL ADDITIONS

- Add 126 new URLs across 10 regression suites with `NEW` tag.
- Run each suite — confirm new hashes are stable.
- All `REG` entries continue to match (existing behaviour unchanged).

### Commit 4: TESTS — sanity + integration

- Add `tests/sanity/test_team_class_baseline_numbers.py` with the
  18 anchor assertions from §9.
- Update `test_avg_baseline_numbers.py` with FilterBar FM mode row.
- Update `test_chip_direction_invariant.py` with FilterBar FM row.
- Add 5 new integration shell scripts per §8.3.
- Run all integration tests — 18+ scripts pass.
- Browser-verify each anchor URL.
- Re-run regression suites — flip NEW → REG once stable.

### Commit 5 (optional, separate session): REGRESSION FLIP

After 1-2 weeks of stable HEAD, flip the NEW entries to REG so they
become permanent guardrails.

### Abandonment criteria

- If pre-flight tests fail BEFORE the work starts, debug those first.
- If Commit 1 breaks `test_avg_baseline_numbers.py` and the breakage
  is NOT due to expected number shifts (i.e. it's a real regression
  on a no-team_class case), revert immediately.
- If Commit 2 results in a FilterBar UI bug visible at any viewport,
  revert and re-design.
- If Commit 3 shows >0 `REG drifted` in any suite, the migration has
  silently broken behaviour for an unrelated query. Bisect via per-
  URL run.

---

## 11. Performance budget

`team_class=full_member` forces live-aggregation fallback in the
bucket dispatch (per `is_precomputed_scope` rejection — bucket
tables don't carry the team-class dimension). For Compare-tab
endpoints this means going from precomputed (~50ms per query) back
to live (~250ms per query). 12 queries × 250ms = ~3s vs ~600ms
precomputed. Acceptable for a narrowing filter (user opt-in).

For non-Compare endpoints (leader boards, match list, dossier)
that don't go through bucket dispatch, no slow-down — they were
already live aggregations.

**Measurement task in next session:**

```bash
# With FM off (baseline)
time curl -s "http://localhost:8000/api/v1/teams/Australia/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025"

# With FM on (FM mode page-load floor)
time curl -s "http://localhost:8000/api/v1/teams/Australia/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member"
```

Expected: FM-on is 3-5× slower (~200ms vs ~50ms) but absolute
latency well under the 1s "feels slow" threshold for a single
endpoint. Multiple parallel fetches in Compare-grid — total page
load ~1.5-2s under FM mode (vs ~0.8s without). Within budget.

Pre-emptive perf work — none planned. If page-load on a real-world
intl + FM URL exceeds 4s, then we look at a `bucketbaseline_full_member`
sibling table. Out of scope for this spec.

---

## 12. Pick-up notes for next session

**Pre-flight (do these FIRST, in order):**

1. Run all sanity tests, regression suites, integration scripts
   per §7.1–7.3. Confirm green.
2. Spawn DB-only subagent to derive the 18 anchor numbers per §7.4
   + §9. Save in a Markdown file
   `internal_docs/team-class-anchor-numbers.md` so they're committable
   independently of the test code.
3. Run the per-page audit per §7.5. Save the BEFORE captures as
   `tests/sanity/team_class_pre_audit.json`.

**Build (in 4 commits per §10):**

1. Commit 1 — backend move. ~6 lines of code, ~80 lines of test
   delta if you redo `_league_aux` propagation comments. Sanity
   tests still pass.
2. Commit 2 — frontend FilterBar widget. ~30 lines of new TSX, ~5
   in ScopeStatusStrip, 1 in scopeLinks, 1 in AddCompareSlot.
3. Commit 3 — regression URL additions. 126 new URLs across 10
   suites. Mechanical via a small generator script.
4. Commit 4 — tests. 5 new integration scripts (~80 lines each), 3
   sanity test updates.

**Hard stops:**

- Commit 1 breaks any sanity test → fix or revert immediately.
- Commit 2 has any visual regression at iPhone 13 width → revert.
  (User has flagged mobile alignment 3× this session; sensitivity
  is high. Verify with agent-browser DOM mode at 390×844 before
  considering Commit 2 done.)
- Commit 3 shows `REG drifted` on any URL → bisect; assume real bug.

**Discipline carried over from 2026-04-27:**

- Commit after every feature.
- Test ground truth from DB-only subagent (no api/ source read).
- Discuss design before non-trivial code changes.
- Pre-flight `wal_checkpoint(TRUNCATE)` is in deploy.sh; do NOT
  edit cricket.db while a deploy is in flight.
- `internal_docs/links.md` rules apply for any new navigation work.
- "No CSS-pixel shortcuts" — if FilterBar widget mobile layout is
  off, fix structurally (grid / flex) not via min-width hacks.

**Estimated effort:** 6-8 hours focused work. Pre-flight ~2h
(running tests, capturing baseline, deriving ground truth). Build
~3h (4 commits, deploy verifications). Post-flight ~2h (regression
URL flip, prod browser-verify, docs sync).

**Risk:** medium. The change is conceptually clean (one new
FilterBar key) but ripples to 10 regression suites + 5 new
integration scripts + 3 sanity-test updates + 18 numerical anchors.
The pre-flight ground truth is the single biggest schedule risk —
underestimating it means the build commits drift from numbers we
can't trust.

---

## 13. Open questions (decisions deferred to next session)

1. **Removal vs deprecation of `AuxParams.team_class`**: removing
   forces all callers onto the FilterBar field. Deprecating with a
   quiet no-op preserves any per-slot URL bookmarks shared in the
   wild. Lean: **remove cleanly**. The per-slot Compare URLs
   (`compareN_team_class=full_member`) keep working via the per-slot
   override mechanism — that field is still on `OVERRIDABLE_SLOT_KEYS`.
2. **Default state**: pill defaults off (current proposal) or on for
   intl users? Lean: **off**. Matches FilterBar's "no narrowing"
   default for everything else.
3. **Class taxonomy expansion**: do we anticipate `team_class=icc_associate`
   or `team_class=tier_1` later? If yes, design the field as an
   enum from day 1. Lean: **start with full_member only, expand
   later**. The `full_member_clause()` function name is specific to
   this case; future expansions will add sibling functions.
4. **Mobile FilterBar layout**: at iPhone 13 width, the existing
   FilterBar is already crowded (Gender / Type / Tournament / Venue
   / Seasons spans 2 rows on mobile). Adding a 6th group bumps to a
   3rd row when team_type=intl. Acceptable for an opt-in toggle?
   Lean: **yes, the pill only appears when team_type is intl, so
   it's not adding to the default-state crowding**. Verify in
   browser.

---

*Spec v2 — 2026-04-27. Replaces the 294-line v1. Pick up next
session per §12.*
