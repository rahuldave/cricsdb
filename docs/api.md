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
- **Venue / city strings are canonical.** `match.venue` and `match.city`
  go through `api/venue_aliases.py` at insert time, so every endpoint
  that echoes them returns the canonicalized form (e.g. `Wankhede
  Stadium, Mumbai`, not the raw cricsheet `Wankhede`; `County Ground
  (Taunton)`, not the ambiguous `County Ground`). Safe to use as an
  exact-match key. `match.venue_country` exists in the DB but is not
  yet surfaced on any endpoint — that's a Phase 2 addition when the
  `/venues` landing ships.

## Common filter query params

Applied across almost every endpoint below (enforced via
`api/filters.py::FilterBarParams` — formerly `FilterParams`, alias
preserved for incremental migration). When omitted → no constraint on
that axis.

| Param | Type | What it filters | Example |
|---|---|---|---|
| `gender` | `male`/`female` | `match.gender` | `gender=male` |
| `team_type` | `international`/`club` | `match.team_type` | `team_type=international` |
| `tournament` | string | `match.event_name` (exact OR canonical → IN variants) | `tournament=Indian%20Premier%20League` or `tournament=T20%20World%20Cup%20%28Men%29` |
| `season_from` | string | `match.season >= ...` | `season_from=2024` |
| `season_to` | string | `match.season <= ...` | `season_to=2024/25` |
| `filter_venue` | string | `match.venue = ...` (exact canonical) | `filter_venue=Wankhede%20Stadium%2C%20Mumbai` |

### Aux filters (page-local narrowings)

A separate `AuxParams` class (`api/filters.py`) holds page-local
filters that aren't driven by the FilterBar UI:

| Param | Type | What it filters | Example |
|---|---|---|---|
| `series_type` | `all`/`bilateral`/`icc`/`club` (default `all`) | Categorises the match — `bilateral` = international non-ICC; `icc` = ICC events (T20 WC etc.); `club` = `team_type=club` | `series_type=bilateral` |
| `scope_to_team` | string | Narrows the match pool to events that team has appeared in (intersection of `m.event_name`s). Used by the Compare-tab avg slot; gated frontend-side on `team_type='club'` (closed-league semantic). | `scope_to_team=Royal%20Challengers%20Bengaluru` |
| `team_class` | `full_member` / `primary_club` / `secondary_club` | Polymorphic over `team_type`. **`full_member`** (`team_type=international`): both teams are ICC full members (Afghanistan, Australia, Bangladesh, England, India, Ireland, New Zealand, Pakistan, South Africa, Sri Lanka, West Indies, Zimbabwe). **`primary_club`** (`team_type=club`): match's event_name is in a marquee international franchise league (IPL, BBL, PSL, BPL, CPL, SA20, ILT20, LPL, MLC, The Hundred (M+W), WBBL, WPL, Women's Cricket Super League). **`secondary_club`** (`team_type=club`): match's event_name is in a domestic state/county/provincial competition (Vitality Blast, Syed Mushtaq Ali Trophy, CSA T20 Challenge, Super Smash, Nepal Premier League, Women's Super Smash, NZC Women's T20). Cross-type combinations are silent no-ops (defensive backend gate — preserves URL robustness when frontend gate fails or curl mixes them). | `team_class=full_member` · `team_class=primary_club` · `team_class=secondary_club` |

Aux filters are accepted by **every endpoint** that takes
`FilterBarParams`. Routers declare both as FastAPI `Depends()` and
pass the aux through `filters.build(aux=aux)`, which appends the
relevant SQL clauses (e.g. `series_type_clause`) centrally so no
router has to wire each one by hand. Practical effect: every
`teams/...`, `batters/...`, `bowlers/...`, `fielders/...`, `matches`,
`venues/...` endpoint now narrows correctly under `?series_type=icc`
etc. (Pre-2026-04-19 they silently ignored it.)

Legacy `bilateral_only` / `tournament_only` values map to `bilateral`
/ `icc` for URL-bookmark compat.

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

