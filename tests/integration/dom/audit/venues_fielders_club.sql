-- Ground-truth SQL for tests/integration/dom/venues_fielders_club.sh.
--
-- Anchor: Wankhede Stadium IPL 2025. Two leaderboards on the page:
--   T0 by_dismissals — 10 rows, RD Rickelton tops with 10 (6C/4St).
--   T1 by_keeper     —  1 row, RD Rickelton (the only keeper to
--                        have keeped at Wankhede in IPL 2025 —
--                        only MI's home matches kept by him).
--
-- fieldingcredit.kind values are underscored: 'caught', 'stumped',
-- 'run_out', 'caught_and_bowled'.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_fielders_club.sql

.mode column
.headers on

.print 'Top 3 fielders by total dismissals at Wankhede IPL 2025:'
SELECT
  p.name,
  COUNT(*) AS total,
  SUM(CASE WHEN fc.kind='caught'  THEN 1 ELSE 0 END) AS C,
  SUM(CASE WHEN fc.kind='stumped' THEN 1 ELSE 0 END) AS St,
  SUM(CASE WHEN fc.kind='run_out' THEN 1 ELSE 0 END) AS RO
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
JOIN   person   p ON p.id = fc.fielder_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  m.venue       = 'Wankhede Stadium'
  AND  i.super_over  = 0
GROUP  BY fc.fielder_id, p.name
ORDER  BY total DESC
LIMIT  3;
