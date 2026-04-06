# CricsDB — T20 Cricket Analytics Platform: Detailed Specification

## 1. Data Foundation

### 1.1 Database Schema (existing)

```
person (17,851 rows)
  id: str (PK, cricsheet hex identifier)
  name, unique_name, key_cricinfo, key_cricbuzz, ... (12 external platform IDs)

personname (7,502 rows)
  id: int (PK) → person_id: FK(person)
  name: str (alternate spellings)

match (12,940 rows)
  id: int (PK)
  filename, data_version, meta_created, meta_revision
  gender: "male" | "female"
  match_type: "T20" | "IT20"
  team_type: "international" | "club"
  season: str (e.g. "2024", "2024/25")
  team1, team2: str
  venue, city: str?
  event_name: str? (tournament name)
  event_match_number, event_group, event_stage: tournament position
  match_type_number: int? (sequential for intl matches)
  overs: int? (usually 20)
  balls_per_over: int (6)
  toss_winner, toss_decision: str?
  outcome_winner, outcome_by_runs, outcome_by_wickets, outcome_by_innings: result
  outcome_result: "draw" | "tie" | "no result" | null
  outcome_method: "D/L" | null
  outcome_eliminator, outcome_bowl_out: str? (super over / bowl out winner)
  player_of_match: JSON list
  dates: JSON list
  officials: JSON object

matchdate (12,959 rows)
  id: int (PK) → match_id: FK(match)
  date: str (YYYY-MM-DD)

matchplayer (285,525 rows)
  id: int (PK) → match_id: FK(match)
  team: str
  player_name: str
  person_id: FK(person)?

innings (25,886 rows)
  id: int (PK) → match_id: FK(match)
  innings_number: int (0-indexed; 0 and 1 are regular, 2+ are super overs)
  team: str (batting team)
  declared, forfeited, super_over: bool
  target_runs, target_overs: chase info
  powerplays: JSON
  penalty_runs_pre, penalty_runs_post: int

delivery (2,954,405 rows)
  id: int (PK) → innings_id: FK(innings)
  over_number: int (0-19)
  delivery_index: int (position within over, 0-based)
  batter, bowler, non_striker: str (names)
  batter_id, bowler_id, non_striker_id: FK(person)?
  runs_batter, runs_extras, runs_total: int
  runs_non_boundary: bool? (rare, 221 occurrences)
  extras_wides, extras_noballs, extras_byes, extras_legbyes, extras_penalty: int

wicket (160,418 rows)
  id: int (PK) → delivery_id: FK(delivery)
  player_out: str
  player_out_id: FK(person)?
  kind: str (caught, bowled, lbw, run out, stumped, caught and bowled,
             hit wicket, retired hurt, retired out, obstructing the field)
  fielders: JSON list of {name: str} objects
```

### 1.2 Key Data Characteristics

- **Team identity is per-match.** Players change teams across seasons (e.g. Kohli: RCB in IPL, India in internationals). The `innings.team` field tells you which team a player was batting for in a given innings. The `matchplayer` table records team assignment per match.
- **Deliveries are ordered** by `(innings_id, id)`. Within an innings, `id` is monotonically increasing and reflects ball order. `over_number` and `delivery_index` give the human-readable ball number (e.g. 3.2 = over 3, delivery index 2).
- **Legal balls vs all deliveries.** Wides and no-balls are deliveries but don't count as legal balls faced by the batter. A legal ball is one where `extras_wides = 0 AND extras_noballs = 0`. For batting stats (balls faced, strike rate), count legal balls. For bowling stats (balls bowled), also count legal balls only.
- **Boundaries.** A four is `runs_batter = 4` (and `runs_non_boundary` is not true). A six is `runs_batter = 6`. The `runs_non_boundary` flag is rare (221 cases) but should be respected: if set, `runs_batter = 4` is not a boundary four.
- **Bowler's wickets** exclude run outs, retired hurt, retired out, obstructing the field. These are "fielding" dismissals. For a bowler's wicket tally, filter `kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')`.
- **Super overs** are innings with `super_over = true`. They should be excluded from standard stats unless specifically requested.

---

## 2. Filtering System

### 2.1 Global Filters

Every API endpoint accepts these query parameters:

| Parameter | Type | Description | SQL Mapping |
|-----------|------|-------------|-------------|
| `gender` | `str?` | `"male"` or `"female"` | `match.gender = ?` |
| `team_type` | `str?` | `"international"` or `"club"` | `match.team_type = ?` |
| `tournament` | `str?` | Exact tournament name | `match.event_name = ?` |
| `season_from` | `str?` | Earliest season (inclusive) | `match.season >= ?` |
| `season_to` | `str?` | Latest season (inclusive) | `match.season <= ?` |

### 2.2 Tournament Taxonomy

Tournaments are identified by `match.event_name`. The API exposes a tournament list endpoint for populating dropdowns.

**Major Club Tournaments (men):**
- Indian Premier League (1,175 matches)
- Vitality Blast / NatWest T20 Blast (835 + 488 = 1,323 combined, name changed)
- Syed Mushtaq Ali Trophy (695)
- Big Bash League (662)
- Bangladesh Premier League (469)
- Caribbean Premier League (407)
- Pakistan Super League (323)
- Super Smash (266)
- The Hundred Men's Competition (167)
- CSA T20 Challenge / Ram Slam T20 Challenge (154 + 130)
- International League T20 (134)
- SA20 (130)
- Lanka Premier League (119)
- Major League Cricket (75)
- Nepal Premier League (64)

**Major Club Tournaments (women):**
- Women's Big Bash League (519)
- The Hundred Women's Competition (155)
- Women's Super Smash (148)
- Women's Cricket Super League (95)
- Women's Premier League (88)

**Major International Tournaments (men):**
- ICC Men's T20 World Cup / ICC World Twenty20 / World T20 (173 + 104 + 57 = 334 combined, name changed)
- ICC Men's T20 World Cup Qualifier / ICC World Twenty20 Qualifier (70 + 103)
- Asia Cup / Men's T20 Asia Cup (22 + 16)
- Bilateral series (e.g. "England tour of West Indies", "South Africa tour of India")

**Major International Tournaments (women):**
- ICC Women's T20 World Cup / Women's World T20 / ICC Women's World Twenty20 (89 + 46 + 21)
- Women's Asia Cup / Women's Twenty20 Asia Cup (38 + 15)
- Women's Ashes (16)
- Commonwealth Games (16)

Note: Some tournaments changed names over time (e.g. "ICC World Twenty20" → "ICC Men's T20 World Cup"). The API serves raw `event_name` values. The frontend may group related names in the UI.

### 2.3 Contextual Filters

In addition to global filters, endpoints accept contextual filters:

| Parameter | Available On | Description |
|-----------|-------------|-------------|
| `team` | batting, bowling, head-to-head | Filter by the batter's/bowler's team in that match |
| `opponent` | teams, batting, bowling | Filter by the opposing team |
| `bowler_id` | batting endpoints | Filter batting stats against a specific bowler |
| `batter_id` | bowling endpoints | Filter bowling stats against a specific batter |

### 2.4 Filter SQL Generation

All filters are applied by joining `delivery → innings → match`. A helper function builds the WHERE clause:

```python
def build_filters(
    gender=None, team_type=None, tournament=None,
    season_from=None, season_to=None,
    team=None, opponent=None,
    table_alias="m",  # match alias
    innings_alias="i",  # innings alias
):
    clauses = []
    params = {}
    if gender:
        clauses.append(f"{table_alias}.gender = :gender")
        params["gender"] = gender
    if team_type:
        clauses.append(f"{table_alias}.team_type = :team_type")
        params["team_type"] = team_type
    if tournament:
        clauses.append(f"{table_alias}.event_name = :tournament")
        params["tournament"] = tournament
    if season_from:
        clauses.append(f"{table_alias}.season >= :season_from")
        params["season_from"] = season_from
    if season_to:
        clauses.append(f"{table_alias}.season <= :season_to")
        params["season_to"] = season_to
    if team:
        clauses.append(f"{innings_alias}.team = :team")
        params["team"] = team
    if opponent:
        # The opponent is the other team in the match
        clauses.append(f"""(
            ({table_alias}.team1 = :opponent AND {innings_alias}.team = {table_alias}.team2)
            OR ({table_alias}.team2 = :opponent AND {innings_alias}.team = {table_alias}.team1)
        )""")
        params["opponent"] = opponent
    return " AND ".join(clauses), params
```

Exclude super overs by default: `AND i.super_over = 0`.

---

## 3. API Endpoints

Base URL: `/api/v1`

All responses are JSON. All endpoints are async. Pagination is not needed for aggregation endpoints; list endpoints (match lists, player search) use `limit` and `offset`.

### 3.0 Reference Data

#### `GET /api/v1/tournaments`

Returns the list of all tournaments with match counts, for populating filter dropdowns.