`filter_venue` is an **ambient** filter (honored by every endpoint that
echoes the FilterBar, same as `gender`/`season`). Must match the
canonical venue name exactly — see the Conventions note above on venue
canonicalization. The FilterBar's Venue typeahead (frontend) calls
`/api/v1/venues?q=...` so the user doesn't need to know the exact
canonical string.

A handful of endpoints add endpoint-specific params (`limit`,
`offset`, `min_balls`, `min_dismissals`, `min_wickets`, `q`, `role`,
`top_n`, `bowler_id` / `batter_id` in matchup endpoints, etc.) —
called out per endpoint below.

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

Tournament dropdown (`/api/v1/tournaments`) and team typeahead
(`/api/v1/teams`) both respect `team_class` — they auto-narrow to
events / teams in the chosen tier so the user can't pick a
combination that would zero out (e.g. `tournament=Vitality Blast` +
`team_class=primary_club`).

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

List seasons in chronological order. Accepts every FilterBar axis
(`team`, `gender`, `team_type`, `tournament`, `filter_team`,
`filter_opponent`, `filter_venue`, `team_class`, `series_type`)
plus the rivalry pair (when `filter_team` + `filter_opponent` are
both set, narrows to seasons the two teams actually met) and —
added 2026-05-07 — `person_id` for player-aware narrowing.

```bash
curl "http://localhost:8000/api/v1/seasons"
```

```json
{ "seasons": ["2004/05", "2005", "2005/06", "…", "2025/26", "2026"] }
```

### `person_id` — player-aware narrowing

When set, the result is intersected with seasons the player
appeared in (matchplayer join). The FilterBar passes the page's
current `?player=<id>` URL param as `?person_id=<id>` so the
From/To dropdowns + the `first-3` / `prev-3` / `last-3` /
`latest` quick-select buttons all reflect the player's actual
career-in-scope rather than the broader dataset. Fixes the
retired-player gap — clicking `last-3` on AB de Villiers'
batting page now sets the season filter to `2019/20`-`2021`
(his actual final seasons) rather than `2024`-`2026` (the
dataset's recent seasons, which would show empty data).

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

`person_id` composes with the other filter axes via intersection
— `?tournament=Indian Premier League&person_id=c4487b84` returns
only IPL seasons ABdV played. The frontend `getSeasons()` wrapper
in `frontend/src/api.ts` accepts `player` (the URL convention)
and forwards it as `person_id` to this endpoint so callers don't
need to know the backend convention.

## `GET /api/v1/teams`

Search team names. Supports all common filters + `q` (substring
match on team name).

```bash
curl "http://localhost:8000/api/v1/teams?q=India&team_type=international&gender=male"
```

```json
{ "teams": [ { "name": "India", "matches": 266 } ] }
```

## `GET /api/v1/venues`

Scope-narrowed venue list, used as the FilterBar's Venue typeahead
(`components/VenueSearch.tsx`). Accepts all common filters except
`filter_venue` itself (self-referential) plus:

- `q` — substring match (case-insensitive) on `venue` OR `city`. When
  absent, returns the top-50 by match count (enough for an empty-state
  dropdown-on-focus).
- `limit` — default 50, max 500.

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

Country-grouped venue directory powering the `/venues` landing page.
Accepts all common filters except `filter_venue`. Countries ordered by
total match count DESC; venues within a country by match count DESC.

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

88 countries in the current DB. Filter-sensitive: with
`?team_type=international&gender=male`, totals and venue inclusion
narrow to men's internationals only.

## `GET /api/v1/venues/{venue}/summary`

Venue-character dossier bundle (Phase 3). Pins `m.venue = :venue` from
the path and strips any ambient `filter_venue` on the query; every
other common filter (gender / team_type / tournament / season window
/ filter_team / filter_opponent / team_class) is honored.

Status codes:
- **200** with `matches: 0` and empty payload sections — venue
  exists in the DB but the current filter scope has no matches
  (e.g. MCG + `team_class=secondary_club` — MCG hosts only
  BBL/WBBL, both primary). Frontend renders an empty-state page,
  not a generic error. **Behaviour change shipped 2026-04-30**:
  pre-fix, the endpoint conflated this with a missing venue and
  returned 404; the conflation only surfaced once the club-tier
  filter made zero-scope reachable.
- **404** only when `venue` doesn't appear at all in `match.venue`
  (genuine missing-venue path).

Returns: headline match count; matches-hosted-by tournament × gender
× season; average first-innings total; bat-first vs chase win counts
and percentages; toss decision split; toss-winner outcome correlation
per decision; boundary % and dot % per phase (powerplay 1-6, middle
7-15, death 16-20); ground-record highest total and lowest all-out.

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

Sanity: `bat_first_win_pct < 50` on dew-heavy grounds (Wankhede,
Chinnaswamy), ≥ 50 on spin-friendly grounds (Chepauk).

## `GET /api/v1/players`

Player search. Params: `q` (≥2 chars), `role` (`batter`/`bowler`/
`fielder`, optional), `limit` (default 20).

Optional FilterBar + aux scope params — when any of `gender`, `team_type`,
`tournament`, `season_from`, `season_to`, `filter_team`, `filter_opponent`,
`filter_venue`, or `series_type` is set, the endpoint narrows to people
who appeared on either team in scope matches (same match-level filter
as the `/series/*-leaders` endpoints). Used by the Series tab's
discipline-picker typeaheads so e.g. "AB" on T20 WC Men 2022/23-2025/26
doesn't surface AB de Villiers.

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

Win/loss totals, toss stats, gender-breakdown banner, Tier-2 keeper
list, and the canonical tournaments the team has matches in within
the active filter scope. Each numeric metric is wrapped in the per-
metric envelope (see "Compare metric envelope" below); identity-
bearing fields (`gender_breakdown`, `keepers`, `tournaments_in_scope`)
stay flat.

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

`tournaments_in_scope` drives the avg-col label promotion on the
Compare tab — when a club team's universe collapses to a singleton
(RCB → IPL), the avg col labels as the tournament instead of the
generic "Men's club average".

`last_match_date` is the team's most recent match in scope (ISO
YYYY-MM-DD). Drives the dormancy badge in the team-page header
via DormancyContext — gap > 60 days renders a small italic
"5 months since last match" / "last match: Oct 2021" badge per
the standard dormancy ladder. Null when the team has no matches
in scope.

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
  Each numeric metric envelope-wrapped — see "Compare metric envelope".
