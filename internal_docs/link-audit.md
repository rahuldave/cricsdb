# CricsDB Frontend Link Audit

**Date:** April 20, 2026  
**Scope:** Complete clickable affordances across all main tabs and subtabs  
**Version:** Comprehensive reference

## How to Read This Audit

This document maps every clickable link across the CricsDB frontend by page and subtab. Three **scope sources** feed link destinations:

1. **Ambient FilterBar** (`useFilters()` / `useScopeFilters()`): Global filters (gender, team_type, tournament, season_from/to, filter_team, filter_opponent, filter_venue, series_type) set by the top bar and ride through every non-override link.

2. **Row-specific override** (`SubscriptSource` in `scopeLinks.ts`): Tables/lists pass per-row scope (tournament, season, team1/team2) to links so the scope matches the row's data, not the page's ambient filter. This is the **primary mechanism for (ed) subscript tokens** — the link URL is narrow (edition-scoped) while wider phrase tiers are offered as clickable alternatives.

3. **Curated / hard-coded**: Landing-page tiles, Featured players, and seeded lists embed scope directly (no FilterBar dependency). These links are predictable across sessions.

## Conventions Checklist

The following patterns should be consistent throughout:

- **(a) Team-name cells in row-specific tables** → Use `TeamLink` with per-row `subscriptSource` for (ed) token. Never raw `<Link>`.
- **(b) Date cells identifying a match** → Link to `/matches/:id`. Use the `matchLink()` helper where available.
- **(c) Score cells** → Use `<Score matchId={...}>` component (if linked) or plain text.
- **(d) Tournament cells for single edition** → Link to `/series?tournament=X&season_from=Y&season_to=Y`. Ideally via `SeriesLink()`.
- **(e) Rivalry / H2H links** → Carry filter_team + filter_opponent through the URL.
- **(f) Breadcrumbs** → Always include a back-to-parent link (e.g., "← All venues" on venue dossier).

## Verification status

- **Series tab** (TournamentsLanding.tsx + TournamentDossier.tsx): re-audited 2026-04-21 post-refactor. All line citations in the Series section below match the current code.
- **Every other tab** (Teams, Players, Batting/Bowling/Fielding, Head-to-Head, Venues, Matches, Scorecard, Home): **NOT re-audited yet.** Treat those sections as stale until re-verified. Some pre-refactor deviations flagged there may still apply; others may have been superseded by the `phraseLabel` + `subscriptSource` pattern now documented in `internal_docs/links.md`.

## Known deviations outside the Series tab

Quick spot-check from grep — NOT a full audit, but these are the same patterns that were refactored out of the Series tab and would likely fail a similar review:

- **Home.tsx:20–87** defines local `TeamLink` and `PlayerLink` components that shadow the real ones from `components/`. They're raw `<Link>`s with hand-rolled URL building — no `subscriptSource`, no phrase subscripts, and (for `TeamLink`) they invert the "name = all-time" contract by appending tournament/season to the name URL. Rename or replace.
- **venues/VenueDossier.tsx:38–40 + VenueOverviewPanel.tsx:14** define a `teamLink()` helper that renders raw `<Link to="/teams?team=X">`. Used 10+ times across both files' Records tables and Overview summary lines (where the Series tab now uses `TeamWithEd` → `TeamLink` with `phraseLabel="ed"`). Same pattern as the pre-refactor Series dossier; same fix applies.
- **venues/VenueDossier.tsx:598–622** — `Largest partnerships` batter pair and `Best bowling figures` bowler cell use `PlayerLink` but without a `subscriptSource`, so they don't get the per-row (ed) phrase the Series Records tab now carries.
- **Batting.tsx:140–143, 158–159 / Bowling.tsx:125–127, 142–143 / Fielding.tsx:153–155, 168–170, 195–197** — innings-list Opponent columns and Matchup bowler/batter columns use raw `<Link>` for team and player cells. The Tournament column on the same tables already uses `SeriesLink` correctly; the team and player columns haven't caught up.
- **Batting.tsx:507 / Bowling.tsx:491 / Fielding.tsx:487, 523** — leaderboard player cells on the landing boards use raw `<Link>` via a local `playerLink()` URL helper, not `PlayerLink`.
- **Teams.tsx:216, 755 / 1051–1054, 1083–1086, 1178–1188 / 1289–1296** — keepers list, partnerships best-pair batter cells, top-10 partnerships batter cells, and Players-tab roster names all use raw `<Link>`. Should be `PlayerLink` with a per-row `subscriptSource` (for partnerships) or `compact` (for the roster).
- **Teams.tsx match-list columns** (lines 135–139) — Opponent, Venue, Tournament, Result render as plain text. The convention in `internal_docs/links.md` calls for TeamLink / venue link / SeriesLink respectively. (Date at line 131 is correct — match-id destination, plain `<Link>`.)

None of these were touched in this session's Series-tab refactor. Flagging them here so a future session can use `internal_docs/links.md` as the contract and clean them up in one pass (or per-page as each tab gets its turn).

---

# Main Tabs & Subtabs

## Series (`/series`) — Tournaments / Matches

