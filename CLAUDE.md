# CricsDB — T20 Cricket Analytics Platform

## Project Status

Live at: https://t20.rahuldave.com
Repo: https://github.com/rahuldave/cricsdb
deebase PR: https://github.com/rahulcredcore/deebase/pull/8 (adds params to db.q())

## Pointers

CLAUDE.md is the inviolable-rules file. Everything describing what the
codebase IS (files, endpoints, payloads, formulas, design decisions) lives
in dedicated docs — go there before making assumptions.

**Orientation**
- Codebase tour (file-by-file): `internal_docs/codebase-tour.md`
- React + Vite primer (this codebase, not generic): `internal_docs/react-primer.md`
- Frontend build pipeline: `internal_docs/frontend-build-pipeline.md`
- Visual identity / Wisden styles: `internal_docs/visual-identity.md`
- Local dev prerequisites + REPL: `internal_docs/local-development.md`

**Domain + UX**
- Landing pages on every search-bar tab + Compare slots + Series/H2H/Venues structure: `internal_docs/landing-pages.md`
- API reference (every endpoint, curl, response): `docs/api.md` — also `/api/docs` (Swagger) and `/api/redoc` on local + prod
- Stat formulas (run rate, economy, win %, per-innings/per-team transforms): `internal_docs/how-stats-calculated.md`
- Design decisions (over-numbering, db.q params, legal balls, URL state, scope-link architecture, FilterBarParams/AuxParams, etc.): `internal_docs/design-decisions.md`
- URL state discipline: `internal_docs/url-state.md`
- Link components (TeamLink / PlayerLink / SeriesLink contract — read before writing ANY navigation): `internal_docs/links.md`

**Data + ops**
- Data pipeline (download, import, update_recent): `internal_docs/data-pipeline.md`
- Smoke-test update_recent against /tmp DB: `internal_docs/testing-update-recent.md`
- Deploying: `internal_docs/deploying.md`

**Performance**
- Leaderboard landings (composite indexes, pure-match-clause pattern): `internal_docs/perf-leaderboards.md`
- deebase pool / async SQLite: `internal_docs/perf-async-deebase.md`
- Compare-tab page-load (bucketbaseline): `internal_docs/perf-bucket-baselines.md`
- Systems / perf catch-all: `internal_docs/systems-followups.md`

**Testing**
- Test catalogue (sanity / regression / integration — what each tests + when to run): `internal_docs/tests.md`
- Regression harness (HEAD-vs-patched md5-diff for shared-helper refactors): `internal_docs/regression-testing-api.md` + `tests/regression/`

**Active work**
- Next-session agenda + NO-DEPLOYS gate: `internal_docs/next-session-ideas.md`
- A–Q lettered roadmap, dated session logs, deferred queue: `internal_docs/enhancements-roadmap.md`
- Build-ready specs: `internal_docs/spec-inning-split.md`, `internal_docs/spec-filterbar-team-class-v3.md`, `internal_docs/spec-filterbar-team-class-club.md`, `internal_docs/spec-distribution-stats.md` (§8 backend + §9 frontend IMPLEMENTED 2026-05-05; v2 extension 2026-05-06 added 6mo+1y form windows, conditional milestones, "Scope" rename, sparkline 20-run reference line; rest of doc framing remains DRAFT)
- Club-tier classification (read before classifying a new club league): `internal_docs/club-tier-classification.md`. Anchor numbers: `internal_docs/club-tier-anchor-numbers.md`.

## Running Locally

```bash
# Terminal 1 — backend
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` → port 8000.

**UI verification (any frontend work must go through this):** After any
change to files under `frontend/src/`, you MUST use the `agent-browser`
skill to load the affected page(s) in a real browser, exercise every
new tab/component, apply the relevant FilterBar combinations (incl.
single-season), hover interactive elements (tooltips, heatmap cells),
and click every link to confirm it navigates. `tsc --noEmit` and
`npm run build` only verify code correctness, not feature correctness.
Do not claim UI work is complete without a browser-agent run.

