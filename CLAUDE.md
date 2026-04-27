# CricsDB — T20 Cricket Analytics Platform

## Project Status

Live at: https://t20.rahuldave.com
Repo: https://github.com/rahuldave/cricsdb
deebase PR: https://github.com/rahulcredcore/deebase/pull/8 (adds params to db.q())

## What This Is

Full-stack T20 cricket analytics platform. 12,940 matches (international + 18 club leagues), 2.95M ball-by-ball deliveries, 160K wickets. Data from cricsheet.org.

## Stack

- **Database:** SQLite (435MB, WAL mode) via deebase ORM
- **Backend:** FastAPI, async, raw SQL via `db.q(sql, params)` with bind parameters
- **Frontend:** React 19 + TypeScript + Tailwind CSS v4 + Semiotic v3 charts (ES6-fluent-but-React-new readers: start with `internal_docs/react-primer.md` — it explains how THIS codebase uses React + Vite, not a generic tutorial)
- **Build:** Vite 8 (see `internal_docs/frontend-build-pipeline.md`)
- **Deploy:** pla.sh (see deploy section below)

## Key Files — entry points

Full file-by-file tour lives in **`internal_docs/codebase-tour.md`**. The
recurring entry points:

- `api/app.py` — FastAPI app, CORS, admin, SPA fallback (registered in lifespan AFTER routers)
- `api/routers/` — one file per subdomain (teams, batting, bowling, fielding, keeping, matches, head_to_head, reference)
- `api/filters.py` — `FilterParams` class (Depends), builds WHERE clauses with `:param` bind syntax
- `models/tables.py` — all deebase tables (Person, Match, Innings, Delivery, Wicket, FieldingCredit, KeeperAssignment, Partnership)
- `scripts/populate_*.py` — denormalized-table builders; all auto-called by `import_data.py` + `update_recent.py`
- `frontend/src/pages/` — one file per top-level route (Home, Teams, Batting, Bowling, Fielding, HeadToHead, Matches, MatchScorecard, Help, HelpUsage)
- `frontend/src/content/` — `about-me.md` and `user-help.md` — editable markdown rendered on the `/help` and `/help/usage` routes via `react-markdown`. Edit the `.md`, rebuild, ship. `user-help.md` embeds screenshots from `/social/*.png`.
- `frontend/public/social/` — 18 curated screenshots used by the Help page AND as attachments for the launch `tweet-thread.md` (in the same folder). Paired with `frontend/scripts/assets-source/` where the HTML sources for `favicon.svg`, the apple-touch / 192 / 512 icon PNGs and the 1200×630 `og-card.png` live (regen via headless Chrome — see the sibling README).
- `frontend/src/api.ts` + `types.ts` — endpoint clients + response types
- `frontend/src/components/charts/` — Semiotic wrappers (BarChart, LineChart, ScatterChart, HeatmapChart, BubbleMatrix, WormChart, etc.)
- `frontend/src/components/{Score,EdHelp}.tsx` — shared row-context primitives used across every Matches/Records surface. `Score` renders "185/6 │ 180/5" with optional scorecard link; `EdHelp` emits the standard italic-serif caption explaining the per-row `(ed)` subscript. Mount `<EdHelp />` above any DataTable whose columns carry `TeamLink phraseLabel="ed"`.
- `frontend/src/components/{TeamLink,PlayerLink}.tsx` — both expose the same prop surface for structural parity: `subscriptSource` per-row scope override, `phraseLabel` / `phraseClassName` rendering overrides (use `phraseClassName="scope-phrase-ed"` + `phraseLabel="ed"` for compact small-caps row-edition markers), `maxTiers`, `seriesType`, `keepRivalry`, `compact`, `layout`.
- `frontend/src/index.css` — Wisden editorial styles (see `internal_docs/visual-identity.md`)

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

See `internal_docs/local-development.md` for prerequisites, the project-layout cheat sheet, type-check / build commands, troubleshooting, and how to query the DB from a Python REPL.

## Deploying

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

See `internal_docs/deploying.md` for what does/doesn't ship, the deebase vendoring quirk, the `.plash` identity file, and troubleshooting.

## Rebuilding / Updating the Database

Full pipeline + dry-run format documented in **`internal_docs/data-pipeline.md`**. Canonical commands:

```bash
uv run python download_data.py                      # fetches zips + people/names CSVs
uv run python download_data.py --force              # force-refresh when dry-run flags CSVs stale
uv run python import_data.py                        # full rebuild (~15 min, drops cricket.db)
uv run python update_recent.py --dry-run --days 30  # check what's new
uv run python update_recent.py --days 30            # incremental import
```

Both `import_data.py` and `update_recent.py` auto-populate `fielding_credit`, `keeper_assignment`, and `partnership`. After a DB update, push to plash with `bash deploy.sh --first` (plain `deploy.sh` skips the DB upload).

