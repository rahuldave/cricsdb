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

### filterDeps arrays — explicit, per-page, easy to under-wire (revisit)

Every page that runs `useFetch(fn, deps)` maintains its own hand-rolled
`filterDeps` array listing the individual filter fields it cares about
— `[filters.gender, filters.team_type, filters.tournament,
filters.season_from, filters.season_to, filters.filter_team,
filters.filter_opponent, filters.filter_venue, …]`. This is explicit
and gives every page tight control over which filter changes trigger
refetches, but it's a **landmine when adding a new filter**: Phase 2
of Venues added `filter_venue` to `FilterParams`, the FilterBar, and
the URL — but the page-level `filterDeps` arrays kept the old list, so
an SPA-set venue change wouldn't trigger a refetch (only reloading
would, because reload rebuilds from URL). We patched 13 call sites +
5 carry functions by hand.

**Revisit when it bites again**: either derive `filterDeps` from
`Object.values(filters)` in `useFilters()` — stable-keyed so reference
identity is preserved when nothing changes — or expose a
`useFilterDeps()` helper that returns the same array everywhere. The
carry-filter utilities (`components/teams/teamUtils.ts::carryTeamFilters`,
`components/players/roleUtils.ts::carryFilters`, inline blocks on
Batting/Bowling/Fielding, `TournamentsLanding.buildFilterQs`) would
collapse similarly. Risk is if an unrelated URL param sneaks into
`useFilters()` later and starts triggering spurious refetches — but
that's a discipline thing, not an architectural blocker.

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
- **Safari + `widget` annotations don't survive prop updates.** `widget` renders into a `<foreignObject>` containing an HTML React node. Safari/WebKit has long-standing bugs reusing `foreignObject` contents when React updates the same node with new props — the old contents stay on screen. Chrome handles it fine. **Rule of thumb:** use `widget` only for annotations whose content is **stable** for the lifetime of the chart (e.g. the top-N name labels — once computed they don't change). For annotations whose content *changes* in response to user interaction (e.g. the selected-row highlight), use `label` instead — it renders as pure SVG `<text>` via d3-annotation and updates correctly in Safari. The `highlight` annotation (single-point ring) is also pure SVG and is Safari-safe.

**The reverse direction (clicking a chart dot to highlight a table row) is deliberately NOT implemented.** Semiotic v3's high-level `Scatterplot` component does not expose `onClick` or any per-point click handler. Adding that would require dropping below the high-level helper to `XYFrame` directly, which is a bigger refactor and would lose some of the convenience defaults the wrapper provides. The tooltip + top-N labels + reverse direction (table → chart) already cover the original "I can't tell who the big dots are" complaint, so the forward direction (chart → table) is left for later — see CLAUDE.md Future Enhancements item H.

### Scorecard auto-scroll to highlighted row

Clicking a date in the Batting, Bowling, or Fielding innings-list opens the match scorecard with a query param (`?highlight_batter=`, `?highlight_bowler=`, or `?highlight_fielder=`, each carrying a person ID). Matching rows get a greenish `.is-highlighted` class and the page auto-scrolls to center the first one.

**Three highlight modes, one selector.** The shared CSS class lets a single `document.querySelector('.is-highlighted')` serve all three modes. `querySelector` returns the first match in document order, which is exactly the behavior we want — for a fielder who has multiple catches, we scroll to their first dismissal; for a batter, to their row in their team's innings; for a bowler, to their row in the bowling table of the opposing innings.

**Fielder attribution goes through `fieldingcredit`, not the dismissal text.** The scorecard API adds `dismissal_fielder_ids: string[]` to each batting row, populated by joining `fieldingcredit` for the innings. That means the frontend never has to parse "c Dhoni b Bumrah" strings to decide whether a row involves the highlighted fielder — it just checks `row.dismissal_fielder_ids.includes(id)`. Run-outs with multiple fielders are covered naturally (each fielder appears in the array).

**Scroll is page-level, not per-InningsCard.** Earlier, each `InningsCard` ran its own `useEffect` → `scrollIntoView` when its ref resolved. That fired *before* sibling async sections (`WormChart`, `ManhattanChart`, `MatchupGridChart`, `InningsGridChart`) had fetched and sized, so the target row was displaced once layout settled. The fix moves the scroll to `MatchScorecard.tsx`, gated on **both** fetches (`data` and `grid.data`) completing, inside a double `requestAnimationFrame` — the first rAF lets the current commit paint, the second lets layout settle. Then `querySelector` finds the first highlighted row and `scrollIntoView({ block: 'center' })` centers it.

**Why not anchor hashes?** `scrollIntoView` operates on a DOM element reference and doesn't require anchors. Hashes would pollute the URL and break when the highlighted element's ID isn't stable (e.g. when data reloads). Direct DOM selection keeps the URL clean and always targets the current first-highlighted element.

### Team-name canonicalization across renames

Cricket franchises rename themselves periodically. Cricsheet records the team name that was current when each match was played, so the same franchise appears in the database under multiple strings depending on the season. Without merging, queries that group by team string treat (e.g.) "Kings XI Punjab" and "Punjab Kings" as separate teams — which makes the Teams page show two Punjabs, the Matches list filter show two RCBs, and breaks every cross-season aggregation.

**Where the truth lives.** A single source-of-truth Python module at `team_aliases.py` (project root) holds a `dict[str, str]` mapping each old name to the canonical (most recent) name, plus a `canonicalize(name)` helper.

**How it's applied.** Two paths:

