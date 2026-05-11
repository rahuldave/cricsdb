# Spec — Splits Mosaic (toss × inning × outcome conditioning, Teams)

**Status:** DRAFT — 2026-05-11.

**Scope of THIS spec:** Teams tab only (landing + team-detail). Player
splits and H2H splits are explicitly out of scope; future specs build
on this one. Compare-slot integration also deferred.

**What it introduces:**

1. Two new aux filter axes: `result` (won/lost/tied) and
   `toss_outcome` (won/lost), composed with existing `inning`.
2. A new endpoint `/api/v1/teams/splits` returning the joint
   distribution across the three axes, with dual-query envelope
   (team-side + league-side baseline + per-cell deltas) — same
   pattern as existing `/summary` endpoints.
3. A `SplitsMosaic` React component rendering the joint
   distribution as a dimensionality-adaptive mosaic, with marginals
   and cells doubling as URL-aware filter controls.

All state is in URL. The widget reads which of `{result,
toss_outcome, inning}` are URL-set and renders the rest. No
localStorage. No collapsed/expanded toggle — the chart's shape IS
the URL state.

---

## Stage 1 — Backend

### 1.1 Aux filter axes

#### `result`

- URL: `?result=won|lost|tied`
- AuxParam (not in `FILTER_KEYS`)
- Semantics: match outcome from subject team's POV
  - `won` — `outcome_winner = :team`
  - `lost` — `outcome_winner != :team AND outcome_winner IS NOT NULL`
  - `tied` — `outcome_winner IS NULL` (tied + no-result collapsed; T20 ties go to super-over and that winner becomes `outcome_winner`, so a NULL is almost exclusively rain-shortened)

