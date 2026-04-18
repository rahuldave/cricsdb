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

Batting/Bowling/Fielding landings additionally default `season_from`/`season_to` to the last 3 seasons in scope via `hooks/useDefaultSeasonWindow` — one-shot per mount, writes to URL so FilterBar reflects it. FilterBar has three inline text buttons: `all-time` clears the season range (always visible, for consistency as a time reset on every page), `latest` pins both ends to the single latest season in the current filter scope (always shown when seasons have loaded — respects gender/team_type/tournament via the FilterBar's scoped seasons fetch), and `reset all` clears every filter (shown when anything is set). Teams landing and Players landing are NOT auto-defaulted — they stay all-time so defunct teams stay visible on Teams, and a player's single-player view opens at full career (the spec's "deep-dive, not leaderboard" policy).

**Players tab** (`/players`): person-focused overview. Three modes driven by the URL:
- `/players` → landing (curated profiles + popular comparisons).
- `/players?player=X` → single-player stack of Batting / Bowling / Fielding / Keeping bands, each with an identity line ("specialist batter · 388 matches" etc.) and a `→ Open <discipline> page` link. Bands hide when the player has no data for that discipline in scope.
- `/players?player=X&compare=Y[,Z]` → 2-way or 3-way comparison. Columns stay vertically aligned via per-discipline placeholders ("— no bowling in scope —") and switch to a compact label/value layout so narrow columns don't overflow. Cross-gender adds are refused in-place — the FilterBar's gender chip is the way to switch. Nav-wise, Players is the group parent for `/batting`, `/bowling`, `/fielding` — desktop hover-dropdown + mobile sub-row. The three discipline URLs are unchanged; only their nav presentation moves under Players.

**Teams → Compare tab** (`/teams?team=X&tab=Compare[&compare=Y[,Z]]`): parallel to Players compare. Side-by-side column grid of up to 3 teams across **Results / Batting / Bowling / Fielding / Partnerships** rows, compact label/value layout, FlagBadge on each column (null-renders for franchise sides). Backed by a frontend composer `getTeamProfile(team, filters)` (`api.ts`) that parallel-fetches five endpoints: `team_summary`, `team_batting/summary`, `team_bowling/summary`, `team_fielding/summary`, and a new `team_partnerships/summary` (aggregate counts + highest single partnership + top pair). Cross-gender / cross-team_type adds are prevented upstream by the FilterBar auto-narrow (locks gender + team_type from the primary); the picker additionally rejects any candidate whose in-scope match count is zero. A self-correcting effect in `Teams.tsx` auto-switches `tab` to `Compare` with `{replace:true}` when a share URL arrives carrying `compare=` but no `tab=`, so share links work without the sender needing to copy the tab param too. See `internal_docs/design-decisions.md` "Team Compare" entry for the cross-type gating rationale (and a pre-existing `fielding/summary.matches` bug this surfaced).

**Series landing** (`/series`, was `/tournaments`): `GET /api/v1/series/landing` returns sectioned payload — ICC events, bilateral rivalry tiles (split men's / women's, bilateral-only counts), other international, and club buckets (franchise / domestic / women_franchise / other). Tournament tiles → `?tournament=X` dossier. Bilateral rivalry tiles → `?filter_team=A&filter_opponent=B&series_type=bilateral_only` (the same dossier UI scoped to a team pair). Dossier endpoints (`/api/v1/series/{summary,by-season,records,batters-leaders,bowlers-leaders,fielders-leaders,partnerships/*}`) all accept optional `tournament` and `series_type` (`all` / `bilateral_only` / `tournament_only`) — when both filter_team + filter_opponent are set, summary returns `by_team` per-team breakdowns alongside the unified rollup. The nav label is "Series" because cricket uses that term for both bilateral series (Ind vs Aus tour) and tournament-seasons (IPL 2024); `/tournaments` URLs redirect to `/series` so old links still work. The `tournament` query param is unchanged — that's the FilterBar's event_name selector, which is what the `/series/` prefix exists to disambiguate from.

**Head-to-Head** (`/head-to-head`): polymorphic via `?mode=team`. Player-vs-player (`mode=player`, default) is the original batter-vs-bowler view. Team-vs-team (`mode=team&team1=A&team2=B`) reuses `TournamentDossier` to show every meeting between two teams — bilateral series + tournament matches — with a Show pill toggling between `all` / `bilateral_only` / `tournament_only`. Common matchups (top-9 men's + women's) shown as suggestion tiles when no teams selected. Teams > vs Opponent has a "See full rivalry →" link to this view. Canonical home for any two-entity matchup analysis.

**Venues tab** (`/venues`): Phase 2 landing only — country-grouped tile directory. Top 3 countries open by default, the rest collapsed (80+ total). Tile click sets `filter_venue=X` and navigates to `/matches?filter_venue=X`. FilterBar gains a **Venue** typeahead slot (mirrors TeamSearch — `components/VenueSearch.tsx`, 250ms debounce, cancel-on-unmount, scoped to current filters). When `filter_venue` is set the input becomes a chip with a dedicated "× Clear venue" button visible on every tab. Phase 3 (per-venue dossier) is opt-in after use reveals it's needed.

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
- **Added a user-visible feature the browser-agent can exercise?** Write or extend the matching **`tests/integration/<feature>.sh`** script. See **`tests/integration/README.md`** for the helper set and when-to-run rules.
- **Introduced a new perf pattern worth reusing?** Add it to **`internal_docs/perf-leaderboards.md`** (or create a sibling `perf-*.md` if scope is different).
- **Changed the page structure, tabs, or search-bar landing?** Update the "Landing pages" and "Key Files" sections of `CLAUDE.md` itself.
- **Changed anything user-visible about the home page, filter bar, or global conventions?** Update the relevant narrative doc and this file's convention list.

If the change is genuinely trivial (typo, whitespace, one-line comment), skip. Otherwise default to updating — undocumented features decay fastest.

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
- **`filter_venue` is an ambient filter** (Phase 2 of Venues, 2026-04-17). Added to `FilterParams` + both hand-rolled pickers (`reference.py::list_teams`, `tournaments.py::_build_filter_clauses`) so every tab respects it. Every page's `filterDeps` array had to be updated by hand — adding a new filter to the FilterBar is a multi-file fan-out today; see `internal_docs/design-decisions.md` "filterDeps arrays — explicit, per-page, easy to under-wire (revisit)" for the landmine and the proposed `Object.values(filters)` refactor when this bites again. Backend SQL clause is `m.venue = :filter_venue` (exact canonical match — the FilterBar typeahead returns canonical names so users don't need to know them).

## Known Issues / Live TODO

- **`wicket.fielders` is double-JSON-encoded in the DB.** `import_data.py` calls `json.dumps(w_data.get("fielders"))`, but deebase's JSON column type also serializes, so the stored string is e.g. `'"[{\"name\": \"SL Malinga\"}]"'` — a JSON string whose contents are themselves a JSON-encoded list. The matches scorecard router (`api/routers/matches.py:_build_dismissal_text`) works around this with `json.loads` twice. Fix: drop the `json.dumps(...)` wrapper in `import_data.py`, rebuild the DB, remove the double-decode branch. Tracked as enhancement C.
- Bowling scatter chart (vs Batters) — enhancement D was partial; see roadmap.
- Player search returns abbreviated cricsheet names ("V Kohli" not "Virat Kohli"). Tracked as enhancement E.1.
- Inter-wicket analysis is Python-side processing (~200ms for top players) — could be slow under load. Consider moving to SQL or caching.
- Consider adding compound indexes on `(delivery.bowler_id, delivery.innings_id)` for bowling queries, and `(partnership.innings_id, partnership.wicket_number)` (already has both separately).
- Admin at `/admin/` is behind HTTP Basic Auth (`ADMIN_USERNAME` + `ADMIN_PASSWORD` from `.env`). Fail-closed: missing env → 503. See `internal_docs/admin-interface.md`.

## Future Enhancements

Full A–O roadmap lives in **`internal_docs/enhancements-roadmap.md`** with done-items as historical markers.

**Shipped 2026-04-17 / 2026-04-18 (this session):**

- **llms.txt** at `/llms.txt` pointing to api.md, Swagger, OpenAPI JSON, user-help — lets an LLM interact with the public API without scraping.
- **Teams landing cross-gender link bug fix**: clicking a gendered tile now atomically sets both `team` and `gender` in the URL (was dropping gender via a raw `history.replaceState` race). Same architectural fix rippled into a codebase-wide **"derive don't mirror" refactor** on every search input — PlayerSearch, TeamSearch, Teams.tsx, Matches.tsx — replacing `useState(urlParam || '')` mirrors with a typing-buffer pattern (`internal_docs/url-state.md` "Search inputs" section).
- **Teams landing gender labeling**: "Franchise leagues" → "Men's franchise leagues"; Domestic section splits Men's / Women's; "Other tournaments" → "Other men's tournaments" / "Other women's tournaments". Per-tile gender badges already present; now section headers also disambiguate.
- **Teams → Compare tab (T)**: up to 3 teams side-by-side across Results / Batting / Bowling / Fielding / Partnerships rows. Mirrors Players compare architecturally. New endpoint `/api/v1/teams/{team}/partnerships/summary` for aggregate counts + highest + top pair. Cross-gender / cross-type blocked via FilterBar auto-narrow + scope-match probe in the picker.
- **Pre-existing fielding/summary filter bug fixed**: the matches-count sub-query wasn't applying `FilterParams`, so `catches_per_match` etc. had a diluted denominator. Surfaced by Compare, fixed in the same batch.
- **Venues Phase 1 (S)** — DB canonicalization + insert hooks. 676 raw `(venue, city)` cricsheet pairs collapse to 456 canonical venues across 88 countries via `api/venue_aliases.py::resolve_or_raw()`. New column `match.venue_country` TEXT NULL. Full worklist round-trip via `scripts/generate_venue_worklist.py` → human-reviewed CSV at `docs/venue-worklist/2026-04-17-worklist.csv` → regenerated alias module. Idempotent retrofit via `scripts/fix_venue_names.py` (can be re-run whenever the alias dict grows). `import_data.py` + `update_recent.py` canonicalize on insert; unknown venues soft-fail to raw pass-through and log to `docs/venue-worklist/unknowns-<date>.csv`.
- **Venues Phase 2 (S)** — FilterBar `filter_venue` param, `/api/v1/venues` typeahead endpoint, `/api/v1/venues/landing` country-grouped directory, `/venues` route, 8th top-level nav slot between Players ▾ and Head to Head. FilterBar gets a typeahead Venue search (mirrors TeamSearch — `components/VenueSearch.tsx`) that flips to a chip + "× Clear venue" button when a venue is active. Every tab (Teams / Players / H2H / Series / Matches / Batting / Bowling / Fielding / Keeping) respects the filter: 68 endpoints via `FilterParams.build()`; `reference.py::list_teams` + `tournaments.py::_build_filter_clauses` (13 Series endpoints) got 3-line additions for the venue clause. Regression harness: 18/18 REG byte-identical, 9/9 NEW queries differ. Also fixed a fan-out landmine: every page's `filterDeps` array + 5 carry functions hand-patched to include `filters.filter_venue` so SPA navigation triggers refetches (not just reloads). Option B (auto-derive filterDeps from `Object.values(filters)`) captured as follow-up in `internal_docs/design-decisions.md`.
- **Venue punctuation-collision sweep** — new permanent tool `scripts/sweep_venue_punctuation_collisions.py`. Slugifies each canonical venue (strip non-alphanumeric, lowercase, strip city suffix) + groups by `(slug, country)` to catch canonical-vs-canonical collisions that differ only by punctuation. Five caught on 2026-04-17: `M.Chinnaswamy → M Chinnaswamy Stadium, Bengaluru` (+17 matches), `ACA VDCA → ACA-VDCA` (+24), `Casey Fields No. 4 → No 4, Melbourne` (+6), `Gahanga … period → …, comma` (+77), `Grand Prairie Stadium, Dallas → Grand Prairie Stadium / Grand Prairie` (+41). 175 rows retrofitted; idempotent on re-run. Run this after every big incremental import (rare — new stadiums are uncommon).
- **tests/ folder restructured** — `integration_tests/` → `tests/integration/` (history preserved via git mv), new sibling `tests/regression/` with a generalised runner at `tests/regression/run.sh` that takes a feature name and runs the HEAD-vs-patched md5-diff cycle previously described only in `internal_docs/regression-testing-api.md` with ad-hoc `/tmp` scripts. Phase-2 inventory checked in at `tests/regression/venues/urls.txt`; matching browser-level suite at `tests/integration/venues.sh` (25/25 asserts pass). Runner uses `mkdir -p` in `capture()` so its output dir is owned by the function. Integration assertions use base64-wrapped `document.body.innerText.toLowerCase()` to sidestep shell-quoting + accessibility-tree gaps + CSS text-transform gotchas.
- **Tests backfill — every tab (2026-04-18).** Every top-level route now has a `tests/regression/<tab>/urls.txt` (all-REG endpoint inventory, 181 new URLs on top of the existing 28 venues URLs, across teams / batting / bowling / fielding / series / head_to_head / matches / players — 209 total) plus a `tests/integration/<tab>.sh` happy-path. Cross-cutting integration tests were reorganised: page-specific URL-state assertions moved from the old `back_button_history.sh` into the relevant per-tab scripts (e.g. `/matches` filter push → `matches.sh`; `/batting` gender auto-fill + default season window + tab switches → `batting.sh`; `/fielding` filter_team auto-narrow → `fielding.sh`; `/series` series_type reset + `/tournaments` redirect + `rivalry=` migration → `series.sh`); the file itself was renamed `cross_cutting_url_state.sh` and kept only ScopeIndicator + PlayerLink (true cross-tab widgets). `mount_unmount.sh` was renamed `cross_cutting_mount_unmount.sh`. `players_tab.sh` was renamed `players.sh` to match the per-tab convention. End-to-end run on 2026-04-18: **180 / 180 asserts pass across 12 scripts** (one selector miss on `matches.sh` Test 1 — `/matches` date cells aren't links, row-click navigates instead — fixed by targeting `tr.is-clickable`). `tests/README.md` + both subdir READMEs describe the new layout.
- **Linking + navigation audit (2026-04-18).** Page-by-page walk of every top-level route against the "match-list date convention", "two-link name + context pattern", and "links up / dead ends" rules in this file. 21 findings, 7 high-severity (scorecard dead-end; plain-text `player_of_match`; plain-`<span>` bowler/batter names in `vs Bowlers` / `vs Batters` / `Victims` matchup tables; broken `h2h` link in fielding Victims that hard-codes `&bowler=`; HeadToHead suggestion tiles aren't styled as links). Full findings + recommended fix order live in `internal_docs/audit-2026-04-18-links-and-navigation.md`. No code changes this session — the doc seeds the next one.

**NEXT SESSION agenda (in order):**

1. **Act on the 2026-04-18 audit.** Full inventory in `internal_docs/audit-2026-04-18-links-and-navigation.md`. Recommended order: (a) scorecard orientation — breadcrumb + `player_of_match` link; (b) matchup-table refactor — bowler_name / batter_name plain-span fix across Batting `vs Bowlers`, Bowling `vs Batters`, Fielding `Victims` (also fixes the broken h2h link in Victims); (c) HeadToHead suggestion-tile styling; (d) venue-cell sweep where `filter_venue` should be the link; (e) match-list date alignment on `/matches` + Home fixtures; (f) Series Records + Partnerships link-up; (g) scorecard did-not-bat / fall-of-wickets / dismissal-text — needs a companion backend change to surface person IDs. Not every item needs shipping — triage with the user before starting.
2. **filterDeps refactor (Option B)** — derive per-page deps from `Object.values(filters)` so new filters auto-wire. See `internal_docs/design-decisions.md` "filterDeps arrays — explicit, per-page, easy to under-wire (revisit)".
3. **Venues Phase 3** — per-venue dossier at `/venues?venue=X`. Tabs: Overview (avg 1st-inn total, bat-first win %, toss-decision pie, boundary % by phase, highest/lowest totals, matches-hosted-by-tournament×gender×season) + Batters/Bowlers/Fielders leaders + Matches + Records. One new endpoint needed (`GET /api/v1/venues/{venue}/summary`) — all other dossier tabs reuse existing `/api/v1/{batters,bowlers,fielders}/leaders?filter_venue=X` and `/api/v1/matches?filter_venue=X` for free. See spec `internal_docs/spec-venues.md`.

**Later (deferred out of the immediate queue):**

- **More filters on `/matches`** — `filter_venue` already lands from Phase 2. Also consider result filter (won/lost/tied/NR from a team perspective), close-match filter, super-over filter, toss-outcome filter. Confirm scope with user before building.
- **O — Tournament-baseline comparison overlays** on team / batter / bowler / fielder pages. M shipped the per-tournament endpoints with explicit baseline reusability — call any `/api/v1/series/{summary,batters-leaders,…}` without a team filter to get the tournament-wide baseline, with one for the team's narrowed view (responses are shape-compatible). Frontend wiring needed: overlay league means on team-tab charts, add "vs league avg" columns to player tables, support "delta from league mean" colour mode on heatmaps. Design sketch in `internal_docs/design-decisions.md` "Team metrics need tournament baselines (revisit when /tournaments ships)".

**Other "(revisit)" items** (see `internal_docs/design-decisions.md` for detail): win-% overlay on discipline tabs (correlates performance with winning), batter consistency stats (median / 30+ rate / dispersion), batter × bowler-type splits + bowler × batter-handedness splits (requires person-table enrichment from Cricinfo).
