# Spec — DOM-tests Batch 4 (Players / Venues / Matches scorecard / charts)

> **Status:** build-ready 2026-04-29. Picks up after Batch 3 ship
> (`d7984e1`). Out-of-scope of `spec-dom-tests-series-teams.md` —
> covers the surfaces deferred PAST that spec.

Total dom/ suite at start of Batch 4: 41 scripts, ~720 assertions.
Target at end of Batch 4: ~63 scripts, ~1100 assertions, every
top-level page and major sub-tab covered.

---

## What this batch closes

The previous spec covered Series + Teams. The remaining top-level
surfaces are:

- **Players standalone page** (`/players?player=X` / `?compare=Y,Z`)
  — per-person profile with discipline bands + 2/3-way compare.
- **Venues sub-tabs** (`/venues?venue=X`) — VenueDossier with
  Overview / Batters / Bowlers / Fielders / Matches / Records
  tabs. Same shape as Series sub-tabs (TournamentDossier).
- **Matches scorecard** (`/matches/:matchId`) — per-match view with
  innings tables + worm/manhattan/grid charts + matchup grid.
- **Chart-DOM extractor** — Semiotic SVG numeric labels.

Sub-batches:

| Sub-batch | Coverage | Scripts | Time | Risk |
|---|---|---|---|---|
| **4a** | Players landing + single + compare (men + women) | 7 | ~1.5h | Low |
| **4b** | Venues sub-tabs (closely mirrors Series) | 8 | ~2h | Low |
| **4c** | Matches scorecard (no charts) | 3 | ~1h | Medium |
| **4d** | Chart-DOM extractor + chart-bearing assertions | 1 ext + 4 | ~3h | High |

Recommended order: 4a → 4b → 4c → 4d. 4d is its own session;
fragile and lower priority. Each prior sub-batch is self-contained.

---

## Pre-flight (start of any sub-batch)

```bash
# Confirm Batch 3 still green
for s in tests/integration/dom/teams_*.sh \
         tests/integration/dom/series_*.sh \
         tests/integration/dom/cross_cutting_*.sh; do
  $s 2>&1 | grep -E "PASS$|FAIL$" | tail -1
done
# Should print 41 PASS lines.

# Confirm dev servers + DB
lsof -ti:8000     # uvicorn --reload
lsof -ti:5173     # vite
ls -lh cricket.db
```

If any Batch 3 script fails: investigate before adding new scripts.

---

## Harness conventions (carried from Batch 3)

Every Batch 4 script follows the same rules. Don't relax these.

1. **Closed-window anchors** — `season_from=2024&season_to=2025`
   (intl) or `season_from=2025&season_to=2025` (IPL 2025) so values
   stay stable.
2. **+4s soak on multi-fetch tabs** — Compare grids, dossier
   sub-tabs, scorecard with charts. Default 3s isn't enough.
3. **Independent SQL ground truth** — every script cites
   `audit/<name>.sql` derived from cricket.db, NOT from `api/` source.
4. **Multi-table pages use ordinal arg** — `extract_data_table 0|1|2`
   (added in Batch 3b).
5. **Custom inline extractors are fine** for non-DataTable shapes
   (e.g. PlayerProfile bands, scorecard tables-with-special-classes).
   Don't expand `_lib.sh` for one-off shapes.
6. **fieldingcredit.kind uses underscores** — `'caught'`,
   `'stumped'`, `'run_out'`, `'caught_and_bowled'`. See
   `internal_docs/how-stats-calculated.md`.
7. **Partnership exclusions**:
   - `/series/partnerships/by-wicket` excludes `retired hurt` /
     `retired not out` AND requires `wicket_number IS NOT NULL`.
   - `/series/partnerships/top` has NEITHER filter.

---

## 4a — Players standalone (4 scripts, ~1h)

`/players` mounts three modes per `frontend/src/pages/Players.tsx`:

1. **Landing** (`/players` no params) — `PlayersLanding` renders 2
   curated tile sections (popular profiles + popular comparisons)
   with hard-coded person IDs from `components/players/CuratedLists.ts`.