SQL clause (added to team router's `_apply_filters`):
```sql
AND (CASE WHEN m.outcome_winner = :team THEN 'won'
          WHEN m.outcome_winner IS NULL THEN 'tied'
          ELSE 'lost' END) = :result
```

#### `toss_outcome`

- URL: `?toss_outcome=won|lost`
- AuxParam
- Semantics: did subject team win the toss?

SQL clause:
```sql
AND m.toss_winner IS NOT NULL
AND (CASE WHEN m.toss_winner = :team THEN 'won' ELSE 'lost' END) = :toss_outcome
```

#### `inning` (existing — included for completeness)

- URL: `?inning=1|2`
- Already plumbed. Semantics: subject team batted first (1) or second (2).
- No backend changes needed; folded into this spec because it
  participates in the joint distribution.

#### Subject-POV requirement

`result` and `toss_outcome` require a canonical team subject. On
the unfiltered `/teams/splits` (no `?team=`), they STILL apply —
filtering across all teams collapses to "matches where any team
won", which is degenerate. The endpoint resolution: when `?team=`
is absent, `result` and `toss_outcome` are silently dropped (return
400 with `detail: "result and toss_outcome require ?team="` to make
the asymmetry explicit).

#### DLS, super-over, substitute exclusions

- DLS-truncated chases: included, count as 1 match each (per
  CLAUDE.md DLS rule).
- Super-overs: outcome already in `outcome_winner`; no special
  handling.
- Substitute fielders: N/A at team grain (substitute filtering is
  a player-grain concern; deferred to player spec).

### 1.2 Plumbing into existing team-router endpoints

Every team-router endpoint that takes `FilterParams` honors the
new aux axes via `_apply_filters` (or equivalent helper). Concrete
endpoints touched:

- `/api/v1/teams/summary`
- `/api/v1/teams/{team}/summary`
- `/api/v1/teams/{team}/batting/summary`
- `/api/v1/teams/{team}/bowling/summary`
- `/api/v1/teams/{team}/fielding/summary`
- `/api/v1/teams/{team}/batting/distribution`
- `/api/v1/teams/{team}/bowling/distribution`
- `/api/v1/teams/{team}/fielding/distribution`
- Per-season / opponent / leader endpoints under the same router
- `/api/v1/seasons` (subject-aware seasons array — narrows the
  range when filters apply)

Audit step: grep every consumer of `FilterParams` in `api/routers/`
and verify the aux axes flow through. Per CLAUDE.md "audit
FilterParams when extending scope helpers".

### 1.3 New endpoint — `GET /api/v1/teams/splits`

**Query params:**
- Standard FilterParams: `gender`, `team_type`, `tournament`,
  `season_from`, `season_to`, `filter_venue`, `series_type`,
  `team_class`
- `team` (optional) — when present, response includes team-side
  cells + per-cell deltas vs the league baseline at the same filter
  scope
- Aux axes: `result`, `toss_outcome`, `inning` — when set, the
  endpoint pre-filters cells server-side. The returned `cells[]`
  contains only cells matching the filter. (Frontend uses this
  fact: when 3 axes are filtered, exactly 1 cell comes back.)

**Response shape — landing (no `?team=`):**

```json
{
  "subject": null,
  "scope_total_n": 1840,
  "cells": [
    {
      "toss_outcome": "won",
      "inning": 1,
      "result": "won",
      "n": 312,
      "share": 0.170,
      "wilson_lo": 0.154,
      "wilson_hi": 0.187
    }
    // … up to 12 cells
  ],
  "marginals": {
    "toss_outcome": {
      "won":  { "n": 950, "share": 0.516, "wilson_lo": 0.494, "wilson_hi": 0.539 },
      "lost": { "n": 890, "share": 0.484, "wilson_lo": 0.461, "wilson_hi": 0.506 }
    },
    "inning":       { "1": { "n": 920, "share": 0.500, ... }, "2": { "n": 920, "share": 0.500, ... } },
    "result":       { "won": { "n": 920, "share": 0.500, ... }, "tied": { "n": 35, ... }, "lost": { "n": 885, ... } }
  }
}
```

Note: the all-teams `result.won` ≈ `result.lost` by definition (every
match has one winner and one loser per match — but at the team-match
grain there are 2 team-matches per match, so the totals match by
construction). Tied counts as ½ per team. Document this in the
endpoint docstring.

**Response shape — team-detail (`?team=Mumbai+Indians`):**

```json
{
  "subject": { "team": "Mumbai Indians" },
  "scope_total_n": 145,
  "league_total_n": 1840,
  "cells": [
    {
      "toss_outcome": "won",
      "inning": 1,
      "result": "won",
      "n": 42,
      "share": 0.290,
      "wilson_lo": 0.220,
      "wilson_hi": 0.370,
      "league_share": 0.170,
      "delta": 0.120,
      "delta_pct": 70.6
    }
    // … up to 12 cells
  ],
  "marginals": {
    "toss_outcome": {
      "won":  { "n": 80, "share": 0.552, "league_share": 0.516,
                "delta": 0.036, "delta_pct": 7.0,
                "wilson_lo": 0.469, "wilson_hi": 0.631 },
      "lost": { "n": 65, "share": 0.448, "league_share": 0.484, ... }
    },
    "inning":  { ... },
    "result":  { ... }
  }
}
```

Key envelope fields when `?team=` set:
- `share` — n / scope_total_n (subject team's conditional probability)
- `league_share` — n_all_teams / league_total_n at the same filter scope (baseline)
- `delta` — `share - league_share`
- `delta_pct` — `(share - league_share) / league_share × 100` (relative %)
- `wilson_lo` / `wilson_hi` — 95% Wilson CI on `share`

Every cell AND every marginal carries the envelope. Frontend renders
deltas as `↑ 70.6%` / `↓ 7.0%` arrows next to the count.

### 1.4 Dual-query envelope SQL pattern

Matches the existing `/summary` endpoint pattern (CLAUDE.md
"Integration tests anchor against /summary's scope_avg"). Single
backend function runs two SQL queries:

1. **League side** (`team` argument = None):
```sql
SELECT
  CASE WHEN tw.team_view = m.toss_winner THEN 'won' ELSE 'lost' END AS toss_outcome,
  /* batting first / second from team_view's POV */
  CASE WHEN (m.toss_decision = 'bat' AND m.toss_winner = tw.team_view)
         OR (m.toss_decision = 'field' AND m.toss_winner <> tw.team_view)
       THEN 1 ELSE 2 END AS team_inning,
  CASE WHEN m.outcome_winner = tw.team_view THEN 'won'
       WHEN m.outcome_winner IS NULL THEN 'tied'
       ELSE 'lost' END AS result,
  COUNT(*) AS n
FROM match m
CROSS JOIN team_view tw     /* unpivots m.team1 + m.team2 into one column */
WHERE m.toss_winner IS NOT NULL
  AND {standard filter clauses}
  AND {aux filter clauses}
GROUP BY toss_outcome, team_inning, result;
```

`team_view` is a CTE that unpivots each match into two rows (one
per team), so the total cell count is 2 × match_count. This is the
clean way to compute the league baseline — each team contributes
its own POV to the joint distribution.

2. **Team side** (`team` argument = `:team`):
```sql
/* Same as above but WHERE (m.team1 = :team OR m.team2 = :team)
   and tw.team_view = :team (filter the unpivot to one POV) */
```

The endpoint runs query 1 always (for the league baseline). When
`?team=` is set, it also runs query 2 and joins the two result
sets cell-by-cell to compute deltas.

Wilson CIs computed in Python after the queries using the existing
`prob_record` helper (per `spec-distribution-stats §15`).

### 1.5 Endpoint file structure

New file: `api/routers/team_splits.py` containing the `/teams/splits`
route. Single endpoint, single file, ~150 LOC including SQL. Mount
under the existing `/api/v1/teams` prefix in `api/app.py`.

### 1.6 Backend tests

#### Sanity (Python — `tests/sanity/test_team_splits.py`)

For 3 representative teams across cricket variants:
- MI (men/club/T20, IPL)
- Australia women (women/intl/T20)
- A small-sample team like Sri Lanka women (verify low-n handling)

Assertions for each subject:
- `sum(cells[].n) == scope_total_n`
- `cells[].n` matches a SQL-direct group-by count
- `marginals.toss_outcome.won.n + marginals.toss_outcome.lost.n == scope_total_n`
- Same for `inning` and `result` (with `tied` counted)
- Wilson CIs bracket the point estimate
- Setting `?result=won` returns only `result=won` cells; sum
  matches `marginals.result.won.n` from the unfiltered call
- League-side and team-side query results consistent:
  `team.scope_total_n` matches `COUNT(*) FROM match WHERE (team1=:t OR team2=:t)`

For the landing case (no `?team=`):
- `scope_total_n` equals 2 × distinct-match count (because
  `team_view` unpivots each match)
- Setting `?result=won` and `?toss_outcome=won` together returns
  expected cell count from a direct SQL query

Convention-3 / DLS:
- `tests/sanity/test_predicate_invariants.py::test_splits_dls_included`
  asserts DLS-truncated chases appear in the cell counts
  (count matches by `target_overs < 20` from /splits matches the
  same predicate from a direct SQL query)

Endpoint asymmetry:
- 400 when `?result=won` set with no `?team=`
- 400 when `?toss_outcome=won` set with no `?team=`

#### Regression (HEAD-vs-patched md5 diff)

New URL inventory at `tests/regression/team_splits/urls.txt`:
- 6 landing-page URLs (varying filters)
- 6 team-detail URLs (3 teams × 2 filter states each)
- 4 URLs with various aux-axis filters set (verify shape doesn't drift)

Tagged `NEW` for first commit (then flipped to `REG` once stable).

### 1.7 Backend docs

After backend ships:

- **`docs/api.md`** — new section for `/api/v1/teams/splits`:
  - Path, one-line description
  - Query params (full list, with aux axes)
  - Curl example (real, captured live)
  - Abbreviated JSON response (landing + team-detail variants)
  - The 400-on-aux-without-subject behavior

- **`internal_docs/codebase-tour.md`** — append `team_splits.py` to
  the router summary.

- **`internal_docs/how-stats-calculated.md`** — new entry
  "Splits Mosaic: result + toss_outcome filter semantics", covering:
  - Team POV definitions
  - Tied-vs-NR collapse rationale
  - DLS treatment (included, count as 1)
  - The `team_view` unpivot pattern for league baseline

- **`internal_docs/design-decisions.md`** — entries:
  - "`result` and `toss_outcome` are AuxParams, not FILTER_KEYS"
  - "Splits endpoint requires `?team=` for aux filters
    (400 otherwise) — degenerate semantics avoided"
  - "League baseline in /splits uses team_view unpivot — every
    match contributes 2 team-matches"

- **`internal_docs/url-state.md`** — list new AuxParams.

- **`internal_docs/server-vs-client-calcs.md`** — new entry for
  splits cells + deltas (computed server-side; Wilson CIs in
  Python).

---

## Stage 2 — Frontend

### 2.1 AuxParams + scope helpers

Add to `frontend/src/types.ts`:
```ts
export interface AuxParams {
  // … existing fields
  result?:        'won' | 'lost' | 'tied'
  toss_outcome?:  'won' | 'lost'
}
```

Update three scope helpers in lockstep (per CLAUDE.md "audit
FilterParams when extending scope helpers"):

- `frontend/src/components/scopeLinks.ts::abbreviateScope` — extend
  to include `result` and `toss_outcome` in the abbreviated tag
  (e.g. "T20 men · won toss · batted first · won")
- `frontend/src/components/ScopeStatusStrip.tsx` — same axes emit
  status-strip segments
- `frontend/src/hooks/useFilters.ts` — pick up the aux params from
  URL via `useUrlParam`

The `_t` (timestamp) refetch suffix on team-page distribution
panels picks up new params automatically (already keys on the full
URL).

### 2.2 `WISDEN_WL` palette block

Add to `frontend/src/components/charts/palette.ts`:

```ts
/**
 * Traffic-light W/L palette for the Splits Mosaic.
 *
 *   WON   = muted green — won the match (traffic-go)
 *   TIED  = muted amber — tied / no-result
 *   LOST  = brick red   — lost
 *
 * Reserved for outcome encoding in the Splits Mosaic only.
 * NOT used elsewhere: the indigo/sage/ochre tier palette owns
 * metric magnitude tiers; oxblood owns the rolling-mean overlay.
 * Reds are deliberately avoided as fills elsewhere in the codebase
 * — the traffic-light vocabulary is familiar and reserved here
 * so a viewer reading the mosaic immediately recognizes "wins /
 * ties / losses" without needing a legend key.
 *
 * Hexes muted for cream (#FAF7F0) background. RED distinct from
 * oxblood (#7A1F1F) so a W/L cell and a rolling-mean overlay
 * never visually collide.
 */
export const WISDEN_WL = {
  won:   '#4B7A3B',  // muted green, brighter than forest #3F7A4D (league-avg stroke)
  tied:  '#C9A636',  // muted amber, yellower than ochre #C9871F
  lost:  '#B85450',  // brick red, distinct from oxblood
} as const
```

### 2.3 `SplitsMosaic` component

New file: `frontend/src/components/SplitsMosaic.tsx`. Props:

```ts
interface SplitsMosaicProps {
  data: SplitsResponse        // from /api/v1/teams/splits
  filters: FilterParams       // for sub-link URL building
  aux: AuxParams              // current aux state (drives dimensionality)
  hasSubject: boolean         // true on team-detail, false on landing
}
```

#### Dimensionality from URL — no internal state

The component reads how many of `{result, toss_outcome, inning}`
are URL-set and renders the corresponding layout. No props, no
state for "expanded/collapsed", no localStorage. The URL state IS
the chart shape.

| Free axes | Layout |
|---|---|
| 3 (none filtered) | 2×2 of (toss × inning), each cell sub-divided into traffic-light outcome sub-rects |
| 2 | 2×2 of the two free axes; cells single-color if outcome is filtered, OR W/T/L fills if outcome is one of the free axes |
| 1 | 1D horizontal stacked bar over the one free axis |
| 0 (all filtered) | Status strip only — no chart |

#### Fixed axis ordering

When free, axes always assigned in this order:
1. `toss_outcome` → outer column split (X)
2. `inning` → inner row split (Y) within column
3. `result` → innermost (cell-internal sub-rects + color)

`result` always owns the color slot. Toss and inning are always
spatially encoded. If `result` is filtered, color drops out
entirely (uniform-neutral cells); we never promote toss or inning
to a color encoding. This is the "what if something else is 3rd
dim" prevention from the design discussion.

### 2.4 Cell content (with deltas when subject set)

Each outer cell renders:

- **Top line**: count (e.g. `42`)
- **Bottom line**: share within parent grouping (column for 2×2,
  whole for 1D), as a %
- **When `hasSubject` is true**: a delta arrow + relative % vs
  league baseline (`↑ 70.6%` or `↓ 7.0%`); positioned right of the
  share

```
┌─────────────────────┐
│  42                 │
│  64% of WT          │
│  ↑ 70.6% vs league  │
└─────────────────────┘
```

Outcome sub-rects inside a cell carry their own deltas (visible
on hover only — the cell label is the 2D aggregate).

Marginal labels (column header / row label / outcome legend)
also display a delta when subject set:

- "Won toss · 55% · ↑ 7.0% vs league"

### 2.5 Click behavior

Three click surfaces, all URL-aware via `useUrlParam`:

1. **Marginal label** → sets ONE axis
   - "Won toss" → `?toss_outcome=won`
   - "Batted first" → `?inning=1`
   - Green outcome swatch → `?result=won`

2. **Outer cell** → sets axes free in the chart at the cell's coordinates
   - 3 free axes: cell click sets `toss_outcome` + `inning` (sub-rect handles `result`)
   - 2 free axes: cell click sets both

3. **Outcome sub-rect inside cell** → sets ALL THREE axes
   - Click green sub-rect in upper-left cell → `?toss_outcome=won&inning=1&result=won`

Browser-back undoes any URL write. No confirm dialog. The chart
shape changes on the next render to match the new URL state.

### 2.6 Verbose status-strip vocabulary

Always-rendered status line above the chart. Scales with filter
density:

| Filters set | Strip text |
|---|---|
| 0 | `All 145 matches` |
| 1 (`result=won`) | `Of 92 wins:` |
| 1 (`toss_outcome=won`) | `Of 80 toss wins:` |
| 1 (`inning=1`) | `Of 70 matches batting first:` |
| 2 (`result=won` + `inning=1`) | `Of 58 wins after batting first:` |
| 2 (`result=won` + `toss_outcome=won`) | `Of 64 wins after winning the toss:` |
| 2 (`toss_outcome=won` + `inning=1`) | `Of 42 matches batting first after winning the toss:` |
| 3 (all) | `Won toss · Batted first · Won the game — 42 matches` |

Vocabulary (used in strip, marginals, legend, tooltips):

| Axis | Value | Label |
|---|---|---|
| toss_outcome | won | Won toss |
| toss_outcome | lost | Lost toss |
| inning | 1 | Batted first |
| inning | 2 | Batted second |
| result | won | Won the game |
| result | lost | Lost the game |
| result | tied | Tied |

No abbreviations. Middot separators in the 3-filter case.

### 2.7 Wilson CIs on hover

Tooltip on cell hover. Content:

```
Won toss · Batted first · Won the game
42 of 66 matches (64%)
Wilson 95% CI: 52% – 75%
Share of 145 in-scope matches: 29%
vs league baseline: ↑ 70.6% (17% → 29%)
```

The last line only appears when `hasSubject` is true.

Outcome sub-rects each get their own hover tooltip (W/T/L sub-cell
stats with Wilson CIs).

Implementation: semiotic `OrdinalFrame` has a `tooltipContent` prop
that takes a render function; pass cell metadata and let the
function build the tooltip.

### 2.8 Opacity for low-n cells

Per-cell `n` thresholds:

| n | Opacity | Treatment |
|---|---|---|
| ≥ 20 | 1.00 | full |
| 10–19 | 0.70 | dim |
| 5–9 | 0.45 | very dim |
| 1–4 | 0.25 | very dim + `n=N` badge centered |
| 0 | hatched/dashed rect | "0" centered, still clickable |

Whole-widget guard: when `scope_total_n < 30`, the widget renders
at opacity 0.8 with a "Thin sample — interpret with caution"
footnote.

### 2.9 Mount placement on Teams page

Widget mounts at the top of `frontend/src/pages/Teams.tsx`, between
the FilterBar and the discipline-tabs strip. Always rendered (no
collapse toggle). Two modes:

- **Landing** (no `?team=`): widget shows the all-teams joint
  distribution at the current filter scope. Cells show raw shares
  (no deltas, because this IS the baseline). Useful as a research
  view: "in T20 men's IPL, how often does the toss-winning team
  also win the match?"

- **Team-detail** (`?team=Mumbai+Indians`): widget shows the team's
  joint distribution AND each cell + marginal carries a delta vs
  the all-teams baseline at the same filter scope. The marquee
  view: "MI wins 64% when winning the toss and batting first — 70%
  higher than the all-teams baseline."

### 2.10 Mobile

Per CLAUDE.md "mobile viewport check is mandatory":

At `@media (max-width: 720px)`:
- 2×2 mosaic stacks the two toss columns vertically (becomes 4
  rows of 1D bars, one per `(toss × inning)` combination). Cells
  shrink-to-readable; tooltips reposition.
- 1D bar keeps shape.
- Status strip wraps to 2 lines.

CSS classes in `frontend/src/index.css`, not inline styles.
Browser-agent verification at 390×844 before every mosaic-
touching commit.

### 2.11 Frontend tests

#### Integration (shell — `tests/integration/team_splits_mosaic.sh`)

SQL-anchored DOM tests, per CLAUDE.md "integration tests must
self-anchor against SQL":

- `sql()` helper at top, reads from `cricket.db`
- For each of {0, 1, 2, 3} filters set, verify:
  - DOM cell count matches expected cell count (per "Sparkline /
    per-item chart bar count must match SQL" rule)
  - Status-strip text matches the §2.6 template
  - Cell-text counts match `sql("SELECT COUNT(*) FROM match …")`
  - Marginal labels carry the correct values
- Click each marginal → URL contains expected single param,
  re-rendered widget shows correct dimensionality
- Click outer cell → URL contains 2 params
- Click outcome sub-rect → URL contains 3 params (collapses to
  status strip)
- Hover on a cell → tooltip contains `Wilson 95% CI`
- On landing page (no `?team=`): widget renders, no deltas shown
- On team-detail (`?team=`): widget renders, deltas present and
  match API response from a `curl` call

Mobile (per "mobile viewport check"):
- `ab set viewport 390 844; reload`
- Mosaic renders without overflow
- 4-row stacked layout instead of 2×2

The integration tests use the dual-anchor pattern:
- SQL-anchored: raw counts and cell existence
- API-anchored: delta values (read `/teams/splits` via `curl` and
  match the DOM-displayed `↑ N%` against the `delta_pct` field)

### 2.12 Frontend docs

After frontend ships:

- **`internal_docs/landing-pages.md`** — Splits Mosaic placement
  on Teams landing + team-detail.

- **`internal_docs/codebase-tour.md`** — append `SplitsMosaic.tsx`
  to the frontend components block. Note the URL-state-as-shape
  pattern.

- **`internal_docs/design-decisions.md`** — entries:
  - "Splits Mosaic dimensionality is URL-derived — no
    local/session state"
  - "Splits Mosaic always rendered on Teams page (landing +
    detail); URL shape determines visual density"
  - "Traffic-light palette `WISDEN_WL` for outcome encoding only"
  - "Fixed axis ordering — `result` always owns the color slot
    when free"

- **`CLAUDE.md`** — new rule entries:
  - Traffic-light `WISDEN_WL` discipline (reserved for Splits
    Mosaic; NOT a fill anywhere else)
  - "When extending mosaic to a new conditioning axis: add as
    spatial split, never as color"

- **`internal_docs/visual-identity.md`** — `WISDEN_WL` palette in
  the chart-palette section.

---

## Stage 3 — Commit order

Per CLAUDE.md "commit cadence — one logical change per commit",
each commit lands runnable:

### Backend

1. Add `result` to AuxParams + plumb into team router `_apply_filters`. Sanity test added. `docs/api.md` updated for the existing /summary endpoint's new param.
2. Add `toss_outcome` to AuxParams + plumb. Sanity test extended. `docs/api.md` extended.
3. New endpoint `/api/v1/teams/splits` (league-side query only, no team). Sanity test for landing case. `docs/api.md` new section. `internal_docs/codebase-tour.md` updated.
4. Extend `/teams/splits` to dual-query envelope (team-side + deltas) when `?team=` set. Sanity test extended. Docs sweep: `how-stats-calculated.md` + `design-decisions.md` + `server-vs-client-calcs.md`.
5. Add regression URL inventory `tests/regression/team_splits/urls.txt`. Run `./tests/regression/run.sh team_splits` — expect 0 drift.

### Frontend

6. `WISDEN_WL` block in `palette.ts`. No consumers yet.
7. AuxParams extension in `types.ts` + scope helper updates (`abbreviateScope`, `ScopeStatusStrip`, `useFilters`). No widget yet; URL params work via paste, status strip + abbreviation already show new axes.
8. `SplitsMosaic.tsx` component, 3-free-axis case (landing-page view). Wired to `/teams/splits` endpoint. Mounted on Teams landing page.
9. 2-free + 1-free + 0-free cases. Status strip vocabulary table from §2.6 codified.
10. Marginal labels + outer cells + outcome sub-rects as clickable filter controls. URL writes via `useUrlParam`. Browser-back works.
11. Wilson hover tooltip via semiotic `tooltipContent`.
12. Opacity-for-low-n thresholds (§2.8). Whole-widget low-sample footnote.
13. Team-detail variant: deltas in cell labels + marginals. Mounted on team-detail (`?team=` set). Browser-agent verification, desktop + mobile.
14. Integration test suite — `tests/integration/team_splits_mosaic.sh` covering §2.11.
15. Docs sweep: `landing-pages.md`, `codebase-tour.md`, `design-decisions.md`, `CLAUDE.md`, `visual-identity.md`.

Total: 15 commits. Backend and frontend stages are independent enough
that backend (1-5) can ship as a coherent pre-frontend deploy if
desired (the new endpoints are usable via curl + Swagger immediately).

---

## Stage 4 — Cross-cutting reminders (carried from CLAUDE.md)

- All filtering encoded in URL. `useUrlParam` writes only on user
  action; never `setUrlParams` from `useEffect`.
- AuxParams audit on every scope helper (`abbreviateScope`,
  `ScopeStatusStrip`, `inheritedScope` — when slot integration
  lands in a follow-up spec).
- Browser-agent verification mandatory before every frontend
  commit (desktop AND 390×844 mobile).
- Integration tests SQL-anchored; numeric expected values derived
  from `cricket.db` at test runtime (not hardcoded).
- Tests cover every mount site of `SplitsMosaic` (landing + team-
  detail × at least one filter state each).
- Mobile media-queries via CSS classes in `index.css`, not inline
  styles.
- Wilson CIs computed server-side per existing `prob_record`
  convention.
- DLS innings count as 1 match each; super-over outcomes inherited
  from `outcome_winner`.
- Tied + no-result collapsed into `tied` for the `result` filter.
- `WISDEN_WL` reserved for outcome encoding in the Splits Mosaic;
  never used as a fill elsewhere.
- Fixed axis ordering — `result` always owns the innermost color
  slot when free; toss and inning are always spatial.

---

## Stage 5 — Follow-up specs (NOT in this spec)

These are tracked as separate, tighter specs once Teams ships:

1. **`spec-splits-mosaic-player.md`** — same component + endpoint
   pattern at player grain. `matchplayer.team` join; substitute
   exclusion. Mounted on player dossier page.
2. **`spec-splits-mosaic-compare.md`** — extend
   `OVERRIDABLE_SLOT_KEYS` with `result` + `toss_outcome`; per-
   slot mini-mosaic in compare-slot cards.
3. **`spec-splits-mosaic-h2h.md`** — H2H POV (team1 vs team2);
   default subject = team1 with per-cell-flip toggle.

Each builds on Teams stage; this spec is the foundation.