```json
{
  "tournaments": [
    {
      "event_name": "Indian Premier League",
      "team_type": "club",
      "gender": "male",
      "matches": 1175,
      "seasons": ["2008", "2009", ..., "2026"]
    },
    ...
  ]
}
```

**SQL:**
```sql
SELECT event_name, team_type, gender,
       COUNT(*) as matches,
       GROUP_CONCAT(DISTINCT season ORDER BY season) as seasons
FROM match
WHERE event_name IS NOT NULL
GROUP BY event_name, team_type, gender
ORDER BY matches DESC
```

#### `GET /api/v1/seasons`

Returns all distinct seasons, sorted.

```json
{ "seasons": ["2003", "2003/04", ..., "2026"] }
```

#### `GET /api/v1/teams`

Returns all teams with match counts.

Query params: `gender`, `team_type`, `tournament`, `q` (search substring)

```json
{
  "teams": [
    { "name": "India", "matches": 312, "team_type": "international", "gender": "male" },
    { "name": "Royal Challengers Bengaluru", "matches": 252, "team_type": "club", "gender": "male" },
    ...
  ]
}
```

**SQL:**
```sql
SELECT team, COUNT(DISTINCT match_id) as matches
FROM matchplayer mp
JOIN match m ON m.id = mp.match_id
WHERE 1=1 {filter_clauses}
GROUP BY team
ORDER BY matches DESC
```

#### `GET /api/v1/players`

Search players by name. Used for autocomplete.

Query params: `q` (required, min 2 chars), `role` (optional: `"batter"` or `"bowler"`), `limit` (default 20)

```json
{
  "players": [
    { "id": "462411b3", "name": "JJ Bumrah", "unique_name": "JJ Bumrah", "matches": 142 },
    ...
  ]
}
```

When `role=batter`, joins on `delivery.batter_id`; when `role=bowler`, joins on `delivery.bowler_id`. The `matches` count helps rank relevance.

**SQL (role=batter):**
```sql
SELECT p.id, p.name, p.unique_name,
       COUNT(DISTINCT d.innings_id) as innings
FROM person p
JOIN delivery d ON d.batter_id = p.id
WHERE p.name LIKE :q || '%' OR p.unique_name LIKE '%' || :q || '%'
GROUP BY p.id
ORDER BY innings DESC
LIMIT :limit
```

Also search `personname` table for alternate spellings.

---

### 3.1 Teams

#### `GET /api/v1/teams/{team_name}/summary`

Overall record for a team.

Query params: global filters + `opponent`

```json
{
  "team": "India",
  "matches": 230,
  "wins": 155,
  "losses": 65,
  "ties": 3,
  "no_results": 7,
  "win_pct": 67.4,
  "toss_wins": 118,
  "bat_first_wins": 70,
  "field_first_wins": 85
}
```

**SQL:**
```sql
SELECT
    COUNT(*) as matches,
    SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN m.outcome_winner IS NOT NULL
             AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
    SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
    SUM(CASE WHEN m.toss_winner = :team THEN 1 ELSE 0 END) as toss_wins
FROM match m
WHERE (m.team1 = :team OR m.team2 = :team)
  {filter_clauses}
```

#### `GET /api/v1/teams/{team_name}/results`

List of individual match results.

Query params: global filters + `opponent`, `limit` (default 50), `offset`

```json
{
  "results": [
    {
      "match_id": 123,
      "date": "2024-03-15",
      "opponent": "Australia",
      "venue": "Eden Gardens",
      "city": "Kolkata",
      "tournament": "ICC Men's T20 World Cup",
      "toss_winner": "India",
      "toss_decision": "field",
      "result": "won",
      "margin": "8 wickets",
      "player_of_match": ["V Kohli"]
    },
    ...
  ],
  "total": 230
}
```

#### `GET /api/v1/teams/{team_name}/vs/{opponent}`

Head-to-head record and match list.

Query params: global filters

```json
{
  "team": "India",
  "opponent": "Pakistan",
  "overall": { "matches": 12, "wins": 9, "losses": 2, "ties": 1 },
  "by_season": [
    { "season": "2024", "matches": 2, "wins": 1, "losses": 1 },
    ...
  ],
  "matches": [
    {
      "match_id": 456,
      "date": "2024-06-09",
      "venue": "Nassau County International Cricket Stadium",
      "tournament": "ICC Men's T20 World Cup",
      "result": "won",
      "margin": "6 runs"
    },
    ...
  ]
}
```

#### `GET /api/v1/teams/{team_name}/by-season`

Season-by-season record for timeline charts.

Query params: global filters

```json
{
  "seasons": [
    { "season": "2024", "matches": 28, "wins": 20, "losses": 6, "ties": 1, "no_results": 1, "win_pct": 71.4 },
    ...
  ]
}
```

---

### 3.2 Batting

#### `GET /api/v1/batters/{person_id}/summary`

Career batting summary.

Query params: global filters + `team`, `opponent`, `bowler_id`

```json
{
  "person_id": "c4487b84",
  "name": "V Kohli",
  "innings": 245,
  "runs": 4038,
  "balls_faced": 3102,
  "not_outs": 52,
  "dismissals": 193,
  "average": 20.92,
  "strike_rate": 130.17,
  "highest_score": 113,
  "hundreds": 1,
  "fifties": 38,
  "thirties": 55,
  "ducks": 14,
  "fours": 352,
  "sixes": 112,
  "boundaries": 464,
  "dots": 1205,
  "dot_pct": 38.8,
  "balls_per_four": 8.81,
  "balls_per_six": 27.70,
  "balls_per_boundary": 6.69
}
```

**Metric definitions:**
- `innings`: COUNT of distinct (match_id, innings_number) combos where this batter faced at least one legal ball
- `balls_faced`: COUNT of deliveries WHERE `batter_id = :id AND extras_wides = 0 AND extras_noballs = 0`
- `runs`: SUM of `runs_batter` on all deliveries (including wides/noballs — batter still gets credit for runs scored off those)
- `not_outs`: innings where the batter was never dismissed (no wicket row with `player_out_id = :id`)
- `dismissals`: COUNT of wickets WHERE `player_out_id = :id AND kind NOT IN ('retired hurt', 'retired out')`
- `average`: `runs / dismissals` (null if no dismissals)
- `strike_rate`: `(runs / balls_faced) * 100`
- `fours`: COUNT WHERE `runs_batter = 4 AND (runs_non_boundary IS NULL OR runs_non_boundary = 0)`
- `sixes`: COUNT WHERE `runs_batter = 6`
- `dots`: COUNT WHERE `runs_batter = 0 AND runs_extras = 0`
- `highest_score`: MAX runs in a single innings (computed per innings)
- `fifties`: innings with 50-99 runs
- `hundreds`: innings with 100+ runs
- `thirties`: innings with 30-49 runs
- `ducks`: innings with 0 runs AND was dismissed

**SQL (core):**
```sql
SELECT
    COUNT(*) as balls_faced,
    SUM(d.runs_batter) as runs,
    SUM(CASE WHEN d.runs_batter = 4
             AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.batter_id = :person_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}
```

**SQL (per-innings for highest, 50s, 100s, ducks, not-outs):**
```sql
SELECT
    i.match_id,
    i.innings_number,
    SUM(d.runs_batter) as innings_runs,
    COUNT(*) as innings_balls,
    MAX(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) as was_dismissed
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
LEFT JOIN wicket w ON w.delivery_id = d.id AND w.player_out_id = :person_id
    AND w.kind NOT IN ('retired hurt', 'retired out')
WHERE d.batter_id = :person_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}
GROUP BY i.match_id, i.innings_number
```

#### `GET /api/v1/batters/{person_id}/by-innings`

List of individual innings (scorecard-style).

Query params: global filters + `team`, `opponent`, `bowler_id`, `limit` (default 50), `offset`, `sort` (`date`, `runs`, `strike_rate`; default `date` desc)

```json
{
  "innings": [
    {
      "match_id": 789,
      "date": "2024-03-15",
      "team": "Royal Challengers Bengaluru",
      "opponent": "Chennai Super Kings",
      "venue": "M Chinnaswamy Stadium",
      "tournament": "Indian Premier League",
      "runs": 77,
      "balls": 49,
      "fours": 8,
      "sixes": 4,
      "strike_rate": 157.14,
      "not_out": false,
      "how_out": "caught",
      "dismissed_by": "RA Jadeja"
    },
    ...
  ],
  "total": 245
}
```

#### `GET /api/v1/batters/{person_id}/vs-bowlers`

Batting record against each bowler faced.

Query params: global filters + `team`, `bowler_id` (optional, to filter to one bowler), `min_balls` (default 6), `limit` (default 50), `sort` (`balls`, `runs`, `strike_rate`, `dismissals`; default `balls` desc)

