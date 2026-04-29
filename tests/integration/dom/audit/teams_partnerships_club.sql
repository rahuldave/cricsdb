-- Ground-truth SQL for tests/integration/dom/teams_partnerships_club.sh.
--
-- Closed window: Royal Challengers Bengaluru, IPL 2025, batting side.
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_partnerships_club.sql

.mode column
.headers on

SELECT 'P1 wkt 1' AS lbl,
       COUNT(*) AS n,
       ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
       MAX(p.partnership_runs) AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  p.wicket_number = 1
  AND  i.team = 'Royal Challengers Bengaluru'
  AND  i.super_over = 0
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season = '2025';

SELECT 'P1 wkt 10' AS lbl,
       COUNT(*) AS n,
       ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
       MAX(p.partnership_runs) AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  p.wicket_number = 10
  AND  i.team = 'Royal Challengers Bengaluru'
  AND  i.super_over = 0
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season = '2025';

-- Expected:
--   P1 wkt 1: n=15, avg_runs=45.5, best=97
--   P1 wkt 10: n=1, avg_runs=2.0, best=2
