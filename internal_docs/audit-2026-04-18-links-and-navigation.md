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

- ~~**Recent-fixtures date cell — no Link.**~~ **Withdrawn on
  re-read 2026-04-18.** The whole fixture row is already wrapped in
  `<Link to={`/matches/${match_id}`}>` at line 245 (it's a `<Link>`,
  not a `<td>` with `onClick`), so cmd/ctrl-click already opens the
  scorecard in a new tab. No gap.
- Player tiles use a local two-link `PlayerLink` (lines 62–87) that
  points name → `/players`, letters → discipline pages. Intentional
  for the masthead — *distinct* from the tables' canonical
  `components/PlayerLink.tsx` which points name → discipline. Worth
  noting so nobody accidentally unifies them.
- Everything else looks right: teams via `TeamLink`, tournaments via
  a local `CompLink`.

### Teams (`pages/Teams.tsx`) — ✅ shipped 2026-04-18

- ✅ **Keepers list `<a href>` → `<Link>`.** SPA navigation now.
- ✅ **Players tab name link** — now routes to
  `/players?player=X&gender=Y&filter_team={team}` instead of the
  old bare `/batting?player=X`. The Players page's `ScopeIndicator`
  already renders "Scoped to matches at {team}" when `filter_team`
  is present, so no context suffix needed (the arrival page
  self-documents). Note: audit originally suggested `PlayerLink`
  with `contextLabel` — wrong for this grid; `PlayerLink` is
  discipline-routed, and a per-row italic suffix would wrap badly
  in the 3-column tight layout.
- ✅ **Opponent stacked-bar: name is now a rivalry link.** Clicking
  the name navigates to `/head-to-head?mode=team&team1=X&team2=Y`
  (with gender + team_type carried). Clicking the bar / record
  span still selects the opponent for inline drill-down.
  `stopPropagation` on the name link prevents the outer `<button>`
  from also firing the selector. Underline constrained to text
  width via `justifySelf: 'start'` — grid was stretching the
  default `display: block` `<a>` to the 200px column width,
  producing a full-cell underline.
- ✅ **NEW bug found during audit: tab-switch leaked `vs=`.**
  Clicking "vs Opponent → NZ → Players" left `vs=New+Zealand` in
  the URL. Tab click was `setActiveTab(tab)` which only touched
  `tab=`. Changed to `setUrlParams({ tab, vs: '' })` to atomically
  clear the tab-local `vs=` param on every tab switch.
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

### Batting (`pages/Batting.tsx`) — ✅ shipped 2026-04-18

- ✅ **`vs Bowlers` — bowler name is now a `comp-link`** to
  `/bowling?player={bowler_id}`. Hybrid shape kept: dropped the
  redundant `(stats)` parenthetical (name is now the stats link),
  kept the matchup affordance relabeled `head to head` in
  uppercase + `letter-spacing: 0.12em` (Wisden nav style).
  Discussion rejected the canonical two-link "· vs {batter} ›"
  pattern because long batter names (e.g. "Mohammad Rizwan") would
  bloat every row with identical suffixes — the page header
  already tells the user which batter they're viewing.
  `stopPropagation` on both links so row-click (if any) isn't
  hijacked.
- ✅ **Innings-list opponent column** now links
  `/teams?team={opponent}`.
- ✅ **NEW finding during re-verify**: innings-list tournament
  column was also plain text — fixed in same batch. Now links
  `/series?tournament={name}`.
- Landing leaderboards + Innings-List date cell: compliant. Filter
  carry-through on tile clicks: good.

### Bowling (`pages/Bowling.tsx`) — ✅ shipped 2026-04-18

- ✅ **`vs Batters` hybrid** — same treatment as Batting's
  `vs Bowlers`: name → `/batting?player={batter_id}`; dropped
  `(stats)`; `HEAD TO HEAD` micro-suffix (0.55rem, uppercase,
  opacity 0.65) → `/head-to-head?batter={batter_id}&bowler={current_bowler}`.
- ✅ **Innings-list opponent column** → `/teams?team={opponent}`.
- ✅ **NEW finding during re-verify**: innings-list tournament
  column was also plain — fixed in same batch → `/series?tournament={name}`.

### Fielding (`pages/Fielding.tsx`) — ✅ shipped 2026-04-18

- ✅ **`Victims` batter name is now a `comp-link`** → `/batting?player={batter_id}`.
  Dropped the entire `(stats · h2h)` micro-menu rather than adapting
  the Batting/Bowling hybrid — because a fielder isn't a bowler,
  there's no meaningful player-vs-player H2H destination (this was
  the root cause of the broken `&bowler=` link). So Fielding gets
  the "just make the name a link" fix, without the uppercase
  HEAD TO HEAD suffix that Batting/Bowling have.
