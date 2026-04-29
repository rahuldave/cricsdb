-- Ground-truth SQL for tests/integration/dom/series_batters_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024.
--
-- Backed by /api/v1/series/batters-leaders → 3 leaderboard modes:
--   by_runs        (Table 0)
--   by_average     (Table 1)  — has min_balls=100, min_dismissals=3 thresholds
--   by_strike_rate (Table 2)  — has min_balls=100 threshold
--
-- Audit anchors only the by_runs top, where the threshold is N/A
-- and the numbers are direct sums.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_batters_intl.sql

.mode column
.headers on

.print 'Top 3 batters by runs (matches Table 0 rows 0-2):'
SELECT
  p.name,
  SUM(d.runs_batter) AS runs,
  COUNT(CASE WHEN d.extras_wides = 0
              AND d.extras_noballs = 0
             THEN 1 END) AS balls
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
JOIN   person  p ON p.id = d.batter_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
GROUP  BY d.batter_id, p.name
ORDER  BY runs DESC
LIMIT  3;