2. **Single profile** (`?player=X`) — `PlayerProfile` shows
   discipline bands (batting / bowling / fielding / keeping). Each
   band is a StatCard row with optional chip envelopes.
3. **Compare** (`?player=X&compare=Y[,Z]`) — `PlayerCompareGrid`
   renders 2-3 column grid; same shape as Teams Compare.

### 4a-1: `players_landing.sh`

```bash
URL: /players (no params; uses default filters)
Extractor: extract_landing_tiles
Tile assertions: profiles + compare tiles from CuratedLists.ts.
                 Each tile carries either a person identity (single)
                 or a "vs" label (compare).
Audit: audit/players_landing.sql — confirm each curated person_id
       has activity (matches > 0) so the tile renders.
```

### 4a-2: `players_single_intl.sh`

Anchor: V Kohli (`ba607b88`), men_intl 2024-25.

```bash
URL: /players?player=ba607b88&gender=male&team_type=international&season_from=2024&season_to=2025
Endpoint: /api/v1/players/ba607b88/profile?...
DOM: PlayerProfile bands — batting (matches/runs/avg/SR), bowling
     (might be empty for specialist), fielding (catches/RO),
     keeping (likely empty).
Extractor: custom inline (walks each .wisden-player-section's
           StatCards). Mirror series_overview's extract_team_overview
           but iterate sections.
Audit: audit/players_single_intl.sql — direct SUM/COUNT on delivery
       + fieldingcredit for Kohli in scope.
```

### 4a-3: `players_single_club.sh`

Anchor: B Sai Sudharsan (`d5130a30`), IPL 2025 (Orange Cap holder).

```bash
URL: /players?player=d5130a30&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025
Audit: audit/players_single_club.sql — Sudharsan 759r/486b/SR 156.17
       (already verified in series_batters_club.sh).
```

### 4a-4: `players_compare_intl.sh`

Anchor: Kohli vs Sharma (`ba607b88`, `81f5d6dc`) men_intl 2024-25.
2-way compare.

```bash
URL: /players?player=ba607b88&compare=81f5d6dc&...
Extractor: extract_grid (already exists from Teams Compare).
Audit: audit/players_compare_intl.sql — both columns' batting
       totals + averages. Math invariant on chip envelopes
       (delta = (value − avg) / avg × 100 ± EPS_PCT).
```

**Skip 3-way compare** — adds combinatorial coverage with no new
DOM mechanism. The 2-way anchor exercises everything 3-way does.

### 4a-5: `players_landing_women.sh`

Women variant of `players_landing.sh`. CuratedLists.ts maintains a
parallel `PROFILE_WOMEN` (9 tiles) + `COMPARE_WOMEN` (3 pairs)
bank, gated on `?gender=female`. NOT optional — any UI bug
affecting the women landing specifically would otherwise ship
undetected.

```bash
URL: /players?gender=female
Extractor: same custom extractor as players_landing.sh
Audit: audit/players_landing_women.sql — confirm each curated
       women ID exists + has match activity.
Note: "D Sharma" curated label vs "DB Sharma" person.name in DB —
      the tile renders the curated label, audit calls this out.
```

### 4a-6: `players_single_intl_women.sh`

Anchor: S Mandhana (`5d2eda89`), women_intl 2024-25. Same shape
as `players_single_intl.sh` (specialist batter; BATTING + FIELDING
bands; no BOWLING / KEEPING).

### 4a-7: `players_compare_intl_women.sh`

Anchor: Mandhana × Mooney (`5d2eda89` × `52d1dbc8`), women_intl
2024-25 — the first `COMPARE_WOMEN` pair. Picked over Perry × Knight
because Mooney is a keeper-batter (her column carries a KEEPING
band) while Mandhana isn't — exercises the empty-section
placeholder behavior for row alignment across columns.

### 4a — commit cadence

- Commit 1: players_landing + players_single_intl + players_single_club (3 scripts)
- Commit 2: players_compare_intl (1 script)
- Commit 3: women anchors (3 scripts: landing + single + compare)

Total: 3 commits, 7 scripts, ~170 assertions.

---

## 4b — Venues sub-tabs (8 scripts, ~2h)

`VenueDossier` mirrors `TournamentDossier` exactly:
`['Overview', 'Batters', 'Bowlers', 'Fielders', 'Matches', 'Records']`.

