# Spec v3 — `team_class` on the FilterBar

> **Supersedes** `spec-filterbar-team-class.md` (v2, 2026-04-27 / 2026-04-28).
> **Status:** build-ready. Not yet implemented.

Promote `team_class=full_member` from a per-slot Compare-tab override to
the **9th FilterBar key**, behaving as the next overridable axis
alongside `tournament` / `season_from` / `season_to` / `filter_venue` /
`series_type`. Pill renders only when `team_type === 'international'`
(closed-league semantic — full-member is an intl classification).

---

## 1. Lessons from v2

v2 framed the FilterBar `team_class` as a new symmetric narrowing mode
("Mode C") that needed to coexist with the per-slot mechanism ("Mode B")
and produced ~50 pages of three-mode preservation argument. That mental
model was wrong:

- The overridable-slot architecture (`useCompareSlots`,
  `OVERRIDABLE_SLOT_KEYS`, `compareN_<key>` URL params) **already supports
  this work natively**. `team_class` is literally already in
  `OVERRIDABLE_SLOT_KEYS`. The system was extended to anticipate exactly
  this rollout.
- The right framing: `team_class` becomes the next overridable axis.
  Primary inherits FilterBar, compare slots inherit primary by default
  and can override per-slot. Identical to how `tournament` / `season` /
  `filter_venue` already work.
- v2's three-mode framing produced parallel test anchors, parallel
  integration scripts, and a chip-plumbing argument that was needed
  only because Mode C was conceived as a special case. Under the
  corrected framing, "FilterBar narrows team data; per-slot mechanism
  narrows avg col" is just the natural consequence of the inheritance
  model — no special handling required for the default flow.

Two audits of v2 (in chat, 2026-04-28) traced consequences of the
wrong framing. Most of those consequences disappear here. The two
findings that survive — chip alignment under explicit avg-slot
override (broadening case) and URL serialization of empty overrides —
are real but **not unique to team_class** (they affect every
overridable axis). Park them in a sibling spec
(`spec-slot-override-chip-alignment.md`); they are not blocking for
this rollout.

---

## 2. Mental model

Three roles in the Compare tab:

| Column | Source of scope | Override mechanism |
|---|---|---|
| **Primary (leftmost)** | Path team + FilterBar URL | None — primary IS the FilterBar |
| **Compare slot 1 (middle)** | Inherits FilterBar by default | Per-slot URL `compareN_<key>` |
| **Compare slot 2 (right)** | Inherits FilterBar by default | Per-slot URL `compareN_<key>` |

Within each compare slot, axes split into two classes:

- **Bound axes** (cannot override): `gender`, `team_type`. Cross-mode
  comparison is a category error in this UI.
- **Overridable axes**: `tournament`, `season_from`, `season_to`,
  `filter_venue`, `series_type`. **Plus `team_class` after this spec.**
  All inherit primary by default; URL `compareN_<key>` overrides.

On every non-Compare tab there is no slot machinery — `team_class`
just narrows that tab's data via FilterBarParams the same way every
other FilterBar field does. Match list shrinks, leader boards reshuffle,
tile counts update.

Default flow against the user's reference URLs:

| URL | FilterBar `team_class` | Per-slot avg | Aus | Avg | India |
|---|---|---|---|---|---|
| **A** (today) | off | off | 22 | 870 | 34 |
| **B** (today) | off | full_member | 22 | 140 | 34 |
| **E1** (new default w/ FilterBar on) | full_member | (inherits) | 16 | 140 | 31 |
| **G** (club, control) | (pill hidden) | (n/a today) | 15 (RCB) | IPL avg today | 14 (SRH) |

URL A and B preserve byte-identical post-migration. URL E1 is the new
functionality. URL G must not regress (club mode, pill never appears).

---

## 3. Gating: intl-only

`team_class=full_member` is meaningful only when `team_type='international'`
because full-member status is an intl classification (12 ICC nations).
For clubs, the FM list contains country names that don't match
franchise team strings, so `full_member_clause` would zero out every
match — confusing UX, useless filter.

Gating happens at three layers, defense-in-depth:

1. **FilterBar widget** — pill is only rendered when
   `team_type === 'international'`. Switching to club / "All" via the
   Type segmented control auto-clears any active `team_class` URL
   param via a `replace`-mode useEffect.
2. **Frontend deep-link guard** — on mount, if URL carries
   `team_class` while `team_type` is not international, strip it
   (replace mode). Prevents a stale link from showing a chip-strip
   value for a filter the UI can't surface.
3. **Backend defensive gate** — `FilterBarParams.build()` only emits
   `full_member_clause` when `self.team_type == 'international'`. If a
   request arrives with `team_type=club&team_class=full_member`
   (frontend gate failed, or curl), the clause is silently a no-op.
   Keeps club URLs robust.

---

## 4. Surface changes

### 4.1 FilterBar widget

A chip-toggle pill labelled **"Full members only"**, visible only when
`team_type === 'international'`. Sits between Tournament and Venue in
the FilterBar:

