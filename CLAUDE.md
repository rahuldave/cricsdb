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
models/tables.py      — deebase models: Person, Match, Innings, Delivery, Wicket, etc.
import_data.py        — Downloads cricsheet JSON + imports into SQLite
frontend/src/
  App.tsx             — React Router: /, /teams, /batting, /bowling, /head-to-head
  hooks/useUrlState.ts — useUrlParam + useSetUrlParams (atomic URL state updates)
  components/         — Layout, FilterBar, PlayerSearch, StatCard, DataTable, charts/
  pages/              — Home, Teams, Batting, Bowling, HeadToHead
deploy.sh             — Stages build_plash/ dir and runs plash_deploy
SPEC.md               — Full specification with all API schemas and SQL queries
docs/                 — frontend-build-pipeline.md, design-decisions.md
```

## Running Locally

```bash
# Backend (port 8000)
uv run uvicorn api.app:app --port 8000

# Frontend dev server (port 5173, proxies /api → 8000)
cd frontend && npm run dev
```

Open http://localhost:5173

## Deploying

```bash
# First deploy (uploads 435MB database):
bash deploy.sh --first

# Subsequent deploys (code only, DB persists in plash's data/):
bash deploy.sh
```

The deploy script stages a clean `build_plash/` directory with only the needed files. deebase is vendored (plash runs Python 3.12, deebase needs 3.13+).

## Rebuilding the Database

```bash
uv run python import_data.py
```

Downloads all T20 JSON data from cricsheet.org into `data/`, imports into `cricket.db`. Takes ~15 minutes.

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
