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
- **Frontend:** React 19 + TypeScript + Tailwind CSS v4 + Semiotic v3 charts
- **Build:** Vite 8 (see `docs/frontend-build-pipeline.md`)
- **Deploy:** pla.sh (see deploy section below)

## Key Files — entry points

Full file-by-file tour lives in **`docs/codebase-tour.md`**. The
recurring entry points:

- `api/app.py` — FastAPI app, CORS, admin, SPA fallback (registered in lifespan AFTER routers)
- `api/routers/` — one file per subdomain (teams, batting, bowling, fielding, keeping, matches, head_to_head, reference)
- `api/filters.py` — `FilterParams` class (Depends), builds WHERE clauses with `:param` bind syntax
- `models/tables.py` — all deebase tables (Person, Match, Innings, Delivery, Wicket, FieldingCredit, KeeperAssignment, Partnership)
- `scripts/populate_*.py` — denormalized-table builders; all auto-called by `import_data.py` + `update_recent.py`
- `frontend/src/pages/` — one file per top-level route (Home, Teams, Batting, Bowling, Fielding, HeadToHead, Matches, MatchScorecard, Help, HelpUsage)
- `frontend/src/content/` — `about-me.md` and `user-help.md` — editable markdown rendered on the `/help` and `/help/usage` routes via `react-markdown`. Edit the `.md`, rebuild, ship.
- `frontend/src/api.ts` + `types.ts` — endpoint clients + response types
- `frontend/src/components/charts/` — Semiotic wrappers (BarChart, LineChart, ScatterChart, HeatmapChart, BubbleMatrix, WormChart, etc.)
- `frontend/src/index.css` — Wisden editorial styles (see `docs/visual-identity.md`)

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

See `docs/local-development.md` for prerequisites, the project-layout cheat sheet, type-check / build commands, troubleshooting, and how to query the DB from a Python REPL.

## Deploying

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

See `docs/deploying.md` for what does/doesn't ship, the deebase vendoring quirk, the `.plash` identity file, and troubleshooting.

## Rebuilding / Updating the Database

Full pipeline + dry-run format documented in **`docs/data-pipeline.md`**. Canonical commands:

```bash
uv run python download_data.py                      # fetches zips + people/names CSVs
uv run python import_data.py                        # full rebuild (~15 min, drops cricket.db)
uv run python update_recent.py --dry-run --days 30  # check what's new
uv run python update_recent.py --days 30            # incremental import
```

Both `import_data.py` and `update_recent.py` auto-populate `fielding_credit`, `keeper_assignment`, and `partnership`. After a DB update, push to plash with `bash deploy.sh --first` (plain `deploy.sh` skips the DB upload).

To smoke-test `update_recent.py` against a copy of the prod DB before deploying, use `--db /tmp/cricket-prod-test.db` after copying the Downloads snapshot — see **`docs/testing-update-recent.md`** for the copy-to-tmp workflow and what not to do.

## Landing pages (search-bar tabs)

Every search-bar tab — `/teams`, `/batting`, `/bowling`, `/fielding` — has a filter-sensitive landing component shown when nothing is selected. Each is backed by a single endpoint:

- **Teams:** `GET /api/v1/teams/landing` — `{international: {regular, associate}, club: [{tournament, teams}]}`. Uses a hardcoded `ICC_FULL_MEMBERS` list in `api/routers/teams.py` for regular/associate split. Club teams grouped by tournament, ordered by match count desc.
- **Batting:** `GET /api/v1/batters/leaders` — `{by_average, by_strike_rate}` top-10. Thresholds `min_balls=100` and `min_dismissals=3` (averages only) exclude tiny-sample winners.
- **Bowling:** `GET /api/v1/bowlers/leaders` — `{by_strike_rate, by_economy}` top-10. Thresholds `min_balls=60` (10 overs), `min_wickets=3` (SR list only).
- **Fielding:** `GET /api/v1/fielders/leaders` — `{by_dismissals, by_keeper_dismissals}` top-10. Volume-based (no thresholds — rank IS the filter). Keeper column uses `keeper_assignment` to count only catches/stumpings taken while the fielder was the designated keeper.

All four are filter-sensitive (gender, team_type, tournament, season_from/to) and all landing-row links carry the current filter scope through to the selected-entity page via `URLSearchParams`.

