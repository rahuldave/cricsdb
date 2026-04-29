-- Ground-truth SQL for tests/integration/dom/series_bowlers_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024.
--
-- Backed by /api/v1/series/bowlers-leaders → 3 leaderboard modes:
--   by_wickets     (Table 0)  — primary sort wickets DESC, tiebreaker
--                                economy ASC (lower econ ranks higher).
--   by_strike_rate (Table 1)  — primary sort SR ASC, tiebreaker
--                                wickets DESC. min_balls=60,
--                                min_wickets=3.
--   by_economy     (Table 2)  — primary sort econ ASC, tiebreaker
--                                balls DESC. min_balls=60.
--
-- Bowler wicket exclusions per CLAUDE.md "Bowler wickets:" — exclude
-- run out, retired hurt, retired out, obstructing the field.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_bowlers_intl.sql

.mode column
.headers on

.print 'Top 3 by wickets (matches Table 0 rows 0-2):'
SELECT
  p.name,
  COUNT(DISTINCT w.id) AS wickets,
  SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
JOIN   person  p ON p.id = d.bowler_id
LEFT   JOIN wicket w ON w.delivery_id = d.id
       AND w.kind NOT IN ('run out', 'retired hurt', 'retired out',
                          'obstructing the field')
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  d.bowler_id IS NOT NULL
GROUP  BY d.bowler_id, p.name
ORDER  BY wickets DESC, balls ASC
LIMIT  3;
