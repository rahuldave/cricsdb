# Using CricsDB

![T20 & CricsDB homepage](/social/01-homepage.png)
*The front door — masthead, coverage, recent fixtures, departments.*

## The shape of the site

Six top-level tabs across the nav (the three discipline pages now
sit inside a **Players ▾** group — hover on desktop, sub-row on mobile):

- **Series** — the home for competitions (IPL, T20 World Cup,
  Vitality Blast, …) AND bilateral rivalries (India vs Australia,
  Ashes T20, …). Cricket uses "series" for both a bilateral tour
  and a tournament edition, so this tab covers both. Click a
  tournament tile to get its dossier (Overview, Editions, Points
  Table for a single edition, Batters, Bowlers, Fielders,
  Partnerships, Records, Matches). Click a rivalry tile to get the
  same dossier scoped to that team pair's bilateral matches.
  Men's and women's rivalries are separate tiles.

![Series landing — tournament + rivalry tiles](/social/06-series-landing.png)
*Series tab — every competition + every men's and women's bilateral rivalry, in tiles.*

![India vs Australia rivalry dossier](/social/08-rivalry-dossier.png)
*A bilateral rivalry dossier — 37 meetings, by-team breakdowns below the unified summary.*

On the Series dossier's **Batters**, **Bowlers**, and **Fielders**
subtabs, the upper-left slot has a scope-aware typeahead (**Picked
batter** / **Picked bowler** / **Picked fielder**). Pick any player
who features in the current match-set — the card fills with their
in-scope runs / wickets / dismissals / economy / SR / average,
alongside the leaderboards in the other quadrants.

Each tab's pick is independent and sticky for the session. Pick
Kohli on Batters, switch to Bowlers and pick Jadeja, then click
back to Batters — Kohli is still there. Only the active tab's pick
shows up in the URL (as `series_batter` / `series_bowler` /
`series_fielder`), so share links stay clean; the other two tabs'
picks are held in session storage until you return to their tab or
close the browser tab. Share a Batters URL with a friend and they
see only your Batters pick — your Bowlers pick doesn't leak.

An inline **× clear** button next to the search input removes the
current tab's pick. If you narrow filters after picking and your
choice no longer has data in the new scope, the card shows a "No
data…" note until you clear or pick someone else.

- **Teams** — win/loss records, team batting/bowling/fielding,
  partnerships, roster by season, plus a **Compare** tab that stacks
  up to three teams side by side across Results / Batting / Bowling /
  Fielding / Partnerships — same shape as the player comparison.
  Comparison is single-gender and single-type (international teams
  only compare with internationals; club teams only with clubs) —
  both constraints are enforced automatically via the filter bar.

![India team dossier — summary stats + tabs](/social/03-team-overview.png)
*A team dossier — summary row, keepers used, By Season / vs Opponent / Compare / Batting / Bowling / Fielding / Partnerships / Players / Match List tabs.*

The landing board is two columns:
  - *Left*: international — men's (full members + associate) and
    women's (full members + associate) — plus domestic / national
    championships below them (Syed Mushtaq Ali, Vitality Blast, CSA
    T20). Grouped together because national-level cricket has a
    different flavour than franchise.
  - *Right*: franchise leagues (IPL, BBL, …), women's franchise
    leagues (WBBL, WPL, …), and other tournaments.
  Each section is a collapsible — only the high-traffic ones (men's
  full members, top franchise leagues) are open by default. Each
  entry is tagged "men's" or "women's" when no gender filter is set,
  so "India men's" and "India women's" appear as separate clickable
  rows.
- **Players ▾** — person-focused home that collects batting, bowling,
  fielding, and keeping on one page, with an N-way comparison mode.
  See the dedicated section below — this is where you come for a
  player's full career at a glance. The three discipline pages
  (Batting / Bowling / Fielding) are still there as sub-routes; the
  desktop hover-dropdown and the mobile sub-row both surface them.
  Use the discipline pages for the deep stats (phase splits,
  matchup scatter, inter-wicket, dismissal analysis, season trend);
  use Players for the overview + comparisons.

