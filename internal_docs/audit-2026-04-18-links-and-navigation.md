# Links & Navigation Audit — 2026-04-18

A page-by-page walk of every top-level route looking for missing
entity links, dead ends, and places where the rendered output
doesn't follow the project's own conventions. No fixes applied —
this is a survey that seeds the next implementation session.

## Rules being audited against

From `CLAUDE.md`:

- **Match-list date convention.** Every match-listing table MUST
  render the date cell as `<Link to={`/matches/${match_id}`}>` with
  className `comp-link`. Player innings-list contexts must also
  carry `highlight_batter` / `highlight_bowler` / `highlight_fielder`
  on the link.
- **Two-link name + context pattern.** A player mention is two
  links: the name (goes to the relevant discipline page with only
  `player` + `gender` set — "show me this player") and an optional
  italic faint suffix ("· in Indian Premier League ›") that goes to
  the same page with extra filter params. Canonical implementation
  is `components/PlayerLink.tsx`. Dense tables (scorecard) skip the
  context suffix via `compact`.
- **Sensible links up.** Every page should offer a way back up or
  sideways: scorecard → match list scoped to the tournament / team
  / season; player → series they played in; etc.

## Methodology

1. Enumerated every linking component and its usages.
2. Three parallel surveys across page files (`pages/*.tsx`) + the
   shared scorecard / dossier components.
3. Spot-verified high-severity findings via direct file reads.

Citations are `file:line` — open them in your editor to confirm.

---

## Findings by page

### Home (`pages/Home.tsx`)

- **Recent-fixtures date cell — no Link.** The whole row is
  `onClick`-clickable (lines 245–253) but the date itself is plain
  text at line 252. Can't cmd/ctrl-click to open the scorecard in a
  new tab. Violates the match-list date convention (which, strictly,
  scopes to "any table that lists matches"). **Gap.**
- Player tiles use a local two-link `PlayerLink` (lines 62–87) that
  points name → `/players`, letters → discipline pages. Intentional
  for the masthead — *distinct* from the tables' canonical
  `components/PlayerLink.tsx` which points name → discipline. Worth
  noting so nobody accidentally unifies them.
- Everything else looks right: teams via `TeamLink`, tournaments via
  a local `CompLink`.

### Teams (`pages/Teams.tsx`)

- **Keepers list uses a raw `<a href>`.** Line 237 — should be
  React `<Link>` with className `comp-link` for SPA navigation. Works
  today (the browser falls back to a hard navigation), but breaks
  the "keep your scroll + state" illusion on click. **Minor.**
- **Players tab player names use bare `<Link>`, not `PlayerLink`.**
  Lines 1313–1316. Should be `PlayerLink` with
  `contextLabel={`at ${team}`}` + `contextParams={{filter_team:
  team}}` so the "· at Team X ›" suffix appears. **Gap.**
- **Selected-opponent stacked-bar buttons** (line 1006): plain text
  `{o.name}`. Arguable — it's a selector, not a drilldown. But
  offering a "see full rivalry →" link beside the selected opponent
  would solve the dead end. (A "See full rivalry →" link already
  exists nearby at 863–869 for the vs-opponent header, so the
  pattern is established.)
- Everything else green: `Match List` + `vs Opponent` both use the
  date-link convention; top-batters/bowlers/fielders use
  `PlayerLink` with context.

### Players (`pages/Players.tsx` + `components/players/`)

- Landing tiles, single-player header, discipline bands all follow
  the canonical patterns. `FlagBadge` uses `linkTo` so nationality
  chips click through to `/teams`.
- **No gaps flagged.** Compare view wasn't inspected in deep detail
  — the three-way compare already has its own integration test
  coverage.

### Batting (`pages/Batting.tsx`)

- **`vs Bowlers` table — bowler name is a plain `<span>`.** Lines
  151–162. The only clickable affordances are tiny "(stats · h2h)"
  suffixes. Users who click the bowler name expect navigation and
  get nothing. Should be `PlayerLink` with contextLabel so the name
  itself is the primary link and "vs Kohli" becomes the context.
  **High-impact usability gap.**
- **Innings-list opponent column — plain text.** Line 140. Should
  link to `/teams?team=...`. **Low-priority gap.**
- Landing leaderboards + Innings-List date cell: compliant. Filter
  carry-through on tile clicks: good.

### Bowling (`pages/Bowling.tsx`)

- **`vs Batters` table — batter name is a plain `<span>`.** Lines
  135–146. Same pattern (and same fix) as Batting's `vs Bowlers`.
  **High.**
- **Innings-list opponent column — plain text.** Line 125. **Low.**
- Landing leaderboards + Innings-List date cell: compliant.

### Fielding (`pages/Fielding.tsx`)

- **`Victims` table — batter name plain `<span>`.** Lines 153–164.
  Same pattern as Batting/Bowling matchups. **High.**
