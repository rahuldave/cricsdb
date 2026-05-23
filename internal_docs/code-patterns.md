# Code patterns

Codebase-specific patterns. CLAUDE.md links here. Each section names the rule, then the why, then the tells.

## Contents

1. [Router imports must come from shipped paths](#router-imports-must-come-from-shipped-paths)
2. [Chart wrappers — header lives OUTSIDE the positioning context](#chart-wrappers--header-lives-outside-the-positioning-context)
3. [Extend existing abstractions — do NOT fork parallel helpers](#extend-existing-abstractions--do-not-fork-parallel-helpers)
4. [Page header — `ScopedPageHeader` for every scoped page](#page-header--scopedpageheader-for-every-scoped-page)
5. [`abbreviateScope` is the source of truth for "what's in scope"](#abbreviatescope-is-the-source-of-truth-for-whats-in-scope)
6. [URL state — share-link reproducibility](#url-state--share-link-reproducibility)
7. [Single-payload + window-toggle](#single-payload--window-toggle)
8. [API ↔ frontend type contract](#api--frontend-type-contract)
9. [Chip ↔ chart baseline symmetry](#chip--chart-baseline-symmetry)
10. [Absolute-vs-per-innings dimensional discipline for chips](#absolute-vs-per-innings-dimensional-discipline-for-chips)
11. [No CSS-pixel shortcuts when a structural fix exists](#no-css-pixel-shortcuts-when-a-structural-fix-exists)
12. [No hacks where a structural fix exists](#no-hacks-where-a-structural-fix-exists)
13. [FilterBar cascade-clear rule (auto-correct loops)](#filterbar-cascade-clear-rule-auto-correct-loops)

---

## Router imports must come from shipped paths

`deploy.sh` ships only `api/` + `models/` + `frontend/dist/` + `main.py` + vendored `deebase/`. Imports in `api/routers/*.py` from `scripts/`, `tests/`, or any other top-level directory resolve locally (project root is on `sys.path`) but **500 in production** because the source files don't exist in `build_plash/`.

Constants used by routers belong in `models/tables.py` (next to the table they describe) or `api/` (cross-router home). Populate scripts can re-import the constant from `models.tables` so it has one canonical definition. Quick pre-deploy probe: `grep -rn 'from scripts\|from tests' api/` should return zero hits.

User flagged 2026-05-14 after Phase C part 2 (`2ead91c`) shipped `from scripts.populate_bucket_baseline import PARTNERSHIP_TOP_K` inside `/series/partnerships/top-by-wicket`. Local: 200. Prod: 500 on every call. Hot-fixed in `48cef68`.

## Chart wrappers — header lives OUTSIDE the positioning context

Every chart wrapper that combines `<ChartHeader />` with absolute-positioned overlays (rotated axis labels, top-of-bar annotations) must use `<ChartContainer>` from `frontend/src/components/charts/ChartContainer.tsx`. ChartContainer renders the header in normal flow, then wraps the SVG + overlays in a separate `position: relative` block — so the overlay's containing block is the chart area, not "header + chart area".

Why: when `<ChartHeader>` is rendered as the first child of a `position: relative` wrapper that ALSO contains absolute-positioned overlays, the overlay's `top: NN` measures from wrapper-top, not SVG-top. Header height (28-53px depending on whether a subtitle auto-fills) pushes the SVG down inside the wrapper, but the overlay's coordinate math doesn't know — labels drift INTO the plot area. Commit `eb8e69f` shipped this regression on every BarChart in May 2026; `51ed9ae` fixed it structurally via `<ChartContainer>`. Locked by `tests/integration/charts_label_positioning.sh`.

## Extend existing abstractions — do NOT fork parallel helpers

Before writing a new helper or component, find the existing API that already solves this class of problem, and extend it with a narrow option.

| Surface | API |
|---|---|
| Scope-link URLs | `frontend/src/components/scopeLinks.ts` (`FILTER_KEYS`, `SubscriptSource`, `resolveBucket`, `resolveScopePhrases`, `ScopeContext`) |
| Team / player / series rendering | `TeamLink.tsx` / `PlayerLink.tsx` / `SeriesLink.tsx` — **READ `internal_docs/links.md` before writing ANY navigation** |
| Filter state | `useFilters()`, `FILTER_KEYS` |
| Tabular rendering | `DataTable.tsx` |
| Score rendering | `Score.tsx` |
| Innings-score aggregation in SQL | scalar-subquery pattern from `api/routers/matches.py::inn_rows` / `wkt_rows` |
| Delta rendering | `MetricDelta` (inline colored text, not pills — pills are reserved for `ProbChip`) |

When a new surface's needs don't fit an existing API's shape, **add a narrow prop / render-prop / override to that API**. If you find yourself typing `teamXHref(...)`, `EdTag`, `scoreCell` alongside existing `TeamLink` / `Score`, stop and ask: "why can't the existing API do this with one more prop?" Reading 100 lines of the existing module is cheaper than maintaining two pipelines that have to stay in lockstep.

This rule overrides the "just make it work" instinct.

## Page header — `ScopedPageHeader` for every scoped page

Every page that takes FilterBar narrowings (Batting / Bowling / Fielding / Players / Teams / Series / Venues / HeadToHead) renders its title via `frontend/src/components/ScopedPageHeader.tsx`. The component reads `abbreviateScope(filters)` from `scopeLinks.ts`. Pass `omit={['tournament']}` etc. on dossier pages where the page subject IS one of the scope axes (Series omits `tournament`, Venues omits `filter_venue`). New scoped page → use `ScopedPageHeader`, do NOT re-roll the H2 + flag JSX inline.

## `abbreviateScope` is the source of truth for "what's in scope"

When you add a new FilterBar field or AuxParam that affects what data the user is looking at, ALSO add it to `abbreviateScope` in `scopeLinks.ts`. The 2026-05-06 inning-missing bug surfaced because inning is an AuxParam (not in `FILTER_KEYS`) and the abbreviation silently dropped it. Audit pattern: for every axis in `FilterParams`, ask "does setting this change what data is shown?" If yes, it belongs in the abbreviation AND in `ScopeStatusStrip` — both should emit the same axes.

## URL state — share-link reproducibility

Anything that selects between pre-fetched dossiers / view modes / windows / toggles MUST encode in the URL via `useUrlParam`. The default value is encoded by ABSENCE of the param (saves URL noise on the canonical default). Per-panel keys use a panel-specific prefix (`dist_window`, `compareN_inning`) so they don't collide.

**URL-clean rule: compute for display, never auto-mutate.** If you find yourself adding a `setUrlParams` call in a `useEffect` to "make the URL explicit" — STOP. Compute the value in the rendering layer and mark it visually distinct (e.g. the status bar's italic faint `(all-time)` suffix). The URL is a faithful record of user choice; silent URL mutation breaks share-link round-trip. User flagged 2026-05-08 (and earlier 2026-04-20 — commit `700d11b`).

## Single-payload + window-toggle

When an endpoint can return multiple related views in one response (lifetime + last_10 + last_60d + last_6mo + last_1yr in `/api/v1/batters/{id}/distribution`), prefer a single roundtrip over per-view fetches. The frontend toggle then redraws from the in-memory payload — no refetch. Acceptable when each view is the same shape and N is small (≤6). Spec: `spec-distribution-stats.md §8.6` + §9.2.1.

## API ↔ frontend type contract

When a backend change drops a field from a response, drop it from the matching TypeScript interface in `frontend/src/types.ts` IN THE SAME COMMIT. Type-API divergence turns "field missing at runtime" into a silent fall-through through `?. ?? 0` — TypeScript believes the type, the gate evaluates to `0 > 0`, the UI hides itself.

## Chip ↔ chart baseline symmetry

When a tile renders a `MetricDelta` chip against `scope_avg` (the league-side dual-query result on `/summary` endpoints) AND the page also renders a by-season chart of the same metric, the chart MUST render the same `scope_avg` source as a reference overlay at the same scope. Don't gate the chart visualisation differently from the chip — they're the same comparison.

`MetricEnvelope.scope_avg` is computed at every FilterBar scope (the dual-query is `team=None` with the same FilterParams). If the chip's delta is meaningful at every scope, the green-line baseline is too. Shipping the chip-without-overlay (or worse, the chip-at-every-scope + overlay-gated-on-one-axis) leaves the reader with a delta number whose comparison target isn't drawn — they can read the +14.9% but can't see what 14.9% larger than is.

Use `LineChart`'s `referenceData` prop (auto-derives the legend label from `abbreviateScope(filters, { discipline }) + " avg"`) and fetch the baseline unconditionally — `/scope/averages/{discipline}/by-season` accepts the same FilterParams the chip's summary endpoint does, so the baseline tracks whatever the FilterBar describes.

User flagged 2026-05-13: CSK win % showed +14.9% at `tournament=IPL` and +16.0% without — the chip surfaced the scope_avg movement at every scope but the chart only drew the green line at one. Naming: avoid `tournamentBaseline` for a variable that fetches at every scope; `scopeBaseline` reads correctly.

## Absolute-vs-per-innings dimensional discipline for chips

A MetricDelta chip ("vs base N · ↑+M%") next to a bold tile value is only coherent when the chip's `scope_avg` is in the SAME dimension as the bold value. Pairing an absolute count (9 hundreds, 125 catches) with a per-innings or per-match rate chip (0.006 hundreds/inn, 0.316 catches/match) creates a dimensional mismatch that the reader can't parse — `9 vs base 0.006 → +450%` reads as nonsense.

**Rules:**
- **Absolute tiles** (counts: `Runs`, `100s`, `Catches`, `Maiden Overs`, `Wickets`) → bold value only, **no chip**.
- **Per-innings / per-match tiles** (rates: `Avg`, `SR`, `100s/Inn`, `Catches/Match`, `Econ`) → bold value + chip OK.
- **"Show both"** — pair every absolute with a sibling per-innings tile so the reader gets both the count AND the comparison. Don't stuff a rate chip onto a volume tile as a shortcut.

Same rule for charts: absolute-per-season chart → no baseline overlay; per-rate-per-season chart → green-line overlay.

User flagged 2026-05-20 after Phase F of `spec-player-baseline-parity.md` shipped Kohli IPL profile with "100s 9 — vs base 0.006 ↑+450%" tiles. Full audit + fix plan in `internal_docs/spec-rate-vs-volume-audit.md`.

**Tells you're about to violate this:**
- Adding `subtitle={baselineSub(b.runs, …)}` on a Runs tile — Runs is volume, subtitle would render a rate chip.
- Pairing `<StatCard label="Catches" value={f.catches.value} subtitle={…catches_per_match}>` — bold is volume, chip is rate; split into two tiles.
- Adding a green baseline overlay to a Volume-by-Season BarChart/LineChart — drop the overlay or convert the chart to per-rate-by-season.

## No CSS-pixel shortcuts when a structural fix exists

When a layout problem has a clean structural solution (CSS Grid / subgrid for cross-column row alignment, semantic flex for inline content), use the structural fix even if a `min-height: 4.6rem` / `padding-top: 12px` hack would land in 30 minutes. Pixel hacks are tuned to one viewport width, one chip density, one font-stack; the next content change shifts the magic number and the layout breaks.

Tells you're about to shortcut:
- `min-height` because "the team col wraps to 2 lines but the avg col fits on 1." → Subgrid.
- `padding-top` to push one element down to match another. → Same row of a grid.
- `position: absolute` to dodge a sibling's height. → Separate grid track.
- Computing pixel values from observed measurements ("agent measured 73px, so I'll use 4.6rem"). → Subgrid sizes to 73px without you needing the number.

Genuinely-correct shortcut cases: sub-pixel rounding (`transform: translateY(-1px)` for a 0.5px gap), aspect-ratio reservation for known-dimension images, cosmetic padding that's not load-bearing for alignment.

## No hacks where a structural fix exists

When a clean idiomatic solution and a hack both look like they'd "work", ship the clean one. The hack lands as a liability that compounds at the next refactor. Tells:
- Reading `window.location.*` synchronously inside a React effect to dodge a desync between live URL and React state. → The codebase's idiom is `useRef` once-per-mount gates (see `pages/Teams.tsx`, `TournamentDossier.tsx`'s `prevFilterKey` ref). Match it.
- Reaching for `setTimeout` / extra `sleep` to "let things settle" in production code. → React state isn't a race; derive one update from the other.
- Adding a feature flag / `if (process.env.NODE_ENV)` to bypass StrictMode dev-replay. → StrictMode replay IS the test surface; if your effect can't survive it, the effect is wrong.

Default: read the surrounding 100 lines first; if there's an established pattern for this class of problem, match it.

## FilterBar cascade-clear rule (auto-correct loops)

When the user clears a coupled filter (gender / team_type), also clear any dependent narrowing (tournament). The FilterBar runs auto-correct deep-link effects that fill missing fields from a tournament's metadata; if the user clears team_type back to "All" but tournament stays, the auto-correct re-asserts team_type=club. "Spring-back" UX bug.

Pattern:
```ts
if (t && (!v || t.team_type !== v)) updates.tournament = ''
```
NOT `if (t && v && t.team_type !== v)` — the `&& v &&` short-circuits on the user's "clear" click.

When adding a NEW auto-correct deep-link effect: make sure the user-clearing path on every participating filter also cascade-clears the inferred narrowings. Test: `tests/integration/filterbar_cascade_clear.sh`.
