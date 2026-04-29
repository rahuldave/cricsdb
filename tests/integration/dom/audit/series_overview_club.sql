-- Ground-truth SQL for tests/integration/dom/series_overview_club.sh.
--
-- Closed window: IPL 2025 (74 matches).
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_overview_club.sql

.mode column
.headers on

SELECT 'SO1 IPL 2025 matches' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.event_name = 'Indian Premier League'
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.season = '2025';

SELECT 'SO2 IPL 2025 RR' AS lbl,
       SUM(d.runs_total) AS total_runs,
       SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                THEN 1 ELSE 0 END) AS legal_balls,
       ROUND(SUM(d.runs_total) * 6.0 /
             SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                      THEN 1 ELSE 0 END), 2) AS run_rate
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  m.event_name = 'Indian Premier League'
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.season = '2025';

SELECT 'SO3 IPL 2025 4s+6s' AS lbl,
       SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0
                THEN 1 ELSE 0 END) AS fours,
       SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  m.event_name = 'Indian Premier League'
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.season = '2025';

-- Expected:
--   SO1 = 74; SO2 = total_runs:?, RR:9.63 (or 9.64); SO3 = 4s:2257, 6s:1301
