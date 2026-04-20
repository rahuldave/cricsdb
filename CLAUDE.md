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
uv run python import_data.py                        # full rebuild (~15 min, drops cricket.db)
uv run python update_recent.py --dry-run --days 30  # check what's new
uv run python update_recent.py --days 30            # incremental import
```

Both `import_data.py` and `update_recent.py` auto-populate `fielding_credit`, `keeper_assignment`, and `partnership`. After a DB update, push to plash with `bash deploy.sh --first` (plain `deploy.sh` skips the DB upload).

To smoke-test `update_recent.py` against a copy of the prod DB before deploying, use `--db /tmp/cricket-prod-test.db` after copying the Downloads snapshot — see **`internal_docs/testing-update-recent.md`** for the copy-to-tmp workflow and what not to do.

Before shipping a refactor of a shared query helper (e.g. `FilterParams`, a router filter fn, a SQL generator) that touches many endpoints, use the HEAD-vs-patched md5-diff harness. The workflow is documented in **`internal_docs/regression-testing-api.md`**; the runner + per-feature URL inventories live at **`tests/regression/`** (use `./tests/regression/run.sh <feature>`). Enumerate every affected URL + a control sample in `tests/regression/<feature>/urls.txt`, tag each `REG` (must match HEAD) or `NEW` (must differ), then the runner does `git stash`/`uvicorn --reload`/diff. Byte-identical `REG` is the proof the refactor is inert where intended. End-to-end browser flows live alongside at **`tests/integration/`** — one bash + `agent-browser` script per feature.

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

**Teams → Compare tab** (`/teams?team=X&tab=Compare[&compare=Y[,Z]]`): parallel to Players compare. Side-by-side column grid of up to 3 teams across **Results / Batting / Bowling / Fielding / Partnerships** rows, compact label/value layout, FlagBadge on each column (null-renders for franchise sides). Backed by a frontend composer `getTeamProfile(team, filters)` (`api.ts`) that parallel-fetches five endpoints: `team_summary`, `team_batting/summary`, `team_bowling/summary`, `team_fielding/summary`, and a new `team_partnerships/summary` (aggregate counts + highest single partnership + top pair). Cross-gender / cross-team_type adds are prevented upstream by the FilterBar auto-narrow (locks gender + team_type from the primary); the picker additionally rejects any candidate whose in-scope match count is zero. A self-correcting effect in `Teams.tsx` auto-switches `tab` to `Compare` with `{replace:true}` when a share URL arrives carrying `compare=` but no `tab=`, so share links work without the sender needing to copy the tab param too. See `internal_docs/design-decisions.md` "Team Compare" entry for the cross-type gating rationale (and a pre-existing `fielding/summary.matches` bug this surfaced).

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

## Performance notes

- **Leaderboard landings** (Batting / Bowling / Fielding) depend on two composite covering indexes (`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`) plus fresh `ANALYZE` stats. These are created idempotently by both `import_data.py` and `update_recent.py`. See **`internal_docs/perf-leaderboards.md`** for the diagnosis and the reusable pattern: use `filters.build(has_innings_join=False)` to get a pure match clause, then conditionally drop the innings/match JOINs entirely when no filters are active (avoids 2.95M × 2 PK probes on the delivery scan).

## Critical Design Decisions

Read `internal_docs/design-decisions.md` for full details. Key points:

- **Over numbering:** DB stores 0-19 (matching cricsheet source). API returns 1-20 (+1 in each router's response). Frontend displays as-is.
- **Phase boundaries:** Powerplay = overs 1-6, Middle = 7-15, Death = 16-20 (in API responses). SQL internally uses 0-5, 6-14, 15-19.
- **Legal balls vs all deliveries:** Batting stats count only legal balls (no wides/noballs). Bowling runs_conceded counts ALL deliveries.
- **Bowler wickets:** Exclude run out, retired hurt, retired out, obstructing the field.
- **Run rate:** Concatenated rate (SUM(runs) × 6 / SUM(legal balls)), NOT mean of per-innings rates. See design-decisions.md "Run rate: concatenated, not per-innings averaged (revisit)" for the why and when-to-revisit.
- **URL state:** All page state (player, tab, filters) lives in URL search params for deep linking. Use `useSetUrlParams()` for atomic multi-param updates (two separate `useUrlParam` setters race). Setters default to pushing history so the back button walks the user's filter steps; pass `{ replace: true }` for programmatic auto-corrections (deep-link gender fill, default season window, invalid-state repair). Full discipline + audit list in **`internal_docs/url-state.md`**. Never call a setter during render — the URL pushes every time, polluting history. Put it in a `useEffect` with `{ replace: true }`.
- **deebase `db.q()`:** Locally patched to accept `params` dict. Use `:param_name` bind syntax, never f-string interpolation. Exception: list params (`WHERE id IN (...)`) need f-string interpolation — SQLite bind params don't expand lists.
- **SPA fallback:** Must be registered AFTER API routers in the lifespan handler (not at import time) or it catches /api/* routes.
- **Bowling field names differ from batting:** `wickets` not `dismissals`, `runs_conceded` not `runs`. Don't reuse batting types.
- **Scorecard highlight auto-scroll:** The innings-list date links on Batting/Bowling/Fielding pages carry `?highlight_batter=`, `?highlight_bowler=`, or `?highlight_fielder=` (person ID). The scorecard page tints the matching row(s) green (`.is-highlighted`) and scrolls to the first one. Scroll logic is **page-level** in `MatchScorecard.tsx`, gated on both `useFetch` calls resolving, then does `document.querySelector('.is-highlighted')` inside a double `requestAnimationFrame` so layout has settled. Per-InningsCard scrolling was abandoned because sibling async sections (WormChart, MatchupGridChart, InningsGridChart) resized after the scroll fired, displacing the target.
- **Match-list date convention:** ANY table that lists matches (Teams > Match List, Teams > vs Opponent match list, Batting/Bowling/Fielding "Innings List", Matches page results, Partnerships "Top N" date column, etc.) MUST render the `date` cell as a `<Link to={`/matches/${match_id}`}>` with className `comp-link`. Row-click to scorecard is fine as a secondary affordance, but the date link itself is mandatory — users rely on cmd/ctrl-click to open the scorecard in a new tab. When the table is in a player's innings-list context, the link must also carry the appropriate highlight param (`highlight_batter` / `highlight_bowler` / `highlight_fielder` = that person_id) so the scorecard tints + scrolls to their row.
- **Fielder dismissal attribution:** The scorecard API joins `fieldingcredit` per innings and returns `dismissal_fielder_ids: string[]` on each batting row. The frontend uses this to match `highlight_fielder` rather than parsing the dismissal text string.
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
