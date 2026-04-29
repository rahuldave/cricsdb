-- Ground-truth SQL for tests/integration/dom/series_bowlers_club.sh.
--
-- Closed window: Indian Premier League 2025.
-- See series_bowlers_intl.sql for the full audit pattern + sort key
-- + threshold notes — this audit anchors the by_wickets top row.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_bowlers_club.sql

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
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  d.bowler_id IS NOT NULL
GROUP  BY d.bowler_id, p.name
ORDER  BY wickets DESC, balls ASC
LIMIT  3;
