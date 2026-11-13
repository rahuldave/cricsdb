# CricsDB API Reference

This page is a practical reference to every endpoint of the CricsDB HTTP API, on one page. For each
endpoint, it gives the URL, a
one-line description and a typical response.

For the SQL behind an endpoint, or for the full schema, read
[`../SPEC.md`](https://github.com/rahuldave/cricsdb/blob/main/SPEC.md) with this page. The examples come
from local development (`http://localhost:8000`). For production, use `https://t20.rahuldave.com` instead.
The responses are cut short and show only the shape of each payload.

The [HTTP reference](https://rahuldave.com/cricsdb/http/) lists every endpoint with all of its parameters, their types
and defaults. smalldocs writes it from the code at each build.

> **Also useful:** the
> [Interactive Swagger UI](https://t20.rahuldave.com/api/docs) (production), or
> [`http://localhost:5173/api/docs`](http://localhost:5173/api/docs) (local, through the Vite proxy) or
> [`http://localhost:8000/api/docs`](http://localhost:8000/api/docs) (local, direct).
> FastAPI generates the Swagger UI from the route decorators. Every
> endpoint on it has a "Try it out" button. To try an endpoint live,
> start there. Come back here for the narrative and for the example
> responses that support the text of each section.

> The Swagger UI is at `/api/docs`, not at the FastAPI default `/docs`,
> so that the Vite dev-server proxy forwards the request to the backend.
> In production the frontend and the backend share an origin, so either
> path would work. But a path under `/api/*` matches the rest of the
> routes and avoids a special case.

## Conventions

- All endpoints return JSON.
- All endpoints are `GET`, and none needs authentication. The only
  protected part is the deebase admin UI at `/admin/*`, which uses HTTP
  Basic Auth.
- On a failure, the response is best effort. A 500 returns
  `{"detail": "..."}` rather than partial JSON.
- **Venue and city strings are canonical.** At insert time, `match.venue`
  and `match.city` go through `api/venue_aliases.py`. So every endpoint
  that returns them gives the canonical form, for example `Wankhede
  Stadium, Mumbai` and not the raw cricsheet `Wankhede`, or `County Ground
  (Taunton)` and not the ambiguous `County Ground`. They are safe to use
  as keys for an exact match. The venue endpoints (`/venues`,
  `/venues/landing` and `/venues/{venue}/summary`) also return
  `match.venue_country`, under the name `country`. On `/venues/landing`
  it is the key of each `by_country` group, and `Unknown` when it is
  missing.

## Common filter query params

The FilterBar is the row of filter dropdowns at the top of the site's
pages. Its values are URL query parameters, and almost every endpoint
below takes them. `api/filters.py::FilterBarParams`
enforces them. Its old name, `FilterParams`, is kept as an alias, so that
the code can move to the new name step by step. If a parameter is
omitted, it puts no limit on that axis.

| Param | Type | What it filters | Example |
|---|---|---|---|
| `gender` | `male`/`female` | `match.gender` | `gender=male` |
| `team_type` | `international`/`club` | `match.team_type` | `team_type=international` |
| `tournament` | string | `match.event_name` (exact OR canonical → IN variants) | `tournament=Indian%20Premier%20League` or `tournament=T20%20World%20Cup%20%28Men%29` |
| `season_from` | string | `match.season >= ...` | `season_from=2024` |
| `season_to` | string | `match.season <= ...` | `season_to=2024/25` |
| `filter_venue` | string | `match.venue = ...` (exact canonical) | `filter_venue=Wankhede%20Stadium%2C%20Mumbai` |
| `series_type` | `all`/`bilateral`/`icc`/`club` (default `all`) | Categorises the match. `bilateral` = international non-ICC; `icc` = ICC events (T20 WC etc.); `club` = `team_type=club` | `series_type=bilateral` |
| `team_class` | `full_member` / `primary_club` / `secondary_club` | Polymorphic over `team_type`. **`full_member`** (`team_type=international`): both teams are ICC full members (Afghanistan, Australia, Bangladesh, England, India, Ireland, New Zealand, Pakistan, South Africa, Sri Lanka, West Indies, Zimbabwe). **`primary_club`** (`team_type=club`): match's event_name is in a marquee international franchise league (IPL, BBL, PSL, BPL, CPL, SA20, ILT20, LPL, MLC, The Hundred (M+W), WBBL, WPL, Women's Cricket Super League). **`secondary_club`** (`team_type=club`): match's event_name is in a domestic state/county/provincial competition (Vitality Blast, Syed Mushtaq Ali Trophy, CSA T20 Challenge, Super Smash, Nepal Premier League, Women's Super Smash, NZC Women's T20). Cross-type combinations are silent no-ops (a defensive backend gate, which keeps URLs robust when frontend gate fails or curl mixes them). | `team_class=full_member` or `team_class=primary_club` or `team_class=secondary_club` |

### Aux filters (page-local narrowings)

A separate `AuxParams` class (`api/filters.py`) holds the aux filters.
They are page-local filters, and the FilterBar UI does not set them.
`series_type` and `team_class` are not aux filters. They are FilterBar
fields, in the table above. The FilterBar sets them with its Series
Type dropdown and its Full members only toggle, both shown for
internationals, and with its Tier buttons, shown for clubs.

| Param | Type | What it filters | Example |
|---|---|---|---|
| `scope_to_team` | string | Narrows the match pool to events that team has appeared in (intersection of `m.event_name`s). Used by the Compare-tab avg slot; gated frontend-side on `team_type='club'` (closed-league semantic). | `scope_to_team=Royal%20Challengers%20Bengaluru` |
| `inning` | `0` / `1` | 1st innings (`0`, batted first) or 2nd innings (`1`, batted second). Team-router endpoints apply it at match level via `_inning_match_filter`; innings-joined endpoints (batting/bowling/fielding) apply it via `filters.build` when `has_innings_join=True`. Per-slot override on the Compare tab via `compareN_inning`. | `inning=0` |
| `result` | `won` / `lost` / `tied` | Match-outcome filter from the point of view (POV) of the path team, the team named in the URL path. `won` = path team is `outcome_winner`; `lost` = another team won; `tied` = `outcome_winner IS NULL` (collapses ties and no-results. A tie keeps `outcome_winner` NULL even when a super over decides it, and puts the super-over winner in `outcome_eliminator`). Subject-team endpoints key on `:team`. The `/scope/averages/*` **cohort** (the set of innings behind the league baseline) narrows per-row. The subject is each innings' batting team `i.team` (bowling/fielding disciplines flip to the other side), so the league baseline is among-winners, a real distinct number (NOT tautological: the count is ~50% but the stats differ). Other non-team endpoints ignore it. Spec: `docs/internal/spec-compare-toss-result.md`, `spec-splits-mosaic.md`. | `result=won` |
| `toss_outcome` | `won` / `lost` | Toss-outcome filter from the path team's POV. `won` = `toss_winner = :team`; `lost` = `toss_winner != :team AND toss_winner IS NOT NULL`. The `/scope/averages/*` cohort narrows per-row on `i.team` (same as `result`). Spec: `docs/internal/spec-compare-toss-result.md`, `spec-splits-mosaic.md`. | `toss_outcome=won` |

Every endpoint that takes `FilterBarParams` also takes the aux filters.
Routers declare both as FastAPI `Depends()` and pass the aux filters
through `filters.build(aux=aux)`. That function adds the SQL clauses
of both (e.g. `series_type_clause`) in one place, so no router has to wire each
one by hand. As a result, every `teams/...`, `batters/...`,
`bowlers/...`, `fielders/...`, `matches` and `venues/...` endpoint now
narrows correctly under `?series_type=icc` and the other filters.
Before 2026-04-19, they ignored `series_type` and gave no error.

The legacy values `bilateral_only` and `tournament_only` map to
`bilateral` and `icc`, so that old bookmarked URLs still work. The
Series Type control of the FilterBar still sends the legacy values.

The `tournament` filter knows the canonical names everywhere. If you
pass `T20 World Cup (Men)`, FilterParams expands it to
`event_name IN ('ICC World Twenty20', 'World T20', "ICC Men's T20 World Cup")`.
The mapping is in `api/tournament_canonical.py`. A tournament with
one variant (for example IPL or BBL) passes through unchanged.

`FilterBarParams` also holds two contextual filters, `filter_team` and
`filter_opponent`. The FilterBar has no control for them. Pages and
links set them:

- `filter_team=<name>` narrows to matches that involve this team.
  Player pages use it as context, and tournament dossiers use it to set
  the scope of a rivalry.
- `filter_opponent=<name>` narrows to matches against this opponent.
  On a tournament-dossier endpoint with both `filter_team` and
  `filter_opponent` set, the scope becomes the rivalry of the two teams.
  Summary responses then also have a `by_team` companion object.

`filter_venue` is an **ambient** filter. Every endpoint that echoes the
FilterBar applies it, the same as `gender`/`season`. It must match the
canonical venue name exactly, as the note on venues under Conventions
says. The Venue typeahead of the FilterBar, in the frontend, calls
`/api/v1/venues?q=...`, so the user does not need to know the exact
canonical string.

A few endpoints add parameters of their own, and the section for each
endpoint below lists them. Some examples are `limit`, `offset`,
`min_balls`, `min_dismissals`, `min_wickets`, `q`, `role`, `top_n`, and
`bowler_id` / `batter_id` in the matchup endpoints.

### `team_class` worked examples

```
# Intl: matches between two ICC full members only (intl-only)
curl 'http://localhost:8000/api/v1/teams/India/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member'

# Club: marquee international franchise leagues only
curl 'http://localhost:8000/api/v1/teams/Mumbai%20Indians/summary?gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club'

# Club: domestic state/county/provincial competitions only
curl 'http://localhost:8000/api/v1/teams/Surrey/summary?gender=male&team_type=club&season_from=2024&season_to=2025&team_class=secondary_club'

# Cross-type silent no-op — these return the same response as
# omitting team_class (defensive backend gate):
curl 'http://localhost:8000/api/v1/teams/India/summary?...&team_class=primary_club'   # intl + club tier
curl 'http://localhost:8000/api/v1/teams/Mumbai%20Indians/summary?...&team_class=full_member'   # club + intl tier
```

The tournament dropdown (`/api/v1/tournaments`) and the team typeahead
(`/api/v1/teams`) both respect `team_class`. They narrow by themselves
to the events and teams of the chosen tier. So the user cannot pick a
combination that returns nothing, for example `tournament=Vitality Blast`
with `team_class=primary_club`.

## Seasons convention

- Season labels are the cricsheet strings, a mix of calendar years
  (`"2024"`) and split years (`"2024/25"`). A lexical sort puts them in
  time order.
- `season_from <= m.season <= season_to` includes both ends.

---

# Reference data (`/api/v1/*`)

The source is `api/routers/reference.py`.

## `GET /api/v1/tournaments`

Lists tournaments with their match counts. Variants are merged under
their canonical display name. So picking "T20 World Cup (Men)" in the
FilterBar narrows queries across all three cricsheet event_names. The
endpoint takes the common filters, and also these:

- `team` gives the tournaments that a team played in. It sets the scope
  of the dropdown on a page about one team.
- `opponent`, with `team`, gives only the tournaments where the two
  teams played each other. The FilterBar uses it to decide whether a
  rivalry is in one competition (MI vs CSK, only IPL) or in many
  (Ind vs Aus, bilaterals and ICC).

The endpoint is called `tournaments`, but it gives the list for the
FilterBar dropdown, where the user selects an `event_name`. The catalog
in sections that the `/series` page uses is under `/api/v1/series/*`,
described below.

```bash
curl "http://localhost:8000/api/v1/tournaments?team_type=club&gender=male"
```

```json
{
  "tournaments": [
    {
      "event_name": "Vitality Blast",
      "team_type": "club",
      "gender": "male",
      "matches": 1455,
      "seasons": ["2014", "2015", "…", "2025"]
    },
    {
      "event_name": "T20 World Cup (Men)",
      "team_type": "international",
      "gender": "male",
      "matches": 334,
      "seasons": ["2007/08", "2009", "…", "2025/26"]
    }
  ]
}
```

## `GET /api/v1/seasons`

Lists seasons in time order. The endpoint takes every FilterBar axis
(`team`, `gender`, `team_type`, `tournament`, `filter_team`,
`filter_opponent`, `filter_venue`, `team_class`, `series_type`). It also
takes the rivalry pair. When `filter_team` and `filter_opponent` are
both set, it narrows to the seasons in which the two teams met. Since
2026-05-07, it also takes `person_id`, which narrows to the seasons of
one player.

```bash
curl "http://localhost:8000/api/v1/seasons"
```

```json
{ "seasons": ["2004/05", "2005", "2005/06", "…", "2025/26", "2026"] }
```

### `person_id`, player-aware narrowing

When it is set, the result keeps only the seasons in which the
player appeared (a join on matchplayer). The FilterBar passes the
page's current `?player=<id>` URL parameter as `?person_id=<id>`. So the
From and To dropdowns, and the quick-select buttons `first-3`, `prev-3`,
`last-3` and `latest`, all follow the player's career in scope rather
than the whole dataset. The narrowing fixes a gap for retired players. On
AB de Villiers' batting page, `last-3` now sets the season filter to
`2019/20` to `2021`, his last seasons. Before, it set `2024` to `2026`,
the recent seasons of the dataset, which would show no data.

```bash
# Active player — Kohli's seasons span 2007/08 to current.
curl "http://localhost:8000/api/v1/seasons?person_id=ba607b88"
```

```json
{ "seasons": ["2007/08", "2009", "…", "2025", "2026"] }
```

```bash
# Retired player — AB de Villiers' seasons end at 2021.
curl "http://localhost:8000/api/v1/seasons?person_id=c4487b84&tournament=Indian%20Premier%20League"
```

```json
{ "seasons": ["2007/08", "2009", "2009/10", "…", "2020/21", "2021"] }
```

`person_id` combines with the other filter axes by intersection. For
example, `?tournament=Indian Premier League&person_id=c4487b84` returns
only the IPL seasons that ABdV played. In the frontend, the
`getSeasons()` wrapper in `frontend/src/api.ts` takes `player` (the URL
convention) and forwards it to this endpoint as `person_id`. So callers
do not need to know the backend convention.

## `GET /api/v1/teams`

Searches team names. The endpoint takes all the common filters and
`q`, a substring match on the team name.

```bash
curl "http://localhost:8000/api/v1/teams?q=India&team_type=international&gender=male"
```

```json
{ "teams": [ { "name": "India", "matches": 266 } ] }
```

## `GET /api/v1/venues`

Lists the venues in scope. The Venue typeahead of the FilterBar
(`components/VenueSearch.tsx`) uses it. The endpoint takes all the
common filters except `filter_venue` itself, which would refer to
itself. It also takes these:

- `q` is a case-insensitive substring match on `venue` or `city`.
  Without it, the endpoint returns the top 50 venues by match count.
  The top 50 is enough for the dropdown that opens when the empty field gets
  the focus.
- `limit` has a default of 50 and a maximum of 500.

```bash
curl "http://localhost:8000/api/v1/venues?q=wank&limit=3"
```

```json
{
  "venues": [
    { "venue": "Wankhede Stadium", "city": "Mumbai",
      "country": "India", "matches": 178 }
  ]
}
```

## `GET /api/v1/venues/landing`

Gives the directory of venues, grouped by country, for the `/venues`
landing page. The endpoint takes all the common filters except
`filter_venue`. Countries are in descending order of total match count,
and the venues within each country are in descending order of their own match count.

```bash
curl "http://localhost:8000/api/v1/venues/landing"
```

```json
{
  "by_country": [
    { "country": "India", "matches": 2019, "venues": [
        { "venue": "Wankhede Stadium", "city": "Mumbai", "matches": 178 },
        { "venue": "Eden Gardens",    "city": "Kolkata", "matches": 146 },
        { "venue": "M Chinnaswamy Stadium", "city": "Bengaluru", "matches": 122 },
        "… 75 more"
    ] },
    { "country": "England", "matches": 1942, "venues": [ "…" ] },
    "…"
  ]
}
```

The current database has 88 countries. The response follows the
filters. For example, with `?team_type=international&gender=male`, the
totals and the list of venues narrow to men's internationals only.

## `GET /api/v1/venues/{venue}/summary`

Gives the dossier of one venue's character, as one bundle (Phase 3).
The path sets `m.venue = :venue`, and the endpoint drops any ambient
`filter_venue` in the query. It applies every other common filter
(gender, team_type, tournament, season window, filter_team,
filter_opponent and team_class).

Status codes:

- **200** with `matches: 0` and empty payload sections means that the
  venue exists in the database, but the current filter scope has no
  matches. An example is MCG with `team_class=secondary_club`, because
  MCG hosts only BBL and WBBL, which are both primary. The frontend shows
  an empty-state page, not a generic error. **Behaviour change shipped
  2026-04-30.** Before the fix, the endpoint treated this case as a
  missing venue and returned 404. The problem showed only once the
  club-tier filter made an empty scope possible.
- **404** means only that `venue` does not appear at all in
  `match.venue`, so the venue is missing.

The response gives:

- the number of matches
- the matches hosted, by tournament, gender and season
- the average first-innings total
- the wins batting first and chasing, as counts and percentages
- the split of toss decisions
- for each toss decision, how often the toss winner won the match
- the boundary % and the dot % for each phase (powerplay overs 1 to 6,
  middle overs 7 to 15, death overs 16 to 20)
- the ground records, which are the highest total and the lowest all-out
  total

```bash
curl "http://localhost:8000/api/v1/venues/Wankhede%20Stadium%2C%20Mumbai/summary"
```

```json
{
  "venue": "Wankhede Stadium",
  "city": "Mumbai",
  "country": "India",
  "matches": 178,
  "by_tournament_gender_season": [
    { "tournament": "Indian Premier League", "gender": "male", "season": "2026", "matches": 2 },
    { "tournament": "ICC Men's T20 World Cup", "gender": "male", "season": "2025/26", "matches": 8 },
    "… 26 more"
  ],
  "avg_first_innings_total": 170.5,
  "first_innings_sample": 178,
  "bat_first_wins": 77,
  "chase_wins": 100,
  "indecisive": 1,
  "bat_first_win_pct": 43.3,
  "chase_win_pct": 56.2,
  "toss_decision_split": { "bat": 38, "field": 140 },
  "toss_and_win_pct": {
    "bat":   { "wins": 15, "decided": 37,  "win_pct": 40.5 },
    "field": { "wins": 78, "decided": 140, "win_pct": 55.7 }
  },
  "boundary_pct_by_phase": { "powerplay": 20.0, "middle": 15.5, "death": 22.2 },
  "dot_pct_by_phase":      { "powerplay": 47.4, "middle": 32.3, "death": 28.4 },
  "highest_total":  { "runs": 254, "team": "West Indies", "opponent": "Zimbabwe",
                      "match_id": 2632, "season": "2025/26", "date": "2026-02-23" },
  "lowest_all_out": { "runs": 67,  "team": "Kolkata Knight Riders",
                      "opponent": "Mumbai Indians",
                      "match_id": 6065, "season": "2007/08", "date": "2008-05-16" }
}
```

As a sanity check, `bat_first_win_pct < 50` on grounds with heavy dew
(Wankhede, Chinnaswamy), and it is at least 50 on grounds that suit
spin (Chepauk).

## `GET /api/v1/players`

Searches players. The parameters are `q` (at least 2 characters),
`role` (`batter`/`bowler`/`fielder`, optional) and `limit` (default 20).

The endpoint also takes optional FilterBar and aux parameters for the
scope. When any of `gender`, `team_type`, `tournament`, `season_from`,
`season_to`, `filter_team`, `filter_opponent`, `filter_venue` or
`series_type` is set, it narrows to people who played for either team in
a match in scope. The filter at match level is the same as in the
`/series/*-leaders` endpoints. The discipline-picker typeaheads of the
Series tab use it. So, for example, "AB" on T20 WC Men 2022/23 to
2025/26 does not show AB de Villiers.

```bash
curl "http://localhost:8000/api/v1/players?q=Kohli&limit=3"

# Scoped: only Kohlis with deliveries in T20 WC Men 2022/23-2025/26
curl "http://localhost:8000/api/v1/players?q=Kohli&role=batter&tournament=T20+World+Cup+%28Men%29&gender=male&team_type=international&season_from=2022%2F23&season_to=2025%2F26"
```

```json
{
  "players": [
    { "id": "ba607b88", "name": "V Kohli", "unique_name": "V Kohli", "innings": 375 },
    { "id": "40caa465", "name": "T Kohli", "unique_name": "T Kohli", "innings": 29 }
  ]
}
```

## `GET /api/v1/players/{person_id}/result-counts`

Gives one player's match counts, split by the match result of the
player's own team and by the toss outcome. The ResultFilter pills (won,
lost, tied) on the player page use these counts, and so does the toss
split. The scope is the FilterBar fields (`gender`, `team_type`,
`tournament`, `season_from`/`_to`, `filter_venue`, `series_type`). It also
includes `inning` (Option-B, a union at match level) and `filter_team`.
It applies that filter again at `mp.team`, so it narrows to
matches in which the player played *for* that team.

The endpoint drops the aux filters `result`/`toss_outcome`, because it
reports those splits, and a filter on them would make the breakdown
circular. It also drops `filter_opponent`, so the pill counts stay at the
level of the team and the scope (see the caveat below).

```bash
curl "http://localhost:8000/api/v1/players/ba607b88/result-counts?gender=male&team_type=club"
```

```json
{
  "matches": 280,
  "wins": 140,
  "losses": 134,
  "ties": 6,
  "no_results": 0,
  "toss_won": 132,
  "toss_lost": 148
}
```

The counts are flat integers. They are not wrapped in a metric envelope, the
object that holds a value next to its baseline (see "Compare metric envelope"). `wins + losses + ties +
no_results == matches`, and `toss_won + toss_lost <= matches`, because a
match with no recorded toss winner is in neither count. `ties` counts
true ties and no-results together (`outcome_winner IS NULL`), so
`no_results` is always 0. The source is
`api/routers/reference.py`.

> **Caveat: `filter_opponent` is not applied here.** A player page can
> carry `filter_opponent` (the "Versus" typeahead). The pill counts from
> this endpoint then stay at the level of the team and the scope, and do
> not narrow to the opponent. The behaviour is known as of 2026-05-29
> (the endpoint `drop`s `filter_opponent`), and it is flagged for review.

---

# Landing pages

Each tab of the search bar has one endpoint for the directory below the search. The directory
changes with the filters. See [`perf-leaderboards.md`](internal/perf-leaderboards.md) for the
pattern that keeps these endpoints fast (conditional JOINs, composite indexes and ANALYZE).

## `GET /api/v1/teams/landing`

The endpoint returns a directory in two columns. International teams are split by **gender** (men's and women's), so that the women's full
members do not get lost in a mixed list. Each gender bucket has `regular` (ICC full members) and
`associate`. If a gender filter is set, the endpoint fills only the bucket of that gender.

Club tournaments are put in buckets by series_type. The canonicalization map in
`api/tournament_canonical.py` gives the buckets:

- **franchise_leagues**, for example IPL, BBL and PSL.
- **domestic_leagues**, the national championships, for example Vitality Blast, Syed Mushtaq Ali
  Trophy and CSA T20 Challenge.
- **women_franchise**, for example WBBL, WPL and The Hundred Women's.
- **other**, for a tournament that is not classified.

Each team entry carries a `gender` field. If no gender filter is set, one name can belong to two
teams. For example, "Royal Challengers Bengaluru" is a men's team in the IPL and a women's team in
the WPL. The two appear as separate entries with different genders, so that the frontend can tell
them apart with a "men's" or "women's" suffix.

```bash
curl "http://localhost:8000/api/v1/teams/landing?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024"
```

The query asks for club teams in the IPL, so every international bucket
and every other club bucket is empty. A tournament's `matches` is the
sum of its teams' match counts, so it counts each match twice. The 71
matches of IPL 2024 give 142.

```json
{
  "international": {
    "men":   { "regular": [], "associate": [] },
    "women": { "regular": [], "associate": [] }
  },
  "club": {
    "franchise_leagues": [
      {
        "tournament": "Indian Premier League",
        "matches": 142,
        "teams": [
          { "name": "Chennai Super Kings", "gender": "male", "matches": 14 },
          { "name": "Delhi Capitals",      "gender": "male", "matches": 14 },
          "…"
        ]
      }
    ],
    "domestic_leagues": [],
    "women_franchise": [],
    "other": []
  }
}
```

## `GET /api/v1/teams/splits`

The endpoint returns the joint distribution of toss outcome, team innings and match result for
the Splits Mosaic. Spec: `docs/internal/spec-splits-mosaic.md`.

The endpoint has two modes:

- **Landing** (no `?team=`) gives league-side cells. It unpivots every match in scope into two
  team views, one for each side. So each match adds 2 rows to the joint distribution.
- **Team-detail** (`?team=X` set) gives team-side cells, the league-side baseline at the same
  filter scope, and a delta for each cell (`share - league_share`, and the relative `delta_pct`).
  The envelope pattern is the same as for
  the `scope_avg` field on `/teams/{team}/summary`. The endpoint **returns the full grid of toss,
  inning and result**, with every combination that passes the aux filter, including cells where
  the subject has `n = 0`. Each cell carries its `league_share`. So the reset bar of the Splits
  Mosaic can sum cells to build conditional counts and deltas that "drop/switch one axis".
  (Landing mode still returns only the cells that occur.)

The endpoint applies aux narrowings at the cell level, after the GROUP BY. If `?result=` or
`?toss_outcome=` is set without `?team=`, the endpoint returns HTTP 400. Both filters are relative
to the subject's point of view (POV), so they have no meaning without a team as the subject.

```bash
# Landing
curl "http://localhost:8000/api/v1/teams/splits?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024"

# Team-detail
curl "http://localhost:8000/api/v1/teams/splits?team=Royal%20Challengers%20Bengaluru&gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024"
```

```json
{
  "subject": { "team": "Royal Challengers Bengaluru" },
  "scope_total_n": 15,
  "league_total_n": 142,
  "cells": [
    {
      "toss_outcome": "lost",
      "inning": 0,
      "result": "lost",
      "n": 4,
      "share": 0.2667,
      "wilson_lo": 0.109,
      "wilson_hi": 0.5195,
      "league_share": 0.169,
      "delta": 0.0977,
      "delta_pct": 57.8
    }
  ],
  "marginals": {
    "toss_outcome": {
      "won":  { "n": 7, "share": 0.4667, "wilson_lo": ..., "wilson_hi": ...,
                "league_share": 0.5141, "delta": -0.0474, "delta_pct": -9.2 },
      "lost": { "n": 8, "share": 0.5333, ... }
    },
    "inning":  { "0": { ... }, "1": { ... } },
    "result":  { "won": { ... }, "lost": { ... }, "tied": { ... } }
  }
}
```

Cell coordinates:

- `toss_outcome`: `"won"` or `"lost"`
- `inning`: `0` (batted first) or `1` (batted second)
- `result`: `"won"`, `"lost"` or `"tied"` (the last one joins tied and no-result)

Errors when a filter needs a subject team:

- `?result=won` without `?team=` returns 400 `"?result= requires ?team= (subject POV needed)."`
- `?toss_outcome=won` without `?team=` returns 400 `"?toss_outcome= requires ?team= (subject POV needed)."`

## `GET /api/v1/batters/leaders`

The endpoint returns the top N batters by average and by strike rate. Thresholds on the size of
the sample leave out cameos. Params: `limit` (default 10), `min_balls` (default 100),
`min_dismissals` (default 3, for the list by average only).

```bash
curl "http://localhost:8000/api/v1/batters/leaders?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&limit=3"
```

```json
{
  "by_average": [
    { "person_id": "3241e3fd", "name": "N Pooran", "runs": 499, "balls": 279, "dismissals": 8, "average": 62.38, "strike_rate": 178.85 }
  ],
  "by_strike_rate": [
    { "person_id": "…", "name": "J Fraser-McGurk", "strike_rate": 233.59, "average": 24.0, "runs": 350, "balls": 150, "dismissals": 12 }
  ],
  "thresholds": { "min_balls": 100, "min_dismissals": 3 }
}
```

## `GET /api/v1/bowlers/leaders`

The endpoint returns the top N bowlers by strike rate and by economy. Params: `limit`
(default 10), `min_balls` (default 60, which is 10 overs), `min_wickets` (default 3, for the list
by strike rate only).

```bash
curl "http://localhost:8000/api/v1/bowlers/leaders?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&limit=3"
```

```json
{
  "by_strike_rate": [
    { "person_id": "bbd41817", "name": "AD Russell", "balls": 176, "runs_conceded": 304, "wickets": 19, "strike_rate": 9.26, "economy": 10.36 }
  ],
  "by_economy": [
    { "person_id": "462411b3", "name": "JJ Bumrah", "economy": 6.48, "strike_rate": 16.8, "balls": 348, "runs_conceded": 376, "wickets": 20 }
  ],
  "thresholds": { "min_balls": 60, "min_wickets": 3 }
}
```

## `GET /api/v1/fielders/leaders`

The endpoint returns the top N fielders by total dismissals (catches, stumpings, run-outs and
caught-and-bowled). It also returns the top N keepers by dismissals as the designated keeper. The
lists rank by volume and have no thresholds. The keepers come from `keeper_assignment` (Tier 2).

```bash
curl "http://localhost:8000/api/v1/fielders/leaders?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&limit=3"
```

```json
{
  "by_dismissals": [
    { "person_id": "919a3be2", "name": "RR Pant", "total": 17, "catches": 11, "stumpings": 5, "run_outs": 1, "c_and_b": 0 }
  ],
  "by_keeper_dismissals": [
    { "person_id": "b17e2f24", "name": "KL Rahul", "total": 17, "catches": 15, "stumpings": 2 }
  ]
}
```

---

# Teams (`/api/v1/teams/{team}/…`)

Source: `api/routers/teams.py`. `{team}` is the URL-encoded name of the team, for example
`Mumbai%20Indians`. All endpoints accept the common filters.

## `GET /api/v1/teams/{team}/summary`

The endpoint returns the totals of wins and losses, toss stats, the banner of the gender breakdown
and the list of Tier-2 keepers. It also returns the canonical tournaments in which the team has
matches within the active filter scope. Each numeric metric is wrapped in the envelope for one
metric (see "Compare metric envelope" below). Fields that identify something (`gender_breakdown`, `keepers`, `tournaments_in_scope`) stay flat.

```bash
curl "http://localhost:8000/api/v1/teams/India/summary?gender=male&team_type=international"
```

```json
{
  "team": "India",
  "matches": { "value": 266, "scope_avg": 14872, "delta_pct": null, "direction": null, "sample_size": 14872 },
  "wins":    { "value": 180, "scope_avg": null, "delta_pct": null, "direction": null, "sample_size": 266 },
  "win_pct": { "value": 67.7, "scope_avg": 49.8, "delta_pct": 35.9, "direction": "higher_better", "sample_size": 266 },
  "ties": { "value": 6, ... },
  "no_results": { "value": 5, ... },
  "toss_wins": { "value": 122, ... },
  "bat_first_wins": { "value": 98, ... },
  "field_first_wins": { "value": 82, ... },
  "gender_breakdown": null,
  "keepers": [
    { "person_id": "4a8a2e3b", "name": "MS Dhoni", "innings_kept": 74 },
    { "person_id": "919a3be2", "name": "RR Pant", "innings_kept": 36 }
  ],
  "keeper_ambiguous_innings": 18,
  "tournaments_in_scope": ["Indian Premier League"],
  "last_match_date": "2026-03-08"
}
```

The Compare tab uses `tournaments_in_scope` to choose the label of the average column. If a club
team plays in only one tournament in scope (RCB in the IPL), the column takes the name of the
tournament instead of the generic "Men's club average".

`last_match_date` is the date of the team's most recent match in scope (ISO YYYY-MM-DD). It sets
the dormancy badge in the header of the team page, through DormancyContext. If the gap is more than
60 days, the page shows a small italic badge, such as "5 months since last match" or "last match:
Oct 2021", by the standard dormancy ladder. The field is null when the team has no matches in scope.

## `GET /api/v1/teams/{team}/results`

The endpoint returns the list of a team's matches, in pages. Params: `limit` (default 50),
`offset`.

```bash
curl "http://localhost:8000/api/v1/teams/India/results?gender=male&team_type=international&limit=1"
```

```json
{
  "results": [
    {
      "match_id": 2643,
      "date": "2026-03-08",
      "opponent": "New Zealand",
      "venue": "Narendra Modi Stadium, Ahmedabad",
      "city": "Ahmedabad",
      "tournament": "ICC Men's T20 World Cup",
      "toss_winner": "New Zealand", "toss_decision": "field",
      "result": "won", "margin": "96 runs",
      "player_of_match": "[\"JJ Bumrah\"]"
    }
  ],
  "total": 266
}
```

## `GET /api/v1/teams/{team}/vs/{opponent}`

The endpoint returns the head-to-head record of two teams, with a summary, a row for each season and
the list of matches.

```bash
curl "http://localhost:8000/api/v1/teams/India/vs/Australia?gender=male&team_type=international&season_from=2024&season_to=2025"
```

```json
{
  "team": "India", "opponent": "Australia",
  "overall": { "matches": 4, "wins": 2, "losses": 2, "ties": 0 },
  "by_season": [{ "season": "2024/25", "matches": 3, "wins": 1, "losses": 2, "ties": 0, "no_results": 0, "win_pct": 33.3 }],
  "matches": [ /* TeamResult rows */ ]
}
```

## `GET /api/v1/teams/{team}/opponents`

The endpoint returns a flat list of opponents with the count of matches against each. The UI does
not use it at present, and it stays for completeness.

## `GET /api/v1/teams/{team}/opponents-matrix`

The endpoint returns a rollup of the top N opponents by number of matches, and a cell for each
opponent in each season. The vs-Opponent tab draws its stacked bars and its bubble matrix from them. Params:
`top_n` (default 8).

```bash
curl "http://localhost:8000/api/v1/teams/India/opponents-matrix?gender=male&team_type=international&top_n=2"
```

```json
{
  "rollup": [
    { "name": "Australia", "matches": 33, "wins": 19, "losses": 13, "ties": 1, "no_results": 0, "win_pct": 57.6 }
  ],
  "cells": [ { "opponent": "Australia", "season": "2025/26", "matches": 3, "wins": 3, "losses": 0, "ties": 0 } ]
}
```

## `GET /api/v1/teams/{team}/by-season`

The endpoint returns the wins and losses in each season, for the "Wins by Season" bar chart.

```bash
curl "http://localhost:8000/api/v1/teams/India/by-season?gender=male&team_type=international&season_from=2024&season_to=2025"
```

```json
{
  "seasons": [
    { "season": "2024", "matches": 15, "wins": 13, "losses": 1, "ties": 1, "no_results": 0, "win_pct": 86.7 },
    { "season": "2024/25", "matches": 12, "wins": 10, "losses": 2, "ties": 0, "no_results": 0, "win_pct": 83.3 }
  ]
}
```

## `GET /api/v1/teams/{team}/players-by-season`

The endpoint returns the roster of each season. The roster lists everyone who played in the XI, in
alphabetical order, with the batting average and the bowling strike rate. It also gives the
turnover from the year before. The full names come from the variants in `personname`.

```bash
curl "http://localhost:8000/api/v1/teams/India/players-by-season?gender=male&team_type=international&season_from=2024&season_to=2024"
```

```json
{
  "seasons": [
    {
      "season": "2024",
      "players": [
        { "person_id": "eef2536f", "name": "Aavesh Khan", "bat_avg": 16.0, "bowl_sr": 11.0 },
        { "person_id": "ba607b88", "name": "Virat Kohli", "bat_avg": 61.75, "bowl_sr": null }
      ],
      "turnover": { "prev_season": "2023/24", "new_count": 14, "left_count": 6 }
    }
  ]
}
```

## Team ball-level: batting / bowling / fielding / partnerships

These endpoints give the aggregates for one team behind the Batting, Bowling, Fielding and
Partnerships tabs on `/teams`. See `docs/internal/spec-team-stats.md` for the design. Their
shapes follow one pattern:

- `.../summary` gives the top-line ball-level stats, such as runs, balls, average and strike
  rate. Each numeric metric is wrapped in the envelope (see "Compare metric envelope").
- `.../by-season` gives the season rows for the line and bar charts.
- `.../by-phase` splits by powerplay, middle and death. The numeric metrics of each phase
  (run_rate, economy, boundary_pct, dot_pct) are wrapped in the envelope against the league
  baseline in scope. The counts (runs, balls, wickets_lost, fours, sixes) stay flat.
- `.../by-inning` splits by 1st innings and 2nd innings. It is the sibling of `/by-phase` for the
  inning-split spec, and it partitions every numeric metric on `i.innings_number` (0 or 1). Its
  envelope shape is the same as for `/by-phase`. It exists for batting, bowling, fielding and
  partnerships. Spec: `docs/internal/spec-inning-split.md` §3.2.
- `.../top-batters`, `.../top-bowlers` and `.../top-fielders` give the top N players for that
  team. Params: `limit` (default 5).
- `.../phase-season-heatmap` gives a matrix of phase by season for the run rate and the wickets
  per innings.

#### Page-local `?inning=0|1` narrowing (AuxParams)

Every endpoint that joins innings, that is, every endpoint with metrics at the innings level, also
accepts a page-local query param. It is `?inning=0` for the 1st innings only, or `?inning=1` for
the 2nd innings only. It is a page-local aux narrowing of AuxParams, and
NOT a field of the FilterBar. The match-level endpoints
(`/teams/{team}/{summary,by-season,vs/{opponent},results}`) honour the same param through a derived
subquery on the match ids, with the meaning `team batted in
inning X`. Spec: `docs/internal/spec-inning-split.md`
§3.1a and §5.2.

### Batting

```bash
curl "http://localhost:8000/api/v1/teams/India/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric is wrapped in the envelope for one metric (see
"Compare metric envelope" below). The endpoint returns:
`{ team, innings_batted, total_runs, legal_balls, run_rate,
boundary_pct, dot_pct, fours, sixes, fifties, hundreds,
avg_1st_innings_total, avg_2nd_innings_total,
highest_total, lowest_all_out_total }`. The fields that identify an innings
(`highest_total`, `lowest_all_out_total`) stay flat. The subroutes `/by-season`, `/by-phase`, `/by-inning`, `/top-batters` and
`/phase-season-heatmap` keep their shapes.

The `/by-inning` shape:

```bash
curl "http://localhost:8000/api/v1/teams/Royal%20Challengers%20Bengaluru/batting/by-inning?gender=male&team_type=club&season_from=2025&season_to=2025"
```

```json
{
  "innings": [
    { "inning_no": 0, "label": "1st innings",
      "runs": 1452, "balls": 924,
      "run_rate": {"value": 9.43, "scope_avg": ..., "delta_pct": ..., "direction": "higher_better", "sample_size": 924},
      "wickets_lost": 55, "boundary_pct": {...}, "dot_pct": {...},
      "fours": 119, "sixes": 77 },
    { "inning_no": 1, "label": "2nd innings", ... }
  ]
}
```

`/bowling/by-inning` has the same shape, with `runs_conceded`, `economy`, `wickets`,
`fours_conceded` and `sixes_conceded` instead. So does `/fielding/by-inning`, with `matches`,
`catches`, `stumpings`, `run_outs` and `*_per_match`. For `/partnerships/by-inning`, a sibling of
`/by-wicket`, the keys of each row are `n`, `avg_runs`, `avg_balls` and `best_runs`.

### Bowling

```bash
curl "http://localhost:8000/api/v1/teams/India/bowling/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric is wrapped in the envelope. The endpoint returns:
`{ team, innings_bowled, matches, runs_conceded, legal_balls, overs,
wickets, economy, strike_rate, average, dot_pct, fours_conceded,
sixes_conceded, wides, noballs, wides_per_match, noballs_per_match,
avg_opposition_total, worst_conceded, best_defence }`.
The fields that identify an innings (`worst_conceded`, `best_defence`) stay flat.
The subroutes are as for batting, with `/top-bowlers` instead of
`/top-batters`.

### Fielding

```bash
curl "http://localhost:8000/api/v1/teams/India/fielding/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric is wrapped in the envelope. The endpoint returns:
`{ team, matches, catches, caught_and_bowled, stumpings, run_outs,
total_dismissals_contributed, catches_per_match, stumpings_per_match,
run_outs_per_match }`. For the rates per match, the server halves `scope_avg`. Each match has 2
fielding sides, so the value that compares with one team is the total divided by 2.
Subroutes: `/by-season`, `/top-fielders`.

### Partnerships

The group has seven endpoints, all under `/teams/{team}/partnerships/…`. They take the same
filter scope, and also `side` (`batting` or `bowling`), which says whether the partnerships are
FOR or AGAINST the team.

- `.../by-wicket?side=batting` gives the stats for each wicket number, that is, the average partnership
  for the 1st wicket, the 2nd, and so on to the 10th. The numeric metrics (n, avg_runs) are wrapped in
  the envelope for each wicket. best_partnership identifies a partnership, so it stays flat.
- `.../by-inning?side=batting` gives the partnerships of each innings, the 1st and the 2nd. The
  count (n) and avg_runs are wrapped in the envelope, and avg_balls and best_runs stay flat.
- `.../best-pairs` gives the top 3 pairs for each wicket, by total runs together.
- `.../heatmap` gives a matrix of wicket by season for the average partnership.
- `.../top?side=batting&limit=10` gives the top N individual partnerships.
- `.../summary?side=batting` gives the counts (total, 50+, 100+), the highest single partnership,
  the average runs and the top pair of all time. It feeds the partnerships row of the Compare tab
  under Teams. Each numeric metric is wrapped in the envelope for one metric (see "Compare metric
  envelope" below).
- `.../by-season?side=batting` gives a rollup of partnerships for each season (total, 50+, 100+,
  average, best). It feeds the partnerships band on the season-trajectory strip of the Compare
  tab.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/top?gender=male&team_type=international&season_from=2024&limit=1&side=batting"
```

The endpoint returns a list of `{ partnership_id, match_id, date, season,
opposition, wicket_number, batter1, batter2, runs, balls, run_rate,
ended_by_kind }`.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/summary?gender=male&team_type=international"
```

The numeric metrics are wrapped in the envelope. `highest` and `best_pair` identify a
partnership or a pair, so they stay flat.

```json
{
  "team": "India",
  "side": "batting",
  "total":          { "value": 1404, "scope_avg": 32145, "delta_pct": null, "direction": null, "sample_size": 1404 },
  "count_50_plus":  { "value": 226, ... },
  "count_100_plus": { "value": 43, ... },
  "avg_runs":       { "value": 26.4, "scope_avg": 25.1, "delta_pct": 5.2, "direction": "higher_better", "sample_size": 1404 },
  "highest": {
    "runs": 176, "balls": 85, "match_id": 795, "date": "2022-06-28",
    "batter1": { "person_id": "a4cc73aa", "name": "SV Samson" },
    "batter2": { "person_id": "73ad96ed", "name": "DJ Hooda" }
  },
  "best_pair": {
    "batter1": { "person_id": "0a476045", "name": "S Dhawan" },
    "batter2": { "person_id": "740742ef", "name": "RG Sharma" },
    "n": 52, "total_runs": 1743, "best_runs": 160
  }
}
```

### Distribution dossiers (per-innings)

The group has one endpoint for each discipline, and the three are siblings. They mirror a player's
distribution dossiers, such as `/batters/{person_id}/distribution`, at team grain. Each
endpoint returns a self-contained dossier over innings. The dossier has these parts:

- two or three sibling distribution blocks under one master sample, which is the set of innings
  that the dossier counts
- a rollup by phase
- four form windows anchored to the scope (`last_10`, `last_60d`, `last_6mo`, `last_1yr`)
- a Wilson 95% confidence interval (CI) on every probability
- suggested splits derived from the scope

The endpoints IGNORE `FilterParams.filter_team`, because the team in the path wins.
`FilterParams.filter_opponent` works as expected. The optional `as_of_date` (YYYY-MM-DD) fixes the
anchor of the calendar form windows, so that the result does not change from day to day.
Production callers omit it. Spec: `docs/internal/spec-distribution-stats.md` §16.

#### `GET /api/v1/teams/{team}/batting/distribution`

The master sample is each innings that the team batted (`i.team = :team`). The endpoint has two
sibling blocks:

- `runs` is a skewed continuous value. It has chain-ladder conditionals at 100, 150, 200 and 230,
  and an over-aware doubling at the checkpoint of 10 overs.
- `run_rate` is a continuous rate, in runs per over. Its polarity is the reverse of bowler economy,
  because a high run rate is good for batting.

The observation row of each innings carries `runs_at_10`, `wickets_at_10` and `reached_10_overs`.
They feed the over-aware probabilities and the paired magnitude stat, the escalation ratio.

```bash
curl "http://localhost:8000/api/v1/teams/Mumbai%20Indians/batting/distribution?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&as_of_date=2025-01-01"
```

```jsonc
{
  "team": "Mumbai Indians",
  "scope": { "tournament": "Indian Premier League",
             "season_from": "2024", "season_to": "2024" },
  "lifetime": {
    "n_innings": 14,
    "runs": {
      "total": 2568, "mean_per_innings": 183.4286, "median": 182.5,
      "variance": 1537.0, "std": 39.205,
      "escalation_ratio_median": 2.1009,
      "observations": [
        { "innings_id": 11782, "match_id": 5879, "innings_number": 1,
          "date": "2024-03-24",
          "runs": 162, "balls": 120, "wickets": 9,
          "runs_at_10": 88, "wickets_at_10": 2, "reached_10_overs": 1,
          "runs_pp": 52, "balls_pp": 36, "wickets_pp": 2,
          "runs_mid": 74, "balls_mid": 54, "wickets_mid": 1,
          "runs_death": 36, "balls_death": 30, "wickets_death": 6 }
        // ... 14 rows, date-asc
      ],
      "milestones": {
        // simples (denom = n_innings)
        "p_lt_100":  { "value": 0.0,    "num": 0,  "denom": 14, "ci_low": 0.0,  "ci_high": 0.2153 },
        "p_geq_100": { "value": 1.0,    "num": 14, "denom": 14, ... },
        "p_geq_150": { "value": 0.7143, "num": 10, "denom": 14, ... },
        "p_geq_200": { "value": 0.2143, "num": 3,  "denom": 14, ... },
        "p_geq_230": { "value": 0.2143, "num": 3,  "denom": 14, ... },
        // chain ladder — denom = the rung below
        "p_150_given_100": { "value": 0.7143, "num": 10, "denom": 14, ... },
        "p_200_given_150": { "value": 0.3,    "num": 3,  "denom": 10, ... },
        "p_230_given_200": { "value": 1.0,    "num": 3,  "denom": 3,  ... },
        // over-aware: denom = innings with reached_10_overs=1 AND runs_at_10>0
        "p_double_at_10":  { "value": 0.6429, "num": 9,  "denom": 14, ... }
      }
    },
    "run_rate": {
      "pool": 9.594, "mean_per_innings": 9.6296,
      "median_per_innings": 9.55, "variance": 0.4861, "std": 0.6972,
      "per_innings": [9.6, 8.55, /* ... */],
      "milestones": {
        "p_rr_leq_7":  {...}, "p_rr_leq_8":  {...},
        "p_rr_geq_9":  {...}, "p_rr_geq_10": {...}
      }
    },
    "phase": {
      "powerplay": { "runs_total": 789,  "balls_total": 504, "wickets_total": 25, "innings_active": 14 },
      "middle":    { "runs_total": 1131, "balls_total": 756, "wickets_total": 35, "innings_active": 14 },
      "death":     { "runs_total": 648,  "balls_total": 346, "wickets_total": 36, "innings_active": 14 }
    },
    "last_match_date": "2024-05-17"
  },
  "form": {
    "last_10":  { "n_innings": 10, "runs": {...}, "run_rate": {...}, "phase": {...} },
    "last_60d": { "n_innings": 14, ... },
    "last_6mo": { "n_innings": 14, ... },
    "last_1yr": { "n_innings": 14, ... },
    "delta": {
      // 8 entries: 4 windows × 2 metrics (runs_mean + run_rate_pool)
      "last_10_runs_mean_minus_lifetime":      -1.5286,
      "last_10_run_rate_pool_minus_lifetime":   0.072,
      // ... last_60d / last_6mo / last_1yr deltas
    }
  },
  "suggested_splits": [
    { "label": "All Indian Premier League", "params": { "tournament": "Indian Premier League" } },
    { "label": "All cricket in 2024", "params": { "season_from": "2024", "season_to": "2024" } },
    { "label": "All-time", "params": {} }
  ]
}
```

Here the wickets are the team-batting count of "wickets fallen". The count excludes
`'retired hurt'` and `'retired not out'`, which follows the existing convention of team-batting by-phase.

#### `GET /api/v1/teams/{team}/bowling/distribution`

The master sample is the OPPONENT's batting innings under the active filter scope. The team filter
is side-neutral. The match has the team, and the batting side of the innings is NOT the team. The
endpoint has three sibling blocks:

- **`wickets`** is a discrete count. It has the simple probabilities (`p_leq_3`, `p_geq_5`,
  `p_geq_7`, `p_eq_10`) and the conditionals anchored at 5 or more wickets (`p_7_given_5`,
  `p_10_given_5`). It also has the over-aware `p_geq_3_at_10` ("early breakthrough") and
  `p_eq_10_given_3_at_10` ("finishing rate after early breakthrough").
- **`runs_conceded`** mirrors the team-batting `runs` with the polarity reversed, because few runs
  conceded is good. It has five simple probabilities
  (`p_lt_100`/`p_lt_150`/`p_geq_150`/`p_geq_200`/`p_geq_230`), the chain ladder and the over-aware
  doubling (`p_double_at_10`, "opp doubled on us from halfway").
- **`economy`** is the sibling of the economy block of bowler v1, at team grain. It has the same
  schema of pool, per-innings values and median, and the same milestones (`p_econ_leq_6/7`,
  `p_econ_geq_9/10`).

**Wickets exclusion list (TEAM-CREDITED).** The wickets count on this endpoint INCLUDES run-outs,
because the team caused them (a fielder threw the ball). It excludes `'retired hurt'`,
`'retired out'`, `'retired not out'` and `'obstructing the field'`, the four kinds that are not
credited to the team. The count DIVERGES from `/teams/{team}/bowling/summary`, which uses the
bowler-credited exclusion list of 5 elements (it also excludes `'run out'`). Both numbers are
correct, because they answer different questions, "how many wickets did this team take?" and
"how many wickets did our bowlers take?". See `docs/internal/
design-decisions.md` "Team-bowling distribution wicket count"
for the reasons.

```bash
curl "http://localhost:8000/api/v1/teams/Mumbai%20Indians/bowling/distribution?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&as_of_date=2025-01-01"
```

```jsonc
{
  "team": "Mumbai Indians",
  "scope": { "tournament": "Indian Premier League",
             "season_from": "2024", "season_to": "2024" },
  "lifetime": {
    "n_innings": 14,
    "wickets": {
      "total": 85, "mean_per_innings": 6.0714, "median": 6.0,
      "variance": 6.9945, "std": 2.6447,
      "observations": [
        { "innings_id": 11781, "match_id": 5879, "innings_number": 0,
          "date": "2024-03-24",
          "runs_conceded": 168, "balls": 120, "wickets": 6,
          "runs_at_10": 82, "wickets_at_10": 2, "reached_10_overs": 1,
          "runs_pp": 47, "balls_pp": 36, "wickets_pp": 1,
          "runs_mid": 77, "balls_mid": 54, "wickets_mid": 2,
          "runs_death": 44, "balls_death": 30, "wickets_death": 3 }
        // ... 14 rows
      ],
      "milestones": {
        // simples (denom = n_innings)
        "p_leq_3":  { "value": 0.1429, "num": 2,  "denom": 14, ... },
        "p_geq_5":  { "value": 0.6429, "num": 9,  "denom": 14, ... },
        "p_geq_7":  { "value": 0.4286, "num": 6,  "denom": 14, ... },
        "p_eq_10":  { "value": 0.1429, "num": 2,  "denom": 14, ... },
        // ≥5-anchored conditionals (stable denom)
        "p_7_given_5":   { "value": 0.6667, "num": 6, "denom": 9, ... },
        "p_10_given_5":  { "value": 0.2222, "num": 2, "denom": 9, ... },
        // over-aware
        "p_geq_3_at_10":         { "value": 0.3571, "num": 5, "denom": 14, ... },
        "p_eq_10_given_3_at_10": { "value": 0.4,    "num": 2, "denom": 5,  ... }
      }
    },
    "runs_conceded": {
      "total": 2660, "mean_per_innings": 190.0, "median": 188.0,
      "variance": ..., "std": ...,
      "escalation_ratio_median": 2.022,
      "milestones": {
        // simples — polarity flipped vs. team-batting (low = good)
        "p_lt_100":  {...}, "p_lt_150":  {...},
        "p_geq_150": {...}, "p_geq_200": {...}, "p_geq_230": {...},
        // chain ladder (the leakage chain — INDIGO across)
        "p_150_given_100": {...}, "p_200_given_150": {...}, "p_230_given_200": {...},
        // over-aware
        "p_double_at_10": {...}
      }
    },
    "economy": {
      "pool": 9.9069, "mean_per_innings": 9.8699,
      "median_per_innings": 9.95, "variance": ..., "std": ...,
      "per_innings": [...],
      "milestones": { "p_econ_leq_6": {...}, "p_econ_leq_7": {...},
                      "p_econ_geq_9": {...}, "p_econ_geq_10": {...} }
    },
    "phase": { "powerplay": {...}, "middle": {...}, "death": {...} },
    "last_match_date": "2024-05-17"
  },
  "form": {
    "last_10": {...}, "last_60d": {...}, "last_6mo": {...}, "last_1yr": {...},
    "delta": {
      // 12 entries: 4 windows × 3 metrics
      // (wickets_mean + runs_conceded_mean + economy_pool)
    }
  },
  "suggested_splits": [...]
}
```

#### `GET /api/v1/teams/{team}/fielding/distribution`

The master sample is the OPPONENT's batting innings. The endpoint counts the fielding events
credited to any of the team's matchplayers in that match. The `substitute_catches` scalar counts
the substitutes on their own. The endpoint has three sibling count blocks:

- **`catches`** has 4 simple probabilities (`p_eq_0`, `p_geq_3`, `p_geq_5`, `p_geq_7`), and no
  conditional ladder.
- **`run_outs`** has a partition into 3 simple probabilities (`p_eq_0`, `p_eq_1`, `p_geq_2`),
  which sum to 1.
- **`stumpings`** has the same partition into 3. The endpoint **ALWAYS returns it at team grain**,
  because every senior team has had a keeper at some point. A scope with no events returns chips
  that are all zero, with CIs for a small n, rather than null. (The player fielder endpoint
  `/fielders/{person_id}/distribution` differs, because there the stumpings block is null for a
  player who is not a keeper.)

The scalars at the top level are `n_innings_fielded`, `wickets_total` and `substitute_catches`.
The second scalar counts wickets of any kind, for the fielder-ratio tooltip "X catches of Y wickets".

```bash
curl "http://localhost:8000/api/v1/teams/Mumbai%20Indians/fielding/distribution?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&as_of_date=2025-01-01"
```

```jsonc
{
  "team": "Mumbai Indians",
  "scope": { "tournament": "Indian Premier League",
             "season_from": "2024", "season_to": "2024" },
  "lifetime": {
    "n_innings_fielded": 14,
    "wickets_total": 85,
    "substitute_catches": 1,
    "observations": [
      { "innings_id": 11781, "match_id": 5879, "innings_number": 0,
        "date": "2024-03-24",
        "catches": 5, "run_outs": 0, "stumpings": 0,
        "substitute_catches": 0, "wickets_total": 6 }
      // ... 14 rows
    ],
    "catches": {
      "total": 55, "mean_per_innings": 3.9286, "median": 4.0,
      "variance": ..., "std": ...,
      "milestones": {
        "p_eq_0":  { "value": 0.0714, "num": 1,  "denom": 14, ... },
        "p_geq_3": { "value": 0.9286, "num": 13, "denom": 14, ... },
        "p_geq_5": { "value": 0.2857, "num": 4,  "denom": 14, ... },
        "p_geq_7": { "value": 0.0,    "num": 0,  "denom": 14, ... }
      }
    },
    "run_outs": {
      "total": 8, "mean_per_innings": 0.5714, ...,
      "milestones": {
        "p_eq_0":  { "value": 0.6429, "num": 9, "denom": 14, ... },
        "p_eq_1":  { "value": 0.1429, "num": 2, "denom": 14, ... },
        "p_geq_2": { "value": 0.2143, "num": 3, "denom": 14, ... }
      }
    },
    "stumpings": {
      "total": 0, "mean_per_innings": 0.0, ...,
      "milestones": {
        "p_eq_0":  { "value": 1.0, "num": 14, "denom": 14, ... },
        "p_eq_1":  { "value": 0.0, "num": 0,  "denom": 14, ... },
        "p_geq_2": { "value": 0.0, "num": 0,  "denom": 14, ... }
      }
    },
    "last_match_date": "2024-05-17"
  },
  "form": {
    "last_10": {...}, "last_60d": {...}, "last_6mo": {...}, "last_1yr": {...},
    "delta": {
      // 12 entries: 4 windows × 3 metrics
      // (catches_mean + run_outs_mean + stumpings_mean)
    }
  },
  "suggested_splits": [...]
}
```

## `GET /api/v1/teams/{team}/records`

The endpoint returns the record lists of one team. The response has the same shape as
`/series/records`, so that the frontend `RecordsTab` component renders both. Every list is about
the subject team. It reads "team X's …" rather than "any team's … in matches involving X":

| List | Predicate |
|---|---|
| `highest_team_totals` | team X's batting innings |
| `lowest_all_out_totals` | team X's all-out batting innings (≥10 wickets) |
| `biggest_wins_by_runs` | team X is `outcome_winner`, by runs |
| `biggest_wins_by_wickets` | team X is `outcome_winner`, by wickets |
| `largest_partnerships` | partnership where the batting side is team X |
| `best_individual_batting` | a team X batter in a team X innings |
| `best_bowling_figures` | a team X bowler (≥2 wickets gate) |
| `most_sixes_in_a_match` | sixes hit BY team X in a single match, NOT the match-grain total across both sides (the `/series/records` semantic) |

Each list stops at `limit` (default 5, max 20). The endpoint reads from the precomputed tables
`inningstotal`, `inningsbatterperf` and `matchbowlerperf`, which `scripts/populate_*.py` fills.
It honours all the narrowings of the FilterBar and `aux.inning`, which it applies at the match
level for the lists of wins, and at the innings level for the lists of batting and partnerships. The 8 reads run in parallel through `asyncio.gather`.

```bash
curl "http://localhost:8000/api/v1/teams/Mumbai%20Indians/records?tournament=Indian%20Premier%20League&limit=2"
```

```json
{
  "team": "Mumbai Indians",
  "canonical": "Indian Premier League",
  "highest_team_totals":   [ "…" ],
  "lowest_all_out_totals": [ "…" ],
  "biggest_wins_by_runs":  [ "…" ],
  "biggest_wins_by_wickets": [ "…" ],
  "largest_partnerships":  [ "…" ],
  "best_individual_batting": [ "…" ],
  "best_bowling_figures":  [ "…" ],
  "most_sixes_in_a_match": [ "…" ]
}
```

Every row carries `tournament` and `season`, so that the Records subtab can render an Edition
column. In each row it can also render an `(ed)` link to that edition, independent of the season
window of the FilterBar.

## Player position-mix cohort baselines

A cohort is the group that the API compares a subject with, in the same filter scope. For a player, it
is the pool of players. A cohort
baseline is the average of that pool. For batting it is weighted by the player's mix of batting positions,
and for bowling by the player's mix of overs. For fielding and keeping it is split by the keeper flag.

An envelope is a small object that wraps one metric. It holds the player's or the team's value
next to the baseline, with the difference in percent, the direction and the sample size.

The four `/api/v1/scope/averages/players/*` endpoints give these cohort baselines. The player `/summary` endpoints use them when they build each envelope.
You can also call each one on its own for ad-hoc analysis.

The endpoints shipped on 2026-05-20 with the rollout of the player baselines
(`docs/internal/spec-player-compare-average.md`).

All four endpoints share one shape:

- a `cohort: {…}` metadata block
- the headline metrics, each wrapped in an envelope
- a `by_<axis>` array with the aggregates of each bucket, where a bucket is one position or one over

Each endpoint applies a strict cliff on a sliding scale. Take each bucket where the player has a non-zero
mix weight. If the cohort sample in any of them is below the threshold of that bucket, the `scope_avg` of
the whole response is null. Then `cliff_buckets` lists the buckets that failed.

### `GET /api/v1/scope/averages/players/batting/summary`

The cohort baseline for batting is weighted by the player's mix of batting positions. The mix vector is 10
floats that sum to 1.0 ± 0.001. Index 0 is the opener, which merges positions 1 and 2, and the next nine
are #3 to #11.

```bash
curl "http://localhost:8000/api/v1/scope/averages/players/batting/summary?tournament=Indian+Premier+League&position_mix=0.54,0.38,0.05,0.03"
```

The response has six headline metrics, each wrapped in an envelope (`innings_batted`,
`runs`, `average`, `strike_rate`, `boundary_pct`, `dot_pct`). It also has the cohort metadata
(`n_players`, `n_innings_total`, the input `position_mix`) and `by_position[10]`. That array gives the
aggregates, the threshold and the `below_support` flag of each bucket.

The threshold of each bucket is in `cohort innings`. It is linear, `27 − 2·bucket`, where the bucket
number counts from 1. Bucket 1 is the opener (index 0 of the mix vector) and bucket 10 is #11. So the
thresholds are 25, 23, 21, 19, 17, 15, 13, 11, 9 and 7, and each row of `by_position` carries its
`bucket` number.

### `GET /api/v1/scope/averages/players/bowling/summary`

The cohort baseline for bowling is weighted by the player's mix of overs. The mix vector is 20 floats,
indexed by the 0-based over. Index 0 is "Over 1", and the tooltips and labels show the overs counted from 1.

```bash
curl "http://localhost:8000/api/v1/scope/averages/players/bowling/summary?tournament=Indian+Premier+League&over_mix=0.02,0.10,0.05,0.10,0.07,0.08,0.02,0.01,0.01,0.01,0.03,0.04,0.05,0.04,0.05,0.04,0.10,0.07,0.08,0.03"
```

The response has six headline rates (`economy`, `average`, `strike_rate`,
`dot_pct`, `wickets_per_over`, `boundary_pct`) and `by_over[20]`.

The threshold of each over is in `cohort legal_balls`, and it has a U shape:

- 60 at overs 1 to 2 and 20
- 50 at overs 3 to 6 and 16 to 19
- 30 at overs 7 to 15

### `GET /api/v1/scope/averages/players/fielding/summary`

The cohort baseline for fielding is split by the keeper flag. It is NOT weighted by position. By dimensional
analysis, the catches per match of each position do not combine into a comparable rate (see
`spec-player-compare-average.md` §5.4). The query takes `?is_keeper=0|1`.

```bash
curl "http://localhost:8000/api/v1/scope/averages/players/fielding/summary?tournament=Indian+Premier+League&is_keeper=1"
```

The response has four headline rates (`catches_per_match`, `stumpings_per_match`,
`run_outs_per_match`, `dismissals_per_match`) and `by_dismissed_position[10]`. That array gives sub-rates
for each position of the dismissed batter, for the deferred `spec-fielding-impact.md`.

The keeper partition is per (person, scope). For example, a player who kept wicket in 2023 but not in 2024
belongs to the outfielder cohort for 2024 only. Substitute catches are excluded from the numerator. The
endpoint follows the semantics of the distribution side, as CLAUDE.md says, "Substitute fielders INCLUDED
in /leaders, EXCLUDED in /distribution".

### `GET /api/v1/scope/averages/players/keeping/summary`

The cohort baseline for keeping has keepers only. Its per-match rates divide by `matches_as_keeper`
and not by the total matches, so that the matches in the outfield do not dilute the keeping rate.
It takes no mix parameter, because the partition is a simple binary one.

```bash
curl "http://localhost:8000/api/v1/scope/averages/players/keeping/summary?tournament=Indian+Premier+League"
```

The response has four headline rates, for catches, stumpings, run_outs and dismissals, each
`_per_match`. Byes per innings are deferred. They need a join of keeperassignment and delivery, and
playerscopestats does not precompute it.

### `drop=` query parameter

Every `/scope/averages/players/*` endpoint accepts `?drop=`. Its value is a comma-separated list of axis
names to mask before the clauses are built. The names are `gender, team_type, tournament, season,
filter_venue, filter_team, filter_opponent, team_class,
series_type`.

Each endpoint carries the parameter as plumbing for surfaces where a baseline can turn tautological. Examples
are the H2H (head-to-head) baselines of the next spec, the venue character strips and the comparisons
across tournament eras. An unknown axis name gives a 400. Surface 1 itself does not use the parameter.

### Per-season / per-phase / per-over cohort endpoints (`person_id`)

Unlike the mix-vector `/summary` endpoints above, these endpoints take
`?person_id=` and NOT a mix vector. The server derives the player's mix of positions or overs, and it
returns the cohort broken down by season, phase or over. They give the green cohort reference lines
on the by-season, by-phase and by-over charts.

```bash
# batting cohort by season (person derives the position mix)
curl "http://localhost:8000/api/v1/scope/averages/players/batting/by-season?person_id=ba607b88&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2016&season_to=2016"
```

- `…/batting/by-season`, `…/bowling/by-season` and `…/fielding/by-season`
  return `{ by_season: [ { season, mix, n_players, n_innings, below_support,
  cliff_buckets, strike_rate, runs_per_innings, … } ] }`.
- `…/{batting,bowling,fielding}/by-phase` returns `{ by_phase: [ { phase,
  phase_bucket, mix, n_players, …, strike_rate / economy / dismissals_per_match } ] }`,
  with 3 entries, for powerplay, middle and death.
- `…/batting/by-over` returns `{ by_over: [ {over, n_balls, n_players, n_innings,
  threshold, below_support, strike_rate, dot_pct, boundary_pct, runs_per_innings,
  dismissals} ], cohort: {…} }`, with 20 entries.

**The cohort narrows live under the six off-key filters.** The six are venue, opponent, team, inning,
toss and result. When any of them is set, all of the
`/scope/averages/players/*` cohort endpoints narrow the comparison pool. So do the cohort blocks that the
`/batters|/bowlers|/fielders/{person_id}` handlers build.

The handler dispatches on `is_precomputed_scope`. When none of the six is set, it reads the precomputed
values. When any of them is set, it aggregates live. With none of the six set, the live aggregation gives
the precomputed value byte for byte. `inning` uses the Option-B flip, so bowling and fielding count the
innings in which the team did not bat. Toss and result key on the relevant side.

The weighting by the mix histogram of positions or overs stays coarse by design, at the grain of
tournament and season. Only the cohort values of each bucket narrow. See
`docs/internal/how-stats-calculated.md` §"Cohort baselines narrow live" and
`spec-tier3-cohort-narrowing.md`.

---

## Compare metric envelope

The five team-compare summary endpoints wrap each numeric metric in an envelope of its own. The endpoints
are
`/teams/{team}/{summary,batting/summary,bowling/summary,fielding/summary,partnerships/summary}`.
Each envelope has this shape:

```json
{
  "value":       8.52,
  "scope_avg":   7.94,
  "delta_pct":   7.3,
  "direction":   "higher_better",
  "sample_size": 1606
}
```

- `value` is the team's raw value.
- `scope_avg` is the league baseline in the same FilterBar scope. The server computes it with the same
  SQL and `team=None`. For per-match fielding rates, the league pool is halved so that it compares with
  one team, because each match has 2 fielding sides.
- `delta_pct` is the signed `(value - scope_avg) / scope_avg × 100`,
  rounded to 1 decimal. It is `null` for count metrics, for example `fours`,
  `wickets` and `total_runs`, where the league total dwarfs the team total. For those metrics the
  percentage can be computed, but it has no useful meaning as "above/below average".
- `direction` is `"higher_better"`, `"lower_better"` or `null`. Each metric has a constant in
  `api/metrics_metadata.py::METRIC_DIRECTIONS`.
- `sample_size` is the denominator that makes the comparison defensible. It is legal_balls for batting
  rates, balls_bowled for bowling rates, partnerships for partnership stats and matches for outcome rates.

The nested objects that carry an identity (`highest_total`, `lowest_all_out_total`,
`worst_conceded`, `best_defence`, `best_pair`, `keepers`,
`gender_breakdown`) stay flat, because they are not metrics.

Today the Teams > Compare UI reads only `value`. The other fields are
there for the Spec-2 surfaces, which are player compare, the delta columns of the leaderboards and the H2H
baseline (see `docs/internal/outlook-comparisons.md`).

The new `/scope/averages/*` endpoints below stay flat. They are the baseline data, and not a view of one
entity with its baseline.

---

# Scope averages (`/api/v1/scope/averages/…`)

Source: `api/routers/scope_averages.py`. These endpoints are the counterpart of the team endpoints for the
"average team", the league baseline. They use the same FilterBar scope with no team filter, and they
return pool-weighted aggregates across every team in the filtered window. They drive the Average column on
the Teams > Compare tab, and the expansions for the phase bands and the season trajectory.

All endpoints accept the standard FilterBar params (`gender`,
`team_type`, `tournament`, `season_from`, `season_to`,
`filter_venue`, `team_class`, `series_type`), and the aux `scope_to_team` of the avg slot.

- `scope_to_team` narrows the tournament universe to the team's events when no tournament filter is
  set. The frontend applies it only for `team_type='club'`, and internationals default to the full pool.
- `team_class` is polymorphic: `full_member` on intl, `primary_club` / `secondary_club` on clubs.

**Per-innings semantic (since 2026-04-26).** Every numeric field on these endpoints returns a per-INNINGS
average, which is what one batting, bowling or fielding innings yields in the scope. It is NOT a pool
aggregate. The exceptions are the match-level totals on `/scope/averages/summary`, and the payloads that
carry an identity, such as `highest_total` and `best_partnership`. See
`docs/internal/perf-bucket-baselines.md`, "What 'average' means", for the table of each metric.

The response drops `innings_batted` and `innings_bowled`, because under the per-innings semantic they would
always be 1. The per-match rates, for example `catches_per_match` and `wides_per_match`, are halved at the
source. They then give a rate for each fielding side or bowling side, which compares with one team's
contribution per match.

The response shape mirrors the team siblings, with two differences:

1. There is no top-level `team` field, because there is no team identity.
2. The nested objects that carry an identity are kept where they mean something at the scope level.
   `highest_total` carries the team that scored it, and the league's `best_partnership` at each wicket
   carries the identity of the pair. The "average team's best pair" does not exist, so the partnerships
   endpoint omits the summary-level `best_pair`.

| Endpoint | Mirrors |
|---|---|
| `/scope/averages/summary` | `/teams/{team}/summary` (results) |
| `/scope/averages/batting/summary` | `/teams/{team}/batting/summary` |
| `/scope/averages/batting/by-phase` | `/teams/{team}/batting/by-phase` |
| `/scope/averages/batting/by-season` | `/teams/{team}/batting/by-season` |
| `/scope/averages/bowling/summary` | `/teams/{team}/bowling/summary` |
| `/scope/averages/bowling/by-phase` | `/teams/{team}/bowling/by-phase` |
| `/scope/averages/bowling/by-season` | `/teams/{team}/bowling/by-season` |
| `/scope/averages/fielding/summary` | `/teams/{team}/fielding/summary` |
| `/scope/averages/fielding/by-season` | `/teams/{team}/fielding/by-season` |
| `/scope/averages/partnerships/summary` | `/teams/{team}/partnerships/summary` |
| `/scope/averages/partnerships/by-wicket` | `/teams/{team}/partnerships/by-wicket` |
| `/scope/averages/partnerships/by-season` | `/teams/{team}/partnerships/by-season` |

```bash
curl "http://localhost:8000/api/v1/scope/averages/batting/summary?tournament=Indian+Premier+League&season_from=2024&season_to=2024"
```

```json
{
  "total_runs": 182.89,
  "legal_balls": 114.78,
  "run_rate": 9.56,
  "boundary_pct": 21.1,
  "dot_pct": 32.9,
  "fours": 15.31,
  "sixes": 8.88,
  "avg_1st_innings_total": 189.6,
  "avg_2nd_innings_total": 176.2,
  "highest_total": {
    "runs": 287,
    "team": "Sunrisers Hyderabad",
    "match_id": 5904,
    "innings_number": 1
  }
}
```

Under the per-innings semantic, `total_runs: 182.89` reads as "an avg batting innings in IPL 2024 scored
182.89 runs". `fours: 15.31` means about 15 fours per innings. The rates (`run_rate`, `boundary_pct`,
`dot_pct`, `avg_*_innings_total`) are unchanged from the pool, because they are per innings by nature.
`highest_total` is a single observation that carries an identity, not an average.

```bash
curl "http://localhost:8000/api/v1/scope/averages/summary?tournament=Indian+Premier+League&season_from=2024&season_to=2024"
```

It returns `{ matches, decided, ties, no_results, toss_decided,
bat_first_wins, field_first_wins, bat_first_win_pct }`. The `bat_first_win_pct` is the most informative
signal at the league level. It reads as "bat first wins X% of matches in this scope."

---

# Batters (`/api/v1/batters/{person_id}/…`)

Source: `api/routers/batting.py`. `{person_id}` is the cricsheet hex person id, which the `/players` search
gives. All the endpoints accept the common filters, and contextual ones as well.

## `GET /api/v1/batters/{person_id}/summary`

It gives the career totals within the filters. It drives the StatCard row on a player's batting page, and
the Batting band on `/players`.

**Runs are all-ball.** `runs`, `fours` and `sixes` sum the batter's off-bat runs over all his
deliveries, so a four hit off a no-ball is his. `balls` and `dots` count legal balls only, so
`strike_rate` is the all-ball runs over the legal balls. Every batting endpoint and the cohort baselines use
this one convention (`spec-batting-allball-runs-single-
source.md`). The switch to it raised V Kohli's career runs from 13117, the old legal-only number, to 13166.

**Response shape, Phase 4 envelope migration (2026-05-20).** Each numeric field is a `MetricEnvelope`
object (`{value, scope_avg,
delta_pct, direction, sample_size}`). It carries the player's value next to a cohort baseline that is
weighted by the position mix. The fields that carry an identity stay flat (`highest_score`, `name`,
`person_id`, `nationalities`). See "Player position-mix cohort baselines" above,
and `docs/internal/spec-player-compare-average.md`.

The counts (`matches, innings, runs, hundreds, …`) have `direction: null`, so their `delta_pct` is always
null. The rates (`average`, `strike_rate`, `dot_pct`, `boundary_pct`, `balls_per_*`) carry a direction and
a signed `delta_pct` against the cohort.

The response also includes a `position_distribution: [10]` array, with the aggregates of each position.
They feed the position histogram of the next spec. The response also has a `cohort: {…}` metadata block,
and the `cohort_below_support` and `cohort_cliff_buckets` flags, which show the result of the sliding-scale
gate.

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/summary?tournament=Indian+Premier+League"
```

```jsonc
{
  "person_id": "ba607b88", "name": "V Kohli",
  "nationalities": [{"team":"India","gender":"male","matches":118}],
  "highest_score": 113,
  "matches":      {"value": 271,  "scope_avg": null,   "delta_pct": null,   "direction": null,            "sample_size": 18852},
  "innings":      {"value": 271,  "scope_avg": 15.85,  "delta_pct": null,   "direction": null,            "sample_size": 18852},
  "runs":         {"value": 9126, "scope_avg": 437.12, "delta_pct": null,   "direction": null,            "sample_size": 18852},
  "dismissals":   {"value": 228,  "scope_avg": null,   "delta_pct": null,   "direction": null,            "sample_size": 18852},
  "not_outs":     {"value":  43,  "scope_avg": null,   "delta_pct": null,   "direction": null,            "sample_size": 18852},
  "average":      {"value": 40.03,"scope_avg": 29.5,   "delta_pct": 35.7,   "direction": "higher_better", "sample_size": 18852},
  "strike_rate":  {"value": 134.34,"scope_avg": 134.7, "delta_pct": -0.3,   "direction": "higher_better", "sample_size": 18852},
  "dot_pct":      {"value": 31.7, "scope_avg": 36.2,   "delta_pct": -12.4,  "direction": "lower_better",  "sample_size": 18852},
  "boundary_pct": {"value": 16.7, "scope_avg": 18.4,   "delta_pct": -9.2,   "direction": "higher_better", "sample_size": 18852},
  // … fours, sixes, boundaries, hundreds, fifties, thirties, ducks,
  // balls_faced, dots, balls_per_{four,six,boundary} also envelope-wrapped.
  "position_distribution": [
    {"bucket":1,"innings":140,"runs":5481,"legal_balls":3883,"dismissals":116,"fours":499,"sixes":134,"dots":1182},
    {"bucket":2,"innings":93, "runs":2809,"legal_balls":2266,"dismissals":80, "fours":252,"sixes":86, "dots":702},
    /* … 10 entries total */
  ],
  "cohort": {
    "match_dimension": "position_mix",
    "position_mix": [0.517, 0.343, 0.048, 0.030, 0.048, 0.015, 0, 0, 0, 0],
    "n_players": 735,
    "n_innings_total": 18852
  },
  "cohort_below_support": false,
  "cohort_cliff_buckets": []
}
```

**Non-striker dismissals (fix shipped 2026-05-20).** The `dismissals` and `not_outs` counts include the
wickets where the batter was at the non-striker's end. Examples are run-outs at the bowler's end, and the
rare obstructing or handled-the-ball as non-striker. Before the fix, this endpoint did not see those
dismissals, because the per-innings query filtered `d.batter_id = :pid` AND used a LEFT JOIN on wicket. In
cricket.db, 4.2% of dismissals are non-striker dismissals. For Kohli at IPL, the fix moved the count from
226 to 228.

## `GET /api/v1/batters/{person_id}/by-innings`

It gives the innings list for the Innings List tab. Params: `limit` (default 50), `offset` and `sort` (for
example `date`, `runs` or `strike_rate`).

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/by-innings?limit=1"
```

```json
{
  "innings": [
    {
      "match_id": 13015, "date": "2026-04-12",
      "team": "Royal Challengers Bengaluru", "opponent": "Mumbai Indians",
      "venue": "Wankhede Stadium",
      "tournament": "Indian Premier League",
      "runs": 50, "balls": 38, "fours": 5, "sixes": 1,
      "strike_rate": 131.58, "not_out": false,
      "how_out": "caught", "dismissed_by": "HH Pandya"
    }
  ],
  "total": 375
}
```

## `GET /api/v1/batters/{person_id}/vs-bowlers`

It gives the matchup table. Params: `bowler_id` (optional, for the drilldown to one bowler) and
`min_balls` (default 6).

It returns `{ matchups: [ { bowler_id, bowler, balls, runs,
dismissals, strike_rate, average, … } ] }`.

## `GET /api/v1/batters/{person_id}/by-over`

It gives the stats of each over, 1 to 20. It returns `{ by_over: [ { over, balls,
runs, strike_rate, dismissals, … } ] }`.

## `GET /api/v1/batters/{person_id}/by-phase`

It splits the stats into the powerplay, middle and death phases. It returns `{ by_phase: [ { phase, balls,
runs, strike_rate, … } ] }`.

## `GET /api/v1/batters/{person_id}/by-season`

It gives the career trajectory season by season. It returns `{ by_season: [ { season, balls,
runs, dismissals, average, strike_rate, innings, fifties, hundreds,
dots, boundaries, … } ] }`.

## `GET /api/v1/batters/{person_id}/dismissals`

It gives the dismissal analysis. It returns the counts by `kind`, a breakdown by the primary `bowler_type`,
and the distribution of dismissals by phase. The Dismissals donut and bars use it.

## `GET /api/v1/batters/{person_id}/inter-wicket`

It gives the analysis of partnership segments, which are the runs and the rate in each span of an innings
between two wickets. It returns `{ inter_wicket: [ { after_wicket, avg_runs,
avg_balls, run_rate, n } ] }`.

## `GET /api/v1/batters/{person_id}/records`

It gives the batting record lists of one player. There are six top-N lists, each capped at `limit`
(default 10, max 20):

- `highest_scores`: by runs DESC, with balls ASC as the tiebreak.
- `fastest_50s`: innings that reach 50, by balls ASC.
- `fastest_100s`: innings that reach 100, by balls ASC.
- `most_sixes_innings`: by sixes DESC.
- `most_fours_innings`: by fours DESC.
- `best_strike_rates`: by SR DESC, with a gate of at least 20 balls. The 20-ball floor filters out
  cameos of 1 ball and 6 runs.

The endpoint reads from `inningsbatterperf`, a precomputed aggregate for each (batter, innings) that
`scripts/populate_records_aggregates.py` fills. It honours all the FilterBar narrowings and `aux.inning`.
Runs are all-ball, so off-bat runs off no-balls are included, and balls faced are legal-only.

The table carries a row of 0 runs and 0 balls for each pure non-striker innings. A batter who never
faced a ball as striker still batted, so the table's innings count matches the summary's. Not-out excludes
retired hurt and retired out.

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/records?tournament=Indian%20Premier%20League&limit=3"
```

```json
{
  "person_id": "ba607b88",
  "name": "V Kohli",
  "highest_scores": [
    { "runs": 113, "balls": 48, "fours": 12, "sixes": 8, "not_out": false,
      "figures": "113 (48)", "strike_rate": 235.4,
      "match_id": 6592, "team": "Royal Challengers Bengaluru",
      "opponent": "Punjab Kings", "tournament": "Indian Premier League",
      "season": "2016", "date": "2016-05-18" }
  ],
  "fastest_50s":   [ "…" ],
  "fastest_100s":  [ "…" ],
  "most_sixes_innings":  [ "…" ],
  "most_fours_innings":  [ "…" ],
  "best_strike_rates":   [ "…" ]
}
```

Every row carries `tournament` and `season`, so the frontend Records subtab can show an Edition column.
Each row can also show an `(ed)` link to that tournament and season.

## `GET /api/v1/batters/{person_id}/distribution`

It gives a dossier of the runs distribution per innings. The dossier has these parts:

- aggregates for the lifetime and for the form windows (mean, median, variance, std, average)
- milestone probabilities (`p_failure_10`, `p_25_plus`, `p_50_plus`, `p_100_plus`)
- a phase decomposition, with the runs and balls of each phase (powerplay, middle, death), and the phase
  columns of each innings on every observation
- hints for the suggested-splits navigation, derived from the scope ("All IPL", "All cricket in 2024",
  "All-time")

The form windows are the last 10 innings and the last 60 days, and both have the same shape as the
lifetime block. A `delta` block reports the window mean minus the lifetime mean, and the window median
minus the lifetime median. The optional `as_of_date` (YYYY-MM-DD) anchors the last-60-day window
deterministically, and production callers omit it. Spec:
`docs/internal/spec-distribution-stats.md` §8.

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/distribution?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&as_of_date=2025-01-01"
```

```jsonc
{
  "scope": { "tournament": "Indian Premier League",
             "season_from": "2024", "season_to": "2024" },
  "lifetime": {
    "n_innings": 15, "n_dismissals": 12, "n_notouts": 3,
    "runs": {
      "total": 741, "balls_total": 479,
      "mean_per_innings": 49.4, "median": 42,
      "variance": 982.83, "std": 31.35, "average": 61.75,
      "observations": [
        { "innings_id": 11773, "match_id": 5875, "date": "2024-03-22",
          "runs": 21, "balls": 20, "dismissed": true,
          "fours": 0, "sixes": 1, "dots": 6,
          "runs_pp": 4, "balls_pp": 6,
          "runs_mid": 17, "balls_mid": 14,
          "runs_death": 0, "balls_death": 0 }
        // ... (15 entries, date-asc)
      ]
    },
    "milestones": { "p_failure_10": 0.0667, "p_25_plus": 0.7333,
                    "p_50_plus": 0.4, "p_100_plus": 0.0667 },
    "phase": {
      "powerplay": { "runs_total": 373, "balls_total": 231, "innings_active": 15 },
      "middle":    { "runs_total": 271, "balls_total": 198, "innings_active": 11 },
      "death":     { "runs_total":  97, "balls_total":  50, "innings_active":  5 }
    }
  },
  "form": {
    "last_10":  { "n_innings": 10, "runs": {/* same shape */}, "milestones": {...}, "phase": {...} },
    "last_60d": { "n_innings": 0,  "runs": {/* null shape */}, "milestones": {...}, "phase": {...} },
    "delta": {
      "last_10_mean_minus_lifetime": -6.9,
      "last_10_median_minus_lifetime": 0.0,
      "last_60d_mean_minus_lifetime": null,
      "last_60d_median_minus_lifetime": null
    }
  },
  "suggested_splits": [
    { "label": "All Indian Premier League",
      "params": { "tournament": "Indian Premier League" } },
    { "label": "All cricket in 2024",
      "params": { "season_from": "2024", "season_to": "2024" } },
    { "label": "All-time", "params": {} }
  ]
}
```

---

# Bowlers (`/api/v1/bowlers/{person_id}/…`)

Source: `api/routers/bowling.py`. The bowler endpoints follow the same pattern as the batter
endpoints.

## `GET /api/v1/bowlers/{person_id}/summary`

The response has the same Phase 4 envelope shape as `/batters/{person_id}/summary` (see above).
In the envelope, each numeric field is an object with its value, the scope average, the difference
in percent, the direction and the sample size. The mix axis is the over mix, with 20 elements, and
the cohort thresholds form a U shape over the overs. The identity fields, `overs` (a formatted
string) and `best_figures`, stay flat. The response also includes the `over_distribution[20]` array
and the `cohort: {…}` metadata.

```bash
curl "http://localhost:8000/api/v1/bowlers/462411b3/summary?tournament=Indian+Premier+League"
```

```jsonc
{
  "person_id": "462411b3", "name": "JJ Bumrah",
  "overs": "597.1", "best_figures": "5/10",
  "matches":       {"value": 156,  "scope_avg": null,   "delta_pct": null,  "direction": null,           "sample_size": 280513},
  "wickets":       {"value": 186,  "scope_avg": null,   "delta_pct": null,  "direction": null,           "sample_size": 280513},
  "runs_conceded": {"value": 4490, "scope_avg": null,   "delta_pct": null,  "direction": null,           "sample_size": 280513},
  "average":       {"value": 24.14,"scope_avg": 29.85,  "delta_pct": -19.1, "direction": "lower_better", "sample_size": 280513},
  "economy":       {"value": 7.52, "scope_avg": 8.96,   "delta_pct": -16.1, "direction": "lower_better", "sample_size": 280513},
  "strike_rate":   {"value": 19.26,"scope_avg": 20.68,  "delta_pct": -6.9,  "direction": "lower_better", "sample_size": 280513},
  "dot_pct":       {"value": 40.0, "scope_avg": 34.9,   "delta_pct": 14.6,  "direction": "higher_better","sample_size": 280513},
  // … other numerics envelope-wrapped.
  "over_distribution": [/* 20 entries — see /scope/averages/players/bowling/summary */],
  "cohort": {"match_dimension":"over_mix","over_mix":[…20…],"n_players":573,"n_balls_total":280513},
  "cohort_below_support": false, "cohort_cliff_buckets": []
}
```

**Note (CLAUDE.md convention):** bowling uses `runs_conceded` and
`wickets`, not `runs`/`dismissals`. Do not reuse the batting types.

## `GET /api/v1/bowlers/{person_id}/distribution`

The endpoint returns a dossier of the bowler's distributions per innings. It has three sibling
distribution blocks, all from one master sample:

- **`wickets`** is a zero-inflated distribution of a discrete count, the wickets taken in each
  innings. It has six simple probabilities
  (`p_zero`/`p_geq_1`/`p_geq_2`/`p_geq_3`/`p_geq_4`/`p_geq_5`)
  and three conditionals anchored at 2 or more wickets (`p_3_given_2`/`p_4_given_2`/
  `p_5_given_2`). Every conditional has the denominator `count(w ≥ 2)`,
  so the noise stays stable across the rare upper rungs. A chain of
  conditionals such as `P(≥5│≥4)` would shrink the denominator
  geometrically and give confidence intervals of ±20pp at the top
  rung. The anchor keeps the denominator bounded by `count(≥2)`.
- **`runs_conceded`** is a skewed continuous distribution, with simple probabilities only
  (`p_leq_15`/`p_leq_25`/`p_geq_40`/`p_geq_50`).
- **`economy`** is a continuous rate per over. It gives both `pool`
  (weighted by balls, the conventional career number) and
  `mean_per_innings` (the unweighted mean of the runs per over in each innings). The two
  answer different questions. The histograms read against
  `mean_per_innings` for the visual centre of mass, and the summary text
  reads against `pool`. Its simple probabilities are
  `p_econ_leq_6`/`p_econ_leq_7`/`p_econ_geq_9`/`p_econ_geq_10`.

The response also has these parts:

- a phase decomposition, with the runs, balls and wickets in each phase (powerplay, middle and
  death), and phase columns for each innings on every observation
- four form windows, for the last 10 innings, the last 60 days, the last 6 months and the last year
- scalars from the pool (`pool_strike_rate` and `pool_average`)
- suggested splits that come from the scope

**Every probability field** comes as
`{ value, num, denom, ci_low, ci_high }`, with a Wilson 95%
confidence interval. `value`, `ci_low` and `ci_high` are `null`
when `denom == 0`, because the ratio is undefined.

**Master sample.** The master sample has one row per `(match, innings the bowler bowled in)`
that clears the `min_balls` threshold for a qualifying innings. The default is
`min_balls=12` (2 legal overs). Pass `min_balls=0` to include
cameos of 1 ball. The response echoes the threshold in
`response.thresholds.min_balls`.

The optional `as_of_date` (YYYY-MM-DD) anchors the calendar form
windows to a fixed date, so that the result is deterministic. Production callers omit it. Spec:
`docs/internal/spec-distribution-stats.md` §11.

```bash
curl "http://localhost:8000/api/v1/bowlers/462411b3/distribution?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&as_of_date=2025-01-01"
```

```jsonc
{
  "scope": { "tournament": "Indian Premier League",
             "season_from": "2024", "season_to": "2024" },
  "thresholds": { "min_balls": 12 },
  "lifetime": {
    "n_innings": 13,
    "pool_strike_rate": 15.55,
    "pool_average": 17.05,
    "wickets": {
      "total": 20, "mean_per_innings": 1.5385, "median": 1,
      "variance": 2.6026, "std": 1.6132,
      "observations": [
        { "innings_id": 11781, "match_id": 5879, "date": "2024-03-24",
          "balls": 24, "runs_conceded": 15, "wickets": 3,
          "dots": 13, "boundaries_conceded": 1,
          "wides": 0, "noballs": 0,
          "runs_pp": 4, "balls_pp": 6, "wickets_pp": 1,
          "runs_mid": 2, "balls_mid": 6, "wickets_mid": 0,
          "runs_death": 9, "balls_death": 12, "wickets_death": 2 }
        // ... (13 entries, date-asc)
      ],
      "milestones": {
        "p_zero":      { "value": 0.3846, "num": 5, "denom": 13, "ci_low": 0.1771, "ci_high": 0.6448 },
        "p_geq_1":     { "value": 0.6154, "num": 8, "denom": 13, "ci_low": 0.3552, "ci_high": 0.8229 },
        "p_geq_2":     { "value": 0.4615, "num": 6, "denom": 13, "ci_low": 0.2321, "ci_high": 0.7086 },
        "p_geq_3":     { "value": 0.3077, "num": 4, "denom": 13, "ci_low": 0.1268, "ci_high": 0.5763 },
        "p_geq_4":     { "value": 0.0769, "num": 1, "denom": 13, "ci_low": 0.0137, "ci_high": 0.3331 },
        "p_geq_5":     { "value": 0.0769, "num": 1, "denom": 13, "ci_low": 0.0137, "ci_high": 0.3331 },
        "p_3_given_2": { "value": 0.6667, "num": 4, "denom":  6, "ci_low": 0.3000, "ci_high": 0.9032 },
        "p_4_given_2": { "value": 0.1667, "num": 1, "denom":  6, "ci_low": 0.0301, "ci_high": 0.5635 },
        "p_5_given_2": { "value": 0.1667, "num": 1, "denom":  6, "ci_low": 0.0301, "ci_high": 0.5635 }
      }
    },
    "runs_conceded": {
      "total": 341, "mean_per_innings": 26.2308, "median": 23,
      "variance": 70.859, "std": 8.4178,
      "milestones": {
        "p_leq_15": { "value": 0.0769, "num": 1, "denom": 13, "ci_low": 0.0137, "ci_high": 0.3331 },
        "p_leq_25": { "value": 0.5385, "num": 7, "denom": 13, "ci_low": 0.2914, "ci_high": 0.7679 },
        "p_geq_40": { "value": 0.0769, "num": 1, "denom": 13, "ci_low": 0.0137, "ci_high": 0.3331 },
        "p_geq_50": { "value": 0.0,    "num": 0, "denom": 13, "ci_low": 0.0,    "ci_high": 0.2281 }
      }
    },
    "economy": {
      "pool": 6.5788, "mean_per_innings": 6.5727, "median_per_innings": 5.75,
      "variance": 4.3645, "std": 2.0891,
      "per_innings": [3.75, 9.0, 6.75 /* ... 13 entries */],
      "milestones": {
        "p_econ_leq_6":  { "value": 0.5385, "num": 7, "denom": 13, "ci_low": 0.2914, "ci_high": 0.7679 },
        "p_econ_leq_7":  { "value": 0.6923, "num": 9, "denom": 13, "ci_low": 0.4237, "ci_high": 0.8732 },
        "p_econ_geq_9":  { "value": 0.3077, "num": 4, "denom": 13, "ci_low": 0.1268, "ci_high": 0.5763 },
        "p_econ_geq_10": { "value": 0.1538, "num": 2, "denom": 13, "ci_low": 0.0432, "ci_high": 0.4202 }
      }
    },
    "phase": {
      "powerplay": { "runs_total": 128, "balls_total": 126, "wickets_total":  6, "innings_active": 13 },
      "middle":    { "runs_total":  62, "balls_total":  60, "wickets_total":  4, "innings_active": 11 },
      "death":     { "runs_total": 151, "balls_total": 125, "wickets_total": 10, "innings_active": 13 }
    }
  },
  "form": {
    "last_10":  { "n_innings": 10, /* same shape — wickets/runs_conceded/economy/phase + scalars */ },
    "last_60d": { "n_innings": 0,  /* null shape: pool stats null, milestones with zero denom */ },
    "last_6mo": { "n_innings": 0,  /* ... */ },
    "last_1yr": { "n_innings": 13, /* ... */ },
    "delta": {
      "last_10_wickets_mean_minus_lifetime":  0.1615,
      "last_10_economy_pool_minus_lifetime":  0.0237,
      "last_60d_wickets_mean_minus_lifetime": null,
      "last_60d_economy_pool_minus_lifetime": null,
      "last_6mo_wickets_mean_minus_lifetime": null,
      "last_6mo_economy_pool_minus_lifetime": null,
      "last_1yr_wickets_mean_minus_lifetime": 0.0,
      "last_1yr_economy_pool_minus_lifetime": 0.0
    }
  },
  "suggested_splits": [
    { "label": "All Indian Premier League",
      "params": { "tournament": "Indian Premier League" } },
    { "label": "All cricket in 2024",
      "params": { "season_from": "2024", "season_to": "2024" } },
    { "label": "All-time", "params": {} }
  ]
}
```

## `GET /api/v1/bowlers/{person_id}/records`

The endpoint returns the bowling records of one player, in two top-N lists. `limit` caps each
list (default 10, max 20):

- `best_figures`: wickets DESC, with runs ASC as the tiebreak. A match needs at least 2 wickets.
- `most_economical`: economy ASC. A match needs at least 18 balls (3 overs).

The endpoint reads from `matchbowlerperf`, an aggregate per bowler and match that
`_populate_match_bowler_perf` in `scripts/populate_records_aggregates.py` precomputes. The table
has no column for the innings, so the endpoint applies `aux.inning`, the auxiliary filter for the
innings, as a filter on matches (`api/filters.py::player_inning_match_clause`, side `bowling`). With
`inning=N`, it keeps the matches in which the bowler's team fielded in innings 1−N. The table leaves
out super overs, and a bowler bowls in one regular innings of a match, the innings in which the
opponent bats. So the lists are the bowler's records in that innings.

```bash
curl "http://localhost:8000/api/v1/bowlers/462411b3/records?tournament=Indian%20Premier%20League&limit=3"
```

```json
{
  "person_id": "462411b3",
  "name": "JJ Bumrah",
  "best_figures": [
    { "wickets": 5, "runs": 10, "balls": 24,
      "overs": "4.0", "economy": 2.5, "figures": "5/10",
      "match_id": 5782, "team": "Mumbai Indians",
      "opponent": "Kolkata Knight Riders", "tournament": "Indian Premier League",
      "season": "2022", "date": "2022-05-09" }
  ],
  "most_economical": [ "…" ]
}
```

## Other endpoints (same shape pattern)

- `GET /api/v1/bowlers/{person_id}/by-innings`: the list of innings, with the bowling figures.
  Params: `limit`, `offset`.
- `GET /api/v1/bowlers/{person_id}/vs-batters`: the matchup table. Params: `batter_id`, `min_balls`.
- `GET /api/v1/bowlers/{person_id}/by-over`: economy and strike rate per over (1 to 20).
- `GET /api/v1/bowlers/{person_id}/by-phase`: the split by powerplay, middle and death.
- `GET /api/v1/bowlers/{person_id}/by-season`: the career season by season.
- `GET /api/v1/bowlers/{person_id}/wickets`: the wicket analysis, with the by_kind donut, the
  by_phase bars, by_batter (the batters dismissed most) and the distribution of the dismissal overs.

---

# Fielders (`/api/v1/fielders/{person_id}/…`), Tier 1

Source: `api/routers/fielding.py`. The `fieldingcredit` table backs these endpoints.

## `GET /api/v1/fielders/{person_id}/summary`

The response has the same Phase 4 envelope shape. The cohort splits in two on `is_keeper`,
which comes from `innings_kept > 0`. The counts have `direction: null`.
The rates per match (`catches_per_match`, `stumpings_per_match`,
`run_outs_per_match`, `dismissals_per_match`) are `higher_better`,
with `delta_pct` against the cohort of keepers or of outfielders. The response also includes
`dismissal_position_distribution[10]`, which aggregates by the position of the dismissed
batter, and `cohort: {match_dimension: "is_keeper",
is_keeper, n_fielders, n_matches_total}`.

**`matches_fielded` (denominator B).** All rates per match divide by
`matches_fielded`, not by the squad count `matches`. It counts the matches where
the fielder was in the XI and the opponent batted, that is, the matches where the fielder took the field. It is
the denominator in units of activity, as `innings_batted` is for batting and
`innings_bowled` is for bowling. `matches` stays the squad count for display. The
two differ only on rare matches with no innings by the opponent (e.g. Kohli in the IPL fielded
in 279 of 280).

The cohort `n_matches_total` divides by the same
`SUM(matches_fielded)`. The `cohort` block, the rates per match and the
`dismissal_position_distribution` cohort all narrow live under the six
filters (venue/opponent/team/inning/toss/result). See the narrowing note for
`/scope/averages/players/*` above.

```bash
curl "http://localhost:8000/api/v1/fielders/4a8a2e3b/summary?tournament=Indian+Premier+League"
```

```jsonc
{
  "person_id": "4a8a2e3b", "name": "MS Dhoni",
  "matches":               {"value": 277, "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "matches_fielded":       {"value": 277, "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "catches":               {"value": 158, "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "catches_per_match":     {"value": 0.570,"scope_avg": 0.584,"delta_pct": -2.4, "direction": "higher_better","sample_size": 2565},
  "stumpings":             {"value": 47,  "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "run_outs":              {"value": 53,  "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "total_dismissals":      {"value": 258, "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "dismissals_per_match":  {"value": 0.931,"scope_avg": 0.899,"delta_pct": 3.6,  "direction": "higher_better","sample_size": 2565},
  "innings_kept":          {"value": 245, "scope_avg": null,  "delta_pct": null, "direction": null,           "sample_size": 2565},
  "dismissal_position_distribution": [/* 10 entries */],
  "cohort": {"match_dimension":"is_keeper","is_keeper":1,"n_fielders":232,"n_matches_total":2565},
  "is_keeper": 1
}
```

The top-level field `is_keeper` tells the frontend to show the
Keeping tab. Here the cohort baseline for dismissals per match compares keepers with
keepers, because Dhoni falls in the keeper cohort.

## `GET /api/v1/fielders/{person_id}/distribution`

The endpoint returns a dossier of the fielding distributions per match. It has three sibling
count blocks (catches, run_outs and stumpings), and each block has three simple milestones
(`P=0` / `P=1` / `P≥2`) with Wilson 95% confidence intervals (CIs). It also has four form
windows. The master sample has one row per match, not per innings. A fielder's events in a match
fall in the innings in which the opponent bats, and in a super over if there is one, so the natural
unit is the match.

The stumpings block is `null` for non-keepers (`innings_kept == 0`),
and the frontend uses the null to hide the Stumpings tab. `catches.total` excludes substitute
catches. The response gives them separately as
`substitute_catches`, to reconcile against `/summary.catches`.
A caught-and-bowled dismissal is credited to the bowler, so it is in the bowling
distribution dossier.

```bash
curl "http://localhost:8000/api/v1/fielders/4a8a2e3b/distribution?tournament=Indian%20Premier%20League&as_of_date=2025-01-01"
```

```jsonc
{
  "scope": { "tournament": "Indian Premier League" },
  "lifetime": {
    "n_matches": 277,
    "innings_kept": 245,
    "substitute_catches": 0,
    "observations": [
      { "match_id": 6027, "date": "2008-04-19",
        "catches": 0, "run_outs": 0, "stumpings": 0, "is_keeper": 0 }
      // … 277 entries total, date-asc
    ],
    "catches": {
      "total": 158, "mean_per_match": 0.57, "median": 0,
      "variance": 0.64, "std": 0.80,
      "milestones": {
        "p_zero":  { "value": 0.58, "num": 161, "denom": 277, "ci_low": 0.52, "ci_high": 0.64 },
        "p_one":   { "value": 0.31, "num":  85, "denom": 277, "ci_low": 0.26, "ci_high": 0.36 },
        "p_geq_2": { "value": 0.11, "num":  31, "denom": 277, "ci_low": 0.08, "ci_high": 0.15 }
      }
    },
    "run_outs":  { /* same shape as catches */ },
    "stumpings": { /* same shape; null when innings_kept == 0 */ }
  },
  "form": {
    "last_10":  { /* full lifetime-shape dossier */ },
    "last_60d": { /* … */ },
    "last_6mo": { /* … */ },
    "last_1yr": { /* … */ },
    "delta": {
      "last_10_catches_mean_minus_lifetime":   -0.06,
      "last_10_run_outs_mean_minus_lifetime":  -0.10,
      "last_10_stumpings_mean_minus_lifetime": -0.02,
      "last_60d_catches_mean_minus_lifetime":  null,
      // … 12 entries total: 4 windows × 3 metrics. Stumpings deltas
      // null for non-keepers.
    }
  },
  "suggested_splits": [
    { "label": "All-time", "params": {} }
  ]
}
```

`as_of_date`, an optional ISO date, anchors the calendar form windows
so that the regression tests are deterministic. Production callers omit it.

**Invariant of the three simples.** In each block, `p_zero + p_one + p_geq_2 == 1.0`.
To match, the Distribution panel of the frontend draws three discrete bars
in the INDIGO/SAGE/OCHRE palette.

Spec: `docs/internal/spec-distribution-stats.md` §13.

## `GET /api/v1/fielders/{person_id}/records`

The endpoint returns the fielding records of one player, in three top-N lists. `limit` caps each
list (default 10, max 20):

- `most_catches_match`: catches DESC, with dismissals DESC as the tiebreak.
- `most_stumpings_match`: stumpings DESC. The list fills only when the
  player has appeared as the designated keeper, so it is typically empty for
  outfielders.
- `most_dismissals_match`: catches + stumpings + run_outs, DESC.

The endpoint reads from `matchfielderperf`, an aggregate per fielder and match that
`_populate_match_fielder_perf` in `scripts/populate_records_aggregates.py` precomputes.

**Catches use the volume framing.** A catch is any dismissal with `kind IN ('caught',
'caught_and_bowled')`, and there is no `is_substitute` filter. The rule matches
the semantics of `/leaders` and `/summary` (Convention 3), not
the semantics of `/distribution`, which excludes substitute appearances.
So the record list counts a catch taken by a
substitute.

The precomputed table, `matchfielderperf`, has one row for each fielder and match, and no column for
the innings. So the endpoint applies `aux.inning` as a filter on matches
(`player_inning_match_clause`, side `fielding`). With `inning=N`, it keeps the matches in which the
fielder's team fielded in innings 1−N. A fielder fields in one regular innings of a match, the innings
in which the opponent bats. The table also counts the credits from a super over, so those credits
stay in under the filter.

```bash
curl "http://localhost:8000/api/v1/fielders/4a8a2e3b/records?limit=3"
```

```json
{
  "person_id": "4a8a2e3b",
  "name": "MS Dhoni",
  "most_catches_match": [
    { "catches": 4, "stumpings": 0, "run_outs": 0, "dismissals": 4,
      "match_id": 5616, "team": "Chennai Super Kings",
      "opponent": "Kolkata Knight Riders",
      "tournament": "Indian Premier League",
      "season": "2020/21", "date": "2020-10-07" }
  ],
  "most_stumpings_match":  [ "…" ],
  "most_dismissals_match": [ "…" ]
}
```

## Other endpoints

- `GET /api/v1/fielders/{person_id}/by-season`: the dismissals per season, split by kind.
- `GET /api/v1/fielders/{person_id}/by-phase`: the dismissals by powerplay, middle and death.
- `GET /api/v1/fielders/{person_id}/by-over`: the count of dismissals per over.
- `GET /api/v1/fielders/{person_id}/dismissal-types`: the donut data (the percentages of catches,
  stumpings, run-outs and c&b).
- `GET /api/v1/fielders/{person_id}/victims`: the batters this fielder dismissed, ranked.
- `GET /api/v1/fielders/{person_id}/by-innings`: the list of innings, with the fielding
  credits of each innings. Params: `limit`, `offset`.

---

# Keeping (`/api/v1/fielders/{person_id}/keeping/…`), Tier 2

Source: `api/routers/keeping.py`. The keeping endpoints matter only when
`summary.innings_kept > 0`, which means that the Tier-2 keeper inference has assigned
innings to this person. See `docs/internal/spec-fielding-tier2.md` for the
algorithm, which has 4 layers.

## `GET /api/v1/fielders/{person_id}/keeping/summary`

The response has the same Phase 4 envelope shape. `innings_kept_by_confidence` stays
flat, because it is a dict of counts per category. Every other numeric field is wrapped in the
envelope. `byes_per_innings` has the `lower_better`
direction. `cohort: {match_dimension: "is_keeper", is_keeper: 1,
n_keepers, n_matches_keeping}` gives the metadata of the keeper cohort.

The cohort denominator is per match, not per innings, so it does not match the rates of this
endpoint. For that reason the endpoint does not use the headline rates of the cohort directly
as `scope_avg`. The use of the cohort for `scope_avg` waits for a future enhancement, when the precompute of byes lands.

```bash
curl "http://localhost:8000/api/v1/fielders/4a8a2e3b/keeping/summary?tournament=Indian+Premier+League"
```

```jsonc
{
  "person_id": "4a8a2e3b", "name": "MS Dhoni",
  "innings_kept_by_confidence": {"definitive":39,"high":177,"medium":29,"low":0},
  "innings_kept":                   {"value":245,"direction":null, …},
  "stumpings":                      {"value": 47,"direction":null, …},
  "keeping_catches":                {"value":142,"direction":null, …},
  "byes_per_innings":               {"value":0.41,"direction":"lower_better","scope_avg":null, …},
  "keeping_dismissals_per_innings": {"value":0.96,"direction":"higher_better","scope_avg":null, …},
  "cohort": {"match_dimension":"is_keeper","is_keeper":1,"n_keepers":232,"n_matches_keeping":2166}
}
```

- `GET /api/v1/fielders/{person_id}/keeping/by-season`: the keeping stats per season.
- `GET /api/v1/fielders/{person_id}/keeping/by-innings`: the list of innings for the Keeping tab.
  Params: `limit`, `offset`.
- `GET /api/v1/fielders/{person_id}/keeping/ambiguous`: the innings where this person was a
  candidate but the algorithm could not resolve a single keeper,
  with the other candidates. The UI shows them for transparency.

---

# Head-to-head (`/api/v1/head-to-head/{batter_id}/{bowler_id}`)

Source: `api/routers/head_to_head.py`. One endpoint returns
everything that the HeadToHead Player-vs-Player page needs. The filter scope
applies. If the pair never met under those filters, the arrays come back
empty, but the structure stays the same.

**`series_type`** is an optional query parameter that narrows by series
category, with the same semantics as in the tournament-dossier endpoints. Its four
categories are mutually exclusive and partition the data:

- `all` (default): every meeting
- `bilateral`: international bilateral T20Is only (e.g. "India tour
  of Australia"). It excludes ICC events and club tournaments.
- `icc`: ICC events only (for example the T20 World Cup, the Asia Cup and qualifiers)
- `club`: club tournaments only (for example the IPL, BBL, PSL and Vitality Blast)

When both players are international teammates (Kohli and
Bumrah for India), `bilateral` and `icc` both return 0, because the two never
face each other internationally. `club` returns their full IPL record
(108 balls and 159 runs, lifetime). `series_type` composes with the filters of the FilterBar,
the bar of filters in the frontend. So `team_type=international&series_type=club` is
contradictory and yields 0.

For compatibility with old URLs, the legacy names `bilateral_only` and `tournament_only` map to
`bilateral` and `icc`. The old `bilateral_only`
included club matches, but the new `bilateral` is international only.

```bash
curl "http://localhost:8000/api/v1/head-to-head/ba607b88/3fb19989?team_type=international&gender=male"
curl "http://localhost:8000/api/v1/head-to-head/ba607b88/462411b3?series_type=tournament_only"
```

```json
{
  "batter": { "id": "ba607b88", "name": "V Kohli" },
  "bowler": { "id": "3fb19989", "name": "MA Starc" },
  "summary": {
    "balls": 18, "runs": 15, "dismissals": 0,
    "average": null, "strike_rate": 83.33,
    "fours": 2, "sixes": 0, "dots": 9,
    "dot_pct": 50.0, "balls_per_boundary": 9.0
  },
  "dismissal_kinds": {},
  "by_over": [ /* up to 20 rows */ ],
  "by_phase": [ /* 3 rows */ ],
  "by_season": [ { "season": "2012/13", "balls": 4, "runs": 6, "wickets": 0, "strike_rate": 150.0 } ],
  "by_match": [ /* match-level rows */ ]
}
```

---

# Matches (`/api/v1/matches…`)

Source: `api/routers/matches.py`.

## `GET /api/v1/matches`

The endpoint returns a paginated list of matches. It accepts the common filters, and also `player_id`,
`team`, `opponent`, `venue`, `city`, `q`, `limit`, `offset` and
`sort` (date, runs and other keys).

```bash
curl "http://localhost:8000/api/v1/matches?gender=male&team_type=international&limit=1"
```

```json
{
  "matches": [
    {
      "match_id": 13017, "date": "2026-04-13",
      "team1": "Sweden", "team2": "Indonesia",
      "venue": "Udayana Cricket Ground", "city": "Bali",
      "tournament": "Sweden tour of Indonesia", "season": "2026",
      "winner": "Sweden", "result_text": "Sweden won by 18 runs",
      "team1_score": "166/8 (20.0)", "team2_score": "148/10 (18.2)"
    }
  ],
  "total": 3498
}
```

## `GET /api/v1/matches/{match_id}/scorecard`

The endpoint returns the full scorecard. Each of the two innings has the batting, the bowling,
the extras, the fall of wickets, the progression of runs and wickets by over, and the keeper label.

```json
{
  "info": { "match_id": 13017, "date": "2026-04-13", "teams": ["Sweden", "Indonesia"], "venue": "…", "toss": "…", "result": "…", "officials": {…}, "player_of_match": "…" },
  "innings": [
    {
      "innings_number": 0, "team": "Sweden", "is_super_over": false, "label": "Sweden innings",
      "total_runs": 166, "wickets": 8, "overs": "20.0", "run_rate": 8.3,
      "batting": [ /* BattingRow per batter with dismissal_fielder_ids */ ],
      "did_not_bat": [ /* person names */ ],
      "extras": { "wides": 6, "noballs": 1, "byes": 0, "legbyes": 4, "penalty": 0, "total": 11 },
      "fall_of_wickets": [ { "over": "3.4", "wicket": 1, "score": 28, "batter": "…" } ],
      "bowling": [ /* BowlingRow per bowler */ ],
      "by_over": [ { "over": 1, "runs": 6, "wickets": 0, "cumulative_runs": 6 } ],
      "keeper": { "person_id": "…", "name": "…", "confidence": "high" }
    }
  ]
}
```

**Fielder attribution.** Each `batting[]` row carries
`dismissal_fielder_ids: string[]` from `fieldingcredit`. The scorecard uses the list to
highlight a fielder through `?highlight_fielder=<person_id>`.

## `GET /api/v1/matches/{match_id}/innings-grid`

The endpoint returns a grid of the deliveries for the InningsGridChart, with every ball as a cell.

```json
{
  "match_id": 13017,
  "innings": [
    {
      "innings_number": 0, "team": "Sweden",
      "batters": ["…"], "batter_ids": ["…"],
      "bowlers": ["…"], "bowler_ids": ["…"],
      "total_balls": 120, "total_runs": 166, "total_wickets": 8,
      "deliveries": [
        {
          "over_ball": "1.1", "bowler": "F Banunaek", "batter": "Imal Zuwak",
          "batter_id": "…", "bowler_id": "…",
          "batter_index": 0, "bowler_index": 0, "non_striker_index": 1,
          "runs_batter": 4, "runs_extras": 1, "runs_total": 5,
          "extras_wides": 0, "extras_noballs": 1,
          "cumulative_runs": 5, "cumulative_wickets": 0,
          "wicket_kind": null, "wicket_player_out": null, "wicket_text": null
        }
      ]
    }
  ]
}
```

---

# Series catalog / match-set dossier (`/api/v1/series/*`)

Source: `api/routers/tournaments.py`. The file name is historical.
The router was renamed from `/tournaments/*` to `/series/*` so that
its name does not clash with the "Tournament" dropdown of the FilterBar.
These endpoints power the `/series` landing page and the dossier UI.
They also power the `/head-to-head?mode=team` Team-vs-Team view.

These endpoints share one concept, the "match-set", which is the set
of matches that the filters select. Every endpoint takes an
optional `tournament` (the canonical name, expanded to its IN-variants)
and an optional `series_type` (`all`, `bilateral`, `icc` or `club`). The legacy
names `bilateral_only` and `tournament_only` map to `bilateral` and `icc`.
It also takes the standard FilterParams, including `filter_team` and
`filter_opponent` for the scope of a rivalry. The same endpoints serve
these match-sets:

- IPL all-time (`?tournament=Indian+Premier+League`)
- IND vs AUS bilateral (`?filter_team=India&filter_opponent=Australia&series_type=bilateral`)
- IND vs AUS within T20 World Cups (`?tournament=T20+World+Cup+%28Men%29&filter_team=India&filter_opponent=Australia`)
- League baseline for any team (call it without a team filter, and the response has the same shape)

When `filter_team` and `filter_opponent` are both set, the summary
returns a `by_team` companion object. It gives a breakdown for each
team of the top scorer, the top wicket-taker, the highest individual
score and the largest partnership. The summary also returns a top-level
`head_to_head` object with team1_wins, team2_wins, ties and no_result.
With these counts, the dossier can show "who won how much" as its top row
of stats.

## `GET /api/v1/series/landing`

The endpoint returns a directory in sections for the `/series` landing
page. The tiles for bilateral rivalries count bilateral matches only,
and they are split by gender (the top-9 full-member pairs for men and
for women). The `latest_match` of each rivalry entry is the most recent
meeting across all international meetings, not bilateral meetings only.
Its `tournament` is the canonical ICC event name when the meeting was
in a recognized tournament (for example the T20 WC or the Asia Cup).
It is `null` for a bilateral tour. The pair counts (`matches`,
`team1_wins` and the others) still count bilateral matches only.

```bash
curl "http://localhost:8000/api/v1/series/landing?gender=male"
```

```json
{
  "international": {
    "icc_events": [
      { "canonical": "T20 World Cup (Men)", "editions": 10, "matches": 334,
        "most_titles": { "team": "India", "titles": 3 },
        "latest_edition": { "season": "2025/26", "champion": "India" },
        "team_type": "international", "gender": "male" }
    ],
    "bilateral_rivalries": {
      "men": {
        "top": [
          { "team1": "New Zealand", "team2": "Pakistan",
            "matches": 42, "team1_wins": 21, "team2_wins": 19,
            "ties": 0, "no_result": 2,
            "latest_match": { "match_id": 1835, "date": "2025-03-26",
                              "winner": "New Zealand",
                              "tournament": null, "season": "2024/25" } }
        ],
        "other_count": 153
      },
      "women": { "top": [], "other_count": 0 },
      "other_threshold": 5
    },
    "other_international": [ "…long tail of qualifiers, regional events…" ]
  },
  "club": {
    "franchise_leagues": [ { "canonical": "Indian Premier League", "editions": 19, "matches": 1190 } ],
    "domestic_leagues": [ "…" ],
    "women_franchise": [ "…" ],
    "other": [ "…" ],
    "rivalries": {
      "men": [
        { "team1": "Chennai Super Kings", "team2": "Mumbai Indians",
          "tournament": "Indian Premier League",
          "matches": 39, "team1_wins": 18, "team2_wins": 21,
          "ties": 0, "no_result": 0 }
      ],
      "women": [ "…top-12 most-played pairs in women's club tournaments…" ]
    }
  }
}
```

The `club.rivalries` lists give, for each gender, the top-12
most-played team pairs within club tournaments. They drive the club
suggestion tiles on the H2H Team-vs-Team page. Each entry carries the
dominant tournament for context. A franchise pair plays in only one
tournament. For example, RCB vs CSK is always IPL, never WBBL.

## `GET /api/v1/series/summary`

The endpoint gives the headline numbers for any match-set scope.
Tournament, series_type and filter_team/opponent are all optional. It
returns `by_team` when a team pair is in scope.

Broad scope means no tournament, no rivalry, no inning or aux narrowing,
and no team_class narrowing that matches team_type. At broad scope, the
count and rate queries read from the precomputed tables
`bucketbaselinematch`, `bucketbaselinebatting` and `bucketbaselinebowling`,
so they return in under a second. The Best moments for each
(person, match) pair (`highest_individual`, `best_bowling`,
`best_fielding`) stay live, because no precompute table carries that
grain. They are gathered with everything else through `asyncio.gather`.

In tier mode at broad scope, the endpoint returns `top_teams_international` and
`top_teams_club`. Each list has the top 5 teams with at least 100 games,
ranked by win % in decided matches. The wins are the sum of bat_first_wins and field_first_wins from
`bucketbaselinematch`. Both lists are empty in tournament mode and in
rivalry mode, where the page shows `teams[]` chips instead. So the
rivalry example below has two empty lists.

Each row of `champions_by_season` carries its own `tournament` (the
cricsheet `event_name`). The Champions tables of cross-tournament tier
mode use it to show a Tournament column. In tournament mode, every
row's tournament equals the dossier's, so the field is redundant there.

> **Historical:** A `/api/v1/league/*` router once had 5 endpoints
> (`/league/overview`, `/league/champions` and
> `/league/leaders/{batting,bowling,fielding}`). They were added on
> 2026-05-13 and deleted on 2026-05-14, because they were parallel
> copies of `/series/*` with `tournament=null`. All of their functions
> now live on `/series/*`.

```bash
curl "http://localhost:8000/api/v1/series/summary?filter_team=India&filter_opponent=Australia&gender=male"
```

```json
{
  "canonical": null, "variants": [],
  "matches": 37, "editions": 13,
  "run_rate": 8.68, "boundary_pct": 17.69, "dot_pct": 34.8,
  "total_runs": "…", "total_wickets": "…",
  "total_fours": 934, "total_sixes": 449,
  "most_titles": null,
  "champions_by_season": [
    { "season": "2024", "tournament": "ICC Men's T20 World Cup",
      "champion": "India", "match_id": 1551,
      "team1": "India", "team2": "South Africa",
      "team1_score": "176/7", "team2_score": "169/8",
      "date": "2024-06-29" }
  ],
  "top_scorer_alltime":     { "person_id": "ba607b88", "name": "V Kohli",
                              "team": "India", "runs": 794 },
  "top_wicket_taker_alltime": { "person_id": "462411b3", "name": "JJ Bumrah",
                              "team": "India", "wickets": 20 },
  "top_teams_international": [],
  "top_teams_club": [],
  "highest_individual":     { "person_id": "55d96c71", "name": "SR Watson",
                              "team": "Australia", "runs": 120,
                              "match_id": 1092, "date": "2016-03-27" },
  "highest_team_total":     { "team": "India", "total": 235, "match_id": 1347,
                              "opponent": "Australia", "date": "2023-11-26" },
  "largest_partnership":    { "runs": 141, "match_id": 1348,
                              "team": "India", "opponent": "Australia",
                              "date": "2023-11-28",
                              "batter1": { "person_id": "45a43fe2", "name": "RD Gaikwad" },
                              "batter2": { "person_id": "8bfbd3a3", "name": "Tilak Varma" } },
  "best_bowling":           { "person_id": "ecd3e89b", "name": "R Ashwin",
                              "team": "India", "figures": "4/11",
                              "wickets": 4, "runs": 11,
                              "match_id": "…", "date": "…" },
  "best_fielding":          { "person_id": "…", "name": "MS Dhoni",
                              "team": "India",
                              "catches": 5, "stumpings": 0,
                              "run_outs": 0, "caught_bowled": 0,
                              "total": 5, "match_id": "…", "date": "…" },
  "teams":  [ { "name": "India", "matches": 37 }, { "name": "Australia", "matches": 37 } ],
  "groups": [],
  "knockouts": [
    { "match_id": 2794, "season": "2007/08", "stage": "Semi Final",
      "tournament": "ICC World Twenty20",
      "team1": "Australia", "team2": "India",
      "winner": "India", "margin": "15 runs",
      "venue": "Kingsmead", "date": "2007-09-22",
      "team1_score": "141/7", "team2_score": "142/6" }
  ],
  "by_team": {
    "India": {
      "top_scorer":      { "person_id": "ba607b88", "name": "V Kohli", "runs": 794 },
      "top_wicket_taker":{ "person_id": "462411b3", "name": "JJ Bumrah", "wickets": 20 },
      "highest_individual": { "person_id": "45a43fe2", "name": "RD Gaikwad", "runs": 119,
                              "match_id": 1348, "date": "2023-11-28" },
      "largest_partnership":{ "runs": 141, "batter1": { "name": "RD Gaikwad" },
                              "batter2": { "name": "Tilak Varma" } }
    },
    "Australia": { "top_scorer": { "name": "GJ Maxwell", "runs": 570 }, "…": "…" }
  },
  "head_to_head": {
    "team1": "India", "team2": "Australia",
    "team1_wins": 22, "team2_wins": 12,
    "ties": 0, "no_result": 3
  }
}
```

## `GET /api/v1/series/by-season`

The endpoint gives a rollup for each edition. Each row has the
champion, the runner-up, the top scorer, the top wicket-taker, the run
rate, the boundary % and the sixes. Tournament, series_type and filter_* are
optional. `champion_record` and `runner_up_record` carry `{played, won}`
for that team in that edition. The Editions tab of the dossier uses
them to show bracketed fractions such as "India (8/9)".

```bash
curl "http://localhost:8000/api/v1/series/by-season?tournament=Indian+Premier+League&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "seasons": [
    { "season": "2024", "matches": 71,
      "champion": "Kolkata Knight Riders",
      "champion_record": { "played": 17, "won": 12 },
      "runner_up": "Sunrisers Hyderabad",
      "runner_up_record": { "played": 16, "won": 9 },
      "final_match_id": 5945,
      "final_team1": "Sunrisers Hyderabad", "final_team2": "Kolkata Knight Riders",
      "final_team1_score": "113/10", "final_team2_score": "114/2",
      "run_rate": 9.56, "boundary_pct": 21.07, "total_sixes": 1261,
      "top_scorer":      { "person_id": "ba607b88", "name": "V Kohli", "runs": 741 },
      "top_wicket_taker":{ "person_id": "f986ca1a", "name": "HV Patel", "wickets": 24 } }
  ]
}
```

## `GET /api/v1/series/points-table`

The endpoint reconstructs the league-stage points table, with NRR. It
requires a single-season scope (`season_from=season_to`) and a
tournament. It returns one table per `event_group` for ICC events, and
one combined table for leagues shaped like the IPL.

```bash
curl "http://localhost:8000/api/v1/series/points-table?tournament=Indian+Premier+League&season_from=2024&season_to=2024&gender=male&team_type=club"
```

```json
{
  "canonical": "Indian Premier League", "season": "2024",
  "tables": [
    { "group": null,
      "rows": [
        { "team": "Kolkata Knight Riders",
          "played": 12, "wins": 9, "losses": 3, "ties": 0, "nr": 0,
          "points": 18, "nrr": 1.123,
          "runs_for": "…", "balls_for": "…", "runs_against": "…", "balls_against": "…" }
      ] }
  ]
}
```

When the requested scope covers several seasons, the response is
`{ "tables": [], "reason": "multi_season" }`, so that the frontend can
hide the tab.

## `GET /api/v1/series/records`

The endpoint gives the records sub-lists for the match-set, each capped
at `limit` (default 5). Tournament is optional.

```bash
curl "http://localhost:8000/api/v1/series/records?tournament=Indian+Premier+League&gender=male&team_type=club&limit=2"
```

```json
{
  "canonical": "Indian Premier League",
  "highest_team_totals":   [ { "team": "Sunrisers Hyderabad", "runs": 287, "opponent": "Royal Challengers Bengaluru",
                                "match_id": 5904, "date": "2024-04-15",
                                "tournament": "Indian Premier League", "season": "2024" } ],
  "lowest_all_out_totals": [ "…" ],
  "biggest_wins_by_runs":   [ { "winner": "Mumbai Indians", "loser": "Delhi Capitals", "margin": 146,
                                 "match_id": 5471, "date": "2017-05-06",
                                 "tournament": "Indian Premier League", "season": "2017" } ],
  "biggest_wins_by_wickets":[ "…" ],
  "largest_partnerships":   [ { "runs": 229, "batter1": { "name": "V Kohli" }, "batter2": { "name": "AB de Villiers" },
                                 "teams": "Royal Challengers Bengaluru v Gujarat Lions",
                                 "team1": "Royal Challengers Bengaluru", "team2": "Gujarat Lions",
                                 "batting_team": "Royal Challengers Bengaluru",
                                 "match_id": 6586, "date": "2016-05-14",
                                 "tournament": "Indian Premier League", "season": "2016" } ],
  "best_individual_batting": [ { "name": "CH Gayle", "runs": 175, "balls": 65,
                                 "fours": 13, "sixes": 17, "not_out": true,
                                 "figures": "175* (65)", "match_id": 6377, "date": "2013-04-23",
                                 "tournament": "Indian Premier League", "season": "2013" } ],
  "best_bowling_figures":   [ { "name": "AS Joseph", "wickets": 6, "runs": 14, "balls": 22,
                                 "figures": "6/14", "match_id": 5565, "date": "2019-04-06",
                                 "tournament": "Indian Premier League", "season": "2019" } ],
  "most_sixes_in_a_match":  [ { "match_id": "…", "sixes": 42,
                                 "teams": "Kolkata Knight Riders v Punjab Kings",
                                 "team1": "Kolkata Knight Riders", "team2": "Punjab Kings",
                                 "date": "2024-04-26",
                                 "tournament": "Indian Premier League", "season": "2024" } ]
}
```

Every row carries `tournament` and `season`. The Records tab of the
frontend uses them to show an Edition column and a `(ed)` team
subscript on each row. The subscript points at that row's own
tournament and season, rather than at the season window that the
FilterBar sets. Partnership rows and most-sixes rows also split `teams` into
explicit `team1` and `team2` fields, so that the links render cleanly.

## `GET /api/v1/series/{batters,bowlers,fielders}-leaders`

The endpoints give leader lists that cover every name variant of a
tournament. They wrap `/batters/leaders` and its siblings, and they
expand the canonical tournament name to its IN-variants. Tournament is optional. Without it,
the lists rank across the full filter scope, which is useful for the
"top batters in this rivalry".

Each row carries a `team` field, which is the player's dominant side in
the current scope. The dominant side is the team with the most balls
faced for a batter, the most balls bowled for a bowler, or the most
fielding credits for a fielder. In rivalry mode, the UI uses the field
to flip `filter_team` and `filter_opponent` for each row. The
"vs <opponent>" context link then goes to the player's actual opponent,
and not to the dossier's `filter_opponent` as written.

`fielders-leaders` returns three top-N lists of fielders:

- `by_dismissals`: catches, stumpings, run-outs and c&b.
- `by_keeper_dismissals`: keeper dismissals only, which are the catches
  and stumpings taken through `keeper_assignment`.
- `by_run_outs`: run-outs alone, sorted DESC, with ties broken on the
  total. It leaves out fielders with zero run-outs, so that the list is
  not padded.

```bash
curl "http://localhost:8000/api/v1/series/batters-leaders?tournament=T20+World+Cup+%28Men%29&gender=male&limit=3"
curl "http://localhost:8000/api/v1/series/fielders-leaders?tournament=Indian+Premier+League&gender=male&team_type=club&limit=3"
```

```json
{
  "by_average":     [ { "person_id": "…", "name": "ML Hayden", "team": "Australia", "runs": 259, "balls": 132, "dismissals": 3, "average": 86.33, "strike_rate": 196.21 } ],
  "by_strike_rate": [ { "person_id": "…", "name": "SV Samson", "team": "India", "strike_rate": 199.38, "runs": 321, "balls": 161 } ],
  "thresholds": { "min_balls": 100, "min_dismissals": 3 }
}
```

An abbreviated `fielders-leaders` response follows. In the IPL, MS Dhoni
leads both on dismissals and on run-outs, so the first row of
`by_dismissals` and of `by_run_outs` is the same.

```json
{
  "by_dismissals":         [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 258, "catches": 158, "stumpings": 47, "run_outs": 53, "c_and_b": 0 } ],
  "by_keeper_dismissals":  [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 189, "catches": 142, "stumpings": 47 } ],
  "by_run_outs":           [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 258, "catches": 158, "stumpings": 47, "run_outs": 53, "c_and_b": 0 } ]
}
```

## `GET /api/v1/series/fielder-scope-stats`

The endpoint gives aggregate fielding stats for one picked player in
the current scope. It is a sibling of `batter-scope-stats` and
`bowler-scope-stats`, and it backs the "Picked fielder" tile of
Series > Fielders. Every member of the XI fields, so this endpoint
differs from its batter and bowler siblings in one way.

If the player took 0 credits in scope but was in the XI for at least
1 scope match (the matchplayer check), the endpoint returns a
zero-filled entry rather than `{"entry": null}`. The picker
can then show, for example, "Jadeja · 0 · 0 · 0 · 0 · 0" for an
all-rounder who fielded in every match but took no catches or run-outs.
A player who is out of scope, with no matchplayer entry, still gets
null.

```bash
curl "http://localhost:8000/api/v1/series/fielder-scope-stats?person_id=ba607b88&tournament=T20+World+Cup+%28Men%29&gender=male&team_type=international&season_from=2022%2F23&season_to=2025%2F26"
```

```json
{
  "entry": {
    "person_id": "ba607b88", "name": "V Kohli",
    "total": 4, "catches": 4, "stumpings": 0,
    "run_outs": 0, "c_and_b": 0,
    "team": "India"
  }
}
```

## `GET /api/v1/series/bowler-scope-stats`

The endpoint gives aggregate bowling stats for one picked player in the
current scope. It is a sibling of `batter-scope-stats`, and it backs the
"Picked bowler" tile of Series > Bowlers. It returns `{"entry": null}`
when the player has no deliveries as bowler in scope. It takes the same
parameters as the batter variant.

```bash
curl "http://localhost:8000/api/v1/series/bowler-scope-stats?person_id=462411b3&tournament=T20+World+Cup+%28Men%29&gender=male&team_type=international&season_from=2022%2F23&season_to=2025%2F26"
```

```json
{
  "entry": {
    "person_id": "462411b3", "name": "JJ Bumrah",
    "runs": 302, "balls": 322, "wickets": 26,
    "economy": 5.63, "strike_rate": 12.38,
    "team": "India"
  }
}
```

## `GET /api/v1/series/batter-scope-stats`

The endpoint gives aggregate batting stats for one specific player in
the current match-set scope. It backs the "Picked batter" tile of
Series > Batters, where the user picks a player from the scope-aware
typeahead. It returns the same row shape as `/series/batters-leaders`,
so that the card reuses the cell renderers of the leaderboard. It
returns `{"entry": null}` when the picked player has no deliveries in
scope, for example when the user changed a filter after the pick.

Params: `person_id` (required), `tournament`, `series_type` and the full
FilterBar.

```bash
curl "http://localhost:8000/api/v1/series/batter-scope-stats?person_id=ba607b88&tournament=T20+World+Cup+%28Men%29&gender=male&team_type=international&season_from=2022%2F23&season_to=2025%2F26"
```

```json
{
  "entry": {
    "person_id": "ba607b88", "name": "V Kohli",
    "runs": 416, "balls": 324, "dismissals": 10,
    "average": 41.6, "strike_rate": 128.4,
    "team": "India"
  }
}
```

## `GET /api/v1/series/partnerships/by-wicket`

The endpoint gives a partnership rollup for each wicket. Each row
includes the single best stand (the batters, the match, the season and
the date), so that a scope of several editions stays unambiguous.
Tournament and filter_team are optional. With `filter_team`, the
endpoint narrows to that team's partnerships (side=batting) or to the
partnerships against them (side=bowling).

```bash
curl "http://localhost:8000/api/v1/series/partnerships/by-wicket?tournament=Indian+Premier+League&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "side": "batting", "filter_team": null,
  "by_wicket": [
    { "wicket_number": 1, "n": 1245, "avg_runs": 41.2, "avg_balls": 26.8,
      "best_runs": 210,
      "best_partnership": {
        "runs": 210, "balls": "…",
        "batter1": { "person_id": "…", "name": "Q de Kock" },
        "batter2": { "person_id": "…", "name": "KL Rahul" },
        "match_id": 5792, "season": "2022", "date": "2022-05-18",
        "batting_team": "Lucknow Super Giants", "opponent": "Kolkata Knight Riders"
      } }
  ]
}
```

## `GET /api/v1/series/partnerships/top`

The endpoint gives the top-N partnerships in the match-set scope. It
takes the same filters as `by-wicket`, and adds `limit` (default 10).

```bash
curl "http://localhost:8000/api/v1/series/partnerships/top?tournament=Indian+Premier+League&limit=2&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "side": "batting", "filter_team": null,
  "partnerships": [
    { "partnership_id": 91349, "runs": 229, "balls": 96,
      "wicket_number": 2, "unbroken": false, "ended_by_kind": "caught",
      "match_id": 6586, "season": "2016", "tournament": "Indian Premier League",
      "date": "2016-05-14",
      "batting_team": "Royal Challengers Bengaluru", "opponent": "Gujarat Lions",
      "batter1": { "name": "V Kohli", "runs": 97, "balls": 45 },
      "batter2": { "name": "AB de Villiers", "runs": 129, "balls": 51 } }
  ]
}
```

## `GET /api/v1/series/partnerships/top-by-wicket`

The endpoint gives the top-N partnerships for each wicket number
(1 to 10). It takes the same filters as `top`, but replaces `limit`
with `per_wicket` (default 10, max 20). It returns ten grouped
sub-lists.

```bash
curl "http://localhost:8000/api/v1/series/partnerships/top-by-wicket?tournament=Indian+Premier+League&per_wicket=2&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "side": "batting", "filter_team": null, "per_wicket": 2,
  "by_wicket": [
    { "wicket_number": 1, "partnerships": [
      { "runs": 210, "batter1": { "name": "B Sai Sudharsan" },
        "batter2": { "name": "Shubman Gill" },
        "batting_team": "Gujarat Titans", "opponent": "Chennai Super Kings",
        "season": "2024", "date": "2024-05-10", "match_id": 5933,
        "tournament": "Indian Premier League" },
      "…"
    ] },
    { "wicket_number": 2, "partnerships": [
      { "runs": 229, "batter1": { "name": "V Kohli" },
        "batter2": { "name": "AB de Villiers" },
        "batting_team": "Royal Challengers Bengaluru", "opponent": "Gujarat Lions",
        "season": "2016", "date": "2016-05-14", "match_id": 6586,
        "tournament": "Indian Premier League" },
      "…"
    ] }
  ]
}
```

## `GET /api/v1/series/partnerships/heatmap`

The endpoint gives a matrix of average runs, by season and by wicket
number.

```bash
curl "http://localhost:8000/api/v1/series/partnerships/heatmap?tournament=Indian+Premier+League&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "side": "batting", "filter_team": null,
  "seasons": ["2008", "2009", "…", "2025"],
  "wickets": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "cells": [
    { "season": "2024", "wicket_number": 1, "avg_runs": 35.4, "n": 141 }
  ]
}
```

## `GET /api/v1/series/other-rivalries`

The "Show other rivalries" expander on the landing page loads this
endpoint lazily. It lists the pairs that involve at least one team
outside the top 9 and that have at least 5 bilateral matches in scope.
Pass `gender` to set the scope.

```bash
curl "http://localhost:8000/api/v1/series/other-rivalries?gender=male"
```

```json
{
  "rivalries": [
    { "team1": "Bangladesh", "team2": "Zimbabwe", "matches": 24,
      "team1_wins": 11, "team2_wins": 13, "ties": 0, "no_result": 0 }
  ],
  "threshold": 5
}
```

## `GET /api/v1/rivalries/summary`

The endpoint gives a synthesized dossier for a bilateral rivalry. It is
legacy and kept for compatibility. New code uses the match-set dossier
endpoints above.

```bash
curl "http://localhost:8000/api/v1/rivalries/summary?team1=India&team2=Australia&gender=male"
```

```json
{
  "team1": "India", "team2": "Australia",
  "matches": 37, "team1_wins": 22, "team2_wins": 12, "ties": 0, "no_result": 3,
  "by_series_type": { "icc_event": 6, "bilateral_tour": 26, "other": 5 },
  "top_scorer_in_rivalry":      { "name": "V Kohli", "runs": 794 },
  "top_wicket_taker_in_rivalry":{ "name": "JJ Bumrah", "wickets": 20 },
  "highest_individual": { "name": "SR Watson", "runs": 120 },
  "largest_partnership":{ "runs": 141, "match_id": 1348 },
  "closest_match":      { "margin": "4 runs", "winner": "Australia" },
  "biggest_win":        { "winner": "India", "margin": "73 runs" },
  "last_match":         { "match_id": "…", "date": "2025-11-08" }
}
```

---

# Players tab, no new endpoints

The `/players` tab gives a single-player overview and an N-way
comparison of careers. The client builds it from existing summary
endpoints, so it needed no new backend work. For each player, the
frontend runs four requests in parallel:

```
GET /api/v1/batters/{person_id}/summary
GET /api/v1/bowlers/{person_id}/summary
GET /api/v1/fielders/{person_id}/summary
GET /api/v1/fielders/{person_id}/keeping/summary
```

The frontend then composes the four responses into a `PlayerProfile`
(see `frontend/src/api.ts::getPlayerProfile`). A 404 on any single
endpoint resolves to `null` and does not abort the rest. For example,
a specialist batter has no bowling row. The Players page hides each
discipline band whose summary came back empty.

For an N-way comparison, each of the two or three players fires its own
bundle of four fetches in parallel. All fetches share the same FilterBar
scope (gender, team_type, tournament, season, filter_team and
filter_opponent), so a narrower URL narrows every card at once.

---

# Things NOT yet in the API

- **Tournament-baseline overlays** (enhancement O) on the team, batter,
  bowler and fielder pages. The endpoints are ready for baselines, but
  the frontend wiring (overlay charts and "vs league avg" columns) has
  not shipped.
- Team-to-team head-to-head beyond the current
  `/teams/{team}/vs/{opponent}` rollup (enhancement B in
  next-session-ideas).
- Caching across workers and across restarts. It is not needed yet.
  See the "three options" capture in `docs/internal/next-session-ideas.md`.
