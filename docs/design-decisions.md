# Design Decisions

## Data Layer

### Why SQLite, not PostgreSQL

The dataset is read-only (imported once from cricsheet), ~435MB, and query patterns are analytical aggregations (GROUP BY, SUM, COUNT). SQLite handles this well, is zero-config, and deploys as a single file. No need for a database server.

WAL mode is enabled on startup (`PRAGMA journal_mode = WAL`) to allow concurrent reads from multiple HTTP requests without blocking.

### Over numbering: 0-indexed in DB, 1-indexed in API

Cricsheet source data uses 0-indexed overs (`"over": 0` through `"over": 19`). The database stores this verbatim to stay faithful to the source. The API adds 1 before returning, so consumers always see overs 1-20.

This means:
- SQL queries use 0-19 internally (WHERE, GROUP BY, phase boundaries)
- Phase definitions in SQL: powerplay = `over_number BETWEEN 0 AND 5`, middle = `6 AND 14`, death = `15 AND 19`
- API responses show 1-20
- Frontend receives 1-20 and displays as-is

Alternative considered: re-import with +1. Rejected because it diverges from cricsheet's canonical format and would require remembering the offset when comparing with source data or other tools.

### Parameterized queries via `db.q(sql, params)`

deebase's `Database.q()` originally didn't support bind parameters — it called `session.execute(sa.text(query))` without a params dict. We patched it locally to accept `params: dict | None = None` and filed PR [rahulcredcore/deebase#8](https://github.com/rahulcredcore/deebase/pull/8).

All API queries use `:param_name` bind parameter syntax:
```python
await db.q("SELECT * FROM match WHERE gender = :gender", {"gender": "male"})
```

This prevents SQL injection and handles values containing special characters (e.g., team name "King's XI Punjab").

### Legal balls vs all deliveries

A critical distinction in cricket stats:
- **Legal balls** (for strike rate, balls faced/bowled): exclude wides and no-balls (`extras_wides = 0 AND extras_noballs = 0`)
- **All deliveries** (for runs conceded by bowler): include wides and no-balls because the bowler is charged for those runs

The batting router counts only legal balls. The bowling router runs two queries: one for legal balls (for economy denominator, dot ball count) and one for all deliveries (for total runs conceded, wide/no-ball counts).

### Bowler's wickets vs all wickets

Not all wickets are attributed to the bowler:
- **Bowler's wickets**: bowled, caught, caught and bowled, lbw, stumped, hit wicket
- **Not bowler's wickets**: run out, retired hurt, retired out, obstructing the field

The bowling router filters `kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')` for wicket tallies, averages, and strike rates.

For batting dismissals, we exclude `retired hurt` and `retired out` (voluntary exits) but include run outs.

### Boundary detection

A four is `runs_batter = 4` unless `runs_non_boundary` is set (221 cases in the dataset — typically overthrows or all-run fours). A six is always `runs_batter = 6`. The SQL:
```sql
CASE WHEN runs_batter = 4 AND COALESCE(runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END as fours
CASE WHEN runs_batter = 6 THEN 1 ELSE 0 END as sixes
```

## API Design

### Filter system

All analytics endpoints share a common filter system via `FilterParams` (FastAPI `Depends()`):
- `gender`: male/female
- `team_type`: international/club
- `tournament`: exact match on `match.event_name` (e.g., "Indian Premier League")
- `season_from`, `season_to`: lexicographic range on `match.season`
- `filter_team`, `filter_opponent`: contextual team filters

The `build()` method returns `(where_clause, params_dict)` with `:param_name` bind syntax. Every query appends this clause.

The `filter_team` and `filter_opponent` query parameter names use the `filter_` prefix to avoid colliding with path parameters like `/{team}/summary` in the teams router.

Super overs (`innings.super_over = 1`) are always excluded from stats.

### Team context: players change teams

A player like Kohli plays for India (international) and RCB (IPL). The `innings.team` field records which team a player batted for in each innings. Filtering by team uses `innings.team`, not a fixed player-team mapping.

The `matchplayer` table records per-match team assignments, and the `person` table is team-agnostic.

### Inter-wicket analysis: Python-side processing

The inter-wicket endpoint cannot be done efficiently in pure SQL because it requires tracking a running wicket count across deliveries within an innings. Instead:

1. Fetch all innings IDs where the batter participated
2. For each innings, fetch ALL deliveries (not just the batter's) ordered by ID
3. Walk through deliveries tracking cumulative team wickets
4. For each delivery the target batter faced, record stats in the current `wickets_down` bucket
5. Aggregate across innings

This processes ~5K-10K deliveries for a top player and runs in <200ms.

### Two queries for batting summary

The batting summary endpoint runs two queries:
1. **Ball-level**: aggregates across all legal deliveries (total runs, balls, fours, sixes, dots)
2. **Per-innings**: groups by (match_id, innings_number) to compute per-innings stats (highest score, 50s, 100s, 30s, ducks, not-outs)

These can't be combined in one query because per-innings stats need a GROUP BY that would change the ball-level aggregation.

## Frontend

### URL-synced state for deep linking

All page state is stored in URL search parameters, not React state alone. This means every view is bookmarkable and shareable.

The `useUrlParam(key, default)` hook wraps React Router's `useSearchParams()` to read/write individual URL params without clobbering others. Each page uses it for:
- Selected player/team ID
- Active tab
- Selected opponent (teams page)

Global filters (gender, tournament, season range) are also in URL params, managed by `FilterBar`.

Example URL: `/batting?player=ba607b88&tab=By+Over&tournament=Indian+Premier+League`

### Semiotic v3 chart wrappers

Semiotic v3 exports named chart components (`BarChart`, `LineChart`, `Scatterplot`, `DonutChart`) rather than the generic Frame components of v1/v2. Our wrappers are thin — they pass props through with sensible defaults:
- `enableHover: true` for tooltips
- Default dimensions (500x400 for most, 300x300 for donuts)
- Phase-based color schemes (blue=powerplay, green=middle, red=death)

### Linking scatter charts to their data tables

The Batting `vs Bowlers` and Bowling `vs Batters` tabs both render a scatter chart with a related `DataTable` underneath. The chart uses dot size to encode "balls faced/bowled," which makes the prominent dots visually striking — but originally there was no way to know *who* a dot was, or how it related to the rows in the table below. Three layered techniques solve it:

1. **Per-dot tooltip on hover.** `ScatterChart` passes Semiotic's `tooltip` prop through; the `vs-` tabs configure it with `{ title: 'bowler_name', fields: [...] }` so hovering any point shows the player's name and key stats.

2. **Top-N labels via annotations.** The 8 dots with the largest `balls` count get a `react-annotation` label drawn directly on the chart with the player's name. This means the visually-prominent points are immediately identifiable without hovering.

3. **Bidirectional row → dot link.** Clicking a row in the `DataTable` sets a selected id; the matching point gets an extra `enclose` annotation drawn on the chart, and the row itself is highlighted yellow + scrolled into view via a ref. So if the player you care about isn't one of the auto-labelled top 8, you can click their row to find them.

**Mechanics that make this work:**
- `ScatterChart` wrapper passes through `tooltip`, `annotations`, and `pointIdAccessor` to Semiotic.
- `DataTable` gained three optional, backwards-compatible props: `rowKey: (row) => string` for identity, `highlightKey: string | null` for which row to highlight, and `onRowClick: (row) => void`. Highlighted rows get a yellow background and `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` via a ref.
- Three annotation types are in use: **`widget`** (a point-anchored label with arbitrary `content: ReactNode`) for the top-N name labels, **`highlight`** (filters chart data by `field`/`value` and draws a circle on each match) for the ring around the selected row's dot, and a second **`widget`** above the selected dot for the player name.

**Semiotic v3 annotation gotchas worth knowing.** The annotation API is *not* the same as react-annotation that v1/v2 used:
- `type: "react-annotation"` does **not** exist in v3 — silently no-ops. Use `type: "widget"` for point-anchored labels and pass `content: <span>...</span>`.
- Annotations look up coordinates via the **same field-name strings** as the chart's accessors. So if your `Scatterplot` uses `xAccessor={(d) => d.strike_rate}` (an accessor function), the annotation can't anchor itself — it doesn't know the field name. Use string accessors (`xAccessor="strike_rate"`) and write annotations as `{ type: "widget", strike_rate: 130, average: 22, dy: -10, content: <...> }` so the field names line up.
- **`enclose` requires at least 2 coordinates** — it uses `d3.packEnclose` to compute a smallest-enclosing-circle hull, and the implementation does `if (coordinates.length < 2) return null`. So a single-point `enclose` silently no-ops. For a single-point ring use `highlight` instead: `{ type: "highlight", field: "bowler_id", value: id, color: "#dc2626", r: 14 }`. The `highlight` type filters the chart's data array by `field === value` and draws a circle at each match using the chart's accessors.
- Other valid v3 types you may want: `y-threshold` (horizontal line with label), `category-highlight` (column highlight on ordinal charts), `rect-enclose` (also requires 2+ coordinates), `bracket`, `note`, `callout`.

**The reverse direction (clicking a chart dot to highlight a table row) is deliberately NOT implemented.** Semiotic v3's high-level `Scatterplot` component does not expose `onClick` or any per-point click handler. Adding that would require dropping below the high-level helper to `XYFrame` directly, which is a bigger refactor and would lose some of the convenience defaults the wrapper provides. The tooltip + top-N labels + reverse direction (table → chart) already cover the original "I can't tell who the big dots are" complaint, so the forward direction (chart → table) is left for later — see CLAUDE.md Future Enhancements item H.

### SPA routing and the catch-all

React Router handles all navigation client-side. In production, FastAPI serves the built frontend:
1. API routes (`/api/v1/*`) match first (registered during app startup)
2. Static assets (`/assets/*`) match second (mounted via `StaticFiles`)
3. Everything else falls through to the SPA catch-all, which serves `index.html`

The catch-all is registered inside the lifespan handler, AFTER API routers, to ensure API routes take priority.

## Deployment

### Vendored deebase

pla.sh uses Python 3.12, but deebase requires 3.13+. Since the deebase source code is actually 3.12-compatible (no 3.13-specific syntax), we vendor it: the `deploy.sh` script copies the deebase package from `.venv/` into the build directory. The `requirements.txt` for plash lists deebase's dependencies (sqlalchemy, aiosqlite, etc.) but not deebase itself.

### Staged build directory

Plash uploads everything in the project directory except dotfiles. To avoid uploading large files (node_modules, raw data, database), the deploy script stages a clean `build_plash/` directory containing only:
- Python code (api/, models/, main.py)
- Vendored deebase
- Built frontend (frontend/dist/)
- requirements.txt
- data/cricket.db (only on first deploy with `--force_data`)

The `.plash` file in `build_plash/` is preserved across deploys to maintain the app identity.

### Database persistence on plash

Plash's `data/` directory persists across deploys. The 435MB `cricket.db` is uploaded once (`deploy.sh --first`), then subsequent deploys only update code. The `dependencies.py` detects production via `PLASH_PRODUCTION=1` (set automatically by plash) and reads from `data/cricket.db`.
