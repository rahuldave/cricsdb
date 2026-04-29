-- Ground-truth SQL for tests/integration/dom/series_overview_intl.sh.
--
-- Closed window: T20 World Cup Men 2024 dossier. Asserts the Series
-- Overview tab's default-landing StatCard grid.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_overview_intl.sql

.mode column
.headers on

-- SO1: Total T20 WC 2024 matches.
SELECT 'SO1 T20 WC 2024 matches' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.event_name = 'ICC Men''s T20 World Cup'
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season = '2024';

-- SO2: T20 WC 2024 total runs + legal balls + run rate (concat).
SELECT 'SO2 T20 WC 2024 RR' AS lbl,
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
  AND  m.event_name = 'ICC Men''s T20 World Cup'
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season = '2024';

-- SO3: T20 WC 2024 total boundaries (4s using non_boundary flag,
-- 6s straight count).
SELECT 'SO3 T20 WC 2024 4s+6s' AS lbl,
       SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0
                THEN 1 ELSE 0 END) AS fours,
       SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  m.event_name = 'ICC Men''s T20 World Cup'
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season = '2024';

-- Expected:
--   SO1 = 44
--   SO2 = total_runs:11073, RR:7.13
--   SO3 = 4s:814, 6s:454