- ✅ **#6 h2h bug naturally fixed** — the broken `&bowler=` link is
  gone with the micro-menu.
- ✅ **Innings-list opponent + tournament columns** linked in BOTH
  the fielding innings table (`inningsColumns`) and the keeping
  innings table (`keepingInningsColumns`). Plus one new tournament-
  column finding from re-verify, same as the Batting/Bowling
  re-verifies flagged.
- Fielding + Keeping date cells: both compliant with the highlight
  param convention.

### Series (`pages/Tournaments.tsx` + `components/tournaments/TournamentDossier.tsx`) — ✅ mostly shipped 2026-04-18

- ✅ **Records tab (all four cells)** — Largest partnerships
  batters now use `renderBatterPair`; teams column uses
  `renderVsTeamsFromString` (parse on " vs " / " v ", fallback to
  plain on parse failure). Best bowling bowler name now links to
  `/bowling?player=X`. Most sixes teams column uses
  `renderVsTeamsFromString`.
- ✅ **Partnerships tabs (4 cells across By-Wicket + Top)** — Best
  Stand / Batters columns use `renderBatterPair`; Match columns
  use `renderVsTeams` directly (structured `batting_team` +
  `opponent` on the types, no parsing needed).
- ✅ **Editions table (not originally in audit, added by user
  review)** — Champion / Runner-up now link `/teams?team=X`; Top
  scorer / Top wicket-taker now link to batting / bowling
  discipline pages; the trailing `(runs)` / `(wickets)` stays
  plain.
- ✅ **Shorter per-row tournament context** (also user-added) —
  `playerContext` helper in `TournamentDossier.tsx` no longer
  appends the full tournament name to every row's label. When the
  only scope in play is the tournament itself, the suffix reads
  `· tournament ›`. When team/rivalry scope is also set, the
  suffix shows just the team/rivalry part (`· at India ›` or
  `· vs CSK ›`); the tournament still flows through URL params so
  the destination page is correctly narrowed.
- ⏳ **Knockouts + Matches venue column** — deferred to the
  venue-cell sweep (items 8, 10, 15 in the table).
- Otherwise green: Overview / Batters / Bowlers / Fielders tabs all
  use `PlayerLink` with context (now shorter); team names + dates
  are linked throughout; champions / knockouts rows link to
  scorecards.

Two small reusable helpers landed inline at the top of
`TournamentDossier.tsx`: `renderBatterPair(b1, b2)` and
`renderVsTeams(t1, t2, sep=' v ')` + `renderVsTeamsFromString(s)`.
These are currently scoped to this file; worth extracting to a
shared `utils/renderLinks.tsx` if they're needed elsewhere.

### HeadToHead (`pages/HeadToHead.tsx`) — ✅ mostly shipped 2026-04-18

- ✅ **Suggestion tiles now render identically to Series landing
  tiles.** Root cause was button defaults leaking through — `<button
  class="wisden-tile">` had `text-align: center` and
  `cursor: default` while `<a class="wisden-tile">` on Series had
  `text-align: start` / `cursor: pointer`. Fixed globally in
  `index.css` by adding `text-align: left; cursor: pointer;
  font: inherit; width: 100%` to `.wisden-tile` — any
  `<button class="wisden-tile">` anywhere on the site now matches
  the anchor-based tiles. No trailing arrow and no title
  hover-color-shift were added; per user direction the tiles should
  stay visually identical to Series (which have neither).
- ✅ **By-match tournament column** now links
  `/series?tournament=X`.
- ⏳ **By-match venue column** — deferred to the venue-cell sweep
  (after the Venues tab walk).
- Player-vs-player header, flags, date column in by-match: all
  compliant.

### Matches (`pages/Matches.tsx`) — ✅ partially shipped 2026-04-18

- ✅ **Date cell is now a `<Link>`** to `/matches/{match_id}` with
  `stopPropagation`. Row-click still navigates; cmd-click now
  opens in a new tab. Kept `color: inherit` so the cell reads as
  faint text not an obvious link (matches the earlier visual).
- ✅ **Venue cell rewritten.** Now shows the canonical venue name
  as a `<Link>` to `/matches?filter_venue={venue}`, with `· {city}`
  as a faint suffix when the city differs. Uses the Phase-1
  canonicalised venue names from `api/venue_aliases.py`. Previously
  the cell rendered `city || venue`, preferring city — now the
  venue is primary since it's reliably canonical.
- Result text — plain (descriptive prose, not an entity).
- ⏳ **Team-name scope ambiguity (new discovery, punted).** Team
  cells are linked but carry `tournament=…` context, which means
  "India" from a Matches row lands on a tournament-scoped team
  page. There's no escape hatch to the overall team page without
  re-editing the URL. Compounded by the bilateral case where
  `tournament` is a transient series name. Documented in
  `internal_docs/design-decisions.md` — "Team-name link scope
  ambiguity — disambiguate via a `TeamLink` component (revisit)".

