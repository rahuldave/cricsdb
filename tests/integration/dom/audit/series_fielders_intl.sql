-- Ground-truth SQL for tests/integration/dom/series_fielders_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024.
--
-- Backed by /api/v1/series/fielders-leaders → 3 leaderboard modes:
--   by_dismissals (Table 0)  — total = catches + stumpings + run-outs
--                              + caught_and_bowled
--   by_keeper_dismissals (Table 1) — keeper-only catches+stumpings,
--                              JOINed through keeperassignment.
--   by_run_outs (Table 2)    — sort by run_outs DESC, total DESC.
--
-- Important — fieldingcredit.kind values use underscores:
-- 'caught', 'stumped', 'run_out', 'caught_and_bowled'.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_fielders_intl.sql

.mode column
.headers on

.print 'Top 3 by dismissals (matches Table 0 rows 0-2):'
SELECT
  p.name,
  COUNT(*) AS total,
  SUM(CASE WHEN fc.kind = 'caught'             THEN 1 ELSE 0 END) AS C,
  SUM(CASE WHEN fc.kind = 'stumped'            THEN 1 ELSE 0 END) AS St,
  SUM(CASE WHEN fc.kind = 'run_out'            THEN 1 ELSE 0 END) AS RO,
  SUM(CASE WHEN fc.kind = 'caught_and_bowled'  THEN 1 ELSE 0 END) AS Cb
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
JOIN   person   p ON p.id = fc.fielder_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  i.super_over  = 0
GROUP  BY fc.fielder_id, p.name
ORDER  BY total DESC
LIMIT  3;
