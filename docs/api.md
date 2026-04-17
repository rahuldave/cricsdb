# CricsDB API Reference

> **Also useful:**
> [Interactive Swagger UI](https://t20.rahuldave.com/api/docs) (prod) or
> [`http://localhost:5173/api/docs`](http://localhost:5173/api/docs) (local via Vite proxy) /
> [`http://localhost:8000/api/docs`](http://localhost:8000/api/docs) (local direct)
> — FastAPI auto-generates this from the route decorators. Every
> endpoint is clickable with a "Try it out" button. If you want to
> poke at something live, start there; come back here for narrative
> + the specific example responses that justify the section text.
>
> The docs live under `/api/docs` (not the FastAPI default `/docs`)
> so the Vite dev-server proxy forwards the request to the backend.
> In prod both frontend and backend share an origin, so either path
> would work, but keeping it on `/api/*` matches the rest of the
> routes and avoids a special case.

Practical one-page reference for every endpoint. Pair this with
[`../SPEC.md`](../SPEC.md) when you need the underlying SQL or the
full schema — this doc just gives you the URL, a one-liner, and a
representative response. Examples taken from local dev
(`http://localhost:8000`); swap to `https://t20.rahuldave.com` for
prod. Responses have been truncated to show shape, not full payloads.

## Conventions

- All endpoints return JSON.
- All endpoints are `GET`. No auth required (the deebase admin UI at
  `/admin/*` is the only protected surface, via HTTP Basic Auth).
- Responses are best-effort on failure: a 500 returns
  `{"detail": "..."}` rather than partial JSON.

## Common filter query params

Applied across almost every endpoint below (enforced via
`api/filters.py::FilterParams`). When omitted → no constraint on
that axis.

| Param | Type | What it filters | Example |
|---|---|---|---|
| `gender` | `male`/`female` | `match.gender` | `gender=male` |
| `team_type` | `international`/`club` | `match.team_type` | `team_type=international` |
| `tournament` | string | `match.event_name` (exact OR canonical → IN variants) | `tournament=Indian%20Premier%20League` or `tournament=T20%20World%20Cup%20%28Men%29` |
| `season_from` | string | `match.season >= ...` | `season_from=2024` |
| `season_to` | string | `match.season <= ...` | `season_to=2024/25` |

The `tournament` filter is canonicalization-aware everywhere. Pass
`T20 World Cup (Men)` and FilterParams expands it to
`event_name IN ('ICC World Twenty20', 'World T20', "ICC Men's T20 World Cup")`.
The mapping lives in `api/tournament_canonical.py`. Single-variant
tournaments (IPL, BBL, …) pass through unchanged.

Some endpoints also accept contextual filters:
- `filter_team=<name>` — narrows to matches involving this team
  (player-page contextual; tournament dossier rivalry scope).
- `filter_opponent=<name>` — narrows to matches against this opponent.
  When both `filter_team` + `filter_opponent` are set on a tournament-
  dossier endpoint, the scope becomes a team-pair rivalry and summary
  responses gain a `by_team` companion object.

A handful of endpoints add endpoint-specific params (`limit`,
`offset`, `min_balls`, `min_dismissals`, `min_wickets`, `q`, `role`,
`top_n`, `bowler_id` / `batter_id` in matchup endpoints, etc.) —
called out per endpoint below.

## Seasons convention

- Season labels are the cricsheet strings — a mix of calendar
  (`"2024"`) and split-year (`"2024/25"`). Lex sort matches
  chronology.
- `season_from <= m.season <= season_to` is inclusive on both sides.

---

# Reference data (`/api/v1/*`)

Source: `api/routers/reference.py`.

## `GET /api/v1/tournaments`

List tournaments with match counts. Variants are merged under their
canonical display name — picking "T20 World Cup (Men)" in the FilterBar
narrows queries across all three cricsheet event_names. Accepts the
common filters plus:

- `team` — tournaments a given team played in (scopes the dropdown on
  a team-scoped page).
- `opponent` — combined with `team`, returns only tournaments where
  the two teams actually played each other. Lets FilterBar decide
  whether a rivalry implies a single competition (MI vs CSK → IPL
  only) or spans many (Ind vs Aus → bilaterals + ICC).

Despite being called `tournaments`, this is the FILTER-BAR dropdown
list (selecting an `event_name`). The sectioned catalog used by the
`/series` page lives under `/api/v1/series/*` — see below.

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

List seasons in chronological order. Accepts `team`, `gender`,
`team_type`, `tournament` to narrow.

```bash
curl "http://localhost:8000/api/v1/seasons"
```

```json
{ "seasons": ["2004/05", "2005", "2005/06", "…", "2025/26", "2026"] }
```

## `GET /api/v1/teams`

Search team names. Supports all common filters + `q` (substring
match on team name).

```bash
curl "http://localhost:8000/api/v1/teams?q=India&team_type=international&gender=male"
```

```json
{ "teams": [ { "name": "India", "matches": 266 } ] }
```

## `GET /api/v1/players`

Player search. Params: `q` (≥2 chars), `role` (`batter`/`bowler`/
`fielder`, optional), `limit` (default 20).

```bash
curl "http://localhost:8000/api/v1/players?q=Kohli&limit=3"
```

```json
{
  "players": [
    { "id": "ba607b88", "name": "V Kohli", "unique_name": "V Kohli", "innings": 378 },
    { "id": "40caa465", "name": "T Kohli", "unique_name": "T Kohli", "innings": 29 }
  ]
}
```

---

# Landing pages

Each search-bar tab has one endpoint for the filter-sensitive
directory shown below the search. See
[`perf-leaderboards.md`](perf-leaderboards.md) for the perf pattern
(conditional JOINs + composite indexes + ANALYZE).

## `GET /api/v1/teams/landing`

Two-column directory.

International is split by **gender** (men's / women's) so women's full
members aren't buried inside a mixed list. Each gender bucket has
`regular` (ICC full members) vs `associate`. With a gender filter set,
only that gender's bucket is populated.

Club tournaments are bucketed by series_type using the canonicalization
map in `api/tournament_canonical.py`: **franchise_leagues** (IPL, BBL,
PSL, …), **domestic_leagues** / national championships (Vitality Blast,
Syed Mushtaq Ali Trophy, CSA T20 Challenge), **women_franchise** (WBBL,
WPL, The Hundred Women's, …), and **other** for unclassified.

Each team entry carries a `gender` field — when no gender filter is
set, the same string ("Royal Challengers Bengaluru" = IPL/men's AND
WPL/women's) appears as separate entries with different gender so the
frontend can disambiguate them with a "men's" / "women's" suffix.

```bash
curl "http://localhost:8000/api/v1/teams/landing?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024"
```

```json
{
  "international": {
    "men":   { "regular": [ { "name": "India", "gender": "male", "matches": 266 } ], "associate": [] },
    "women": { "regular": [], "associate": [] }
  },
  "club": {
    "franchise_leagues": [
      {
        "tournament": "Indian Premier League",
        "matches": 142,
        "teams": [
          { "name": "Chennai Super Kings", "gender": "male", "matches": 14 },
          { "name": "Delhi Capitals",       "gender": "male", "matches": 14 }
        ]
      }
    ],
    "domestic_leagues": [
      { "tournament": "Syed Mushtaq Ali Trophy", "matches": 695, "teams": [ "…" ] }
    ],
    "women_franchise": [
      { "tournament": "Women's Premier League", "matches": 88, "teams": [ "…" ] }
    ],
    "other": []
  }
```

## `GET /api/v1/batters/leaders`

Top-N batters by average and by strike rate, with min-sample
thresholds to exclude cameos. Params: `limit` (default 10),
`min_balls` (default 100), `min_dismissals` (default 3, applies to
averages list only).

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

Top-N bowlers by strike rate and by economy. Params: `limit`
(default 10), `min_balls` (default 60 = 10 overs), `min_wickets`
(default 3, applies to SR list only).

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

Top-N fielders by total dismissals (catches + stumpings +
run-outs + caught-and-bowled) and top-N keepers by designated-
keeper dismissals. Volume-based, no thresholds. Keepers sourced
via `keeper_assignment` (Tier 2).

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

Source: `api/routers/teams.py`. `{team}` is URL-encoded team name
(e.g. `Mumbai%20Indians`). All endpoints accept the common filters.

## `GET /api/v1/teams/{team}/summary`

Win/loss totals, toss stats, gender-breakdown banner, and Tier-2
keeper list.

```bash
curl "http://localhost:8000/api/v1/teams/India/summary?gender=male&team_type=international"
```

```json
{
  "team": "India",
  "matches": 266, "wins": 180, "losses": 75, "ties": 6, "no_results": 5,
  "win_pct": 67.7,
  "toss_wins": 122, "bat_first_wins": 98, "field_first_wins": 82,
  "gender_breakdown": null,
  "keepers": [
    { "person_id": "4a8a2e3b", "name": "MS Dhoni", "innings_kept": 74 },
    { "person_id": "919a3be2", "name": "RR Pant", "innings_kept": 36 }
  ],
  "keeper_ambiguous_innings": 18
}
```

## `GET /api/v1/teams/{team}/results`

Paginated match list for a team. Params: `limit` (default 50),
`offset`.

```bash
curl "http://localhost:8000/api/v1/teams/India/results?gender=male&team_type=international&limit=1"
```

```json
{
  "results": [
    {
      "match_id": 12903,
      "date": "2026-02-02",
      "opponent": "England",
      "venue": "ACA-VDCA Stadium",
      "tournament": "England in India T20I Series",
      "result": "won", "margin": "India won by 150 runs"
    }
  ],
  "total": 266
}
```

## `GET /api/v1/teams/{team}/vs/{opponent}`

Head-to-head team record (summary + per-season + match list).

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

Flat list of opponents with match counts (unused by UI currently,
kept for completeness).

## `GET /api/v1/teams/{team}/opponents-matrix`

Rollup (top-N opponents by match volume) + per-season cells for the
vs-Opponent tab's stacked bars + bubble matrix. Params: `top_n`
(default 8).

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

Wins/losses per season, used by the "Wins by Season" bar chart.

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

Per-season roster — everyone who appeared in the XI, alphabetical,
with batting average + bowling SR + year-over-year turnover.
Full-name resolution via `personname` variants.

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

Per-team aggregates that power the Batting / Bowling / Fielding /
Partnerships tabs on `/teams`. See `docs/spec-team-stats.md` for the
design. Shape follows a consistent pattern:

- `.../summary` — top-line ball-level stats (runs/balls/avg/SR/etc.).
- `.../by-season` — season rows for the line/bar charts.
- `.../by-phase` — powerplay / middle / death split.
- `.../top-batters` `.../top-bowlers` `.../top-fielders` — top-N
  players for that team. Params: `limit` (default 5).
- `.../phase-season-heatmap` — phase × season matrix for run rate +
  wickets/innings.

### Batting

```bash
curl "http://localhost:8000/api/v1/teams/India/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Returns: `{ team, innings_batted, total_runs, legal_balls, run_rate,
balls_per_boundary, balls_per_dismissal, dot_pct, highest_total,
lowest_total, avg_1st_innings, avg_2nd_innings }`. Subroutes:
`/by-season`, `/by-phase`, `/top-batters`, `/phase-season-heatmap`.

### Bowling

```bash
curl "http://localhost:8000/api/v1/teams/India/bowling/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Returns: `{ innings_bowled, total_runs_conceded, legal_balls_bowled,
wickets, economy, bowling_strike_rate, boundary_pct_conceded,
dot_pct_conceded, highest_conceded, lowest_conceded,
avg_1st_innings_conceded, avg_2nd_innings_conceded }`. Subroutes as
per batting — with `/top-bowlers` instead of `/top-batters`.

### Fielding

```bash
curl "http://localhost:8000/api/v1/teams/India/fielding/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Returns: `{ innings_fielded, catches, stumpings, run_outs,
caught_and_bowled, total_dismissals, substitute_catches,
catches_per_match, dismissals_per_match }`. Subroutes: `/by-season`,
`/top-fielders`.

### Partnerships

Five endpoints, all under `/teams/{team}/partnerships/…`. Takes the
same filter scope plus `side` (`batting`/`bowling` — whether
partnerships are FOR or AGAINST the team).

- `.../by-wicket?side=batting` — stats per wicket-number (1st-wicket
  avg partnership, 2nd, …, 10th).
- `.../best-pairs` — top-3 pairs per wicket by total runs together.
- `.../heatmap` — wicket × season matrix for avg partnership.
- `.../top?side=batting&limit=10` — top-N individual partnerships.
- `.../summary?side=batting` — aggregate counts (total / 50+ / 100+),
  highest single partnership, avg runs, and the all-time top pair.
  Powers the Teams → Compare tab's partnerships row.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/top?gender=male&team_type=international&season_from=2024&limit=1&side=batting"
```

Returns a list of `{ partnership_id, match_id, date, season,
opposition, wicket_number, batter1, batter2, runs, balls, run_rate,
ended_by_kind }`.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/summary?gender=male&team_type=international"
```

```json
{
  "team": "India",
  "side": "batting",
  "total": 1404,
  "count_50_plus": 226,
  "count_100_plus": 43,
  "avg_runs": 26.4,
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

---

# Batters (`/api/v1/batters/{id}/…`)

Source: `api/routers/batting.py`. `{id}` is the cricsheet hex
person_id (from `/players` search). All accept common filters plus
contextual ones.

## `GET /api/v1/batters/{id}/summary`

Career totals scoped to filters. Drives the StatCard row on a
player's batting page.

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/summary?gender=male&team_type=international"
```

```json
{
  "person_id": "ba607b88", "name": "V Kohli",
  "innings": 112, "runs": 3934, "balls_faced": 2895,
  "not_outs": 31, "dismissals": 81,
  "average": 48.57, "strike_rate": 135.89,
  "highest_score": 91, "hundreds": 0, "fifties": 37, "thirties": 17, "ducks": 6,
  "fours": 347, "sixes": 114, "boundaries": 461, "dots": 810,
  "dot_pct": 28.0, "balls_per_four": 8.34, "balls_per_six": 25.39, "balls_per_boundary": 6.28
}
```

## `GET /api/v1/batters/{id}/by-innings`

Innings list (Innings List tab). Params: `limit` (default 50),
`offset`, `sort` (`date`, `runs`, `strike_rate`, etc.).

```bash
curl "http://localhost:8000/api/v1/batters/ba607b88/by-innings?limit=1"
```

```json
{
  "innings": [
    {
      "match_id": 1551, "date": "2024-06-29",
      "team": "India", "opponent": "South Africa",
      "venue": "Kensington Oval, Bridgetown, Barbados",
      "tournament": "ICC Men's T20 World Cup",
      "runs": 76, "balls": 58, "fours": 6, "sixes": 2,
      "strike_rate": 131.03, "not_out": false,
      "how_out": "caught", "dismissed_by": "M Jansen"
    }
  ],
  "total": 378
}
```

## `GET /api/v1/batters/{id}/vs-bowlers`

Matchup table. Params: `bowler_id` (optional, for single-bowler
drilldown), `min_balls` (default 6).

Returns `{ matchups: [ { bowler_id, bowler, balls, runs,
dismissals, strike_rate, average, … } ] }`.

## `GET /api/v1/batters/{id}/by-over`

Over-by-over stats (1..20). Returns `{ by_over: [ { over, balls,
runs, strike_rate, dismissals, … } ] }`.

## `GET /api/v1/batters/{id}/by-phase`

Powerplay / middle / death split. `{ by_phase: [ { phase, balls,
runs, strike_rate, … } ] }`.

## `GET /api/v1/batters/{id}/by-season`

Season-by-season career trajectory. `{ by_season: [ { season, balls,
runs, dismissals, average, strike_rate, innings, fifties, hundreds,
dots, boundaries, … } ] }`.

## `GET /api/v1/batters/{id}/dismissals`

Dismissal analysis. Returns counts by `kind`, primary `bowler_type`
breakdown, and by_phase dismissal distribution. Used by the
Dismissals donut + bars.

## `GET /api/v1/batters/{id}/inter-wicket`

Partnership-segment analysis: runs + rate in each "between-wickets"
span of an innings. `{ inter_wicket: [ { after_wicket, avg_runs,
avg_balls, run_rate, n } ] }`.

---

# Bowlers (`/api/v1/bowlers/{id}/…`)

Source: `api/routers/bowling.py`. Mirror of the batters pattern.

## `GET /api/v1/bowlers/{id}/summary`

```bash
curl "http://localhost:8000/api/v1/bowlers/462411b3/summary?gender=male&team_type=international"
```

```json
{
  "person_id": "462411b3", "name": "JJ Bumrah",
  "innings": 90, "balls": 1966, "overs": "327.4",
  "runs_conceded": 2223, "wickets": 117,
  "average": 19.0, "economy": 6.78, "strike_rate": 16.8,
  "best_figures": "4/15", "four_wicket_hauls": 1,
  "fours_conceded": 210, "sixes_conceded": 54, "dots": 906, "dot_pct": 46.1,
  "wides": 73, "noballs": 11, "maiden_overs": 9
}
```

**Note (CLAUDE.md convention):** bowling uses `runs_conceded` and
`wickets`, NOT `runs`/`dismissals`. Don't reuse batting types.

## Other endpoints (same shape pattern)

- `GET /by-innings` — innings list with bowling figures. Params:
  `limit`, `offset`.
- `GET /vs-batters` — matchup table. Params: `batter_id`, `min_balls`.
- `GET /by-over` — economy/SR per over (1..20).
- `GET /by-phase` — powerplay / middle / death split.
- `GET /by-season` — season-by-season career.
- `GET /wickets` — wicket analysis: by_kind donut, by_phase bars,
  by_batter (most-dismissed batters), dismissal-over distribution.

---

# Fielders (`/api/v1/fielders/{id}/…`) — Tier 1

Source: `api/routers/fielding.py`. Backed by the `fieldingcredit`
table.

## `GET /api/v1/fielders/{id}/summary`

```bash
curl "http://localhost:8000/api/v1/fielders/a757b0d8/summary?gender=male&team_type=club"
```

```json
{
  "person_id": "a757b0d8", "name": "KA Pollard",
  "matches": 534,
  "catches": 300, "stumpings": 0, "run_outs": 19, "caught_and_bowled": 13,
  "total_dismissals": 332, "dismissals_per_match": 0.62,
  "substitute_catches": 0, "innings_kept": 0
}
```

`innings_kept > 0` signals to the frontend to show the Keeping tab.

## Other endpoints

- `GET /by-season` — dismissals per season split by kind.
- `GET /by-phase` — dismissals by powerplay / middle / death.
- `GET /by-over` — per-over dismissal counts.
- `GET /dismissal-types` — donut data (% catches vs stumpings vs
  run-outs vs c&b).
- `GET /victims` — batters dismissed by this fielder, ranked.
- `GET /by-innings` — innings-level list with per-innings fielding
  credits. Params: `limit`, `offset`.

---

# Keeping (`/api/v1/fielders/{id}/keeping/…`) — Tier 2

Source: `api/routers/keeping.py`. Only relevant when
`summary.innings_kept > 0` (Tier-2 keeper inference has assigned
innings to this person). See `docs/spec-fielding-tier2.md` for the
4-layer algorithm.

## `GET /keeping/summary`

```bash
curl "http://localhost:8000/api/v1/fielders/4a8a2e3b/keeping/summary?gender=male&team_type=club&tournament=Indian%20Premier%20League"
```

```json
{
  "person_id": "4a8a2e3b", "name": "MS Dhoni",
  "innings_kept": 245,
  "innings_kept_by_confidence": { "definitive": 39, "high": 177, "medium": 29, "low": 0 },
  "stumpings": 47, "keeping_catches": 142,
  "run_outs_while_keeping": 46, "byes_conceded": 100, "byes_per_innings": 0.41,
  "dismissals_while_keeping": 235, "keeping_dismissals_per_innings": 0.96,
  "ambiguous_innings": 32
}
```

- `GET /keeping/by-season` — per-season keeping stats.
- `GET /keeping/by-innings` — innings list for the Keeping tab.
  Params: `limit`, `offset`.
- `GET /keeping/ambiguous` — innings where this person was a
  candidate but the algorithm couldn't resolve to a single keeper,
  with the other candidates. For transparency in the UI.

---

# Head-to-head (`/api/v1/head-to-head/{batter_id}/{bowler_id}`)

Source: `api/routers/head_to_head.py`. Single endpoint — returns
everything the HeadToHead Player-vs-Player page needs. Filter scope
applies; if the pair never met under those filters, arrays come back
empty but the structure stays consistent.

Accepts an optional **`series_type`** query param to narrow by series
category — same semantics as the tournament-dossier endpoints. Four
mutually-exclusive categories that partition the data:

- `all` (default) — every meeting
- `bilateral` — international bilateral T20Is only (e.g. "India tour
  of Australia"). Excludes ICC events AND club tournaments.
- `icc` — ICC events only (T20 World Cup, Asia Cup, qualifiers, …)
- `club` — club tournaments only (IPL, BBL, PSL, Vitality Blast, …)

For matchups where both players are international teammates (Kohli +
Bumrah on India), `bilateral` and `icc` both return 0 — they never
face each other internationally. `club` returns their full IPL record
(108 balls, 159 runs lifetime). `series_type` composes with FilterBar
filters; setting `team_type=international&series_type=club` is
contradictory and yields 0.

Legacy names `bilateral_only` and `tournament_only` map to `bilateral`
and `icc` respectively for URL compat. The old `bilateral_only`
included club matches; the new `bilateral` is international-only.

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

Paginated list of matches. Accepts common filters plus `player_id`,
`team`, `opponent`, `venue`, `city`, `q`, `limit`, `offset`,
`sort` (date/runs/…).

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

Full scorecard — both innings with batting, bowling, extras, fall
of wickets, by-over run/wicket progression, keeper label.

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

**Fielder attribution:** each `batting[]` row carries
`dismissal_fielder_ids: string[]` from `fieldingcredit`, used by
the scorecard to highlight via `?highlight_fielder=<person_id>`.

## `GET /api/v1/matches/{match_id}/innings-grid`

Per-delivery grid for the InningsGridChart (every ball as a cell).

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

Source: `api/routers/tournaments.py` (filename is historical — the
router was renamed from `/tournaments/*` to `/series/*` to
disambiguate from the FilterBar's "Tournament" dropdown). These
power the `/series` landing + dossier UI AND the
`/head-to-head?mode=team` Team-vs-Team view.

The "match-set" framing is the unifying concept: every endpoint
takes optional `tournament` (canonical name; expanded to IN-variants),
optional `series_type` (`all` / `bilateral_only` / `tournament_only`),
plus the standard FilterParams including `filter_team` / `filter_opponent`
for rivalry scope. Same endpoints serve:

- IPL all-time (`?tournament=Indian+Premier+League`)
- IND vs AUS bilateral (`?filter_team=India&filter_opponent=Australia&series_type=bilateral_only`)
- IND vs AUS within T20 World Cups (`?tournament=T20+World+Cup+%28Men%29&filter_team=India&filter_opponent=Australia`)
- League baseline for any team (call without a team filter; same shape)

When `filter_team` + `filter_opponent` are both set, summary returns a
`by_team` companion with per-team breakdowns of top scorer, top wicket-
taker, highest individual, largest partnership — AND a top-level
`head_to_head` object with team1_wins / team2_wins / ties / no_result
so the dossier can show "who won how much" as the top stat row.

## `GET /api/v1/series/landing`

Sectioned directory for the `/series` landing page. Bilateral
rivalry tiles are bilateral-only and split by gender (top-9 full-member
men's and women's pairs).

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
                              "winner": "New Zealand" } }
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

The `club.rivalries` lists are top-12 most-played team pairs within
club tournaments per gender — drives the H2H Team-vs-Team page's club
suggestion tiles. Each entry carries the dominant tournament for
context (franchise pairs are unambiguously single-tournament: RCB vs
CSK is always IPL, never WBBL).

## `GET /api/v1/series/summary`

Headline numbers for any match-set scope. Tournament + series_type +
filter_team/opponent are all optional. Returns `by_team` when team-pair
in scope.

```bash
curl "http://localhost:8000/api/v1/series/summary?filter_team=India&filter_opponent=Australia&gender=male"
```

```json
{
  "canonical": null, "variants": [],
  "matches": 37, "editions": 13,
  "run_rate": 8.68, "boundary_pct": 17.69, "dot_pct": 34.8,
  "total_runs": "…", "total_wickets": "…", "total_sixes": 449,
  "most_titles": null,
  "champions_by_season": [],
  "top_scorer_alltime":   { "person_id": "ba607b88", "name": "V Kohli",  "runs": 794 },
  "top_wicket_taker_alltime": { "person_id": "462411b3", "name": "JJ Bumrah", "wickets": 20 },
  "highest_team_total":   { "team": "India", "total": 235, "match_id": 1347,
                            "opponent": "Australia", "date": "2023-11-26" },
  "largest_partnership":  { "runs": 141, "match_id": 1348 },
  "best_bowling": "…",
  "teams":  [ { "name": "India", "matches": 37 }, { "name": "Australia", "matches": 37 } ],
  "groups": [],
  "knockouts": [ "…matches with event_stage in (Final, Semi Final, …)" ],
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

Per-edition rollup: champion, runner-up, top scorer, top wicket-taker,
run rate, boundary %, sixes. Tournament + series_type + filter_*
optional.

```bash
curl "http://localhost:8000/api/v1/series/by-season?tournament=Indian+Premier+League&gender=male&team_type=club"
```

```json
{
  "tournament": "Indian Premier League",
  "seasons": [
    { "season": "2024", "matches": 71,
      "champion": "Kolkata Knight Riders", "runner_up": "Sunrisers Hyderabad",
      "final_match_id": 5945,
      "run_rate": 9.56, "boundary_pct": 21.07, "total_sixes": 1261,
      "top_scorer":      { "person_id": "ba607b88", "name": "V Kohli", "runs": 741 },
      "top_wicket_taker":{ "person_id": "f986ca1a", "name": "HV Patel", "wickets": 24 } }
  ]
}
```

## `GET /api/v1/series/points-table`

Reconstructed league-stage points table + NRR. Single-season scope
required (`season_from=season_to`). Tournament required. Returns one
table per `event_group` for ICC events; one combined table for IPL-shape
leagues.

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

When the requested scope is multi-season, response is
`{ "tables": [], "reason": "multi_season" }` so the frontend can hide
the tab.

## `GET /api/v1/series/records`

Records sub-lists for the match-set, each capped at `limit` (default 5).
Tournament optional.

```bash
curl "http://localhost:8000/api/v1/series/records?tournament=Indian+Premier+League&gender=male&team_type=club&limit=2"
```

```json
{
  "canonical": "Indian Premier League",
  "highest_team_totals":   [ { "team": "Sunrisers Hyderabad", "runs": 287, "opponent": "Royal Challengers Bengaluru", "match_id": 5904, "date": "2024-04-15" } ],
  "lowest_all_out_totals": [ "…" ],
  "biggest_wins_by_runs":   [ { "winner": "Mumbai Indians", "loser": "Delhi Capitals", "margin": 146, "match_id": 5471, "date": "2017-05-06" } ],
  "biggest_wins_by_wickets":[ "…" ],
  "largest_partnerships":   [ { "runs": 229, "batter1": { "name": "V Kohli" }, "batter2": { "name": "AB de Villiers" },
                                 "teams": "Royal Challengers Bengaluru v Gujarat Lions",
                                 "batting_team": "Royal Challengers Bengaluru",
                                 "match_id": 6586, "date": "2016-05-14" } ],
  "best_bowling_figures":   [ { "name": "AS Joseph", "wickets": 6, "runs": 14, "balls": 22,
                                 "figures": "6/14", "match_id": 5565, "date": "2019-04-06" } ],
  "most_sixes_in_a_match":  [ "…" ]
}
```

## `GET /api/v1/series/{batters,bowlers,fielders}-leaders`

Variant-aware leader lists (the `/batters/leaders` etc. wrappers, but
tournament canonical is expanded to IN-variants). Tournament optional;
when omitted, ranks across the full filter scope (useful for "top
batters in this rivalry").

Each row carries a `team` field — the player's dominant side in the
current scope (most balls faced for batters, most balls bowled for
bowlers, most fielding credits for fielders). In rivalry mode the UI
uses this to flip `filter_team` / `filter_opponent` per row so the
"vs <opponent>" context link points the player at their actual
opponent, not the dossier's verbatim `filter_opponent`.

```bash
curl "http://localhost:8000/api/v1/series/batters-leaders?tournament=T20+World+Cup+%28Men%29&gender=male&limit=3"
```

```json
{
  "by_average":     [ { "person_id": "…", "name": "ML Hayden", "team": "Australia", "runs": 259, "balls": 132, "dismissals": 3, "average": 86.33, "strike_rate": 196.21 } ],
  "by_strike_rate": [ { "person_id": "…", "name": "SV Samson", "team": "India", "strike_rate": 199.38, "runs": 321, "balls": 161 } ],
  "thresholds": { "min_balls": 100, "min_dismissals": 3 }
}
```

## `GET /api/v1/series/partnerships/by-wicket`

Per-wicket partnership rollup. Each row includes the single best stand
(batters + match + season + date) so multi-edition scope is
disambiguated. Tournament + filter_team optional. With `filter_team`,
narrows to that team's partnerships (side=batting) or against them
(side=bowling).

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

Top-N partnerships in the match-set scope. Same filters as `by-wicket`;
adds `limit` (default 10).

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

## `GET /api/v1/series/partnerships/heatmap`

Season × wicket-number average-runs matrix.

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

Lazy-loaded by the landing's "Show other rivalries" expander. Pairs
involving at least one non-top-9 team with ≥ 5 bilateral matches in
scope. Pass `gender` to scope.

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

Synthesized bilateral-rivalry dossier (legacy — new code uses the
match-set dossier endpoints above). Kept for compatibility.

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

# Players tab — no new endpoints

The `/players` tab (single-player overview + N-way career comparison)
is composed client-side from existing summary endpoints — no new
backend work. Per player, the frontend runs four requests in parallel:

```
GET /api/v1/batters/{id}/summary
GET /api/v1/bowlers/{id}/summary
GET /api/v1/fielders/{id}/summary
GET /api/v1/fielders/{id}/keeping/summary
```

and composes the four responses into a `PlayerProfile` (see
`frontend/src/api.ts::getPlayerProfile`). A 404 on any single
endpoint (specialist batters have no bowling row, etc.) resolves
to `null` without aborting the rest — the Players page hides
discipline bands whose summary came back empty.

For N-way comparison, each of the two or three players fires its own
four-fetch bundle in parallel. All fetches share the same FilterBar
scope (gender / team_type / tournament / season / filter_team /
filter_opponent), so narrowing the URL narrows every card at once.

---

# Things NOT yet in the API

- **Tournament-baseline overlays** (enhancement O) on team / batter /
  bowler / fielder pages — endpoints are baseline-ready but the
  frontend wiring (overlay charts + "vs league avg" columns) hasn't
  shipped.
- Team-to-team head-to-head beyond the current
  `/teams/{team}/vs/{opponent}` rollup (enhancement B in
  next-session-ideas).
- Cross-worker / cross-restart caching. Not needed yet — see the
  "three options" capture in `docs/next-session-ideas.md`.
