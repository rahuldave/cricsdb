# CricsDB API Reference

> **Also useful:**
> [Interactive Swagger UI](https://t20.rahuldave.com/docs) (prod) or
> [`http://localhost:8000/docs`](http://localhost:8000/docs) (local)
> — FastAPI auto-generates this from the route decorators. Every
> endpoint is clickable with a "Try it out" button. If you want to
> poke at something live, start there; come back here for narrative
> + the specific example responses that justify the section text.

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
| `tournament` | string | `match.event_name` (exact) | `tournament=Indian%20Premier%20League` |
| `season_from` | string | `match.season >= ...` | `season_from=2024` |
| `season_to` | string | `match.season <= ...` | `season_to=2024/25` |

Some endpoints also accept contextual filters:
- `filter_team=<name>` — restricts player stats to matches the
  person played while a member of that team.
- `filter_opponent=<name>` — restricts stats to matches against that
  opposition.

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

List tournaments (distinct `event_name`) with match counts. Accepts
the common filters plus `team` to narrow to tournaments a team
played in.

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

Two-column directory. International split into regular (ICC full
members) vs associate; clubs grouped by tournament.

```bash
curl "http://localhost:8000/api/v1/teams/landing?gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2024&season_to=2024"
```

```json
{
  "international": { "regular": [], "associate": [] },
  "club": [
    {
      "tournament": "Indian Premier League",
      "matches": 142,
      "teams": [
        { "name": "Chennai Super Kings", "matches": 14 },
        { "name": "Delhi Capitals", "matches": 14 }
      ]
    }
  ]
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

Four endpoints, all under `/teams/{team}/partnerships/…`. Takes the
same filter scope plus `side` on by-wicket / best-pairs
(`batting`/`bowling` — whether partnerships are FOR or AGAINST the
team).

- `.../by-wicket?side=batting` — stats per wicket-number (1st-wicket
  avg partnership, 2nd, …, 10th).
- `.../best-pairs` — top-3 pairs per wicket by total runs together.
- `.../heatmap` — wicket × season matrix for avg partnership.
- `.../top?side=batting&limit=10` — top-N individual partnerships.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/top?gender=male&team_type=international&season_from=2024&limit=1&side=batting"
```

Returns a list of `{ partnership_id, match_id, date, season,
opposition, wicket_number, batter1, batter2, runs, balls, run_rate,
ended_by_kind }`.

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
everything the HeadToHead page needs. Filter scope applies; if the
pair never met under those filters, arrays come back empty but the
structure stays consistent.

```bash
curl "http://localhost:8000/api/v1/head-to-head/ba607b88/3fb19989?team_type=international&gender=male"
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

# Things NOT yet in the API

- `/api/v1/tournaments/...` — the tournament-dossier tab itself
  (enhancement M); current `/tournaments` endpoint is just the
  reference list. See `docs/next-session-ideas.md`.
- Team-to-team head-to-head beyond the current
  `/teams/{team}/vs/{opponent}` rollup (enhancement B in
  next-session-ideas).
- Cross-worker / cross-restart caching. Not needed yet — see the
  "three options" capture in `docs/next-session-ideas.md`.