```
[Gender ▾] [Type ▾] [Tournament ▾] [▢ Full members only]   [📍 Venue …]   [Seasons …]
                                    └── visible only when team_type=international
```

Off (default): no `team_class` URL param. ▢ box.
On: URL gains `?team_class=full_member`. ▣ filled box, `is-active` class.

Tooltip: "Restricts to matches between the 12 ICC full-member nations
(excludes associate teams like Scotland, Nepal, USA, …)."

`anyFilterSet` (line 188) and `clearAll()` (line 209) extend to
include `team_class`.

### 4.2 ScopeStatusStrip

Add a chip when `filters.team_class === 'full_member'`:

```
SHOWING: gender: men's · type: international · team class: full members · …
```

Sits alongside the existing FilterBar chips. The "Show:" sub-line
stays reserved for the page-local aux `series_type`.

### 4.3 Scope-link URLs

`team_class` rides through every scope-link URL automatically because
`buildParams` in `scopeLinks.ts:263` iterates `FILTER_KEYS`. **Zero
edits in TeamLink / PlayerLink / SeriesLink.** Decision: include
`team_class` in phrase URLs (narrowing) but NOT in `nameParams`
identity URLs — same convention as `tournament` / `season`. A team's
name link drops narrowings; phrases preserve them.

### 4.4 Compare-tab UI

`SlotScopeEditor` Class dropdown stays. Initial value falls back to
`primary.team_class` rather than `''`, so opening the editor with
ambient FM-on shows "Full members only" pre-selected (matching what
the slot is actually doing).

`AddCompareSlot`'s "+ Full-member avg in current scope" quick-pick
**stays visible regardless of FilterBar state**. It's the explicit-
override entry point — the same role the "Same team, previous season"
quick-pick plays for the season axis. Hiding it when ambient FM is on
(per v2) was based on the symmetric-narrowing misreading; under the
corrected design the quick-pick remains useful (it forces FM on the
avg slot whether or not FilterBar narrows).