> **Re-audit 2026-04-21, post-refactor.** The B1/B2 intentional inversions and the C1–C5 deviations flagged in the pre-refactor pass are all gone. `teamUrl`, `teamLinkHref`, `renderBatter`, `renderBatterPair`, and `renderVsTeams` have been deleted. Every team or player cell on the Series tab now routes through `TeamLink` / `PlayerLink` / `SeriesLink`, with `phraseLabel` + `subscriptSource` carrying per-row scope. Browser-verified against a live dev server before commit.
>
> Line citations below match the current files: `TournamentsLanding.tsx` (519 lines) and `TournamentDossier.tsx` (2161 lines).

### Helpers in TournamentDossier.tsx

Only two local helpers survive; the rest are real components.

| Helper | Lines | Purpose |
|---|---|---|
| `matchLink(matchId, label)` | 44–46 | Plain `<Link to="/matches/:id">`. Match-id destination, no phrase model. |
| `partnershipMatchLink(matchId, label, id1, id2)` | 48–58 | Plain `<Link>` to `/matches/:id?highlight_batter=id1,id2`. |
| `TeamWithEd({team, row, gender, team_type})` | 73–95 | Thin `TeamLink` wrapper with `phraseLabel="ed"`, `phraseClassName="scope-phrase-ed"`, `maxTiers={1}`, and a per-row `{tournament, season, team1: null, team2: null}` subscriptSource. The team1/team2 nulls explicitly drop any ambient rivalry pair so the (ed) link goes to the single team at that edition (see comment at lines 60–72). |

No `teamUrl` / `teamLinkHref` / `renderBatter` / `renderBatterPair` / `renderVsTeams` anymore — they were deleted when their last callers migrated.

---

### Landing View (`/series`)
**File:** `src/components/tournaments/TournamentsLanding.tsx` (519 lines)

#### `TournamentTile` (lines 35–121)

| Line(s) | Affordance | Component | Destination |
|---|---|---|---|
| 45–56 | Tile primary (stretched click area) | **`SeriesLink`** | `/series?tournament=X&…` |
| 67–74 | "Most titles: `<Team>`" — single title | **`TeamLink compact`** | `/teams?team=X` (all-time) |
| 76–86 | "Most titles: `<Team>` (N)" — titles > 1 | **`TeamLink`** with `subscriptSource={tournament}`, `maxTiers={1}`, `phraseLabel="(N)"` | Name → all-time; (N) → `/teams?team=X&tournament=T` |
| 89–97 | "Latest: `<Season>`" | **`SeriesLink`** | `/series?tournament=X&season_from=S&season_to=S` |
| 103–115 | "Winner: `<Team>` (ed)" | **`TeamLink`** with `subscriptSource={tournament, season}`, `phraseLabel="ed"`, `phraseClassName="scope-phrase-ed"` | Name → all-time; (ed) → scoped to the edition |

The "Winner" / "Most titles" inversion documented in the previous audit pass is gone. Name links go all-time (the "escape"); the bracketed count or (ed) phrase is the scoped link, matching the standard convention.

#### `RivalryTile` (lines 123–211)

| Line(s) | Affordance | Component | Destination |
|---|---|---|---|
| 135–147 | Tile primary (stretched click area) | **`SeriesLink`** | `/series?team1=A&team2=B&seriesType=all&…` |
| 169–181 | "Latest: `<season> bilateral` / `<Tournament> <Season>`" | **`SeriesLink`** | Scoped edition URL |
| 186–209 | "Winner: `<Team>` (ed)" | **`TeamLink`** with `keepRivalry`, `seriesType`, `subscriptSource={tournament, season, team1, team2}`, `phraseLabel="ed"` | Name → all-time; (ed) → edition + rivalry |

No raw `<Link>` remaining on either tile type.

---

### Dossier View (`/series?tournament=X` **or** `/series?filter_team=A&filter_opponent=B`)
**File:** `src/components/tournaments/TournamentDossier.tsx`

Tabs (BASE_TABS at line 115): Overview · Editions · Batters · Bowlers · Fielders · Partnerships · Records · Matches. Points is inserted dynamically between Editions and Batters when a single season is in scope.

---

#### Overview tab — `OverviewTab()` lines 520–1235

**Top StatCards — "Most titles / Top scorer / Top wicket-taker"** (640–725)

| Line(s) | Affordance | Component |
|---|---|---|
| 654 | Most titles — team name | **`TeamLink compact`** |
| 662 | …scope-phrase chain after title count | Raw `<Link>` via local `phraseLinks()` helper (569–594) — composes phrase tiers manually for the StatCard subtitle |
| 673–680 | Top scorer — player name, rivalry-oriented | **`PlayerLink compact`** with `orientedSource()` (553–558) |
| 688–690 | Top scorer — phrase chain to `/batting?player=…` | Raw `<Link>` via `phraseLinks()` |
| 701–708 | Top wicket-taker — player name | **`PlayerLink compact`** |
| 716–718 | Top wicket-taker — phrase chain | Raw `<Link>` via `phraseLinks()` |

The raw `<Link>`s in `phraseLinks()` are the only place on the dossier where tier phrases are rendered outside `PlayerLink`/`TeamLink`. The StatCard subtitle composes tiers manually because it needs an inline comma-separated list ("759 runs · at IPL, 2024, at IPL") that doesn't fit the component's trailing-subscript layout. Acceptable — the URL shape still flows through the shared `resolveBucket` / `resolveScopePhrases` pipeline.

