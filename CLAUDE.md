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
- Build-ready specs: `internal_docs/spec-inning-split.md`, `internal_docs/spec-filterbar-team-class-v3.md`, `internal_docs/spec-filterbar-team-class-club.md`, `internal_docs/spec-distribution-stats.md` (§8 batter v1 IMPLEMENTED 2026-05-05; rest of doc framing remains DRAFT)
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
