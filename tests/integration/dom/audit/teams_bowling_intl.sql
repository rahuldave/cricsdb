-- Ground-truth SQL for tests/integration/dom/teams_bowling_intl.sh.
--
-- Closed window: Australia, men's T20I 2024-2025. Foundational
-- numbers for the Bowling tab StatCard grid. Bowling counts
-- against the OPPONENT's batting innings (team is on the field).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_bowling_intl.sql

.mode column
.headers on

-- BO1: Aus innings_bowled = innings where Aus is on the field.
SELECT 'BO1 Aus innings_bowled' AS lbl, COUNT(*) AS innings
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Australia'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- BO2: Aus runs_conceded + legal_balls + wickets.
-- runs_conceded counts ALL deliveries (incl. wides + noballs); legal_balls
-- excludes them. Wickets exclude run out / retired hurt / retired out /
-- obstructing the field (CLAUDE.md "Bowler wickets:").
SELECT 'BO2 Aus runs/balls/wkts' AS lbl,
       SUM(d.runs_total) AS runs_conceded,
       SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                THEN 1 ELSE 0 END) AS legal_balls,
       (SELECT COUNT(*) FROM wicket w
        JOIN delivery d2 ON d2.id = w.delivery_id
        JOIN innings i2 ON i2.id = d2.innings_id
        JOIN match m2 ON m2.id = i2.match_id
        WHERE w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')
          AND i2.super_over = 0 AND i2.team != 'Australia'
          AND ('Australia' IN (m2.team1, m2.team2))
          AND m2.gender = 'male' AND m2.team_type = 'international'
          AND m2.season BETWEEN '2024' AND '2025'
       ) AS wickets
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Australia'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- BO3: Derived rates from BO2:
--   economy = runs_conceded × 6 / legal_balls = 3477 × 6 / 2500 = 8.34
--   strike_rate = legal_balls / wickets       = 2500 / 173 = 14.45
--   average = runs_conceded / wickets          = 3477 / 173 = 20.10
--   overs (display) = legal_balls / 6          = 2500 / 6   = 416.7

-- Expected:
--   BO1 = 22
--   BO2 = runs:3477, legal_balls:2500, wickets:173