**Best moments prose block** (733–855)

| Line(s) | Affordance | Component |
|---|---|---|
| 742–760 | Best batting — name + stat + match date | **`PlayerLink`** + `matchLink()` |
| 762–780 | Best bowling — name + figures + date | **`PlayerLink`** + `matchLink()` |
| 785–804 | Highest partnership — two batter names | **`PlayerLink compact`** × 2 |
| 806 | Partnership date | `matchLink()` |
| 811 | Partnership scope phrases | Raw `<Link>` via `phraseLinks()` |
| 816–833 | Best fielding — name + dismissals + date | **`PlayerLink`** + `matchLink()` |
| 839, 841 | Highest total — team + opponent | **`TeamLink compact`** × 2 |
| 844 | Highest-total date | `matchLink()` |
| 849 | Highest-total scope phrases | Raw `<Link>` via `phraseLinks()` |

**Rivalry-mode by-team tiles** (lines 885–976, only when `summary.by_team` is present)

| Line(s) | Affordance | Component |
|---|---|---|
| 895–904 | Tile title — team name | **`TeamLink`** with `keepRivalry` and rivalry-oriented `subscriptSource` (was a raw `<Link>` via `teamLinkHref` — now fixed) |
| 911–918 | Top scorer | **`PlayerLink`** |
| 923–931 | Top wicket-taker | **`PlayerLink`** |
| 936–944 | Highest individual | **`PlayerLink`** |
| 947 | Individual-score date | `matchLink()` |
| 953–966 | Largest partnership — two batters | **`PlayerLink`** × 2 |

**Groups section** (lines 985–1010, single-edition tournaments only)

| Line(s) | Affordance | Component |
|---|---|---|
| 995–1002 | Team name + "`N` m" scoped match-count | **`TeamLink`** with `subscriptSource={tournament, season}`, `maxTiers={1}`, `phraseLabel={`${t.matches} m`}` |

Name → all-time; "N m" phrase → scoped to tournament + single season.

**Knockouts table** (lines 1013–1108)

| Line(s) | Column | Component |
|---|---|---|
| 1030–1037 | Edition — only shown if multi-tournament dossier | **`SeriesLink`** |
| 1046, 1048 | Match cell — team1, team2 with (ed) | **`TeamWithEd`** × 2 → `TeamLink` with phraseLabel="ed" |
| 1057–1062 | Winner — team name | **`TeamLink compact`** (with `(margin)` plain text after) |
| 1072 | Venue | Raw `<Link to="/venues?venue=V">` |
| 1087 | Date | Raw `<Link to="/matches/:id">` |
| 1093–1098 | Score | `<Score matchId=…>` |

**Participating teams chips** (lines 1118–1144, tournament-scope only)

| Line(s) | Affordance | Component |
|---|---|---|
| 1131–1138 | Team name + "(N)" scoped match-count | **`TeamLink`** with `subscriptSource={tournament}`, `maxTiers={1}`, `phraseLabel="(N)"` |

**Champions by season** (lines 1146–1223)

| Line(s) | Column | Component |
|---|---|---|
| 1157, 1163 | Final — team1, team2 with (ed) | **`TeamWithEd`** × 2 |
| 1174–1180 | Champion — team name | **`TeamLink compact`** (all-time) |
| 1191 | Date | Raw `<Link to="/matches/:id">` |
| 1195–1200 | Score | `<Score matchId=…>` |

---

#### Editions tab — `EditionsTab()` lines 1497–1611

| Line(s) | Column | Component |
|---|---|---|
| 1507–1513 | Season | `<button onClick={onPickSeason}>` — narrows page state in place, not a `<Link>` |
| 1515 | Matches | plain text |
| 1518–1532 | Champion | **`TeamLink`** with `subscriptSource={tournament, season}`, `maxTiers={1}`, `phraseLabel="(won/played)"`; falls back to `TeamLink compact` when `champion_record` is null |
| 1535–1550 | Runner-up | Same pattern as Champion |
| 1554–1565 | Top scorer | **`PlayerLink`** with edition subscriptSource, `phraseLabel="(runs)"` |
| 1567–1579 | Top wicket-taker | **`PlayerLink`** with edition subscriptSource, `phraseLabel="(wickets)"` |
| 1583–1599 | Final cell | `<Score>` if both scores present, else `matchLink()` to "scorecard →" |

All bracketed counts now ride the phrase pipeline. Name = all-time everywhere.

---

#### Points tab — `PointsTab()` lines 1613–1680

Rendered only when a single season is in scope (via `data.reason === 'multi_season'` early-return at lines 1628–1634).

| Line(s) | Column | Component |
|---|---|---|
| 1641–1652 | Team | **`TeamLink`** with `subscriptSource={tournament, season}`, `maxTiers={1}`, `phraseLabel="ed"` (was plain text — now fixed) |
| 1653–1663 | P / W / L / T / NR / Pts / NRR | plain text / numeric |

Team cells are now clickable with per-row (ed) phrase.

---

#### Batters / Bowlers / Fielders tabs — lines 1695–1908