**Mobile viewport check is part of UI verification, not optional.**
For any new component / layout / panel / stat-row, check at a phone
viewport (`agent-browser set viewport 390 844` then `reload`)
BEFORE committing. Common failure modes:
- A grid with `minmax(0, 1fr) minmax(220px, …)` squeezes the first
  column to ~98px on a 342-wide panel — the histogram or chart
  becomes invisible at that width. Use a CSS class with a
  `@media (max-width: 720px) { grid-template-columns: 1fr }`
  fallback (inline `style={{}}` can't do media queries — extract
  to a `wisden-*` class in `index.css`).
- Inline widgets that work fine on desktop (toggles, milestone
  chip rows, form-delta lines) need `flex-wrap: wrap` to drop to
  the next line on mobile, or they overflow the panel.
- `grid-template-columns: repeat(N, 1fr)` with N > 3 typically
  needs to drop to fewer columns on mobile via a media-query
  override.

**A frontend change is not "done" until both desktop and mobile
viewports look right.** Reproduce the user's exact URL at both
widths; the panel that reads great on a 1280-wide laptop can be
broken (literally invisible content) on a 390-wide phone.
The user flagged this 2026-05-06: a width-`1fr | minmax(220, 320)`
grid silently zero'd the histogram column on mobile while sailing
through desktop verification.

**DO NOT SPECULATE — verify before proposing a fix or explanation.**
When the user reports a bug or asks why something looks/behaves a
certain way, do NOT reason from code-reading or prior assumptions and
guess what's wrong. First REPRODUCE: load the URL with agent-browser
and observe what's actually rendered, click the actual control,
query the DB, run the actual test. Then propose. Phrases like
"this might be because…", "probably the X is Y…", "I bet the issue
is…" are tells that you're about to ship a speculative fix — STOP
and verify first. The user has flagged this twice (2026-04-29):
speculation that turns out wrong wastes a round-trip; speculation
that "matches what they're seeing" by accident sets the wrong fix
in motion. Reproduction is cheap (one agent-browser call); guessing
costs the user trust.