1. **One-time fix** for the existing database via `scripts/fix_team_names.py`. Walks every (table, column) tuple that holds a team string — `match.team1`, `match.team2`, `match.outcome_winner`, `match.toss_winner`, `innings.team`, `matchplayer.team` — and runs `UPDATE` statements per alias. Idempotent (safe to re-run; the second pass finds zero rows because canonical names aren't keys in the alias map). Has a `--dry-run` mode that reports row counts without writing. Calls `VACUUM` at the end.

2. **At import time** via `import_data.py`. The `import_match_file()` function calls `canon_team()` on every team string before insert (`team1`, `team2`, `toss_winner`, `outcome_winner`, `matchplayer.team`, `innings.team`). Future imports — including incremental updates from `update_recent.py`, which reuses `import_match_file()` — are clean automatically.

**Why this approach (and not the alternatives).**

- **Aliases table + COALESCE in queries** — non-destructive but every existing query needs updating, easy to forget one, and joins/coalesce add per-query cost. Rejected.
- **In-API canonicalization** — apply at the response layer instead of the storage layer. Same forgetting risk, plus `WHERE team = ?` queries from the frontend pass the canonical name and the storage layer wouldn't match unless the API also rewrote the query parameters. Rejected.
- **Direct UPDATE in the existing DB only** (no import_data patch) — works once, breaks the next time you do a full DB rebuild. Rejected.
- **Direct UPDATE + import_data patch** ← chosen. Cleanest because the DB itself is canonical (no query code knows or cares about the rename history) AND the cleanliness is preserved across rebuilds.

**Choosing the canonical name.** For each franchise, pick the **most recent** name. The current name is what the user expects to see when they look at recent matches; old-name aggregations get attributed to the current branding.

**Conservative principle: only merge confirmed renames.** A team is merged only when (a) the franchise has continuous ownership across the rename and (b) the rename is well-attested in cricket sources. Cases NOT merged:

- **BPL franchises** — Bangladesh Premier League has had massive ownership churn, with new ownership groups frequently buying the franchise slot for a city. Same city, different team. Without specific knowledge of every franchise's ownership history, we can't confidently call any of them renames.
- **St Lucia Stars** vs Zouks/Kings — Stars was a separate one-season ownership in 2017-2018, NOT the same franchise as the Zouks→Kings lineage.
- **Antigua Hawksbills** (2013-2014) vs **Antigua and Barbuda Falcons** (2024+) — 10-year gap, new franchise, different ownership. Not merged.
- **Deccan Chargers** (became defunct), **Gujarat Lions**, **Pune Warriors**, **Kochi Tuskers Kerala** — all dissolved franchises; their successors (in the case of Deccan, Sunrisers Hyderabad) are conventionally treated as new teams.

**Tournament-name canonicalization** (done in a follow-up pass) — uses the exact same pattern at `event_aliases.py` + `scripts/fix_event_names.py`. Three competitions had multiple sponsor brand names in the data:

- **NatWest T20 Blast** / **Vitality Blast Men** → **Vitality Blast** (English domestic men's T20, NatWest 2014-2017, then Vitality from 2018+; cricsheet added "Men" disambiguator in 2025 which we collapse back since there's no women's Vitality Blast)
- **MiWAY T20 Challenge** / **Ram Slam T20 Challenge** → **CSA T20 Challenge** (South African domestic men's T20, three sponsor eras)
- **HRV Cup** / **HRV Twenty20** → **Super Smash** (New Zealand domestic men's T20)

The `import_data.py` patch covers both `canon_team()` and `canon_event()` calls so future imports stay clean. Effect on local DB: 784 `match.event_name` rows updated, club-tournament count drops from 27 to 21. The single exception to the "latest wins" rule lives in `event_aliases.py`: we collapse `Vitality Blast Men` back to `Vitality Blast` because the disambiguator is unnecessary in our data and the cleaner name reads better in the UI.

**Effect of running `fix_team_names.py` on the existing DB:** ~13,400 rows updated across the six (table, column) pairs, mostly in `matchplayer.team` (each match has ~22 player rows, and ~600 matches were affected by the IPL renames alone). After the fix, IPL drops from 19 distinct team strings to 15 (the four rename pairs collapse), LPL from 16 to 5 (massive consolidation due to LPL's per-season sponsor rebrands), CPL from 12 to 9 (three rename pairs collapsed, three deliberately-separate franchises kept).

**One thing this doesn't fix.** A few pages currently use the team string in the URL path (`/teams?team=Kings+XI+Punjab`). Bookmarked links to old-name URLs will return empty data after the rename because the storage no longer has those strings. Could add a tiny redirect at the API layer that catches the four-or-so old IPL names and rewrites the query — not done because the affected URL count is small. Logged for later.

### Season labels: split-year formats and what they mean

Cricsheet's `season` field uses the **cricket board's own season designation**, not the calendar year the matches were played. This produces three formats:

- **Plain year** (`2023`): the season falls within one calendar year.
- **Split year** (`2022/23`): the season crosses a year boundary.
- **Both for the same tournament** (e.g. IPL has `2007/08`, `2009/10`, `2020/21` alongside plain `2011`–`2019`, `2021`–`2026`).

**Southern Hemisphere leagues** (BBL, WBBL, Super Smash, CSA T20 Challenge) genuinely cross the calendar year boundary (Dec–Feb), so `2022/23` is correct and meaningful — matches span both calendar years.

**Indian domestic cricket** (Syed Mushtaq Ali Trophy) similarly runs Oct–Jan, so split seasons are expected.

**IPL split seasons are historical artifacts:**
- `2007/08` — IPL was conceived as part of the 2007/08 Indian cricket season; all matches were in April 2008.
- `2009/10` — same pattern; matches were in March 2010.
- `2020/21` — COVID-disrupted IPL played Sep 2020 – Oct 2021 (genuinely split).
- From 2011 onward (except 2020/21), IPL uses plain years because it settled into a Mar–May window.

**Effect on the season filter:** The `season_from` and `season_to` filters use lexicographic comparison. This means `2009/10` sorts after `2009` but before `2010`. A filter of `2009`–`2009` would NOT include IPL 2009/10 (which was really the 2010 tournament). This is technically correct per the season label but can be surprising to users who think in calendar years.

**Why we don't normalize:** Mapping split seasons to their end year would work for IPL (where the matches all fall in one calendar year) but break BBL/WBBL (where matches genuinely span both years). The inconsistency is in the source data and any normalization would be lossy for some tournaments. We pass through cricsheet's labels as-is.

### Matchup grid: per-innings batter × bowler matrix

A second new chart on the scorecard page (sibling to the innings grid). For each innings, renders the full set of batter-vs-bowler matchups that happened in that innings as an HTML table: batters as rows in batting order, bowlers as columns in order of first appearance, each cell shows that pair's `runs(balls)w` for the innings. Lives in `frontend/src/components/charts/MatchupGridChart.tsx`.

**Why it exists.** The regular scorecard tells you each batter's total and each bowler's total but not how those totals decomposed between specific opponents. The matchup grid shows the cross-section: did a particular bowler get rinsed by a particular batter? Did a bowler dismiss multiple batters? Was the run-scoring concentrated against one bowler or distributed?

#### Layout

| | Bowler 1 | Bowler 2 | Bowler 3 | … |
|---|---|---|---|---|
| **Batter 1** | `25(11)¹w` | `8(7)` | `–` | … |
| **Batter 2** | `13(8)` | `48(21)` | `1(1)` | … |
| **Batter 3** | `–` | `14(8)¹w` | `…` | … |

- **Batters as rows, bowlers as columns** — bowlers attack batters, so reading a single batter row left-to-right scans "what each bowler did to me."
- **Sticky left column** for the batter name (`position: sticky; left: 0`) so the row label stays visible during horizontal scroll on mobile.
- **Rotated bowler names** in the header (60°) so the columns can be narrow without truncating long bowler names.
- **Cell content**: `runs` in bold black + `(balls)` in gray + a small red `Nw` superscript when wickets fell. Empty cells (no balls faced) show a faded `·`.
- **Light heatmap**: red-100 background where the bowler took at least one wicket; light green where the batter scored at SR ≥ 150 (over ≥4 balls). White otherwise. Tints are subtle so the cell text stays readable.
- **One grid per innings**, stacked vertically.

#### Cell links

Every non-empty cell is a `<Link>` to `/head-to-head?batter={bid}&bowler={pid}` carrying the same `gender` / `team_type` / `tournament` query params as the rest of the scorecard's player links. So clicking any cell takes you to the players' full career head-to-head pre-filtered to this match's tournament context. The `linkParams` string is computed once in `MatchScorecard.tsx` (mirroring the same computation that lives in `Scorecard.tsx`) and passed down as a prop.

#### Wicket attribution

A wicket counts toward a `(batter, bowler)` cell only if **both**:
1. The dismissal kind is bowler-creditable (mirrors the backend `NON_BOWLER_WICKETS` exclusion list — run-out, retired, retired hurt, obstructing).
2. The dismissed batter is the on-strike batter at that ball (handles the rare edge case where a non-striker is given out as part of an extras play).

This keeps the matchup wicket counts in agreement with the bowling figures shown in the regular scorecard.

#### Position on the page

In `ScorecardView`'s children slot, **after** the worm/Manhattan charts but **before** the regular innings tables. Final order on the scorecard page:

1. Back link
2. Header card
3. Worm + Manhattan charts
4. **Matchup grids** (new)
5. Regular innings tables (the per-batter / per-bowler scorecard)
6. Innings grids (the per-delivery visualization)

The user wanted the matchup grid "above the scoreboard" — the scoreboard means the per-innings tables at #5.

#### Backend cost

Zero new round-trip. The matchup matrix is computed entirely on the frontend from the deliveries that the existing `/api/v1/matches/{id}/innings-grid` endpoint already returns. The endpoint was extended to include:

- `batter_id`, `bowler_id`, `bowler_index` on each delivery row
- `bowlers: string[]` and `bowler_ids: (string|null)[]` arrays at the innings level (parallel to the existing `batters` / `batter_ids`)

So both the innings grid AND the matchup grid share one network call.

#### Responsiveness

CSS table inside `overflow-x-auto`. Sized in `rem` units. The sticky left column means horizontal scroll on mobile keeps the batter name visible. At iPhone 13 width (390px), about 3-4 bowler columns fit on screen at once and the rest scroll into view. No mobile-specific reflow — the matrix structure is intrinsic to what's being shown.

#### Things to revisit later

- **Sort order toggle** — currently rows are batting order and columns are bowling-introduction order. Could add a button to sort rows by total runs, or columns by total wickets.
- **Highlight a row/column on hover** — dim the others to make scanning easier in dense cases.
- **Phase coloring** — subtly tint the column header by the phase the bowler bowled most balls in (powerplay/middle/death).
- **A `dot %` micro-stat in each cell** — useful but might over-clutter the cell.

### Innings grid: per-delivery visualization

A novel chart on the scorecard page that renders an entire batting innings as a grid: rows are deliveries top-to-bottom, columns are batters left-to-right in order of appearance. The on-strike batter's cell is colored to encode what happened on that ball. Lives in `frontend/src/components/charts/InningsGridChart.tsx`, backed by a new `/api/v1/matches/{id}/innings-grid` endpoint that returns ordered deliveries plus the ordered batters list.

**Why it's interesting.** Traditional scorecards show aggregate stats per batter. The grid shows the *time-series structure* of the innings — when each batter came in, who was their partner, when they faced sustained pressure, where the boundaries clustered. Vertical extent of a column = how long that batter was at the crease. Horizontal gap between two columns = how far apart in the order they came in.

#### Visual encoding

| Element | Color / shape | Notes |
|---|---|---|
| Off-bat runs | Greens, light → dark by run count | 0 → light gray (dot ball), 1 → mint, 4 → bright green, 6 → dark green |
| Wide (extras only) | Yellow `#fde047` | Text `w` or `w(N-1)` for wide+ran |
| No-ball (extras only) | Slightly darker yellow `#facc15` | Text `n` |
| No-ball + off-bat runs | Off-bat color (green) with small orange `n` overlay | Honest about the off-bat runs without losing the no-ball flag |
| Bye | Orange `#fb923c` | Text `b` or `b{n}` |
| Leg-bye | Lighter orange `#fdba74` | Text `lb` or `lb{n}` |
| Wicket | Red `#dc2626` | Text `W`, drawn in the *dismissed* batter's column (handles non-striker run-outs correctly) |
| At crease, not facing | Pale blue (slot A) or pale violet (slot B) | See "Slot inheritance" below |

#### Slot inheritance for the at-crease stripes

Each batter is assigned one of two "slots" — A or B — and their stripe is rendered in slot A's color (`#dbeafe` blue-100) or slot B's color (`#fce7f3` pink-100). The first ball's batter is A; the non-striker is B. On every wicket, the first not-yet-assigned batter to appear inherits the dismissed batter's slot. So at any moment the two at-crease batters always have one A and one B stripe, and a new batter walking in always takes the SAME shade as the one they replaced. Visually you can scan a column and see the partnership it belongs to without guessing.

The colors went through three iterations:
1. **Single tint** (`#dbeafe`) — confusing because both at-crease batters were the same color, no slot visual.
2. **Blue-50 + cyan-50** — too close in hue, merged visually at thumbnail scale.
3. **Blue-50 + violet-50** — clearer hue split but still too pale; the stripes barely registered against the white background.
4. **Blue-100 + pink-100** _(current)_ — cool-warm hue split at a slightly stronger lightness. Both still recede behind the saturated semantic colors (greens, wicket red, extras yellow/orange) but are obviously different at any zoom.

Rejected alternatives that came up along the way: blue + amber-100 — risked confusion with extras yellow/orange; cross-hatch / dot-pattern fills instead of solid color — harder to read; full saturation — fought the foreground encoding too much. Pink was OK against red-600 wicket because the lightness gap is huge — `#fce7f3` is almost white compared to `#dc2626`.

#### Layout

```
[over.ball] [bowler] [batter cells × N] | [run histogram] | [score] | [wicket text]
```

- **Over column** prints `over.ball` (e.g., `6.5`) only on the first ball of each over; other balls get a faded `·` placeholder.
- **Bowler column** prints the bowler name only on bowler change (handles mid-over substitutions automatically — same logic as the over column, just on bowler equality).
- **Batter cells** is the main grid. Most cells in any given row are empty/striped; only the on-strike batter's column has a colored cell (or the dismissed batter's column for a wicket).
- **Histogram column** decomposes the ball's runs by source. Each "run unit" gets its own small cell, colored by source: green for off-bat, yellow for no-ball penalty, more yellow for wides, orange for byes, lighter orange for leg-byes. So `noball + 4 off the bat` shows as 4 green cells + 1 yellow cell. The total count is shown in small black text in the leftmost cell.
- **Score column** shows the cumulative team score after this ball as `runs/wickets`.
- **Wicket text column** is populated only on wicket balls and shows the standard scorecard dismissal format (e.g., `c Rohit b Bumrah`). Hidden below the `md` breakpoint to keep the grid fitting on phones.
- **Vertical 2px dividers** separate the four conceptual sections (batter cells, histogram, score, wicket text).

#### Summary rows

Two kinds of slim summary rows are interleaved between ball rows:

- **Over summary** — gray-accented, after the last ball of each over: `end of over N · X runs[, Y wkts]`
- **Partnership summary** — blue-accented, after every wicket and after the final ball of the innings: `partnership N · R runs (B balls)`

Both summary rows preserve the full per-batter cell layout and render the at-crease tints with the same slot colors as ball rows. This is critical: without it the stripes would be broken by the gray over-summary band, and a batter's "presence stripe" wouldn't read as one continuous vertical band from arrival to dismissal. Both summary types use a shared `SummaryRow` helper component.

#### Sizing and responsiveness

All sizing in `rem` (not raw pixels) so the grid respects the user's root font scale. The grid is wrapped in `overflow-x-auto` because at iPhone 13 width (390px), 11 batter columns plus the sidebars exceed the available width and must scroll horizontally. The wicket-text column is hidden via `hidden md:flex` on viewports below 768px so the grid stays compact on phones; the wicket text is still accessible via the cell's title tooltip.

#### Position on the page

The grid is rendered as a sibling AFTER `<ScorecardView>`, NOT in its `children` slot. Order on the scorecard page: header → charts (worm + Manhattan) → innings tables → innings grids. This was a deliberate revision — the original prototype rendered the grid via `children`, putting it between the header and the innings tables, but the user found that the grid's height and visual density buried the more familiar scorecard tables.

#### Things considered but not built

- **SVG-based rendering** — rejected, HTML divs are easier to align with the rest of the page and don't need a custom layout engine. Performance is fine for ~120 rows × ~17 columns per innings.
- **Cross-hatch / dot-pattern fills** for the at-crease stripe instead of solid color — rejected, less readable and still requires a color choice.
- **A vertical "partnership lane"** showing partnership runs as a growing bar to the right of the batter columns — rejected in favor of summary rows after each partnership end, which are simpler and read more like cricket scorecards.
- **Click-to-expand cell** for full delivery details — could be added later, currently only the cell `title` tooltip shows the info on hover.
- **Hover sync** with the worm and Manhattan charts (hovering a ball in one would highlight the same ball in the others) — would be a nice polish but requires shared selection state between three components.
- **Replay animation** — render the innings ball-by-ball over time, like a cricket simulator — fun but not core.
- **Two innings side by side** instead of stacked — would need narrower cells to fit two grids horizontally; stacked is fine for now.
- **Mobile-first reflow** — at iPhone 13 width the user has to scroll horizontally. A truly mobile-friendly variant would be a stacked-card view with one batter per card, but that loses the time-series structure that makes the grid interesting in the first place.

#### Things to revisit

- **Color accessibility.** The stripes are differentiated by hue + lightness, but I haven't tested with color-blindness simulators. The dot ball gray vs the at-crease blues could blur for some color profiles. Worth running through Coblis or similar.
- **Histogram cap.** The histogram has 7 cells, which covers the realistic max (boundary off no-ball = 5) plus headroom. A pathological wide that goes for 7+ runs would clip silently. Add an overflow indicator if it ever matters.
- **Partnership numbering** restarts at 1 for each innings. When showing both innings, that's slightly confusing. Consider prefixing with the team or innings number.
- **DOM size.** Each innings is ~120 rows × (4 sidebar cells + N batter cells + 7 histogram cells + 3 column dividers) ≈ 25 elements per row × 120 rows = 3,000 nodes per innings, ~6,000 per match. Renders fine on desktop and on iPhone 13 in my testing, but if we ever support test cricket (~600 balls per innings), virtualization would be worth considering.
- **Bowler change visualization.** Currently the bowler name appears on the row of the new bowler's first ball. Could add a small marker or thicker top-border on bowler-change rows for emphasis.
- **Phase coloring on the over column.** The current chart has powerplay/middle/death color schemes; could subtly tint the over-number column background by phase.

#### Features worth adding later

- **Ball-by-ball commentary feed** as a sibling tab — render each delivery as a sentence (`19.6  Bumrah to Kohli — 1 run`) using the same data. Pairs naturally with the grid: click a row in the grid to scroll the feed to the same ball, and vice versa.
- **Per-batter highlight on hover** — hover a batter's column header and dim everything except that batter's cells. Same on the row dimension for bowlers.
- **Filter toggles** above the grid: "show only boundaries", "show only wickets", "show only powerplay", "extras only" — selectively dim non-matching cells.
- **Comparison mode** — overlay two innings grids (e.g., chase vs target) with the second innings shown semi-transparent.
- **Click a cell → modal with full delivery details**, including any commentary text and the wagon-wheel position if cricsheet ever exposes it.

### Rotated x-axis labels: HTML overlay outside the SVG

When a `BarChart` has more categories than fit at the chart's pixel width (e.g. 30 seasons crammed into ~330px on iPhone 13), labels overlap. Standard fix is to rotate them ~60°. With Semiotic v3's high-level `BarChart`, that turns out to be much harder than expected. The journey through five failed attempts and one working approach is recorded here so the next person changing chart styling doesn't repeat it.

**What didn't work and why:**

1. **`categoryFormat` returning SVG `<text transform="rotate(-60)">`.** Semiotic puts the result inside `<foreignObject><div>`, so the SVG `<text>` element becomes unknown HTML inside HTML — the SVG `transform` attribute is silently ignored. Verified by inspecting the live DOM (parent of the rotated `<text>` is `DIV`, not `<g>`).

2. **`frameProps.oLabel` (the lower-level OrdinalFrame API).** OrdinalFrame's `oLabel` accepts a function returning a real SVG `Element`. But the high-level `BarChart` wrapper builds its own `oLabel` from `categoryLabel` and passes that through, overriding anything in `frameProps.oLabel`. Verified by reading the minified bundle.

3. **`categoryFormat` returning HTML `<div>` with `position: absolute`.** The wrapper Semiotic provides has no `position: relative`, so the absolute children escape to the SVG root and every label stacks in the upper-left corner of the chart. Visually verified.

4. **`categoryFormat` with `padding-right: 50%` + `text-align: right` + transform.** Worked in Chrome. Broke in Safari — labels coalesced in two upper-left clusters. WebKit's `<foreignObject>` content layout has multiple known bugs around percentage padding and absolute positioning.

5. **Bare `display: inline-block + transform: rotate(-60deg)`** (no positioning, no padding, no text-align). Still broke in Safari — all labels coalesced in the upper-left corner. The `transform` on a foreignObject child appears to disable the foreignObject's positional `x`/`y` propagation in WebKit.

**What worked: HTML overlay outside the SVG.** The escape hatch is to abandon `<foreignObject>` entirely and render labels as plain HTML positioned over the chart container.

```tsx
const ROT_MARGIN = { top: 50, right: 20, bottom: 90, left: 60 }
return (
  <div style={{ position: 'relative' }}>
    <SemioticBarChart
      ...
      categoryFormat={() => ''}                   // suppress default labels
      frameProps={{ margin: ROT_MARGIN }}          // pin chart-area dims
    />
    <div style={{ position: 'absolute', left: ROT_MARGIN.left,
                  top: finalHeight - ROT_MARGIN.bottom + 6,
                  width: effectiveWidth - ROT_MARGIN.left - ROT_MARGIN.right }}>
      {data.map((d, i) => {
        const xPct = ((i + 0.5) / data.length) * 100
        return (
          <div style={{ position: 'absolute', left: `${xPct}%`, width: 0 }}>
            <div style={{
              position: 'absolute', right: 0, top: 0,
              transformOrigin: '100% 0',
              transform: 'rotate(-60deg)',
            }}>{getLabel(d)}</div>
          </div>
        )
      })}
    </div>
  </div>
)
```

The mechanics: empty-string `categoryFormat` removes Semiotic's default labels (the empty foreignObjects render nothing — that part works in all browsers). `frameProps.margin` pins the chart area to known offsets so we know where the bars are. Each overlay label is a wrapper at `left: xPct%` with `width: 0`, with a child positioned `right: 0` so its right edge is at the bar center; `transform-origin: 100% 0` makes the rotation pivot at the top-right corner, and `rotate(-60deg)` makes the text trail down-and-to-the-left.

**One related quirk:** `categoryLabel` (the axis-name label) gets positioned by Semiotic inside the bottom margin, where the rotated overlay also lives. They visually collide. When rotating, set `categoryLabel={undefined}` — the rotated tick labels themselves (years, over numbers) are self-evident enough that the axis name is redundant.

**Generalizable lesson.** Anything more than plain text inside a `<foreignObject>` is a roll of the dice on WebKit. Position, padding percentages, transforms, even bare inline-blocks can all break. When you need rich content over an SVG chart in a way that has to work cross-browser, render it as a sibling HTML overlay positioned with absolute coordinates, and use `frameProps.margin` to pin the chart area so the overlay's coordinate system matches.

### SPA routing and the catch-all

React Router handles all navigation client-side. In production, FastAPI serves the built frontend:
1. API routes (`/api/v1/*`) match first (registered during app startup)
2. Static assets (`/assets/*`) match second (mounted via `StaticFiles`)
3. Everything else falls through to the SPA catch-all, which serves `index.html`

The catch-all is registered inside the lifespan handler, AFTER API routers, to ensure API routes take priority.

### Run rate: concatenated, not per-innings averaged (revisit)

Every team-level rate metric (`run_rate`, `economy`, by-season, by-phase,
phase × season heatmaps) is the **concatenated rate**:

```
run_rate = SUM(runs in scope) × 6 / SUM(legal balls in scope)
```

NOT the mean of per-innings rates. So MI's 2023 powerplay RR is the
total PP runs across all 16 IPL 2023 powerplays divided by the total PP
legal balls × 6 — every ball gets equal weight.

**Why this matters:** the two methods only diverge when innings have
materially different lengths in the bucket. For the powerplay this is
mostly a non-issue — every innings spends ~30 legal balls in the PP
unless the team is bowled out inside it (rare). But in the middle and
death phases, length variance is huge: a chase finishing in 14 overs
contributes 0 death-phase balls, a collapse can compress the middle to
20 balls, etc. Concatenated weights long completed innings more (which
is usually correct — they show what tempo the team actually settled
into), but it understates "we typically open at X" when only a few
innings dominate the sample.

**Revisit if/when:**
- A user asks "how does the team typically pace itself" — that's the
  per-innings-mean metric, not the concatenated one.
- We add a "average innings RR" companion column to the run-rate
  heatmaps so users can compare "what we usually did" vs. "the
  weighted-average tempo".
- Phase-level cells with tiny `n` (low ball count) start influencing
  comparisons unduly — at that point either filter cells with `balls <
  threshold` or surface both views side-by-side.

For now: keep concatenated everywhere, label tooltips with `balls=N`
and `innings=N` so the reader can judge sample size themselves.

### Team metrics need tournament baselines (revisit when /tournaments ships)

Most team-tab charts currently show **absolute values**: "MI hit 410 4s
in 2024", "MI's 2023 boundary % was 21.9%", "MI's PP economy in 2022
was 8.5". These are uninformative on their own — they answer "what
happened" but not "was that good?"

A boundary % of 21.9% looks great until you learn the IPL 2023 league
average was 19.4% (above average) or 24% (below). 4s/season totals are
even more misleading because they scale with games played (10-team
league + playoffs = many games).

**The fix (planned for after the Tournaments tab ships):** every
team-level rate metric should optionally render the **tournament-and-
season-scoped average** as a horizontal reference line on bars / a
pale comparison line on time-series / a contour band on the heatmap.

Backend: a `/api/v1/tournaments/{event}/{season}/baselines` endpoint
returning the season's averages for every metric we display. Frontend:
a "vs tournament average" toggle on each chart card.

Concrete examples of where this matters:
- Boundary % time-series — show the league average % each season as a
  pale dashed line. MI above the line = better-than-average tempo.
- 4s/6s by season — convert to "4s per innings" first (so the bars are
  comparable to the league mean), then overlay the league mean.
- Phase × season heatmap — colour by **delta from league average** in a
  toggle mode (oxblood = above league mean; indigo = below; cream =
  near).
- Top-N batter SR — append a "league SR for that season" column.

This is a follow-on for enhancement M (Tournaments page) — once we
have per-tournament-per-season aggregates, we get baselines for free.
Until then, team charts are absolute-only and the user has to remember
that "9.5 RR in death" is good for 2014 but only OK for 2024.

### Win-% overlay on discipline tabs (revisit)

The team By Season tab and the vs-Opponent drill-in chart already
overlay win % above each wins bar (oxblood text via BarChart's
`topLabelFormat`). Same idea wants to extend to the Batting / Bowling
/ Fielding / Partnerships tabs:

- A pale "team won that match"-marker (oxblood dot, indigo dot) on
  every per-season chart, so the reader can see at a glance whether
  the team's elevated boundary % in 2024 came from won games or lost
  games.
- On phase × season heatmaps, an optional "filter to wins only / losses
  only" toggle so you can see "what we did in our wins" vs "what
  failed in our losses".
- On batter / bowler leaderboards within a team tab, a "win
  contribution" indicator (% of player's runs/wickets that came in
  team wins).

Goal: surface visual correlation between performance metrics
(boundary %, RR, econ, catches/match, partnership averages) and
**winning**. By itself "MI's death-phase RR is 10.5 in 2024" is just
a number; coloured by win/loss it answers "is this how we won, or
did the death-phase RR collapse in losses?"

This pairs naturally with the tournament-baselines work — together
they let the user see "performance vs tournament average, weighted by
whether we won". Postponed until both pieces are in place.

### Batter consistency metrics — median / 30+ rate / dispersion (revisit)

A batter who scores two 150s + ten single-digit innings has a
respectable mean, but the median tells you the player only really
helped the team in 2 of 12 games. The current Batting page shows mean
(`average`), strike rate, 50s/100s — but no measure of **consistency**.

Stats to consider (defer until a separate "batter shape" pass):
- **Median** alongside mean — when median ≪ mean, the player's value
  is concentrated in a few innings.
- **% of innings ≥ 30** (or ≥ team-context threshold) — proportion of
  innings where they made a "useful" contribution.
- **Standard deviation** of innings score — lower SD = more reliable.
- **Coefficient of variation** (SD/mean) — normalised dispersion.
- A small box-and-whiskers (or strip-plot) per season showing the
  spread of innings scores rather than just the mean.

Tied conceptually to the win-% overlay above: a player who scores big
only in losses (mean-inflated) is materially less valuable than one
who scores big in wins (mean × win-contribution).

Same applies to bowlers (a 4-for and three 0-for vs a steady 1-for
each game) — wickets-per-innings dispersion + economy SD per match.

Postponed.

### Player splits — batter × bowler-type and bowler × batter-handedness (revisit)

Two player-page splits we want but don't have:

**Batter splits (on /batting):** SR / avg / boundary % broken down by
bowler type — left-arm spin (LAS), right-arm spin (RAS), left-arm pace
(LAP), right-arm pace (RAP). Helpful for "which match-up does this
batter exploit / struggle against" reads. Cricsheet records bowling
style per delivery's bowler (via `person.key_*` cross-references and
external sources), so the join needs an enrichment pass first — bowler
style is NOT in the cricsheet match JSON we currently import.

**Bowler splits (on /bowling):** wickets / econ / SR broken down by
batter handedness (LHB vs RHB). Same enrichment problem: handedness
isn't in cricsheet's match data.

Both require extending the `person` table with two columns:
`batting_hand` (LHB/RHB) and `bowling_style` (LAS/RAS/LAP/RAP/none).
Population can come from Cricinfo / Cricbuzz (we already have their
keys on `person`) — a separate scraper script, similar to the
`scrape_cricinfo_keepers.py` pattern we sketched for keeper resolution.

**Threshold cut-off for "useful sample":** the user suggested grouping
by averages "below ~15 or so" to flag genuine-tail vs proper-batter
match-ups, but 15 is too low even for T20 (ball-faced threshold is
more meaningful). Tentative defaults:
- Batter splits: include only opponents the batter has faced ≥ 30
  legal balls of (otherwise the SR is dominated by 1-2 deliveries).
- Bowler splits: include only batters the bowler has bowled ≥ 12
  balls to.

The actual thresholds want experimentation — surface as tunable query
params on the endpoint, default to the above.

Postponed. Tied to the broader player-detail enrichment work.

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

## Brand assets

### Fraunces variable-font axes need Chrome, not rsvg-convert

The site's masthead ampersand is a specific Fraunces italic glyph — optical-size 144, weight 400. Fraunces is a variable font with four axes (`ital`, `opsz`, `wght`, plus `SOFT` and `WONK` for alternate shapes).

We regenerate `favicon.svg`, the PNG icons (`apple-touch-icon.png`, `icon-192.png`, `icon-512.png`), and the 1200×630 `og-card.png` from source. First pass used `rsvg-convert` on SVG files with `font-variation-settings` embedded — but `rsvg-convert`'s Cairo/Pango font stack on macOS ignores those variation settings entirely. The result rendered Fraunces's default-WONK glyph, which is a DIFFERENT italic ampersand shape than the masthead shows. The two surfaces read as inconsistent.

Fix: source the PNGs from headless Chrome instead. `frontend/scripts/assets-source/` contains `favicon.html` + `og-card.html` — self-contained HTML files that load Fraunces from Google Fonts, set `font-variation-settings` on the glyphs, and rely on Chrome's CSS font renderer to honour the axes. The regeneration recipe (in the sibling `README.md`) uses `agent-browser screenshot body <path>` to capture the rendered output at exact pixel dimensions, followed by `sips -z` to downscale the 512×512 favicon PNG to the 180 / 192 sizes.

Corollary: the SVG favicon still ships (browsers honour variable axes when rendering SVG favicons), but the authoritative source of truth for the icon and OG-card shapes is the Chrome-rendered PNG. If anyone future-edits `favicon.svg` in isolation, the browser render will drift from the PNGs. The scripts/assets-source/README documents the round-trip.

## Team Compare: no special FilterBar awareness, picker probes scope-match

The `/teams` Compare tab reuses the player-compare architecture almost verbatim: `TeamCompareGrid` mirrors `PlayerCompareGrid`, `TeamSummaryRow` mirrors `PlayerSummaryRow`, `AddTeamComparePicker` mirrors `AddComparePicker`. The interesting divergence is how cross-gender / cross-team_type adds get blocked.

Players does a bespoke probe (`getBatterSummary(id)` → read `nationalities[0].gender`) because `PlayerSearchResult` carries no gender, and a URL-paste add can bypass the dropdown entirely.

Teams sidesteps that. The primary's presence drives FilterBar's auto-narrow (`FilterBar.tsx:99-108` — when the primary's tournaments are all one type and/or one gender, `team_type` + `gender` get auto-filled with `replace: true`). Every real team in the DB is either fully international or fully club, so the one-type guarantee always holds in practice. `TeamSearch`, in turn, calls `getTeams({...filters, q})` and the `/teams` list endpoint honours `team_type` + `gender` + `tournament` — so the picker dropdown can't surface a wrong-type team.

`AddTeamComparePicker` still runs a probe, but it's a scope-match-count check (`getTeamSummary(candidate, filters).matches < 1`), not a team-type / gender inspection. This catches the one race-condition path — if a URL-paste add arrives before the FilterBar auto-narrow effect fires, the candidate's scope-match count is zero and the add is refused in-place with a clear "no matches in current filter scope" message.

**Why it matters if you future-edit this:** don't thread `team_type` / `gender` into `AddTeamComparePicker` as explicit props or gates. The FilterBar is the single source of truth; duplicating the gate elsewhere would be an instance of the URL-as-input anti-pattern we fixed across all search inputs (see `internal_docs/url-state.md`).

**Pre-existing bug fixed in the same batch:** `/{team}/fielding/summary` was computing its `matches` count without applying `FilterParams`, so it returned an all-formats / all-genders / all-time number even under a filter scope. That fed `catches_per_match` / `stumpings_per_match` / `run_outs_per_match` as a diluted denominator (India men's intl was 422 instead of ≈263). Fix: the matches query now reuses the same `where` / `params` built by `_team_innings_clause(filters, team, side="fielding")` that the kind aggregation above it already uses.

The Compare identity line still reads from `profile.summary.matches` — same value conceptually now, but it's the match-level count (team_summary's `COUNT(*)` over filtered matches) vs the fielding endpoint's innings-derived `COUNT(DISTINCT m.id)`. The two can diverge by a handful of abandoned / no-result matches where a team never fielded; `summary.matches` is the canonical headline number.

## Team-name link scope ambiguity — disambiguate via a `TeamLink` component (revisit)

As of 2026-04-18 the scope attached to a team-name hyperlink varies by the
page that emits it:

- **Teams landing / team tiles / FlagBadge linkTo:** `/teams?team=X&gender=&team_type=`.
  Pure overall view.
- **Matches list row, Scorecard header, Series dossier team cells:**
  `/teams?team=X&tournament=Y&gender=&team_type=`. Tournament-scoped.
- **Stray `<Link>`s without a helper:** sometimes just `?team=X`.

Clicking "India" therefore means three different things depending on where
you click. For tournament events (e.g. T20 World Cup (Men)) the
tournament-scoped link lands on "India across all editions" because
`tournament` is the canonical event name — editions are keyed via
`season_from` / `season_to`. For bilateral series, `tournament` is a
transient series name ("Pakistan tour of New Zealand 2026"), and clicking
a team link from a bilateral match lands on a scoped view that may show
just the 1-3 matches of that tour. Feels broken.

The cleanest fix is a `TeamLink` component parallel to `PlayerLink`, with
the same two-link name + context pattern:

- Name link → `/teams?team=X&gender=&team_type=` (overall, always).
- Context link (optional, faint italic suffix) → `/teams?team=X&...filter params`.
  Context suffix should read "in {tournament} {season}" for
  tournament-scoped views and "in {bilateral-series-name} {season}" for
  bilaterals — the bilateral + season tuple disambiguates the specific
  tour the same way tournament + season disambiguates a tournament
  edition.
- Dense contexts (scorecard h2) use a compact mode that skips the
  context suffix; the tournament link in the meta line already carries
  that affordance.

The `PlayerLink` pattern can't be reused verbatim because it's hard-coded
to discipline routes. A dedicated `TeamLink` keeps the two-link rule
consistent site-wide and eliminates the current ambiguity. Not done in
this session — flagged for the next one.

## Scorecard linkability: API response-shape follow-up

The scorecard (`/matches/{match_id}`) has several text fields that
would benefit from being linked — player mentions that currently
render as plain strings because the backend returns names without
person IDs. Listed here as a pre-defined shopping list for when we
extend the matches router's response shape.

Pure-frontend linking was shipped for: match breadcrumb (tournament /
season-edition / all-matches escape hatches), toss-winner team name,
innings-header team name.

Still needs backend work:

- **`player_of_match` (`ScorecardInfo.player_of_match: string[]`)** —
  currently names only. Should be `{name, person_id}[]` so the
  frontend can wrap each in a `PlayerLink`. Tiny change: one extra
  join in `api/routers/matches.py` when building the info block.
- **Dismissal text (`ScorecardBatter.dismissal: string`)** — e.g.
  "c Sharma b Bumrah". The fielder half is already covered by the
  separate `dismissal_fielder_ids: string[]` field (see CLAUDE.md
  "Fielder dismissal attribution"); the bowler half is embedded only
  in the text string. Cleanest fix: return structured
  `dismissal: {how_out, bowler?: PersonRef, fielders?: PersonRef[]}`
  alongside (or instead of) the pre-rendered string, and have the
  frontend compose the "c X b Y" text with each name wrapped.
- **Did-not-bat (`ScorecardInnings.did_not_bat: string[]`)** — same
  shape issue. Change to `PersonRef[]`.
- **Fall-of-wickets (`ScorecardFallOfWicket`)** — has the over/score,
  but batter is embedded in a text string. Change to expose
  `batter: PersonRef` directly on the fall-of-wickets row.

All four are response-shape changes to `/api/v1/matches/{match_id}` —
cheaply added in one PR since the backend already has person_id
access (it's doing the fielder join for one of them). Do as a single
batch to avoid multiple deploy cycles.
