-- Ground-truth SQL for tests/integration/dom/series_partnerships_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024.
--
-- The Partnerships tab fans out into 12 DataTables:
--   Table 0  — "By wicket — averages"  (10 rows: 1st…10th wicket)
--   Table 1  — "Top partnerships" overall (top 20 by runs)
--   Tables 2-11 — "Top partnerships by wicket" (one sub-table per
--                 wicket — out of script scope, asserting Table 0+1
--                 covers the canonical aggregations).
--
-- Important — the API excludes partnerships ended by 'retired hurt'
-- or 'retired not out' (matches tournament_partnerships_by_wicket
-- in api/routers/tournaments.py:2664). Without this exclusion, the
-- 1st-wicket pool is 85 partnerships; with it, 84 — and the API
-- shows 84. Audit MUST include the same exclusion to match the API
-- numbers (otherwise the integration test would fail loudly with
-- the audit "ground truth" that disagrees with the application).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_partnerships_intl.sql

.mode column
.headers on

-- P1: by-wicket grid (Table 0 of the DOM, 10 rows).
.print 'P1 By wicket — averages (matches Table 0):'
SELECT
  p.wicket_number                              AS wkt,
  COUNT(*)                                     AS n,
  ROUND(AVG(p.partnership_runs),  1)           AS avg_runs,
  ROUND(AVG(p.partnership_balls), 1)           AS avg_balls,
  MAX(p.partnership_runs)                      AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  p.wicket_number IS NOT NULL
  AND  p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
GROUP  BY p.wicket_number
ORDER  BY p.wicket_number;

-- P2: top 5 partnerships overall (matches Table 1, top of 20).
.print ''
.print 'P2 Top 5 partnerships (matches first 5 rows of Table 1):'
SELECT
  p.partnership_runs        AS runs,
  p.wicket_number            AS wkt,
  p.batter1_name             AS batter1,
  p.batter2_name             AS batter2
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  p.wicket_number IS NOT NULL
  AND  p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
ORDER  BY p.partnership_runs DESC
LIMIT  5;
