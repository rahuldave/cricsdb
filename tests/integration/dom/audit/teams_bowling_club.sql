-- Ground-truth SQL for tests/integration/dom/teams_bowling_club.sh.
--
-- Closed window: Royal Challengers Bengaluru, IPL 2025. Same shape
-- as audit/teams_bowling_intl.sql.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_bowling_club.sql

.mode column
.headers on

-- BO1: RCB innings_bowled in IPL 2025.
SELECT 'BO1 RCB innings_bowled' AS lbl, COUNT(*) AS innings
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Royal Challengers Bengaluru'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- BO2: RCB runs_conceded + legal_balls + wickets.
SELECT 'BO2 RCB runs/balls/wkts' AS lbl,
       SUM(d.runs_total) AS runs_conceded,
       SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                THEN 1 ELSE 0 END) AS legal_balls,
       (SELECT COUNT(*) FROM wicket w
        JOIN delivery d2 ON d2.id = w.delivery_id
        JOIN innings i2 ON i2.id = d2.innings_id
        JOIN match m2 ON m2.id = i2.match_id
        WHERE w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field')
          AND i2.super_over = 0 AND i2.team != 'Royal Challengers Bengaluru'
          AND ('Royal Challengers Bengaluru' IN (m2.team1, m2.team2))
          AND m2.gender = 'male' AND m2.team_type = 'club'
          AND m2.event_name = 'Indian Premier League'
          AND m2.season = '2025'
       ) AS wickets
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Royal Challengers Bengaluru'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- Expected:
--   BO1 = 15
--   BO2 = runs:2606, legal_balls:1692, wickets:91
--   Derived:
--     economy = 2606 × 6 / 1692 = 9.24
--     strike_rate = 1692 / 91 = 18.59
--     average = 2606 / 91 = 28.64
--     overs = 1692 / 6 = 282.0