- `.../by-season` — season rows for the line/bar charts.
- `.../by-phase` — powerplay / middle / death split. Per-phase
  numeric metrics (run_rate / economy / boundary_pct / dot_pct)
  envelope-wrapped against the in-scope league baseline; counts
  (runs / balls / wickets_lost / fours / sixes) stay flat.
- `.../by-inning` — 1st-innings / 2nd-innings split. Sibling of
  `/by-phase` for the inning-split spec; partitions every numeric
  metric on `i.innings_number` (0/1). Same envelope shape as
  `/by-phase`. Available for batting / bowling / fielding /
  partnerships. Spec: `internal_docs/spec-inning-split.md` §3.2.
- `.../top-batters` `.../top-bowlers` `.../top-fielders` — top-N
  players for that team. Params: `limit` (default 5).
- `.../phase-season-heatmap` — phase × season matrix for run rate +
  wickets/innings.

#### Page-local `?inning=0|1` narrowing (AuxParams)

Every endpoint that joins innings (i.e. has innings-level metrics)
also accepts the page-local `?inning=0` (1st-innings only) or
`?inning=1` (2nd-innings only) query param. NOT a FilterBar field —
it's an AuxParams aux narrowing. Match-level endpoints
(`/teams/{team}/{summary,by-season,vs-opponent,match-list}`) honour
the same param via a derived match-id subquery (`team batted in
inning X` semantic). Spec: `internal_docs/spec-inning-split.md`
§3.1a + §5.2.

### Batting