![Kohli single-player view](/social/10-player-single.png)
*A single-player view stacks every discipline the player has data in. Role classifier adapts to the current scope.*
- **Batting / Bowling / Fielding** (under Players) — player-level
  deep dives. The landing view on each shows the top 10 by the
  role's core metrics (average, strike rate, economy, dismissals)
  filtered to the active season window. Click a player name to go
  deep.

![Kohli vs Bowlers scatter chart](/social/12-batting-vs-bowlers.png)
*Batting page has a signature vs-Bowlers scatter — strike rate × average, dot size = balls faced. Click a row in the table to highlight that bowler's dot.*
- **Head to Head** — two-entity matchups.

![Kohli vs Bumrah head-to-head](/social/14-h2h-player.png)
*Player vs player — summary, dismissal donut, SR by phase, SR by season, runs by over, every match.*

Two modes (picker at the top of the page):
  - *Player vs Player* — any batter vs any bowler (summary, phase
    breakdown, season trend, match-by-match record). A "Show" pill
    narrows by series category: All meetings (default) /
    **Bilateral T20Is** (international tours only) / **ICC events**
    (T20 World Cup, Asia Cup) / **Club tournaments** (IPL, BBL, …).
    Three separate questions, three separate answers. For Kohli vs
    Bumrah (India teammates), the bilateral and ICC slices are empty
    — they never face each other in international cricket — but the
    club slice has their full IPL record. The empty picker shows a
    "Popular matchups" grid (Kohli–Bumrah, Mandhana–Perry, …) so you
    can jump in without typing.
  - *Team vs Team* — every meeting between two teams, bilateral
    series AND tournament matches combined. Same four-way "Show" pill.
    The empty picker has four tile sections: men's international
    rivalries, women's international rivalries, men's club rivalries
    (CSK v MI in IPL, etc.), and women's club rivalries. Reuses the
    Series dossier so the same tabs (Batters, Bowlers, Fielders,
    Partnerships, Records, Matches) apply.

  The Show pill composes with the FilterBar filters at the top of
  every page — gender / type / tournament / season range all apply
  on top. To keep "All" honest, the pill adapts:
  - With no Type filter: all four options shown; "All meetings"
    means genuinely every meeting.
  - With `Type = International`: Club option is hidden and the "All"
    button reads "All international" (bilateral + ICC combined).
  - With `Type = Club`: the pill collapses to a small
    "Showing: Club tournaments" caption — every option would select
    the same rows, so there's nothing to pick.
- **Venues** — directory of every ground that's hosted a match,
  grouped by country (India has 78 venues in the dataset, England
  38, Australia 56, …). The top three countries open by default and
  the long tail of associate nations (Rwanda, Bhutan, …) stays
  collapsed. A search box at the top filters tiles instantly as
  you type — "mumbai" surfaces Wankhede, Brabourne, DY Patil, BKC
  Ground, and Sharad Pawar Academy in one sweep regardless of what
  country they're nominally grouped under. Click a tile to open
  that ground's **dossier** —
  headline match count, average first-innings total, bat-first vs
  chasing win %, toss-decision split + win correlation, boundary %
  and dot % per phase (powerplay / middle / death), ground-record
  highest total and lowest all-out, plus matches hosted broken down
  by tournament × gender × season. Sub-tabs show the top batters,
  bowlers, fielders, and full match list at that venue (all
  filter-sensitive). A "view all matches →" link on the dossier
  opens the bare list for users who want to skip the tabs. To scope
  any other tab by venue instead, use the **Venue** typeahead in
  the filter bar (see the filter-bar section below) — venue-
  filtered stats work across Teams, Players, Head-to-Head, Series
  and Matches.
- **Matches** — searchable list of every match. Click any row for
  the full scorecard, ball-by-ball innings grid, worm chart, and
  per-batter / per-bowler matchup grid. Every team name in a row
  is followed by a small italic "ed" link — that opens the team's
  page scoped to THIS match's edition (tournament + season),
  independent of whatever season range your FilterBar has set. The
  same "ed" convention appears on every dense table in the app
  (Series Records, Series Overview Knockouts / Champions, Venue
  Matches) — a caption explaining it sits above each such table.