**DO NOT defer parts of an assigned task without asking.** When the
user gives you a task — "add per-page Twitter cards", "wire up X for
the whole app" — finish it. Don't ship the easy half and pitch the
rest as a follow-up ("I deferred the player/match routes since they
need DB lookups"). If a part is genuinely out-of-scope or needs a
different design call, ASK before cutting it; don't decide
unilaterally. The "shipped + deferred" pattern reads as scope-
shaving and forces the user to re-prompt for the work they already
asked for. User flagged 2026-04-29 after a per-page social-meta
task shipped 4-of-6 route patterns and deferred the two that
needed an `await db.q(...)` lookup. The fix isn't more deferral
discipline — it's finishing the job.

**On bug reports — understand the bug first, propose, then wait.**
When the user reports a bug ("X doesn't work", "Y looks broken",
"why does Z behave like this"), the response sequence is:
1. **Reproduce.** Load the URL with agent-browser, query the DB,
   run the test. Confirm what's actually wrong before forming a
   hypothesis. (See "DO NOT SPECULATE" above.)
2. **Identify the root cause.** Code path, data state, design
   choice — name the actual mechanism, not a plausible-sounding
   guess.
3. **Explain to the user what you found AND propose 1-3 possible
   fixes with trade-offs.** Two-three sentences each, not a wall
   of code.
4. **WAIT for the user's call.** Do NOT ship the fix in the same
   turn unless explicitly told to ("just fix it"). The user
   knows their codebase and may pick a different fix than what
   you'd propose, OR may decide the behavior is correct and the
   bug report was a misunderstanding.

This rule is stricter than "discuss design before coding"
because bug reports often LOOK like routine fixes but turn out
to be design questions in disguise. User flagged 2026-05-08
after a session where a bug report ("status bar broken") got
fixed (clicking all-time button now sets explicit range) but
the actual user intent was different (auto-apply on landing).
Mid-session ship landed the wrong fix; round-trip wasted.

Tells you're about to skip this rule:
- You jump to a code edit without first reading what's there.
- You announce "Going to ship this now" / "Implementing the
  fix" before the user has confirmed the diagnosis.
- Auto mode is on and you treat it as a license to ship without
  pause — auto mode is for routine work, NOT for bug-fix
  decisions. Bug reports always pause for explicit
  confirmation.

**Audit prompt discipline:** when asking agent-browser to verify, ask
for RAW OUTPUT, not verdicts. "List every section header with the first
row label per column" is checkable. "Verify all sections render" is a
summary that drops information — when the agent reports PASS but
walked the wrong cells, the bug ships. The 2026-04-27
"empty-section bug on the avg column" landed because a Commit-5
audit prompt asked for value sanity-checks instead of cell-by-cell
text. From there on, audits should:
- Request the literal text content of each cell/section the assertion
  cares about, not a yes/no.
- For each assertion you'd put in an integration test, write the test
  AT THE SAME TIME, not after a bug surfaces. One-shot browser audits
  are exploratory. Checked-in `tests/integration/<feature>.sh`
  assertions are durable.

**Page header convention — `ScopedPageHeader` for every scoped page.**
Every page that takes FilterBar narrowings (Batting / Bowling /
Fielding / Players / Teams / Series / Venues / HeadToHead) renders
its title via `frontend/src/components/ScopedPageHeader.tsx`:
title content + flag on the left, "SCOPE <abbreviated narrowings>"
small italic on the right, flex-wrap to a second row on mobile.
The component reads `abbreviateScope(filters)` from
`scopeLinks.ts`. Pass `omit={['tournament']}` etc. on dossier pages
where the page subject IS one of the scope axes (Series omits
`tournament`, Venues omits `filter_venue`) to avoid duplicating
the title in the abbreviation. The status-strip "SCOPE" pseudo-
segment between path-identity and FilterBar narrowings establishes
the same vocabulary at the top of the page. New scoped page →
use `ScopedPageHeader`, do NOT re-roll the H2 + flag JSX inline.

**`abbreviateScope` is the source of truth for "what's in scope".**
When you add a new FilterBar field or AuxParam that affects what
data the user is looking at, ALSO add it to `abbreviateScope` in
`scopeLinks.ts`. The 2026-05-06 inning-missing bug surfaced because
inning is an AuxParam, not in `FILTER_KEYS`, and the abbreviation
silently dropped it. The audit pattern: for every axis in
`FilterParams`, ask "does setting this change what data is shown?"
If yes, it's in scope and belongs in the abbreviation. The
`ScopeStatusStrip` is the parallel reference list — both should
emit the same axes.

**URL state for "what view am I looking at".** Anything that
selects between pre-fetched dossiers / view modes / windows /
toggles MUST encode in the URL via `useUrlParam` so share-link
reproducibility holds. The default value is encoded by ABSENCE
of the param (saves URL noise on the canonical default).
Per-panel keys use a panel-specific prefix (`dist_window` for the
Distribution panel; `compareN_inning` for Compare slot inning
override) so they don't collide. `feedback_state_location.md` —
share-link reproducibility wins; if you send someone a link to
"Kohli's last-10 form", the receiver should land on the same view.

**Single-payload + window-toggle pattern.** When an endpoint can
return multiple related views in one response (e.g. lifetime +
last_10 + last_60d + last_6mo + last_1yr in
`/api/v1/batters/{id}/distribution`), prefer a single roundtrip
over per-view fetches. The frontend toggle then redraws from the
in-memory payload — no refetch, instant switching. Cost: payload
size grows linearly with N views. Acceptable when each view is
the same shape and N is small (≤6). Spec:
`internal_docs/spec-distribution-stats.md §8.6` + §9.2.1.

**API-frontend type contract:** when a backend change drops a field
from a response, drop it from the matching TypeScript interface in
`frontend/src/types.ts` IN THE SAME COMMIT. Type-API divergence is
what turns "field missing at runtime" into a silent fall-through
through `?. ?? 0` — TypeScript believes the type, the gate evaluates
to `0 > 0`, the UI hides itself. Tightening types alongside the
backend change makes `tsc -b` catch the next consumer.

**Integration tests must self-anchor against SQL.** Numeric
expected values in `tests/integration/<feature>.sh` (Matches counts,
Runs, RR values, leaderboard sizes, baseline-avg numerator/denominator)
must be **derived from `cricket.db` at test runtime**, not hardcoded
literals. Pattern:

```bash
expected=$(sqlite3 "$DB" "SELECT COUNT(*) FROM match WHERE …")
actual=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "label" "$expected" "$actual"
```

Three-layer chain:
- **Sanity** (`tests/sanity/test_*.py`) asserts SQL ↔ API.
- **Integration** (`tests/integration/*.sh`) asserts DOM ↔ SQL via
  the running app (transitively SQL ↔ API ↔ DOM).
- **Regression** (`tests/regression/<feature>/urls.txt`) asserts
  no-drift across refactors at the API layer.

If you hardcode `assert_eq "label" "548" "$actual"`, a bug that
drifts the API to 548-by-coincidence (or that drifts both API and
DOM together) silently passes. The DB is the source of truth — if
the test computes its expected value from SQL each run, the test
self-corrects against DB updates AND surfaces drift the moment
either API or DOM departs from SQL. The team_class club-tier work
shipped a `filterDeps`-missing bug on 7 of 8 entry pages because
the original integration tests asserted hardcoded counts on Teams
only; flipping to SQL-derived anchors lets the test walk every
page and surface mismatches at the page that's actually broken.

`tests/integration/team_class_club_per_page_refetch.sh` is the
reference implementation. New shell tests follow that shape:
`sql()` helper wraps `sqlite3 $DB`, every `assert_eq` reads its
expected from `$(sql ...)`. Keep IN-list constants (FM frozenset,
PRIMARY/SECONDARY club leagues, ICC events) inline at the top of
the script, mirroring the Python source-of-truth — divergence
between the two surfaces immediately because both sanity and
integration run against the same DB but different SQL strings.

**No hacks where a structural fix exists.** When a clean, idiomatic
solution and a hack both look like they'd "work," ship the clean
one even if the hack is faster to write. The hack lands as a
liability that compounds at the next refactor. Tells you're about
to ship a hack:
- Reading `window.location.*` synchronously inside a React effect
  to dodge a desync between live URL and React state. → The
  codebase's idiom is `useRef` once-per-mount gates (see the
  legacy-compare migration in `pages/Teams.tsx`, and
  `TournamentDossier.tsx`'s `prevFilterKey` ref). Match it.
- Computing pixel values from observed agent-browser measurements
  ("agent measured 73px, so I'll use 4.6rem"). → That's a CSS
  Grid / subgrid problem (already documented under "No CSS-pixel
  shortcuts" below).
- Reaching for `setTimeout` / extra `sleep` to "let things
  settle" inside production code (test settle is fine). → React
  state isn't a race; if you need to sequence two updates,
  derive one from the other.
- Adding a feature flag / `if (process.env.NODE_ENV)` to bypass
  StrictMode dev-replay. → StrictMode replay is the test surface;
  if your effect can't survive it, the effect is wrong.

User flagged 2026-05-01 after a fix used live `window.location.search`
in an effect to disambiguate "tab missing" from "tab=non-Compare,"
where the established pattern (used twice in the codebase already)
was a `useRef` once-per-mount gate. Both worked; the hack was
inconsistent with the codebase and would degrade future
maintainability. Default: read the surrounding 100 lines first; if
you see an established pattern for this class of problem, match it.

**Tests must cover EVERY call site of a shared abstraction.** When
you fix a bug in a shared helper (`useFilterDeps`, `FilterParams`,
a SQL generator), the integration test must exercise every page
that consumes it — not just the page where the bug surfaced. A
test that hits 1 of 10 call sites passes through the next
refactor that re-breaks 9 of them. Pattern: enumerate the call
sites with `grep -rn 'helperName' src/` and write one assertion
per site. User flagged 2026-05-01 after commit `be4d755`
(useFilterDeps migration) shipped with 83 integration passes
while silently breaking the inning toggle on every InningToggle
mount site — the green tests covered only `team_class` clicks,
the migration's marquee feature. The reference test for this
shape is `tests/integration/inning_per_page_refetch.sh`: 10 mount
sites × click-after-mount × 4 toggle states × SQL-anchored DOM
assertions.

See `internal_docs/local-development.md` for prerequisites, the project-layout cheat sheet, type-check / build commands, troubleshooting, and how to query the DB from a Python REPL.

## Deploying

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

See `internal_docs/deploying.md` for what does/doesn't ship, the deebase vendoring quirk, the `.plash` identity file, and troubleshooting.

## Keeping docs in sync

**Every feature or substantive change must end with a docs pass.** Before calling a change done (and certainly before committing), scan the doc set and update whatever the change affects. Specifically:

- **Added / changed / removed an API route?** Update **`docs/api.md`** — add or amend the endpoint section (path, one-liner, curl, abbreviated JSON response). Hit the endpoint via `curl` to capture a real response rather than inventing one.
- **Changed a URL scheme, filter param, or response shape on an existing endpoint?** Same — update the affected `docs/api.md` section. Re-curl the example if the shape changed.
- **Added a new router file, a new page, or a new hook?** Update **`internal_docs/codebase-tour.md`** (both the router summary line and the frontend hooks block).
- **Shipped a feature that belongs in the A-O narrative?** Add or amend the entry in **`internal_docs/enhancements-roadmap.md`**; done items stay there as historical markers.
- **Made a non-obvious design decision** (a convention future contributors would otherwise try to change)? Add a bullet to **`internal_docs/design-decisions.md`**.
- **Added or changed a metric formula** (run rate, economy, win %, a transform, an exclusion rule)? Update the matching section in **`internal_docs/how-stats-calculated.md`** with the new formula + WHY. The doc grows with the codebase; never let a formula go undocumented.
- **Changed pipeline behaviour, introduced a new invariant the DB must carry, or added a testing workflow?** Touch **`internal_docs/data-pipeline.md`** (and/or `internal_docs/testing-update-recent.md`).
- **Refactored a shared query helper (`FilterParams`, router filter fns, SQL generators) with many callers?** Run `./tests/regression/run.sh <feature>` against a URL inventory at `tests/regression/<feature>/urls.txt`. Workflow + inventory conventions in **`internal_docs/regression-testing-api.md`** + **`tests/regression/README.md`**. Report the pass count before claiming done.
- **Intentionally changed the response shape of an endpoint that has REG entries in `urls.txt`?** Flip those lines from `REG` to `NEW` in a **separate, earlier commit** before the shape change itself. The runner keys on the HEAD-side `kind` column (`kind, hh = head[k]` in `run.sh`), so an uncommitted flip has no effect — it has to be in HEAD when the runner stashes. Workflow: (1) commit the `REG→NEW` flip on affected URLs, (2) commit the backend change, (3) run `./tests/regression/run.sh <feature>` — expected output is `0 REG drifted, N NEW changed, 0 NEW unchanged`.
- **Added a user-visible feature the browser-agent can exercise?** Write or extend the matching **`tests/integration/<feature>.sh`** script. See **`tests/integration/README.md`** for the helper set and when-to-run rules.
- **Introduced a new perf pattern worth reusing?** Add it to **`internal_docs/perf-leaderboards.md`** (or create a sibling `perf-*.md` if scope is different).
- **Changed the page structure, tabs, or search-bar landing?** Update **`internal_docs/landing-pages.md`**.
- **Changed anything user-visible about the home page, filter bar, or global conventions?** Update the relevant narrative doc.

If the change is genuinely trivial (typo, whitespace, one-line comment), skip. Otherwise default to updating — undocumented features decay fastest.

## Commit cadence

**Commit as soon as a feature looks complete — don't batch.** One
logical change per commit, committed at the moment it reaches a
runnable state (type-check passing, feature working in the browser,
tests still green). Sessions that accumulate 30 files of uncommitted
work across five unrelated features make `git bisect` useless — if a
later change breaks something that worked two features ago, the
bisect lands on a mega-commit and the signal is gone. Small commits
are cheap; lost-bisect debugging is not.

Concretely: if you just finished "X" and "X works", commit X before
starting "Y". Even if Y is obviously the next step, the atomicity is
the point. Don't wait for the whole arc to finish.

## Extend existing abstractions — do NOT fork parallel helpers

**Before writing a new helper or component, find the existing API that
already solves this class of problem, and extend it with a narrow
option.** The codebase has deliberate, maintained APIs for recurring
patterns:

- Scope-link URLs → `frontend/src/components/scopeLinks.ts` (`FILTER_KEYS`, `SubscriptSource`, `resolveBucket`, `resolveScopePhrases`, `ScopeContext`)
- **Team / player / series rendering → `TeamLink.tsx` / `PlayerLink.tsx` / `SeriesLink.tsx`. Before writing ANY navigation to `/teams?…`, `/batting|bowling|fielding|players?…`, or `/series?…` — including raw `<Link>` tags, local URL helpers (`teamUrl`, `teamLinkHref`), or inline render helpers (`renderBatter`, `renderVsTeams`) — READ `internal_docs/links.md`. It documents the name-vs-phrase invariant, `subscriptSource`, `phraseLabel`, the decision tree, common patterns, and the anti-patterns. Nearly every cell you think needs a raw `<Link>` is one or two props on the existing component.**
- Filter state → `useFilters()`, `FILTER_KEYS`
- Tabular rendering → `DataTable.tsx`
- Score rendering → `Score.tsx`
- Innings-score aggregation in SQL → scalar-subquery pattern from `api/routers/matches.py::inn_rows` / `wkt_rows`

When a new surface's needs don't fit an existing API's shape (label
text, URL shape, render variant), **add a narrow prop / render-prop /
override to that API**, don't write a sibling helper that duplicates
its logic. Duplicated mechanisms drift: one path gets a bug fix, the
other silently keeps the bug; one path learns a new filter key, the
other silently ignores it.

If you find yourself typing `teamXHref(...)`, `EdTag`, `scoreCell`,
`playerYTag` alongside existing `TeamLink` / `Score` / `PlayerLink`,
stop and ask: **"why can't the existing API do this with one more
prop?"** The answer is almost always "it can — I just didn't read it
first." Reading 100 lines of the existing module is cheaper than
maintaining two pipelines that are supposed to stay in lockstep.

This rule overrides the "just make it work" instinct. A parallel
helper that works in the current call-site is a liability at every
call-site that follows.

## No CSS-pixel shortcuts when a structural fix exists

**When a layout problem has a clean structural solution — CSS Grid /
subgrid for cross-column row alignment, semantic flex for inline
content, baseline grids for typography — use the structural fix even
if a `min-height: 4.6rem` / `padding-top: 12px` hack would land in 30
minutes.** Pixel hacks are tuned to one viewport width, one chip
density, one font-stack. The next content change (a new metric, a
longer chip, a different season span) shifts the magic number and
the layout breaks.

**Tells that you're about to take a shortcut:**

- You're typing `min-height` because "the team col wraps to 2 lines but the avg col fits on 1." → That's a subgrid problem. Make both cells the same grid track and let it size to max content.
- You're adding `padding-top` to push one element down to match another. → They should be in the same row of a grid.
- You're using `position: absolute` to overlay something to dodge a sibling's height. → The sibling should be in a separate grid track (or a different DOM ancestor).
- You're computing pixel values from observed measurements ("agent measured 73px, so I'll use 4.6rem"). → Subgrid would size to 73px without you needing to know the number.

**When the shortcut is genuinely correct:** sub-pixel rounding (e.g.
`transform: translateY(-1px)` to fix a 0.5px gap), aspect-ratio
reservation for an image whose dimensions are known at build time,
padding for visual polish that's not load-bearing for alignment.
These are *cosmetic* uses; they don't carry alignment correctness on
their backs.

User feedback that drove this rule (2026-04-27): "shouldn't a grid
not have this problem?" — yes. If the answer to that question is
"in principle yes but I took a shortcut," refactor.

## Distribution-panel color discipline (3-tier palette)

**One semantic 3-tier palette is shared across histograms,
sparklines, AND probability chips on every distribution panel.**
Never let chip colors drift from the histogram tier color of the
same threshold — that "the chip is green but the bar at this
value is gray" inconsistency is what the user flagged twice on
2026-05-06 ("the colors of the pills did not change in response
to our color changes" / "Why is the color co-ordination off?").

The three semantic tiers (`frontend/src/components/charts/palette.ts`):
- **INDIGO** `#7090A8` — poor outcome for the player
- **SAGE**   `#7A8E6A` — typical
- **OCHRE**  `WISDEN.ochre` — really good ("hot")

**Polarity convention** — color is tied to OUTCOME for the player,
not bin index:
- Higher-is-better metrics (runs, wickets, SR): low→indigo,
  mid→sage, high→ochre.
- Lower-is-better metrics (economy, runs conceded): low→ochre,
  mid→sage, high→indigo (polarity flipped — low econ is good).

**Chip-tint helper:** `WISDEN_TIER_TINTS` exports `{indigo, sage,
ochre}` → `{bg: rgba, fg: hex}` pairs. The `ProbChip` component
takes a `tint` prop directly (not a `polarity`); each chip caller
picks the tier its threshold falls in. So `<ProbChip
tint={T_OCHRE} ...>` for `P(≥3)` on the wickets tab matches the
strike-tier histogram bar at value 3.

**Reds are reserved for the rolling-mean overlay (oxbow)** —
NEVER used in tier coloring. The "failure"/"wicketless" tier was
flipped from muted red to muted indigo on 2026-05-06 so red
exclusively signals the rolling overlay.

**Sparkline visual contract** (codified
`frontend/src/components/distribution/DistributionSparkline.tsx`):
- Bar opacity 0.8 (blue/indigo tier overrides to 1.0 — washes
  out worst at 0.8); per-bar `opacity` field on `SparklinePoint`.
- Reference lines: black scope-baseline (2px) + gray gender-global
  (1.5px) + red rolling-10 mean (1.2px) on the Scope window only.
- Below-baseline 4px stub zone — every bar (including value=0)
  has a clickable footprint; the user-flagged "missing matches"
  bug was zero-height bars vanishing.
- Mobile (< 720px): bar `<a>`s get `pointer-events: none` —
  sparkline is impressionistic only; navigation via the season-
  tick axis context + the page's existing By Innings tab.

Spec: `internal_docs/spec-distribution-stats.md` §10.3 +
§12.2.6.

## FilterBar cascade-clear rule (auto-correct loops)

**When the user clears a coupled filter (gender / team_type),
also clear any dependent narrowing (tournament).** The FilterBar
runs auto-correct deep-link effects that fill missing fields from
a tournament's metadata (e.g. tournament=IPL → team_type=club).
If the user then clears team_type back to "All" but tournament
stays, the auto-correct re-asserts team_type=club from the
tournament. "Spring-back" UX bug — flagged 2026-05-06.

The fix in `setGender` / `setTeamType`: cascade-clear the
dependent tournament when v is empty OR mismatched. Pattern:
```ts
if (t && (!v || t.team_type !== v)) updates.tournament = ''
```
NOT `if (t && v && t.team_type !== v)` — the `&& v &&`
short-circuits on the user's "clear" click.

**When adding a NEW auto-correct deep-link effect:** make sure
the user-clearing path on every filter that participates also
cascade-clears the inferred narrowings — otherwise the auto-
correct loop fights the user. Test coverage:
`tests/integration/filterbar_cascade_clear.sh`.

## Sparkline / per-item chart bar count must match SQL

**Any chart rendering one bar per (innings / spell / match /
event) MUST have an integration assertion that the rendered bar
count equals the SQL-anchored item count.** The user-flagged
"missing matches" bug on 2026-05-06 was 15 wicketless spells
rendering with `height=0` → invisible AND unclickable; SQL said
45 spells, the user counted ~30 visible bars.

Pattern (see `tests/integration/bowler_distribution.sh` Test 1
+ `batter_distribution.sh` Test 8):
```bash
sql_n=$(sql "$INNS_SQL")
dom_n=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline rect[opacity]').length")
assert_eq "Bar count == SQL n_innings" "$sql_n" "$dom_n"

zero_h=$(ab_eval "Array.from(...).filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars (would be invisible)" "0" "$zero_h"
```

The class of bug this catches: any per-item chart where some
items render at zero size (height/width/area) and silently vanish
from the DOM-visible count even though they exist in the data.
