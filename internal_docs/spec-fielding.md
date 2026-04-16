# Spec: Fielding Analytics (Tier 1)

## Overview

Add a Fielding page at `/fielding` at the same level as Batting and
Bowling. Every catch, stumping, run out, and caught-and-bowled in the
database is attributed to a fielder. No keeper/non-keeper distinction
in Tier 1 — all fielding contributions are treated equally.

Tier 2 (future, separate spec) adds keeper identification for 59% of
innings and a "Keeping" sub-tab on the fielding page.

## Scope

- **New table**: `fielding_credit` — one row per fielder-per-wicket,
  denormalized from the double-encoded `wicket.fielders` JSON + the
  `delivery.bowler_id` for caught-and-bowled.
- **Fielder name resolution**: a `fielder_aliases.py` mapping for the
  56 unmatched names (same pattern as `team_aliases.py`).
- **Fix**: the `wicket.fielders` double-encoding bug (Future Enhancement
  C in CLAUDE.md) — fix at the source in `import_data.py` so the new
  `fielding_credit` table gets clean data. Existing double-decode
  workarounds remain until the next full DB rebuild.
- **New API router**: `api/routers/fielding.py` with endpoints mirroring
  the batting/bowling pattern.
- **New frontend page**: `frontend/src/pages/Fielding.tsx` with search,
  stat cards, and tabbed analytics.
- **Nav + routing**: add Fielding to Layout nav and App.tsx routes.

## Data layer

### `fielding_credit` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | auto-increment |
| `wicket_id` | INTEGER FK → wicket | which wicket this credit belongs to |
| `delivery_id` | INTEGER FK → delivery | denormalized for joins to innings/match |
| `fielder_name` | VARCHAR | the name as it appears in cricsheet |
| `fielder_id` | VARCHAR FK → person | resolved person ID, NULL for ~42 unresolvable |
| `kind` | VARCHAR | `caught`, `stumped`, `run_out`, `caught_and_bowled` |
| `is_substitute` | BOOLEAN | true if the fielder was a substitute |

**Indexes**: `fielder_id`, `delivery_id`, `kind`.

**Row count estimate**: ~121,700 rows.
- 91,319 catches (1 row each)
- 5,517 stumpings (1 row each)
- 11,219 run outs with attribution (some have 2 fielders → ~16,637 rows)
- 5,155 caught-and-bowled (1 row each, bowler as fielder)

### Population logic (`scripts/populate_fielding_credits.py`)

For each wicket row:

1. **`kind = 'caught'`**: decode `fielders` JSON (handle double-encoding),
   extract `name` and `substitute` flag. Resolve `fielder_id` via
   `person.name` → `person.unique_name` → `personname.name` →
   `fielder_aliases.py` fallback. Insert one row.

2. **`kind = 'stumped'`**: same as caught. Insert one row.

3. **`kind = 'run out'`**: same, but may produce 2+ rows (one per
   fielder in the relay). Each row gets `kind = 'run_out'`.

4. **`kind = 'caught and bowled'`**: `fielders` is null. Look up
   `delivery.bowler_id` via the `delivery_id` FK. Insert one row
   with `fielder_id = bowler_id`, `fielder_name = bowler name`,
   `kind = 'caught_and_bowled'`.

5. **All other kinds** (bowled, lbw, hit wicket, retired, obstructing):
   no fielding credit. Skip.

The script is idempotent — it truncates `fielding_credit` before
repopulating. Called at the end of `import_data.py` (full rebuild)
and `update_recent.py` (incremental — repopulate only for new
wicket IDs).

### `fielder_aliases.py`

Same pattern as `team_aliases.py`. A `dict[str, str]` mapping
unmatched fielder names to canonical `person.name` values:

```python
FIELDER_ALIASES = {
    # Married name changes
    "NR Sciver-Brunt": "NR Sciver",        # 56 appearances
    "KH Sciver-Brunt": "KH Brunt",         # 6 appearances
    "L Winfield-Hill": "L Winfield",        # via personname alias
    # Disambiguated names (cricsheet uses parenthetical suffix)
    "Mohammad Nawaz (3)": "Mohammad Nawaz",  # match via unique_name
    "Imran Khan (1)": "Imran Khan",
    "Imran Khan (2)": "Imran Khan",         # different person, same name
    # ... remaining ~50 entries
    # (some will map to None = unresolvable)
}
```

