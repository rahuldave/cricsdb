-- Ground-truth SQL for tests/integration/dom/series_fielders_club.sh.
--
-- Closed window: Indian Premier League 2025.
-- See series_fielders_intl.sql for the full audit pattern + kind
-- value notes — this audit anchors the by_dismissals top row
-- (JM Sharma 22 = 19 C + 1 St + 2 RO; RCB's keeper-cum-finisher
-- who took 19 catches behind the stumps + 1 stumping + 2 run-outs
-- across the 15-match campaign).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_fielders_club.sql

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
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  i.super_over  = 0
GROUP  BY fc.fielder_id, p.name
ORDER  BY total DESC
LIMIT  3;
