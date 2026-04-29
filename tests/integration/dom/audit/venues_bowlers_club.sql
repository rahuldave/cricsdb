-- Ground-truth SQL for tests/integration/dom/venues_bowlers_club.sh.
--
-- Anchor: Wankhede Stadium IPL 2025. Bowler leaderboard backed by
-- /api/v1/bowlers/leaders?filter_venue=Wankhede+Stadium&...
--
-- Renders TWO tables (by_strike_rate + by_economy), NOT three like
-- Series Bowlers — by_wickets dropped at venue scope per the same
-- low-volume rationale as venues_batters_*.
--
-- Top 3 by wickets at Wankhede IPL 2025 (with API exclusions —
-- run out / retired hurt / retired out / obstructing the field):
--   JJ Bumrah     12W / 140b → tops both by_SR (11.67) + by_econ (5.49)
--   TA Boult      10W / 168b
--   Ashwani Kumar  7W /  54b
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_bowlers_club.sql

.mode column
.headers on

.print 'Top 3 bowlers by wickets at Wankhede IPL 2025:'
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
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  m.venue       = 'Wankhede Stadium'
  AND  d.bowler_id IS NOT NULL
GROUP  BY d.bowler_id, p.name
ORDER  BY wickets DESC, balls ASC
LIMIT  3;