### Scorecard (`components/Scorecard.tsx` + `InningsCard.tsx` + `pages/MatchScorecard.tsx`) — ✅ partially shipped 2026-04-18

Pure-frontend items shipped. API-dependent items documented as a
single follow-up batch in `design-decisions.md` — "Scorecard
linkability: API response-shape follow-up".

- ✅ **Breadcrumb above the h2** — `Tournament › Season › All
  matches`. Gives deep-linked arrivals explicit up + sideways
  escape hatches without relying on browser history. `← Back`
  retained on the page shell because it preserves the highlight
  scroll when returning to an innings list (the in-app flow).
- ⏳ **`player_of_match` plain text** — deferred. Needs API to
  return `{name, person_id}[]` instead of `string[]`.
- ✅ **Toss-winner team name** now linked to `/teams?team=X`
  (overall, no tournament scope — acknowledging the punted
  `TeamLink` refactor).
- ✅ **Venue in header** already linked (shipped in earlier batch).
  Date in header — kept plain (prose, not an entity worth linking
  alone; the breadcrumb's season link covers the discovery need).
- ⏳ **Dismissal text** — deferred. Backend already has the fielder
  IDs; needs to also expose the bowler / batter IDs so the text
  can be composed with linked names.
- ⏳ **Did-not-bat list** — deferred. Needs `did_not_bat` to become
  `PersonRef[]`.
- ⏳ **Fall-of-wickets batter names** — deferred. Needs
  `fall_of_wickets[].batter: PersonRef`.
- ✅ **Innings-header team name** (`InningsCard.tsx:35`) — team
  prefix of `innings.label` now wraps in a `<Link>` to
  `/teams?team=X`. Falls back to the raw label if the team-prefix
  heuristic doesn't match (super-overs / unusual labels).

### Venues (`pages/Venues.tsx`)

- Landing is a picker, not a drill-down. Tiles click through to
  `/matches?filter_venue=…`. Correctly plain-text country group
  headers; correctly scope-narrowing section defaults. **No gaps.**

---

## Consolidated action list

Priority reflects user impact (`H` = high, `M` = medium, `L` = low).

| ID | Page / Location | Issue | Severity |
|----|-----------------|-------|----------|
| ~~1~~ | ~~Scorecard header~~ | ✅ **Shipped** — breadcrumb `Tournament › Season › All matches`. | — |
| 2  | Scorecard | `player_of_match` plain text | ⏳ Deferred (needs API shape change — documented in design-decisions.md) |
| ~~3~~ | ~~Batting `vs Bowlers`~~ | ✅ **Shipped** — hybrid: name → `/bowling?player=X`; `HEAD TO HEAD` suffix in Wisden uppercase style → `/head-to-head`. Dropped `(stats)`. | — |
| ~~4~~ | ~~Bowling `vs Batters`~~ | ✅ **Shipped** — same hybrid as #3. | — |
| ~~5~~ | ~~Fielding `Victims`~~ | ✅ **Shipped** — name is now `<Link>` to `/batting?player=X`. Dropped `(stats · h2h)` entirely (no meaningful H2H for fielder). | — |
| ~~6~~ | ~~Fielding `Victims` broken h2h~~ | ✅ **Fixed by #5** — offending link removed. | — |
| ~~7~~ | ~~HeadToHead~~ | ✅ **Shipped** — `.wisden-tile` CSS reset so button-tiles render like anchor-tiles (left align + pointer cursor). | — |
| 8  | HeadToHead by-match | ✅ Tournament linked. Venue deferred to venue-cell sweep. | M partial |
| ~~9~~ | ~~Matches list~~ | ✅ **Shipped** — date is now a `<Link>` with stopPropagation. | — |
| ~~10~~ | ~~Matches list~~ | ✅ **Shipped** — venue linked via `filter_venue`; canonical venue name + `· city` suffix. | — |
| ~~11~~ | ~~Teams Players tab~~ | ✅ **Shipped** — name → `/players?player=X&gender=Y&filter_team={team}`; ScopeIndicator pill on arrival. | — |
| ~~12~~ | ~~Teams Keepers list~~ | ✅ **Shipped** — now uses `<Link>`. | — |
| ~~13~~ | ~~Series Records~~ | ✅ **Shipped** — batter pair, bowler, and teams cells all linked; new `renderBatterPair` + `renderVsTeams` helpers. | — |
| ~~14~~ | ~~Series Partnerships~~ | ✅ **Shipped** — same helpers applied to By-Wicket + Top partnership tables. | — |
| 15 | Series Knockouts + Matches | Venue column plain text | L |
| ~~16~~ | ~~Home fixtures~~ | ~~Date cell not a Link~~ — **withdrawn, row is already a `<Link>`** | — |
| ~~17~~ | ~~Scorecard innings header~~ | ✅ **Shipped** — team prefix of `innings.label` linked. | — |
| 18 | Scorecard dismissal text | Fielder + bowler inside text not individually linked | ⏳ Deferred — API shape change |
| 19 | Scorecard did-not-bat | Names plain text | ⏳ Deferred — API shape change |
| 20 | Scorecard fall-of-wickets | Batter names plain text | ⏳ Deferred — API shape change |
| ~~21~~ | ~~Batting / Bowling / Fielding innings list~~ | ✅ **Shipped on all three tabs** 2026-04-18 — opponent + tournament columns both linked. | — |

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

## In-session progress (2026-04-18)

Walking the audit tab-by-tab with the user, shipping fixes at the
end of each page's discussion.

- **Home**: 0 items. (#16 withdrawn on re-read.)
- **Teams**: 4 items shipped — #11, #12, the opponent stacked-bar
  name-as-rivalry-link (audit's "selected-opponent buttons" item,
  reinterpreted per user: name → `/head-to-head?mode=team`, bar →
  selector, stopPropagation on the link). Plus a bug caught during
  the walk: tab-switch was leaking the tab-local `vs=` param into
  every other tab — fixed in the same batch via
  `setUrlParams({ tab, vs: '' })`.
- **Players**: 0 items. Re-verified independently; all player-name
  renderings use `<Link>` or `PlayerLink`; nationalities use
  FlagBadge with `linkTo`; ScopeIndicator already wired for
  `filter_team` arrivals.
- **Batting**: 3 items shipped — #3 (hybrid), #21 opponent link,
  new tournament-column link found during re-verify.
- **Bowling**: 3 items shipped — mirror of Batting (#4 hybrid,
  opponent link, tournament link).
- **Fielding**: 3 items shipped — #5 + #6 (Victims name link,
  micro-menu removed entirely since no meaningful H2H for a
  fielder, which fixes the broken-`&bowler=` bug naturally).
  Opponent + tournament columns linked in BOTH the fielding and
  keeping innings-list tables.
- **Series**: 5 buckets shipped — Records tab (4 cells via new
  `renderBatterPair` + `renderVsTeams(FromString)` helpers),
  Partnerships tabs (4 cells, structured data), Editions table
  (champion, runner-up, top scorer, top wicket-taker — new finding
  not in original audit), and shortened per-row tournament context
  label (`in {long tournament name}` → `tournament` when no other
  scope; drops entirely when team/rivalry is also set, since those
  now communicate the scope). Knockouts + Matches venue cells
  deferred to the venue-cell sweep.
- **HeadToHead**: 2 items shipped — suggestion tiles now render
  identically to Series landing tiles (CSS reset on `.wisden-tile`
  for button-defaults), and by-match tournament column linked.
  Venue cells deferred to the venue-cell sweep.
- **Matches + Scorecard**: 3 items shipped — Matches list date
  cell is now a `<Link>`, Matches venue cell uses canonical venue
  name linked via `filter_venue`, and Scorecard meta-line venue is
  linked similarly. Team-name scope ambiguity (team links carry
  `tournament=` context, no escape to overall view; compounded by
  transient bilateral series names) **punted** — documented in
  `design-decisions.md` as "disambiguate via a `TeamLink`
  component (revisit)". Ditto the cross-site "India link means
  different things" disambiguation.
- **Scorecard (pure-frontend)**: 3 items shipped — breadcrumb
  above the h2 (`Tournament › Season › All matches`) as a
  deep-link escape hatch, toss-winner team name linked,
  innings-header team prefix linked in `InningsCard`. API-
  dependent items (player_of_match, dismissal text, did-not-bat,
  fall-of-wickets) documented as a single response-shape follow-up
  in `design-decisions.md` — "Scorecard linkability: API
  response-shape follow-up".

## For the next session

Recommend tackling in this order (remaining items):

1. **Scorecard orientation (items 1, 2).** Breadcrumb + player-of-match
   link — both pure-frontend, both high-user-value.
2. **Matchup-table refactor (items 3–6).** One shared fix across
   three pages + the fielding h2h bug.
3. **HeadToHead suggestion-tile styling (item 7).** Low code, high
   discoverability.
4. **Venue-cell sweep (items 8, 10, 15).** Consistent with the
   Phase-2 venue filter.
5. **Match-list date alignment (item 9).** Small, purely additive.
   (Item 16 was withdrawn — Home fixtures already wrap the whole row
   in a `<Link>`.)
6. **Series Records / Partnerships link-up (items 13, 14).**
7. **Scorecard API + innings header (items 17–20).** The only items
   that require a backend change.
