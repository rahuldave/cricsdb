-- Ground-truth SQL for tests/integration/dom/players_single_intl.sh.
--
-- Closed window: V Kohli (ba607b88), men_intl 2024-25.
-- Kohli is a specialist batter; the profile renders a BATTING band
-- + FIELDING band (no BOWLING, no KEEPING).
--
-- Numbers (DOM-asserted):
--   Identity: "specialist batter · 7 matches"
--   BATTING:  Runs 127, Avg 18.14, SR 116.51, 100s 0, 50s 1, HS 76
--   FIELDING: Catches 2, Stumpings 0, Run-outs 0, Total 2
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_single_intl.sql

.mode column
.headers on

-- B1: batting totals (runs, balls, matches, HS).
.print 'B1 Kohli batting 24-25:'
WITH per_innings AS (
  SELECT i.id AS innings_id, SUM(d.runs_batter) AS runs
  FROM   innings i
  JOIN   delivery d ON d.innings_id = i.id
  JOIN   match m ON m.id = i.match_id
  WHERE  m.team_type = 'international' AND m.gender = 'male'
    AND  m.season >= '2024' AND m.season <= '2025'
    AND  d.batter_id = 'ba607b88'
  GROUP  BY i.id
)
SELECT
  SUM(d.runs_batter) AS runs,
  SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls,
  COUNT(DISTINCT i.id) AS innings,
  COUNT(DISTINCT m.id) AS matches,
  (SELECT MAX(runs) FROM per_innings) AS HS
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  d.batter_id   = 'ba607b88';

-- F1: fielding credit breakdown.
.print ''
.print 'F1 Kohli fielding credits 24-25:'
SELECT fc.kind, COUNT(*) AS n
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  fc.fielder_id = 'ba607b88'
GROUP  BY fc.kind;
