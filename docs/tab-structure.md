# CricsDB tabs, subtabs, and filtering scheme

This page maps each page and tab of the site to its URL and to the API endpoints behind it. It is a
structural reference for agents and other models that must turn a question in plain English into the
right page or API endpoint. The conversational tour for people is
[`frontend/src/content/user-help.md`](https://github.com/rahuldave/cricsdb/blob/main/frontend/src/content/user-help.md),
which the site shows at <https://t20.rahuldave.com/help/usage>. The full API catalog is
[`docs/api.md`](./api.md).

The site is at <https://t20.rahuldave.com>. All pages are React routes over a FastAPI backend at
`/api/v1/*`. Every selection lives in the URL search parameters, for example the filters, the picked entity
and the active subtab. The design contract is that a shared link opens the same view. So an agent
can tie each answer back to a URL that anyone can open again.

---

## 1. Top-level routes

| Route | Page | Purpose |
|---|---|---|
| `/` | Home | Landing page, with the masthead, coverage stats and recent fixtures. |
| `/series` | Series | Competitions (IPL, T20 WC, Vitality Blast and others) and bilateral rivalries (India vs Australia, Ashes T20 and others). Cricket uses "series" for both senses. |
| `/teams` | Teams | Team dossier, with win and loss, batting, bowling, fielding, partnerships, roster, the Compare tab, Records and the match list. |
| `/players` | Players | One person's overview that stacks every discipline, and a compare view of N players. |
| `/batting` | Batting | Deep batting page, with by-season, by-over, by-phase, the vs-bowlers scatter, dismissals, inter-wicket, innings list and records. |
| `/bowling` | Bowling | Deep bowling page, the sibling of batting. |
| `/fielding` | Fielding | Deep fielding page, with by-season, by-over, by-phase, dismissal types, victims, innings list and records. |
| `/head-to-head` | Head to Head | Matchups of two sides, either Player vs Player or Team vs Team. |
| `/venues` | Venues | Directory of venues grouped by country, and a dossier for each venue. |
| `/matches` | Matches | Searchable list of every match. |
| `/matches/:matchId` | MatchScorecard | Full scorecard, innings grid, worm chart and matchup grid. |
| `/help` | Help | About the project. |
| `/help/usage` | HelpUsage | The user manual (`user-help.md`), rendered. |

On a desktop, the navigation bar groups `/batting`, `/bowling` and `/fielding` under a **Players ▾** menu
that opens on hover. The separate `/players` route is the entry point for the overview across all
disciplines.

---

## 2. Subtabs by page

Every page in the style of a dossier has a strip of subtabs, set by `?tab=<name>`. The active subtab is
part of the shared link. The default subtab is `Overview` on `/series`, `/venues` and Team vs Team on
`/head-to-head`, and `By Season` on `/teams` and the discipline pages. On `/teams`, a link with a compare slot and no
`tab` opens on Compare.

### `/series` (Tournaments + Rivalry dossier)

The URL takes `?tournament=<name>`, or `?filter_team=<X>&filter_opponent=<Y>` for a rivalry. The empty
landing page shows a tile for every tournament and for every bilateral rivalry, for men and for women.

| Subtab | URL | What it shows |
|---|---|---|
| Overview | `?tab=Overview` (default) | Headline summary, top-line winners and knockouts. |
| Editions | `?tab=Editions` | A rollup for each edition, only when a single tournament is bound and not a rivalry. |
| Points | `?tab=Points` | Points table, only for a single tournament and a single season. |
| Batting | `?tab=Batting` | Top batters by average and strike rate (SR), and a "Picked batter" tile of scope stats through `?series_batter=<id>`. |
| Bowling | `?tab=Bowling` | Top bowlers by SR and economy, and a "Picked bowler" tile through `?series_bowler=<id>`. |
| Fielding | `?tab=Fielding` | Top fielders by dismissals, keeper dismissals and run-outs, and "Picked fielder" through `?series_fielder=<id>`. |
| Partnerships | `?tab=Partnerships` | Largest partnerships overall, and the top 10 for each wicket (1st to 10th). |
| Records | `?tab=Records` | 8 record lists: highest team totals, lowest all-out, biggest wins by runs and by wickets, largest partnerships, best individual batting, best bowling figures and most sixes in a match. |
| Matches | `?tab=Matches` | Full match list, in pages. |

The picked-player tiles on Batting, Bowling and Fielding are independent of each other, and each keeps its
pick for the session. Only the pick of the active subtab shows in the URL.

### `/teams` (Team dossier)

The URL takes `?team=<name>`. The empty landing page shows the directory of international teams and club
teams. The international teams are the full members and associates, for men and for women. The club teams
are the franchise leagues, the women's franchise leagues and the domestic championships.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | `?tab=By%20Season` (default) | Wins and losses for each season, and a summary row. |
| vs Opponent | `?tab=vs%20Opponent` | Stacked bars for each opponent, and a bubble matrix. |
| Compare | `?tab=Compare` | Up to 3 columns side by side, across Results, Batting, Bowling, Fielding and Partnerships. |
| Batting | `?tab=Batting` | Team batting aggregates: summary, by-season, by-phase, by-inning, top batters and a heatmap of phase by season. |
| Bowling | `?tab=Bowling` | Team bowling aggregates, in the same shape. |
| Fielding | `?tab=Fielding` | Team fielding aggregates, in the same shape. |
| Partnerships | `?tab=Partnerships` | Team partnerships: summary, by-season, by-wicket, best pairs, heatmap and top. |
| Players | `?tab=Players` | Roster for each season (appearances in the XI), with batting average, bowling SR and the turnover from year to year. |
| Records | `?tab=Records` | Records of the subject team: 8 lists in the same shape as the `/series` Records, scoped to "team X's". |
| Match List | `?tab=Match%20List` | Match list in pages, with a filter on the result (won, lost or tied). |

The **Splits Mosaic** sits above the panels on Teams, and it is also a filter. A click on a cell sets
`?toss_outcome=`, `?inning=` and `?result=` to the coordinates of that cell.

### `/players` (Single + N-way compare)

The URL takes `?player=<id>` for one player, and `?player=<id>&compare=<id2>&compare=<id3>` for a
comparison. The page stacks a band for Batting, then Bowling, then Fielding, then Keeping for each player.
Each band has an "Open <discipline> page →" link, which carries the scope of the FilterBar to that page.
A comparison holds players of one gender only, and the gender chip of the FilterBar enforces it.

The page has no subtabs. The browser composes it from `/batters/{id}/summary`, `/bowlers/{id}/summary`,
`/fielders/{id}/summary` and `/fielders/{id}/keeping/summary`.

When one player is picked, the page also shows a short Records section with the top 5 across disciplines.
It comes from `/batters/{id}/records`, `/bowlers/{id}/records` and `/fielders/{id}/records`.

**Inline baseline visual** (shipped 2026-05-20). Every numeric stat tile on the player bands shows a
stack of three parts. They are the value in bold, a `vs base N` subtitle and a coloured chip for the
difference.

The baseline is a cohort weighted by the player's own mix. A cohort is the group of players in the same
scope. Batting uses 10 position buckets (opener, and #3 to #11). Bowling uses 20
buckets, one for each over. Fielding uses a binary flag, keeper or not. The backend computes the baseline
in the same process from the matching `/api/v1/scope/averages/players/<disc>/summary` endpoint, and adds
it to the existing /summary round trip.

Hover over the `vs base N` text to see how the cohort is described, with the player's mix and the size
of the cohort. Each column of the compare grid shows an inline chip for the difference, from the mix of
that column's player. The spec is `docs/internal/spec-player-compare-average.md`.

### `/batting` (Batter deep dive)

The URL takes `?player=<id>` for a single batter. The landing view, with no player, shows the top 10 by
average and by SR for the current scope.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | `?tab=By%20Season` (default) | The career, season by season. |
| By Over | `?tab=By%20Over` | Runs, SR and the distribution of dismissal overs, for each over (1 to 20). |
| By Phase | `?tab=By%20Phase` | Powerplay (overs 1 to 6), Middle (7 to 15) and Death (16 to 20). |
| vs Bowlers | `?tab=vs%20Bowlers` | Scatter and table of matchups: SR against average, with the dot size for balls faced. |
| Dismissals | `?tab=Dismissals` | Dismissal donut by kind, by phase and by the primary type of bowler. |
| Inter-Wicket | `?tab=Inter-Wicket` | Runs and rate in each span between wickets. |
| Innings List | `?tab=Innings%20List` | Innings list, in pages. |
| Records | `?tab=Records` | 6 lists: highest scores, fastest 50s and 100s, most sixes and most fours in an innings, and best strike rates. |

### `/bowling` (Bowler deep dive)

The URL takes `?player=<id>`. The landing page shows the top 10 by SR and by economy.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | default | The career, season by season. |
| By Over | `?tab=By%20Over` | Economy and SR for each over. |
| By Phase | `?tab=By%20Phase` | Economy and SR in the powerplay (PP), Middle and Death. |
| vs Batters | `?tab=vs%20Batters` | Matchup table by batter. |
| Wickets | `?tab=Wickets` | Wicket analysis: by kind, by phase, by batter, and the distribution of dismissal overs. |
| Innings List | `?tab=Innings%20List` | Innings list, in pages. |
| Records | `?tab=Records` | 2 lists: best figures, and most economical (at least 18 balls, which is 3 overs). |

### `/fielding` (Fielder + keeper deep dive)

The URL takes `?player=<id>`. The landing page shows the top fielders by dismissals and the top keepers by
keeper dismissals.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | default | Dismissals for each season, split by kind. |
| By Over | `?tab=By%20Over` | Dismissal counts for each over. |
| By Phase | `?tab=By%20Phase` | Dismissals in PP, Middle and Death. |
| Dismissal Types | `?tab=Dismissal%20Types` | Donut of the percentages of catches, stumpings, run-outs and caught-and-bowled (c&b). |
| Victims | `?tab=Victims` | Batters that this fielder dismissed, ranked. |
| Innings List | `?tab=Innings%20List` | Fielding credits for each innings. |
| Records | `?tab=Records` | 3 lists: most catches in a match, most stumpings and most dismissals. |

### `/head-to-head` (Player vs Player OR Team vs Team)

The URL takes `?batter=<id>&bowler=<id>` for Player vs Player (PvP), and `?team=<X>&vs=<Y>` for Team vs
Team (TvT). A "Show" pill at the top narrows the matches to one category of series. The categories are All,
Bilateral T20Is, ICC events and Club tournaments. The Show pill works together with the FilterBar, because it sets a value
of `series_type`.

Team vs Team uses the same shape as the `/series` dossier, with the subtabs Overview, Batting, Bowling,
Fielding, Partnerships, Records and Matches. The only difference is the scope, which is the set of matches between
the two teams.

### `/venues` (Venue dossier)

The URL takes `?venue=<name>`. The landing page shows tiles grouped by country, and a search box filters
them by name or city.

| Subtab | URL | What it shows |
|---|---|---|
| Overview | default | Average first-innings total, the win % batting first against chasing, the split of toss decisions and how they relate to the result, the boundary % and dot % in each phase, and the ground records. |
| Batters | `?tab=Batters` | Top batters at this venue. |
| Bowlers | `?tab=Bowlers` | Top bowlers at this venue. |
| Fielders | `?tab=Fielders` | Top fielders at this venue. |
| Matches | `?tab=Matches` | Full match list at this venue. |
| Records | `?tab=Records` | Record lists scoped to the venue. |

### `/matches` (Match list)

The URL is `/matches?…filters…`, and the page has no subtabs. A click on a row opens `/matches/:matchId`,
with the full scorecard, the innings grid, the worm chart and the matchup grid. Each team name in a row
has a small `(ed)` link. That link opens the team's page, scoped to the edition of THIS match (its
tournament and season), whatever the FilterBar holds.

---

## 3. The FilterBar (sticky across pages)

The FilterBar is a row of dropdowns at the top of every page, except `/` and `/matches/:matchId`. Its
state lives in the URL query parameters, and it stays the same as you move between pages. For example,
set Gender to Men once, and every page shows men's data until you change it.

### FilterBar fields (`FilterBarParams` in the API)

| URL param | Values | What it filters | Notes |
|---|---|---|---|
| `gender` | `male` / `female` | `match.gender` | |
| `team_type` | `international` / `club` | `match.team_type` | International means national teams (T20Is). Club means every franchise and domestic league. |
| `tournament` | string | `match.event_name` | Knows the canonical names. "T20 World Cup (Men)" expands to the IN-list of the cricsheet variants (`ICC World Twenty20` / `World T20` / `ICC Men's T20 World Cup`). |
| `season_from` | string | `match.season >= …` | Cricsheet seasons mix calendar years (`"2024"`) and split years (`"2024/25"`). A sort by the text of the labels gives the order in time. |
| `season_to` | string | `match.season <= …` | The range includes both ends. |
| `filter_venue` | string | `match.venue` (exact canonical name) | The import gives each venue string its canonical form through `api/venue_aliases.py`. The Venue typeahead returns the canonical form. |
| `series_type` | `all` / `bilateral` / `icc` / `club` | Match category | `bilateral` means international and not ICC. `icc` means ICC tournaments. `club` means `team_type=club`. The old values `bilateral_only` / `tournament_only` map to `bilateral` / `icc`. The Series Type dropdown still sends the old values. |
| `team_class` | `full_member` / `primary_club` / `secondary_club` | Tier within team_type | `full_member` (international): both teams are ICC full members. `primary_club` (club): a marquee international franchise league (IPL/BBL/PSL/CPL/SA20/ILT20/LPL/MLC/Hundred/WBBL/WPL/WCSL). `secondary_club` (club): a domestic state or county league. A combination across types changes nothing, and gives no error. |
| `filter_team` | string | Depends on the page: narrows to matches that involve this team | The FilterBar has no control for it. Player-team links and rivalry links set it. |
| `filter_opponent` | string | Depends on the page: narrows to matches against this opponent | The FilterBar has no control for it. The Versus dropdown of the player pages sets it, and so do rivalry links. With `filter_team`, it gives a rivalry of two teams. |

The season pickers have buttons for a quick choice:

- `all-time` clears the season range.
- `latest` sets both ends to the most recent season in the current filter scope. So with
  Tournament=BBL, it moves to the current BBL season, and not to the current IPL season.
- `reset all` clears every filter.

The landing pages of Batting, Bowling and Fielding set the season range to the **last 3 seasons** by
default, because users rarely want the unfiltered view of all time. Click `all-time` to widen it.

### Page-local Aux filters (`AuxParams`)

The aux filters are not part of the sticky FilterBar. Each applies only to the current page. The same
endpoints read them through FastAPI `Depends()`. Their state is in the URL, so a shared link still opens
the same view.

| URL param | Values | What it filters | Notes |
|---|---|---|---|
| `inning` | `0` / `1` | 1st innings (batted first) / 2nd innings (chased) | The meaning in the URL is fixed (`innings.innings_number`). The label of the pill depends on the point of view, through `useDiscipline()`. Spec: `docs/internal/spec-inning-split.md`. |
| `result` | `won` / `lost` / `tied` | Match outcome from the point of view of the path team | Meant for a team bound by `?team=` or the path. No endpoint rejects it without one: on `/teams/splits` it then narrows the team views of the landing. `tied` collapses ties, including those a super over decides, and no-results (rain-abandoned). |
| `toss_outcome` | `won` / `lost` | Toss outcome from the point of view of the path team | Meant for a team bound by `?team=` or the path. No endpoint rejects it without one. |
| `scope_to_team` | string | Narrows the average slot of the Compare tab | Limits the league baseline to the events in which the team played. The front end offers it only with `team_type=club`. |

### How filters compose

All filters combine with **AND**, and there is no OR mode. Two filters on different axes intersect, so
only the matches that satisfy both pass. An example is `tournament=Indian Premier League` with
`filter_venue=Wankhede Stadium, Mumbai`. The canonical name of a `tournament` widens to its IN-list, but
that wider list still combines by AND with every other filter.

The dropdowns are themselves narrowed to the scope. The Tournament dropdown lists only the tournaments
that have matches under the current Gender and Type. The Venue typeahead lists only the venues with matches
under the current scope. So a user usually cannot pick a combination that returns zero matches. A deep
link with conflicting filters can still do it, and then the endpoints return `matches: 0` rather than a
404.

### Cascade-clear rule

When a user clears a coupled filter (Gender or Team Type), the page also clears each filter that depends
on it (Tournament). Without this rule, the effects of the FilterBar that correct a deep link would set
the old value again from the tournament's metadata.

---

## 4. URL patterns for common queries

### "Kohli's IPL record"
```
/batting?player=ba607b88&tournament=Indian%20Premier%20League&gender=male&team_type=club&season_from=all-time
```
API: `GET /api/v1/batters/ba607b88/summary?tournament=…`

### "Bumrah's best bowling figures in T20Is"
```
/bowling?player=462411b3&team_type=international&gender=male&tab=Records
```
API: `GET /api/v1/bowlers/462411b3/records?team_type=international&gender=male`

### "Mumbai Indians chasing record at Wankhede"
```
/teams?team=Mumbai%20Indians&filter_venue=Wankhede%20Stadium%2C%20Mumbai&inning=1
```
API: `GET /api/v1/teams/Mumbai Indians/summary?filter_venue=Wankhede%20Stadium%2C%20Mumbai&inning=1`

### "India vs Australia in T20 World Cups"
```
/head-to-head?team=India&vs=Australia&tournament=T20%20World%20Cup%20(Men)&gender=male
```
API: `GET /api/v1/teams/India/vs/Australia?tournament=T20%20World%20Cup%20(Men)&gender=male`

### "IPL 2024 top batters by strike rate"
```
/series?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&tab=Batting
```
API: `GET /api/v1/series/batters-leaders?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024`

### "Records at Wankhede"
```
/venues?venue=Wankhede%20Stadium%2C%20Mumbai&tab=Records
```
API: `GET /api/v1/venues/Wankhede%20Stadium%2C%20Mumbai/summary` for the overview. The records come from
`/series/records` with `filter_venue=…`.

---

## 5. Reading conventions

- **Innings semantics.** `?inning=0` always means `innings.innings_number = 0`, the first half of the
  match, in which the first side batted. The label of the pill depends on the point of view, through
  `useDiscipline()`. On a batting page it reads "Batting first", and on bowling or fielding it reads
  "Bowling first". On the pages that mix disciplines (Players, and the Records subtabs) it stays neutral,
  as "1st innings".
- **`result` and `toss_outcome` are from the subject's point of view.** They make sense only when a path
  team is bound (the path `:team` or `?team=`). The endpoints do not reject either parameter without a
  team. On `/teams/splits`, without `?team=`, they narrow the team views of the landing, so
  `?toss_outcome=won` gives the league-wide picture for toss winners (see `docs/api.md`).
- **Series vs Tournament terminology.** Cricket uses "series" for both bilateral tours (India vs
  Australia) and tournament editions (IPL 2024). The `/series` tab covers both. `match.event_name` carries
  the identity of the tournament, and `filter_team` with `filter_opponent` defines a bilateral rivalry.
  The API path `/series/*` is the dossier of a tournament or a rivalry. `/tournaments` is only the list of
  `event_name`s for the FilterBar dropdown.
- **Volume vs rate framing.** Fielding leaderboards rank by total dismissals, a volume. Batting and
  bowling leaderboards rank by average, SR or economy, which are rates. A player must pass a minimum
  sample to be ranked. For batting averages it is 100 balls and 3 dismissals, and for bowling SR it is 60
  balls and 3 wickets. Each response returns the thresholds in its `thresholds` field, so the UI can show
  them in the caption of the table.
- **Catches include caught-and-bowled (Convention 3).** Every `/summary` and `/leaders` endpoint that
  shows a `catches` headline uses `kind IN ('caught', 'caught_and_bowled')`. The `/distribution` endpoint
  is the one exception. Its master sample has one row for each match a player played (from matchplayer),
  so it leaves out appearances as a substitute. There, `caught_and_bowled` is a sibling block under the
  bowling distribution, credited to the bowler.
- **DLS-shortened innings are included everywhere.** Take a chase of 90 runs that rain cuts short in
  over 12. It adds its 60 to 72 legal balls or so to every stat that divides by overs, and it counts as 1
  innings in every stat that divides by innings. No `target_overs` filter exists anywhere in the API.

---

## 6. Pointers

- **Full API reference:** [`docs/api.md`](./api.md) gives every endpoint with its path, query parameters,
  an example curl command and a shortened response.
- **Interactive API docs (Swagger).** <https://t20.rahuldave.com/api/docs>
- **OpenAPI schema (JSON):** <https://t20.rahuldave.com/api/openapi.json>
- **User manual:** [`frontend/src/content/user-help.md`](https://github.com/rahuldave/cricsdb/blob/main/frontend/src/content/user-help.md)
  is the tour for people, with screenshots.
- **`llms.txt`:** <https://t20.rahuldave.com/llms.txt> is the index for agents, and it points at all of
  the above.
- **Source code:** <https://github.com/rahuldave/cricsdb>
