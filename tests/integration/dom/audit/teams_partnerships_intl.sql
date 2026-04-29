-- Ground-truth SQL for tests/integration/dom/teams_partnerships_intl.sh.
--
-- Closed window: Australia, men's T20I 2024-2025, batting side. The
-- partnership table is per-innings; team is i.team. By-wicket
-- aggregation: GROUP BY wicket_number across all Aus innings.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_partnerships_intl.sql

.mode column
.headers on

-- P1: Aus partnership counts + avg runs by wicket. Pin wkt 1 + wkt 10.
SELECT 'P1 wkt 1' AS lbl,
       COUNT(*) AS n,
       ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
       MAX(p.partnership_runs) AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  p.wicket_number = 1
  AND  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season BETWEEN '2024' AND '2025';

SELECT 'P1 wkt 10' AS lbl,
       COUNT(*) AS n,
       ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
       MAX(p.partnership_runs) AS best_runs
FROM   partnership p
JOIN   innings i ON i.id = p.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  p.wicket_number = 10
  AND  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season BETWEEN '2024' AND '2025';

-- P2: Total Aus innings (= count of innings, used as a control for
-- the wkt-1 count which should equal innings since the 1st-wkt
-- partnership starts every innings).
SELECT 'P2 Aus innings' AS lbl, COUNT(*) AS innings
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season BETWEEN '2024' AND '2025';

-- Expected:
--   P1 wkt 1: n=22, avg_runs=26.5 (or close — 1-decimal), best=86
--   P1 wkt 10: n=3, avg_runs ~ 6.3, best=12
--   P2 = 22 (matches wkt-1 count — every innings starts with a 1st-wkt
--       partnership)
