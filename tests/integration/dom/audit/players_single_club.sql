-- Ground-truth SQL for tests/integration/dom/players_single_club.sh.
--
-- Closed window: B Sai Sudharsan (d5130a30), IPL 2025. Orange Cap
-- holder — top run-scorer in IPL 2025 with 759 runs.
--
-- Numbers (DOM-asserted):
--   Identity: "specialist batter · 15 matches"
--   BATTING:  Runs 759, Avg 54.21, SR 156.17, 100s 1, 50s 6, HS 108
--   FIELDING: Catches 7, Stumpings 0, Run-outs 0, Total 7
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_single_club.sql

.mode column
.headers on

-- B1: batting totals.
.print 'B1 Sudharsan batting IPL 2025:'
WITH per_innings AS (
  SELECT i.id AS innings_id, SUM(d.runs_batter) AS runs
  FROM   innings i
  JOIN   delivery d ON d.innings_id = i.id
  JOIN   match m ON m.id = i.match_id
  WHERE  m.team_type = 'club' AND m.gender = 'male'
    AND  m.event_name = 'Indian Premier League'
    AND  m.season = '2025'
    AND  d.batter_id = 'd5130a30'
  GROUP  BY i.id
)
SELECT
  SUM(d.runs_batter) AS runs,
  COUNT(DISTINCT i.id) AS innings,
  COUNT(DISTINCT m.id) AS matches,
  (SELECT MAX(runs) FROM per_innings) AS HS,
  (SELECT COUNT(*) FROM per_innings WHERE runs >= 100) AS hundreds,
  (SELECT COUNT(*) FROM per_innings WHERE runs >= 50 AND runs < 100) AS fifties
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  d.batter_id   = 'd5130a30';

-- F1: fielding credits.
.print ''
.print 'F1 Sudharsan fielding credits IPL 2025:'
SELECT fc.kind, COUNT(*) AS n
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  fc.fielder_id = 'd5130a30'
GROUP  BY fc.kind;