`SlotHeaderChip` continues to surface per-slot diff vs primary. With
the inheritance fix, a slot inheriting `team_class=full_member` from
primary doesn't render a "full members only" chip (no diff). A slot
overriding to differ does (e.g. avg slot kept at unbounded while
FilterBar is FM — though that's the override edge case parked in §10).

---

## 5. Backend changes

Six files. Most edits are 1-3 lines.

### 5.1 `api/filters.py`

- **Add** `team_class: Optional[str] = Query(None, description=...)` to
  `FilterBarParams.__init__`. Description: "Restrict to matches
  between two ICC full-member teams. Currently supports `full_member`.
  No-op when team_type != 'international'."
- **Set** `self.team_class = team_class`.
- **In `build()`**, append after the team / opponent block:

  ```python
  if self.team_class == "full_member" and self.team_type == "international":
      clauses.append(full_member_clause(table_alias=table_alias))
  ```

  The `team_type == 'international'` gate is the defensive backend
  gate from §3 layer 3.

- **Remove** `team_class` field from `AuxParams.__init__` and its
  storage line (`self.team_class = ...`). The URL param now binds to
  `FilterBarParams.team_class`.
- **Keep** `AuxParams.chip_team_class` as-is. Different mechanism
  (alignment hint), unaffected by this move.

### 5.2 `api/routers/teams.py::_league_aux`

The chip alignment hint synthesis path stays. Today it does:

```python
if aux.chip_team_class:
    new = copy(aux)
    new.team_class = aux.chip_team_class  # writes to AuxParams.team_class
```

After the field move, `team_class` lives on `FilterBarParams`, not
`AuxParams`. The synthesis must land on the league-side `filters`
copy instead. Refactor `_league_aux` to take and return both:

```python
def _league_aux(
    team: str | None, aux: AuxParams,
    filters: FilterBarParams | None = None,
) -> tuple[FilterBarParams, AuxParams]:
    """Return (league_filters, league_aux) for the league-side call.

    Two synthesis steps run independently:

      1. scope_to_team — clubs only, league_aux.scope_to_team = team.
      2. chip_team_class → league_filters.team_class — when the team
         request carries a chip alignment hint (peer avg slot has
         team_class set), apply that team_class to the league-side
         filters so chip's scope_avg matches the displayed avg col.
    """
    from copy import copy
    if team is None:
        return filters, aux
    new_aux = aux
    new_filters = filters
    if not aux.scope_to_team and (filters is None or filters.team_type == "club"):
        new_aux = copy(aux)
        new_aux.scope_to_team = team
    if aux.chip_team_class:
        if new_filters is filters:  # always true here; clone
            new_filters = copy(filters) if filters else None
        if new_filters is not None:
            new_filters.team_class = aux.chip_team_class
    return new_filters, new_aux
```

Update the seven call sites (lines 1327, 1665, 2117, 2438, 2745, 3079,
3501) to destructure the tuple:

```python
lf, la = _league_aux(team, aux, filters)
s = await _batting_aggregates(None, lf, la)
```

This preserves Mode B (URL B) — the existing chip alignment for
asymmetric per-slot avg overrides keeps working. The two changes (move
`team_class` to FilterBarParams + plumb it through `_league_aux`) ship
together in commit 1.

### 5.3 `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope`

- Change rejection check from `aux.team_class` to `filters.team_class`.
- Bucket tables don't carry the team-class dimension, so live
  aggregation is the fallback when `team_class=full_member` is on.
- Apply the gate symmetrically: only reject when team_class will
  actually fire (i.e. when `team_type='international'`). For
  `team_type='club'`, defensive backend gate makes team_class a no-op
  → bucket dispatch can stay enabled.

### 5.4 `api/routers/tournaments.py::_build_filter_clauses`

The Series-tab router hand-rolls filter clauses (no `filters.build()`
call, no `aux` parameter). Add a defensive-gated team_class branch:

```python
def _build_filter_clauses(filters, alias="m", include_tournament=False, include_team_pair=True):
    clauses, params = ...  # existing
    # team_class — gated on team_type='international'
    if filters.team_class == "full_member" and filters.team_type == "international":
        from ..full_members import full_member_clause
        clauses.append(full_member_clause(table_alias=alias))
    return clauses, params
```

This applies team_class to all 17 endpoints in `tournaments.py` that
go through `_build_filter_clauses` (landing, summary, by_season,
points_table, records, batters_leaders, batter_scope_stats,
bowlers_leaders, bowler_scope_stats, fielders_leaders,
fielder_scope_stats, partnerships_*, rivalry_summary, etc.).

### 5.5 `api/routers/reference.py`

Two helpers hand-roll filter clauses:

- `_reference_clauses` (drives `/tournaments` and `/seasons`) — add a
  `team_class` parameter and gated branch matching §5.4.
- `list_teams` (`/teams` endpoint, FilterBar typeahead) — add the
  team_class clause to its where_parts. Without this, picking
  Scotland from the typeahead while FilterBar is FM yields a
  fully-empty page (Scotland is associate; FM filter excludes every
  match). Better: typeahead doesn't surface Scotland in that scope at
  all.

### 5.6 `api/full_members.py`

No change. `full_member_clause` already defensive (literal IN list,
no bind params, frozenset of 12 country names).

---

## 6. Frontend changes

Five files.

### 6.1 `frontend/src/components/scopeLinks.ts::FILTER_KEYS`

Append `'team_class'`:

```ts
export const FILTER_KEYS = [
  'gender', 'team_type', 'tournament',
  'season_from', 'season_to',
  'filter_team', 'filter_opponent', 'filter_venue',
  'team_class',
] as const
```

Auto-rides through `useFilters`, `useFilterDeps`, scope-link URL
builders. **One line.**

### 6.2 `frontend/src/components/FilterBar.tsx`

Add the toggle widget (~25 lines):

```tsx
const teamClass = params.get('team_class') || ''

const setTeamClass = (v: string) => set('team_class', v)

// Auto-clear team_class when team_type leaves 'international'.
// Defensive deep-link guard + Type-segmented-control side effect.
useEffect(() => {
  if (teamType !== 'international' && teamClass) {
    setUrlParams({ team_class: '' }, { replace: true })
  }
}, [teamType, teamClass])

// In render, between Tournament and Venue:
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

Update `anyFilterSet` (line 188) and `clearAll` (line 209) to include
team_class:

```ts
const anyFilterSet = Boolean(
  gender || teamType || tournament || seasonFrom || seasonTo
  || filterVenue || teamClass
)
const clearAll = () => setUrlParams({
  gender: '', team_type: '', tournament: '',
  season_from: '', season_to: '', filter_venue: '',
  team_class: '',
})
```

### 6.3 `frontend/src/hooks/useCompareSlots.ts`

**The one-line bugfix.** Line 50:

```ts
function inheritedScope(primary: FilterParams): ResolvedSlotScope {
  return {
    gender: primary.gender,
    team_type: primary.team_type,
    tournament: primary.tournament,
    season_from: primary.season_from,
    season_to: primary.season_to,
    filter_venue: primary.filter_venue,
    series_type: primary.series_type,
    team_class: primary.team_class,   // ← was: undefined
  }
}
```

Update the comment block (lines 48-49) to remove the now-obsolete
"team_class isn't in the FilterBar — primary always inherits null"
line.

### 6.4 `frontend/src/components/teams/SlotScopeEditor.tsx`

Two small fixes:

- Line 27: fall back to primary on initial state.

  ```ts
  const [teamClass, setTeamClass] = useState(
    initial.team_class ?? primary.team_class ?? ''
  )
  ```

- Line 58: persist override only when it differs from primary (matches
  every other axis).

  ```ts
  if (cmp(teamClass, primary.team_class)) o.team_class = teamClass
  ```

`tournamentsFetch` and `seasonsFetch` (lines 31-47) take
`primary.gender / team_type / tournament` to narrow dropdowns. The
auto-narrowing already covers what users care about for the editor;
adding team_class to those fetches is non-blocking (the editor's
dropdown narrowing is a smaller surface than the FilterBar's). Add it
opportunistically — no behaviour regression if skipped.

### 6.5 `frontend/src/components/ScopeStatusStrip.tsx`

Add the chip (~3 lines):

```ts
if (filters.team_class === 'full_member') {
  segs.push({ label: 'team class', value: 'full members' })
}
```

### 6.6 `frontend/src/components/teams/AddCompareSlot.tsx`

No change. The "+ Full-member avg in current scope" quick-pick stays
visible regardless of ambient FilterBar state. v2's hide-when-ambient
logic is dropped.

### 6.7 `frontend/src/components/teams/teamUtils.ts::scopeAvgLabel`

No change. Already handles `team_class === 'full_member'` correctly
when present in the slot scope.

### 6.8 `frontend/src/types.ts::FilterParams`

No code change. Update the docstring on `team_class` to remove the
"Per-slot avg baseline narrowing" framing — it's now a FilterBar
field that flows down to slots via inheritance.

---

## 7. SQL ground truth — anchors derived pre-flight

**DERIVED 2026-04-28** by a DB-only subagent (no `api/` source read).
Pinned numbers live at
`internal_docs/team-class-anchor-numbers.md` (28 anchors, A1-A18 +
A9/A10/A11/A12 top-10 lists + C1-C4 + D1-D2 + B1-B4). Quoted in
summary form below; consult the anchor file for exact SQL.

Closed historical window: **`gender='male'`, `team_type='international'`,
`season IN ('2024','2024/25','2025')`.** (NOT `'2025/26'` — it falls
outside the closed window. Initial spec wording ambiguous; confirmed
empirically that `('2024','2024/25','2025')` reproduces the 22/16/34/31
pre-known anchors.)

### A. Intl narrowing — derived counts

| Anchor | Description | Result |
|---|---|---|
| A1 | Total men_intl 2024-25 matches, unbounded | **870** |
| A2 | Same scope, FM-only | **140** |
| A3 | Australia, unbounded | **22** ✓ |
| A4 | Australia, FM-only | **16** ✓ |
| A5 | India, unbounded | **34** ✓ |
| A6 | India, FM-only | **31** ✓ |
| A7 | Scotland, unbounded | **17** |
| A8 | Scotland, FM-only | **0** ✓ |
| A13 | ICC Men's T20 World Cup, unbounded | **44** |
| A14 | ICC Men's T20 World Cup, FM-only | **16** |
| A15a/b | India vs Australia, both modes | **1 / 1** |
| A16a/b | India vs Scotland, both modes | **0 / 0** (didn't meet) |
| A17 | Wankhede intl 2024-25, unbounded | **1** |
| A18 | Wankhede intl 2024-25, FM-only | **1** |

### A9-A12. Top-10 batter / bowler lists

Pinned in `team-class-anchor-numbers.md` §A9-A12. Key signals:
- **A10** (FM-only batters): Nissanka, Buttler, Abhishek Sharma, Salt,
  Tilak Varma, Hendricks, Hope, Saim Ayub, Hridoy, Samson. Note that
  spec prose anticipated "Suryakumar / Yashasvi rise" — the actual
  scope-window subset doesn't surface them; the test pins the literal
  ordering above.
- **A12** (FM-only bowlers): CV Varun, Shaheen Afridi, Haris Rauf,
  Rishad Hossain, Abbas Afridi, Taskin Ahmed, Wanindu Hasaranga,
  Arshdeep Singh, Duffy, Adil Rashid.

### A15/A16 caveat

Both A15 (Ind-Aus) and A16 (Ind-Sco) return identical counts in both
modes within this scope window:
- A15: 1 = 1 (both FM, FM filter is a no-op)
- A16: 0 = 0 (didn't play in scope)

The sanity-test invariant must be **`FM ≤ unbounded`**, which
0=0 satisfies. The spec's earlier "any → 0" prose for A16 anticipated
a positive unbounded count; the actual zero unbounded is acceptable.

### B-prime. Club no-op (defensive gate proof)

| Anchor | Description | Result |
|---|---|---|
| B1 | RCB IPL 2025 matches, no team_class | **15** |
| B2 | Same query + FM clause SQL-direct (zero, NOT what API should return) | **0** ⚠️ |
| B3 | SRH IPL 2025 matches | **14** |
| B4 | All IPL 2025 matches | **74** |

**Critical test interpretation**: B1 = 15, B2 = 0 reveals the failure
mode the gate prevents. The sanity test must assert that calling the
API with `team_type=club&team_class=full_member` returns **15** (i.e.
B1, ignoring the team_class), NOT **0** (i.e. B2, naively applying
the FM clause). This is the load-bearing assertion proving the
defensive backend gate fires.

### C. Compare-grid chip baselines (run rates)

| Anchor | Description | Result |
|---|---|---|
| C1 | Australia batting RR, men_intl 2024-25 unbounded | **9.9150** |
| C2 | Australia batting RR, men_intl 2024-25 FM-only | **9.8232** |
| C3 | League batting RR, men_intl 2024-25 unbounded | **7.5172** |
| C4 | League batting RR, men_intl 2024-25 FM-only | **8.4974** |

**Interesting semantic**: Australia's chip flips MAGNITUDE between
modes:
- Unbounded: Aus 9.92 vs league 7.52 → **+32%** above avg (good)
- FM-only: Aus 9.82 vs league 8.50 → **+15.6%** above avg (still
  good but dramatically smaller delta)

The league RR jumps 1.0+ points (7.52 → 8.50) because dropping
associate-team matches lifts the average — those tend to be lower-
scoring on average. Australia barely moves (its own scoring is
similar regardless of opposition). This is the core narrative the
FilterBar exposes: "is X above avg" depends crucially on what pool
"avg" means.

### D. Women's intl symmetry

| Anchor | Description | Result |
|---|---|---|
| D1 | Total women_intl 2024-25 matches, unbounded | **596** |
| D2 | Same scope, FM-only | **97** |

Women_intl narrows ~6.1× under FM (596 → 97). Comparable to men_intl's
~6.2× (870 → 140). FM symmetry across genders confirmed.

Total: **28 anchors** pinned at `team-class-anchor-numbers.md`. Each
becomes one row in `tests/sanity/test_team_class_baseline_numbers.py`.

---

## 8. Test plan

Four test layers run, each with a distinct role.

### 8.1 Sanity (Python, DB-direct)

**New file:** `tests/sanity/test_team_class_baseline_numbers.py`.
Pin all ~25 anchors from §7. Each row:

```python
async def assert_anchor(label, sql_query, sql_params, api_call, expected_count):
    db_count = (await db.q(sql_query, sql_params))[0]['count']
    api_count = await api_call()
    assert db_count == expected_count, f"DB drift on {label}"
    assert api_count == db_count, f"API≠DB on {label}: api={api_count} db={db_count}"
```

This is the SQL-vs-API end-to-end contract — catches the class of
bugs where the API thinks it's narrowing but doesn't generate the SQL
to match.

**Updates** to existing sanity tests — bundled IN commit 1 because the
field move breaks them:

- `tests/sanity/test_avg_baseline_pools.py:43-54`: replace
  `make_aux(team_class=...)` with `make_filters(team_class=...)`. The
  4th column ("ambient FM mode via FilterBarParams") replaces the
  former AuxParams team_class invocation. Same numbers.
- `tests/sanity/test_avg_baseline_numbers.py:77`: same field move.
  Add a row for FilterBar-mode (team_class on filters, not aux).
- `tests/sanity/test_chip_direction_invariant.py:85-90`: same field
  move. Add `aus_ind_men_intl_2024_2025_filterbar_fm` row testing
  native chip alignment under symmetric FilterBar narrowing (no
  chip_team_class hint needed).

### 8.2 Regression (shell, hash diff)

Two no-drift contracts:

1. **Existing intl URLs without team_class** match HEAD hashes byte-
   identical post-migration. The new field defaults to None →
   response shape and content unchanged.
2. **Club URLs** match HEAD hashes byte-identical. The defensive
   backend gate ensures team_class is a no-op for `team_type='club'`.

**No `REG → NEW` flips** are required for this work — no existing URL
changes shape. All work is additive.

**New URL additions** (~125 across 10 suites, all tagged `NEW`):

- `tests/regression/teams/urls.txt` — 32 intl-FM URLs covering match
  list, summary, batting, bowling, fielding, partnerships, vs-opponent
- `tests/regression/scope-averages/urls.txt` — 14 intl-FM avg URLs
- `tests/regression/batting/urls.txt` — 10 intl-FM URLs
- `tests/regression/bowling/urls.txt` — 9 intl-FM URLs
- `tests/regression/fielding/urls.txt` — 13 intl-FM URLs
- `tests/regression/players/urls.txt` — 21 intl-FM URLs
- `tests/regression/head_to_head/urls.txt` — 9 intl-FM URLs
- `tests/regression/matches/urls.txt` — 3 intl-FM URLs
- `tests/regression/venues/urls.txt` — 7 intl-FM URLs
- `tests/regression/filterbar_refs/urls.txt` — 8 intl-FM URLs
  (covers `/tournaments` + `/seasons` + `/teams` typeahead scoped
  by team_class)

URL generation can be scripted: derive each NEW URL from its REG
sibling by appending `&team_class=full_member`. After commit 4
stabilises, flip these to REG in a follow-up commit.

### 8.3 Integration (shell, agent-browser)

**New scripts:**

- `tests/integration/team_class_filterbar.sh` — pill renders only on
  intl, hidden on club. Toggle on writes URL; toggle off removes;
  reset all clears; status strip chip appears; COPY LINK preserves
  team_class.
- `tests/integration/team_class_gating.sh` — switching team_type to
  club auto-clears team_class (replace mode, no history entry);
  switching to '' auto-clears; deep link
  `?team_class=full_member&team_type=club` cleans on mount.
- `tests/integration/team_class_persistence.sh` — toggle on /teams →
  navigate /batting → /series → /matches → /venues → /head-to-head;
  team_class survives on every navigation. Status strip mirrors.
- `tests/integration/team_class_per_tab_narrowing.sh` — for each of
  the surfaces in the matrix below, hit the page with team_class=on
  and team_class=off, capture key cell text, assert the FM-on numbers
  match SQL anchors and FM-off numbers match HEAD baseline.
- `tests/integration/teams_compare_intl_fm_default.sh` — Anchor E1
  (FilterBar on, all three columns narrow via inheritance, native
  chip alignment via filters.team_class on both sides).
- `tests/integration/teams_compare_club_no_op.sh` — Anchor G (RCB +
  __avg__ + SRH on IPL 2025, pill hidden, all numbers must equal HEAD
  baseline).

**Updates to existing scripts:**

- `tests/integration/compare_avg_chips.sh` — Anchor A unchanged;
  Anchor A' (per-slot FM avg via URL B) unchanged; **add Anchor E1**
  (FilterBar on, default inheritance).
- `tests/integration/compare_filters.sh` — add Anchor 6 (Mode E1).
- `tests/integration/cross_cutting_aux_filters.sh` — verify
  series_type tests continue to pass (no interaction with team_class).
- `tests/integration/cross_cutting_url_state.sh` — add team_class to
  the URL-state-sharing assertion list.

**Per-tab narrowing matrix** (covered by
`team_class_per_tab_narrowing.sh`):

| Tab / surface | FM-on assertion | Club-no-op assertion |
|---|---|---|
| /matches | Aus row count 22 → 16 (men_intl 2024-25) | RCB IPL 2025 row count unchanged |
| /teams (landing) | Associate tile counts shift; Scotland tile shows FM-only (=0) match count | Club tile counts unchanged |
| /teams?team=Australia → Match List | 22 → 16 | n/a (clubs hide pill) |
| /teams?team=Australia → Batting | RR / boundary% / fifties shift to FM-only stats | n/a |
| /teams?team=Australia → Bowling | Wickets / economy shift to FM-only | n/a |
| /teams?team=Australia → Fielding | Catches / dismissals shift | n/a |
| /teams?team=Australia → Partnerships | Best-pair / 50+ counts narrow | n/a |
| /teams?team=Australia → vs Opponent → Scotland | Match list goes to 0 with FM-on | n/a |
| /teams?team=Australia → Compare | Three columns narrow on FilterBar (E1) | n/a |
| /teams?team=Royal Challengers Bengaluru | (pill hidden on every subtab) | All numbers identical to HEAD |
| /series (landing) | ICC WC tile drops to FM-only count; India-vs-Scotland rivalry tile zeros out | Club franchise tiles unchanged |
| /series?tournament=ICC%20Men%27s%20T20%20World%20Cup | All inner stats narrow | n/a |
| /series?filter_team=India&filter_opponent=Scotland | Goes to 0 matches | n/a |
| /head-to-head?mode=team&team1=India&team2=Scotland | Goes to 0 matches | n/a |
| /head-to-head?mode=player&batter=Kohli&bowler=Boult | Per-ball aggregates exclude vs-associate work | n/a |
| /batting (leaders) | Top-10 reshuffles; associate-only batters drop | RCB/IPL leaders unchanged |
| /bowling (leaders) | Same | Same |
| /fielding (leaders) | Same | Same |
| /players (landing) | Curated tile stat strips reflect FM-narrowed counts | Club tile strips unchanged |
| /players?player=Kohli | Per-discipline numbers shift to FM-only | n/a |
| /players?player=Kohli&compare=Smith | Both columns narrow | n/a |
| /matches/:id | No-op (match identity is fixed) | No-op |
| /venues (landing) | Country-grouped counts narrow | Club venue counts unchanged |
| /venues?venue=Wankhede | Per-venue stats narrow | n/a |

22 surfaces × 2 assertions ≈ 44 cell-text checks. The matrix is
implemented as a single shell script with a per-row helper that takes
a URL, an FM-mode flag, a CSS selector, and an expected text/regex.

### 8.4 Capture-before-and-after (per-tab API URL audit)

**New script:** `tests/sanity/team_class_url_audit.py`. Two phases:

1. **BEFORE** — for each tab in the matrix, fire the page in
   agent-browser, capture every `/api/v1/` URL the page requested via
   `performance.getEntries()`. Save to
   `tests/sanity/team_class_pre_audit.json`.
2. **AFTER** — repeat with team_class=full_member on the URL. Save to
   `tests/sanity/team_class_post_audit.json`.
3. **DIFF** — for every URL in the AFTER set, assert it carries
   `team_class=full_member` as a query param. URLs missing the
   param are pages silently ignoring the filter — file as bugs.

The diff format flags two failure modes:

- "Page X fires URL Y but Y doesn't carry team_class" — backend
  endpoint not respecting the filter, or frontend dropping it before
  fetch.
- "Page X fires URL Y in BEFORE that's missing in AFTER (or vice
  versa)" — page-level conditional fetch path that depends on
  team_class. Investigate.

This is the single most load-bearing test for "no page silently
ignores the FilterBar." Run pre-flight, run after every commit.

---

## 9. Migration sequence

Five commits. The order is bounded — commits 1 and 2 are the only
behaviour-changing commits; commits 3-5 are tests + URL fan-out.

### Commit 1: backend move + sanity-test updates

- `api/filters.py` — `team_class` moves to `FilterBarParams` with
  defensive intl gate. Removed from `AuxParams`.
- `api/routers/teams.py::_league_aux` — refactor to take and return
  `(filters, aux)` tuple. Update 7 call sites.
- `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope` —
  rejection check on `filters.team_class`.
- `tests/sanity/test_avg_baseline_pools.py` — `make_aux` field move.
- `tests/sanity/test_avg_baseline_numbers.py` — `make_aux` field move
  + new FilterBar-mode row.
- `tests/sanity/test_chip_direction_invariant.py` — `make_aux` field
  move + new symmetric-FilterBar row.

**Pass criteria:** all sanity tests green, all regression suites 0
drift, all integration scripts pass.

### Commit 2: frontend FilterBar widget + Compare inheritance fix

- `frontend/src/components/scopeLinks.ts::FILTER_KEYS` — add
  `'team_class'`.
- `frontend/src/components/FilterBar.tsx` — pill widget, auto-clear
  effect, anyFilterSet + clearAll updates.
- `frontend/src/components/ScopeStatusStrip.tsx` — chip entry.
- `frontend/src/hooks/useCompareSlots.ts:50` — change `undefined` to
  `primary.team_class`. Update the comment.
- `frontend/src/components/teams/SlotScopeEditor.tsx` — primary
  fallback on init + diff-vs-primary on persist.
- `frontend/src/types.ts` — docstring update on `team_class`.

**Pass criteria:** browser-verify pill renders intl-only, hidden on
club; toggle writes URL; auto-clear on Type change; Compare grid
narrows on E1; URL A and URL B continue to behave identically to
pre-commit; URL G (RCB) unchanged.

### Commit 3: backend router fan-out

- `api/routers/tournaments.py::_build_filter_clauses` — add gated
  team_class branch. Affects 17 endpoints.
- `api/routers/reference.py::_reference_clauses` — add gated branch.
- `api/routers/reference.py::list_teams` — add gated where_part.

**Pass criteria:** Series tab regression URLs (when augmented with
team_class=full_member) return narrowed counts matching SQL anchors;
team typeahead in FM mode no longer surfaces associate teams; tournaments
+ seasons dropdowns narrow when team_class is on.

### Commit 4: regression URL additions

- ~125 new `NEW` URLs across 10 regression suites with
  `team_class=full_member` appended.

**Pass criteria:** all NEW hashes stable; 0 REG drift.

### Commit 5: tests + per-tab narrowing matrix

- `tests/sanity/test_team_class_baseline_numbers.py` (new, ~25 anchors).
- `tests/sanity/team_class_url_audit.py` (new, capture-before-and-after).
- 6 new integration scripts (§8.3).
- 4 updated integration scripts (§8.3).

**Pass criteria:** all integration scripts green; per-tab URL audit
shows zero pages silently ignoring the filter; SQL-vs-API anchors
match.

### Optional commit 6: regression flip

After 1-2 weeks of stable HEAD, flip the ~125 NEW entries to REG so
they become permanent guardrails.

### Abandonment criteria

- Commit 1 breaks any sanity test → fix or revert.
- Commit 2 has any visual regression at iPhone 13 width (390×844) →
  revert and re-design FilterBar layout. User has flagged mobile
  alignment three times in this session; sensitivity is high.
- Commit 3 shows numerical drift on ANY existing REG URL → bisect.
  This shouldn't happen (defensive gate keeps existing URLs unchanged)
  but indicates a logic bug in the gate if it does.
- Commit 4 shows NEW hash instability across two consecutive runs →
  non-deterministic backend code path; investigate before flipping to
  REG.

---

## 10. Out of scope

These belong in a sibling spec (`spec-slot-override-chip-alignment.md`)
and are NOT blocking for v3:

### 10.1 Override-to-empty URL serialization

`useUrlParam` / `useSetUrlParams` delete params when given a falsy
value. There is no way to write `compareN_team_class=''` (an explicit
empty value distinct from "no override") into the URL. This means a
slot cannot explicitly override-to-cleared while inheriting a non-
empty primary value.

For the team_class case: with FilterBar `team_class=full_member`, a
user cannot set the avg slot to "show unbounded baseline regardless"
— the per-slot URL grammar can't express it.

**Affects every overridable axis**, not just team_class. A user can't
override a slot's tournament to "(none, all tournaments)" while the
FilterBar has tournament set, either. The URL machinery needs a
sentinel value (e.g. `__any__`) mapped at the read site, or a
separate mechanism. Out of scope here.

### 10.2 Chip alignment under bidirectional override

Today's `chip_team_class` hint can narrow the team-side league
baseline (Mode B / URL B). It cannot broaden it. If a user overrides
the avg slot to differ from primary by removing a narrowing,
the chip on the team col baselines against primary's narrowing while
the avg col displays the broader pool — chip math contradicts displayed
avg.

**Same shape of problem applies to `season_from` / `tournament` /
`filter_venue` overrides**, each of which has the same chip-
alignment limitation. The fix is a generalised "compute league-side
baseline using slot's resolved scope, not request's filters" — out of
scope here.

### 10.3 Sibling spec — `spec-filterbar-series-type.md`

`series_type` should also be promoted from `AuxParams` to
`FilterBarParams` and join `FILTER_KEYS`. Same shape of work as v3,
independent rollout. Recommend doing team_class first (this spec),
series_type next session. Doing both in one session means 2× the
regression URL fan-out (~250 new URLs) and 2× the integration script
work.

---

## 11. Pre-flight checklist

Before any code change. Each item produces a committable artifact.

1. **Green run all existing tests** + spec drift check.
2. **Spawn DB-only subagent** (no `api/` reads) to derive the ~25
   anchor numbers from §7. Save as
   `internal_docs/team-class-anchor-numbers.md`. Commit on its own.
3. **Capture per-tab BEFORE snapshot.** Run the URL audit script with
   team_class OFF on every tab in §8.3 matrix. Save to
   `tests/sanity/team_class_pre_audit.json`. Commit.
4. **Sketch test scaffolding** — skeleton files for sanity, URL-audit,
   6 new integration scripts, regression URL generator. Per Phase D
   of the implementation plan.

After pre-flight green and ground-truth derived, start commit 1.

## 11.5. Pre-flight status (2026-04-28)

| Phase | Status | Artifact | Notes |
|---|---|---|---|
| A. Green baseline + spec drift | **DONE** | `internal_docs/team-class-v3-preflight-baseline.md` | 6/6 sanity green, 0 REG drift across 11 suites (~233 URLs), critical integration scripts green, 4 pre-existing test rot failures documented. Spec drift: zero commits to load-bearing files. |
| B. SQL ground truth (28 anchors) | **DONE** | `internal_docs/team-class-anchor-numbers.md` | DB-only subagent. 28 anchors derived (A1-A18 + 4 top-10 lists + C1-C4 + D1-D2 + B1-B4). Spec §7 narrative corrected: scope window is `('2024','2024/25','2025')`, A1=870 not 1196, A13=44 not 55, A16=0/0 not non-zero/0. Surprises documented in anchor file's "Surprises" section. |
| C. Per-tab BEFORE snapshot | **DONE** | `tests/sanity/team_class_pre_audit.json` | 24/24 surfaces captured, 0 failures, 0 surfaces with non-zero `diff_today` (confirms backend silently ignores team_class today — clean BEFORE state). Heaviest surfaces: Compare tabs at 82 URLs each. Used real player IDs (Kohli ba607b88, Smith 30a45b23, Boult a818c1be) and match 13057 (UAE-Nepal 2026-04-21). |
| D. Test scaffolding (sketches) | **DONE** | 9 skeleton files | `tests/sanity/test_team_class_baseline_numbers.py` (now populated with all 28 anchor numbers from Phase B), `tests/sanity/team_class_url_audit.py`, 6 integration scripts (filterbar / gating / persistence / per-tab-narrowing / compare E1 / compare club no-op), `tests/regression/team_class_url_gen.sh` (dry-run produces 121 NEW URLs across 10 suites). |
| E. Spec status update | **DONE** | This file + `project_next_session.md` memory | All 4 prior phases tracked. Commit 1 unblocked. |

All pre-flight phases DONE. Commit 1 (backend field move + sanity test
updates) is unblocked. Next session opens with `§9 Migration sequence`
commit 1.

---

## 12. Estimated effort

| Phase | Time | Notes |
|---|---|---|
| Pre-flight | 2h | Sanity + regression + integration green run, ground-truth derivation, BEFORE snapshot |
| Commit 1 | 1.5h | Backend field move + `_league_aux` tuple refactor + 7 call sites + 3 sanity test updates |
| Commit 2 | 2h | FilterBar widget + status strip + useCompareSlots one-liner + SlotScopeEditor fallback fixes + browser verification at desktop and mobile widths |
| Commit 3 | 1h | tournaments.py + reference.py edits — small surface, agent-browser verify on Series tab + typeahead |
| Commit 4 | 1.5h | Mechanical URL generation + regression run × 10 suites |
| Commit 5 | 3h | Sanity test (~25 anchors) + URL audit script + 6 new integration scripts + 4 script updates |
| **Total** | **~11h focused work** | |

Risk: medium. The mental-model correction collapses v2's complexity,
but ~125 regression URLs + 22-surface integration matrix + URL audit
script is still substantial mechanical work.

---

## 13. Discipline carried forward

- Commit after every feature (no batching across commits 1-5).
- DB-direct ground truth via subagent that hasn't read `api/` source
  (pre-flight discipline from 2026-04-27 chip-baseline work).
- No CSS-pixel shortcuts in the FilterBar widget (mobile flex-wrap
  is the structural fix; min-width hacks are not).
- `internal_docs/links.md` rules apply for any new navigation work
  (none anticipated in this rollout).
- Pre-flight `wal_checkpoint(TRUNCATE)` is in deploy.sh; do NOT edit
  cricket.db while a deploy is in flight.

---

*Spec v3 — 2026-04-28. Replaces v2 entirely. Pick up next session per §11.*