```json
{
  "matchups": [
    {
      "bowler_id": "462411b3",
      "bowler_name": "JJ Bumrah",
      "balls": 82,
      "runs": 74,
      "dismissals": 4,
      "average": 18.50,
      "strike_rate": 90.24,
      "fours": 6,
      "sixes": 2,
      "dots": 42,
      "dot_pct": 51.2,
      "balls_per_four": 13.67,
      "balls_per_six": 41.00,
      "balls_per_boundary": 10.25
    },
    ...
  ]
}
```

**SQL:**
```sql
SELECT
    d.bowler_id,
    d.bowler as bowler_name,
    COUNT(*) as balls,
    SUM(d.runs_batter) as runs,
    SUM(CASE WHEN d.runs_batter = 4
             AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.batter_id = :person_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}
GROUP BY d.bowler_id
HAVING COUNT(*) >= :min_balls
ORDER BY balls DESC
```

Wickets counted separately:
```sql
SELECT d.bowler_id, COUNT(*) as dismissals
FROM wicket w
JOIN delivery d ON d.id = w.delivery_id
WHERE w.player_out_id = :person_id
  AND w.kind NOT IN ('retired hurt', 'retired out')
GROUP BY d.bowler_id
```

#### `GET /api/v1/batters/{person_id}/by-over`

Batting performance by over number (0-19).

Query params: global filters + `team`, `opponent`, `bowler_id`

```json
{
  "by_over": [
    {
      "over_number": 0,
      "balls": 340,
      "runs": 380,
      "fours": 42,
      "sixes": 8,
      "dots": 145,
      "dismissals": 12,
      "strike_rate": 111.76,
      "dot_pct": 42.6,
      "boundary_pct": 14.7,
      "balls_per_four": 8.10,
      "balls_per_six": 42.50,
      "balls_per_boundary": 6.80
    },
    ...
  ]
}
```

**SQL:**
```sql
SELECT
    d.over_number,
    COUNT(*) as balls,
    SUM(d.runs_batter) as runs,
    SUM(CASE WHEN d.runs_batter = 4
             AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.batter_id = :person_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}
GROUP BY d.over_number
ORDER BY d.over_number
```

Dismissals per over:
```sql
SELECT d.over_number, COUNT(*) as dismissals
FROM wicket w
JOIN delivery d ON d.id = w.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE w.player_out_id = :person_id
  AND w.kind NOT IN ('retired hurt', 'retired out')
  AND i.super_over = 0
  {filter_clauses}
GROUP BY d.over_number
```

#### `GET /api/v1/batters/{person_id}/by-phase`

Batting by phase (powerplay / middle / death).

Query params: global filters + `team`, `opponent`, `bowler_id`

Same response shape as by-over but grouped into 3 phases:
- **Powerplay:** overs 0-5
- **Middle:** overs 6-14
- **Death:** overs 15-19

```json
{
  "by_phase": [
    { "phase": "powerplay", "overs": "0-5", "balls": 1200, "runs": 1560, ... },
    { "phase": "middle",    "overs": "6-14", "balls": 1400, "runs": 1700, ... },
    { "phase": "death",     "overs": "15-19", "balls": 502, "runs": 778, ... }
  ]
}
```

**SQL:** Same as by-over but with:
```sql
CASE
    WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
    WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
    WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
END as phase
```

#### `GET /api/v1/batters/{person_id}/by-season`

Season-by-season batting record for timeline charts.

Query params: global filters + `team`, `opponent`

```json
{
  "by_season": [
    {
      "season": "2024",
      "innings": 18,
      "runs": 741,
      "balls": 530,
      "average": 52.93,
      "strike_rate": 139.81,
      "fours": 72,
      "sixes": 28,
      "fifties": 7,
      "hundreds": 1,
      "dismissals": 14,
      "balls_per_boundary": 5.30
    },
    ...
  ]
}
```

#### `GET /api/v1/batters/{person_id}/dismissals`

Dismissal analysis.

Query params: global filters + `team`, `opponent`, `bowler_id`

```json
{
  "total_dismissals": 193,
  "by_kind": {
    "caught": 102,
    "bowled": 38,
    "lbw": 22,
    "run out": 15,
    "stumped": 12,
    "caught and bowled": 4
  },
  "by_phase": {
    "powerplay": 28,
    "middle": 95,
    "death": 70
  },
  "by_over": [
    { "over_number": 0, "dismissals": 5 },
    ...
  ],
  "top_bowlers": [
    { "bowler_id": "xxx", "bowler_name": "JJ Bumrah", "dismissals": 4, "kinds": {"caught": 2, "bowled": 1, "lbw": 1} },
    ...
  ]
}
```

#### `GET /api/v1/batters/{person_id}/inter-wicket`

Inter-wicket analysis: how the batter performs between successive team wicket falls.

This answers: "When the team is 2 down vs 3 down, how does this batter perform?"

Query params: global filters + `team`, `opponent`

**Algorithm:** For each innings the batter participated in:
1. Order all deliveries in the innings by id
2. Track cumulative team wickets (from `wicket` table — all kinds count as team wickets except retired hurt/out)
3. For each delivery the target batter faced, record which "wicket phase" it fell in (0 wickets down, 1 wicket down, ..., 9 wickets down)
4. Aggregate across innings

```json
{
  "inter_wicket": [
    {
      "wickets_down": 0,
      "innings_count": 180,
      "balls": 820,
      "runs": 1050,
      "fours": 110,
      "sixes": 35,
      "strike_rate": 128.05,
      "dismissals": 42,
      "avg_balls_before_next_wicket": 24.5
    },
    {
      "wickets_down": 1,
      "innings_count": 160,
      "balls": 700,
      ...
    },
    ...
  ]
}
```

**Note:** This is the most expensive query. It cannot be done in pure SQL efficiently because it requires tracking running wicket state across deliveries within an innings. Two implementation options:

**Option A (Python-side):** Fetch all deliveries + wickets for the batter's innings, process in Python. Fine for a single player's career (~3K-10K deliveries).

**Option B (Materialized):** Pre-compute a `wickets_down` column on the delivery table. Better for repeated access but adds import complexity.

**Recommendation:** Option A for v1. The query fetches ~5K deliveries for a top player, processes in <100ms.

---

### 3.3 Bowling

#### `GET /api/v1/bowlers/{person_id}/summary`

Career bowling summary.

Query params: global filters + `team`, `opponent`, `batter_id`

```json
{
  "person_id": "462411b3",
  "name": "JJ Bumrah",
  "innings": 142,
  "balls": 3248,
  "overs": "541.2",
  "runs_conceded": 4197,
  "wickets": 318,
  "average": 13.20,
  "economy": 7.75,
  "strike_rate": 10.21,
  "best_figures": "4/14",
  "four_wicket_hauls": 3,
  "fours_conceded": 380,
  "sixes_conceded": 112,
  "boundaries_conceded": 492,
  "dots": 1680,
  "dot_pct": 51.7,
  "wides": 125,
  "noballs": 32,
  "balls_per_four": 8.55,
  "balls_per_six": 29.00,
  "balls_per_boundary": 6.60,
  "maiden_overs": 5
}
```

**Metric definitions:**
- `balls`: COUNT WHERE `bowler_id = :id AND extras_wides = 0 AND extras_noballs = 0` (legal deliveries)
- `overs`: `balls // 6` + "." + `balls % 6` (e.g. "541.2" means 541 overs and 2 balls)
- `runs_conceded`: SUM of `runs_total` on all deliveries bowled (including wides/noballs — bowler charged for all runs)
- `wickets`: COUNT from wicket table WHERE bowler_id matches AND kind is a bowler's wicket
- `economy`: `(runs_conceded / balls) * 6` — runs per over (using legal balls)
- `average`: `runs_conceded / wickets`
- `strike_rate`: `balls / wickets` (balls per wicket)
- `fours_conceded`: COUNT WHERE `runs_batter = 4 AND COALESCE(runs_non_boundary, 0) = 0`
- `sixes_conceded`: COUNT WHERE `runs_batter = 6`
- `dots`: COUNT WHERE `runs_total = 0` (all deliveries, including wides=0 noballs=0)
- `best_figures`: best wickets/runs in a single innings (requires per-innings grouping)
- `maiden_overs`: overs where total runs = 0 and exactly 6 legal deliveries bowled

**SQL (core — note: runs_conceded uses ALL deliveries, balls uses only legal):**
```sql
-- Legal balls, batting runs, boundaries, dots
SELECT
    COUNT(*) as legal_balls,
    SUM(d.runs_batter) as batter_runs,
    SUM(CASE WHEN d.runs_batter = 4
             AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_total = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.bowler_id = :person_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}

-- All deliveries for runs conceded and extras counts
SELECT
    COUNT(*) as all_deliveries,
    SUM(d.runs_total) as runs_conceded,
    SUM(d.extras_wides) as wides,
    SUM(d.extras_noballs) as noballs
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.bowler_id = :person_id
  AND i.super_over = 0
  {filter_clauses}
```

