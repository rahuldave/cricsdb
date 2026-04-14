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

## Key Files

```
api/
  app.py              — FastAPI app, CORS, admin, SPA fallback (registered in lifespan after routers)
  dependencies.py     — Database init (WAL mode, PLASH_PRODUCTION-aware path)
  filters.py          — FilterParams class (Depends), builds WHERE clauses with :param bind syntax
  routers/
    reference.py      — /api/v1/tournaments, /seasons, /teams, /players
    teams.py          — /api/v1/teams/{team}/summary|results|vs/{opponent}|by-season
    batting.py        — /api/v1/batters/{id}/summary|by-innings|vs-bowlers|by-over|by-phase|by-season|dismissals|inter-wicket
    bowling.py        — /api/v1/bowlers/{id}/summary|by-innings|vs-batters|by-over|by-phase|by-season|wickets
    fielding.py       — /api/v1/fielders/{id}/summary|by-season|by-phase|by-over|dismissal-types|victims|by-innings
    keeping.py        — /api/v1/fielders/{id}/keeping/summary|by-season|by-innings|ambiguous (Tier 2)
    head_to_head.py   — /api/v1/head-to-head/{batter_id}/{bowler_id}
    matches.py        — /api/v1/matches list, /matches/{id}/scorecard, /matches/{id}/innings-grid
models/tables.py      — deebase models: Person, Match, Innings, Delivery, Wicket, FieldingCredit, KeeperAssignment, etc.
team_aliases.py       — Canonical team-name mapping (used by import + fix script)
event_aliases.py      — Canonical tournament-name mapping (same pattern as team_aliases)
fielder_aliases.py    — Canonical fielder-name mapping (married names, disambiguated names)
scripts/fix_team_names.py  — One-time UPDATE pass to canonicalize old team names in cricket.db
scripts/fix_event_names.py — Same for tournament names (match.event_name)
scripts/populate_fielding_credits.py — Builds fielding_credit table (called automatically by import + update pipelines)
scripts/populate_keeper_assignments.py — Builds keeper_assignment table + writes ambiguous worklist partitions (auto on import + update)
scripts/apply_keeper_resolutions.py — Applies manual resolutions from docs/keeper-ambiguous/*.csv back into the DB
import_data.py        — Downloads cricsheet JSON + imports into SQLite (canonicalizes via team_aliases + event_aliases, populates fielding_credit)
frontend/src/
  App.tsx             — React Router: /, /teams, /batting, /bowling, /fielding, /head-to-head, /matches, /matches/:matchId
  hooks/useUrlState.ts — useUrlParam + useSetUrlParams (atomic URL state updates)
  hooks/useFetch.ts    — { data, loading, error, refetch } wrapper around an async fn
  hooks/useContainerWidth.ts — ResizeObserver wrapper used by responsive chart wrappers
  components/         — Layout, FilterBar, PlayerSearch, StatCard, DataTable, Spinner, ErrorBanner, Scorecard, InningsCard, charts/
    charts/           — BarChart, LineChart, ScatterChart, DonutChart wrappers (responsive),
                        WormChart, ManhattanChart, InningsGridChart, MatchupGridChart
  pages/              — Home, Teams, Batting, Bowling, Fielding, HeadToHead, Matches, MatchScorecard
deploy.sh             — Stages build_plash/ dir and runs plash_deploy
SPEC.md               — Full specification with all API schemas and SQL queries
docs/                 — frontend-build-pipeline.md, design-decisions.md
```

## Running Locally

