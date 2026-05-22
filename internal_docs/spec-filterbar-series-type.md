# Spec — `series_type` on the FilterBar

> **Status:** SHIPPED. `series_type` is the 10th FilterBar key
> (`api/filters.py:70-71`, `FilterBar.tsx:271`); typeahead respects it
> per commit `fbcd953` ("list_teams typeahead — apply series_type
> clause"). Mirrors `spec-filterbar-team-class-v3.md` structurally —
> this spec was shorter because most per-slot plumbing
> (`useCompareSlots.inheritedScope`, `OVERRIDABLE_SLOT_KEYS`) already
> existed at spec-write time.

Promote `series_type` from `AuxParams` to `FilterBarParams` so it
becomes the **10th FilterBar key** alongside `team_class` (the
9th, shipped 2026-04-28). Today it's a Series-tab-local pill that
propagates via `useFilters` as a special case; the FilterBar
widget proper doesn't surface it. After this spec it behaves as a
peer of every other overridable axis with default-then-override
semantics.

---

## 1. Why now

`series_type` (`all` / `bilateral_only` / `tournament_only` —
plus the legacy `bilateral` / `icc` / `club` aliases) is already a
useful global narrowing. Today:

- The Series tab has a "Show" pill that toggles it, scoped to
  that tab only on the surface but actually propagating
  everywhere via `useFilters`'s special-case read at line 31-32.
- The FilterBar widget itself doesn't render it — the user has
  no way to set it on /teams or /batting unless they navigate
  through Series first or hand-edit the URL.
- It IS in `OVERRIDABLE_SLOT_KEYS` and `inheritedScope` already
  passes it from primary to compare slots, so the per-slot
  override path works.

Promoting unifies the contract: every narrowing axis the user
controls lives in one place (the FilterBar) and rides through
every tab uniformly.

---

## 2. Mental model

Same as v3 team_class: one axis with default flow + per-slot
override. Three roles in Compare:

| Column | Source | Override mechanism |
|---|---|---|
| Primary | Path team + FilterBar | None — primary IS FilterBar |
| Compare slot 1 | Inherits primary | URL `compareN_series_type=...` |
| Compare slot 2 | Inherits primary | URL `compareN_series_type=...` |

Bound axes (`gender`, `team_type`) stay unchanged. Overridable
axes after this spec: `tournament`, `season_from`, `season_to`,
`filter_venue`, `team_class`, **`series_type`**.

---

## 3. Gating

`series_type` has no team-type gate (unlike team_class which is
intl-only). It applies to ALL scopes — bilateral t20 series exist
in both internationals (Eng tour of WI) and clubs would
conceptually be "domestic series" though that mapping is
imperfect today.

For `series_type='bilateral_only'` on club scopes, the SQL clause
narrows to bilateral-style events but most club tournaments are
multi-team leagues, so the result tends to be near-empty. UX:
let it ride; the user will see the empty result and back out.

No defensive backend gate beyond the existing
`series_type_clause` returning empty-string for unknown values.

---

## 4. Surface changes

### 4.1 FilterBar widget

Today there's no FilterBar widget. Add a segmented control
between `team_class` (intl-only pill) and `Venue`:

```
[Tournament ▾] [▢ FM only]   [Show: All ▾]   [📍 Venue …]   [Seasons …]
                              └── 4-state segmented control
```

Options:
- **All** (no filter — default, removes URL param)
- **Bilateral**
- **ICC events**
- **Club tournaments**

Implementation: a `<select>` (consistent with Tournament dropdown)
or a 4-button segmented control (consistent with Type / Gender).
Recommend `<select>` to keep the FilterBar visually compact —
4 segmented buttons would crowd the row, especially on mobile.

`series_type=bilateral_only` URL value displays as "Bilateral";
canonicalize on read so legacy URLs (`bilateral` / `icc` /
`club`) still work — same approach `series_type_clause` already
takes.

### 4.2 ScopeStatusStrip

Today the strip surfaces `series_type` as a "Show:" sub-line
(distinct from the regular chip strip). With promotion, it
becomes a regular chip alongside the other FilterBar fields:

```
SHOWING: gender: men's · type: international · series: bilateral · ...
```

Drop the special "Show:" sub-line; everything is one chip strip.

### 4.3 useFilters

Today reads `series_type` as a special case (lines 27-32).
After promotion, `FILTER_KEYS` already covers it via the
existing iterate. **Remove** the special-case read so the
single source of truth is `FILTER_KEYS`.

### 4.4 useCompareSlots / SlotScopeEditor

Already work. `inheritedScope` already passes
`primary.series_type` (not undefined). `OVERRIDABLE_SLOT_KEYS`
already includes it. `SlotScopeEditor` already has a Series
dropdown. **Zero edits.**

### 4.5 Scope-link URLs (TeamLink / PlayerLink / SeriesLink)

Already ride `series_type` through because `FILTER_KEYS` is
where the URL builders iterate. **Zero edits.**

---

## 5. Backend changes

Three files. Most edits are 1-3 lines.

### 5.1 `api/filters.py`

- **Add** `series_type` to `FilterBarParams.__init__` as a Query
  field. Description: "Page-local narrowing: all (default) /
  bilateral / icc / club. Legacy aliases: bilateral_only /
  tournament_only."
- **Set** `self.series_type = series_type`.
- **In `build()`**, move the `aux.series_type` clause to read
  from `self.series_type` (or both — keep aux read for
  back-compat during migration, prefer self).
- **Remove** `series_type` field from `AuxParams` and its
  storage line. Only `chip_team_class` and `scope_to_team`
  remain in AuxParams.
- **Keep** `AuxParams` itself — `chip_team_class` and
  `scope_to_team` are still aux-only.

Equivalent of v3 commit 1's field move.

### 5.2 `api/routers/teams.py::_league_aux`

Already returns `(filters, aux)` tuple after v3. The synthesis
steps inside don't reference `series_type`. **Zero edits.**

### 5.3 `api/routers/bucket_baseline_dispatch.py::is_precomputed_scope`

Today rejects when `aux.series_type and aux.series_type != "all"`.
Change to read from `filters.series_type`. Same rejection logic.
Bucket tables don't carry the series_type dimension, so live
aggregation is the fallback when set.

### 5.4 Hand-rolled filter helpers — MOSTLY ALREADY WIRED

Verified via curl 2026-04-28: `/tournaments` already narrows
under `series_type` — 128 unbounded → 126 bilateral_only → 2 icc
on men_intl 2024-25. The plumbing was added when series_type was
introduced via AuxParams, predating this spec.

What's already wired:
- `reference.py::_reference_clauses` accepts `series_type` and
  applies `series_type_clause`. Drives `/tournaments` + `/seasons`
  dropdown narrowing. ✓
- `reference.py::list_teams` — passes through via FilterBarParams
  build path. ✓
- `tournaments.py` Series-tab endpoints — use
  `_tournament_scope_where()` which already takes `series_type`.
  ✓ (Note: `_build_filter_clauses` in the same file does NOT
  take series_type, but the endpoints that use it — landing,
  by-season — don't need series_type narrowing because the
  enclosing tournament context already determines series-type
  identity.)
- Frontend `FilterBar.tsx` already passes `series_type` from URL
  to `getTournaments` / `getSeasons` calls. ✓

What's NOT wired and matters: `list_teams` in `reference.py`
should still apply series_type via the `aux` flow (today it
takes `filters: FilterParams = Depends()` only — no aux).
Verify whether the typeahead narrowing is needed; if a user
sets series_type=bilateral_only they'd want the team typeahead
to drop teams that only appear in tournaments. Edge case; may
not be worth the wire unless flagged.

**Update 2026-04-28** — flagged + fixed same-session.
`list_teams` reads `filters.series_type` directly (no aux needed
post-promotion) and applies `_series_type_clause` alongside the
`team_class` defensive gate. The fix is one ~5-line block;
typeahead narrows 100 → 27 under `series_type=icc` on men_intl
2024-25, with row counts also narrowing (Scotland 17 → 4).
Regression assertion landed in
`tests/integration/series_type_per_tab_narrowing.sh::Test 7`.

Net work in this commit: zero or near-zero edits. Most of
"commit 3" work in this spec is verification, not editing.

---

## 6. Frontend changes

Four files; most edits 1-3 lines.

### 6.1 `frontend/src/components/scopeLinks.ts::FILTER_KEYS`

Append `'series_type'`:

```ts
export const FILTER_KEYS = [
  'gender', 'team_type', 'tournament',
  'season_from', 'season_to',
  'filter_team', 'filter_opponent', 'filter_venue',
  'team_class', 'series_type',
] as const
```

Auto-rides through `useFilters`, scope-link URL builders,
`useFilterDeps`. **One line.**

### 6.2 `frontend/src/hooks/useFilters.ts`

**Remove** the special-case `series_type` read (lines 27-32) —
`FILTER_KEYS` now covers it. Net removal.

### 6.3 `frontend/src/components/FilterBar.tsx`

Add the widget. Either a `<select>` next to Tournament/Venue
(~10 lines) or a segmented control (~20 lines). `<select>`
recommended for compactness:

```tsx
const seriesType = params.get('series_type') || ''

<div className="wisden-filter-group">
  <span className="wisden-filter-label">Show</span>
  <select
    value={seriesType}
    onChange={e => set('series_type', e.target.value)}
    className="wisden-select"
  >
    <option value="">All matches</option>
    <option value="bilateral_only">Bilateral series</option>
    <option value="tournament_only">Tournaments only</option>
    <option value="icc">ICC events</option>
    <option value="club">Club tournaments</option>
  </select>
</div>
```

Verify the canonical option values — they MUST match what
`series_type_clause` accepts. Cross-check against
`tournament_canonical.py::series_type_clause` before commit.

Update `anyFilterSet` and `clearAll` to include series_type.

No auto-clear effect needed (series_type doesn't have a
team_type gate).

### 6.4 `frontend/src/components/ScopeStatusStrip.tsx`

Remove the special "Show: <label>" sub-line code (lines around
86-91 — find the `seriesType && seriesType !== 'all'` branch).
Replace with a regular chip:

```ts
if (filters.series_type && filters.series_type !== 'all') {
  segs.push({ label: 'Series', value: <pretty-label> })
}
```

Pretty-label map:
- `bilateral_only` / `bilateral` → "bilateral"
- `tournament_only` → "tournaments only"
- `icc` → "ICC events"
- `club` → "club tournaments"

### 6.5 `frontend/src/components/teams/SlotScopeEditor.tsx`

Already has a Series dropdown (lines around 109-117).
Already passes `primary.series_type` as initial fallback.
**Zero edits.**

---

## 7. SQL ground truth

`series_type_clause` already implemented in
`tournament_canonical.py`. Pre-flight: derive ~10 anchor counts
for the test matrix.

Closed scope: men's intl 2024-25.

| Anchor | Description | Result |
|---|---|---|
| S1 | Total men_intl 24-25 (no series_type) | 870 (per-team avg 17.4) |
| S2 | bilateral_only | TBD — derive |
| S3 | tournament_only / icc | TBD — derive |
| S4 | + tournament=T20 WC + bilateral_only | 0 (WC is ICC, no bilaterals in scope) |
| S5 | + tournament=T20 WC + icc | 44 (WC is ICC) |
| S6 | filter_team=India + bilateral_only | TBD |
| S7 | + filter_opponent=Aus + bilateral_only | TBD |
| S8 | women_intl 24-25 + bilateral_only | TBD |
| S9 | club + bilateral_only (near-empty edge case) | TBD |
| S10 | scope_to_team=Aus + bilateral_only | TBD |

Pre-flight subagent runs against the same window as v3.
Document in `internal_docs/series-type-anchor-numbers.md`.

---

## 8. Test plan

Exact mirror of v3 §8.

### 8.1 Sanity

`tests/sanity/test_series_type_baseline_numbers.py` (NEW) —
pin all S1-S10 anchors via SQL-vs-API. Same pattern as
`test_team_class_baseline_numbers.py`.

`tests/sanity/test_chip_direction_invariant.py` — gains an
`aus_ind_men_intl_2024_2025_filterbar_bilat` SCOPE row testing
chip alignment under FilterBar series_type=bilateral.

### 8.2 Regression

Same workflow as v3 commit 4. ~125 NEW URLs across 10 suites
generated by mirroring intl REG URLs with `&series_type=bilateral_only`.
Reuse `tests/regression/team_class_url_gen.sh` as a template
or create a sibling `series_type_url_gen.sh`.

No REG → NEW flips required (additive — existing URLs without
series_type stay byte-identical).

### 8.3 Integration

`tests/integration/series_type_filterbar.sh` (NEW) — widget
rendering, toggle, URL plumbing, status strip. Same shape as
`team_class_filterbar.sh`.

`tests/integration/series_type_persistence.sh` (NEW) — survives
across all 9 tabs.

`tests/integration/series_type_per_tab_narrowing.sh` (NEW) —
API-direct narrowing checks. Bilateral filter on /teams,
/series, etc. should reduce match counts.

`tests/integration/cross_cutting_aux_filters.sh` — already
tests series_type. Verify it still passes (it should — the
backend math doesn't change). The test currently checks via
URL params which mirror what the new pill writes, so it's
pre-validated.

### 8.4 URL audit

`tests/sanity/series_type_url_audit.py` mirroring
`team_class_url_audit.py`. Capture BEFORE (today) + AFTER
(post-promotion). Expectation: every page-fetched URL with
`series_type` set on FilterBar carries the param to every
backend endpoint.

---

## 9. Migration sequence

5 commits, mirroring v3:

1. **Backend field move + sanity-test updates.** `series_type`
   moves to `FilterBarParams`. Remove from `AuxParams`. Update
   `is_precomputed_scope`. Update any `make_aux(series_type=...)`
   call sites in tests to use `make_filters` instead.
2. **Frontend FilterBar widget + cleanup.** `FILTER_KEYS`
   extends to 10. `<select>` widget. ScopeStatusStrip chip
   replaces "Show:" sub-line. Remove `useFilters` special-case
   read. `anyFilterSet` + `clearAll` updates.
3. **Backend router fan-out — verification only (likely zero
   edits).** All hand-rolled helpers already apply series_type;
   curl-verified 2026-04-28. Only edit if a specific gap surfaces
   during the per-tab narrowing matrix run.
4. **Regression URL additions.** ~125 NEW URLs across 10 suites.
5. **Tests.** Sanity + URL audit + integration scripts.

Estimated effort: ~5-6h (smaller than the original ~8h estimate
because curl-verification 2026-04-28 confirmed the dropdown
narrowing is already in production — the work is mostly the
FilterBar widget + ScopeStatusStrip cleanup + the field move).

---

## 10. Out of scope

- Bidirectional override + override-to-empty (parked in
  `spec-slot-override-chip-alignment.md`). Same limitations as
  v3.
- Renaming `series_type` values to be more user-readable in the
  URL (e.g. `bilateral_only` → `bilaterals`). Backwards-compat
  burden; defer.
- Removing the legacy `bilateral` / `icc` / `club` aliases.
  Deferred — the canonicalization in `series_type_clause` handles
  both forms.

---

## 11. Pre-flight checklist

1. Green run all existing tests + spec drift check.
2. DB-only subagent derives S1-S10 anchor numbers. Save as
   `internal_docs/series-type-anchor-numbers.md`.
3. Capture BEFORE URL audit snapshot
   (`tests/sanity/series_type_pre_audit.json`).
4. Sketch test scaffolding (sanity + URL audit + integration
   scripts).

After pre-flight green, start commit 1.

---

## 12. Why this is mechanical (vs v3 which had a real bug)

v3 contained a literal `useCompareSlots:50` one-line bug
(`team_class: undefined`) that the corrected mental model
exposed. Series_type doesn't have an analogous bug — the
inheritance was already plumbed correctly. So this spec is
~80% mechanical refactor + UI widget addition.

The novelty is just: `series_type` becomes a first-class
FilterBar field instead of a Series-tab-local-with-bleed.

---

*Spec written 2026-04-28 alongside team_class v3. Pick up next
session per §11.*