#### `GET /api/v1/bowlers/{person_id}/by-innings`

List of individual bowling spells.

Query params: global filters + `team`, `opponent`, `batter_id`, `limit`, `offset`, `sort`

```json
{
  "innings": [
    {
      "match_id": 789,
      "date": "2024-04-12",
      "team": "Mumbai Indians",
      "opponent": "Chennai Super Kings",
      "tournament": "Indian Premier League",
      "overs": "4.0",
      "balls": 24,
      "runs": 28,
      "wickets": 3,
      "economy": 7.00,
      "fours": 2,
      "sixes": 1,
      "dots": 12,
      "maidens": 0,
      "wides": 1,
      "noballs": 0
    },
    ...
  ]
}
```

#### `GET /api/v1/bowlers/{person_id}/vs-batters`

Bowling record against each batter faced.

Query params: global filters + `team`, `batter_id`, `min_balls` (default 6), `limit`, `sort`

```json
{
  "matchups": [
    {
      "batter_id": "c4487b84",
      "batter_name": "V Kohli",
      "balls": 82,
      "runs_conceded": 74,
      "wickets": 4,
      "average": 18.50,
      "economy": 5.41,
      "strike_rate": 20.50,
      "fours_conceded": 6,
      "sixes_conceded": 2,
      "dots": 42,
      "dot_pct": 51.2,
      "balls_per_four": 13.67,
      "balls_per_six": 41.00,
      "balls_per_boundary": 10.25
    },
    ...
  ]
}
```

#### `GET /api/v1/bowlers/{person_id}/by-over`

Bowling performance by over number (0-19).

Query params: global filters + `team`, `opponent`, `batter_id`

```json
{
  "by_over": [
    {
      "over_number": 0,
      "balls": 420,
      "runs_conceded": 340,
      "wickets": 18,
      "economy": 4.86,
      "dot_pct": 55.2,
      "boundary_pct": 10.5,
      "balls_per_four": 12.00,
      "balls_per_six": 52.50,
      "balls_per_boundary": 9.55
    },
    ...
  ]
}
```

#### `GET /api/v1/bowlers/{person_id}/by-phase`

Same as by-over but grouped into powerplay / middle / death.

#### `GET /api/v1/bowlers/{person_id}/by-season`

Season-by-season bowling record.

#### `GET /api/v1/bowlers/{person_id}/wickets`

Wicket analysis.

Query params: global filters + `team`, `opponent`, `batter_id`

```json
{
  "total_wickets": 318,
  "by_kind": {
    "caught": 145,
    "bowled": 82,
    "lbw": 48,
    "caught and bowled": 20,
    "stumped": 15,
    "hit wicket": 8
  },
  "by_phase": {
    "powerplay": 65,
    "middle": 120,
    "death": 133
  },
  "by_over": [
    { "over_number": 0, "wickets": 18 },
    ...
  ],
  "top_victims": [
    { "batter_id": "xxx", "batter_name": "AB de Villiers", "dismissals": 5, "kinds": {"caught": 3, "bowled": 2} },
    ...
  ]
}
```

---

### 3.4 Head-to-Head

#### `GET /api/v1/head-to-head/{batter_id}/{bowler_id}`

Complete head-to-head analysis between a specific batter and bowler.

Query params: global filters

```json
{
  "batter": { "id": "c4487b84", "name": "V Kohli" },
  "bowler": { "id": "462411b3", "name": "JJ Bumrah" },
  "summary": {
    "balls": 82,
    "runs": 74,
    "dismissals": 4,
    "average": 18.50,
    "strike_rate": 90.24,
    "fours": 6,
    "sixes": 2,
    "dots": 42,
    "dot_pct": 51.2,
    "balls_per_boundary": 10.25
  },
  "dismissal_kinds": { "caught": 2, "bowled": 1, "lbw": 1 },
  "by_over": [
    { "over_number": 0, "balls": 8, "runs": 5, "wickets": 0 },
    ...
  ],
  "by_phase": [
    { "phase": "powerplay", "balls": 22, "runs": 18, "wickets": 1, "strike_rate": 81.82 },
    ...
  ],
  "by_season": [
    { "season": "2024", "balls": 14, "runs": 12, "wickets": 1, "strike_rate": 85.71 },
    ...
  ],
  "by_match": [
    {
      "match_id": 789,
      "date": "2024-04-12",
      "tournament": "Indian Premier League",
      "venue": "Wankhede Stadium",
      "balls": 8,
      "runs": 6,
      "fours": 1,
      "sixes": 0,
      "dismissed": true,
      "how_out": "caught"
    },
    ...
  ]
}
```

**SQL (summary):**
```sql
SELECT
    COUNT(*) as balls,
    SUM(d.runs_batter) as runs,
    SUM(CASE WHEN d.runs_batter = 4
             AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN d.runs_batter = 0 AND d.runs_extras = 0 THEN 1 ELSE 0 END) as dots
FROM delivery d
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.batter_id = :batter_id
  AND d.bowler_id = :bowler_id
  AND d.extras_wides = 0 AND d.extras_noballs = 0
  AND i.super_over = 0
  {filter_clauses}
```

---

### 3.6 Matches & Scorecards

A new endpoint family backing the Matches tab. Two endpoints: a paginated
match list (with the standard global filters plus optional team and
player filters) and a full Cricinfo-style scorecard for one match.

#### `GET /api/v1/matches`

List matches matching the filters. Used by the Matches page list view.

Query params: global filters + `team` (optional, name) + `player_id`
(optional, person.id) + `limit` (default 50, max 200) + `offset`.

```json
{
  "matches": [
    {
      "match_id": 1234567,
      "date": "2024-05-26",
      "team1": "Mumbai Indians",
      "team2": "Chennai Super Kings",
      "venue": "Wankhede Stadium",
      "city": "Mumbai",
      "tournament": "Indian Premier League",
      "season": "2024",
      "winner": "Mumbai Indians",
      "result_text": "Mumbai Indians won by 5 wickets",
      "team1_score": "187/4 (20)",
      "team2_score": "184/9 (20)"
    },
    ...
  ],
  "total": 1234
}
```

The two `*_score` summary strings come from a per-innings rollup
(`SUM(runs_total)`, wicket count, max over) — same logic the scorecard
endpoint uses, just truncated to one line per innings.

**Filter logic:**
- Global filters (gender, team_type, tournament, season range) apply
  to `match` columns directly.
- `team` → `(m.team1 = :team OR m.team2 = :team)`.
- `player_id` → `EXISTS (SELECT 1 FROM matchplayer mp WHERE
  mp.match_id = m.id AND mp.person_id = :player_id)`.

**SQL (sketch):**
```sql
SELECT m.id as match_id, ..., m.team1, m.team2, m.venue, m.city,
       m.event_name as tournament, m.season,
       m.outcome_winner as winner,
       (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) as date
FROM match m
WHERE 1=1
  {global_filter_clauses}
  {team_clause}
  {player_exists_clause}
ORDER BY date DESC
LIMIT :limit OFFSET :offset
```