```bash
# Terminal 1 — backend
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

**UI verification (any frontend work must go through this):** After any
change to files under `frontend/src/`, you MUST use the `agent-browser`
skill to load the affected page(s) in a real browser, exercise every
new tab/component, apply the relevant FilterBar combinations (incl.
single-season), hover interactive elements (tooltips, heatmap cells),
and click every link to confirm it navigates. `tsc --noEmit` and
`npm run build` only verify code correctness, not feature correctness.
Do not claim UI work is complete without a browser-agent run.

Open http://localhost:5173. Vite proxies `/api/*` → port 8000.

See `docs/local-development.md` for prerequisites, the project-layout cheat sheet, type-check / build commands, troubleshooting, and how to query the DB from a Python REPL.

## Deploying

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

See `docs/deploying.md` for what does/doesn't ship, the deebase vendoring quirk, the `.plash` identity file, and troubleshooting.

## Rebuilding / Updating the Database

See `docs/data-pipeline.md` for the full pipeline and dry-run output format.

```bash
# Full rebuild (~15 min):
uv run python download_data.py        # fetches zips + people/names CSVs
uv run python import_data.py          # drops cricket.db and reimports + populates fielding_credit

# Incremental update (just new T20 matches):
uv run python update_recent.py --dry-run --days 7   # check status
uv run python update_recent.py --days 7              # import + incremental fielding_credit

# One-time: populate fielding_credit on an existing DB that doesn't have it yet:
uv run python scripts/populate_fielding_credits.py
```

Both `import_data.py` (full rebuild) and `update_recent.py` (incremental)
automatically populate the `fielding_credit` table — no separate step needed.
The full rebuild truncates and repopulates all ~118K rows; incremental adds
credits only for newly imported matches.

`update_recent.py --dry-run` reports today's date, latest match in DB,
latest in cricsheet's bundle, plus `Last-Modified` for `people.csv` and
`names.csv`, so you can tell whether *you* are behind or whether
*cricsheet* hasn't published yet.

After a DB update, push it to plash with `bash deploy.sh --first`
(plain `deploy.sh` skips the DB upload).

## Critical Design Decisions

Read `docs/design-decisions.md` for full details. Key points:

- **Over numbering:** DB stores 0-19 (matching cricsheet source). API returns 1-20 (+1 in each router's response). Frontend displays as-is.
- **Phase boundaries:** Powerplay = overs 1-6, Middle = 7-15, Death = 16-20 (in API responses). SQL internally uses 0-5, 6-14, 15-19.
- **Legal balls vs all deliveries:** Batting stats count only legal balls (no wides/noballs). Bowling runs_conceded counts ALL deliveries.
- **Bowler wickets:** Exclude run out, retired hurt, retired out, obstructing the field.
- **URL state:** All page state (player, tab, filters) lives in URL search params for deep linking. Use `useSetUrlParams()` for atomic multi-param updates (two separate `useUrlParam` setters race).
- **deebase `db.q()`:** Locally patched to accept `params` dict. Use `:param_name` bind syntax, never f-string interpolation.
- **SPA fallback:** Must be registered AFTER API routers in the lifespan handler (not at import time) or it catches /api/* routes.
- **Bowling field names differ from batting:** `wickets` not `dismissals`, `runs_conceded` not `runs`. Don't reuse batting types.
- **Scorecard highlight auto-scroll:** The innings-list date links on Batting/Bowling/Fielding pages carry `?highlight_batter=`, `?highlight_bowler=`, or `?highlight_fielder=` (person ID). The scorecard page tints the matching row(s) green (`.is-highlighted`) and scrolls to the first one. Scroll logic is **page-level** in `MatchScorecard.tsx`, gated on both `useFetch` calls resolving, then does `document.querySelector('.is-highlighted')` inside a double `requestAnimationFrame` so layout has settled. Per-InningsCard scrolling was abandoned because sibling async sections (WormChart, MatchupGridChart, InningsGridChart) resized after the scroll fired, displacing the target.
- **Match-list date convention:** ANY table that lists matches (Teams > Match List, Teams > vs Opponent match list, Batting/Bowling/Fielding "Innings List", Matches page results, Partnerships "Top N" date column, etc.) MUST render the `date` cell as a `<Link to={`/matches/${match_id}`}>` with className `comp-link`. Row-click to scorecard is fine as a secondary affordance, but the date link itself is mandatory — users rely on cmd/ctrl-click to open the scorecard in a new tab. When the table is in a player's innings-list context, the link must also carry the appropriate highlight param (`highlight_batter` / `highlight_bowler` / `highlight_fielder` = that person_id) so the scorecard tints + scrolls to their row.
- **Fielder dismissal attribution:** The scorecard API joins `fieldingcredit` per innings and returns `dismissal_fielder_ids: string[]` on each batting row. The frontend uses this to match `highlight_fielder` rather than parsing the dismissal text string.
- **Keeper identification (Tier 2):** Cricsheet has no keeper designation, so we infer it via a 4-layer algorithm (stumping this innings → exactly-1 season-candidate in XI → exactly-1 career-N≥3 keeper in XI → exactly-1 team-ever-keeper in XI). Stored in `keeper_assignment` with nullable `keeper_id` + explicit `confidence` enum. When 2+ candidates match at any layer, the row stays NULL with `ambiguous_reason` + `candidate_ids_json`, and the innings is exported to `docs/keeper-ambiguous/<YYYY-MM-DD>.csv` for later manual/Cricinfo resolution. Manual resolutions (same CSV, `resolved_keeper_id` column) always win — applied last in `populate_full` / `populate_incremental`. See `docs/spec-fielding-tier2.md`.

## Known Issues / TODO

- Bowling scatter chart (vs Batters): Y-axis is "bowling strike rate" (balls/wicket) which is counterintuitive — high = bad but looks prominent. Consider flipping axis or using average instead.
- Semiotic bar charts with many seasons get crowded x-axis labels. May need rotation or responsive sizing.
- Player search matches cricsheet names (e.g., "V Kohli" not "Virat Kohli"). The personname table alternate name search works but users may not expect abbreviated names in results.
- No loading spinners — data fetches show nothing while in flight.
- No error states — failed API calls silently show empty content.
- The deebase admin at /admin/ is behind HTTP Basic Auth (username `ADMIN_USERNAME` + password `ADMIN_PASSWORD` from `.env`, loaded by `api/app.py` locally and by plash's `plash.env` source-step in production). Fail-closed: missing env → 503. See `docs/admin-interface.md` for the full doc (tables exposed, compat fixes, deploy.sh's export-prefix transform for plash's bash-source ENTRYPOINT).
- Inter-wicket analysis is Python-side processing (~200ms for top players) — could be slow under load.
- Consider adding indexes on `(delivery.bowler_id, delivery.innings_id)` compound index for bowling queries.
- **`wicket.fielders` is double-JSON-encoded in the DB.** The import path in `import_data.py` does `json.dumps(w_data.get("fielders"))`, but deebase's JSON column type also serializes the value, so the stored string is e.g. `'"[{\"name\": \"SL Malinga\"}]"'` — a JSON string whose contents are themselves a JSON-encoded list. The matches scorecard router (`api/routers/matches.py:_build_dismissal_text`) works around this by calling `json.loads` twice. To fix at the source: in `import_data.py` pass the raw list (`w_data.get("fielders")`) instead of `json.dumps(...)` and rebuild the DB. Other JSON-typed columns (`match.dates`, `match.officials`, `match.player_of_match`, `innings.powerplays`) store correctly already — only `wicket.fielders` has the double-encode bug because it's the only one wrapped in `json.dumps` before insert.

## Future Enhancements

The list below is roughly ordered by value/effort. Pick the highest one
that fits the available time.

**A. Loading + error states across all pages.** _Done._ See `docs/data-fetching.md` for the full pattern (useFetch hook, Spinner, ErrorBanner, gated fetches, per-tab `<TabState>` helper, when NOT to use useFetch, where loading/error sit relative to data). Rolled out to Home, Matches list, MatchScorecard, Teams, Batting, Bowling, Head to Head, PlayerSearch dropdown, FilterBar dropdowns.

**B. Mechanically-generated ball-by-ball commentary tab on the scorecard page.** Cricsheet does NOT ship natural-language commentary like Cricinfo's editorial feed — what we have is structured ball data. So this would render each delivery as a feed line: `19.6 — Bumrah to Kohli — 4 runs (FOUR)` or `19.4 — Bumrah to Sharma — OUT! caught Rohit b Bumrah`. Useful and conventional, but be honest with users that it's generated from data, not a writer's prose. Pairs naturally with the **innings grid** (see `docs/design-decisions.md` "Innings grid: per-delivery visualization") — clicking a row in the grid could scroll the commentary feed to the same ball, and vice versa.

**C. Fix `wicket.fielders` double-encoding at the source.** Currently `import_data.py` calls `json.dumps(w_data.get("fielders"))` redundantly — deebase's JSON column type also serializes, so the stored value is a JSON string of a JSON string. The matches scorecard router parses twice as a workaround (`api/routers/matches.py:_build_dismissal_text`). Fix: drop the `json.dumps(...)` wrapper in `import_data.py`, rebuild the DB with `import_data.py`, then remove the double-decode branch. ~5-line code change + 15-min DB rebuild.

**D. Bowling-vs-Batters scatter Y axis is counterintuitive.** _Done._ Switched the Y metric from bowling strike rate (balls/wicket) to bowling average (runs/wicket), then flipped the Y axis via `frameProps.yExtent = [maxAvg * 1.05, 0]` so low values (good for bowler) sit at the TOP. The visually prominent top-left corner is now where the bowler dominated. `ScatterChart` wrapper gained a `frameProps` pass-through so any scatter can be axis-flipped.

**E. Identity ambiguity — players and teams.** Three related issues, all about the same thing: cricsheet uses one name string for entities that some users mentally model as separate, others as the same.

   1. **Player search returns abbreviated cricsheet names** ("V Kohli" not "Virat Kohli"). The `personname` table has alias variants — search ranking should prefer alias matches that include a longer/more familiar form when one exists. Backend change in `api/routers/reference.py` (`/api/v1/players`) plus a ranking heuristic.

   2. **Team names collide across genders.** ~110 team names appear in BOTH men's and women's matches: every international side (India, Australia, England, etc.), all IPL↔WPL franchises (Mumbai Indians, Delhi Capitals, RCB), all BBL↔WBBL franchises, all 8 Hundred men/women pairs, NZ domestic sides. With Gender filter = "All", a team page aggregates both squads — statistically meaningless ("Mumbai Indians: 315 matches" = 278 IPL men + 37 WPL women across two different leagues). _Partial fix shipped:_ when a URL has `?tournament=X` but no gender, FilterBar auto-fills gender + team_type from the tournament metadata so deep links like `/matches?tournament=IPL` self-correct (commit 8947f0c). _Still TODO:_ direct team search on `/teams` with no filters. Recommended: when team summary has matches in both genders AND no gender filter is active, show an italic-serif notice above the stat row with one-click "Show men only" / "Show women only" buttons. Backend: extend `getTeamSummary` to return `gender_breakdown: { male: N, female: M } | null`. Frontend: small banner in `Teams.tsx`.

   3. **Player names can also collide across people.** Two separate "V Kohli"s could exist in the personname table (e.g. an Indian batter and a women's batter with the same initials + surname). Player IDs disambiguate everywhere internally, but the SEARCH dropdown shows names without context. Same fix shape as #2: when multiple people share a search-result name, append a small distinguishing tag (gender, primary team, era) so the user can pick the right one.

**F. Multi-player intersection filter on `/matches`.** Currently single player only. Extend `player_id` to `player_ids` and `AND` the EXISTS clauses. UI needs a multi-pill input. Useful but niche.

**G. Worm chart wicket markers as actual chart points.** _Done._ Each wicket appears as a red dot on the worm line at the exact (fractional-over, score) coordinate. Hover shows the dismissed batter via the standard Semiotic tooltip. Strategy: combine over-end and wicket data points into one sorted-by-over data array tagged with `is_wicket: boolean`, then use Semiotic v3's `highlight` annotation type which filters chart data by `field=value` and draws circles on each match. The line draws through the wicket points naturally because cumulative runs are monotonic. `LineChart` wrapper updated to pass through `annotations` and `tooltip` props.

**I. Responsive chart sizing.** _Done._ `frontend/src/hooks/useContainerWidth.ts` wraps a `ResizeObserver`. `BarChart`, `LineChart`, and `ScatterChart` wrappers make `width` optional and use the hook to fill their container when omitted. `DonutChart` stays fixed-width (a circle doesn't usefully stretch). All chart call sites now omit `width`; the dual-chart layouts that used `flex gap-6 flex-wrap` were converted to `grid grid-cols-1 lg:grid-cols-2 gap-6` (or `grid-cols-[350px_minmax(0,1fr)]` for donut+bar layouts) so each chart cell has a definite container width. The previous mobile pass's `overflow-x-auto` workaround on chart cards was stripped.

**K. Tournament-name canonicalization.** _Done._ Implemented in `event_aliases.py` + `scripts/fix_event_names.py`, mirroring the team-aliases pattern. Three competitions merged: NatWest T20 Blast / Vitality Blast Men → Vitality Blast (English), MiWAY / Ram Slam → CSA T20 Challenge (SA), HRV Cup / HRV Twenty20 → Super Smash (NZ). 784 rows updated; club-tournament count went from 27 to 21. See `docs/design-decisions.md` "Team-name canonicalization across renames" for the shared writeup.

**J. Distinctive visual identity.** _Done._ Wisden editorial redesign shipped. Cream background, Fraunces display serif + Inter Tight sans, oxblood accent, rule-based layouts instead of card chrome. Full documentation in `docs/visual-identity.md`. Consistency rule: subject in ink, connective in oxblood, hover to oxblood.

**H. Reverse direction of the scatter↔table linking on Batting/Bowling vs-tabs.** The forward direction (click a row → highlight the matching dot on the chart with an `enclose` annotation, scroll the row into view) is shipped — see `docs/design-decisions.md` "Linking scatter charts to their data tables." The reverse direction (click a dot → highlight the row, scroll the table to it) is missing because Semiotic v3's high-level `Scatterplot` component does not expose `onClick` or any per-point click handler.

**L. Fielding analytics page.** _Tier 1 + Tier 2 done._ `/fielding` page with `fielding_credit` denormalized table (~118K rows), `fielder_aliases.py`, `wicket.fielders` double-encoding fix, 7 API endpoints (`api/routers/fielding.py`), frontend page with 6 tabs (By Season, By Over, By Phase, Dismissal Types, Victims, Innings List). Fielder search via `role=fielder` in `/api/v1/players`. Tier 1 spec: `docs/spec-fielding.md`.
   - **Tier 2** — wicketkeeper identification via 4-layer algorithm (stumping → season-candidate → career N≥3 → team-ever-keeper). `keeper_assignment` table (one row per regular innings, 25,846 rows) with `keeper_id` (nullable), `confidence` enum (`definitive/high/medium/low/NULL`), `method` tag, and `ambiguous_reason` + `candidate_ids_json` for the NULL rows. **Coverage**: 82.2% assigned (18.2% definitive, 43.2% high, 17.4% medium, 3.4% low), 17.8% NULL. Ambiguous rows exported to date-partitioned CSVs under `docs/keeper-ambiguous/<YYYY-MM-DD>.csv` (Hive-style; each innings_id appears in exactly one partition). Manual resolutions via `resolved_keeper_id` column + `scripts/apply_keeper_resolutions.py` — auto-applied at the end of every populate run so corrections survive rebuilds. New `api/routers/keeping.py` (4 endpoints) and Keeping sub-tab on `/fielding` with stumpings, keeping catches, byes conceded, confidence transparency. Scorecard shows per-innings keeper label (ambiguous rows render `"ambiguous — X or Y"` with both candidates clickable). Team pages show "Keepers used: X (N), Y (M)" rollup. Both `import_data.py` and `update_recent.py` auto-populate. Spec: `docs/spec-fielding-tier2.md`, worklist README: `docs/keeper-ambiguous/README.md`.

**M. Tournament analytics page.** New `/tournaments` page with **two** route levels (decision made during the team-stats build — flatten season into a filter rather than a separate route, mirroring how Teams works): tournament listing → per-tournament overview that scopes by season via FilterBar. Spec needs writing; first feasibility cuts informed by the team-stats build are captured in `docs/spec-team-stats.md`'s "Implication for tournaments" callout. Tied to **enhancement O (baselines)** — the per-tournament-per-season aggregates we compute here are exactly what the team tabs need for tournament-mean comparison overlays.

**N. Team statistics — batting / bowling / fielding / partnerships.** _Done._ Spec at `docs/spec-team-stats.md`, ~21h of build. New `partnership` table (~180K rows, populated by `scripts/populate_partnerships.py`, auto-called by `import_data.py` + `update_recent.py`). 16 new endpoints on `api/routers/teams.py` covering: batting/bowling/fielding summary + by-season + by-phase + top-N players, phase × season heatmaps with run-rate AND wickets-per-innings, partnerships by-wicket + heatmap + top-10 + best-pairs (top-3 ranked by total runs together), opponents-matrix (rollup + cells), team-scoped tournaments + seasons (`/api/v1/tournaments?team=X`, `/api/v1/seasons?team=X&tournament=X&...`). Frontend: 4 new tabs on `/teams` (Batting, Bowling, Fielding, Partnerships), redesigned vs-Opponent tab (stacked-bar rollup + drill-in + bubble matrix instead of one-opponent-at-a-time dropdown), new `BubbleMatrix` and `HeatmapChart` components, win-% labels above wins-by-season bars (oxblood, per-bar tracking), team-aware FilterBar (auto-narrows team_type/gender + season list to team's actual matches), Match-list tab moved to last for player-page consistency, Home-page additions (RCB IPL 2025 / RCB Women WPL 2025/26 / Perth Scorchers BBL / MI Women WPL champion links + Pollard/Mooney fielders in focus + WI 2016 T20 WC). Wisden style addition: `.wisden-section-title` for centered editorial headings above charts (avoids the in-chart `title` prop colliding with above-bar percentage labels). Several follow-on items captured as "(revisit)" subsections in `docs/design-decisions.md`: tournament baselines (enhancement O), win-% overlay on discipline tabs, batter consistency stats (median / 30+ rate / dispersion), batter × bowler-type and bowler × batter-handedness splits.

**O. Tournament-baseline comparisons across team / batter / bowler / fielder pages.** Once enhancement M ships and we have per-tournament-per-season aggregates, every team-tab chart should be able to overlay the league mean as a reference line/band, every player table should gain a "vs league avg" column, and the phase × season heatmaps should support a "delta from league mean" colour mode. Detail in `docs/design-decisions.md` "Team metrics need tournament baselines (revisit when /tournaments ships)".