```bash
curl "http://localhost:8000/api/v1/teams/India/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric is wrapped in the per-metric envelope (see
"Compare metric envelope" below). Returns:
`{ team, innings_batted, total_runs, legal_balls, run_rate,
boundary_pct, dot_pct, fours, sixes, fifties, hundreds,
avg_1st_innings_total, avg_2nd_innings_total,
highest_total, lowest_all_out_total }`. Identity-bearing fields
(`highest_total`, `lowest_all_out_total`) stay flat. Subroutes:
`/by-season`, `/by-phase`, `/by-inning`, `/top-batters`,
`/phase-season-heatmap` (unchanged shapes).

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

Same shape for `/bowling/by-inning` (with `runs_conceded` /
`economy` / `wickets` / `fours_conceded` / `sixes_conceded`
instead) and `/fielding/by-inning` (`matches` / `catches` /
`stumpings` / `run_outs` / `*_per_match`). For
`/partnerships/by-inning` the per-row keys are `n` / `avg_runs` /
`avg_balls` / `best_runs` (sibling of `/by-wicket`).

### Bowling

```bash
curl "http://localhost:8000/api/v1/teams/India/bowling/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric envelope-wrapped. Returns:
`{ team, innings_bowled, matches, runs_conceded, legal_balls, overs,
wickets, economy, strike_rate, average, dot_pct, fours_conceded,
sixes_conceded, wides, noballs, wides_per_match, noballs_per_match,
avg_opposition_total, worst_conceded, best_defence }`.
Identity-bearing fields (`worst_conceded`, `best_defence`) stay flat.
Subroutes as per batting — with `/top-bowlers` instead of
`/top-batters`.

### Fielding

```bash
curl "http://localhost:8000/api/v1/teams/India/fielding/summary?gender=male&team_type=international&season_from=2024&season_to=2025"
```

Each numeric metric envelope-wrapped. Returns:
`{ team, matches, catches, caught_and_bowled, stumpings, run_outs,
total_dismissals_contributed, catches_per_match, stumpings_per_match,
run_outs_per_match }`. Per-match rates' `scope_avg` is halved server-
side (each match has 2 fielding sides — team-side comparable is /2).
Subroutes: `/by-season`, `/top-fielders`.

### Partnerships

Five endpoints, all under `/teams/{team}/partnerships/…`. Takes the
same filter scope plus `side` (`batting`/`bowling` — whether
partnerships are FOR or AGAINST the team).

- `.../by-wicket?side=batting` — stats per wicket-number (1st-wicket
  avg partnership, 2nd, …, 10th). Numeric metrics (n, avg_runs)
  envelope-wrapped per wicket; identity-bearing best_partnership
  stays flat.
