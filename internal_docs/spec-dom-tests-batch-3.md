# Spec — DOM-tests Batch 3 (3a / 3b / 3c)

> **Status:** SHIPPED. Batch 3 wrap commit `d7984e1` ("Batch 3c
> commit 4 … + Batch 3 wrap"). Picked up after Batch 2 ship
> (commit `b57b63a`). 23 scripts + 1 cross-cutting test + 2 small
> harness extensions, split into 3 sub-batches at natural commit
> boundaries — all landed.

Total dom/ suite at start of Batch 3: 18 scripts, 353 assertions.
Target at end of Batch 3: ~41 scripts, ~750 assertions, every
sub-tab in the spec covered.

---

## Pre-flight (start of any sub-batch)

```bash
# Confirm Batch 2 still green
for s in tests/integration/dom/teams_*.sh tests/integration/dom/series_*.sh; do
  $s 2>&1 | grep -E "PASS$|FAIL$" | tail -1
done
# Should print 18 lines all "PASS".

# Confirm dev servers are up
lsof -ti:8000  # uvicorn --reload
lsof -ti:5173  # vite

# Confirm cricket.db exists
ls -lh cricket.db
```

If any Batch 2 script fails: investigate before adding new scripts.
The audit/*.sql files use `m.season BETWEEN '2024' AND '2025'` style
pinning, so cricsheet retroactive edits flip values noisily. Update
the failing script's expected dict + commit before continuing.

---

## Harness conventions to honor

Lessons from Batch 1 + 2 — apply throughout:

1. **Closed-window anchors.** Use `season_from=2024&season_to=2025`
   (intl) or `season_from=2025&season_to=2025` (IPL 2025). Past
   seasons don't drift.
2. **+4s soak on multi-fetch tabs.** The Records tab fans out to 5+
   DataTable endpoints; the default 3s soak in `navigate()` isn't
   enough. Add `sleep 4` after navigate when extracting from any
   fan-out tab. Symptom: "no table found" on first run, works on
   second eval.
3. **Independent SQL ground truth.** Every script MUST cite an
   `audit/<script-name>.sql` that derives the expected numbers from
   `cricket.db` directly without reading `api/` source. The DOM-test
   value-add is "API correct + UI wrong" detection — that requires
   ground truth from outside the API code path.
4. **Boundary formula gotcha.** Fours = `runs_batter=4 AND
   COALESCE(runs_non_boundary,0)=0` (excludes all-run 4s). Sixes =
   `runs_batter=6` plain (every 6 is a boundary by definition).
   Mirrors `populate_bucket_baseline.py:237`.
5. **Catches inclusive convention.** API's `catches` field =
   catches_only + caught_and_bowled. Audit pins both decomposed
   counts plus the inclusive total per CLAUDE.md
   "Wides/noballs/catches semantic".
6. **Chip envelope rendering.** API often returns `{value,
   scope_avg, delta_pct, …}` for stats. If a DataTable column has
   no `format` function and the field is an envelope, React
   stringifies the object as `[object Object]`. The DOM test will
   catch this — fix the JSX with a narrow format function that
   pulls `.value` (template in `pages/Teams.tsx:wicketColumns` post
   commit `6f8099c`).
7. **Dossier endpoints request `limit=10` by default.** When
   asserting a top-N DataTable, expect 10 rows even if the bare API
   (without `&limit=10`) returns 5.

---

## 3a — Teams completion + Series Landing club twin

**6 scripts, ~1 hour, no harness extensions needed.** Reuses
`extract_team_overview`, `extract_data_table`, `extract_landing_tiles`
from `_lib.sh`. Closes the Teams chapter of the inventory.

### 3a-1: `teams_match_list_club.sh`

The club twin of Batch 1's `teams_match_list_intl_fm.sh`. Anchor:
RCB IPL 2025 match list.

```bash
URL: /teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Match+List
Endpoint: /api/v1/teams/Royal%20Challengers%20Bengaluru/results?...
Total rows: 15
First row (DESC by date): 2025-06-03 vs Punjab Kings  (final loss)
Last row: 2025-03-22 vs Kolkata Knight Riders         (opener)
Extractor: extract_data_table
Audit: audit/teams_match_list_club.sql — count + first/last opponents
```

Reuses `run_data_table_assertions`. Same structure as the intl twin.

### 3a-2: `teams_vs_opponent_intl.sh`

Aus vs India 2024-25 (T20 WC 2024 group-stage match). Endpoint:
`/api/v1/teams/{team}/vs/{opp}` returns `{overall, by_season,
matches}`. The vs-Opponent tab renders a `.wisden-statrow` of
4 StatCards (Matches/Wins/Losses/Ties) plus a per-season chart
plus a match list.

```bash
URL: /teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=vs+Opponent&vs=India
Endpoint: /api/v1/teams/Australia/vs/India?...
Expected (from API): overall.matches=1, wins=0, losses=1 (India won
                     the SF in the WC 2024 — note this is just 1
                     match in window).
Extractor: extract_team_overview (StatCards)
Audit: audit/teams_vs_opponent_intl.sql — pin matches/wins/losses
```

Note: 1-match window is unusual — pick a richer 24-25 rivalry if
the SOLO match is too thin. Eng-vs-Aus, Ind-vs-SL, etc. Verify via
curl in pre-flight.

### 3a-3: `teams_vs_opponent_club.sh`

RCB vs MI IPL 2025. Probably 2 matches (home + away).

```bash
URL: /teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=vs+Opponent&vs=Mumbai+Indians
Verify: /api/v1/teams/Royal%20Challengers%20Bengaluru/vs/Mumbai%20Indians?...
Audit: audit/teams_vs_opponent_club.sql
```

### 3a-4: `teams_players_intl.sh` + 3a-5: `teams_players_club.sh`

Team Players tab — roster grid. Renders a DataTable of
(person_id, name, innings_batted, innings_bowled, …). For Aus
24-25 the roster is ~25 players; for RCB IPL 2025 it's ~22.

```bash
Anchor INTL: /teams?team=Australia&...&tab=Players
Anchor CLUB: /teams?team=Royal+Challengers+Bengaluru&...&tab=Players
Endpoint: /api/v1/teams/{team}/players?...  (verify exact path —
          may be /matchplayers or /squad)
Extractor: extract_data_table
Audit: COUNT(DISTINCT mp.person_id) FROM matchplayer mp WHERE …
       Pin total row count + first row (top batter by innings).
```

**Pre-flight check** — confirm the endpoint path and JSON shape
before writing the script. Some teams pages may redirect Players to
the standalone `/players?...` page; if so, this script may need to
target a different surface.

### 3a-6: `series_landing_club.sh`

The club twin of Batch 1's `series_landing_intl_fm.sh`. Same
extractor (`extract_landing_tiles`), different anchor — male club
2025, no team_class filter (team_class is intl-only).

```bash
URL: /series?gender=male&team_type=club&season_from=2025&season_to=2025
Tile assertions: IPL 2025 (74 matches), CPL 2025 (31 matches), BBL
                 2024/25 (?), … — verify counts via curl on
                 /api/v1/series/landing
Extractor: extract_landing_tiles
Audit: audit/series_landing_club.sql — match counts per tournament
```

### 3a — commit cadence

One commit per script-pair OR one commit per logical group:
- Commit 1: teams_match_list_club + teams_vs_opponent_{intl,club} (3 scripts)
- Commit 2: teams_players_{intl,club} (2 scripts)
- Commit 3: series_landing_club (1 script)

Total: 3 commits, ~6 scripts, ~50 assertions added.

---

## 3b — Series sub-tabs (12 scripts + 1 harness extension)

**Opens with a small harness extension before the script work
starts.** ~3-4 hours. The Series sub-tabs render multiple DataTables
per page; today's `extract_data_table` only grabs the first.

### Harness extension: `extract_data_table` gains an ordinal arg

Today:
```bash
extract_data_table()  →  walks document.querySelector('.wisden-table')
```

Add an optional ordinal index parameter:
```bash
extract_data_table_at "${idx:-0}"  →  document.querySelectorAll('.wisden-table')[idx]
```

Or — cleaner — replace `extract_data_table` with a positional arg:
```bash
extract_data_table 0  →  first table (default, current behavior)
extract_data_table 1  →  second table
```

Implementation: change the JS extractor to accept an index argument.
agent-browser eval supports template substitution via stdin variable
binding; alternatively wrap the JS in a sourceable function with
$1 substituted before passing to eval.

Test the extension by re-running Batch 2's `series_records_*` scripts
(they should still find table 0 cleanly) plus a probe call against
table 1 on the records tab (should return "lowest_all_out_totals").

Commit standalone before any Batch 3b script: `tests/integration/dom:
extract_data_table accepts ordinal index for multi-table pages`.

### 3b-1: `series_editions_intl.sh` + 3b-2: `series_editions_club.sh`

The Editions tab ("/series?tournament=X&tab=Editions") shows all
editions of a tournament. Backed by `/api/v1/series/by-season`
(NOT `/series/editions` — endpoint name differs from tab name).

```bash
Anchor INTL: /series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&tab=Editions
Anchor CLUB: /series?tournament=Indian+Premier+League&gender=male&team_type=club&tab=Editions
Endpoint: /api/v1/series/by-season?tournament=...
Returns: {tournament, seasons: [{season, matches, champion, top_scorer, …}, …]}

For IPL: 19 seasons (2008-2026). T20 WC: 9 seasons.
Audit: COUNT(DISTINCT season) per tournament. Pin top + last row.

Extractor: extract_data_table_at 0 (single table on this tab —
                                    won't need the new ordinal arg)
```

### 3b-3: `series_batters_intl.sh` + 3b-4: `series_batters_club.sh`

Series > Batters tab. Backed by `/api/v1/series/batters-leaders`
which returns `{by_runs, by_average, by_strike_rate, thresholds}`.
The DOM renders 2-3 DataTables in sequence (one per leaderboard
mode, plus an active-mode picker).

```bash
Anchor INTL: /series?tournament=ICC+Men%27s+T20+World+Cup&...&tab=Batters
Anchor CLUB: /series?tournament=Indian+Premier+League&...&tab=Batters

Endpoint check: /api/v1/series/batters-leaders?...&limit=5
  Returns: by_runs[5], by_average[5], by_strike_rate[5]

For IPL 2025:
  by_runs[0]: B Sai Sudharsan, 759 runs (Gujarat Titans)
  by_average[0]: SA Yadav, 65.18 avg (Mumbai Indians)
  by_strike_rate[0]: V Suryavanshi, 208.26 SR (Rajasthan Royals)

Extractor: extract_data_table_at 0  (by_runs)
           extract_data_table_at 1  (by_average — needs the new arg)
Audit: SQL JOIN delivery+innings+match GROUP BY batter_id
       ORDER BY total_runs DESC LIMIT 5
```

### 3b-5: `series_bowlers_intl.sh` + 3b-6: `series_bowlers_club.sh`

Analogous to batters. `/series/bowlers-leaders` returns `{by_wickets,
by_economy, by_strike_rate, thresholds}`.

```bash
For IPL 2025: by_wickets[0]: M Prasidh Krishna, 25 wickets (GT)
Audit: SQL with wicket-kind exclusions per CLAUDE.md "Bowler wickets:"
```

### 3b-7: `series_fielders_intl.sh` + 3b-8: `series_fielders_club.sh`

`/series/fielders-leaders`. Top-N by total dismissals + by
keeper-dismissals.

```bash
Audit: SQL on fieldingcredit + matchplayer (or just delivery+innings
       side-neutral) GROUP BY fielder_id
       Note: catches inclusive (catches_only + caught_and_bowled) per
       CLAUDE.md convention.
```

### 3b-9: `series_partnerships_intl.sh` + 3b-10: `series_partnerships_club.sh`

`/series/partnerships/by-wicket` + `/series/partnerships/top`. The
tab renders the by-wicket grid (10 rows) + a top-N list.

```bash
Extractor: extract_data_table_at 0 (by-wicket grid, 10 rows)
           extract_data_table_at 1 (top partnerships list)
Audit: 
  By-wicket: GROUP BY p.wicket_number; COUNT, AVG runs, MAX runs.
  Top-N: ORDER BY p.partnership_runs DESC LIMIT 10.
```

For IPL 2025, top partnership is probably ~200 (need to verify).

### 3b-11: `series_matches_intl.sh` + 3b-12: `series_matches_club.sh`

Full match list within the dossier scope. Same shape as
`teams_match_list_*` but the route is `/series` and the filter is
`tournament=` (not `team=`).

```bash
Anchor INTL: /series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&tab=Matches
  → 44 rows
Anchor CLUB: /series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Matches
  → 74 rows
Extractor: extract_data_table (first table — only one on this tab)
Audit: COUNT(*) FROM match WHERE event_name + season filters.
       Pin first row (most recent) + last row (oldest in window).
```

### 3b — commit cadence

Inside-out by complexity:
- Commit 1: extract_data_table_at extension (standalone)
- Commit 2: series_editions_{intl,club}
- Commit 3: series_matches_{intl,club} (simplest of the leaderboards)
- Commit 4: series_partnerships_{intl,club}
- Commit 5: series_batters_{intl,club} + series_bowlers_{intl,club}
- Commit 6: series_fielders_{intl,club}

Total: 6 commits, 12 scripts + 1 harness ext, ~120 new assertions.

---

## 3c — Specials + cross-cutting (5 scripts, ~1 hour)

Closes the spec. ICC-only and club-only tabs, plus the cross-cutting
consistency test.

### 3c-1: `series_overview_intl_bilateral.sh`

The bilateral-rivalry anchor for Series Overview (deferred from Batch
2). Tests that `filter_team` + `filter_opponent` produce a rivalry-
scoped dossier.

```bash
URL: /series?filter_team=India&filter_opponent=Australia&gender=male&team_type=international&series_type=bilateral&season_from=2024&season_to=2025
Endpoint: /api/v1/series/summary?filter_team=India&filter_opponent=Australia&...
  Returns: {…, by_team: {team1: {…}, team2: {…}}, head_to_head: {…}}
DOM renders: rivalry h2h StatCards + per-team summary cards
Extractor: extract_team_overview (StatCards)
Audit: SQL count + per-team wins via the side-neutral pair clause.
```

Note S7 anchor in `series-type-anchor-numbers.md` is 0 (Ind-vs-Aus
bilateral 2024-25 = 0). Verify a richer rivalry — Ind vs SL, Aus
vs Eng, etc. — via pre-flight curl.

### 3c-2: `series_champions_intl.sh`

ICC-only Champions tab. T20 WC Men all years. Backed by the
`champions_by_season` field of `/api/v1/series/summary` (no
separate endpoint).

```bash
URL: /series?tournament=ICC+Men%27s+T20+World+Cup&tab=Champions
DOM: A simple table of (year, champion). 9 editions.
Extractor: extract_data_table
Audit: SELECT season, outcome_winner FROM match WHERE
       event_name = 'ICC Men''s T20 World Cup' AND event_stage =
       'Final' GROUP BY season ORDER BY season ASC.
       Pin first row (2007 — first edition, India won) + last row
       (2024 — India won again).
```

No club twin — IPL doesn't have a "Champions" tab because its
single-season champion is shown in the Editions tab.

### 3c-3: `series_knockouts_intl.sh`

ICC-only Knockouts tab. T20 WC Men 2024 — semis + final. Backed by
the `knockouts` field of `/series/summary`.

```bash
URL: /series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&tab=Knockouts
DOM: A small DataTable of (stage, team1, team2, winner, margin)
     2024 had 2 knockouts (SF + Final).
Extractor: extract_data_table
Audit: SELECT event_stage, team1, team2, outcome_winner, … FROM match
       WHERE event_name = '...' AND event_stage IN ('Semi Final',
       'Final') ORDER BY date.
```

### 3c-4: `series_points_club.sh`

Club-only Points tab. IPL 2025 league-stage points table.
`/api/v1/series/points-table` returns `{tables: [{group, rows: [...]}]}`.

```bash
URL: /series?tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Points
DOM: One DataTable per group (IPL is a single round-robin so one
     table). Rows: team, played, won, lost, NRR, points.
Extractor: extract_data_table
Audit: SELECT team, COUNT(*) AS played,
              SUM(outcome_winner = team) AS won, … 
       FROM match WHERE event_stage NOT IN ('Final', 'Eliminator', …)
       GROUP BY team ORDER BY points DESC.
       Pin top row (group winner) + last row (wooden spoon).
```

For IPL 2025, RCB topped the league stage — verify via curl.

No intl twin — ICC events don't have a points table at the dossier
level (group stages do, but they're per-group and visible inside
the Editions tab).

### 3c-5: `cross_cutting_team_class_consistency.sh`

The keystone test. Asserts a single number — Australia's match count
in men_intl 2024-25 + team_class=full_member — renders identically
across four surfaces:

```bash
1. /teams?team=Australia&...&team_class=full_member&tab=Match+List
   → DataTable total_rows = 16
2. /teams?team=Australia&...&team_class=full_member&tab=Compare
   → Compare-grid Australia col matches_text = "16"
3. /head-to-head?mode=team&team1=Australia&team2=India&...&team_class=full_member
   → "1 match" (or 0 — verify) in the rivalry overview
4. /series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&...&team_class=full_member&tab=Matches
   → DataTable of WC matches × FM filter
```

Implementation: navigate each URL in sequence, extract the relevant
number via the appropriate extractor, assert all four agree.

This catches the bug class where one tab's filter wiring diverges
from another's (e.g. team_class auto-clear effect fires too
aggressively, OR a tab forgets to pass `team_class` into a
sub-fetch). Same shape as the curl matrix in
`spec-filterbar-team-class-v3.md` §5.4 but DOM-side.

### 3c — commit cadence

- Commit 1: series_overview_intl_bilateral
- Commit 2: series_champions_intl + series_knockouts_intl
- Commit 3: series_points_club
- Commit 4: cross_cutting_team_class_consistency

Total: 4 commits, 5 scripts.

---

## End-of-Batch-3 wrap commit

After 3c finishes, one more docs-only commit:

```
tests/integration/dom: Batch 3 wrap — full dom/ inventory complete
```

Touches:
- `internal_docs/spec-dom-grounded-tests.md` — flip Batch 3 status to ✅
- `internal_docs/spec-dom-tests-series-teams.md` — same
- `internal_docs/enhancements-roadmap.md` — Batch 3 day log
- `tests/integration/dom/README.md` — final inventory table
- Memory `project_next_session.md` — point at next thing
  (slot-override-chip-alignment spec, the only build-ready item left)

---

## Estimated effort

| Sub-batch | Scripts | Harness | Commits | Time |
|---|---|---|---|---|
| 3a | 6 | 0 | 3 | ~1h |
| 3b | 12 | 1 | 6 | ~3-4h |
| 3c | 5 | 0 | 4 | ~1h |
| Wrap | — | — | 1 | ~15m |
| **Total** | **23** | **1** | **14** | **~5-6h** |

Splittable across 1-3 sessions. Best stopping points: end of 3a (Teams
chapter closed), end of 3b (Series sub-tabs done — biggest milestone),
end of 3c (spec complete).

---

## Pre-flight questions to settle before starting

These weren't fully verified in this spec — settle via curl in the
opening minutes of each sub-batch:

**For 3a:**
- `teams_vs_opponent` endpoint shape — is it `/api/v1/teams/{team}/vs/{opp}`?
  The probe in this session returned `{team, opponent, overall, by_season,
  matches}` — confirmed.
- `teams_players` endpoint path — is it `/players?team=X&...` or a
  team-scoped route? Find it.

**For 3b:**
- Series Editions: confirmed `/series/by-season` (not /series/editions).
- Series Batters/Bowlers/Fielders/Partnerships: confirmed leader endpoints.
- Series Matches: probably `/api/v1/matches?event_name=X&...` — verify.

**For 3c:**
- Champions endpoint: there is NO `/series/champions` endpoint — the
  data lives in `/series/summary`'s `champions_by_season` field.
- Knockouts endpoint: same — lives in `/series/summary`'s `knockouts`
  field.
- Points endpoint: `/series/points-table` returns `{canonical, season,
  tables}` — verified.
- Cross-cutting consistency: confirm that all four surfaces accept
  `team_class=full_member` as a query param BEFORE writing the
  assertions. If one doesn't, mention it as a bug + skip that surface
  in the assertion (don't silently let the test pass).

---

## What's deferred PAST Batch 3

- **Chart-DOM extractor.** Several tabs render Semiotic charts (bar/
  line) with numeric labels. We've consistently said "deferred to
  Batch 3" but realistically it's Batch 4 — the SVG-walking is more
  fragile than DOM-text extraction and deserves its own session.
- **Players standalone page** (`/players?player=X`) — the per-person
  card stack. Same DOM primitives as Teams sub-tabs (StatCard grids)
  so it's mechanical, but a new entity type.
- **Matches scorecard page** (`/matches/{id}`) — the per-match deep
  dive. Many tables, charts, and the worm/innings grid. Significant
  surface; worth its own session.
- **Venues sub-tabs** (per-venue dossier) — analogous to Series sub-
  tabs but venue-scoped.

These together would be Batch 4-6. Out of scope for the
spec-dom-tests-series-teams.md file but logged here for continuity.