Backed by `/api/v1/venues/{venue}/summary` for the Overview band +
the existing leaders/matches/records endpoints with `filter_venue=X`
appended.

### Anchors

- **INTL anchor:** Eden Gardens (Kolkata), men_intl all-time.
  Eden has hosted multiple T20Is, ICC events, and bilateral. Rich
  payload across every sub-tab.
- **CLUB anchor:** Wankhede Stadium (Mumbai), IPL 2025. Wankhede
  is MI's home — heavy IPL match volume + a marquee "highest total"
  history.

### 4b-1: `venues_overview_intl.sh` + 4b-2: `venues_overview_club.sh`

```bash
INTL: /venues?venue=Eden+Gardens&gender=male&team_type=international
CLUB: /venues?venue=Wankhede+Stadium&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025
Endpoint: /api/v1/venues/Eden%20Gardens/summary?...
DOM: StatCard band (matches, avg 1st-inn total, bat-first win %,
     toss decision split, boundary % per phase).
Extractor: extract_team_overview (StatCard band)
Audit: audit/venues_overview_{intl,club}.sql — bat-first vs chase
       win counts, avg first innings total per match.
```

### 4b-3: `venues_batters_intl.sh` + 4b-4: `venues_batters_club.sh`

Reuses `/batters/leaders` with `filter_venue=X`. Same shape as
`series_batters_*.sh` — 3 DataTables (by_runs / by_average /
by_strike_rate).

```bash
INTL: Eden Gardens — top run-scorer in T20Is at Eden (history).
CLUB: Wankhede Stadium — IPL 2025 top run-scorer at Wankhede.
Extractor: extract_data_table 0|1|2 (ordinal arg)
Audit: audit/venues_batters_{intl,club}.sql — venue-filtered
       SUM(runs_batter) GROUP BY batter_id.
```

### 4b-5: `venues_bowlers_club.sh` + 4b-6: `venues_fielders_club.sh`

Single-anchor (club only) for bowlers + fielders. The intl twins
add little marginal coverage — same code path as Series
leaderboards exercised in Batch 3b. Skip them unless a venue-
specific bug is suspected.

```bash
Wankhede IPL 2025: top wicket-taker, top fielder by dismissals
Audit: audit/venues_{bowlers,fielders}_club.sql
```

### 4b-7: `venues_matches_club.sh`

```bash
URL: /venues?venue=Wankhede+Stadium&...&tab=Matches
DOM: Match list, single DataTable, paginated.
     ~7-9 matches at Wankhede in IPL 2025 (MI home + DC home shared).
Extractor: extract_data_table
Audit: audit/venues_matches_club.sql — matches WHERE venue
       canonical = 'Wankhede Stadium' AND season=2025.
```

### 4b-8: `venues_records_intl.sh`

```bash
URL: /venues?venue=Eden+Gardens&...&tab=Records
DOM: Multi-DataTable (highest team totals, lowest, best individual
     batting, best bowling figures). Same as series_records.
Extractor: extract_data_table 0..N
Audit: audit/venues_records_intl.sql — covers each Records sub-table.
```

### 4b — commit cadence

- Commit 1: venues_overview pair (2 scripts)
- Commit 2: venues_batters pair (2 scripts)
- Commit 3: venues_bowlers_club + venues_fielders_club + venues_matches_club (3 scripts)
- Commit 4: venues_records_intl (1 script)

Total: 4 commits, 8 scripts, ~150 assertions.

---

## 4c — Matches scorecard (3 scripts, ~1h)

`/matches/:matchId` renders:

1. Match header (toss, result, MoM).
2. WormChart + ManhattanChart (charts — see 4d).
3. One InningsCard per innings, each containing:
   - Batting table (DataTable: batter, dismissal, runs, balls, 4s,
     6s, SR).
   - Bowling table (DataTable: bowler, overs, maidens, runs, wkts,
     econ).
   - Extras line, total line.
   - InningsGridChart (ball-by-ball; 4d).
   - MatchupGridChart (batter × bowler — only if 2-innings match).

