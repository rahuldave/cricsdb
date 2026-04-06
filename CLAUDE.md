# CricsDB — T20 Cricket Analytics Platform

## Project Status

Live at: https://t20-cricket-db.pla.sh
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
    head_to_head.py   — /api/v1/head-to-head/{batter_id}/{bowler_id}
    matches.py        — /api/v1/matches list, /matches/{id}/scorecard, /matches/{id}/innings-grid
models/tables.py      — deebase models: Person, Match, Innings, Delivery, Wicket, etc.
team_aliases.py       — Canonical team-name mapping (used by import + fix script)
scripts/fix_team_names.py — One-time UPDATE pass to canonicalize old team names in cricket.db
import_data.py        — Downloads cricsheet JSON + imports into SQLite (canonicalizes via team_aliases)
frontend/src/
  App.tsx             — React Router: /, /teams, /batting, /bowling, /head-to-head, /matches, /matches/:matchId
  hooks/useUrlState.ts — useUrlParam + useSetUrlParams (atomic URL state updates)
  hooks/useFetch.ts    — { data, loading, error, refetch } wrapper around an async fn
  hooks/useContainerWidth.ts — ResizeObserver wrapper used by responsive chart wrappers
  components/         — Layout, FilterBar, PlayerSearch, StatCard, DataTable, Spinner, ErrorBanner, Scorecard, InningsCard, charts/
    charts/           — BarChart, LineChart, ScatterChart, DonutChart wrappers (responsive),
                        WormChart, ManhattanChart, InningsGridChart, MatchupGridChart
  pages/              — Home, Teams, Batting, Bowling, HeadToHead, Matches, MatchScorecard
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
uv run python import_data.py          # drops cricket.db and reimports

