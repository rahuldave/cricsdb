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

## Deviations Found

The audit identified the following departures from conventions:

- **TournamentDossier.tsx:68–74** (renderVsTeams): Raw `<Link>` to `/teams?team=...` instead of `TeamLink`. **Acceptable** because rendering is inline prose ("A v B") without semantic scope phrases, so full `TeamLink` is unnecessary.
- **VenueOverviewPanel.tsx:13–14** (teamLink helper): Inline `<Link>` to `/teams` without `TeamLink`. **Acceptable** — used in small phrases where phrase subscripts are not needed.
- **Matches.tsx:date column** (Teams.tsx:131): Uses `<Link>` to `/matches/:id` directly. **OK** — compact cell, no scope phrases needed.
- **No "highlight_" URL params on most match links** — Only partnership-match links carry `highlight_batter=...`. This is intentional; scorecard highlighting is an opt-in navigation feature, not ambient. ✓

---

# Main Tabs & Subtabs

## Series (`/series`) — Tournaments / Matches

### Landing View (`/series`)
**File:** `src/components/tournaments/TournamentsLanding.tsx`

| Affordance | Target | Scope Source | Notes |
|---|---|---|---|
| **Tournament tile (main)** | `/series?tournament=X` | Hard-coded (tile) + ambient gender/team_type | Primary link on each tile. `SeriesLink` component carries tournament + season_from/to. |
| **"Most titles" team link** | `/teams?team=X` | Hard-coded team name + ambient gender/team_type | Raw `<Link>`, no phrase subscripts. |
| **"Most titles" count link** | `/teams?team=X&tournament=X&season_from=Y&season_to=Y` | Hard-coded team + tournament + latest season | When count > 1, links to team at specific tournament edition. |
| **Latest season link** | `/series?tournament=X&season_from=Y&season_to=Y` | Hard-coded tournament + latest edition | `SeriesLink` component. |
| **Champion team link** | `/teams?team=X&tournament=X&season_from=Y&season_to=Y` | Hard-coded scope (edition-specific) | One-off team link scoped to the edition. |
| **Rivalry tiles (if present)** | `/series?filter_team=A&filter_opponent=B&series_type=...` | Hard-coded team pair + implicit series_type | Conditional on data availability. |

**Summary:** Tournament landing is curated with hard-coded scope. Every link carries tournament + latest season context. No ambient FilterBar influence here.

---

### Dossier View (`/series?tournament=X` OR `/series?filter_team=A&filter_opponent=B`)

**File:** `src/components/tournaments/TournamentDossier.tsx` (2161 lines)

#### Overview Tab
**Location:** TournamentDossier.tsx:543–850

| Element | Affordance | Target | Scope | Source |
|---|---|---|---|---|
| **StatCards (top)** | Team/player name | `/teams?team=X` or `/batting?player=X` | Ambient + row's team (oriented via `orientedSource()`) | `TeamLink` / `PlayerLink` with subscriptSource |
| **Phrase subscripts (StatCard subtitle)** | Scope tier link | `/teams?...` or `/batting?...` | Full bucket + phrase tier params | `phraseLinks()` helper @ 593–618 |
| **Best moments — batter** | Player name | `/batting?player=X` | Ambient + row's team + match date | `PlayerLink` with subscriptSource |
| **Best moments — bowler** | Player name | `/bowling?player=X` | Ambient + row's team + match date | `PlayerLink` with subscriptSource |
| **Best moments — partnership** | Batter pair | `/batting?player=X` | Ambient + row's team | Two `PlayerLink` renders, comma-separated |
| **Best moments — match date** | Match scorecard | `/matches/:id` | Hard-coded match_id | `matchLink()` @ 44–46 |

**Subtabs:**

#### Editions Tab
**Location:** TournamentDossier.tsx (via EditionsTab component)

| Affordance | Target | Scope | Source | Notes |
|---|---|---|---|---|
| **Season row click** | `/series?tournament=X&season_from=Y&season_to=Y` | Hard-coded to single edition | FilterBar + table row | `onPickSeason()` callback sets tab='Overview' + narrows season filters. |
| **Season team leaderboard (if expandable)** | Per-team stats at edition | Scoped within edition | Ambient | Tab stays on Editions; row expansion is in-place. |

#### Points Tab
**Location:** TournamentDossier.tsx (via PointsTab component, shown only when single-season is in scope)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Points table team cells** | `/teams?team=X` | Ambient + tournament + single season | Should use `TeamLink` with subscriptSource scoped to tournament/season (not verified in audit). |

#### Batters / Bowlers / Fielders Tabs
**Location:** TournamentDossier.tsx (via BattersTab, BowlersTab, FieldersTab)

| Affordance | Target | Scope | Source |
|---|---|---|---|
| **Player name (leaderboard row)** | `/batting?player=X` / `/bowling?player=X` / `/fielding?player=X` | Ambient + row's team (if rivalry mode) | `PlayerLink` with `rowSubscriptSource()` — orientation flips pair per row |
| **Phrase subscripts** | Discipline page with scope tier | Full bucket from row + phrase tier | `resolveScopePhrases()` output |
| **Team cell (if shown)** | `/teams?team=X` | Ambient + tournament + season | Should be `TeamLink` with (ed) subscript (not verified in code). |

#### Partnerships Tab
**Location:** TournamentDossier.tsx (via PartnershipsTab)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Batter-pair names** | `/batting?player=ID1,ID2` or individual `/batting?player=ID` | Ambient + tournament + season | Pair links not yet implemented (shows plain text). Individual redirects TBD. |
| **Match link (partnership row)** | `/matches/:id?highlight_batter=ID1,ID2` | Hard-coded match_id + batter pair IDs | `partnershipMatchLink()` @ 48–58; highlights both batters on scorecard. |
| **Wicket number cell** | In-page toggle / phase filter | N/A | No external link; filters data in-place. |

#### Records Tab
**Location:** TournamentDossier.tsx (via RecordsTab)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Team cell (e.g., Most titles)** | `/teams?team=X` | Ambient + tournament + season | `TeamWithEd` component @ 104–126; carries (ed) subscript for tournament+season scope. |
| **Player name (records)** | `/batting?player=X` / `/bowling?player=X` | Ambient + row's team (if applicable) | `PlayerLink` with subscriptSource scoped to row. |
| **Match link (highest total, best bowling, etc.)** | `/matches/:id` | Hard-coded match_id | `matchLink()` helper. |

#### Matches Tab
**Location:** TournamentDossier.tsx (via MatchesTab)

| Affordance | Target | Scope | Notes |
|---|---|---|---|
| **Date cell** | `/matches/:id` | Hard-coded match_id | Primary affordance to scorecard. |
| **Team cells (both sides)** | `/teams?team=X` | Ambient (FilterBar) | Raw `<Link>`, no `TeamLink`. Scoped by ambient alone. |
| **Venue cell** | In-page filter / no link | Ambient filter_venue | Venue cells are informational; VenueSearch is the affordance. |
| **Score cell** | `/matches/:id` (or via date) | Hard-coded match_id | `<Score>` component if match is linkable; otherwise plain text. |
| **Tournament cell** | (Usually not shown; match row is already filtered by tournament) | Ambient | If shown, should link to `/series?tournament=X`. |
| **Pagination** | `/series?...&page=N` | Ambient + tab + offset | Button clicks update `pageParam` URL state. |

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