Per CLAUDE.md "Scorecard highlight auto-scroll", URLs may carry
`?highlight_batter=X` / `?highlight_bowler=X` / `?highlight_fielder=X`
which tints the matching row green.

### 4c-1: `matches_scorecard_intl.sh`

Anchor: T20 WC 2024 Final (`match_id=1551`, India v South Africa
on 2024-06-29). Two innings, full payload, India won by 7 runs.

```bash
URL: /matches/1551
Endpoint: /api/v1/matches/1551 (returns nested innings with batting
          + bowling rows)
DOM:
  Header: Match title + result line.
  Innings 1 (India batting): top scorer = V Kohli 76 (59).
                              Top bowler vs India = Maharaj 2/23.
  Innings 2 (SA batting):    top scorer = H Klaasen 52 (27).
                              Top bowler vs SA = Pandya 3/20.
Extractor: custom inline — walk InningsCard sections, extract
           batting + bowling table rows.
Audit: audit/matches_scorecard_intl.sql — pin top-3 batters per
       innings + top-3 bowlers per innings + total runs per innings.
```

### 4c-2: `matches_scorecard_club.sh`

Anchor: IPL 2025 Final (`match_id=6018`, RCB v PBKS on 2025-06-03).
RCB won by 6 runs — the famous low-scoring final.

```bash
URL: /matches/6018
Audit: audit/matches_scorecard_club.sql — pin RCB innings (190/9
       in 20.0) + PBKS innings (184/7 in 20.0).
```

### 4c-3: `matches_scorecard_highlight.sh`

