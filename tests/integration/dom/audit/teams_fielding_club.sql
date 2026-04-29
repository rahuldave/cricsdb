-- Ground-truth SQL for tests/integration/dom/teams_fielding_club.sh.
--
-- Closed window: Royal Challengers Bengaluru, IPL 2025.
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_fielding_club.sql

.mode column
.headers on

SELECT 'F1 RCB fielding by kind' AS lbl,
       SUM(CASE WHEN fc.kind = 'caught'             THEN 1 ELSE 0 END) AS catches_only,
       SUM(CASE WHEN fc.kind = 'caught_and_bowled'  THEN 1 ELSE 0 END) AS caught_and_bowled,
       SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled')
                                                    THEN 1 ELSE 0 END) AS catches_inclusive,
       SUM(CASE WHEN fc.kind = 'stumped'            THEN 1 ELSE 0 END) AS stumpings,
       SUM(CASE WHEN fc.kind = 'run_out'            THEN 1 ELSE 0 END) AS run_outs
FROM   fieldingcredit fc
JOIN   wicket   w ON w.id = fc.wicket_id
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Royal Challengers Bengaluru'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- Expected:
--   catches_only:69 caught_and_bowled:0 catches_inclusive:69
--   stumpings:1 run_outs:7