**Registry refresh diff pattern.** When `update_recent.py --dry-run` reports `people.csv` / `names.csv` as STALE, snapshot the current copies (`cp data/people.csv /tmp/people-before.csv`) before running `download_data.py --force`, then classify the diff into three buckets: **pure additions** (new debutants — expected), **modifications** (same person_id on both sides — almost always cricsheet populating additional external keys like `key_nvplay` / `key_cricinfo_2`; names and core IDs don't change), **pure removals** (id in old but not new — rare, usually cricsheet collapsing a duplicate person_id; check whether the removed id has any references in `matchplayer`/`delivery` before worrying — zero references = harmless orphan). `names.csv` in practice only grows.

To smoke-test `update_recent.py` against a copy of the prod DB before deploying, use `--db /tmp/cricket-prod-test.db` after copying the Downloads snapshot — see **`internal_docs/testing-update-recent.md`** for the copy-to-tmp workflow and what not to do.

Before shipping a refactor of a shared query helper (e.g. `FilterParams`, a router filter fn, a SQL generator) that touches many endpoints, use the HEAD-vs-patched md5-diff harness. The workflow is documented in **`internal_docs/regression-testing-api.md`**; the runner + per-feature URL inventories live at **`tests/regression/`** (use `./tests/regression/run.sh <feature>`). Enumerate every affected URL + a control sample in `tests/regression/<feature>/urls.txt`, tag each `REG` (must match HEAD) or `NEW` (must differ), then the runner does `git stash`/`uvicorn --reload`/diff. Byte-identical `REG` is the proof the refactor is inert where intended. End-to-end browser flows live alongside at **`tests/integration/`** — one bash + `agent-browser` script per feature.

For a complete catalogue of every test in the repo (sanity / regression / integration) — what each tests, when to run it, the invocation — see **`internal_docs/tests.md`**.

## Landing pages (search-bar tabs)

Every search-bar tab — `/teams`, `/players`, `/batting`, `/bowling`, `/fielding`, `/venues` — has a filter-sensitive landing component shown when nothing is selected. Each is backed by a single endpoint (or, for `/players`, a client-side composition of four existing ones):

- **Teams:** `GET /api/v1/teams/landing` — `{international: {regular, associate}, club: [{tournament, teams}]}`. Uses a hardcoded `ICC_FULL_MEMBERS` list in `api/routers/teams.py` for regular/associate split. Club teams grouped by tournament, ordered by match count desc.
- **Batting:** `GET /api/v1/batters/leaders` — `{by_average, by_strike_rate}` top-10. Thresholds `min_balls=100` and `min_dismissals=3` (averages only) exclude tiny-sample winners.
- **Bowling:** `GET /api/v1/bowlers/leaders` — `{by_strike_rate, by_economy}` top-10. Thresholds `min_balls=60` (10 overs), `min_wickets=3` (SR list only).
- **Fielding:** `GET /api/v1/fielders/leaders` — `{by_dismissals, by_keeper_dismissals}` top-10. Volume-based (no thresholds — rank IS the filter). Keeper column uses `keeper_assignment` to count only catches/stumpings taken while the fielder was the designated keeper.
- **Players:** no backend endpoint. `PlayersLanding` renders two curated-tile sections (popular profiles, popular comparisons) with hard-coded person IDs from `components/players/CuratedLists.ts`. Profile tiles fetch one summary per tile (batter or bowler, depending on the tile's annotated primary role) for a one-line stat strip; compare tiles are static. All tiles are filter-sensitive (gender toggles hide the opposite list; tournament/season narrowing scopes the stat strips). Tile clicks set `player` + `gender` (and for compare tiles, also `compare`) atomically — one history entry per pick.
- **Venues:** `GET /api/v1/venues/landing` — `{by_country: [{country, matches, venues: [{venue, city, matches}, …]}, …]}`. Countries ordered by total match count DESC; venues within a country by match count DESC. Filter-sensitive (narrowing to India+men shows only Indian men's venues). Landing tile click sets `filter_venue` and navigates to `/matches?filter_venue=X` (the Phase-2 default drilldown; Phase 3 will swap to a per-venue dossier). The Venues page itself has no "selected venue" mode yet.

The four landing endpoints are filter-sensitive (gender, team_type, tournament, season_from/to) and all landing-row links carry the current filter scope through to the selected-entity page via `URLSearchParams`.

All landings open **all-time** — the old "last 3 seasons" auto-default on Batting/Bowling/Fielding was removed 2026-04-20 at user's request. FilterBar has three inline text buttons: `all-time` clears the season range (always visible, for consistency as a time reset on every page), `latest` pins both ends to the single latest season in the current filter scope (always shown when seasons have loaded — respects gender/team_type/tournament via the FilterBar's scoped seasons fetch), and `reset all` clears every filter (shown when anything is set). The `hooks/useDefaultSeasonWindow` hook still exists unused — kept in case a specific landing wants to opt in later.

**Players tab** (`/players`): person-focused overview. Three modes driven by the URL:
- `/players` → landing (curated profiles + popular comparisons).
- `/players?player=X` → single-player stack of Batting / Bowling / Fielding / Keeping bands, each with an identity line ("specialist batter · 388 matches" etc.) and a `→ Open <discipline> page` link. Bands hide when the player has no data for that discipline in scope.
- `/players?player=X&compare=Y[,Z]` → 2-way or 3-way comparison. Columns stay vertically aligned via per-discipline placeholders ("— no bowling in scope —") and switch to a compact label/value layout so narrow columns don't overflow. Cross-gender adds are refused in-place — the FilterBar's gender chip is the way to switch. Nav-wise, Players is the group parent for `/batting`, `/bowling`, `/fielding` — desktop hover-dropdown + mobile sub-row. The three discipline URLs are unchanged; only their nav presentation moves under Players.

**Teams → Compare tab** (`/teams?team=X&tab=Compare[&compare1=Y[&compare1_…]][&compare2=Z[&compare2_…]]`): parallel to Players compare. **Three columns max** (primary + 2 compare slots); each compare slot has its own `(kind, entity, scope, overrides)` tuple so columns can be independently scoped (RCB 2024 vs RCB 2025 vs IPL 2025 league avg). Side-by-side column grid across **Results / Batting / Bowling / Fielding / Partnerships** rows, compact label/value layout, FlagBadge on each team column (null-renders for franchise sides). Backed by a frontend composer `getTeamProfile(team, scope)` (`api.ts`) that parallel-fetches 12 endpoints per team — fetched against each slot's RESOLVED scope (bound axes inherit from primary, overridable axes from URL `compareN_<filter>` ?? primary). Slots resolve via `useCompareSlots()` (`hooks/useCompareSlots.ts`); Teams.tsx runs a one-shot mount-time migration (useRef-gated, `replace:true`) translating legacy `compare=A,B` / `avg_slot=1` URLs to the new `compareN` shape (slot contiguity also normalized: `compare2` alone shifts to `compare1`). Auto-switch-to-Compare-tab effect fires when a share URL carries any compare slot but no `tab=`, so share links work without the sender copying tab. See `internal_docs/spec-team-compare-scoped-slots.md` for the slot model + `design-decisions.md` "Team Compare" entry for cross-type gating rationale.

**Compare tab — slot kinds + auto-fill avg + per-slot scope override** (Spec of `internal_docs/spec-team-compare-scoped-slots.md`, builds on `spec-team-compare-average.md`):
- **Slot kinds**: each compare slot is `kind='team'` (named team via `compareN=<team>`) OR `kind='avg'` (league baseline via `compareN=__avg__`). The avg kind uses `getScopeAverageProfile()` → `/api/v1/scope/averages/*` (12 mirrors of the team endpoints, helpers `_team_innings_clause` and `_partnership_filter` accept `team=None`); column header is scope-computed (`scopeAvgLabel` in `teamUtils.ts` — e.g. "Indian Premier League 2024 avg"); FlagBadge null-renders.
- **Default first-load auto-fill**: landing on `?team=X&tab=Compare` with no compare slots fills `compare1=__avg__` once-per-mount via useRef gate (`replace:true`). ✕'ing the auto-fill within the same SPA session does NOT bring it back; only fresh mount (hard reload, route away + back) re-fires.
- **Per-slot overrides**: 5 fields can differ per slot — `tournament`, `season_from`, `season_to`, `filter_venue`, `series_type` — encoded as `compareN_<filter>` URL params. `gender` + `team_type` stay BOUND to primary (cross-mode comparison is a category error in this UI). `useCompareSlots` resolves each slot's scope as `urlOverride ?? primary[field]` and stores actually-divergent fields in `slot.overrides`.
- **Slot UI**: `AddCompareSlot.tsx` is a toggleable picker panel with 4 quick-picks (League avg in current scope / Same team, previous season / Different team, current scope / Same team, all-time) plus a team typeahead behind "Different team". `SlotScopeEditor.tsx` is an inline 5-field form mounted under each non-primary column when ✎ is clicked; "Apply" writes only fields differing from primary, "Reset to primary" clears all overrides on the slot. `SlotHeaderChip.tsx` renders an italic sub-line under team-slot names showing the diff (e.g. `· 2025` or `· IPL 2025 · @ Wankhede`); avg slots fold scope into their column label so chip is suppressed.
- **"Previous season" semantics**: walks `/api/v1/seasons?<bound scope>` backward by one — handles biennial events (Aus T20 WC 2024 → 2022/23, NOT calendar-prior 2023), calendar-continuous internationals, BBL `2024/25` strings, sparse associate teams uniformly without per-team-type special cases.
- **Phase bands + partnership-by-wicket sub-rows**: render in every column via shared `PhaseBandsRow.tsx` + `PartnershipByWicketRows.tsx`. Bowling phase `· w` substat + by-wicket `· n` substat both render per-innings (rate, e.g. `1.5/inn`) on team and avg sides — team-side computes from pool/innings, avg-side passes through (already per-innings post-Commit 2 of `spec-avg-column-per-innings.md`). Below the grid, `SeasonTrajectoryStrip.tsx` renders a 2-panel chart strip (Batting RR + Bowling Econ by season) when the scope spans ≥2 seasons.
- **Two-row layout for absolute counts** (Compare tab only, 2026-04-26): a count and an average never share the same row. Fielding (Catches/Stumpings/Run-outs), Bowling (Wickets), and Partnerships (50+/100+) each render TWO rows — pool count (team col only, "—" on avg col) + per-innings rate (both cols, with chip on the rate row when the metric has a direction tag). The pool row carries the team's scale fact ("RCB took 70 catches in 15 matches"); the per-innings row carries the comparable rate ("4.6 catches/innings vs avg 4.21"). `TeamSummaryRow.tsx` synthesizes per-innings chip envelopes via `perInnings(env, divisor)` from existing pool envelopes + the team's `innings_batted` / `innings_bowled` / `matches`. `AvgSummaryRow.tsx` renders pool rows as "—" and /inn rows from the avg endpoint's per-innings field directly. Spec: `internal_docs/spec-avg-column-per-innings.md`.
- **Envelope shape**: `api/metrics_metadata.py` wraps each numeric metric on the 5 team-compare summary endpoints + by-phase + partnerships/by-wicket in `{value, scope_avg, delta_pct, direction, sample_size}`. Each slot's request computes its own `scope_avg` against that slot's scope, so chips on slot 1's "RCB 2025" cell baseline against IPL 2025 avg even when primary is IPL 2024. Identity-bearing nested objects (`highest_total`, `best_pair`, `keepers`, `gender_breakdown`) stay flat. Per-match fielding rates' `scope_avg` is halved at source by `_apply_fielding_per_innings` when the team-side helper is called with `team=None` (each match has 2 fielding sides — team-side comparable is /2). The chip's `scope_avg` is auto-narrowed to the team's tournament universe via `_league_aux(team, aux)` synthesis so it numerically equals the avg endpoint's displayed value (`tests/sanity/test_chip_direction_invariant.py` enforces this on every chip-bearing metric).
- **Backend zero-touch for scoped slots**: every endpoint already takes `FilterParams` per-request via `Depends`; no new SQL, no new endpoints needed for the per-slot scope override. Each column's request is independent.

**Series landing** (`/series`, was `/tournaments`): `GET /api/v1/series/landing` returns sectioned payload — ICC events, bilateral rivalry tiles (split men's / women's, bilateral-only counts), other international, and club buckets (franchise / domestic / women_franchise / other). Tournament tiles → `?tournament=X` dossier. Bilateral rivalry tiles → `?filter_team=A&filter_opponent=B&series_type=bilateral_only` (the same dossier UI scoped to a team pair). Dossier endpoints (`/api/v1/series/{summary,by-season,records,batters-leaders,bowlers-leaders,fielders-leaders,partnerships/*}`) all accept optional `tournament` and `series_type` (`all` / `bilateral_only` / `tournament_only`) — when both filter_team + filter_opponent are set, summary returns `by_team` per-team breakdowns alongside the unified rollup. The nav label is "Series" because cricket uses that term for both bilateral series (Ind vs Aus tour) and tournament-seasons (IPL 2024); `/tournaments` URLs redirect to `/series` so old links still work. The `tournament` query param is unchanged — that's the FilterBar's event_name selector, which is what the `/series/` prefix exists to disambiguate from.

**Head-to-Head** (`/head-to-head`): polymorphic via `?mode=team`. Player-vs-player (`mode=player`, default) is the original batter-vs-bowler view. Team-vs-team (`mode=team&team1=A&team2=B`) reuses `TournamentDossier` to show every meeting between two teams — bilateral series + tournament matches — with a Show pill toggling between `all` / `bilateral_only` / `tournament_only`. Common matchups (top-9 men's + women's) shown as suggestion tiles when no teams selected. Teams > vs Opponent has a "See full rivalry →" link to this view. Canonical home for any two-entity matchup analysis.

**Venues tab** (`/venues`): landing + per-venue dossier. `/venues` (no param) renders a country-grouped tile directory; top 3 countries open by default, the rest collapsed (80+ total). A client-side **search input** above the accordion does substring match on venue+city over the full 456-row landing payload — typing "mumbai" collapses the grid to Wankhede / Brabourne / DY Patil / … across one country (all surviving countries auto-expand while a query is active). No URL param, no backend round-trip per keystroke. `/venues?venue=<canonical>` opens the **per-venue dossier** (Phase 3, shipped 2026-04-18) — tabs Overview / Batters / Bowlers / Fielders / Matches / Records, backed by a single new endpoint `/api/v1/venues/{venue}/summary` (avg 1st-inn total, bat-first vs chase win %, toss decision + win correlation, boundary % + dot % per phase, highest total, lowest all-out, matches hosted by tournament × gender × season) plus reuse of the existing `/batters/leaders`, `/bowlers/leaders`, `/fielders/leaders`, `/matches`, `/series/records` endpoints with `filter_venue=X`. Tile click on the landing goes to the dossier (not `/matches` anymore); the dossier carries a "view all matches →" escape hatch for users who just want the list. The FilterBar's Venue typeahead — which sets ambient `filter_venue` everywhere else in the app — is a no-op on this tab, so a `useEffect` in `Venues.tsx` auto-promotes any incoming `filter_venue` to `?venue=` (replace-mode, so no history entry) and clears the ambient. Net effect: picking a venue from the FilterBar typeahead while on `/venues` acts as a shortcut that opens the dossier; the landing's own search input is the right tool for "show me all Mumbai venues". FilterBar gains a **Venue** typeahead slot (mirrors TeamSearch — `components/VenueSearch.tsx`, 250ms debounce, cancel-on-unmount, scoped to current filters) which drives the ambient `filter_venue` for every other tab; when set the input becomes a chip with a dedicated "× Clear venue" button visible on every tab.

## API reference

For every endpoint — path, query params, example curl, and an abbreviated response — see **`docs/api.md`**. It's the quick-reference companion to `SPEC.md` (which has the underlying SQL + full schemas).

FastAPI also exposes auto-generated interactive docs at **`/api/docs`** (Swagger UI) and **`/api/redoc`** (ReDoc) on both local and prod — the `/api/*` prefix (not the FastAPI default `/docs`) so the Vite dev-server proxy forwards correctly. The help page (`/help`) links to both.

## Keeping docs in sync

**Every feature or substantive change must end with a docs pass.** Before calling a change done (and certainly before committing), scan the doc set and update whatever the change affects. Specifically:

- **Added / changed / removed an API route?** Update **`docs/api.md`** — add or amend the endpoint section (path, one-liner, curl, abbreviated JSON response). Hit the endpoint via `curl` to capture a real response rather than inventing one.
- **Changed a URL scheme, filter param, or response shape on an existing endpoint?** Same — update the affected `docs/api.md` section. Re-curl the example if the shape changed.
- **Added a new router file, a new page, or a new hook?** Update **`internal_docs/codebase-tour.md`** (both the router summary line and the frontend hooks block).
- **Shipped a feature that belongs in the A-O narrative?** Add or amend the entry in **`internal_docs/enhancements-roadmap.md`**; done items stay there as historical markers.
- **Made a non-obvious design decision** (a convention future contributors would otherwise try to change)? Add a bullet to **`internal_docs/design-decisions.md`**.
- **Changed pipeline behaviour, introduced a new invariant the DB must carry, or added a testing workflow?** Touch **`internal_docs/data-pipeline.md`** (and/or `internal_docs/testing-update-recent.md`).
- **Refactored a shared query helper (`FilterParams`, router filter fns, SQL generators) with many callers?** Run `./tests/regression/run.sh <feature>` against a URL inventory at `tests/regression/<feature>/urls.txt`. Workflow + inventory conventions in **`internal_docs/regression-testing-api.md`** + **`tests/regression/README.md`**. Report the pass count before claiming done.
- **Intentionally changed the response shape of an endpoint that has REG entries in `urls.txt`?** Flip those lines from `REG` to `NEW` in a **separate, earlier commit** before the shape change itself. The runner keys on the HEAD-side `kind` column (`kind, hh = head[k]` in `run.sh`), so an uncommitted flip has no effect — it has to be in HEAD when the runner stashes. Workflow: (1) commit the `REG→NEW` flip on affected URLs, (2) commit the backend change, (3) run `./tests/regression/run.sh <feature>` — expected output is `0 REG drifted, N NEW changed, 0 NEW unchanged`.
- **Added a user-visible feature the browser-agent can exercise?** Write or extend the matching **`tests/integration/<feature>.sh`** script. See **`tests/integration/README.md`** for the helper set and when-to-run rules.
- **Introduced a new perf pattern worth reusing?** Add it to **`internal_docs/perf-leaderboards.md`** (or create a sibling `perf-*.md` if scope is different).
- **Changed the page structure, tabs, or search-bar landing?** Update the "Landing pages" and "Key Files" sections of `CLAUDE.md` itself.
- **Changed anything user-visible about the home page, filter bar, or global conventions?** Update the relevant narrative doc and this file's convention list.

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

- Scope-link URLs → `frontend/src/components/scopeLinks.ts`
  (`FILTER_KEYS`, `SubscriptSource`, `resolveBucket`,
  `resolveScopePhrases`, `ScopeContext`)
- **Team / player / series rendering → `TeamLink.tsx` /
  `PlayerLink.tsx` / `SeriesLink.tsx`. Before writing ANY navigation
  to `/teams?…`, `/batting|bowling|fielding|players?…`, or
  `/series?…` — including raw `<Link>` tags, local URL helpers
  (`teamUrl`, `teamLinkHref`), or inline render helpers
  (`renderBatter`, `renderVsTeams`) — READ `internal_docs/links.md`.
  It documents the name-vs-phrase invariant, `subscriptSource`,
  `phraseLabel` (compact token + bracketed-count override), the
  decision tree, common patterns, and the anti-patterns. Nearly every
  cell you think needs a raw `<Link>` is one or two props on the
  existing component.**
- Filter state → `useFilters()`, `FILTER_KEYS`
- Tabular rendering → `DataTable.tsx`
- Score rendering → `Score.tsx`
- Innings-score aggregation in SQL → `scalar-subquery pattern from
  `api/routers/matches.py::inn_rows` / `wkt_rows`

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

Concrete examples of the right move:

- "I need a compact `ed` token after the team name" → add
  `phraseLabel` prop to `TeamLink`, not a parallel `EdTag` component.
- "I need to override TeamLink's rivalry behaviour per-tile" → add
  `keepRivalry` / `seriesType` props (already done 2026-04-20), not a
  parallel `RivalryTeamLink`.
- "I need a per-row scope override" → use `SubscriptSource` +
  `resolveBucket`, not a new `rowScope` helper.

This rule overrides the "just make it work" instinct. A parallel
helper that works in the current call-site is a liability at every
call-site that follows.

## Performance notes

- **Leaderboard landings** (Batting / Bowling / Fielding) depend on two composite covering indexes (`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`) plus fresh `ANALYZE` stats. These are created idempotently by both `import_data.py` and `update_recent.py`. See **`internal_docs/perf-leaderboards.md`** for the diagnosis and the reusable pattern: use `filters.build(has_innings_join=False)` to get a pure match clause, then conditionally drop the innings/match JOINs entirely when no filters are active (avoids 2.95M × 2 PK probes on the delivery scan).
- **deebase pool / async SQLite concurrency** — investigation doc at `internal_docs/perf-async-deebase.md`. TL;DR: deebase's default `AsyncAdaptedQueuePool` (size=5) already gives true concurrent reads in WAL mode; bigger pools yield ~3%. Don't tune deebase for concurrency — push at the application layer (composite endpoints, `asyncio.gather` inside helpers, client-side envelope).
- **Systems / perf catch-all** — `internal_docs/systems-followups.md` is the entry point when starting fresh on any perf or systems-side work (database file layout, where the page-load floor sits, what's safe to ignore, what's NOT safe to touch, reproducible benchmarks).
- **Compare-tab page-load** (Phase 2 — runbook in `internal_docs/perf-bucket-baselines.md`; spec in `internal_docs/spec-team-bucket-baseline.md`). Six `bucketbaseline_*` tables hold per-(gender, team_type, tournament, season, team) aggregates with `team='__league__'` rows for pool-weighted league baselines + identity columns (`highest_inn_match_id`, `lowest_all_out_match_id`, `worst_inn_runs`, `best_pair_partnership_id`, `fifties`, `hundreds`, `count_50_plus`, `count_100_plus`, `wide_runs`, `noball_runs`). `populate_bucket_baseline.py` builds them in ~115s (full) or per-cell (incremental); auto-called from `import_data.py` + `update_recent.py`. Dispatch via `is_precomputed_scope()` in `api/routers/bucket_baseline_dispatch.py`: 12/12 `/scope/averages/*` + 11/12 `/teams/{team}/*` endpoints table-driven for the 90% case (no venue / rivalry / series_type / partial-season filter), live aggregation otherwise. Only `/teams/{team}/partnerships/summary` stays live (best-pair-by-total-runs needs per-(batter1, batter2) aggregation not in schema). Net: unbounded RCB Compare-tab page-load **4s → 0.81s in prod** (5x). Phase 1 (auto-scope-team subquery + `ix_matchplayer_team` index in `api/routers/teams.py::_scope_to_team_clause`) is a prerequisite for the avg-slot semantic correctness.

## Critical Design Decisions

Read `internal_docs/design-decisions.md` for full details. Key points:

- **Over numbering:** DB stores 0-19 (matching cricsheet source). API returns 1-20 (+1 in each router's response). Frontend displays as-is.
- **Phase boundaries:** Powerplay = overs 1-6, Middle = 7-15, Death = 16-20 (in API responses). SQL internally uses 0-5, 6-14, 15-19.
- **Legal balls vs all deliveries:** Batting stats count only legal balls (no wides/noballs). Bowling runs_conceded counts ALL deliveries.
- **Bowler wickets:** Exclude run out, retired hurt, retired out, obstructing the field.
- **Run rate:** Concatenated rate (SUM(runs) × 6 / SUM(legal balls)), NOT mean of per-innings rates. See design-decisions.md "Run rate: concatenated, not per-innings averaged (revisit)" for the why and when-to-revisit.
- **"Average" means per-innings, NOT pool.** Every `/scope/averages/*` numeric field + every chip's `scope_avg` baseline expresses what one batting / bowling / fielding innings yields in scope. Implemented via `_apply_{batting,bowling,fielding,partnerships}_per_innings` helpers in `api/routers/teams.py` (used by both that router AND `scope_averages.py`). The chip-side helper synthesizes `aux.scope_to_team = team` (via `_league_aux`) so the league baseline auto-narrows to the team's tournament universe — same scope the avg endpoint displays. End-to-end mechanism doc: **`internal_docs/perf-bucket-baselines.md`** sections "What 'average' means in this codebase" + "Chip-baseline scope alignment" + "Read-side mechanism — end-to-end data flow" + "Per-innings transform helpers". Chip-direction invariant test (`tests/sanity/test_chip_direction_invariant.py`) enforces `chip_scope_avg == displayed_avg` and direction × side-of-baseline color rule on every chip-bearing metric.
- **Avg-baseline gate: clubs auto-narrow, internationals don't.** The `scope_to_team` synthesis above is gated on `team_type='club'` (closed-league semantic). For closed leagues like the IPL, every team plays every other team, so narrowing the avg col to RCB's tournament universe (= IPL) gives a 10-team symmetric baseline. For internationals, a single team's tournament universe contains that team in every match — narrowing collapses the avg col into a self-centered mirror (Australia 2024-25 in 6 events ⇒ 67-match pool with Aus in all 67). Gates apply on BOTH sides: (1) frontend `TeamCompareGrid.fetchSlot` only sets `scope_to_team` when `team_type === 'club'` and no tournament override; (2) backend `_league_aux(team, aux, filters)` only synthesizes when `filters.team_type == 'club'`. International avg col defaults to the full pool (`Men's T20I 2024-2025 avg` = 870 matches). User can opt into a tighter international pool via the **"+ Full-member avg in current scope"** quick-pick on the avg-slot picker, which sets `team_class=full_member` (matches between two ICC full-member teams only — 140 matches in 2024-25). `team_class` is an `AuxParams` field plumbed through `filters.build()` via `full_member_clause()` in `api/full_members.py` (the canonical full-member list). `is_precomputed_scope` rejects `team_class` so dispatch falls back to live aggregation (bucket tables don't carry the team-class dimension). Time-pinned `tests/sanity/test_avg_baseline_pools.py` asserts the three baseline modes (unbounded / full-member / scope_to_team) on a closed historical window (men_intl 2018) so counts don't drift over time. Spec rationale: `internal_docs/next-session-ideas.md` 2026-04-27 entry.
- **Wides / noballs / catches semantic (Conventions 2 + 3):** Both team-side and avg-endpoint return delivery COUNT for wides/noballs (not run-total) and inclusive `catches` (= catches_only + caught_and_bowled) on every endpoint. Unified 2026-04-26. `caught_and_bowled` exposed as a separate sub-count; consumers MUST NOT add catches + caught_and_bowled (would double-count). See `perf-bucket-baselines.md` Conventions 2 + 3.
- **URL state — URL is the default, but not the only place.** Page-identifying state (player, tab, filters, the active tab's scoped pick) lives in URL search params so a third party opening the URL reconstructs the same view. That criterion — *"can a recipient reproduce this view from the URL alone?"* — is how to decide placement. If yes, URL; if no, one of the three other options: React state (dies on unmount), `sessionStorage` (survives reload, dies on tab close, per-tab), `localStorage` (cross-session — right only for user preferences). Use `useSetUrlParams()` for atomic multi-param updates (two separate `useUrlParam` setters race). Setters default to pushing history so the back button walks the user's filter steps; pass `{ replace: true }` for programmatic auto-corrections (deep-link gender fill, default season window, invalid-state repair). Never call a setter during render — the URL pushes every time, polluting history. Put it in a `useEffect` with `{ replace: true }`. The Series > Batters/Bowlers/Fielders pickers use an **active-URL / dormant-session** split: only the active tab's pick is in the URL; the other two live in sessionStorage so tab round-trips preserve them without cluttering share links. Full discipline + audit list + the picker-memory section in **`internal_docs/url-state.md`**.
- **deebase `db.q()`:** Locally patched to accept `params` dict. Use `:param_name` bind syntax, never f-string interpolation. Exception: list params (`WHERE id IN (...)`) need f-string interpolation — SQLite bind params don't expand lists.
- **SPA fallback:** Must be registered AFTER API routers in the lifespan handler (not at import time) or it catches /api/* routes.
- **Bowling field names differ from batting:** `wickets` not `dismissals`, `runs_conceded` not `runs`. Don't reuse batting types.
- **Scorecard highlight auto-scroll:** The innings-list date links on Batting/Bowling/Fielding pages carry `?highlight_batter=`, `?highlight_bowler=`, or `?highlight_fielder=` (person ID). The scorecard page tints the matching row(s) green (`.is-highlighted`) and scrolls to the first one. Scroll logic is **page-level** in `MatchScorecard.tsx`, gated on both `useFetch` calls resolving, then does `document.querySelector('.is-highlighted')` inside a double `requestAnimationFrame` so layout has settled. Per-InningsCard scrolling was abandoned because sibling async sections (WormChart, MatchupGridChart, InningsGridChart) resized after the scroll fired, displacing the target.
- **Match-list date convention:** ANY table that lists matches (Teams > Match List, Teams > vs Opponent match list, Batting/Bowling/Fielding "Innings List", Matches page results, Partnerships "Top N" date column, etc.) MUST render the `date` cell as a `<Link to={`/matches/${match_id}`}>` with className `comp-link`. Row-click to scorecard is fine as a secondary affordance, but the date link itself is mandatory — users rely on cmd/ctrl-click to open the scorecard in a new tab. When the table is in a player's innings-list context, the link must also carry the appropriate highlight param (`highlight_batter` / `highlight_bowler` / `highlight_fielder` = that person_id) so the scorecard tints + scrolls to their row.
- **Fielder dismissal attribution:** The scorecard API joins `fieldingcredit` per innings and returns `dismissal_fielder_ids: string[]` on each batting row. The frontend uses this to match `highlight_fielder` rather than parsing the dismissal text string.
- **Fielding is universal — role=fielder scope uses `matchplayer`, not `fieldingcredit`.** The scope-aware `/api/v1/players` search narrows role=batter and role=bowler by ≥1 `delivery` in that role (role-specific activity is the natural universe). For role=fielder it instead joins `matchplayer` — every XI member fields, even if they take 0 catches/stumpings/run-outs. Caught on prod 2026-04-21: Jadeja played 11 T20 WC Men 2021/22+ matches with zero fielding credits and was invisible to the fielder picker, even though he was demonstrably "in scope". Sibling rule: `/api/v1/series/fielder-scope-stats` returns a zero-filled entry for squad members with no credits (not `{entry: null}`) — only truly out-of-scope persons null. Do NOT "fix" the asymmetry by narrowing fielder scope back to `fieldingcredit`; the asymmetry is correct. See `api/routers/reference.py::search_players` role=fielder branch + `internal_docs/enhancements-roadmap.md` 2026-04-21.
- **Keeper identification (Tier 2):** Cricsheet has no keeper designation, so we infer it via a 4-layer algorithm (stumping this innings → exactly-1 season-candidate in XI → exactly-1 career-N≥3 keeper in XI → exactly-1 team-ever-keeper in XI). Stored in `keeper_assignment` with nullable `keeper_id` + explicit `confidence` enum. When 2+ candidates match at any layer, the row stays NULL with `ambiguous_reason` + `candidate_ids_json`, and the innings is exported to `docs/keeper-ambiguous/<YYYY-MM-DD>.csv` for later manual/Cricinfo resolution. Manual resolutions (same CSV, `resolved_keeper_id` column) always win — applied last in `populate_full` / `populate_incremental`. See `internal_docs/spec-fielding-tier2.md`.
- **Team-stats FilterBar auto-narrowing (enhancement N):** When a team is selected, `/api/v1/tournaments?team=X` + `/api/v1/seasons?team=X&tournament=Y&...` return only the team's actual context. FilterBar auto-sets team_type/gender when unambiguous (e.g. MI → club). See `internal_docs/spec-team-stats.md`. Extended 2026-04-16 to cover player-page rivalry scope: when URL has `filter_team` + `filter_opponent`, FilterBar feeds both to `/tournaments?team=X&opponent=Y` (returns only tournaments where the two teams actually met). If the result collapses to one entry, tournament auto-sets (MI × CSK → IPL); otherwise tournament stays empty (India vs Australia spans bilaterals + ICC — the rivalry IS the lens).
- **`filter_venue` is an ambient filter.** Lives in `FilterParams` + both hand-rolled pickers (`reference.py::list_teams`, `tournaments.py::_build_filter_clauses`) so every tab respects it. Backend SQL clause is `m.venue = :filter_venue` (exact canonical match — the FilterBar typeahead returns canonical names). Adding a NEW filter is currently a multi-file fan-out (every page's `filterDeps` array); see `internal_docs/design-decisions.md` "filterDeps arrays — explicit, per-page, easy to under-wire (revisit)".
- **Scope-link architecture — unified phrase model.** `PlayerLink` and `TeamLink` both live in `frontend/src/components/` and share the phrase-based subscript API in `scopeLinks.ts::resolveScopePhrases`. Both: name link = identity only (gender for player; gender + team_type for team). The old (e, t, s, b) letter model on `PlayerLink` was retired 2026-04-20 — `TIER_SPECS`, `activeTiers`, `tierParams`, `tierTooltip`, `sameParams` are gone.
  - Container resolution driven by `series_type`:
    - `icc`/`club` + tournament → `at <tournament>` (tournament kept in URL)
    - `bilateral` → `in bilaterals` (tournament dropped — bilateral tournaments are rivalry-specific)
    - unset/`all` + tournament → `at <tournament>` kept **for PlayerLink** and for TeamLink only when there's no rivalry pair (TeamLink drops it in rivalry context; PlayerLink keeps it because a player's "at IPL vs CSK" is meaningful).
  - Rivalry phrase `vs <Opp>` only emitted when caller passes `keepRivalry: true` (PlayerLink). TeamLink passes `false` — destination is a single-team page, so the rivalry pair is always dropped from the URL.
  - Tiers (NARROW → BROAD, chained with commas — critical when a phrase renders immediately after a scope-intrinsic stat, so the first phrase matches the stat's scope):
    - Tier A — narrowest: container + season (+ rivalry if kept) — "at IPL, 2024 vs CSK".
    - Tier B — mid: container (+ rivalry if kept) — "at IPL vs CSK".
    - Tier C — broad: rivalry alone (drops container + season) — "vs India". Only emitted when there's a narrower tier above.
    - Rivalry-only fallback when rivalry is the only axis ("vs India" alone).
  - TeamLink H2 `layout='block'` stacks phrases below the name; wrapper is `inline-block` so "Australia v India" stays on one line.
  - `FILTER_KEYS` is the single source of truth for FilterBar fields participating in scope-link URLs. Adding a new filter = ONE edit; `useFilters`, FilterBar dropdown-narrowing, scope-link URL builder, and `useFilterDeps` all iterate it.
  - `series_type` is intentionally NOT in `FILTER_KEYS` — it's an aux filter (mirrors backend `AuxParams`). `useFilters` surfaces it as a special case; both `TeamLink` and `PlayerLink` read it directly from `useSearchParams`.
  - `ScopeContext` promotes path-identity into filter pinnings for `/teams?team=X`, `/venues?venue=X`, `/head-to-head?mode=team`. Layering: `FilterBar state → ScopeContext → SubscriptSource (per-row override)`.
  - For rivalry-mode leaderboards, `TournamentDossier.rowSubscriptSource` pre-orients `{team1, team2}` per row so the "vs Opp" phrase faces the row's own team (Kohli row → "vs Australia", Smith row → "vs India").
  - Tooltips on each phrase spell out the destination scope so the convention is learnable without docs.
  - **`SeriesLink`** is the `/series?…`-destination sibling of TeamLink/PlayerLink. Thin `<Link>` wrapper that builds its URL from an explicit scope spec (no FilterBar context) — used for tile stretched-link primaries + innings-list tournament cells. See `internal_docs/design-decisions.md` "Series-landing tile convention" for the stretched-link CSS pattern, the "phrase-wraps-name when natural reading is scoped" convention, and the "section title hoists the scope" + "bracketed count carries scope" patterns that keep the bare-name-link-is-always-all-time invariant intact on dense surfaces.
  - **TeamLink opt-in props** (2026-04-20): `keepRivalry`, `seriesType`, `team_type`, `maxTiers`. Defaults preserve pre-existing behavior; tiles pass them to describe row-intrinsic scope without relying on ambient URL state.
- **FilterBarParams + AuxParams split.** `api/filters.py` separates 8 FilterBar UI fields (`FilterBarParams`, mirrors frontend `FILTER_KEYS`) from page-local aux filters (`AuxParams`, currently holds `series_type`). Routers declare `aux: AuxParams = Depends()` alongside `filters: FilterBarParams = Depends()` and call `filters.build(aux=aux)`. `FilterParams` preserved as alias. Future page-local filters (result_filter, close_match, toss_decision) belong in `AuxParams`. **When adding a shared helper that calls `filters.build()`, it MUST take `aux: AuxParams | None = None` as a parameter and pass it through.** Omitting it leaves `aux` as a free variable — import-time silent, request-time 500. Grep `filters\.build\(` in `api/` before shipping a helper refactor; every call site should have `aux=aux` or `aux=None`. This is how the Teams > Partnerships 500 (2026-04-20) lurked across multiple deploys.
- **`series_type` is a global aux filter.** `useFilters()` reads it from URL alongside `FILTER_KEYS` and surfaces it on the FilterParams object. Every API consumer passes `filters` through; the backend lands it in `AuxParams` and applies via `series_type_clause`. The status strip surfaces it as `Show: <label>` on every tab where set. End-to-end coverage: `tests/integration/cross_cutting_aux_filters.sh` (asserts plain ≠ bilateral ≠ icc AND plain = bilateral + icc).
- **`ScopeStatusStrip` mirrors active filters one-line below the FilterBar.** `components/ScopeStatusStrip.tsx`, mounted in `Layout.tsx`. Reads FilterBar fields + aux `series_type` + path identity (`team=` / `player=` / `venue=`). Includes COPY LINK button. Auto-hidden when nothing narrowed. Background tinted `--bg-soft` (slightly darker cream) to visually separate nav/filter chrome from page content.
- **FilterBar dropdown narrowing respects every FilterBar field.** `getTournaments` / `getSeasons` receive the full FilterParams payload plus page-local `series_type`. Backend `/api/v1/tournaments` + `/api/v1/seasons` narrow by `season_from` / `season_to` / `filter_venue` / `series_type` via shared `_reference_clauses`.
- **Venue canonical names never carry a trailing `, <City>` suffix.** Parens-style disambiguators (`County Ground (Taunton)`, `National Stadium (Karachi)`) stay. `resolve_or_raw` applies a `_strip_city_suffix` fallback on dict miss so brand-new cricsheet venues auto-resolve without a worklist round-trip. `update_recent.py` reuses `import_data.import_match_file`, so the hook fires on full rebuild AND incremental paths.

## Active work — pointers

CLAUDE.md is meant to carry only the always-on instructions and
conventions. Everything in-flight, deferred, shipped, or open lives in
the dedicated docs:

- **Next-session agenda + NO DEPLOYS gate + Series/Teams deep-dive
  plan**: `internal_docs/next-session-ideas.md`.
- **A–Q lettered roadmap, dated session logs (what shipped on day X),
  known issues / live TODO, deferred queue**:
  `internal_docs/enhancements-roadmap.md`.
- **"(revisit)" follow-ups + non-obvious decisions worth a paper
  trail**: `internal_docs/design-decisions.md`.

### Build-ready specs (pick up next session)

- **`internal_docs/spec-team-compare-scoped-slots.md`** — per-column
  scope override on Teams Compare so users can do "RCB 2024 vs RCB
  2025 vs IPL 2025 avg". 5 design decisions locked, 3-commit
  rollout plan in the spec, backend zero-touch. Pick-up notes
  (pre-flight checks, gotchas, international test scenarios) live
  in the `project_next_session.md` memory.