![2024 T20 World Cup Final scorecard](/social/17-scorecard-full.png)
*Full match page — scorecard for both innings, worm chart, innings grid, fall of wickets, matchup grid.*

## The Players tab

`/players` answers "who is this player?" before any discipline-
specific question.

**Single-player view** — pick a player from the search box (or click
a curated tile on the landing) and you get a stack of discipline
bands: Batting → Bowling → Fielding → Keeping. Each band has the
top-level numbers for that discipline and a `→ Open <discipline>
page` link that carries every active filter through to the deep-dive.

An identity line under the name summarises the scope's shape:
*"specialist batter · 388 matches"* or *"all-rounder · 212 matches"*
or *"keeper-batter · 240 matches"*. Bands hide themselves when the
player has no data for that discipline in the current scope — a
specialist batter's page won't waste a row on their empty bowling
line, and Bumrah's batting band won't appear if the scope window
starts after his last T20I.

The role label is computed fresh each time: narrowing the scope
to a single tournament can truthfully flip someone from "specialist
batter" to "all-rounder" if they bowled meaningfully there.

**Comparison mode** — enter a second player via the *Compare with
another player…* box beneath the single-player view, or click any of
the *Popular comparisons* tiles on the landing. You get two columns
side-by-side with aligned discipline bands; a disciple without data
in one column shows a dim "— no bowling in scope —" placeholder so
the rows stay level. Add a third player with the `+ Add another…`
picker that appears when only two are compared.

![3-way compare — Kohli vs Williamson vs Smith](/social/11-player-compare.png)
*Side-by-side 3-way compare. Columns use a compact label/value layout so they fit narrow widths; remove one via the ✕ at the top of each column.*

Comparison is single-gender — men vs men or women vs women. Trying
to add a women's player to a men's comparison (or vice versa)
surfaces an inline refusal; the FilterBar's gender chip is the way
to switch.