- `.../best-pairs` — top-3 pairs per wicket by total runs together.
- `.../heatmap` — wicket × season matrix for avg partnership.
- `.../top?side=batting&limit=10` — top-N individual partnerships.
- `.../summary?side=batting` — aggregate counts (total / 50+ / 100+),
  highest single partnership, avg runs, and the all-time top pair.
  Powers the Teams → Compare tab's partnerships row. Each numeric
  metric is wrapped in the per-metric envelope (see "Compare metric
  envelope" below).
- `.../by-season?side=batting` — per-season partnership rollup (total,
  50+, 100+, avg, best). Drives the partnerships band on the Compare
  tab's season-trajectory strip.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/top?gender=male&team_type=international&season_from=2024&limit=1&side=batting"
```

Returns a list of `{ partnership_id, match_id, date, season,
opposition, wicket_number, batter1, batter2, runs, balls, run_rate,
ended_by_kind }`.

```bash
curl "http://localhost:8000/api/v1/teams/India/partnerships/summary?gender=male&team_type=international"
```

Numeric metrics envelope-wrapped; identity-bearing `highest` +
`best_pair` stay flat.

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

Three sibling endpoints — one per discipline — that mirror the per-
player distribution dossiers (`/batters/{id}/distribution`, etc.)
at team grain. Each is a self-contained per-innings dossier with
two or three sibling distribution blocks under one master sample,
phase rollup, four scope-anchored form windows (`last_10` /
`last_60d` / `last_6mo` / `last_1yr`), Wilson 95% CIs on every
probability, and scope-derived suggested-splits.

`FilterParams.filter_team` is IGNORED — the team path-param
dominates. `FilterParams.filter_opponent` works as expected.
Optional `as_of_date` (YYYY-MM-DD) anchors the calendar form
windows deterministically; production callers omit it. Spec:
`internal_docs/spec-distribution-stats.md` §16.

#### `GET /api/v1/teams/{team}/batting/distribution`

Master sample = each innings the team batted (`i.team = :team`).
Two sibling blocks: `runs` (skewed continuous; chain-ladder
conditionals at 100/150/200/230 + over-aware doubling at the
10-over checkpoint) + `run_rate` (continuous per-over; flipped
polarity vs. bowler economy — high RR is good for batting). Per-
innings observation row carries `runs_at_10` / `wickets_at_10` /
`reached_10_overs` for the over-aware probabilities + the
escalation-ratio paired magnitude stat.

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

Wickets here is the team-batting "wickets fallen" count and excludes
`'retired hurt'` / `'retired not out'` (matches the existing team-
batting/by-phase convention).

#### `GET /api/v1/teams/{team}/bowling/distribution`

Master sample = the OPPONENT's batting innings under the active
filter scope (side-neutral team filter — match has the team, the
innings's batting side is NOT the team). Three sibling blocks:

- **`wickets`** — discrete count + simples (`p_leq_3`, `p_geq_5`,
  `p_geq_7`, `p_eq_10`) + ≥5-anchored conditionals (`p_7_given_5`,
  `p_10_given_5`) + over-aware `p_geq_3_at_10` ("early
  breakthrough") and `p_eq_10_given_3_at_10` ("finishing rate
  after early breakthrough").
- **`runs_conceded`** — mirror of team-batting `runs` polarity-
  flipped (low conceded is good). Five simples
  (`p_lt_100`/`p_lt_150`/`p_geq_150`/`p_geq_200`/`p_geq_230`) +
  chain ladder + over-aware doubling (`p_double_at_10` —
  "opp doubled on us from halfway").
- **`economy`** — sibling of bowler v1 economy block, at team
  grain. Same pool / per-innings / median schema; same milestones
  (`p_econ_leq_6/7`, `p_econ_geq_9/10`).

**Wickets exclusion list (TEAM-CREDITED).** The wickets count on
this endpoint INCLUDES run-outs — the team caused them (a fielder
threw the ball). Excluded kinds: `'retired hurt'`, `'retired out'`,
`'retired not out'`, `'obstructing the field'` (the four non-team-
credited kinds). This DIVERGES from `/teams/{team}/bowling/summary`
which uses the bowler-credited 5-element exclusion list (also
excludes `'run out'`). Both numbers are correct — they answer
different questions ("how many wickets did this team take?" vs
"how many wickets did our bowlers take?"). See `internal_docs/
design-decisions.md` "Team-bowling distribution wicket count"
for rationale.

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

Master sample = the OPPONENT's batting innings; counts fielding
events credited to any of the team's matchplayers in that match
(substitutes are tracked separately on the `substitute_catches`
scalar). Three sibling count blocks:

- **`catches`** — 4 simples (`p_eq_0`, `p_geq_3`, `p_geq_5`,
  `p_geq_7`); no conditional ladder.
- **`run_outs`** — 3-simple partition (`p_eq_0`, `p_eq_1`,
  `p_geq_2`); sums to 1.
- **`stumpings`** — same 3-simple partition. **ALWAYS shipped at
  team grain** — every senior team has had a keeper at some
  point; zero-event scopes ship all-zero chips with small-n CIs
  rather than null. (Diverges from player-fielder
  `/fielders/{id}/distribution`, where the stumpings block is
  null for non-keepers.)

Top-level scalars: `n_innings_fielded`, `wickets_total` (any-kind
count for the fielder-ratio tooltip "X catches of Y wickets"),
`substitute_catches`.

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

## Compare metric envelope

The 5 team-compare summary endpoints —
`/teams/{team}/{summary,batting/summary,bowling/summary,fielding/summary,partnerships/summary}` —
wrap each numeric metric in a per-metric envelope:

```json
{
  "value":       8.52,
  "scope_avg":   7.94,
  "delta_pct":   7.3,
  "direction":   "higher_better",
  "sample_size": 1606
}
```

- `value` — the team's raw value.
- `scope_avg` — the league baseline in the same FilterBar scope
  (computed server-side via the same SQL with `team=None`). For
  per-match fielding rates, the league pool is halved to be
  per-team comparable (each match has 2 fielding sides).
- `delta_pct` — signed `(value - scope_avg) / scope_avg × 100`,
  rounded to 1 decimal. Returns `null` for count metrics (`fours`,
  `wickets`, `total_runs`, etc.) where league total dwarfs team
  total — the percentage is mathematically computable but not
  meaningfully interpretable as "above/below average."
- `direction` — `"higher_better"` / `"lower_better"` / `null`.
  Per-metric constant in `api/metrics_metadata.py::METRIC_DIRECTIONS`.
- `sample_size` — the denominator that makes the comparison
  defensible (legal_balls for batting rates, balls_bowled for
  bowling rates, partnerships for partnership stats, matches for
  outcome rates).

Identity-bearing nested objects (`highest_total`, `lowest_all_out_total`,
`worst_conceded`, `best_defence`, `best_pair`, `keepers`,
`gender_breakdown`) stay flat — they're not metrics.

The envelope is consumed lightly by the Teams > Compare UI today
(`value` only). The other fields are shipped for Spec-2 surfaces
(player compare, leaderboard delta columns, H2H baseline) — see
`internal_docs/outlook-comparisons.md`.

The new `/scope/averages/*` endpoints below stay flat — they're the
baseline data, not a per-entity-with-baseline view.

---

# Scope averages (`/api/v1/scope/averages/…`)

Source: `api/routers/scope_averages.py`. The "average team" / league-
baseline counterpart to the team endpoints. Same FilterBar scope,
no team filter — pool-weighted aggregates across every team in the
filtered window. Drives the Average column on the Teams > Compare
tab plus the phase-bands and season-trajectory expansions.

All endpoints accept the standard FilterBar params (`gender`,
`team_type`, `tournament`, `season_from`, `season_to`,
`filter_venue`), the page-local `series_type`, the avg-slot's
`scope_to_team` (auto-narrows tournament universe to the team's
events when no tournament filter is set — applied frontend-side
only for `team_type='club'`; internationals default to the full
pool), and `team_class` (polymorphic — `full_member` on intl,
`primary_club` / `secondary_club` on clubs).

**Per-innings semantic** (since 2026-04-26):
Every numeric field on these endpoints (except match-level totals
on `/scope/averages/summary` and identity-bearing payloads like
`highest_total` / `best_partnership`) returns a per-INNINGS average
— what one batting / bowling / fielding innings yields in scope.
NOT a pool aggregate. See `internal_docs/perf-bucket-baselines.md`
"What 'average' means" for the per-metric table.

`innings_batted` / `innings_bowled` are dropped from the response
(they'd always be 1 under per-innings semantic). Per-match rates
(`catches_per_match`, `wides_per_match`, etc.) are halved at source
to express per-fielding-side or per-bowling-side rate, comparable
to a single team's contribution per match.

The response shape mirrors the team siblings, with two differences:

1. No `team` field on top-level (no team identity).
2. Identity-bearing nested objects are kept where meaningful at scope
   level. `highest_total` carries the team that scored it; the
   league's `best_partnership` at each wicket carries pair identity.
   The "average team's best pair" doesn't exist, so summary-level
   `best_pair` is omitted from the partnerships endpoint.

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

Per-innings semantic — `total_runs: 182.89` reads as "an avg
batting innings in IPL 2024 scored 182.89 runs". `fours: 15.31` =
~15 fours per innings. Rates (`run_rate`, `boundary_pct`,
`dot_pct`, `avg_*_innings_total`) unchanged from pool — they're
inherently per-innings. `highest_total` is identity (single
observation), not an average.

```bash
curl "http://localhost:8000/api/v1/scope/averages/summary?tournament=Indian+Premier+League&season_from=2024&season_to=2024"
```

Returns `{ matches, decided, ties, no_results, toss_decided,
bat_first_wins, field_first_wins, bat_first_win_pct }`. The
`bat_first_win_pct` is the most informative league-level signal —
"bat first wins X% of matches in this scope."

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

## `GET /api/v1/batters/{id}/distribution`

Per-innings runs distribution dossier: lifetime + form-window
aggregates (mean / median / variance / std / average), milestone
probabilities (`p_failure_10`, `p_25_plus`, `p_50_plus`,
`p_100_plus`), phase decomposition (powerplay / middle / death
runs and balls per phase, plus per-innings phase columns on every
observation), and scope-derived suggested-splits navigation hints
("All IPL", "All cricket in 2024", "All-time"). Form windows are
last-10 innings + last-60 days, both with the same shape as
lifetime; a `delta` block reports window-mean-minus-lifetime-mean
and window-median-minus-lifetime-median. Optional `as_of_date`
(YYYY-MM-DD) anchors the last-60-day window deterministically;
production callers omit it. Spec:
`internal_docs/spec-distribution-stats.md` §8.

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

## `GET /api/v1/bowlers/{id}/distribution`

Per-innings bowling distribution dossier. Three sibling
distribution blocks under one master sample:

- **`wickets`** — zero-inflated discrete count distribution
  (per-innings wickets taken). Six simples
  (`p_zero`/`p_geq_1`/`p_geq_2`/`p_geq_3`/`p_geq_4`/`p_geq_5`)
  + three ≥2-anchored conditionals (`p_3_given_2`/`p_4_given_2`/
  `p_5_given_2`). All conditional denominators equal `count(w ≥ 2)`
  for stable noise across the rare-event upper rungs (chain
  conditionals like `P(≥5│≥4)` would shrink the denominator
  geometrically and produce ±20pp confidence intervals at the top
  rung; anchoring keeps it bounded by `count(≥2)`).
- **`runs_conceded`** — skewed continuous, simples only
  (`p_leq_15`/`p_leq_25`/`p_geq_40`/`p_geq_50`).
- **`economy`** — continuous per-over rate. Surfaces BOTH `pool`
  (balls-weighted, the conventional career number) AND
  `mean_per_innings` (unweighted mean of per-innings RPO) — they
  answer different questions; histograms read against
  `mean_per_innings` for visual centre-of-mass, summary text
  reads against `pool`. Simples
  `p_econ_leq_6`/`p_econ_leq_7`/`p_econ_geq_9`/`p_econ_geq_10`.

Plus phase decomposition (powerplay/middle/death runs+balls+
wickets per phase, plus per-innings phase columns on every
observation), four form windows (last-10 innings, last-60d,
last-6mo, last-1yr), pool-derived scalars (`pool_strike_rate`,
`pool_average`), and scope-derived suggested-splits.

**Every probability field** ships as
`{ value, num, denom, ci_low, ci_high }` with a Wilson 95%
confidence interval. `value`, `ci_low`, `ci_high` are `null`
when `denom == 0` (undefined ratio).

**Master sample** = per `(match, innings the bowler bowled in)`
clearing the `min_balls` qualifying-innings threshold. Default
`min_balls=12` (= 2 legal overs); pass `min_balls=0` to include
1-ball cameos. The threshold is echoed back in
`response.thresholds.min_balls`.

Optional `as_of_date` (YYYY-MM-DD) anchors the calendar form
windows deterministically; production callers omit it. Spec:
`internal_docs/spec-distribution-stats.md` §11.

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

## `GET /api/v1/fielders/{id}/distribution`

Per-match fielding distribution dossier — three sibling count blocks
(catches / run_outs / stumpings) with three-simple milestones
(`P=0` / `P=1` / `P≥2`), Wilson 95% CIs, and four form windows.
Master sample is per-MATCH (not per-innings); fielding events span
both opponent-batting innings, so the natural unit is the match.

Stumpings block is `null` for non-keepers (`innings_kept == 0`);
the frontend uses this to hide the Stumpings tab. Substitute catches
are excluded from `catches.total` and surfaced separately as
`substitute_catches` for reconciliation against `/summary.catches`.
Caught-and-bowled is bowler-credited and lives on the bowling
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

`as_of_date` (optional ISO date) anchors the calendar form windows
for deterministic regression tests; production callers omit it.

Three-simples invariant: `p_zero + p_one + p_geq_2 == 1.0` per
block. The frontend Distribution panel renders three discrete bars
in the INDIGO/SAGE/OCHRE palette to match.

Spec: `internal_docs/spec-distribution-stats.md` §13.

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
men's and women's pairs). Each rivalry entry's `latest_match` carries
the most recent meeting across **all** international meetings (not
bilateral-only) — `tournament` is the canonical ICC event name when
the meeting was a recognized tournament (T20 WC, Asia Cup, …), or
`null` for bilateral tours. The pair counts (`matches`, `team1_wins`,
etc.) remain bilateral-only.

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
  "total_runs": "…", "total_wickets": "…",
  "total_fours": 934, "total_sixes": 449,
  "most_titles": null,
  "champions_by_season": [
    { "season": "2024", "champion": "India", "match_id": 1551,
      "team1": "India", "team2": "South Africa",
      "team1_score": "176/7", "team2_score": "169/8",
      "date": "2024-06-29" }
  ],
  "top_scorer_alltime":     { "person_id": "ba607b88", "name": "V Kohli",
                              "team": "India", "runs": 794 },
  "top_wicket_taker_alltime": { "person_id": "462411b3", "name": "JJ Bumrah",
                              "team": "India", "wickets": 20 },
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

Per-edition rollup: champion, runner-up, top scorer, top wicket-taker,
run rate, boundary %, sixes. Tournament + series_type + filter_*
optional. `champion_record` / `runner_up_record` carry `{played, won}`
for that team in that edition — used by the dossier's Editions tab to
render "India (8/9)" style bracketed fractions.

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

Every row carries `tournament` + `season` so the frontend Records tab
can render an Edition column + per-row `(ed)` team subscripts that
point at that specific tournament+season rather than the FilterBar's
ambient season window. Partnership + most-sixes rows additionally
split `teams` into explicit `team1` / `team2` for clean link
rendering.

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

`fielders-leaders` returns three top-N lists: `by_dismissals`
(catches + stumpings + run-outs + c&b), `by_keeper_dismissals`
(keeper-only — catches + stumpings sourced via `keeper_assignment`),
and `by_run_outs` (run-outs alone, sorted DESC, tiebreak on total;
excludes fielders with zero run-outs so the list isn't padded).

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

`fielders-leaders` response abbreviated:

```json
{
  "by_dismissals":         [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 258, "catches": 158, "stumpings": 47, "run_outs": 53, "c_and_b": 0 } ],
  "by_keeper_dismissals":  [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 189, "catches": 142, "stumpings": 47 } ],
  "by_run_outs":           [ { "person_id": "4a8a2e3b", "name": "MS Dhoni", "total": 258, "catches": 158, "stumpings": 47, "run_outs": 53, "c_and_b": 0 } ]
}
```

## `GET /api/v1/series/fielder-scope-stats`

Aggregate fielding stats for one picked player in the current scope —
sibling of `batter-scope-stats` and `bowler-scope-stats`. Backs the
Series > Fielders "Picked fielder" tile. Fielding is universal
(every XI member fields), so this endpoint differs from its batter /
bowler siblings in one way: when the player took 0 credits in scope
BUT was in the XI for ≥1 scope match (matchplayer check), it returns
a zero-filled entry rather than `{"entry": null}`. That way the
picker can render e.g. "Jadeja · 0 · 0 · 0 · 0 · 0" for an all-
rounder who fielded every match but took no catches / run-outs.
Truly out-of-scope players (no matchplayer entry) still return null.

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

Aggregate bowling stats for one picked player in the current scope —
sibling of `batter-scope-stats`. Backs the Series > Bowlers "Picked
bowler" tile. Returns `{"entry": null}` when the player has no
deliveries as bowler in scope. Same param set as the batter variant.

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

Aggregate batting stats for one specific player in the current
match-set scope. Backs the Series > Batters "Picked batter" tile: the
user picks a player from the scope-aware typeahead; this returns the
same row shape as `/series/batters-leaders` so the card reuses the
leaderboard cell renderers. Returns `{"entry": null}` when the
picked player has no deliveries in scope (e.g. filter tweaked after
picking).

Params: `person_id` (required), `tournament`, `series_type`, + full
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

## `GET /api/v1/series/partnerships/top-by-wicket`

Top-N partnerships **per wicket number** (1–10). Same filters as
`top`; replaces `limit` with `per_wicket` (default 10, max 20).
Returns ten grouped sub-lists.

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