Batting/Bowling/Fielding landings additionally default `season_from`/`season_to` to the last 3 seasons in scope via `hooks/useDefaultSeasonWindow` — one-shot per mount, writes to URL so FilterBar reflects it. FilterBar has three inline text buttons: `all-time` clears the season range (always visible, for consistency as a time reset on every page), `latest` pins both ends to the single latest season in the current filter scope (always shown when seasons have loaded — respects gender/team_type/tournament via the FilterBar's scoped seasons fetch), and `reset all` clears every filter (shown when anything is set). Teams landing is NOT auto-defaulted — it stays all-time so defunct teams remain visible.

## API reference

For every endpoint — path, query params, example curl, and an abbreviated response — see **`docs/api.md`**. It's the quick-reference companion to `SPEC.md` (which has the underlying SQL + full schemas).

FastAPI also exposes auto-generated interactive docs at **`/api/docs`** (Swagger UI) and **`/api/redoc`** (ReDoc) on both local and prod — the `/api/*` prefix (not the FastAPI default `/docs`) so the Vite dev-server proxy forwards correctly. The help page (`/help`) links to both.

## Keeping docs in sync

**Every feature or substantive change must end with a docs pass.** Before calling a change done (and certainly before committing), scan the doc set and update whatever the change affects. Specifically:

- **Added / changed / removed an API route?** Update **`docs/api.md`** — add or amend the endpoint section (path, one-liner, curl, abbreviated JSON response). Hit the endpoint via `curl` to capture a real response rather than inventing one.
- **Changed a URL scheme, filter param, or response shape on an existing endpoint?** Same — update the affected `docs/api.md` section. Re-curl the example if the shape changed.
- **Added a new router file, a new page, or a new hook?** Update **`docs/codebase-tour.md`** (both the router summary line and the frontend hooks block).
- **Shipped a feature that belongs in the A-O narrative?** Add or amend the entry in **`docs/enhancements-roadmap.md`**; done items stay there as historical markers.
- **Made a non-obvious design decision** (a convention future contributors would otherwise try to change)? Add a bullet to **`docs/design-decisions.md`**.
- **Changed pipeline behaviour, introduced a new invariant the DB must carry, or added a testing workflow?** Touch **`docs/data-pipeline.md`** (and/or `docs/testing-update-recent.md`).
- **Introduced a new perf pattern worth reusing?** Add it to **`docs/perf-leaderboards.md`** (or create a sibling `perf-*.md` if scope is different).
- **Changed the page structure, tabs, or search-bar landing?** Update the "Landing pages" and "Key Files" sections of `CLAUDE.md` itself.
- **Changed anything user-visible about the home page, filter bar, or global conventions?** Update the relevant narrative doc and this file's convention list.

If the change is genuinely trivial (typo, whitespace, one-line comment), skip. Otherwise default to updating — undocumented features decay fastest.

## Performance notes

- **Leaderboard landings** (Batting / Bowling / Fielding) depend on two composite covering indexes (`ix_delivery_batter_agg`, `ix_delivery_bowler_agg`) plus fresh `ANALYZE` stats. These are created idempotently by both `import_data.py` and `update_recent.py`. See **`docs/perf-leaderboards.md`** for the diagnosis and the reusable pattern: use `filters.build(has_innings_join=False)` to get a pure match clause, then conditionally drop the innings/match JOINs entirely when no filters are active (avoids 2.95M × 2 PK probes on the delivery scan).

## Critical Design Decisions

Read `docs/design-decisions.md` for full details. Key points:

- **Over numbering:** DB stores 0-19 (matching cricsheet source). API returns 1-20 (+1 in each router's response). Frontend displays as-is.
- **Phase boundaries:** Powerplay = overs 1-6, Middle = 7-15, Death = 16-20 (in API responses). SQL internally uses 0-5, 6-14, 15-19.
- **Legal balls vs all deliveries:** Batting stats count only legal balls (no wides/noballs). Bowling runs_conceded counts ALL deliveries.
- **Bowler wickets:** Exclude run out, retired hurt, retired out, obstructing the field.
- **Run rate:** Concatenated rate (SUM(runs) × 6 / SUM(legal balls)), NOT mean of per-innings rates. See design-decisions.md "Run rate: concatenated, not per-innings averaged (revisit)" for the why and when-to-revisit.
- **URL state:** All page state (player, tab, filters) lives in URL search params for deep linking. Use `useSetUrlParams()` for atomic multi-param updates (two separate `useUrlParam` setters race).
- **deebase `db.q()`:** Locally patched to accept `params` dict. Use `:param_name` bind syntax, never f-string interpolation. Exception: list params (`WHERE id IN (...)`) need f-string interpolation — SQLite bind params don't expand lists.
- **SPA fallback:** Must be registered AFTER API routers in the lifespan handler (not at import time) or it catches /api/* routes.
- **Bowling field names differ from batting:** `wickets` not `dismissals`, `runs_conceded` not `runs`. Don't reuse batting types.
- **Scorecard highlight auto-scroll:** The innings-list date links on Batting/Bowling/Fielding pages carry `?highlight_batter=`, `?highlight_bowler=`, or `?highlight_fielder=` (person ID). The scorecard page tints the matching row(s) green (`.is-highlighted`) and scrolls to the first one. Scroll logic is **page-level** in `MatchScorecard.tsx`, gated on both `useFetch` calls resolving, then does `document.querySelector('.is-highlighted')` inside a double `requestAnimationFrame` so layout has settled. Per-InningsCard scrolling was abandoned because sibling async sections (WormChart, MatchupGridChart, InningsGridChart) resized after the scroll fired, displacing the target.
- **Match-list date convention:** ANY table that lists matches (Teams > Match List, Teams > vs Opponent match list, Batting/Bowling/Fielding "Innings List", Matches page results, Partnerships "Top N" date column, etc.) MUST render the `date` cell as a `<Link to={`/matches/${match_id}`}>` with className `comp-link`. Row-click to scorecard is fine as a secondary affordance, but the date link itself is mandatory — users rely on cmd/ctrl-click to open the scorecard in a new tab. When the table is in a player's innings-list context, the link must also carry the appropriate highlight param (`highlight_batter` / `highlight_bowler` / `highlight_fielder` = that person_id) so the scorecard tints + scrolls to their row.
- **Fielder dismissal attribution:** The scorecard API joins `fieldingcredit` per innings and returns `dismissal_fielder_ids: string[]` on each batting row. The frontend uses this to match `highlight_fielder` rather than parsing the dismissal text string.
- **Keeper identification (Tier 2):** Cricsheet has no keeper designation, so we infer it via a 4-layer algorithm (stumping this innings → exactly-1 season-candidate in XI → exactly-1 career-N≥3 keeper in XI → exactly-1 team-ever-keeper in XI). Stored in `keeper_assignment` with nullable `keeper_id` + explicit `confidence` enum. When 2+ candidates match at any layer, the row stays NULL with `ambiguous_reason` + `candidate_ids_json`, and the innings is exported to `docs/keeper-ambiguous/<YYYY-MM-DD>.csv` for later manual/Cricinfo resolution. Manual resolutions (same CSV, `resolved_keeper_id` column) always win — applied last in `populate_full` / `populate_incremental`. See `docs/spec-fielding-tier2.md`.
- **Team-stats FilterBar auto-narrowing (enhancement N):** When a team is selected, `/api/v1/tournaments?team=X` + `/api/v1/seasons?team=X&tournament=Y&...` return only the team's actual context. FilterBar auto-sets team_type/gender when unambiguous (e.g. MI → club). See `docs/spec-team-stats.md`.

## Known Issues / Live TODO

- **`wicket.fielders` is double-JSON-encoded in the DB.** `import_data.py` calls `json.dumps(w_data.get("fielders"))`, but deebase's JSON column type also serializes, so the stored string is e.g. `'"[{\"name\": \"SL Malinga\"}]"'` — a JSON string whose contents are themselves a JSON-encoded list. The matches scorecard router (`api/routers/matches.py:_build_dismissal_text`) works around this with `json.loads` twice. Fix: drop the `json.dumps(...)` wrapper in `import_data.py`, rebuild the DB, remove the double-decode branch. Tracked as enhancement C.
- Bowling scatter chart (vs Batters) — enhancement D was partial; see roadmap.
- Player search returns abbreviated cricsheet names ("V Kohli" not "Virat Kohli"). Tracked as enhancement E.1.
- Inter-wicket analysis is Python-side processing (~200ms for top players) — could be slow under load. Consider moving to SQL or caching.
- Consider adding compound indexes on `(delivery.bowler_id, delivery.innings_id)` for bowling queries, and `(partnership.innings_id, partnership.wicket_number)` (already has both separately).
- Admin at `/admin/` is behind HTTP Basic Auth (`ADMIN_USERNAME` + `ADMIN_PASSWORD` from `.env`). Fail-closed: missing env → 503. See `docs/admin-interface.md`.

## Future Enhancements

Full A–O roadmap lives in **`docs/enhancements-roadmap.md`** with done-items as historical markers.

**Next up: M — Tournament analytics page.** Two route levels (listing → per-tournament), season as FilterBar param not path (matches Teams). Spec needs writing; partial design in `docs/spec-team-stats.md` "Implication for tournaments". Design questions + placement debate for the adjacent "team-to-team rollup" work captured in **`docs/next-session-ideas.md`** — open question there is whether `/head-to-head` should go polymorphic (player-v-player + team-v-team) or stay player-only.

**After M: O — Tournament-baseline comparison overlays** on team / batter / bowler / fielder pages. Depends on M's per-tournament-per-season aggregates. Design sketched in `docs/design-decisions.md` "Team metrics need tournament baselines (revisit when /tournaments ships)".

**Other "(revisit)" items** (see `docs/design-decisions.md` for detail): win-% overlay on discipline tabs (correlates performance with winning), batter consistency stats (median / 30+ rate / dispersion), batter × bowler-type splits + bowler × batter-handedness splits (requires person-table enrichment from Cricinfo).
