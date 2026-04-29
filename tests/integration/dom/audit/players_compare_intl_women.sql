-- Ground-truth SQL for tests/integration/dom/players_compare_intl_women.sh.
--
-- Closed window: S Mandhana × BL Mooney, women_intl 2024-25.
-- The first COMPARE_WOMEN pair from CuratedLists.ts. Two contrasted
-- columns — Mandhana plays as a specialist top-order batter with no
-- KEEPING band; Mooney is a keeper-batter so KEEPING renders.
--
-- Expected (DOM-asserted):
--   Mandhana col: BATTING 877r/43.85/SR 133.69/1×100/8×50/HS 112
--                 FIELDING 10C / 0St / 2RO / Total 12
--                 (NO KEEPING — section renders empty placeholder
--                  for cross-column row alignment with Mooney)
--   Mooney col:   BATTING 548r/54.80/SR 137.34/0×100/4×50/HS 94
--                 FIELDING 8C / 1St / 3RO / Total 12
--                 KEEPING  Innings kept 8, Catches 5, Stumpings 1,
--                          Byes 10, Byes/inn 1.25
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_compare_intl_women.sql

.mode column
.headers on

.print 'B1 Mandhana + Mooney batting 24-25 (legal balls only):'
WITH players AS (
  SELECT '5d2eda89' AS pid, 'Mandhana' AS who UNION ALL
  SELECT '52d1dbc8' AS pid, 'Mooney'   AS who
),
per_innings AS (
  SELECT i.id AS innings_id, d.batter_id, SUM(d.runs_batter) AS runs
  FROM   innings i
  JOIN   delivery d ON d.innings_id = i.id
  JOIN   match m ON m.id = i.match_id
  WHERE  m.team_type = 'international' AND m.gender = 'female'
    AND  m.season >= '2024' AND m.season <= '2025'
    AND  d.batter_id IN (SELECT pid FROM players)
    AND  d.extras_wides = 0 AND d.extras_noballs = 0
  GROUP  BY i.id, d.batter_id
)
SELECT
  p.who,
  SUM(d.runs_batter) AS runs,
  COUNT(*)           AS balls,
  COUNT(DISTINCT i.id) AS innings,
  (SELECT MAX(runs) FROM per_innings WHERE batter_id = p.pid) AS HS,
  (SELECT COUNT(*) FROM per_innings WHERE batter_id = p.pid AND runs >= 100) AS hundreds,
  (SELECT COUNT(*) FROM per_innings WHERE batter_id = p.pid AND runs >= 50 AND runs < 100) AS fifties
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
JOIN   players  p ON p.pid = d.batter_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'female'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  d.extras_wides = 0 AND d.extras_noballs = 0
GROUP  BY p.pid, p.who;

.print ''
.print 'F1 Fielding credits 24-25:'
SELECT
  CASE fc.fielder_id WHEN '5d2eda89' THEN 'Mandhana' WHEN '52d1dbc8' THEN 'Mooney' END AS who,
  fc.kind,
  COUNT(*) AS n
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'female'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  fc.fielder_id IN ('5d2eda89','52d1dbc8')
GROUP  BY who, fc.kind
ORDER  BY who, fc.kind;