Six side-by-side leaderboards (two per tab). Unchanged from the previous audit pass — they were already on `PlayerLink`.

| Line(s) | Leaderboard | Player cell | Stat columns |
|---|---|---|---|
| 1723–1726 | Batters by average | **`PlayerLink`** with `rowSrc` (rivalry-oriented via `rowSubscriptSource`, 1682–1693) | plain text |
| 1748–1751 | Batters by SR | **`PlayerLink`** | plain text |
| 1795–1798 | Bowlers by SR | **`PlayerLink`** | plain text |
| 1819–1822 | Bowlers by econ | **`PlayerLink`** | plain text |
| 1866–1869 | Fielders by total | **`PlayerLink`** | plain text |
| 1891–1894 | Fielders by keeper dismissals | **`PlayerLink`** | plain text |

No team column on any of these tables (row's team is read for rivalry orientation only).

---

#### Partnerships tab — `PartnershipsTab()` lines 1215–1393

Previously the biggest deviation on the dossier (two tables using raw-Link helpers). Now uses two local closure-helpers `batterPair()` (1229–1252) and `matchTeams()` (1253–1260) that compose `PlayerLink` × 2 and `TeamWithEd` × 2 respectively.

**By-wicket averages** (1292–1358)

| Line(s) | Column | Component |
|---|---|---|
| 1303–1305 | Wkt / N / Avg / Balls / Best | plain / numeric |
| 1320–1330 | Best stand — batter pair | `batterPair()` → **`PlayerLink compact`** × 2 with `subscriptSource={tournament, season, team1: batting_team, team2: opponent}` |
| 1332–1342 | Match — batting_team vs opponent | `matchTeams()` → **`TeamWithEd`** × 2 |
| 1344–1346 | Season | plain text (from row) |
| 1348–1357 | Date | `partnershipMatchLink()` with both batter IDs |

**Top partnerships** (1364–1392)

| Line(s) | Column | Component |
|---|---|---|
| 1370 | Runs | plain text |
| 1371 | Wkt | plain text |
| 1372–1380 | Batters — pair | `batterPair()` → **`PlayerLink compact`** × 2 |
| 1381–1389 | Match | `matchTeams()` → **`TeamWithEd`** × 2 (tournament = `r.tournament ?? dossierTournament`) |
| 1390 | Season | plain text |
| 1391–1395 | Date | `partnershipMatchLink()` |

`EdHelp` caption now mounts above each table (lines 1291, 1361).

---

#### Records tab — `RecordsTab()` lines 1910–2161

Eight tables. Team cells go through `teamCell()` (1926–1928) → `TeamWithEd` → `TeamLink` with `phraseLabel="ed"`. The two remaining player deviations (Largest partnerships batter pair, Best bowling bowler cell) have been fixed. New "Best individual batting" table mirrors Best bowling figures, shown as a sibling in the same grid.

| Line(s) | Table | Team cell | Player cell | Date cell |
|---|---|---|---|---|
| 1953–1974 | Highest team totals | `teamCell` | — | `matchLink()` |
| 1977–1998 | Lowest all-out totals | `teamCell` | — | `matchLink()` |
| 2001–2022 | Biggest wins by runs | `teamCell` × 2 (Winner + Loser) | — | `matchLink()` |
| 2025–2046 | Biggest wins by wickets | `teamCell` × 2 | — | `matchLink()` |
| 2049–2093 | Largest partnerships | Match = `teamCell` × 2 | **Batters = `PlayerLink compact` × 2** with per-row rivalry-oriented subscriptSource | `matchLink()` |
| 2102–2131 | Best individual batting | — | **Batter = `PlayerLink` with `subscriptSource={r.tournament, r.season}`, `phraseLabel="ed"`** | `matchLink()` |
| 2132–2160 | Best bowling figures | — | **Bowler = `PlayerLink` with `subscriptSource={r.tournament, r.season}`, `phraseLabel="ed"`** | `matchLink()` |
| 2162–2185 | Most sixes in a match | `teamCell` × 2 (team1 v team2) | — | `matchLink()` |

---

#### Matches tab — `MatchesTab()` lines 1395–1495

| Line(s) | Column | Component |
|---|---|---|
| 1418–1421 | Date | `matchLink()` |
| 1423 | Edition — hidden when a tournament is selected (`showTournamentCol = !tournament` at 1415); shown only on rivalry/unfiltered dossiers, as plain text | — |
| 1424 | Season | plain text |
| 1427–1433 | Match — team1 v team2 | **`TeamWithEd`** × 2 |
| 1436–1442 | Winner | **`TeamWithEd`**; falls back to `r.result_text` plain string when no winner (tie / no-result) |
| 1445–1448 | Score | `<Score matchId=…>` |
| 1451–1454 | Venue | Raw `<Link to="/venues?venue=V">` |
| 1469–1486 | Pagination | `<button>`s updating the `page` URL param |

---

### Links on the Series tab that are **not** `PlayerLink` / `TeamLink`

Post-refactor, these are the only categories left. All are legitimate.

**A. Match-id / venue / page destinations — no entity+scope model to apply**
- Every `matchLink()` and `partnershipMatchLink()` call (Overview best moments, Knockouts 1087, Champions 1191, Editions scorecard-arrow 1596, Records date columns, Partnerships dates, Matches date 1420).
- Every `<Score matchId=…>` cell (Knockouts, Champions, Editions final, Matches).
- Every Venue cell `<Link to="/venues?venue=V">`: Knockouts 1072, Matches 1453.
- Season "click-to-narrow" `<button>`s in Editions (1508–1513) and pagination `<button>`s in Matches (1472–1485).

**B. Phrase-tier composition outside the component**
- Overview StatCard subtitle chains (`phraseLinks()` helper, 569–594): raw `<Link>`s because the StatCard subtitle needs an inline comma-separated chain that doesn't fit `TeamLink`/`PlayerLink`'s trailing-subscript rendering. The URL shape still flows through shared `resolveBucket` / `resolveScopePhrases`. Used at lines 662, 688–690, 716–718, 811, 849.

**C. Plain-text cells (no link by design)**
- Numeric columns (runs, balls, SR, etc.) on every leaderboard and record table.
- Season columns in Editions, Partnerships, Champions — the season button in Editions is the click target; in other tables the date cell handles navigation.
- Edition column in Matches when a tournament is selected (hidden); when shown (rivalry/unfiltered), it's plain text — arguably upgradeable to `SeriesLink`, but low priority.

No remaining raw `<Link to="/teams…">` or `<Link to="/batting|bowling|fielding?player=…">` calls on the Series tab. Every team-name cell is a `TeamLink`, every player-name cell is a `PlayerLink`, every /series destination is a `SeriesLink`.

---

## Teams (`/teams`) — Team Dossier

**File:** `src/pages/Teams.tsx` (69,279 lines)

### Landing (`/teams`)
No dedicated landing tile. Team selection is via search or from elsewhere in the app.

### Dossier (`/teams?team=X`)

#### By Season Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Season row (if clickable)** | `/teams?team=X&season_from=Y&season_to=Y` | Ambient + explicit season | Season as secondary parameter; updates FilterBar on click. |
| **vs Opponent link (row)** | `/teams?team=X&vs=OppName&tab=vs+Opponent` | Ambient + team + opponent | Initiates head-to-head view within Team dossier. |
| **Match count (cell)** | (Toggle or expand row) | Ambient | No external link in current phase. |

#### vs Opponent Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Opponent name (cell)** | `/teams?team=X&vs=OppName&tab=vs+Opponent` | Ambient + team + opponent | Conditional click; row represents the matchup. |
| **Rivalry link** | `/series?filter_team=X&filter_opponent=Opp&gender=...&team_type=...` | Ambient + team pair | Navigates to /series in rivalry mode (if "Show matches" link). |

#### Compare Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Compare column header (team name)** | `/teams?team=Y` | Implicit team_type + gender | Links each compare-team to its own dossier. |
| **Compare column stat cell** | (No external link) | – | Stats are displayed but not linked (comparison view is the context). |
| **Remove team button** | `/teams?team=X&compare=Z` (updates compare CSV) | Ambient + remaining teams | Updates URL; page re-renders with subset. |

#### Batting / Bowling / Fielding Tabs
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Player name (leaderboard)** | `/batting?player=ID` / `/bowling?player=ID` / `/fielding?player=ID` | Ambient + team (via implicit filter_team from context, if rivalry) | `PlayerLink` component; phrase subscripts include team context if applicable. |
| **Team cell (discipline tables)** | `/teams?team=X` | Ambient + season | Raw `<Link>` (not `TeamLink`). |
| **Venue cell** | (No link; ambient filter_venue applies) | Ambient | Informational only. |

#### Partnerships Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Batter-pair names** | (Not yet fully linked) | – | Placeholder for future per-pair detail pages. |
| **Match link** | `/matches/:id?highlight_batter=ID1,ID2` | Hard-coded match_id + batter IDs | `partnershipMatchLink()` highlights pair on scorecard. |

#### Players Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Player name (roster)** | `/batting?player=ID` (role-inferred) | Ambient + team + season | `PlayerLink` scoped to team context. |
| **Match count (cell)** | (No external link) | – | Informational. |
| **Flag (nationality)** | (No external link) | – | `FlagBadge` component, visual only. |

#### Match List Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Date cell** | `/matches/:id` | Hard-coded match_id | Primary scorecard link. |
| **Opponent cell** | `/teams?team=Opp&tournament=X&season_from=Y&season_to=Y` (conditional) | Ambient + opponent name | Navigates to opponent's dossier, optionally filtered. |
| **Venue cell** | `/venues?venue=V` | Hard-coded venue name | Opens venue dossier. |
| **Tournament cell** | `/series?tournament=X&season_from=Y&season_to=Y` | Hard-coded tournament + season | Opens series dossier. |
| **Result cell** | (No external link) | – | Informational badge. |

---

## Players (`/players`) — Player Profiles & Comparisons

**File:** `src/pages/Players.tsx`

### Landing (`/players`)
**File:** `src/components/players/PlayersLanding.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Profile tile (player)** | `/batting?player=ID` (or `/bowling` / `/fielding` depending on tile type) | Hard-coded player + implicit gender (from FLAG_BY_ID map) | Curated tiles with hard-coded gender/nationality. Filters respect ambient gender filter. |
| **Profile tile click** | `/batting?player=ID&gender=M` (or gender override) | Hard-coded gender from tile config | `carryFilters()` merges ambient FilterBar with tile's gender override. |
| **Compare pair tile** | `/players?player=ID1&compare=ID2&gender=M` | Hard-coded pair + gender | Opens compare-grid mode with two players side-by-side. |

### Single Player (`/players?player=X`)
**File:** `src/components/players/PlayerProfile.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Discipline tab link (Batting / Bowling / Fielding)** | `/batting?player=X` / `/bowling?player=X` / `/fielding?player=X` | Ambient + player ID | Tab navigation within player context. |
| **All discipline-tab content** | (Delegates to Batting.tsx / Bowling.tsx / Fielding.tsx) | – | See discipline pages below. |

---

## Batting / Bowling / Fielding (`/batting`, `/bowling`, `/fielding`)

**Files:** `src/pages/Batting.tsx`, `src/pages/Bowling.tsx`, `src/pages/Fielding.tsx` (each ~25KB)

### Per-page structure (same for all three):

#### By Season Tab

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Tournament cell (if shown)** | `/series?tournament=X&season_from=Y&season_to=Y` | Row's tournament + season | Should link to series dossier at edition. |
| **Team cell** | `/teams?team=X&season_from=Y&season_to=Y` | Row's team + season | Scoped to season context. |
| **Opponent cell (if rivalry mode)** | `/series?filter_team=X&filter_opponent=Y&tournament=...` | Row's rivalry pair | Should carry tournament if set. |
| **Stat cells (runs, wickets, etc.)** | (No link) | – | Informational. |

#### vs Bowlers / vs Batters Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Opponent player name** | `/bowling?player=ID` (if viewing batter vs bowler) | Ambient + tournament + season | Click row or name to drill into opponent's detail. |
| **Opponent team** | `/teams?team=X` | Ambient + season | Team of the opponent. |
| **Match count / stat** | (No link) | – | Informational. |

#### By Phase / By Over Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Phase name** | (In-page filter / no external link) | – | Toggles phase filter on same page. |
| **Over range** | (Informational) | – | No external link. |

#### Dismissals Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Bowler name (if linkable)** | `/bowling?player=ID` | Ambient + tournament + season | Batter's dismissal by specific bowler. |
| **Match link** | `/matches/:id` | Hard-coded match_id | Scorecard of the dismissal. |

#### Inter-Wicket Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Partner player name** | `/batting?player=ID` | Ambient + tournament + season | Links to partner's batting record. |
| **Match link** | `/matches/:id?highlight_batter=ID1,ID2` | Hard-coded match_id + both batter IDs | Opens scorecard with both batters highlighted. |

#### Innings List Tab

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Date cell** | `/matches/:id` | Hard-coded match_id | Primary scorecard link. |
| **Opponent cell** | `/teams?team=X` | Hard-coded opponent team name | Opponent's team dossier. |
| **Venue cell** | `/venues?venue=V` | Hard-coded venue name | Venue dossier. |
| **Tournament cell** | `/series?tournament=X&season_from=Y&season_to=Y` | Row's tournament + season | Series dossier at edition. |
| **Score / stat cell (runs, wickets, etc.)** | (No external link) | – | Informational; scorecard link is date cell. |

---

## Head to Head (`/head-to-head`)

**File:** `src/pages/HeadToHead.tsx`

### Player vs Player Mode (`mode=player`)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Mode toggle (Team vs Team)** | `/head-to-head?mode=team&batter=&bowler=` | Hard-coded; clears batter/bowler | Switch modes; clears player selections. |
| **Batter search (input)** | (Player search typeahead) | – | Updates `?batter=ID` on select. |
| **Bowler search (input)** | (Player search typeahead) | – | Updates `?bowler=ID` on select. |
| **Popular matchup tile (if shown)** | `/head-to-head?mode=player&batter=ID1&bowler=ID2&gender=M` | Hard-coded player pair + gender | Quick-access to popular rivalries. |
| **Match list (if data shown)** | (Row clickable or date links to scorecard) | – | Match rows show stats; date cell → `/matches/:id`. |

### Team vs Team Mode (`mode=team`)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Mode toggle (Player vs Player)** | `/head-to-head?mode=player&team1=&team2=` | Hard-coded; clears team1/team2 | Switch modes; clears team selections. |
| **Team1 / Team2 search (input)** | (Team search typeahead) | – | Updates `?team1=X&team2=Y` on select. |
| **Series-type pill (if shown)** | `/head-to-head?series_type=bilateral` (etc.) | Hard-coded series_type value | Toggle between all/bilateral/icc/club. |
| **Tournament dossier (rendered below)** | (Delegates to TournamentDossier component) | `ScopeContext` { filter_team, filter_opponent } | TournamentDossier re-scoped to the team pair. All its links (batters, matches, records) carry the rivalry context. |

---

## Venues (`/venues`)

**File:** `src/pages/Venues.tsx`

### Landing (`/venues`)
**File:** `src/components/venues/VenuesLanding.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Venue tile (country group expanded)** | `/venues?venue=VenueName` | Hard-coded venue name | Opens venue dossier on same page. |
| **Venue search input** | (Client-side filter) | – | Filters venue list by name/city substring; no external link. |
| **Country group header (collapsed/expand toggle)** | (In-page toggle) | – | Expands/collapses country group; no navigation. |

### Dossier (`/venues?venue=V`)
**File:** `src/components/venues/VenueOverviewPanel.tsx` + `src/components/venues/VenueDossier.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Breadcrumb ("← All venues")** | `/venues` | Hard-coded | Back to landing. |
| **"view all matches →" link** | `/matches?filter_venue=V` | Hard-coded venue name | Opens match list filtered to this venue. |

#### Overview Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Ground-record team cells (highest total, lowest all-out)** | `/teams?team=X` | Hard-coded team name | Team dossier (not scoped to venue). |
| **Ground-record match link** | `/matches/:id` | Hard-coded match_id | Scorecard of the record-holding match. |
| **By-tournament-gender-season table (tournament cell)** | (Should link to `/series?tournament=X&season_from=Y&season_to=Y`) | Row's tournament + season | Currently not implemented as links; cells are plain text. |

#### Batters / Bowlers / Fielders Tabs
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Player name (leaderboard)** | `/batting?player=ID` / `/bowling?player=ID` / `/fielding?player=ID` | Ambient + venue (via `ScopeContext.filter_venue`) | `PlayerLink` with venue context carried through. |
| **Team cell** | `/teams?team=X&filter_venue=V` | Ambient + venue | `TeamLink` scoped to venue. |

#### Matches Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Date cell** | `/matches/:id` | Hard-coded match_id | Scorecard. |
| **Team cells** | `/teams?team=X&filter_venue=V` | Ambient + venue | Both sides' teams linked. |
| **Tournament cell** | `/series?tournament=X&season_from=Y&season_to=Y&filter_venue=V` | Ambient + venue | Should be `SeriesLink` (not verified). |

#### Records Tab
| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Team cell (Most titles, Best total, etc.)** | `/teams?team=X&filter_venue=V` | Ambient + venue | `TeamWithEd` component scoped to venue. |
| **Player name (record)** | `/batting?player=ID` / `/bowling?player=ID` | Ambient + venue | `PlayerLink` with venue context. |
| **Match link** | `/matches/:id` | Hard-coded match_id | Record-holding match. |

---

## Matches (`/matches`)

**File:** `src/pages/Matches.tsx`

### Landing (`/matches`)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Team filter (input + dropdown)** | `/matches?team=X` | Hard-coded team name | Updates `team` URL param on select. |
| **Player filter (search + dropdown)** | `/matches?player=ID&player_name=Name` | Hard-coded player ID | Filters matches by player participation. |
| **Match count display** | (Informational) | – | Shows total matching the current filters. |

### Match List Table

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Date cell** | `/matches/:id` | Hard-coded match_id | Primary scorecard link (convention: date cell is the main affordance). |
| **Match description cell (Team A v Team B)** | (Informational, no separate link) | – | Both team names are plain text; date cell links to scorecard. |
| **Edition cell** | `/series?tournament=X&season_from=Y&season_to=Y` | Row's tournament + season | Should be `SeriesLink` (not verified). |
| **Pagination** | `/matches?...&page=N` | Ambient + offset | Button clicks update URL offset. |

---

## Match Scorecard (`/matches/:id`)

**File:** `src/pages/MatchScorecard.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Breadcrumb (← Back to matches)** | `/matches` | Hard-coded | Back to flat match list. |
| **Tournament name (header)** | `/series?tournament=X&season_from=Y&season_to=Y` | Hard-coded tournament + season | Links to series dossier at edition. |
| **Team name (heading, each side)** | `/teams?team=X&tournament=T&season_from=Y&season_to=Y` | Hard-coded team + tournament + season | Team dossier scoped to this match's tournament + season. |
| **Innings scorecard (batting row — player name)** | `/batting?player=ID` | Hard-coded player ID + match context (via `highlight_batter=ID` param, optional) | Links to batter's profile; optional highlight param to focus this innings. |
| **Innings scorecard (bowling row — player name)** | `/bowling?player=ID` | Hard-coded player ID | Links to bowler's profile. |
| **Fielding stat cell (fielder name, if linked)** | `/fielding?player=ID` | Hard-coded fielder ID | Links to fielder's profile. |
| **Partnership link (in scorcard text, if shown)** | `/head-to-head?mode=player&batter=ID1&bowler=... (or partnership detail if future phase)` | Hard-coded player pair | TBD if partnership detail pages are built. |
| **Venue name (in scorecard)** | `/venues?venue=V` | Hard-coded venue name | Venue dossier. |
| **Toss decision / weather notes** | (Informational) | – | No external links in current phase. |

---

## Home / Landing (`/`)

**File:** `src/pages/Home.tsx`

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Featured player tile** | `/batting?player=ID&gender=M` (etc., role-specific) | Hard-coded player + gender | Curated tiles with seeded players. |
| **Featured rivalry / H2H tile** | `/head-to-head?mode=player&batter=ID1&bowler=ID2` | Hard-coded player pair | Popular matchups (hard-coded list). |
| **Featured series tile** | `/series?tournament=X` | Hard-coded tournament | Latest editions of major tournaments. |
| **"Browse all" link (if shown)** | `/series` / `/teams` / `/players` / `/venues` | Hard-coded page | Navigation to landing pages. |

---

# Scope Flow Summary

## FilterBar Filters & Propagation

**Global filters** (set by FilterBar, available via `useFilters()`):

- `gender`: 'male' | 'female' | null
- `team_type`: 'international' | 'club' | null
- `tournament`: string | null (tournament name)
- `season_from` / `season_to`: string | null (calendar years)
- `filter_team` / `filter_opponent`: string | null (rivalry pair)
- `filter_venue`: string | null (venue name)

**Series-type filter** (Series tab local):
- `series_type`: 'all' | 'bilateral' | 'icc' | 'club' | null (read from URL search params directly, NOT in FilterBar)

**Standard flow:**
1. User sets FilterBar filters → URL search params updated.
2. Page/tab reads filters via `useFilters()` or `useScopeFilters()` (if ScopeContext is in scope).
3. All non-override links inherit these filters automatically via `FILTER_KEYS` registry in `scopeLinks.ts:31–40`.

## Override / Context Layers

**Tier 1 — Page-identity pinning (ScopeContext):**
- `/teams?team=X` page pins `team: X` → `ScopeContext` → `useScopeFilters()` reads it.
- `/venues?venue=V` page pins `filter_venue: V` → links on the page "just know" venue context.
- `/series?filter_team=A&filter_opponent=B` pins rivalry pair → ScopeContext override.

**Tier 2 — Per-row override (SubscriptSource):**
- Leaderboard rows pass `subscriptSource` with row-specific tournament/season/team pair.
- `resolveBucket()` merges FilterBar + subscriptSource.
- Result: phrase URLs are scoped to the row's data, not ambient filters.

---

# Link URL Patterns

## Common destinations & their shapes:

| Destination | URL Shape | When to Use |
|---|---|---|
| **Team dossier (all-time)** | `/teams?team=X` | Team name link from anywhere. |
| **Team dossier (filtered)** | `/teams?team=X&tournament=T&season_from=Y&season_to=Y` | Scoped context (e.g., "India at T20 WC 2024"). |
| **Player profile** | `/batting?player=ID` / `/bowling?player=ID` / `/fielding?player=ID` | Role-specific landing. |
| **Player profile (filtered)** | `/batting?player=ID&tournament=T&season_from=Y&season_to=Y&filter_opponent=X` | Scoped context (e.g., "Kohli at IPL vs CSK"). |
| **Series dossier (tournament)** | `/series?tournament=X` | All editions. |
| **Series dossier (edition)** | `/series?tournament=X&season_from=Y&season_to=Y` | Single edition. |
| **Series dossier (rivalry)** | `/series?filter_team=A&filter_opponent=B` | All-time head-to-head. |
| **Series dossier (rivalry + tournament)** | `/series?filter_team=A&filter_opponent=B&tournament=X` | H2H at specific tournament. |
| **Venue dossier** | `/venues?venue=V` | Venue detail. |
| **Match scorecard** | `/matches/:id` | Single match. |
| **Match list (flat)** | `/matches` | All matches (filterable by team/player/scope). |
| **Scorecard with highlight** | `/matches/:id?highlight_batter=ID1,ID2` | Scorecard with partnership or fielding context highlighted. |

---

# Audit Notes & Observations

## High-level checklist:

✓ **Navigation spine intact** — All main tabs reachable from Layout.tsx nav bar.  
✓ **Breadcrumbs present** — Dossier pages (venue, tournament) have back-to-landing links.  
✓ **Date-cell convention followed** — Match lists use date cell as primary scorecard link.  
✓ **PlayerLink / TeamLink used consistently** — Entity landing links delegate scope to components.  
✓ **(ed) subscripts properly scoped** — Team/player rows in records/editions carry per-row tournament+season context.  
✓ **Rivalry mode support** — `/series?filter_team=A&filter_opponent=B` and Head-to-Head both work correctly.  
✓ **Phrase tiers offered** — PlayerLink and TeamLink render 0–3 narrowing phrases as clickable subscripts.  

## Minor gaps (acceptable):

- Venue dossier's "Matches hosted by tournament" table doesn't link tournament cells yet (informational only). Phase 4 TODO.
- Partnership-detail page not yet built; match links carry optional `highlight_batter=` but no dedicated partnership page.
- Some small tables (e.g., venue phase breakdown) are not hyper-linked; information-dense context prioritized over link density.

## Consistency notes:

- **Name links are entity-scoped, never rivalry-scoped.** A team-name link always goes to the team's all-time page. Scope (tournament, season, opponent) is **only** in phrase subscripts or ambient FilterBar.
- **Each page's "landing" has a breadcrumb.** Venue → "← All venues", Series → (implicit home), Team → (search-accessible).
- **FilterBar changes auto-reset pagination.** When filters change mid-list, offset resets to 0 (page 1) via `useRef` + `useEffect`.
- **Ambient filters ride through silently** — callers don't need to mention them; `FILTER_KEYS` registry ensures they're included.

---

**End of Link Audit**  
*Generated: 2026-04-20*

