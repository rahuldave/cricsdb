# CricsDB — T20 Cricket Analytics Platform

Live: https://t20.rahuldave.com · Repo: https://github.com/rahuldave/cricsdb · deebase PR: https://github.com/rahulcredcore/deebase/pull/8

CLAUDE.md is the **inviolable-rules file**. Everything describing what the codebase IS (files, endpoints, payloads, formulas, design history) lives in dedicated docs — go there before assuming.

## Contents

1. [Pointers (doc index)](#pointers)
2. [Running locally + deploying](#running-locally--deploying)
3. [Documentation discipline](#documentation-discipline)
4. [Methodology rules](#methodology-rules)
5. [Code patterns](#code-patterns)
6. [Testing discipline](#testing-discipline)
7. [Cricket invariants](#cricket-invariants)
8. [Page conventions](#page-conventions)
9. [Palette](#palette)
10. [Splits Mosaic](#splits-mosaic)

---

## Pointers

**Orientation**
- Codebase tour: `internal_docs/codebase-tour.md`
- React + Vite primer (this codebase): `internal_docs/react-primer.md`
- Frontend build pipeline: `internal_docs/frontend-build-pipeline.md`
- Visual identity / Wisden styles: `internal_docs/visual-identity.md`
- Color discipline (palettes, reference lines, swatch alignment): `internal_docs/colors.md`
- Local dev prerequisites + REPL: `internal_docs/local-development.md`

**Domain + UX**
- Landing pages on every search-bar tab + Compare slots + Series/H2H/Venues structure: `internal_docs/landing-pages.md`
- API reference (every endpoint, curl, response): `docs/api.md` — also `/api/docs` (Swagger) and `/api/redoc`
- Stat formulas: `internal_docs/how-stats-calculated.md`
- Server-vs-client calc inventory + cross-endpoint divergence audit: `internal_docs/server-vs-client-calcs.md` — read before changing any predicate or shipping a new derived metric
- Design decisions: `internal_docs/design-decisions.md`
- URL state discipline: `internal_docs/url-state.md`
- Link components (TeamLink / PlayerLink / SeriesLink contract — read before writing ANY navigation): `internal_docs/links.md`
- Inning-controls mount-site inventory (InningToggle / Splits Mosaic per route × subtab — read before adding/moving either widget): `internal_docs/inning-controls-mount-sites.md`

**Data + ops**
- Data pipeline: `internal_docs/data-pipeline.md`
- Smoke-test update_recent against /tmp DB: `internal_docs/testing-update-recent.md`
- Deploying: `internal_docs/deploying.md`

**Performance**
- Leaderboard landings: `internal_docs/perf-leaderboards.md`
- deebase pool / async SQLite: `internal_docs/perf-async-deebase.md`
- Compare-tab page-load: `internal_docs/perf-bucket-baselines.md`
- Systems / perf catch-all: `internal_docs/systems-followups.md`

**Testing**
- Test catalogue: `internal_docs/tests.md`
- Regression harness: `internal_docs/regression-testing-api.md` + `tests/regression/`

**Active work**
- Next-session agenda + NO-DEPLOYS gate: `internal_docs/next-session-ideas.md`
- A–Q lettered roadmap, dated session logs, deferred queue: `internal_docs/enhancements-roadmap.md`
- Build-ready specs: `internal_docs/spec-inning-split.md`, `internal_docs/spec-filterbar-team-class-v3.md`, `internal_docs/spec-filterbar-team-class-club.md`, `internal_docs/spec-distribution-stats.md`, `internal_docs/spec-splits-mosaic.md`, `internal_docs/splits-mosaic-cross-page.md`, `internal_docs/spec-rate-vs-volume-audit.md` (next-up Phase I — absolute-vs-per-innings tile/chart hygiene; backend extensions front of doc)
- Club-tier classification: `internal_docs/club-tier-classification.md` + anchor numbers `internal_docs/club-tier-anchor-numbers.md`

---

## Running locally + deploying

```bash
# Terminal 1 — backend (ALWAYS --reload; bare uvicorn serves stale code)
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` → port 8000.

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

Type-check with `tsc -b` or `npm run build` — `tsc --noEmit` is a no-op here (root tsconfig has `files: []`).

Prereqs, REPL, troubleshooting: `internal_docs/local-development.md`. Deploy details: `internal_docs/deploying.md`.

---

## Documentation discipline

**READ `internal_docs/docs-sync.md` before claiming any feature done.** It is the update-map (API route → `docs/api.md`, design decision → `design-decisions.md`, palette → `colors.md`, etc.) and the regression REG→NEW flip-order workflow.

**Update the affected sections IN that doc** at the end of every feature. CLAUDE.md is rules, not history; new history goes in the right named doc.

---

## Methodology rules

### Commit cadence — one feature, one commit, immediately

**Commit as soon as a feature looks complete — don't batch.** One logical change per commit, committed at the moment it reaches a runnable state (type-check passing, feature working in the browser, tests still green). If you just finished X and X works, commit X before starting Y. Even if Y is the obvious next step — the atomicity is the point.

Why: sessions that accumulate 30 files of uncommitted work across five unrelated features make `git bisect` useless. Lost-bisect debugging is expensive; small commits are free.

User has flagged this repeatedly, including the session that prompted this rewrite. Tells you're about to violate it:
- You've made 3+ working changes and haven't committed.
- You're tempted to "finish the whole arc" before committing.
- You're using `git add -A` because the diff sprawls. → Use `git add -p` to split.

### Filter-combination testing — the matrix is mandatory

The app's premise is **consistent comparisons across all filter combinations**. A delta that works at `team=X` but disappears at `team=X&filter_venue=Y` is a bug. User feedback 2026-05-11: "things need to be consistent on filtration" — flagged after Wankhede + toss filter lost its league-baseline chips.

When a change touches anything that depends on FilterBar / AuxParam state (deltas, league-avg chips, marginals, baselines), exercise this matrix:

- No team selected (landing view) + a narrowing filter (`filter_venue=...`, opponent, single season).
- Team selected + same narrowing filters (venue, opponent, season).
- Team selected + aux filter (`toss_outcome`, `inning`, `result`) AND a narrowing together (e.g. `team=MI&filter_venue=Wankhede&toss_outcome=won`).
- Bowling tab + inning filter (the inning POV flip).
- Multiple filters chained (`&season_from=2018&season_to=2020&filter_venue=...`).

Regression + tsc + curl are NOT substitutes. **Load the actual page in agent-browser, click the actual controls, verify the rendered DOM at each combination.**

### UI verification — browser-agent + mobile, every time

After any change to `frontend/src/`:
1. Use the `agent-browser` skill to load affected pages in a real browser, exercise every new tab/component, hover interactive elements, click every link to confirm navigation.
2. **Mobile viewport check is not optional.** `agent-browser set viewport 390 844` then `reload` BEFORE committing. Reproduce the user's exact URL at both 1280 and 390 widths.

Common mobile failure modes:
- Inline `style={{gridTemplateColumns: 'minmax(0, 1fr) minmax(220px, …)'}}` silently zeros the first column on a 342-wide panel — histogram/chart becomes invisible. Inline styles can't do media queries; extract to a `wisden-*` class in `index.css` with `@media (max-width: 720px) { grid-template-columns: 1fr }`.
- Inline rows (toggles, milestone chips, form-delta lines) overflow without `flex-wrap: wrap`.
- `grid-template-columns: repeat(N, 1fr)` with N > 3 needs to drop on mobile.

A frontend change is not "done" until both desktop AND mobile look right. `tsc -b` and `npm run build` verify code correctness, not feature correctness.

### Bug reports — reproduce, propose, WAIT

When the user reports a bug or asks why something looks/behaves a certain way:

1. **Reproduce.** Load the URL with agent-browser, query the DB, run the test. Confirm what's actually wrong before forming a hypothesis. Phrases like "this might be because…", "probably the X is Y…", "I bet the issue is…" are tells that you're about to ship a speculative fix — STOP and verify first.
2. **Identify the root cause.** Name the actual mechanism — code path, data state, design choice — not a plausible-sounding guess.
3. **Explain what you found AND propose 1–3 fixes with trade-offs.** Two-three sentences each, not a wall of code.
4. **WAIT.** Do NOT ship the fix in the same turn unless explicitly told to ("just fix it"). The user knows their codebase; they may pick a different fix, OR decide the behavior is correct.

Bug reports often LOOK like routine fixes but turn out to be design questions in disguise. Auto mode is NOT a license to skip this — auto mode is for routine work, not bug-fix decisions.

Tells you're about to skip the rule:
- You jump to an Edit before reading the surrounding code.
- You announce "Going to ship this now" / "Implementing the fix" before the user has confirmed the diagnosis.

### Do NOT defer parts of an assigned task

When the user gives you a task — "add per-page Twitter cards", "wire up X for the whole app" — finish it. Don't ship the easy half and pitch the rest as a follow-up. If a part is genuinely out-of-scope or needs a different design call, ASK before cutting it. The "shipped + deferred" pattern reads as scope-shaving and forces the user to re-prompt.

### Audit prompt discipline — raw output, not verdicts

When asking agent-browser to verify, ask for RAW OUTPUT, not summaries. "List every section header with the first row label per column" is checkable. "Verify all sections render" is a verdict that drops information — when the agent reports PASS but walked the wrong cells, the bug ships.

For each assertion you'd put in an integration test, **write the test AT THE SAME TIME**, not after a bug surfaces. One-shot browser audits are exploratory; checked-in `tests/integration/<feature>.sh` assertions are durable.

### Red-then-green test discipline

Every fix gets a test that demonstrates the bug (red against HEAD), THEN the fix (green). Report both phases in the commit message. A green-only test ships a fix that may or may not address the actual bug.

### Perf changes — measure after every single change

When optimizing, make ONE change at a time and measure it in isolation. Do not stack 2–3 changes and measure at the end.

Why: batched measurements can't tell you which change moved the number. If the final result is faster, slower, or flat, you can't decide which change to keep, drop, or extend. You also can't notice when one change cancelled out the gain from another — the way `lite=true` skipping the 3 GROUP BY queries hid the actual cost of restoring them when `lite` was deleted in the next iteration (2026-05-14 /series perf work).

A perf pass should look like:
1. Baseline timing recorded.
2. Change A. Measure. Record delta.
3. Change B. Measure. Record delta.
4. Change C. Measure. Record delta.

If a commit message claims a perf win, the win should be measurable in isolation — gather one query, time it; gather another, time it; etc.

Tells you're about to violate this:
- Several refactors stacked without a baseline timing between them.
- Vague claims like "this should be faster" without a number-vs-number comparison.
- Switching to a precomputed table AND parallelizing the query AND deleting an endpoint in one commit.

User flagged 2026-05-14. Pair with [Bug reports — reproduce, propose, WAIT] above.

### Spec review via Roughdraft

This codebase keeps build-ready specs in `internal_docs/spec-*.md` (apples-to-apples baselines, rate-vs-volume audit, prob-baselines, etc.). When the user wants to review a NEW spec or your edits to an EXISTING one, use **Roughdraft** — a local single-file Markdown viewer that round-trips CriticMarkup comments through a browser pane.

The user may refer to Roughdraft as `rd` in natural language. Treat `rd` as shorthand. Do NOT create any shell alias / executable / symlink / command named `rd`.

When the user asks for a plan, write the plan as a Markdown file on disk BEFORE asking them to review it (this codebase's convention — drop it under `internal_docs/spec-*.md`).

To open a spec for review:

```bash
roughdraft open "/absolute/path/to/internal_docs/spec-*.md"
```

Roughdraft is single-file — open one `.md` at a time. If Roughdraft isn't running, `roughdraft open` starts it automatically.

After `roughdraft open` runs, **leave the command running**. Do not interrupt, kill, background, detach, or treat the waiting process as cleanup — the wait IS the signal. Roughdraft exits the command when the user clicks Done Reviewing, and that exit is your signal to resume.

**Known issue on this machine:** `roughdraft watch` (the long-poll for Done Reviewing) hits a Node 25 / undici 60-second headers timeout. The browser window still opens fine and edits still save to disk. If the CLI errors out with `HeadersTimeoutError` / `UND_ERR_HEADERS_TIMEOUT`, the window IS open at `http://localhost:7373/?path=...`; tell the user, then re-read the file from disk after they say they're done.

After the user finishes reviewing, **read the Markdown file from disk** and respond to any CriticMarkup comments / suggested changes. Don't assume — `grep -nE '\{>>|\{\+\+|\{--|\{~~|\{=='` the file to surface all markers.

#### CriticMarkup syntax (Roughdraft-flavored)

Base markers:

- Comment: `{>>comment<<}`
- Insertion: `{++new text++}`
- Deletion: `{--old text--}`
- Substitution: `{~~old~>new~~}`
- Highlight: `{==text==}`

Anchored comment: `{==selected text==}{>>Comment text<<}{id="c1" by="AI" at="2026-04-28T12:00:00.000Z"}`.
Suggested change: `{++new text++}{id="s1" by="AI" at="..."}` or `{~~old text~>new text~~}{id="s2" by="AI" at="..."}`.
Reply (refers to parent via `re`): `{>>Reply text<<}{id="c2" by="AI" at="..." re="c1"}`.

When you ADD a new comment or suggested change, use the extended attribute block: `{id="cN" by="AI" at="<ISO timestamp>"}`. Generate stable doc-local ids (`c1`, `c2`, … for comments; `s1`, `s2`, … for suggestions). When replying, set `re` to the parent id.

Roughdraft may already have attribute blocks on existing comments — **preserve them** unless you're intentionally removing the comment. Common attributes: `id`, `by`, `at`, `re`.

#### Spec-review flow for this codebase

For build-ready specs (`spec-apples-to-apples-baselines.md`, `spec-prob-baselines.md`, etc.):

1. Draft the spec as a single Markdown file under `internal_docs/`.
2. Commit the draft (one clean commit so the review pass diff is readable).
3. `roughdraft open "/Users/rahul/Projects/cricsdb/internal_docs/<spec>.md"` — the user reviews in the browser.
4. After Done Reviewing, grep the file for CriticMarkup markers; respond to each as inline reply comments (preserve original ids; assign new ids to your replies with `re=` set).
5. Apply any structural changes the user asked for (e.g., promote "open questions" to "decisions", drop deferred sections, tighten ambiguous principles).
6. Commit the review pass as a separate commit with `spec: review pass — decisions locked` style message that summarises which comments were addressed.
7. Push so a future session sees the locked spec on `origin/main`.

If `roughdraft help` or `roughdraft help criticmarkup` is needed for local CLI / syntax details, run them directly.

---

## Code patterns

### Router imports must come from shipped paths

`deploy.sh` ships only `api/` + `models/` + `frontend/dist/` + `main.py` + vendored `deebase/`. Imports in `api/routers/*.py` from `scripts/`, `tests/`, or any other top-level directory resolve locally (project root is on `sys.path`) but **500 in production** because the source files don't exist in `build_plash/`.

Constants used by routers belong in `models/tables.py` (next to the table they describe) or `api/` (cross-router home). Populate scripts can re-import the constant from `models.tables` so it has one canonical definition. Quick pre-deploy probe: `grep -rn 'from scripts\|from tests' api/` should return zero hits.

User flagged 2026-05-14 after Phase C part 2 (`2ead91c`) shipped `from scripts.populate_bucket_baseline import PARTNERSHIP_TOP_K` inside `/series/partnerships/top-by-wicket`. Local: 200. Prod: 500 on every call. Hot-fixed in `48cef68`.

### Chart wrappers — header lives OUTSIDE the positioning context

Every chart wrapper that combines `<ChartHeader />` with absolute-positioned overlays (rotated axis labels, top-of-bar annotations) must use `<ChartContainer>` from `frontend/src/components/charts/ChartContainer.tsx`. ChartContainer renders the header in normal flow, then wraps the SVG + overlays in a separate `position: relative` block — so the overlay's containing block is the chart area, not "header + chart area".

Why: when `<ChartHeader>` is rendered as the first child of a `position: relative` wrapper that ALSO contains absolute-positioned overlays, the overlay's `top: NN` measures from wrapper-top, not SVG-top. Header height (28-53px depending on whether a subtitle auto-fills) pushes the SVG down inside the wrapper, but the overlay's coordinate math doesn't know — labels drift INTO the plot area. Commit `eb8e69f` shipped this regression on every BarChart in May 2026; `51ed9ae` fixed it structurally via `<ChartContainer>`. Locked by `tests/integration/charts_label_positioning.sh`.

### Extend existing abstractions — do NOT fork parallel helpers

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

### Page header — `ScopedPageHeader` for every scoped page

Every page that takes FilterBar narrowings (Batting / Bowling / Fielding / Players / Teams / Series / Venues / HeadToHead) renders its title via `frontend/src/components/ScopedPageHeader.tsx`. The component reads `abbreviateScope(filters)` from `scopeLinks.ts`. Pass `omit={['tournament']}` etc. on dossier pages where the page subject IS one of the scope axes (Series omits `tournament`, Venues omits `filter_venue`). New scoped page → use `ScopedPageHeader`, do NOT re-roll the H2 + flag JSX inline.

### `abbreviateScope` is the source of truth for "what's in scope"

When you add a new FilterBar field or AuxParam that affects what data the user is looking at, ALSO add it to `abbreviateScope` in `scopeLinks.ts`. The 2026-05-06 inning-missing bug surfaced because inning is an AuxParam (not in `FILTER_KEYS`) and the abbreviation silently dropped it. Audit pattern: for every axis in `FilterParams`, ask "does setting this change what data is shown?" If yes, it belongs in the abbreviation AND in `ScopeStatusStrip` — both should emit the same axes.

### URL state — share-link reproducibility

Anything that selects between pre-fetched dossiers / view modes / windows / toggles MUST encode in the URL via `useUrlParam`. The default value is encoded by ABSENCE of the param (saves URL noise on the canonical default). Per-panel keys use a panel-specific prefix (`dist_window`, `compareN_inning`) so they don't collide.

**URL-clean rule: compute for display, never auto-mutate.** If you find yourself adding a `setUrlParams` call in a `useEffect` to "make the URL explicit" — STOP. Compute the value in the rendering layer and mark it visually distinct (e.g. the status bar's italic faint `(all-time)` suffix). The URL is a faithful record of user choice; silent URL mutation breaks share-link round-trip. User flagged 2026-05-08 (and earlier 2026-04-20 — commit `700d11b`).

### Single-payload + window-toggle

When an endpoint can return multiple related views in one response (lifetime + last_10 + last_60d + last_6mo + last_1yr in `/api/v1/batters/{id}/distribution`), prefer a single roundtrip over per-view fetches. The frontend toggle then redraws from the in-memory payload — no refetch. Acceptable when each view is the same shape and N is small (≤6). Spec: `spec-distribution-stats.md §8.6` + §9.2.1.

### API ↔ frontend type contract

When a backend change drops a field from a response, drop it from the matching TypeScript interface in `frontend/src/types.ts` IN THE SAME COMMIT. Type-API divergence turns "field missing at runtime" into a silent fall-through through `?. ?? 0` — TypeScript believes the type, the gate evaluates to `0 > 0`, the UI hides itself.

### Chip ↔ chart baseline symmetry

When a tile renders a `MetricDelta` chip against `scope_avg` (the league-side dual-query result on `/summary` endpoints) AND the page also renders a by-season chart of the same metric, the chart MUST render the same `scope_avg` source as a reference overlay at the same scope. Don't gate the chart visualisation differently from the chip — they're the same comparison.

`MetricEnvelope.scope_avg` is computed at every FilterBar scope (the dual-query is `team=None` with the same FilterParams). If the chip's delta is meaningful at every scope, the green-line baseline is too. Shipping the chip-without-overlay (or worse, the chip-at-every-scope + overlay-gated-on-one-axis) leaves the reader with a delta number whose comparison target isn't drawn — they can read the +14.9% but can't see what 14.9% larger than is.

Use `LineChart`'s `referenceData` prop (auto-derives the legend label from `abbreviateScope(filters, { discipline }) + " avg"`) and fetch the baseline unconditionally — `/scope/averages/{discipline}/by-season` accepts the same FilterParams the chip's summary endpoint does, so the baseline tracks whatever the FilterBar describes.

User flagged 2026-05-13: CSK win % showed +14.9% at `tournament=IPL` and +16.0% without — the chip surfaced the scope_avg movement at every scope but the chart only drew the green line at one. Naming: avoid `tournamentBaseline` for a variable that fetches at every scope; `scopeBaseline` reads correctly.

### Absolute-vs-per-innings dimensional discipline for chips

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

### No CSS-pixel shortcuts when a structural fix exists

When a layout problem has a clean structural solution (CSS Grid / subgrid for cross-column row alignment, semantic flex for inline content), use the structural fix even if a `min-height: 4.6rem` / `padding-top: 12px` hack would land in 30 minutes. Pixel hacks are tuned to one viewport width, one chip density, one font-stack; the next content change shifts the magic number and the layout breaks.

Tells you're about to shortcut:
- `min-height` because "the team col wraps to 2 lines but the avg col fits on 1." → Subgrid.
- `padding-top` to push one element down to match another. → Same row of a grid.
- `position: absolute` to dodge a sibling's height. → Separate grid track.
- Computing pixel values from observed measurements ("agent measured 73px, so I'll use 4.6rem"). → Subgrid sizes to 73px without you needing the number.

Genuinely-correct shortcut cases: sub-pixel rounding (`transform: translateY(-1px)` for a 0.5px gap), aspect-ratio reservation for known-dimension images, cosmetic padding that's not load-bearing for alignment.

### No hacks where a structural fix exists

When a clean idiomatic solution and a hack both look like they'd "work", ship the clean one. The hack lands as a liability that compounds at the next refactor. Tells:
- Reading `window.location.*` synchronously inside a React effect to dodge a desync between live URL and React state. → The codebase's idiom is `useRef` once-per-mount gates (see `pages/Teams.tsx`, `TournamentDossier.tsx`'s `prevFilterKey` ref). Match it.
- Reaching for `setTimeout` / extra `sleep` to "let things settle" in production code. → React state isn't a race; derive one update from the other.
- Adding a feature flag / `if (process.env.NODE_ENV)` to bypass StrictMode dev-replay. → StrictMode replay IS the test surface; if your effect can't survive it, the effect is wrong.

Default: read the surrounding 100 lines first; if there's an established pattern for this class of problem, match it.

### FilterBar cascade-clear rule (auto-correct loops)

When the user clears a coupled filter (gender / team_type), also clear any dependent narrowing (tournament). The FilterBar runs auto-correct deep-link effects that fill missing fields from a tournament's metadata; if the user clears team_type back to "All" but tournament stays, the auto-correct re-asserts team_type=club. "Spring-back" UX bug.

Pattern:
```ts
if (t && (!v || t.team_type !== v)) updates.tournament = ''
```
NOT `if (t && v && t.team_type !== v)` — the `&& v &&` short-circuits on the user's "clear" click.

When adding a NEW auto-correct deep-link effect: make sure the user-clearing path on every participating filter also cascade-clears the inferred narrowings. Test: `tests/integration/filterbar_cascade_clear.sh`.

---

## Testing discipline

### Integration tests must self-anchor against SQL

Numeric expected values in `tests/integration/<feature>.sh` (Matches counts, Runs, RR, leaderboard sizes, baseline-avg numerator/denominator) must be **derived from `cricket.db` at test runtime**, not hardcoded.

```bash
expected=$(sqlite3 "$DB" "SELECT COUNT(*) FROM match WHERE …")
actual=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "label" "$expected" "$actual"
```

Three-layer chain:
- **Sanity** (`tests/sanity/test_*.py`): SQL ↔ API.
- **Integration** (`tests/integration/*.sh`): DOM ↔ SQL via the running app (transitively SQL ↔ API ↔ DOM).
- **Regression** (`tests/regression/<feature>/urls.txt`): no-drift across refactors at the API layer.

Hardcoding `assert_eq "label" "548" "$actual"` means a bug that drifts the API to 548-by-coincidence silently passes. The DB is source of truth; SQL-derived expecteds self-correct against DB updates AND surface drift the moment either API or DOM departs.

Reference implementation: `tests/integration/team_class_club_per_page_refetch.sh`. `sql()` helper wraps `sqlite3 $DB`; every `assert_eq` reads its expected from `$(sql ...)`. IN-list constants (FM frozenset, PRIMARY/SECONDARY club leagues, ICC events) stay inline at the top of the script, mirroring the Python source — divergence surfaces immediately.

### Tests must cover EVERY call site of a shared abstraction

When you fix a bug in a shared helper (`useFilterDeps`, `FilterParams`, a SQL generator), the integration test must exercise every page that consumes it — not just the page where the bug surfaced. A test hitting 1 of 10 call sites passes through the next refactor that re-breaks 9 of them.

Pattern: `grep -rn 'helperName' src/` enumerates the sites; write one assertion per site. Reference: `tests/integration/inning_per_page_refetch.sh` — 10 mount sites × click-after-mount × 4 toggle states × SQL-anchored DOM assertions. User flagged 2026-05-01 after commit `be4d755` shipped with 83 integration passes while silently breaking the inning toggle on every InningToggle mount site.

### Sparkline / per-item chart bar count must match SQL

Any chart rendering one bar per (innings / spell / match / event) MUST have an integration assertion that the rendered bar count equals the SQL-anchored item count. The "missing matches" bug on 2026-05-06 was 15 wicketless spells rendering at `height=0` — invisible AND unclickable; SQL said 45, the user counted ~30.

```bash
sql_n=$(sql "$INNS_SQL")
dom_n=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline rect[opacity]').length")
assert_eq "Bar count == SQL n_innings" "$sql_n" "$dom_n"

zero_h=$(ab_eval "Array.from(...).filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars" "0" "$zero_h"
```

Reference: `tests/integration/bowler_distribution.sh` Test 1, `batter_distribution.sh` Test 8.

### Integration tests anchor against `/summary`'s scope_avg, not re-derived SQL

When testing a UI element that displays a value the API computes via the dual-query envelope (the `team=None` league-side fetch combined with team-side — every `MetricEnvelope.scope_avg`), pull the expected value from `/summary` via `curl` rather than re-deriving it in SQL. Re-deriving league-avg in SQL inside the integration test is brittle (200+ lines of denominator logic) AND tests the wrong layer; `/summary`'s sanity tests cover SQL↔API, the integration test covers API↔DOM plumbing.

```bash
api_summary=$(curl -s "$API_BASE/api/v1/teams/$TEAM_URL/batting/summary?$SCOPE_URL")
expected_scope_avg=$(echo "$api_summary" | python3 -c "
import json, sys
print(f'{json.load(sys.stdin)[\"total_runs\"][\"scope_avg\"]:.1f}')")
dom_legend=$(ab_eval "...legend element innerText...")
assert_contains "legend matches API scope_avg" "league avg $expected_scope_avg" "$dom_legend"
```

Reference: `tests/integration/team_batting_distribution.sh` Test 11 / 12.

---

## Cricket invariants

### Catches counts include caught-and-bowled (Convention 3)

When writing or auditing any endpoint that surfaces a `catches` headline at fielder OR team grain, the predicate MUST be `fc.kind IN ('caught', 'caught_and_bowled')` AND `COALESCE(fc.is_substitute, 0) = 0`. C&B is a catch — both in cricket terms and in this codebase's "Convention 3" (codified 2026-04-26 across all `/summary` endpoints; the contract is "`catches` is the inclusive total, `caught_and_bowled` is a sub-count broken out separately so consumers summing both would double-count").

The two distribution endpoints shipped 2026-05-07/08 inadvertently counted `kind = 'caught'` only, silently dropping ~6% of MI's IPL catches and 27% of Bumrah's career catches before being fixed 2026-05-08. The spec text and the integration test SQL both shared the bug — SQL-anchoring tests against the buggy API predicate is internally consistent but semantically wrong.

**Substitute_catches is the explicit exception** — predicate stays `kind = 'caught'` only because substitutes can't bowl by Law (zero C&B-by-substitute exists in the data) AND it's a reconciliation scalar surfaced separately for verification against /summary, not part of the catches block.

**Tells you might be about to repeat the bug:**
- Typing `kind = 'caught'` for a catches headline → inclusive predicate per Convention 3.
- Reading spec §13/§16 from memory and trusting the text — the spec was wrong before the 2026-05-08 fix.
- Integration test passes with `kind = 'caught'` → verify against `/summary`'s catches count (inclusive predicate) as a cross-check before trusting.

Spec: `design-decisions.md` "Convention 3 applies to distribution endpoints, not just /summary".

### Substitute fielders — INCLUDED in /leaders, EXCLUDED in /distribution (by design)

The two endpoints apply different `is_substitute` predicates **intentionally**:

- `/fielders/leaders.catches` — NO `is_substitute` filter. Volume leaderboard ranks "who took the most catches in scope, period."
- `/fielders/{id}/distribution` per-match `catches` — `is_substitute = 0` filter. The master sample is `matchplayer`-based (matches the player was in the squad); substitute appearances aren't in that sample, so counting substitute catches against the matchplayer denominator would miscalibrate per-match averages.
- `/fielders/{id}/distribution.lifetime.substitute_catches` — sibling reconciliation scalar (`is_substitute = 1`).
- `/fielders/{id}/summary.catches` — NO filter (volume framing, matches /leaders).
- `/fielders/{id}/records.most_catches_match` — NO filter (volume framing, matches /leaders). The matchfielderperf precomp table populates from fieldingcredit with no is_substitute predicate; the matchplayer JOIN in the read SQL is for display (team / opponent) NOT for denominator construction, so it doesn't trigger the distribution-side rule.

The asymmetry is **structural** (sample-denominator consistency), NOT a normative judgment that subs don't deserve credit. A sub who took a catch took a catch — leaderboards reflect that; per-match-rate panels can't fold them in without breaking the denominator.

**Tells you might be about to break this:**
- Adding `AND is_substitute = 0` to `/fielders/leaders.catches` to "fix consistency" — DON'T.
- Adding a sub-only match to /distribution's master sample to "include sub catches" — would change /distribution's semantic axis from "matches you played in the squad" to something fuzzier; not the right fix.
- A new endpoint surfacing a `catches` headline that joins `matchplayer` for the master sample — apply `is_substitute = 0` to match /distribution. A new endpoint that's pure volume aggregation (no matchplayer join) — leave subs in to match /leaders.

**Tested by:** `tests/sanity/test_catches_convention3.py::assert_leaders_substitute_leak` locks the algebraic identity `leaders.catches - distribution.catches.total == distribution.substitute_catches`.

Spec: `how-stats-calculated.md` §Fielding "Substitute fielders — INCLUDED in /leaders, EXCLUDED in /distribution (intentional asymmetry)".

### DLS-truncated innings — INCLUDED everywhere (no filter)

DLS-shortened chases (`innings.target_overs < 20`) are NOT filtered or branched on anywhere in `api/routers/`. ~5.9% of 2nd innings in `cricket.db` are DLS-shortened (724 of 12,248). The handling is intentional and codified — do NOT introduce a `target_overs` filter without re-reading this section.

**Two-class rule:**

- **Overs/balls-denominator stats** (run rate, economy, SR, boundary %, dot %, phase rates) — DLS-safe by construction. Every overs-denominator stat divides by actual legal-ball counts from `delivery`; never by an assumed-20-overs number. Verified: zero hardcoded `20` or `20.0` denominators in `api/routers/`. A 12-over DLS chase contributes its real ~60-72 legal balls and the math works.

- **Innings-denominator stats** (Avg innings total, mean_per_innings, wickets_lost / innings_batted, dismissals_per_match) — DLS innings count as 1 innings each. The cricket logic: a 90-run DLS chase that ended in over 12 is structurally identical to a 90-run fast chase that ended in over 12 of a normal 20-over game. Both played one innings, both scored runs, both ended early. Filtering DLS without also filtering fast-chase / all-out-early innings would be inconsistent.

**Tells you might be about to break this:**
- Tempted to add `WHERE i.target_overs IS NULL OR i.target_overs = 20` to a per-innings denominator. → Don't. The mixed treatment with fast-chase innings is the bug.
- Hardcoding `20` as a divisor anywhere. → Use the actual ball count from delivery.
- New endpoint surfaces a "per-innings X" — verify it uses `count(distinct innings.id)` consistently and doesn't accidentally filter DLS via a JOIN that requires `target_overs = 20`.

**Concrete impact** (Mumbai Indians IPL): 0.36 runs/innings swing on Avg innings total from including DLS — small at scale, larger on narrow scopes; accepted as the correct cricket story.

**Tested by:** `tests/sanity/test_predicate_invariants.py` — prints variant-axis inventory + asserts `declared`/`forfeited` stay at zero (non-zero ⇒ schema/data changed, policy needs re-decision).

Spec: `how-stats-calculated.md` "DLS-truncated innings (target_overs < 20) — INCLUDED everywhere" + `server-vs-client-calcs.md` §3.5.

### Scope-anchored form-window cutoffs

Distribution-panel calendar form windows (`last_60d` / `last_6mo` / `last_1yr`) compute cutoffs against `anchor = min(today, max_obs_date)`, NOT today directly. For active subjects in unconstrained scopes the anchor IS today; for retired subjects (Gayle, ABdV) and tightly-scoped subjects the anchor follows the data — the windows mean "the last N calendar days OF SCOPE." Today-direct cutoffs produced empty windows for retired players and for filter-pinned scopes (e.g. Kohli@IPL 2016 with `dist_window=last_1yr`).

Single helper at `api/form_windows.py::scope_anchor`. All three distribution slices import it. New endpoints MUST use it; do NOT re-introduce raw `today - timedelta(days=N)` cutoffs.

Spec: `spec-distribution-stats.md §8.6` + `design-decisions.md` "Form-window cutoffs are scope-anchored, not today-anchored".

### Player/team-aware seasons + scope-anchored quick-select buttons

`/api/v1/seasons` accepts `?person_id=` and `?team=` so the seasons array reflects the subject's actual career-in-scope. Frontend `getSeasons()` forwards URL `?player=` as `?person_id=`.

The FilterBar quick-select buttons (`first-3` / `all-time` / `prev-3` / `last-3` / `latest`) all read from this array → all are subject-aware automatically. Concretely: `last-3` on ABdV sets 2019/20-2021 (his actual final seasons), NOT 2024-2026; `first-3` on Kohli sets 2007/08-2009/10.

Adding a new FilterBar season button? Slice the array; don't re-fetch with different args. New /seasons-consuming endpoints elsewhere? Honour `person_id` / `team` query params symmetrically.

Spec: `design-decisions.md` "FilterBar season-window quick-select buttons — scope-aware AND player-aware".

### Player baseline buckets — opener merged + per-over + keeper-binary

The player-baseline rollout (`spec-player-compare-average.md`, shipped 2026-05-20) locks three bucket definitions across three child tables and four cohort endpoints. Any new endpoint or surface that derives a player cohort baseline MUST use the same buckets to stay comparable:

- **Batting** — 10 position buckets. Bucket 1 = positions 1+2 merged (opener — `derive_positions` assigns the ball-1 striker/non-striker arbitrarily, so splitting them is noise). Buckets 2..10 = positions #3..#11 individual. Position derivation lives at `api/innings_positions.py::derive_positions`; reused across three populate scripts. Child table: `playerscopestats_position`. Cohort endpoint: `/api/v1/scope/averages/players/batting/summary?position_mix=…`.
- **Bowling** — 20 buckets, 1-indexed overs 1..20. Child table: `playerscopestats_over`. Cohort endpoint: `/api/v1/scope/averages/players/bowling/summary?over_mix=…`.
- **Fielding** — binary keeper flag (`is_keeper=0|1`), NOT position-weighted. Position-mix-weighting fielding fails dimensional analysis (per-position catches/match are sub-components of one rate, not separate rates). Per-dismissed-position data still collected in `playerscopestats_fielding_position` for the deferred impact-weighted spec. Cohort endpoint: `/api/v1/scope/averages/players/fielding/summary?is_keeper=…`.

**Sliding-scale thresholds (spec §6):** per-bucket cohort sample minimums. Batting linear `27 − 2·bucket` → 25, 23, 21, 19, 17, 15, 13, 11, 9, 7. Bowling U-shape: 60 at overs 1-2/20, 50 at overs 3-6/16-19, 30 at overs 7-15. Fielding linear `13 − bucket` → 12, 11, 10, …, 3 (used by the next-spec impact-weighted analyses, not by this rollout's headline). Strict cliff: any bucket the player has non-zero mix-weight on must be at or above its threshold; otherwise the entire response's `scope_avg` is null. No drops, no renormalisation.

**Phase 4 child tables (added 2026-05-20 by `spec-player-baseline-parity.md` §3.1):**

- `playerscopestats_batting_phase` — one row per (person, scope_key, phase_bucket); phase_bucket = 1=powerplay (overs 0-5) / 2=middle (6-14) / 3=death (15-19). Same phase boundaries as `populate_player_scope_stats.py::_phase` and the team-side conventions. Backs `/api/v1/scope/averages/players/batting/by-phase` (position-flat — no position × phase precompute).
- `playerscopestats_fielding_phase` — one row per (fielder, scope_key, phase_bucket); same phase mapping. Substitute fielders EXCLUDED at populate (is_substitute = 0). Convention 3: `catches_in_phase` includes c&b. Backs `/api/v1/scope/averages/players/fielding/by-phase`.

By-season + by-phase cohort endpoints exist for all three disciplines (`/scope/averages/players/{batting,bowling,fielding}/{by-season,by-phase}`) — all accept `person_id` (not a caller-supplied mix vector) so the endpoint derives per-season/per-phase mix server-side. Mirror that convention on new variants.

**Tells you might be about to break this:**
- New surface adds a 5-bucket "position-group" batting axis. → Don't. Reuse the 10-bucket axis (collapse client-side if needed).
- Tempted to split opener into "pos 1" vs "pos 2". → Don't. `derive_positions` makes it arbitrary on ball 1.
- New fielding surface wants position-weighted catches-per-match. → That's `spec-fielding-impact.md` territory (deferred). Keep this spec's headline keeper-binary.
- New "by-X" cohort endpoint accepting `position_mix=…` directly. → Don't. By-season/by-phase variants take `person_id` and derive the mix internally; only the lifetime `/summary` endpoints take the mix vector externally (for the compare-grid case where there's no subject player).
- New playerscopestats child table NOT wired into both `import_data.py` (full) AND `update_recent.py` (incremental, touched-scope-recompute pattern). → Wire both; sibling populates establish the contract.

Spec: `internal_docs/spec-player-compare-average.md` §4 + §6; `internal_docs/spec-player-baseline-parity.md` §3.1 + §3.2.

---

## Page conventions

### Status bar derives "all-time" range; URL stays clean

When a subject is in URL (`?player=X` or `?team=X`) and the user hasn't picked a season range, `ScopeStatusStrip` derives `Season: 2005/06–2021 (all-time)` from the seasons fetch and displays it with an italic faint `(all-time)` suffix to signal "computed, not picked." **The URL is NOT auto-mutated.**

Rule: the URL is a faithful record of user choice. Computed values display in the status bar with a visual cue, never as URL params written without user action. See the URL-clean rule under [Code patterns](#code-patterns).

Spec: `design-decisions.md` "Status bar computes the all-time season range".

### Dormancy badge — page-header only

When a subject's last match in scope is more than 60 days before today, a small italic badge renders next to the subject name in `ScopedPageHeader`:

| Gap | Badge |
|---|---|
| ≤ 60 days | (hidden — active in scope) |
| 61–364 days | `5 months since last match` |
| ≥ 365 days | `last match: Oct 2021` |

Page header ONLY (NOT in the status strip — strip describes URL state, dormancy is derived player state; same axis-separation principle as the URL-clean rule).

Wired via `last_match_date` on the distribution endpoints' lifetime block; pages populate `DormancyContext` after the dossier fetch. Adding a new subject-page Distribution panel? Plumb `last_match_date` into the context the same way. New endpoint that needs the dormancy signal? Surface `last_match_date` on the lifetime block (avoids 200-URL regression rotations).

Spec: `design-decisions.md` "Dormancy badge".

### Inning-toggle labels — POV-aware via `useDiscipline()`

`?inning=0/1` always means `innings.innings_number = 0/1` (the match's 1st / 2nd innings half) — the URL semantics are **constant** across pages. The **rendered pill label** is POV-aware, derived from `useDiscipline()`:

| Page POV | `useDiscipline()` | Pills (after "All innings") |
|---|---|---|
| Batting · Partnerships | `'batting'` | `Batting first` / `Batting second` |
| Bowling · Fielding | `'bowling'` / `'fielding'` | `Bowling first` / `Bowling second` |
| Ambiguous (Records, single-player profile) | `null` | `1st innings` / `2nd innings` (neutral) |

**Ambiguous pages stay neutral because the same `?inning=0` token simultaneously means three different POVs on one page.** On Players/Records the batting section reflects batted-first, the bowling section reflects bowled-first, the fielding section reflects fielded-first — all under one toggle. No single POV label can be accurate; the neutral wording forces the reader to interpret per-section.

**Fielding inherits Bowling terminology** — pills say "Bowling first" on `/fielding`, never "Fielded first". The fielding side IS the bowling side in any given innings; "Bowling first" is the standard cricket idiom.

**Partnerships → batting POV** (not null). A partnership is intrinsically a batting concept — both batters belong to the batting team, the wicket that ends it is the batting team's loss. `useDiscipline()` maps `tab=Partnerships` → `'batting'`.

13 mount sites total: 4 batting-POV (Batting + Venue/Batters + Tournament/Batters + Tournament/Partnerships), 6 bowling-POV (Bowling + Fielding + Venue/Bowlers + Venue/Fielders + Tournament/Bowlers + Tournament/Fielders), 3 ambiguous (Players + Venue/Records + Tournament/Records).

**Tells you might be about to break this:**
- New mount site for `InningToggle` on a multi-discipline page → confirm `useDiscipline()` returns `null` there; if it forces a POV that doesn't match the page content, propagate it to ambiguous rather than picking one POV.
- New dossier-style page with `?tab=<axis>` → extend `useDiscipline()` to map the tab, not the rendering layer.
- Tempted to add an explicit `pov` prop to `InningToggle` → don't; `useDiscipline()` is the single source of truth. Extend that hook, not the toggle.
- New aux narrowing (toss, result, batting-position, etc.) that needs a similar POV label → mirror this pattern via `useDiscipline()`, don't roll your own POV resolution.

Tested by `tests/integration/inning_toggle_pov_labels.sh` — Part A asserts pill text per site; Part B locks the ambiguous-page polysemy (one `?inning=0` URL == three POVs simultaneously, SQL-anchored).

Spec: `spec-inning-split.md` §7.1 + `design-decisions.md`.

---

## Palette

Three palette systems, never blurred:

- **Magnitude tiers** (indigo / sage / ochre) — histograms, sparklines, ProbChips on Distribution panels. Polarity tied to OUTCOME for the player (high SR = ochre; high econ = indigo).
- **Outcome traffic light** (`WISDEN_WL` green/amber/red) — **Splits Mosaic only**.
- **Accent strokes** — oxblood `#7A1F1F` for rolling-mean overlay, forest `#3F7A4D` for league-avg reference line.

Reds are reserved across the whole codebase: oxblood (strokes) and `WISDEN_WL.lost` (Mosaic cells). Nowhere else.

Full rules — polarity convention, `WISDEN_TIER_TINTS` chip helper, sparkline visual contract, reference-line table, legend-swatch alignment pattern — in **`internal_docs/colors.md`**.

---

## Splits Mosaic

The Mosaic is a filter widget that LOOKS like a stat chart. URL params drive the visual density (no internal state for expanded/collapsed):

| Aux URL params set | Layout |
|---|---|
| 0 | 2×2 (toss × inning) cells with W/T/L sub-rects per cell |
| 1 | 2×2 of the two free axes |
| 2 | 1D horizontal stacked bar of the one free axis |
| 3 | verbose colloquial status strip — "Won toss · Batted first · Won the game — 3 matches" |

`result` and `toss_outcome` aux filters **require `?team=`** (without a subject team, the unpivoted league-side view makes "won" tautologically 50%). `/teams/splits` returns HTTP 400 when either aux is set without `?team=`.

Full rules — aux semantics, palette reservation, share-denominator-follows-filter, tells — in **`internal_docs/splits-mosaic-discipline.md`**. Design specs: `spec-splits-mosaic.md` (Teams-only — implemented 2026-05-11), `splits-mosaic-cross-page.md` (cross-page reuse DESIGN).
