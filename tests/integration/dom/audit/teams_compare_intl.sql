-- Ground-truth SQL for tests/integration/dom/teams_compare_intl.sh.
--
-- Closed window: men's T20Is, 2024-2025 (calendar). Three baselines:
--   • UNBOUNDED — all male international matches in window (870)
--   • FM-ONLY   — both teams ICC full members           (140)
--   • SCOPE     — Australia matches in window           (22)
--                 ↳ FM-only narrowing                   (16)
--                 India matches                         (34)
--                 ↳ FM-only narrowing                   (31)
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_compare_intl.sql

.mode column
.headers on

-- A1: total male intl matches in 2024-2025 (unbounded pool)
SELECT 'A1 unbounded match pool' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025';

-- A2: FM-only pool — both teams are ICC full members
SELECT 'A2 FM-only match pool' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025'
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- A3: Australia's matches in window (unbounded)
SELECT 'A3 Aus matches unbounded' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025'
  AND  ('Australia' IN (team1, team2));

-- A4: Australia's matches in window (FM-only)
SELECT 'A4 Aus matches FM-only' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- A5: India's matches in window (unbounded)
SELECT 'A5 India matches unbounded' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025'
  AND  ('India' IN (team1, team2));

-- A6: India's matches FM-only
SELECT 'A6 India matches FM-only' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  team_type = 'international'
  AND  gender    = 'male'
  AND  season   >= '2024'
  AND  season   <= '2025'
  AND  ('India' IN (m.team1, m.team2))
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- A7: Australia run rate (per-innings concatenated rate). Legal balls
-- only (no wides/noballs); over numbering is 0-19 in DB so phase
-- boundaries don't matter for total rate.
SELECT
  'A7 Aus run rate'           AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  i.team = 'Australia';

-- A8: Unbounded pool run rate (all male intl 2024-2025 innings).
SELECT
  'A8 unbounded RR'           AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- A9: FM-only pool run rate (both teams in match are full members).
SELECT
  'A9 FM-only RR'             AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- Expected:
--   A1 = 870   A2 = 140
--   A3 = 22    A4 = 16        (E1 anchor: Aus narrows 22 → 16)
--   A5 = 34    A6 = 31        (E1 anchor: India narrows 34 → 31)
--   A7 = 9.91  A8 = 7.52      (Anchor A: Aus chip vs unbounded avg)
--   A9 = 8.50                 (Anchors A' / E1: FM-only avg)
