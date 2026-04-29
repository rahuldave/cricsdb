-- Ground-truth SQL for tests/integration/dom/players_single_intl_women.sh.
--
-- Closed window: S Mandhana (5d2eda89), women_intl 2024-25.
-- Mandhana led India's batting through the women's T20 World Cup
-- 2024 cycle and the 2024-25 bilaterals. Specialist batter — only
-- BATTING + FIELDING bands render.
--
-- Numbers (DOM-asserted):
--   Identity: "specialist batter · 25 matches"
--             (matches = max across batting/bowling/fielding;
--              matchplayer is the fielding side, all 25 played)
--   BATTING:  Runs 877, Avg 43.85, SR 133.69, 100s 1, 50s 8, HS 112
--   FIELDING: Catches 10, Stumpings 0, Run-outs 2, Total 12
--
-- The batter summary endpoint counts ONLY legal balls (excludes
-- wides + noballs) — see api/routers/batting.py:_batting_filter.
-- Audit applies the same filter so SQL matches API.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_single_intl_women.sql

.mode column
.headers on

.print 'B1 Mandhana batting 24-25:'
WITH per_innings AS (
  SELECT i.id AS innings_id, SUM(d.runs_batter) AS runs
  FROM   innings i
  JOIN   delivery d ON d.innings_id = i.id
  JOIN   match m ON m.id = i.match_id
  WHERE  m.team_type = 'international' AND m.gender = 'female'
    AND  m.season >= '2024' AND m.season <= '2025'
    AND  d.batter_id = '5d2eda89'
    AND  d.extras_wides = 0 AND d.extras_noballs = 0
  GROUP  BY i.id
)
SELECT
  SUM(d.runs_batter) AS runs,
  COUNT(*)           AS balls,
  COUNT(DISTINCT i.id) AS innings,
  COUNT(DISTINCT m.id) AS matches_batted,
  (SELECT MAX(runs) FROM per_innings) AS HS,
  (SELECT COUNT(*) FROM per_innings WHERE runs >= 100) AS hundreds,
  (SELECT COUNT(*) FROM per_innings WHERE runs >= 50 AND runs < 100) AS fifties
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'female'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  d.batter_id   = '5d2eda89'
  AND  d.extras_wides = 0 AND d.extras_noballs = 0;

-- M1: total matches Mandhana appeared in (matchplayer, used by
-- frontend matchesInScope() which is max across disciplines).
.print ''
.print 'M1 Mandhana matchplayer count 24-25:'
SELECT COUNT(DISTINCT mp.match_id) AS matches
FROM   matchplayer mp
JOIN   match m ON m.id = mp.match_id
WHERE  m.team_type = 'international'
  AND  m.gender    = 'female'
  AND  m.season   >= '2024' AND m.season <= '2025'
  AND  mp.person_id = '5d2eda89';

-- F1: fielding credits.
.print ''
.print 'F1 Mandhana fielding credits 24-25:'
SELECT fc.kind, COUNT(*) AS n
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'female'
  AND  m.season     >= '2024' AND m.season <= '2025'
  AND  fc.fielder_id = '5d2eda89'
GROUP  BY fc.kind;