Filters apply globally. Narrow to IPL and every column shows IPL-
only numbers; add a rivalry lens (click a context link like "· vs
Australia ›" elsewhere in the app) and the whole comparison is
scoped to that rivalry.

## The filter bar

Every page (except the home page and individual match scorecards)
carries a filter bar at the top. It's **sticky** — the scope you
set on one page follows you around until you change it.

- **Gender** — Men / Women (or All).
- **Type** — International / Club (or All). International is
  national-team T20Is; Club covers every franchise league in the
  dataset (IPL, BBL, CPL, PSL, WBBL, WPL, and many more).
- **Tournament** — narrow to one competition. The dropdown is
  scoped to the gender / type you've picked. T20 World Cup variants
  across cricsheet history (ICC World Twenty20 / World T20 / ICC
  Men's T20 World Cup) are merged into a single canonical entry —
  picking it narrows everything across all three names.
- **Seasons** — `From ... To ...` range. Cricsheet uses a mix of
  calendar years (`2024`) and split-year labels (`2024/25`);
  sorting is chronological.
- **Venue** — search for a ground by name or city (type at least
  two letters). The dropdown narrows to the current filter scope —
  picking India + Men and typing "eden" will show Eden Gardens if
  India men's have played there. Once a venue is set, the input
  flips to a compact chip with a dedicated **× Clear venue** button;
  the chip stays visible on every tab so you always know your data
  is scoped, and one click clears it wherever you are.

Three little text buttons sit beside the season pickers:

- **`all-time`** — clears the season range.
- **`latest`** — pins both ends to the most recent season available
  in your current filter scope (so with Tournament = BBL set, it
  jumps to the current BBL season, not the current IPL).
- **`reset all`** — clears every filter at once (including venue).

The Batting, Bowling, and Fielding pages default the season range
to the **last 3 seasons** on first visit, because the unfiltered
all-time view is rarely what people actually want. You can always
click `all-time` to widen it.

## Reading the landings

**Top-10 batters** are ranked by batting average and by strike
rate. We exclude tiny-sample innings so a one-ball 4* doesn't top
the list (the exact thresholds are shown under the tables).

**Top-10 bowlers** — strike rate (balls per wicket) and economy
(runs per over). Same thresholding.

**Top fielders** are volume-based (total catches + stumpings + run
outs + caught-and-bowled). Rate metrics don't work here — catches
per match is mostly a position / opportunity stat, not a skill
stat.

**Top keepers** filters fielding credits to innings where the
person was the designated wicketkeeper, using our best-effort
inference (see spec in the repo). Some innings are ambiguous and
are flagged rather than guessed.

## Rivalries and cross-team analysis

A rivalry isn't a separate screen — it's the same tournament-style
dossier, just scoped to two teams instead of one tournament. That means
every question you can ask about IPL ("top partnerships", "best bowling
figures", "match records") you can also ask about India vs Australia,
India vs Australia in the T20 World Cup, or CSK vs Mumbai Indians in
IPL.

Three ways to get there:

1. **Series landing** → bilateral-rivalry tiles (men's or women's).
   These open to "pure bilateral series only" — no World Cup meetings
   mixed in.
2. **Head to Head → Team vs Team** → all meetings combined by default,
   with a Show pill to narrow to Bilateral only or Tournament only. Set
   a tournament in the FilterBar to see "India vs Australia across all
   T20 World Cups". Set a season range to scope by year. Below the
   picker: men's + women's international rivalries AND men's + women's
   club rivalries (CSK v MI in IPL, RCB v MI, etc.) as suggestion tiles.
3. **Teams → vs Opponent tab → "See full rivalry →"** link, which opens
   the full dossier in Head to Head.

All three land at the same dossier. The URL just expresses different
default filters.

**Scoped player pages.** From a tournament dossier or a rivalry
dossier, a small italic "context link" sits next to each player name
(`· at Mumbai Indians ›`, `· vs Australia ›`). Clicking the plain
name opens the player's page un-scoped; clicking the context link
opens it narrowed to that lens. The narrowed page shows an oxblood
pill under the player header — "Scoped to Mumbai Indians" or "Scoped
to India vs Australia" — with a `CLEAR` button that lifts the lens
back to the full career without changing player or gender.
FilterBar auto-fills team_type / gender (and for single-tournament
rivalries like MI × CSK, the tournament too) so the dropdowns reflect
the scope at a glance.

![Kohli on /batting, scoped to India vs Australia](/social/18-filter-rivalry.png)
*Scope pill + auto-filled FilterBar. The "Scoped to India vs Australia" pill has a one-click CLEAR that returns the page to full career.*

### Why the same team name appears twice

Cricsheet uses the same string for men's and women's national sides
("India" plays as both). The Teams landing and the H2H rivalry tiles
disambiguate by appending "men's" / "women's" to each entry — clicking
sets the gender filter so the page narrows correctly. With a gender
filter already applied, the suffix disappears.

For franchise teams, the same string can mean different sides too —
"Royal Challengers Bengaluru" is both the men's IPL side and the
women's WPL side. Same disambiguation rule.

## What's NOT in the data

- **Afghanistan men's and women's cricket** is missing. Cricsheet
  doesn't publish their matches, for reasons only they know. Every
  other full-member nation is present.
- **Commentary** — there's no natural-language ball-by-ball text.
  The innings grid and worm chart visualise the same information.
- **Videos, photos, player bios** — not the point of this site.
  Cricinfo and the national boards remain the places for those.
- **Super-over deliveries** — stored but generally excluded from
  leader boards; they'd muddy averages with 1–6 ball samples.

## If something looks wrong

The repo is on [GitHub](https://github.com/rahuldave/cricsdb).
Open an issue with the URL and what looked off. Ball-level bugs
(a wrong dismissal, a mis-attributed catch) are usually a
cricsheet source quirk that we could either fix upstream or patch
with a resolution file.