For the disambiguated-name cases (e.g. "Imran Khan (2)"), the script
must look up `person.unique_name` to find the correct `person.id`
since multiple people share the canonical `person.name`.

### Fix `wicket.fielders` double-encoding

In `import_data.py` line 292, change:

```python
# Before:
"fielders": json.dumps(w_data.get("fielders"))
    if w_data.get("fielders") else None,

# After:
"fielders": w_data.get("fielders"),
```

The raw list from cricsheet is already the correct Python object for
deebase's JSON column type. The current `json.dumps()` wrapper
causes double-encoding. After this fix + a DB rebuild, the
`_build_dismissal_text` double-decode workaround in
`api/routers/matches.py` can be simplified to a single decode.

**Note**: the `fielding_credit` population script handles BOTH the
old double-encoded format and the fixed format, so it works before
and after a rebuild.

## API layer

### New router: `api/routers/fielding.py`

Mirrors the batting/bowling router pattern. All endpoints take the
standard `FilterParams` (gender, team_type, tournament, season_from,
season_to) via `Depends()`.

#### `GET /api/v1/fielders/{person_id}/summary`

```json
{
  "name": "MS Dhoni",
  "matches": 372,
  "catches": 210,
  "stumpings": 81,
  "run_outs": 74,
  "caught_and_bowled": 0,
  "total_dismissals": 365,
  "dismissals_per_match": 0.98,
  "substitute_catches": 0
}
```

SQL: count `fielding_credit` rows by kind, join through
`delivery → innings → match` for filters. Match count from
`matchplayer`.

#### `GET /api/v1/fielders/{person_id}/by-season`

```json
{
  "by_season": [
    { "season": "2023", "catches": 12, "stumpings": 4, "run_outs": 3, "total": 19 },
    ...
  ]
}
```

#### `GET /api/v1/fielders/{person_id}/by-phase`

Breakdown by powerplay / middle / death (via `delivery.over_number`).
Same phase boundaries as batting/bowling.

#### `GET /api/v1/fielders/{person_id}/by-over`

Dismissals per over number (1-20).

#### `GET /api/v1/fielders/{person_id}/dismissal-types`

Donut chart data: catches vs stumpings vs run outs vs c&b.

#### `GET /api/v1/fielders/{person_id}/victims`

Top batters dismissed by this fielder:

```json
{
  "victims": [
    { "batter_id": "ba607b88", "batter_name": "V Kohli", "catches": 3, "stumpings": 0, "run_outs": 1, "total": 4 },
    ...
  ]
}
```

#### `GET /api/v1/fielders/{person_id}/by-innings`

Match-by-match fielding log:

```json
{
  "innings": [
    { "match_id": 1234, "date": "2024-04-15", "opponent": "Mumbai Indians",
      "tournament": "Indian Premier League", "catches": 2, "stumpings": 1,
      "run_outs": 0, "total": 3 },
    ...
  ],
  "total": 150
}
```

Paginated (limit/offset) like batting/bowling innings list.

#### Player search

Reuse the existing `/api/v1/players` endpoint with `role=fielder`.
Backend change: add a fielder search path that queries
`fielding_credit` for players with fielding entries, ranked by total
dismissals. The existing `role=batter|bowler` paths remain unchanged.

### Register the router

In `api/app.py`, import and include the new router in the lifespan
handler (before the SPA fallback, same as other routers).

## Frontend layer

### New page: `frontend/src/pages/Fielding.tsx`

Same structure as Batting.tsx and Bowling.tsx:

1. **PlayerSearch** with `role="fielder"` and placeholder
   "Search for a fielder…"
2. **Page title**: player name (wisden-page-title)
3. **Stat cards** in a `wisden-statrow`:
   - Catches | Stumpings | Run Outs | Total | Matches | Dis/Match
4. **Tabs** (wisden-tabs):
   - By Season | By Over | By Phase | Dismissal Types | Victims | Innings List

#### Tab content

| Tab | Chart | Table |
|-----|-------|-------|
| **By Season** | BarChart: dismissals by season, stacked by kind | — |
| **By Over** | BarChart: dismissals by over number | — |
| **By Phase** | Three wisden-phaseblock cards (powerplay/middle/death) with catches/stumpings/run_outs per phase | — |
| **Dismissal Types** | DonutChart: catches vs stumpings vs run_outs vs c&b | — |
| **Victims** | — | DataTable: batter name, catches, stumpings, run_outs, total. Name column has (stats · h2h) links. |
| **Innings List** | — | DataTable: date (links to scorecard), opponent, tournament, catches, stumpings, run_outs, total. Paginated. |

