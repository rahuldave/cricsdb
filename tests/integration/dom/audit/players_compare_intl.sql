-- Ground-truth SQL for tests/integration/dom/players_compare_intl.sh.
--
-- Closed window: V Kohli vs RG Sharma, men_intl 2024-25 — both
-- played the same 7-match return-to-T20I window after the 2024 T20
-- World Cup. Provides one rich + one rich column. Compare-mode
-- DOM uses .wisden-compare-col + .wisden-player-compact-row dt/dd
-- (NOT the .wisden-statrow band shape used in single-mode).
--
-- Expected (DOM-asserted, both columns):
--   Kohli:  BATTING Runs 127, Avg 18.14, SR 116.51, 100s 0, 50s 1, HS 76
--           FIELDING Catches 2, Total 2
--   Sharma: BATTING Runs 249, Avg 41.50, SR 164.90, 100s 0, 50s 3, HS 92
--           FIELDING Catches 3, Total 3
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_compare_intl.sql

.mode column
.headers on

.print 'B1 Kohli + Sharma batting 24-25:'
WITH players AS (
  SELECT 'ba607b88' AS pid, 'V Kohli'   AS name UNION ALL
  SELECT '740742ef' AS pid, 'RG Sharma' AS name
),
per_innings AS (
  SELECT i.id AS innings_id, d.batter_id, SUM(d.runs_batter) AS runs
  FROM   innings i
  JOIN   delivery d ON d.innings_id = i.id
  JOIN   match    m ON m.id = i.match_id
  WHERE  m.team_type = 'international' AND m.gender = 'male'
    AND  m.season >= '2024' AND m.season <= '2025'
    AND  d.batter_id IN (SELECT pid FROM players)
  GROUP  BY i.id, d.batter_id
)
SELECT
  p.name,
  SUM(d.runs_batter)  AS runs,
  SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls,
  COUNT(DISTINCT m.id) AS matches,
  (SELECT MAX(runs) FROM per_innings WHERE batter_id = p.pid) AS HS,
  (SELECT COUNT(*) FROM per_innings WHERE batter_id = p.pid AND runs >= 100) AS hundreds,
  (SELECT COUNT(*) FROM per_innings WHERE batter_id = p.pid AND runs >= 50 AND runs < 100) AS fifties
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
JOIN   players  p ON p.pid = d.batter_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.season     >= '2024' AND m.season <= '2025'
GROUP  BY p.pid, p.name;

.print ''
.print 'F1 Kohli + Sharma fielding credits 24-25:'
SELECT
  CASE fc.fielder_id WHEN 'ba607b88' THEN 'Kohli' WHEN '740742ef' THEN 'Sharma' END AS who,
  fc.kind,
  COUNT(*) AS n
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  fc.fielder_id IN ('ba607b88','740742ef')
GROUP  BY who, fc.kind
ORDER  BY who, fc.kind;