# Incremental update (just new T20 matches):
uv run python update_recent.py --dry-run --days 7   # check status
uv run python update_recent.py --days 7              # import
```

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

## Known Issues / TODO

- Bowling scatter chart (vs Batters): Y-axis is "bowling strike rate" (balls/wicket) which is counterintuitive — high = bad but looks prominent. Consider flipping axis or using average instead.
- Semiotic bar charts with many seasons get crowded x-axis labels. May need rotation or responsive sizing.
- Player search matches cricsheet names (e.g., "V Kohli" not "Virat Kohli"). The personname table alternate name search works but users may not expect abbreviated names in results.
- No loading spinners — data fetches show nothing while in flight.
- No error states — failed API calls silently show empty content.
- The deebase admin at /admin/ doesn't load on plash (deebase[api] extras not installed in vendored setup).
- Inter-wicket analysis is Python-side processing (~200ms for top players) — could be slow under load.
- Consider adding indexes on `(delivery.bowler_id, delivery.innings_id)` compound index for bowling queries.
- **`wicket.fielders` is double-JSON-encoded in the DB.** The import path in `import_data.py` does `json.dumps(w_data.get("fielders"))`, but deebase's JSON column type also serializes the value, so the stored string is e.g. `'"[{\"name\": \"SL Malinga\"}]"'` — a JSON string whose contents are themselves a JSON-encoded list. The matches scorecard router (`api/routers/matches.py:_build_dismissal_text`) works around this by calling `json.loads` twice. To fix at the source: in `import_data.py` pass the raw list (`w_data.get("fielders")`) instead of `json.dumps(...)` and rebuild the DB. Other JSON-typed columns (`match.dates`, `match.officials`, `match.player_of_match`, `innings.powerplays`) store correctly already — only `wicket.fielders` has the double-encode bug because it's the only one wrapped in `json.dumps` before insert.

## Future Enhancements

The list below is roughly ordered by value/effort. Pick the highest one
that fits the available time.

**A. Loading + error states across all pages.** _Done._ See `docs/data-fetching.md` for the full pattern (useFetch hook, Spinner, ErrorBanner, gated fetches, per-tab `<TabState>` helper, when NOT to use useFetch, where loading/error sit relative to data). Rolled out to Home, Matches list, MatchScorecard, Teams, Batting, Bowling, Head to Head, PlayerSearch dropdown, FilterBar dropdowns.

**B. Mechanically-generated ball-by-ball commentary tab on the scorecard page.** Cricsheet does NOT ship natural-language commentary like Cricinfo's editorial feed — what we have is structured ball data. So this would render each delivery as a feed line: `19.6 — Bumrah to Kohli — 4 runs (FOUR)` or `19.4 — Bumrah to Sharma — OUT! caught Rohit b Bumrah`. Useful and conventional, but be honest with users that it's generated from data, not a writer's prose. Pairs naturally with the **innings grid** (see `docs/design-decisions.md` "Innings grid: per-delivery visualization") — clicking a row in the grid could scroll the commentary feed to the same ball, and vice versa.

**C. Fix `wicket.fielders` double-encoding at the source.** Currently `import_data.py` calls `json.dumps(w_data.get("fielders"))` redundantly — deebase's JSON column type also serializes, so the stored value is a JSON string of a JSON string. The matches scorecard router parses twice as a workaround (`api/routers/matches.py:_build_dismissal_text`). Fix: drop the `json.dumps(...)` wrapper in `import_data.py`, rebuild the DB with `import_data.py`, then remove the double-decode branch. ~5-line code change + 15-min DB rebuild.

**D. Bowling-vs-Batters scatter Y axis is counterintuitive.** Currently shows "balls per wicket" which is high=bad but visually prominent. Either flip the Y axis or switch to bowling average (runs per wicket). See `pages/Bowling.tsx` and the Known Issues note above.

**E. Player search returns abbreviated cricsheet names** ("V Kohli" not "Virat Kohli"). The `personname` table has alias variants — search ranking should prefer alias matches that include a longer/more familiar form when one exists. Backend change in `api/routers/reference.py` (`/api/v1/players`) plus possibly a small ranking heuristic.

**F. Multi-player intersection filter on `/matches`.** Currently single player only. Extend `player_id` to `player_ids` and `AND` the EXISTS clauses. UI needs a multi-pill input. Useful but niche.

**G. Worm chart wicket markers as actual chart points** (not just a footer line). Currently the worm renders as two clean lines plus a "Wickets fell at: ..." text line beneath, because the existing Semiotic high-level wrappers don't expose per-point styling. To add markers we'd either drop down to `XYFrame` directly or layer a separate `Scatterplot` overlay. Worth doing for visual narrative but not critical.

**I. Responsive chart sizing.** _Done._ `frontend/src/hooks/useContainerWidth.ts` wraps a `ResizeObserver`. `BarChart`, `LineChart`, and `ScatterChart` wrappers make `width` optional and use the hook to fill their container when omitted. `DonutChart` stays fixed-width (a circle doesn't usefully stretch). All chart call sites now omit `width`; the dual-chart layouts that used `flex gap-6 flex-wrap` were converted to `grid grid-cols-1 lg:grid-cols-2 gap-6` (or `grid-cols-[350px_minmax(0,1fr)]` for donut+bar layouts) so each chart cell has a definite container width. The previous mobile pass's `overflow-x-auto` workaround on chart cards was stripped.

**K. Tournament-name canonicalization.** Same problem as team renames (which is now fixed — see `docs/design-decisions.md` "Team-name canonicalization across renames") but for `event_name`. Three competitions in the database appear under multiple sponsor names: NatWest T20 Blast / Vitality Blast / Vitality Blast Men (English domestic), CSA T20 Challenge / Ram Slam T20 Challenge / MiWAY T20 Challenge (South African domestic), and HRV Cup / HRV Twenty20 / Super Smash (New Zealand domestic). The teams within these are correct — only the tournament label differs by year. To fix: parallel `event_aliases.py` + `scripts/fix_event_names.py`, both modeled exactly on the team-aliases pattern. Touches `match.event_name` only. Should also patch `import_data.py` similarly so future imports stay clean.

**J. Distinctive visual identity.** The site is functional but generically Tailwind — Inter-ish system font, blue/gray utility palette, default shadows. Not bad, but not memorable either. A bolder typographic identity (e.g., a display serif or characterful sans for player names + headers, monospace tabular numerals for stats) and a stronger color hierarchy would lift it from "competent dashboard" to "memorable cricket database." This is a redesign pass, not a fix — flagged after a mobile-audit pass surfaced it as the highest-impact aesthetic improvement that wasn't a bug. Inspirations to consider: Cricinfo's editorial typography, Edward Tufte's data-density principles, the FiveThirtyEight numerical aesthetic.

**H. Reverse direction of the scatter↔table linking on Batting/Bowling vs-tabs.** The forward direction (click a row → highlight the matching dot on the chart with an `enclose` annotation, scroll the row into view) is shipped — see `docs/design-decisions.md` "Linking scatter charts to their data tables." The reverse direction (click a dot → highlight the row, scroll the table to it) is missing because Semiotic v3's high-level `Scatterplot` component does not expose `onClick` or any per-point click handler. Adding it requires dropping below the high-level helper to `XYFrame` directly: build a custom XY chart that wires `customClickBehavior` through to a callback, then plumb that callback up to the page state already managed for the table highlight. The wrapper at `frontend/src/components/charts/ScatterChart.tsx` is a good place to encapsulate this — add an `onPointClick?: (d: T) => void` prop and switch the implementation from `Scatterplot` to `XYFrame` only when that prop is set, so other callers don't pay the complexity. Once done, the page-level `selectedBowlerId` / `selectedBatterId` state in `Batting.tsx` and `Bowling.tsx` already drives row highlighting — just call the setter from the new click handler.
