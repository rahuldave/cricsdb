# Using CricsDB

## The shape of the site

Seven top-level tabs across the nav:

- **Tournaments** — the home for competitions (IPL, T20 World Cup,
  Vitality Blast, …) AND bilateral rivalries (India vs Australia,
  Ashes T20, …). Click a tournament tile to get its dossier
  (Overview, Editions, Points Table for a single edition, Batters,
  Bowlers, Fielders, Partnerships, Records, Matches). Click a
  rivalry tile to get the same dossier scoped to that team pair's
  bilateral series. Men's and women's rivalries are separate tiles.
- **Teams** — win/loss records, team batting/bowling/fielding,
  partnerships, roster by season. Start with a search or pick one
  of the teams listed on the landing board.
- **Batting / Bowling / Fielding** — player-level stats. The landing
  view shows the top 10 in each metric (by average, strike rate,
  economy, dismissals) filtered to the active season window. Click
  a player name to go deep.
- **Head to Head** — two-entity matchups. Two modes:
  - *Player vs Player* — any batter vs any bowler (summary, phase
    breakdown, season trend, match-by-match record).
  - *Team vs Team* — every meeting between two countries, bilateral
    series AND tournament matches combined. Toggle the "Show" pill
    between All meetings / Bilateral only / Tournament only. Suggest
    tiles below the picker for common matchups. Reuses the Tournaments
    dossier so the same tabs (Batters, Bowlers, Fielders, Partnerships,
    Records, Matches) apply.
- **Matches** — searchable list of every match. Click any row for
  the full scorecard, ball-by-ball innings grid, worm chart, and
  per-batter / per-bowler matchup grid.

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

Three little text buttons sit beside the season pickers:

- **`all-time`** — clears the season range.
- **`latest`** — pins both ends to the most recent season available
  in your current filter scope (so with Tournament = BBL set, it
  jumps to the current BBL season, not the current IPL).
- **`reset all`** — clears every filter at once.

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
or India vs Australia in the T20 World Cup.

Three ways to get there:

1. **Tournaments landing** → bilateral-rivalry tiles (men's or women's).
   These open to "pure bilateral series only" — no World Cup meetings
   mixed in.
2. **Head to Head → Team vs Team** → all meetings combined by default,
   with a Show pill to narrow to Bilateral only or Tournament only. Set
   a tournament in the FilterBar to see "India vs Australia across all
   T20 World Cups". Set a season range to scope by year.
3. **Teams → vs Opponent tab → "See full rivalry →"** link, which opens
   the full dossier in Head to Head.

All three land at the same dossier. The URL just expresses different
default filters.

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