The auto-scroll behavior has a known gotcha (MatchScorecard.tsx:35
notes "Doing this per-InningsCard fired the scroll before the
async InningsGridChart + MatchupGridChart siblings had…"). This
script asserts:

```bash
URL: /matches/1551?highlight_batter=ba607b88
DOM: The Kohli row in Innings 1 has class .is-highlighted.
     scrollY > 0 (the page auto-scrolled to him).
Extractor: custom inline — find tr.is-highlighted, return its
           cell text + window.scrollY.
Audit: N/A — this is purely a DOM-behavior assertion (CSS class +
       scroll-occurred). Document the test rationale in the script
       header instead.
```

Sibling assertions for `highlight_bowler` and `highlight_fielder`
within the same script — three navigations, three assertions, no
new audit.

### 4c — commit cadence

- Commit 1: matches_scorecard_intl + matches_scorecard_club (2 scripts)
- Commit 2: matches_scorecard_highlight (1 script)

Total: 2 commits, 3 scripts, ~80 assertions.

---

## 4d — Chart-DOM extractor (own session — fragile, ~3h)

**Skip 4d on first pass through Batch 4.** Charts are fragile:
Semiotic positions text labels via CSS transforms which can vary
with axis scale, font-rendering, viewport width. Asserting numeric
labels means accepting brittleness.

If/when 4d is built, scope:

### Harness extension: `extract_chart_labels`

```bash
extract_chart_labels <selector> <label-class>
  → returns [{text, x, y}] for every text label inside the SVG.
```

For Semiotic SVGs in cricsdb the canonical selector is
`.semiotic-frame text` plus a more-specific narrowing per chart
type. WormChart labels are `<text>` siblings of `<path>`;
ManhattanChart uses `text.bar-label`; etc.

### Candidate scripts (decide during 4d session)

- `worm_chart_intl.sh` — WC 2024 Final worm: India peak run
  rate around over 12, SA chase fell short at over 18.
- `manhattan_chart_intl.sh` — same match, per-over runs.
- `innings_grid_chart_club.sh` — IPL 2025 Final ball-by-ball grid
  numeric labels.
- `matchup_grid_chart_intl.sh` — WC 2024 Final batter × bowler.

Each script asserts a HANDFUL of high-signal labels (peak total,
final total, key batter's score) — NOT every label. The fragility
budget is ~5-10 labels per script.

### Why 4d is its own session

- Selector engineering takes time per chart type.
- Browser version drift can move labels by 1-2 pixels, breaking
  position-based extractors. We need text-content-based extractors
  (find label by text, NOT by position).
- Chart bugs are worth catching but the test cost is high — DOM
  text assertions in 4a-4c already exercise the underlying API,
  so chart numeric assertions are second-order coverage.

### 4d — commit cadence (when shipped)

- Commit 1: extract_chart_labels harness extension (standalone)
- Commit 2-N: one commit per chart pair.

Total (estimate): 5 commits, 4 scripts + 1 extension.

---

## End-of-Batch-4 wrap commit (after 4a + 4b + 4c)

```
tests/integration/dom: Batch 4 wrap — Players + Venues + Matches scorecard
```

Touches:
- `internal_docs/spec-dom-grounded-tests.md` — flip Batch 4 status
  to ✅ partial (4a/b/c shipped, 4d deferred) OR ✅ complete if 4d
  shipped too.
- `internal_docs/enhancements-roadmap.md` — Batch 4 day-log entry.
- `tests/integration/dom/README.md` — extend the inventory table.
- Memory `project_next_session.md` — point at the next thing
  (slot-override-chip-alignment or 4d).

---

## Estimated effort

| Sub-batch | Scripts | Harness | Commits | Time |
|---|---|---|---|---|
| 4a | 7 | 0 | 3 | ~1.5h |
| 4b | 8 | 0 | 4 | ~2h |
| 4c | 3 | 0 | 2 | ~1h |
| Wrap | — | — | 1 | ~15m |
| **Subtotal (4a+4b+4c)** | **18** | **0** | **10** | **~5h** |
| 4d (optional, own session) | 4 | 1 | 5 | ~3h |
| **Total (with 4d)** | **22** | **1** | **15** | **~8h** |

Splittable across 1-3 sessions. Best stopping points: end of 4a
(Players covered), end of 4b (Venues covered), end of 4c
(scorecard covered, 4d deferred).

---

## Pre-flight questions to settle before starting

These need an opening-minutes curl probe; don't trust the spec's
sketch values without verifying against the running API.

**For 4a:**
- Confirm `getPlayerProfile` response shape — discipline bands +
  scoped fields. The compare grid extractor reuses `extract_grid`
  but the column header selector may differ from
  `.wisden-compare-col` if PlayerCompareGrid uses a different class.
  Probe the DOM: `agent-browser eval` for the page's column
  selectors.
- Confirm `CuratedLists.ts` person IDs are still valid (no
  retroactive cricsheet ID changes).

**For 4b:**
- Confirm Eden Gardens canonical name + Wankhede Stadium canonical
  name in `venue` column. Per CLAUDE.md "Venue canonical names
  never carry trailing `, <City>` suffix", but parens-style
  disambiguators (`County Ground (Taunton)`) stay.
- Confirm the venue dossier endpoint shape — `/venues/{venue}/summary`.

**For 4c:**
- Confirm `match_id=1551` is the WC 2024 Final + `match_id=6018`
  is the IPL 2025 Final via curl.
- Confirm scorecard endpoint shape — single nested `innings[]` or
  flat list.
- Confirm `.is-highlighted` class is applied at the row level (not
  cell) and survives the React rerender after page-level scroll
  fires (per `MatchScorecard.tsx:35` workaround).

**For 4d (later):**
- Audit which chart components use stable text-content vs
  position-only labels. Charts with named axis ticks are easier;
  charts with raw `<text>` SVG nodes need text-content fingerprints.

---

## What's deferred PAST Batch 4

After 4a+4b+4c+4d:

- **Batting / Bowling / Fielding standalone pages**
  (`/batting`, `/bowling`, `/fielding`) — these are top-level
  routes too. Same shape as Players (per-person discipline view)
  but scoped to one discipline at a time. Skipped here because
  Players already exercises the underlying endpoints; the
  routing is the only thing not covered.
- **Help / About / Tweet-thread renders** — markdown-rendered
  pages. No numeric assertions; smoke-test only.
- **404 / empty-state coverage** — invalid match ID, unknown
  venue, etc. Lower priority than positive-path coverage.
- **Mobile viewport** — agent-browser supports viewport sizing
  but DOM assertions should be viewport-agnostic. Mobile-only
  bugs (responsive collapse, touch targets) are visual and need
  a different testing pass.

These together would be Batch 5+. Out of scope for this spec but
logged here for continuity.