After fetching match rows, a second pass aggregates the two innings
totals per match (one query, `IN (...)` over the page's match_ids) and
attaches them as `team1_score` / `team2_score`. The result line is
built in Python from `outcome_winner`, `outcome_by_runs`,
`outcome_by_wickets`, `outcome_result`, `outcome_method`,
`outcome_eliminator`, `outcome_bowl_out`.

#### `GET /api/v1/matches/{match_id}/scorecard`

Return everything needed to render a full scorecard for one match.

```json
{
  "info": {
    "match_id": 1234567,
    "teams": ["Mumbai Indians", "Chennai Super Kings"],
    "venue": "Wankhede Stadium",
    "city": "Mumbai",
    "dates": ["2024-05-26"],
    "tournament": "Indian Premier League",
    "season": "2024",
    "match_number": 70,
    "stage": "Final",
    "toss_winner": "Chennai Super Kings",
    "toss_decision": "field",
    "result_text": "Mumbai Indians won by 5 wickets",
    "method": null,
    "player_of_match": ["JJ Bumrah"],
    "officials": { "umpires": [...], "tv_umpires": [...], "match_referees": [...] }
  },
  "innings": [
    {
      "innings_number": 0,
      "team": "Chennai Super Kings",
      "is_super_over": false,
      "label": "Chennai Super Kings Innings",
      "total_runs": 184,
      "wickets": 9,
      "overs": "20.0",
      "run_rate": 9.20,
      "batting": [
        {
          "person_id": "abc123",
          "name": "RD Gaikwad",
          "dismissal": "c Rohit b Bumrah",
          "runs": 53,
          "balls": 38,
          "fours": 5,
          "sixes": 2,
          "strike_rate": 139.47
        },
        ...
      ],
      "did_not_bat": ["MM Ali", "DL Chahar"],
      "extras": { "byes": 0, "legbyes": 4, "wides": 6, "noballs": 1, "penalty": 0, "total": 11 },
      "fall_of_wickets": [
        { "wicket": 1, "score": 23, "batter": "RD Gaikwad", "over_ball": "2.4", "team_runs": 23 },
        ...
      ],
      "bowling": [
        {
          "person_id": "def456",
          "name": "JJ Bumrah",
          "overs": "4.0",
          "maidens": 1,
          "runs": 18,
          "wickets": 3,
          "econ": 4.50,
          "wides": 0,
          "noballs": 0
        },
        ...
      ]
    },
    ... (innings 2)
    ... (super over innings if any, with is_super_over=true and label "Super Over (Team)")
  ]
}
```

**Per-innings SQL building blocks:**

*Total + overs + wickets:*
```sql
SELECT SUM(d.runs_total) as total,
       MAX(d.over_number) + 1 as max_over_index,  -- 0-indexed in DB
       (SELECT COUNT(*) FROM wicket w
        JOIN delivery dd ON dd.id = w.delivery_id
        WHERE dd.innings_id = :innings_id) as wickets
FROM delivery d
WHERE d.innings_id = :innings_id
```
The displayed "overs" is computed in Python from total legal balls
(`COUNT(*) WHERE extras_wides=0 AND extras_noballs=0`) → `f"{balls//6}.{balls%6}"`.

*Batting rows:* group by `batter_id`, joined to person for the name,
left-joined to wicket-of-the-batter for the dismissal:
```sql
SELECT
    d.batter_id, d.batter,
    SUM(d.runs_batter) as runs,
    SUM(CASE WHEN d.extras_wides = 0 THEN 1 ELSE 0 END) as balls,
    SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    MIN(d.id) as first_delivery_id  -- for batting order
FROM delivery d
WHERE d.innings_id = :innings_id
GROUP BY d.batter_id, d.batter
ORDER BY first_delivery_id
```
Then for each batter, look up the dismissal:
```sql
SELECT w.kind, w.fielders, dd.bowler
FROM wicket w
JOIN delivery dd ON dd.id = w.delivery_id
WHERE dd.innings_id = :innings_id
  AND w.player_out = :batter_name
LIMIT 1
```
Dismissal text is constructed in Python:
- `bowled` → "b {bowler}"
- `caught` → "c {fielder} b {bowler}" (or "c & b {bowler}" if fielder == bowler)
- `lbw` → "lbw b {bowler}"
- `stumped` → "st {fielder} b {bowler}"
- `run out` → "run out ({fielders})"
- `caught and bowled` → "c & b {bowler}"
- `hit wicket` → "hit wicket b {bowler}"
- `retired hurt` / `retired out` → as-is
- `obstructing the field` → "obstructing the field"
- not dismissed → `"not out"`

*Did not bat:* `matchplayer.player_name` for the batting team, minus
every name that appeared as `delivery.batter` or `delivery.non_striker`
in this innings.

*Extras totals:*
```sql
SELECT SUM(extras_byes) b, SUM(extras_legbyes) lb,
       SUM(extras_wides) w, SUM(extras_noballs) nb,
       SUM(extras_penalty) p
FROM delivery WHERE innings_id = :innings_id
```

*Fall of wickets:* one row per wicket, in delivery order, with
running team total (computed in Python over the deliveries in order):
```sql
SELECT w.player_out, dd.over_number, dd.delivery_index, dd.id as delivery_id
FROM wicket w JOIN delivery dd ON dd.id = w.delivery_id
WHERE dd.innings_id = :innings_id
ORDER BY dd.id
```
Combined with a cumulative running total over `delivery.runs_total`.

*Bowling rows:* group by `bowler_id`. Wickets exclude `run out`,
`retired hurt`, `retired out`, `obstructing the field`. Maidens
computed via subquery grouped by `(bowler_id, over_number)` where
`SUM(runs_batter + extras_wides + extras_noballs) = 0`:
```sql
SELECT
    d.bowler_id, d.bowler,
    SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) as legal_balls,
    SUM(d.runs_total) as runs,  -- bowling runs include all deliveries
    SUM(d.extras_wides) as wides,
    SUM(d.extras_noballs) as noballs,
    (SELECT COUNT(*) FROM wicket w
     JOIN delivery dd ON dd.id = w.delivery_id
     WHERE dd.innings_id = :innings_id
       AND dd.bowler_id = d.bowler_id
       AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')) as wickets,
    (SELECT COUNT(*) FROM (
        SELECT 1 FROM delivery dm
        WHERE dm.innings_id = :innings_id AND dm.bowler_id = d.bowler_id
        GROUP BY dm.over_number
        HAVING SUM(dm.runs_batter + dm.extras_wides + dm.extras_noballs) = 0
    )) as maidens,
    MIN(d.id) as first_delivery_id
FROM delivery d
WHERE d.innings_id = :innings_id
GROUP BY d.bowler_id, d.bowler
ORDER BY first_delivery_id
```
Overs displayed as `f"{legal_balls//6}.{legal_balls%6}"`. Econ is
`runs / (legal_balls/6)`.

#### Decisions captured

These choices were agreed up front and govern the implementation:

1. **Same-page list + scorecard**, with the selected match on a URL
   query param (`?match=1234567`) so links are shareable. No separate
   route.
2. **Single-player filter** (not multi-player intersection). 95% of
   the use case is "show me Kohli's matches"; multi-player can be
   added later if needed.
3. **Super overs** are returned as additional `innings` entries with
   `is_super_over: true` and a label like `"Super Over (Mumbai Indians)"`.
4. **DLS / rain-affected matches**: `outcome_method` is shown in the
   result line if present (e.g. "Mumbai Indians won by 12 runs (D/L)").
   No further special-casing.

---

## 4. Frontend Pages

### 4.1 Navigation

Top nav bar with:
- **Teams** — team results, head-to-head
- **Batting** — batter profiles, matchups
- **Bowling** — bowler profiles, matchups
- **Head to Head** — batter vs bowler deep dive

Global filter bar (sticky, below nav):
- Gender toggle (Male / Female / All)
- Team Type toggle (International / Club / All)
- Tournament dropdown (populated from `/api/v1/tournaments`)
- Season range (two dropdowns, from `/api/v1/seasons`)

Filters sync to URL query params so pages are shareable/bookmarkable.

### 4.2 Page: Teams (`/teams`)

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [Team Search / Dropdown]                            │
├──────────────────────────────────────────────────────┤
│  Team Summary Card                                   │
│  ┌─────────┬─────────┬─────────┬─────────┐          │
│  │ Matches │  Wins   │ Losses  │ Win %   │          │
│  │   230   │   155   │   65    │  67.4%  │          │
│  └─────────┴─────────┴─────────┴─────────┘          │
├──────────────────────────────────────────────────────┤
│  Tabs: [By Season] [vs Opponent] [Match List]        │
├──────────────────────────────────────────────────────┤
│  [By Season tab]                                     │
│  ┌──────────────────────────────────────────────┐    │
│  │  Bar chart: wins/losses by season             │    │
│  │  (OrdinalFrame, stacked bars, green/red)      │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [vs Opponent tab]                                   │
│  [Opponent Dropdown] ────────────────────────        │
│  ┌──────────────────────────────────────────────┐    │
│  │  Head-to-head record summary                  │    │
│  │  Timeline: result per match (XYFrame dots)    │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [Match List tab]                                    │
│  Table: date, opponent, venue, result, margin        │
│  Sortable columns, paginated                         │
└──────────────────────────────────────────────────────┘
```

**Data flow:**
1. User selects team → `GET /api/v1/teams/{team}/summary`
2. By Season tab → `GET /api/v1/teams/{team}/by-season`
3. vs Opponent tab → user selects opponent → `GET /api/v1/teams/{team}/vs/{opponent}`
4. Match List tab → `GET /api/v1/teams/{team}/results`

### 4.3 Page: Batting (`/batting`)

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [Player Search Autocomplete]                        │
│  (hits /api/v1/players?role=batter&q=...)            │
├──────────────────────────────────────────────────────┤
│  Player Header: Name, Teams Played For               │
├──────────────────────────────────────────────────────┤
│  Summary Cards Row                                   │
│  ┌───────┬────────┬──────┬─────────┬───────────┐    │
│  │ Runs  │  Avg   │  SR  │ Innings │ Boundaries│    │
│  │ 4038  │ 20.92  │130.2 │  245    │    464    │    │
│  └───────┴────────┴──────┴─────────┴───────────┘    │
│  ┌───────┬────────┬──────┬─────────┬───────────┐    │
│  │B/Four │ B/Six  │B/Bnd │ Dot %   │  50s/100s │    │
│  │ 8.81  │ 27.70  │ 6.69 │ 38.8%   │  38 / 1   │    │
│  └───────┴────────┴──────┴─────────┴───────────┘    │
├──────────────────────────────────────────────────────┤
│  Tabs: [By Season] [By Over] [By Phase]              │
│        [vs Bowlers] [Dismissals] [Inter-Wicket]      │
│        [Innings List]                                │
├──────────────────────────────────────────────────────┤
│  [By Season]                                         │
│  ┌──────────────────────────────────────────────┐    │
│  │  Dual-axis chart: runs (bars) + SR (line)     │    │
│  │  (XYFrame with OrdinalFrame overlay)          │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [By Over]                                           │
│  ┌──────────────────────────────────────────────┐    │
│  │  Bar: strike rate by over 0-19                │    │
│  │  Color: powerplay=blue, middle=green,         │    │
│  │         death=red                             │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [vs Bowlers]                                        │
│  Optional: [Bowler filter dropdown]                  │
│  ┌──────────────────────────────────────────────┐    │
│  │  Scatter: SR (x) vs Average (y) per bowler    │    │
│  │  Dot size = balls faced                       │    │
│  │  Hover: bowler name, stats                    │    │
│  └──────────────────────────────────────────────┘    │
│  Table: bowler matchups, sortable                    │
│                                                      │
│  [Dismissals]                                        │
│  ┌──────────────────────────────────────────────┐    │
│  │  Donut: dismissal types                       │    │
│  │  Bar: dismissals by over                      │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [Inter-Wicket]                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  Line: SR by wickets-down (0..9)              │    │
│  │  Bar: avg runs per wicket phase               │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  [Innings List]                                      │
│  Table: date, opponent, runs, balls, SR, how out     │
│  Sortable, paginated                                 │
└──────────────────────────────────────────────────────┘
```

**Additional context filter on batting page:**
- Team dropdown (which team the batter played for — useful for IPL players)
- Opponent dropdown

### 4.4 Page: Bowling (`/bowling`)

**Layout:** Mirrors batting page structure.

```
┌──────────────────────────────────────────────────────┐
│  [Player Search Autocomplete]                        │
│  (hits /api/v1/players?role=bowler&q=...)             │
├──────────────────────────────────────────────────────┤
│  Player Header: Name, Teams                          │
├──────────────────────────────────────────────────────┤
│  Summary Cards Row                                   │
│  ┌───────┬────────┬──────┬─────────┬───────────┐    │
│  │Wickets│  Avg   │ Econ │ Overs   │    SR     │    │
│  │  318  │ 13.20  │ 7.75 │  541.2  │  10.21   │    │
│  └───────┴────────┴──────┴─────────┴───────────┘    │
│  ┌───────┬────────┬──────┬─────────┬───────────┐    │
│  │B/Four │ B/Six  │B/Bnd │ Dot %   │Best Figs  │    │
│  │ 8.55  │ 29.00  │ 6.60 │ 51.7%   │  4/14    │    │
│  └───────┴────────┴──────┴─────────┴───────────┘    │
├──────────────────────────────────────────────────────┤
│  Tabs: [By Season] [By Over] [By Phase]              │
│        [vs Batters] [Wickets] [Innings List]         │
├──────────────────────────────────────────────────────┤
│  [By Season]                                         │
│  Dual axis: wickets (bars) + economy (line)          │
│                                                      │
│  [By Over]                                           │
│  Bar: economy by over 0-19, colored by phase         │
│                                                      │
│  [vs Batters]                                        │
│  Scatter: economy (x) vs SR (y) per batter           │
│  Dot size = balls bowled                              │
│  Table: batter matchups, sortable                    │
│                                                      │
│  [Wickets]                                           │
│  Donut: wicket types                                 │
│  Bar: wickets by phase                               │
│  Table: top victims                                  │
│                                                      │
│  [Innings List]                                      │
│  Table: date, opponent, overs, runs, wickets, econ   │
└──────────────────────────────────────────────────────┘
```

### 4.5 Page: Head to Head (`/head-to-head`)

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [Batter Search]          vs    [Bowler Search]      │
├──────────────────────────────────────────────────────┤
│  Matchup Summary                                     │
│  ┌───────┬────────┬──────┬─────────┬───────────┐    │
│  │ Balls │  Runs  │ Outs │  Avg    │    SR     │    │
│  │  82   │   74   │   4  │ 18.50   │  90.24   │    │
│  └───────┴────────┴──────┴─────────┴───────────┘    │
│  ┌───────┬────────┬──────┬─────────┐                │
│  │ Fours │ Sixes  │ Dots │ Dot %   │                │
│  │   6   │   2    │  42  │ 51.2%   │                │
│  └───────┴────────┴──────┴─────────┘                │
├──────────────────────────────────────────────────────┤
│  Left Col                    Right Col               │
│  ┌─────────────────────┐    ┌─────────────────────┐  │
│  │ By Phase (3 bars)   │    │ Dismissal types     │  │
│  │ SR per phase        │    │ (donut chart)       │  │
│  └─────────────────────┘    └─────────────────────┘  │
│  ┌──────────────────────────────────────────────┐    │
│  │ By Season line chart: SR + runs over time     │    │
│  └──────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────┐    │
│  │ By Over heatmap: runs per over (0-19)         │    │
│  └──────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────┤
│  Match-by-match table                                │
│  date, tournament, venue, balls, runs, 4s, 6s, out   │
└──────────────────────────────────────────────────────┘
```

### 4.6 Page: Matches (`/matches`)

A scorecard browser. Combines the global filter bar with a team picker
and a player picker, lists matching matches, and renders a full
Cricinfo-style scorecard for the selected match underneath.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [Global FilterBar]  Men/Women  Intl/Club  Tournament │
│                       Season-from  Season-to          │
├──────────────────────────────────────────────────────┤
│  [Team search: e.g. "SRH"]  [Player search: "Kohli"]  │
├──────────────────────────────────────────────────────┤
│  Match list (paginated, 50/page)                     │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 2024-05-26 | MI vs CSK | Wankhede | IPL Final   │ │
│  │            | MI 187/4 (20)  CSK 184/9 (20)      │ │
│  │            | MI won by 5 wickets                │ │
│  └─────────────────────────────────────────────────┘ │
│  ...                                                 │
├──────────────────────────────────────────────────────┤
│  [Scorecard (when ?match= is set in URL)]            │
│                                                      │
│  Match header                                        │
│  ┌─────────────────────────────────────────────────┐ │
│  │ MI vs CSK · IPL Final · Wankhede · 2024-05-26   │ │
│  │ Toss: CSK chose to field                        │ │
│  │ Result: Mumbai Indians won by 5 wickets          │ │
│  │ Player of the Match: JJ Bumrah                  │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  CSK Innings — 184/9 (20.0)                          │
│  ┌─────────────────────────────────────────────────┐ │
│  │ Batter         Dismissal           R   B  4 6 SR│ │
│  │ Gaikwad        c Rohit b Bumrah    53 38  5 2.. │ │
│  │ ...                                              │ │
│  │ Extras  (b 0, lb 4, w 6, nb 1)               11 │ │
│  │ Total                              184/9 (20.0) │ │
│  │ Did not bat: Ali, Chahar                        │ │
│  │                                                  │ │
│  │ Fall of wickets: 1-23 (Gaikwad, 2.4 ov), ...    │ │
│  │                                                  │ │
│  │ Bowler       O    M  R  W  Econ  wd nb          │ │
│  │ Bumrah       4.0  1 18  3  4.50   0  0          │ │
│  │ ...                                              │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  MI Innings — 187/4 (19.2)                           │
│  ┌─────────────────────────────────────────────────┐ │
│  │ ... same structure ...                          │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  [Super Over innings cards if applicable]            │
└──────────────────────────────────────────────────────┘
```

**URL state:**
- `?team=`, `?player=`, `?match=` (the selected match for the scorecard)
- Standard global filter params

**Data flow:**
1. Filters/team/player change → `GET /api/v1/matches?...&limit=50&offset=...`
   re-fetches the list. Pagination controls underneath.
2. User clicks a match row → set `?match={id}` in URL.
3. `?match=` change → `GET /api/v1/matches/{id}/scorecard` → render
   header + N innings cards.

**Components (new):**
- `pages/Matches.tsx` — page wiring (filters, list fetch, scorecard fetch).
- `components/Scorecard.tsx` — top-level scorecard renderer (header + N innings).
- `components/InningsCard.tsx` — one innings: batting table, extras line,
  total, did-not-bat, fall-of-wickets, bowling table.
- `components/TeamSearch.tsx` — small reusable team-name search input
  (also used elsewhere if needed).

**Reuses:**
- `FilterBar` and `useFilters` (no changes needed).
- `PlayerSearch` for the player filter input.
- `DataTable` for batting/bowling tables (already supports
  sortable columns).
- `useUrlParam` / `useSetUrlParams` for URL state.

---

## 5. Technical Details

### 5.1 Backend Stack

- **FastAPI** — async API framework, colocated with deebase admin
- **deebase** — ORM for model definitions, table creation, admin UI
- **Raw SQL via `db.q()`** — for analytics queries (too complex for ORM)
- **SQLite** — database engine (435MB, single file)

### 5.2 Frontend Stack

- **React 18+** with React Router v6
- **Tailwind CSS** for styling
- **Semiotic** (`semiotic@^2`) for charts
  - `XYFrame` — line charts, scatter plots
  - `OrdinalFrame` — bar charts, stacked bars, pie/donut
  - `NetworkFrame` — future: fielding networks, team graphs
- **Vite** for dev server and build

### 5.3 API-Frontend Contract

- All API responses are JSON
- Frontend calls API with `fetch()`, no state management library needed (React state + useEffect)
- Filter state lives in URL search params — React Router `useSearchParams()`
- Player search is debounced (300ms) autocomplete
- Charts re-render on filter change

### 5.4 Performance Notes

- Query performance tested: full career aggregation for top players runs in <100ms on SQLite with existing indexes
- Indexes exist on: `delivery.innings_id`, `delivery.batter_id`, `delivery.bowler_id`, `wicket.delivery_id`, `wicket.player_out_id`, `innings.match_id`, `match.event_name`, `match.gender`, `match.season`
- Most expensive query: inter-wicket analysis (requires fetching full innings and processing in Python). Still <200ms for a single player.
- The `/api/v1/players` search endpoint should use `LIKE` with prefix matching for speed. Full-text search via deebase FTS is a future optimization.

### 5.5 Project Structure

```
cricsdb/
├── api/
│   ├── app.py              # FastAPI app with admin + custom routers
│   ├── dependencies.py     # get_db() dependency
│   ├── filters.py          # build_filters() helper
│   └── routers/
│       ├── reference.py    # /api/v1/tournaments, /seasons, /teams, /players
│       ├── teams.py        # /api/v1/teams/...
│       ├── batting.py      # /api/v1/batters/...
│       ├── bowling.py      # /api/v1/bowlers/...
│       └── head_to_head.py # /api/v1/head-to-head/...
├── models/
│   ├── __init__.py
│   └── tables.py           # deebase models
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── api.ts           # fetch wrappers
│       ├── types.ts         # TypeScript interfaces matching API responses
│       ├── components/
│       │   ├── Layout.tsx       # nav + global filter bar
│       │   ├── FilterBar.tsx    # global filters (gender, tournament, season)
│       │   ├── PlayerSearch.tsx # autocomplete input
│       │   ├── StatCard.tsx     # single metric display card
│       │   ├── DataTable.tsx    # sortable, paginated table
│       │   └── charts/
│       │       ├── BarChart.tsx       # OrdinalFrame wrapper
│       │       ├── LineChart.tsx      # XYFrame wrapper
│       │       ├── ScatterChart.tsx   # XYFrame wrapper
│       │       ├── DonutChart.tsx     # OrdinalFrame pie wrapper
│       │       └── HeatmapChart.tsx   # OrdinalFrame wrapper
│       └── pages/
│           ├── Teams.tsx
│           ├── Batting.tsx
│           ├── Bowling.tsx
│           └── HeadToHead.tsx
├── cricket.db
├── import_data.py
├── models.py               # original models (also in models/tables.py)
├── main.py                 # plash entry point (production)
├── requirements.txt        # plash dependencies
├── setup.sh                # plash system deps (if needed)
└── SPEC.md
```

---

## 6. Deployment (pla.sh)

### 6.1 Platform Constraints

- **Port:** App must listen on port **5001**
- **Entry point:** `main.py` at project root
- **Dependencies:** `requirements.txt` at project root (cannot use pyproject.toml)
- **Persistent storage:** Only the `data/` directory survives redeployments. Everything else is replaced.
- **System deps:** Optional `setup.sh` for `apt install` commands (runs as root during build)
- **Environment:** `PLASH_PRODUCTION=1` is set automatically in production
- **Backups:** Hourly snapshots of `data/`, retained on a tiered schedule
- **CLI:** `pip install plash-cli` → `plash_login` → `plash_deploy` → `plash_view`

### 6.2 Deployment Architecture

Since `data/` is the only persistent directory, and our SQLite DB is 435MB:

```
Project root (replaced on deploy)      data/ (persisted)
├── main.py                             └── cricket.db
├── requirements.txt
├── api/
├── models/
└── frontend/dist/   (built static)
```

- `cricket.db` lives in `data/` so it persists across deploys
- Frontend is pre-built (`npm run build`) and served as static files by FastAPI
- The import script is a dev-only tool, not deployed

### 6.3 Entry Point (`main.py`)

```python
import os
import uvicorn
from api.app import app

# Plash requires port 5001
if __name__ == "__main__":
    port = 5001 if os.getenv("PLASH_PRODUCTION") == "1" else 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### 6.4 FastAPI Static File Serving

In production, FastAPI serves the built React frontend:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve React build
if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # API routes are already registered with higher priority
        file_path = f"frontend/dist/{path}"
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse("frontend/dist/index.html")
```

### 6.5 Database Path Configuration

```python
DB_DIR = "data" if os.getenv("PLASH_PRODUCTION") == "1" else "."
DB_PATH = os.path.join(DB_DIR, "cricket.db")
db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
```

### 6.6 requirements.txt

```
deebase>=0.6.1
fastapi
uvicorn
```

### 6.7 Deploy Steps

```bash
# 1. Build frontend
cd frontend && npm run build && cd ..

# 2. Ensure cricket.db is in data/ for first deploy
mkdir -p data && cp cricket.db data/cricket.db

# 3. Deploy
plash_deploy
```

After first deploy, `data/cricket.db` persists — no need to re-upload on subsequent deploys unless the schema changes.

### 6.8 Custom Domain (optional)

Edit `.plash` file:
```
PLASH_APP_NAME=cricsdb
```

Or bring your own domain with a CNAME pointing to `pla.sh`.

---

## 7. Implementation Plans

### Overview

Four plans, partially parallelizable:

```
Plan 1: API Backend ─────────┐
                              ├──→ Plan 3: Frontend Pages ──→ Plan 4: Deployment
Plan 2: Frontend Scaffold ───┘
```

Plans 1 and 2 are **independent** and can be worked in parallel.
Plan 3 depends on both 1 and 2.
Plan 4 depends on 3.

---

### Plan 1: API Backend

Build all FastAPI routers with the filter system, wired into the deebase app.

**Step 1.1: Filter helper (`api/filters.py`)**
- `build_filters()` function that takes global + contextual filter params and returns `(where_clause, params_dict)`
- Handles: gender, team_type, tournament, season_from, season_to, team (innings.team), opponent
- Auto-adds `i.super_over = 0` exclusion
- Unit-testable in isolation

**Step 1.2: Database dependency (`api/dependencies.py`)**
- Update to use our cricket.db path (production-aware: `data/cricket.db` vs `./cricket.db`)
- `get_db()` FastAPI dependency
- Initialize deebase `Database` on startup, close on shutdown

**Step 1.3: Reference router (`api/routers/reference.py`)**
- `GET /api/v1/tournaments` — distinct event_name with counts, grouped by team_type/gender
- `GET /api/v1/seasons` — distinct seasons, sorted
- `GET /api/v1/teams` — team list with match counts, filterable by gender/team_type/tournament, searchable by `q`
- `GET /api/v1/players` — player search with `q`, `role` (batter/bowler), returns person_id/name/match count
- All endpoints are simple single-query, good for validating the filter system works

**Step 1.4: Teams router (`api/routers/teams.py`)**
- `GET /api/v1/teams/{team}/summary` — W/L/T/NR record
- `GET /api/v1/teams/{team}/results` — paginated match list
- `GET /api/v1/teams/{team}/vs/{opponent}` — head-to-head with by-season breakdown
- `GET /api/v1/teams/{team}/by-season` — season-by-season W/L record

**Step 1.5: Batting router (`api/routers/batting.py`)**
- `GET /api/v1/batters/{person_id}/summary` — career aggregation (two queries: ball-level + per-innings)
- `GET /api/v1/batters/{person_id}/by-innings` — innings list, paginated/sortable
- `GET /api/v1/batters/{person_id}/vs-bowlers` — grouped by bowler_id, with min_balls threshold
- `GET /api/v1/batters/{person_id}/by-over` — grouped by over_number
- `GET /api/v1/batters/{person_id}/by-phase` — grouped by powerplay/middle/death
- `GET /api/v1/batters/{person_id}/by-season` — grouped by season
- `GET /api/v1/batters/{person_id}/dismissals` — wicket kind/phase/over/top-bowler breakdown
- `GET /api/v1/batters/{person_id}/inter-wicket` — Python-side processing of wickets-down phases

**Step 1.6: Bowling router (`api/routers/bowling.py`)**
- Mirrors batting structure: summary, by-innings, vs-batters, by-over, by-phase, by-season, wickets
- Key difference: runs_conceded counts ALL deliveries (incl. wides/noballs), balls counts only legal
- Wicket counting excludes run outs, retired hurt/out

**Step 1.7: Head-to-head router (`api/routers/head_to_head.py`)**
- Single compound endpoint: `GET /api/v1/head-to-head/{batter_id}/{bowler_id}`
- Combines: summary stats, dismissal types, by-over, by-phase, by-season, by-match
- Multiple queries composed into one response

**Step 1.8: Wire into app.py**
- Register all routers with `/api/v1` prefix
- Ensure admin UI still works at `/admin/`
- Add CORS middleware for frontend dev server
- Test all endpoints manually with curl / httpie

**Deliverable:** All 18+ API endpoints working, testable at `http://localhost:8000/api/v1/...`, colocated with deebase admin at `/admin/`.

---

### Plan 2: Frontend Scaffold

Set up the React project with shared components, ready for page-specific work.

**Step 2.1: Project initialization**
- `npm create vite@latest frontend -- --template react-ts`
- Install: `tailwindcss`, `@tailwindcss/vite`, `react-router-dom`, `semiotic`
- Configure Vite proxy: `/api` → `http://localhost:8000`
- Tailwind config with cricket-themed color palette

**Step 2.2: TypeScript types (`src/types.ts`)**
- Interfaces matching every API response shape from the spec
- Shared types: `FilterParams`, `PaginationParams`, `PlayerRef`, `MatchResult`

**Step 2.3: API client (`src/api.ts`)**
- `fetchApi<T>(path, params)` generic wrapper with error handling
- One function per endpoint group: `fetchBatterSummary()`, `fetchTeams()`, etc.
- Handles query param serialization from filter state

**Step 2.4: Layout and navigation (`src/components/Layout.tsx`)**
- Top nav: Teams | Batting | Bowling | Head to Head
- Active route highlighting with React Router
- Responsive (hamburger menu on mobile)

**Step 2.5: Global filter bar (`src/components/FilterBar.tsx`)**
- Gender toggle (Male / Female / All)
- Team Type toggle (International / Club / All)
- Tournament dropdown — fetches from `/api/v1/tournaments`, filters by selected team_type
- Season range — two dropdowns (From / To), fetches from `/api/v1/seasons`
- State syncs to URL search params via `useSearchParams()`
- `useFilters()` custom hook that reads URL params and returns `FilterParams` object

**Step 2.6: Player search (`src/components/PlayerSearch.tsx`)**
- Debounced (300ms) autocomplete input
- Hits `/api/v1/players?q=...&role=batter` or `role=bowler`
- Dropdown shows name + match count
- On select, navigates to `/batting/{id}` or `/bowling/{id}`
- Used on Batting, Bowling, and Head-to-Head pages

**Step 2.7: Stat card (`src/components/StatCard.tsx`)**
- Displays: label, value, optional subtitle (e.g. "runs", "4038", "in 245 innings")
- Tailwind: rounded card with subtle border, large value, small label
- Grid-friendly (used in rows of 5)

**Step 2.8: Data table (`src/components/DataTable.tsx`)**
- Column definitions: key, label, sortable?, format function
- Client-side sorting by clicking column headers
- Pagination controls (previous / next / page N of M)
- Calls parent's onSort/onPage callbacks for server-side sort/pagination

**Step 2.9: Chart wrappers (`src/components/charts/`)**
- `BarChart.tsx` — wraps semiotic `OrdinalFrame` for bar/stacked bar charts
  - Props: data, oColumn, rColumn, colors, title, xLabel, yLabel
- `LineChart.tsx` — wraps semiotic `XYFrame` for line/multi-line charts
  - Props: lines (array of series), xAccessor, yAccessor, title
- `ScatterChart.tsx` — wraps semiotic `XYFrame` for scatter plots
  - Props: points, xAccessor, yAccessor, sizeAccessor, hoverContent
- `DonutChart.tsx` — wraps semiotic `OrdinalFrame` with `type="bar"` + `projection="radial"`
  - Props: data, oColumn, rColumn, colors
- `HeatmapChart.tsx` — wraps semiotic `OrdinalFrame` for over-by-over heatmaps
  - Props: data, columns, rows, valueAccessor, colorScale
- All charts: responsive width, consistent Tailwind-compatible styling, loading state

**Step 2.10: App shell and routing (`src/App.tsx`)**
- React Router setup: `/teams`, `/batting`, `/batting/:personId`, `/bowling`, `/bowling/:personId`, `/head-to-head`
- Default redirect to `/teams`
- Wrap all routes in `<Layout>` with filter bar
- Placeholder pages (just titles) for each route

**Deliverable:** Running frontend at `http://localhost:5173` with nav, filters, search, and empty page shells. All shared components built and ready for page integration.

---

### Plan 3: Frontend Pages

Build each page using the scaffold components and API endpoints.

**Step 3.1: Teams page**
- Team search/dropdown at top
- Summary card row (matches, wins, losses, win %)
- Three tabs:
  - **By Season:** stacked bar chart (wins green, losses red) using BarChart
  - **vs Opponent:** opponent dropdown → head-to-head summary + timeline dots using ScatterChart
  - **Match List:** DataTable with date, opponent, venue, result, margin columns

**Step 3.2: Batting page**
- Player search at top → loads `/api/v1/batters/{id}/summary`
- Summary card row (10 stat cards: runs, avg, SR, innings, boundaries, B/4, B/6, B/boundary, dot%, 50s/100s)
- Seven tabs:
  - **By Season:** dual-axis bar+line (runs bars + SR line) using BarChart + LineChart overlay
  - **By Over:** bar chart of SR by over 0-19, colored by phase, using BarChart
  - **By Phase:** 3 bars (powerplay/middle/death) with SR + runs, using BarChart
  - **vs Bowlers:** scatter plot (SR vs avg, sized by balls) + sortable DataTable
  - **Dismissals:** donut chart of types + bar chart of dismissals by over
  - **Inter-Wicket:** line chart of SR by wickets-down + bar chart of avg runs per phase
  - **Innings List:** sortable/paginated DataTable

**Step 3.3: Bowling page**
- Same structure as batting, swapping metrics:
  - Summary: wickets, avg, economy, overs, SR, B/4, B/6, B/boundary, dot%, best figures
  - By Season: wickets bars + economy line
  - By Over: economy by over, colored by phase
  - vs Batters: scatter (economy vs SR) + table
  - Wickets: donut of types + bar by phase + top victims table
  - Innings List: overs, runs, wickets, economy

**Step 3.4: Head-to-Head page**
- Two player search inputs (batter + bowler)
- Summary card row
- 2-column layout: phase bars (left) + dismissal donut (right)
- By Season line chart (SR over time)
- By Over heatmap
- Match-by-match DataTable

**Step 3.5: Cross-page navigation**
- Clicking a bowler name in batting vs-bowlers tab → navigates to `/head-to-head?batter={id}&bowler={id}`
- Clicking a batter name in bowling vs-batters tab → same
- Clicking a player name anywhere → navigates to their batting or bowling page
- Team names in match lists → navigates to `/teams?team={name}`

**Deliverable:** Fully functional 4-page app with charts, tables, filters, and cross-navigation.

---

### Plan 4: Deployment to pla.sh

**Step 4.1: Production entry point**
- Create `main.py` at project root (plash entry point)
- Imports and runs the FastAPI app on port 5001
- Detects `PLASH_PRODUCTION` env var for production vs dev mode

**Step 4.2: Database path handling**
- Update `api/dependencies.py` to use `data/cricket.db` in production, `./cricket.db` in dev
- Ensure `data/` directory exists on first deploy

**Step 4.3: Static file serving**
- Build frontend: `cd frontend && npm run build`
- FastAPI mounts `frontend/dist/` as static files
- SPA fallback: all non-API, non-admin routes serve `index.html`
- API routes (`/api/v1/...`) and admin (`/admin/`) take priority over static fallback

**Step 4.4: Requirements and dependencies**
- Create `requirements.txt` at project root: `deebase>=0.6.1`, `fastapi`, `uvicorn`
- If node/npm needed at build time: add `setup.sh` with `apt install -y nodejs npm`
- Alternative: pre-build frontend locally, commit `frontend/dist/` to deploy

**Step 4.5: Initial deployment**
```bash
# Build frontend
cd frontend && npm run build && cd ..

# Copy DB to persistent data dir
mkdir -p data
cp cricket.db data/cricket.db

# Login and deploy
plash_login
plash_deploy

# View
plash_view
```

**Step 4.6: Verify**
- Check `/admin/` loads the deebase admin
- Check `/api/v1/tournaments` returns data
- Check `/` loads the React frontend
- Check filters and charts work end-to-end

**Step 4.7: Custom domain (optional)**
- Edit `.plash` → `PLASH_APP_NAME=cricsdb`
- Or configure CNAME for custom domain → `pla.sh`
- Redeploy

**Deliverable:** Live app at `https://cricsdb.pla.sh` (or custom domain) with API, admin, and frontend all served from one process on port 5001.