- **`Victims` h2h link is broken.** Line 160:
  `` `/head-to-head?batter=${r.batter_id}&bowler=` `` — the `bowler=`
  param is hard-coded empty because there's no canonical "bowler"
  to pair with for a fielder. The link lands on the H2H landing
  with one half filled. Either remove the h2h link entirely for
  fielders, or re-interpret the fielder's `person_id` as the
  "bowler" side (questionable). **BUG.**
- **Innings-list opponent column — plain text.** Lines 176, 198.
  **Low.**
- Fielding + Keeping date cells: both compliant with the highlight
  param convention.

### Series (`pages/Tournaments.tsx` + `components/tournaments/TournamentDossier.tsx`)

- **Records tab — largest partnerships: batter names plain text.**
  Lines ~1386–1388 (RecordsTab). Dates are linked; batters aren't.
  **Gap.**
- **Records tab — best bowling: bowler name plain text.** Line
  ~1406. Date is linked; bowler isn't. **Gap.**
- **Records tab — most sixes in a match: teams column plain text.**
  Line ~1422. Date is linked; teams aren't. **Gap.**
- **Partnerships tabs (By-Wicket + Top): batter names in the
  "Best Stand" / "Batters" columns plain text** — lines ~802,
  849–850. Date columns link to a clever "both-batters-highlighted"
  H2H scorecard, which is great; but the batter names right there
  in the row aren't links. **Gap.**
- **Knockouts + Matches tabs: venue column plain text.** Lines 689,
  929. Should link `?filter_venue=…` now that it's an ambient
  filter. **Low-medium.**
- Otherwise green: Overview / Batters / Bowlers / Fielders tabs all
  use `PlayerLink` with context; team names + dates are linked
  throughout; champions / knockouts rows link to scorecards.

### HeadToHead (`pages/HeadToHead.tsx`)

- **Suggestion tiles aren't styled as links.** Lines ~208–241
  (player mode) and 435–517 (team mode). They're clickable via
  `onClick`, but no underline, no hover cursor affordance. Users
  don't discover they're clickable. **High (discoverability).**
- **By-match row — tournament + venue plain text.** Lines 124, 125.
  Tournament should link `/series?tournament=…`; venue should link
  `?filter_venue=…`. **Gap.**
- Player-vs-player header, flags, date column in by-match: all
  compliant.

### Matches (`pages/Matches.tsx`)

- **Date cell is plain `<td>` (row-click navigates).** Line 174.
  This predates the strict match-list date convention, which was
  introduced for player innings-list tables. Users can't cmd-click
  a date to open the scorecard in a new tab. Recommend aligning:
  add `<Link to={`/matches/${m.match_id}`}>…</Link>` inside the
  `<td>` so both row-click *and* cmd-click work. **Medium.**
- **Venue / city cell — plain text.** Line 194. Should link
  `?filter_venue=…` now that venue is an ambient filter.
- **Result text — plain text.** Line 195. Probably fine (it's
  descriptive prose, not an entity).
- Team cells + tournament cell are correctly linked.

### Scorecard (`components/Scorecard.tsx` + `InningsCard.tsx` + `pages/MatchScorecard.tsx`)

This is the biggest cluster of gaps. The scorecard is hit from
deep-link shares, player innings lists, and tournament dossiers —
arriving users often have no local history to "back" into.

- **Dead-end scorecard (no links up).** `MatchScorecard.tsx:61-67`
  only offers a back button that falls back to `/matches`. No
  breadcrumb, no "← Indian Premier League 2024 ›" or "← Mumbai
  Indians Match List ›". **High (orientation gap).**
- **`player_of_match` plain text.** Scorecard.tsx:78 —
  `info.player_of_match.join(', ')`. Needs a PlayerLink per name.
  The API already returns a JSON array (see `docs/api.md`), but the
  frontend stringifies. **High.**
- **Toss text — team + player names plain text.** Scorecard.tsx:72–74.
  The string is pre-rendered server-side; splitting it at the
  frontend would be fragile. Flag for design discussion rather
  than a straight fix.
- **Venue + date in header — plain text.** Scorecard.tsx:68.
  Venue should link `?filter_venue=…`; date could link to
  `/matches?season_from=…&season_to=…` scoped to that season, or
  simply remain prose.
- **Dismissal text (`c Sharma b Bumrah`) — only the whole cell is
  an H2H link.** InningsCard.tsx:100–104. The fielder "Sharma" and
  bowler "Bumrah" inside that text are not individually navigable.
  The scorecard API returns `dismissal_fielder_ids` (see CLAUDE.md
  "Fielder dismissal attribution"), so surfacing those names as
  PlayerLinks is feasible — but the server currently returns just
  the pre-formatted `dismissal` string. Flag for design discussion.
