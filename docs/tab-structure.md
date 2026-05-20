# CricsDB — Tabs, Subtabs, and Filtering Scheme

This is a structural reference for agents and downstream models that
need to map a natural-language question onto the right page or API
endpoint. For the conversational human-facing tour, see
[`frontend/src/content/user-help.md`](../frontend/src/content/user-help.md)
(rendered at <https://t20.rahuldave.com/help/usage>). For the full API
catalog, see [`docs/api.md`](./api.md).

Site: <https://t20.rahuldave.com>. All pages are React routes over a
FastAPI backend at `/api/v1/*`. Every selection (filters, picked
entity, active subtab) lives in URL search params — share-link
round-trip is the design contract, so any answer an agent gives can
be tied back to a reproducible URL.

---

## 1. Top-level routes

| Route | Page | Purpose |
|---|---|---|
| `/` | Home | Landing — masthead, coverage stats, recent fixtures. |
| `/series` | Series | Competitions (IPL, T20 WC, Vitality Blast, …) AND bilateral rivalries (India vs Australia, Ashes T20, …). Cricket uses "series" for both senses. |
| `/teams` | Teams | Team dossier — win/loss, batting, bowling, fielding, partnerships, roster, Compare tab, Records, match list. |
| `/players` | Players | Person-focused — single-player overview that stacks every discipline, plus N-way compare. |
| `/batting` | Batting | Deep batting page — by-season, by-over, by-phase, vs-bowlers scatter, dismissals, inter-wicket, innings list, records. |
| `/bowling` | Bowling | Deep bowling page — sibling of batting. |
| `/fielding` | Fielding | Deep fielding page — by-season, by-over, by-phase, dismissal types, victims, innings list, records. |
| `/head-to-head` | Head to Head | Two-entity matchups — Player vs Player OR Team vs Team. |
| `/venues` | Venues | Country-grouped venue directory + per-venue dossier. |
| `/matches` | Matches | Searchable list of every match. |
| `/matches/:matchId` | MatchScorecard | Full scorecard, innings grid, worm chart, matchup grid. |
| `/help` | Help | About / project context. |
| `/help/usage` | HelpUsage | Rendered user manual (`user-help.md`). |

The nav groups `/batting`, `/bowling`, `/fielding` under a **Players ▾**
hover-menu on desktop; the standalone `/players` route is the entry
point for the cross-discipline overview.

---

## 2. Subtabs by page

Every dossier-style page exposes a subtab strip via `?tab=<name>`.
Active subtab is part of the share link; default subtab is `Overview`
(or `By Season` on the discipline pages).

### `/series` (Tournaments + Rivalry dossier)

URL: `?tournament=<name>` OR `?filter_team=<X>&filter_opponent=<Y>`.
The empty landing shows tiles for every tournament + every bilateral
rivalry (men's + women's).

| Subtab | URL | What it shows |
|---|---|---|
| Overview | `?tab=Overview` (default) | Headline summary, top-line winners, knockouts. |
| Editions | `?tab=Editions` | Per-edition rollup (only when a single tournament is bound, not a rivalry). |
| Points | `?tab=Points` | Points table (only when a single tournament + single season). |
| Batting | `?tab=Batting` | Top batters by avg + SR; a "Picked batter" scope-stats tile via `?series_batter=<id>`. |
| Bowling | `?tab=Bowling` | Top bowlers by SR + economy; "Picked bowler" tile via `?series_bowler=<id>`. |
| Fielding | `?tab=Fielding` | Top fielders by dismissals + keeper-dismissals + run-outs; "Picked fielder" via `?series_fielder=<id>`. |
| Partnerships | `?tab=Partnerships` | Largest partnerships overall + top-10 per wicket (1st through 10th). |
| Records | `?tab=Records` | 8 record lists: highest team totals, lowest all-out, biggest wins by runs/wickets, largest partnerships, best individual batting, best bowling figures, most sixes in a match. |
| Matches | `?tab=Matches` | Full match list, paginated. |

The picked-player tiles on Batting / Bowling / Fielding are
independent and sticky-per-session; only the active subtab's pick
shows up in the URL.

### `/teams` (Team dossier)

URL: `?team=<name>`. The empty landing shows the international (men's
+ women's full members + associate) and club (franchise leagues,
women's franchise, domestic championships) directory.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | `?tab=By%20Season` (default) | Wins/losses per season + summary row. |
| vs Opponent | `?tab=vs%20Opponent` | Per-opponent stacked bars + bubble matrix. |
| Compare | `?tab=Compare` | Up to 3 columns side-by-side across Results / Batting / Bowling / Fielding / Partnerships. |
| Batting | `?tab=Batting` | Team batting aggregates — summary, by-season, by-phase, by-inning, top-batters, phase-season heatmap. |
| Bowling | `?tab=Bowling` | Team bowling aggregates — sibling shape. |
| Fielding | `?tab=Fielding` | Team fielding aggregates — sibling shape. |
| Partnerships | `?tab=Partnerships` | Team partnerships — summary, by-season, by-wicket, best-pairs, heatmap, top. |
| Players | `?tab=Players` | Per-season roster (XI appearances) with batting avg + bowling SR + year-over-year turnover. |
| Records | `?tab=Records` | Subject-team records — 8 lists, same shape as `/series` Records, scoped to "team X's". |
| Match List | `?tab=Match%20List` | Paginated match list with a won/lost/tied result filter. |

The **Splits Mosaic** sits above the panels on Teams and is also a
filter widget: clicking a cell narrows `?toss_outcome=` + `?inning=` +
`?result=` to the cell's coordinates.

### `/players` (Single + N-way compare)

URL: `?player=<id>` for single; `?player=<id>&compare=<id2>&compare=<id3>`
for compare. Stacks Batting → Bowling → Fielding → Keeping bands for
each player; each band has an "Open <discipline> page →" link
forwarding the FilterBar scope. Comparison is single-gender (enforced
via the FilterBar's gender chip). No subtabs — composed client-side
from `/batters/{id}/summary`, `/bowlers/{id}/summary`,
`/fielders/{id}/summary`, `/fielders/{id}/keeping/summary`.

The page also surfaces a condensed top-5 Records section
(cross-discipline) once a single player is picked, sourced from
`/batters/{id}/records` + `/bowlers/{id}/records` +
`/fielders/{id}/records`.

**Inline baseline visual** (shipped 2026-05-20). Every numeric stat
tile on the player bands renders as a three-tier stack: bold value
/ `vs base N` subtitle / coloured delta chip. The baseline is a
position-mix-weighted cohort (batting: 10 position buckets opener
+ #3..#11; bowling: 20 per-over buckets; fielding: keeper-flag
binary), computed in-process from the corresponding
`/api/v1/scope/averages/players/<disc>/summary` endpoint and folded
into the existing /summary roundtrip. Hover the `vs base N` text
for the cohort phrasing (player mix + cohort size). Compare-grid
columns each show an inline delta chip derived from that column's
own mix. Spec: `internal_docs/spec-player-compare-average.md`.

### `/batting` (Batter deep dive)

URL: `?player=<id>` for a single batter; the landing view (no
player) shows top-10 by avg + SR for the current scope.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | `?tab=By%20Season` (default) | Season-by-season career. |
| By Over | `?tab=By%20Over` | Per-over (1..20) runs / SR / dismissal-over distribution. |
| By Phase | `?tab=By%20Phase` | Powerplay (overs 1-6) / Middle (7-15) / Death (16-20). |
| vs Bowlers | `?tab=vs%20Bowlers` | Scatter + table of matchups: SR × avg, dot size = balls faced. |
| Dismissals | `?tab=Dismissals` | Dismissal donut by kind + by phase + primary bowler type. |
| Inter-Wicket | `?tab=Inter-Wicket` | Runs + rate in each between-wickets span. |
| Innings List | `?tab=Innings%20List` | Paginated innings list. |
| Records | `?tab=Records` | 6 lists: highest scores, fastest 50s/100s, most sixes/fours in an innings, best strike rates. |

### `/bowling` (Bowler deep dive)

URL: `?player=<id>`. Landing shows top-10 by SR + economy.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | default | Season-by-season career. |
| By Over | `?tab=By%20Over` | Per-over economy + SR. |
| By Phase | `?tab=By%20Phase` | PP / Middle / Death economy + SR. |
| vs Batters | `?tab=vs%20Batters` | Matchup table by batter. |
| Wickets | `?tab=Wickets` | Wicket analysis: by kind, by phase, by batter, dismissal-over distribution. |
| Innings List | `?tab=Innings%20List` | Paginated innings list. |
| Records | `?tab=Records` | 2 lists: best figures, most economical (min 18 balls / 3 overs). |

### `/fielding` (Fielder + keeper deep dive)

URL: `?player=<id>`. Landing shows top fielders by dismissals + top
keepers by keeper-dismissals.

| Subtab | URL | What it shows |
|---|---|---|
| By Season | default | Per-season dismissals split by kind. |
| By Over | `?tab=By%20Over` | Per-over dismissal counts. |
| By Phase | `?tab=By%20Phase` | PP / Middle / Death dismissals. |
| Dismissal Types | `?tab=Dismissal%20Types` | Donut: % catches vs stumpings vs run-outs vs c&b. |
| Victims | `?tab=Victims` | Batters dismissed by this fielder, ranked. |
| Innings List | `?tab=Innings%20List` | Per-innings fielding credits. |
| Records | `?tab=Records` | 3 lists: most catches in a match, most stumpings, most dismissals. |

### `/head-to-head` (Player vs Player OR Team vs Team)

URL: `?batter=<id>&bowler=<id>` for PvP; `?team=<X>&vs=<Y>` for TvT.
A "Show" pill at the top narrows by series category: All / Bilateral
T20Is / ICC events / Club tournaments. The Show pill composes with
the FilterBar — it's a slice of `series_type`.

Team vs Team reuses the `/series` dossier shape (Batters, Bowlers,
Fielders, Partnerships, Records, Matches subtabs), just scoped to
the team-pair match-set.

### `/venues` (Venue dossier)

URL: `?venue=<name>`. Landing shows country-grouped tiles; a
search box filters by name or city.

| Subtab | URL | What it shows |
|---|---|---|
| Overview | default | Avg first-innings total, bat-first vs chase win %, toss decision split + correlation, boundary/dot % per phase, ground records. |
| Batters | `?tab=Batters` | Top batters at this venue. |
| Bowlers | `?tab=Bowlers` | Top bowlers at this venue. |
| Fielders | `?tab=Fielders` | Top fielders at this venue. |
| Matches | `?tab=Matches` | Full match list at this venue. |
| Records | `?tab=Records` | Venue-scoped record lists. |

### `/matches` (Match list)

URL: `/matches?…filters…`. No subtabs. Click a row to open
`/matches/:matchId` for the full scorecard, innings grid, worm
chart, and matchup grid. Every team name in a row carries a small
`(ed)` link that opens that team's page scoped to THIS match's
edition (tournament + season), independent of the FilterBar.

---

## 3. The FilterBar (sticky across pages)

A row of dropdowns sits at the top of every page (except `/` and
`/matches/:matchId`). Its state lives in URL query params and
persists across navigation — set Gender=Men once, you'll see Men's
data on every page until you change it.

### FilterBar fields (`FilterBarParams` in the API)

| URL param | Values | What it filters | Notes |
|---|---|---|---|
| `gender` | `male` / `female` | `match.gender` | |
| `team_type` | `international` / `club` | `match.team_type` | International = national teams (T20Is); club = every franchise + domestic league. |
| `tournament` | string | `match.event_name` | Canonicalisation-aware: "T20 World Cup (Men)" expands to the IN-list of cricsheet variants (`ICC World Twenty20` / `World T20` / `ICC Men's T20 World Cup`). |
| `season_from` | string | `match.season >= …` | Cricsheet seasons are a mix of calendar (`"2024"`) and split-year (`"2024/25"`). Lex sort matches chronology. |
| `season_to` | string | `match.season <= …` | Inclusive on both ends. |
| `filter_venue` | string | `match.venue` (exact canonical) | Venue strings are canonicalised at insert via `api/venue_aliases.py`. The Venue typeahead returns the canonical form. |

Quick-select buttons in the season pickers:

- `all-time` — clear the season range.
- `latest` — pin both ends to the most recent season available in
  the current filter scope (so with Tournament=BBL, jumps to the
  current BBL season, not the current IPL).
- `reset all` — clear every filter.

The Batting / Bowling / Fielding landings default the season range
to the **last 3 seasons** because the unfiltered all-time view is
rarely what users want. Click `all-time` to widen.

### Page-local Aux filters (`AuxParams`)

These are not part of the sticky FilterBar; they apply only to the
current page and are read by the same endpoints via FastAPI
`Depends()`. Their state is in the URL so share-link round-trip
still works.

| URL param | Values | What it filters | Notes |
|---|---|---|---|
| `inning` | `0` / `1` | 1st innings (batted first) / 2nd innings (chased) | URL semantics are constant (`innings.innings_number`); the pill label is POV-aware via `useDiscipline()`. Spec: `internal_docs/spec-inning-split.md`. |
| `result` | `won` / `lost` / `tied` | Match outcome from path-team POV | Requires `?team=` (or path team binding); endpoint returns HTTP 400 otherwise. `tied` collapses true ties (super-over loss) + no-result (rain-abandoned). |
| `toss_outcome` | `won` / `lost` | Toss outcome from path-team POV | Requires `?team=`; otherwise 400. |
| `series_type` | `all` / `bilateral` / `icc` / `club` | Match category | `bilateral` = international non-ICC; `icc` = ICC tournaments; `club` = `team_type=club`. Legacy `bilateral_only` / `tournament_only` map to `bilateral` / `icc`. |
| `team_class` | `full_member` / `primary_club` / `secondary_club` | Tier within team_type | `full_member` (intl): both teams ICC full members. `primary_club` (club): marquee international franchise league (IPL/BBL/PSL/CPL/SA20/ILT20/LPL/MLC/Hundred/WBBL/WPL/WCSL). `secondary_club` (club): domestic state/county league. Cross-type combinations are silent no-ops. |
| `scope_to_team` | string | Compare-tab avg slot narrowing | Restricts the league baseline to events the team has appeared in. Gated frontend-side on `team_type=club`. |
| `filter_team` | string | Page-contextual: narrows to matches involving this team | Used by player pages and rivalry dossiers. |
| `filter_opponent` | string | Page-contextual: narrows to matches against this opponent | Combined with `filter_team`, gives a team-pair rivalry. |

### How filters compose

All filters are **AND**-combined. There is no OR mode. Two filters
on different axes (e.g. `tournament=Indian Premier League` +
`filter_venue=Wankhede Stadium, Mumbai`) intersect — only matches
that satisfy both pass. The `tournament` canonicalisation widens
to the IN-list, but that widening still composes AND'd with every
other filter.

The dropdowns themselves are scope-narrowed: the Tournament
dropdown lists only tournaments that have matches under the
current Gender + Type; the Venue typeahead lists only venues with
matches under the current scope. So a user can't typically pick
a combination that returns zero matches — but if they do
(deep-link with conflicting filters), endpoints return `matches: 0`
rather than a 404.

### Cascade-clear rule

When a coupled filter is cleared (Gender or Team Type), any
dependent narrowing (Tournament) is also cleared. Without this,
the FilterBar's auto-correct deep-link effects would re-assert the
prior value from the tournament's metadata.

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
API: `GET /api/v1/venues/Wankhede%20Stadium%2C%20Mumbai/summary` for the overview;
records render via `/series/records` with `filter_venue=…`.

---

## 5. Reading conventions

- **Innings semantics.** `?inning=0` always means
  `innings.innings_number = 0` (the match's first half — the side
  that batted first). The rendered pill label is POV-aware via
  `useDiscipline()`: on a batting page it reads "Batting first"; on
  bowling/fielding it reads "Bowling first"; on the ambiguous
  multi-discipline pages (Players, Records subtabs) it stays neutral
  ("1st innings"). So the URL is constant, the label adapts.
- **`result` and `toss_outcome` are subject-POV.** They only make
  sense when a path team is bound (the path `:team` or `?team=`).
  Without a team subject, "won" is tautological. Endpoints return
  HTTP 400 on the combination.
- **Series vs Tournament terminology.** Cricket uses "series" for
  both bilateral tours (India vs Australia) AND tournament editions
  (IPL 2024). The `/series` tab covers both; `match.event_name`
  carries the tournament identity; `filter_team` + `filter_opponent`
  together define a bilateral rivalry. The API path `/series/*` is
  the tournament-or-rivalry dossier; `/tournaments` is just the
  FilterBar dropdown list of `event_name`s.
- **Volume vs rate framing.** Fielding leaderboards rank by total
  dismissals (volume). Batting / bowling leaderboards rank by avg /
  SR / economy (rate) with min-sample gates (min 100 balls + 3
  dismissals for batting averages, min 60 balls + 3 wickets for
  bowling SR). The thresholds are returned in each response's
  `thresholds` field so the UI can render them in the table caption.
- **Catches include caught-and-bowled (Convention 3).** Every
  `/summary` and `/leaders` endpoint that surfaces a `catches`
  headline uses `kind IN ('caught', 'caught_and_bowled')`. The
  `/distribution` endpoint is the one exception — its master sample
  is per-match (matchplayer-based), so substitute appearances are
  excluded and `caught_and_bowled` is a sibling block under the
  bowling distribution (bowler-credited).
- **DLS-shortened innings are included everywhere.** A 90-run chase
  truncated by rain in over 12 contributes its ~60-72 legal balls
  to every overs-denominator stat and counts as 1 innings in every
  per-innings denominator. No `target_overs` filter exists anywhere
  in the API.

---

## 6. Pointers

- **Full API reference:** [`docs/api.md`](./api.md) — every endpoint
  with path, query params, example curl, abbreviated response.
- **Interactive API docs (Swagger):** <https://t20.rahuldave.com/api/docs>
- **OpenAPI schema (JSON):** <https://t20.rahuldave.com/api/openapi.json>
- **User manual:** [`frontend/src/content/user-help.md`](../frontend/src/content/user-help.md)
  — human-facing tour with screenshots.
- **`llms.txt`:** <https://t20.rahuldave.com/llms.txt> — the
  agent-discovery index pointing at all of the above.
- **Source code:** <https://github.com/rahuldave/cricsdb>