#### By Season stacked bar

The BarChart wrapper currently doesn't support stacking. Two options:
- (a) Show total dismissals only (single color), same as batting runs-by-season. Simpler.
- (b) Show stacked bars (catches in indigo, stumpings in ochre, run_outs in oxblood). Requires a stacked-bar wrapper or raw Semiotic `BarChart` with `type="bar"` and `rAccessor` grouping.

**Recommendation**: start with (a). Add (b) as a follow-up if the
donut chart doesn't give enough visual breakdown by season.

### Routing

In `App.tsx`, add:
```tsx
<Route path="/fielding" element={<Fielding />} />
```

### Navigation

In `Layout.tsx`, add to `navItems`:
```tsx
{ to: '/fielding', label: 'Fielding' },
```

Position: after Bowling, before Head to Head.

### Types

In `frontend/src/types.ts`, add:

```typescript
export interface FieldingSummary {
  name: string
  matches: number
  catches: number
  stumpings: number
  run_outs: number
  caught_and_bowled: number
  total_dismissals: number
  dismissals_per_match: number | null
  substitute_catches: number
}

export interface FieldingSeason {
  season: string
  catches: number
  stumpings: number
  run_outs: number
  caught_and_bowled: number
  total: number
}

export interface FieldingVictim {
  batter_id: string
  batter_name: string
  catches: number
  stumpings: number
  run_outs: number
  total: number
}

export interface FieldingInnings {
  match_id: number
  date: string
  opponent: string
  tournament: string | null
  catches: number
  stumpings: number
  run_outs: number
  total: number
}
```

### Document title

`useDocumentTitle(summary ? `${summary.name} — Fielding` : playerId ? null : 'Fielding')`

### API client functions

In `frontend/src/api.ts`, add:

```typescript
export const getFielderSummary = (id: string, f?: F) =>
  fetchApi<FieldingSummary>(`/api/v1/fielders/${id}/summary`, f)
export const getFielderBySeason = (id: string, f?: F) =>
  fetchApi<{ by_season: FieldingSeason[] }>(`/api/v1/fielders/${id}/by-season`, f)
// ... etc for each endpoint
```

## Implementation order

1. **`fielder_aliases.py`** — the 56-name mapping dict. Manual work:
   cross-reference each unmatched name against `person.unique_name`,
   `personname`, and cricket knowledge. ~30 min.

2. **Fix double-encoding** in `import_data.py` (1 line). Don't rebuild
   yet — the population script handles both formats.

3. **`fielding_credit` model** in `models/tables.py`. Add the dataclass.

4. **`scripts/populate_fielding_credits.py`** — the population script.
   Run it against the existing DB to create and fill the table. Verify
   counts match expectations (~121,700 rows).

5. **`api/routers/fielding.py`** — all endpoints. Test with curl.

6. **Frontend types + API client** — types.ts + api.ts additions.

7. **`Fielding.tsx`** — the page, tabs, charts, tables.

8. **Routing + nav** — App.tsx + Layout.tsx.

9. **Hook into import pipeline** — call populate_fielding_credits at
   the end of import_data.py and update_recent.py.

10. **Full DB rebuild** (optional but recommended) — fixes the
    double-encoding and gives the cleanest data. ~15 min.

## Test cases

- Search for "MS Dhoni" → 365 total dismissals (210c, 81st, 74ro)
- Search for "KA Pollard" → 357 total (337c, 0st, 20ro) — confirms
  non-keeper shows zero stumpings
- By Season for Dhoni → stumpings should cluster in IPL seasons
- Victims for Dhoni → show the batters he's caught/stumped most
- Innings List date links → scorecard with highlight
- Filter by tournament=IPL → only IPL fielding stats
- Filter by gender=female → women's fielding stats only

## Out of scope (Tier 2)

- Keeper identification per innings
- "Keeping" sub-tab with catches-as-keeper vs catches-in-field
- Keeper-specific stats (byes conceded, stumpings per match keeping)
- Fielding positions (slip, point, etc. — not in cricsheet data)

## Estimated effort

- Data layer (steps 1-4): ~2 hours
- API (step 5): ~2 hours
- Frontend (steps 6-8): ~3 hours
- Pipeline hooks (step 9): ~30 min
- Testing + polish: ~1 hour

Total: ~8-9 hours
