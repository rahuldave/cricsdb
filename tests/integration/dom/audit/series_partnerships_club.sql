-- Ground-truth SQL for tests/integration/dom/series_partnerships_club.sh.
--
-- Closed window: Indian Premier League 2025.
--
-- Two endpoints back the Partnerships tab:
--   /api/v1/series/partnerships/by-wicket  → Table 0 (10-row grid)
--     Excludes wicket_number IS NULL and retired-hurt/retired-not-out.
--   /api/v1/series/partnerships/top         → Table 1 (top-20 list)
--     NO wicket_number / ended_by_kind exclusions — top 20 by runs
--     across the whole partnership pool. This is why the IPL 2025
--     #1 row (205, B Sai Sudharsan & Shubman Gill, GT v DC
--     2025-05-18) shows wicket_number "-" — it was an unbroken
--     opening stand (the GT chase finished without losing a wicket).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_partnerships_club.sql

.mode column
.headers on

-- P1: by-wicket grid (Table 0).
.print 'P1 By wicket — averages:'
SELECT
  p.wicket_number              AS wkt,
  COUNT(*)                     AS n,
  ROUND(AVG(p.partnership_runs),  1) AS avg_runs,
  ROUND(AVG(p.partnership_balls), 1) AS avg_balls,
  MAX(p.partnership_runs)      AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  p.wicket_number IS NOT NULL
  AND  p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
GROUP  BY p.wicket_number
ORDER  BY p.wicket_number;

-- P2: top 5 partnerships overall (Table 1, top of 20).
.print ''
.print 'P2 Top 5 partnerships (NO exclusions — matches /partnerships/top):'
SELECT
  p.partnership_runs        AS runs,
  p.wicket_number            AS wkt,
  p.batter1_name             AS batter1,
  p.batter2_name             AS batter2,
  p.unbroken                 AS unbroken
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
ORDER  BY p.partnership_runs DESC, p.partnership_balls ASC
LIMIT  5;