- **Did-not-bat list — plain text.** InningsCard.tsx:132–136 joins
  names with `', '`. Each should be a PlayerLink (compact, no
  context). API returns names (no IDs), so server response needs to
  include `did_not_bat_ids` first. Flag as a two-part change.
- **Fall-of-wickets batter names — plain text.** InningsCard.tsx:143.
  Names come inline in the wicket text (no IDs). Same two-part fix
  as did-not-bat: backend change + frontend PlayerLink.
- **Innings-header team name — plain text.** InningsCard.tsx:35.
  Should be a `<Link to={`/teams?team=…`}>`.

### Venues (`pages/Venues.tsx`)

- Landing is a picker, not a drill-down. Tiles click through to
  `/matches?filter_venue=…`. Correctly plain-text country group
  headers; correctly scope-narrowing section defaults. **No gaps.**

---

## Consolidated action list

Priority reflects user impact (`H` = high, `M` = medium, `L` = low).

| ID | Page / Location | Issue | Severity |
|----|-----------------|-------|----------|
| 1  | Scorecard header | Dead end — no breadcrumb up to tournament / team / season | H |
| 2  | Scorecard | `player_of_match` plain text | H |
| 3  | Batting `vs Bowlers` | Bowler name is plain `<span>`, not a link | H |
| 4  | Bowling `vs Batters` | Batter name is plain `<span>`, not a link | H |
| 5  | Fielding `Victims` | Batter name plain `<span>` | H |
| 6  | Fielding `Victims` | h2h link hard-codes `&bowler=` (empty) | H (bug) |
| 7  | HeadToHead | Suggestion tiles not visually styled as links | H |
| 8  | HeadToHead by-match | Tournament + venue cells plain text | M |
| 9  | Matches list | Date cell isn't a Link (row-click only) | M |
| 10 | Matches list | Venue cell plain text | M |
| 11 | Teams Players tab | Player names use bare `<Link>`, not `PlayerLink` | M |
| 12 | Teams Keepers list | Uses raw `<a href>` not React `<Link>` | L |
| 13 | Series Records | Largest partnership batters, best-bowling bowler, most-sixes teams plain text | M |
| 14 | Series Partnerships | Batter names in By-Wicket / Top tables plain text | M |
| 15 | Series Knockouts + Matches | Venue column plain text | L |
| 16 | Home fixtures | Date cell not a Link | M |
| 17 | Scorecard innings header | Team name plain text | L |
| 18 | Scorecard dismissal text | Fielder + bowler inside text not individually linked | M — needs API change |
| 19 | Scorecard did-not-bat | Names plain text | M — needs API change |
| 20 | Scorecard fall-of-wickets | Batter names plain text | M — needs API change |
| 21 | Batting / Bowling / Fielding innings list | Opponent column plain text | L |

## Cross-cutting observations

- The "bowler_name / batter_name in a plain span with tiny (stats ·
  h2h) suffixes" pattern appears on three pages (Batting vs Bowlers,
  Bowling vs Batters, Fielding Victims). Treat as one refactor: use
  `PlayerLink` with the appropriate `role`, and move "stats"/"h2h"
  into context params. That collapses items 3–5 (plus 6's bug) into
  a single coordinated change.
- Several Scorecard gaps (18–20) are two-part: the API response
  needs to expose person IDs the frontend can link. Scope separately
  from the pure-frontend gaps.
- `filter_venue` is an ambient filter as of 2026-04-17, but venue
  *cells* across the site (items 8, 10, 15) still render as plain
  text. A simple "venue → ?filter_venue=…" sweep would surface the
  filter more naturally.

## Not gaps

- City names next to venues (Home, Venues landing) stay plain —
  there's no `/city` page.
- Officials (umpires, match referee) stay plain — no `/officials`
  page and none planned.
- Fall-of-wickets over number stays plain (no "over page").
- Result-text prose in Matches list / Scorecard stays plain — it's
  a sentence, not an entity.
- The home-page masthead `PlayerLink` intentionally differs from the
  components/ `PlayerLink` — they have different jobs.

## For the next session

Recommend tackling in this order:

1. **Scorecard orientation (items 1, 2).** Breadcrumb + player-of-match
   link — both pure-frontend, both high-user-value.
2. **Matchup-table refactor (items 3–6).** One shared fix across
   three pages + the fielding h2h bug.
3. **HeadToHead suggestion-tile styling (item 7).** Low code, high
   discoverability.
4. **Venue-cell sweep (items 8, 10, 15).** Consistent with the
   Phase-2 venue filter.
5. **Match-list date alignment (items 9, 16).** Small, purely
   additive.
6. **Series Records / Partnerships link-up (items 13, 14, 11, 12).**
7. **Scorecard API + innings header (items 17–20).** The only items
   that require a backend change.
