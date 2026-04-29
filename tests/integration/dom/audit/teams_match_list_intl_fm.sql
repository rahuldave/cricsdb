-- Ground-truth SQL for tests/integration/dom/teams_match_list_intl_fm.sh.
--
-- Closed window: Aus T20Is, 2024-2025, FM-only (both teams ICC full members).
-- Pool: 16 matches (vs 22 unbounded — 6 dropped: associates Scotland,
-- Namibia, USA, Oman, Canada, etc).
--
-- The Match List endpoint sorts by date DESC. We assert:
--   • Total row count = 16
--   • Pagination footer label contains "16"
--   • First (most recent) row's opponent + date
--   • Last (oldest) row's opponent + date
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_match_list_intl_fm.sql

.mode column
.headers on

-- M1: Aus FM-only match count (must equal 16 for E1 to be valid).
SELECT 'M1 Aus FM-only count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- M2: Top 3 rows (most recent first) — match date + opponent.
.print ''
.print 'M2 Top 3 rows (DESC):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                                AS match_date,
  CASE WHEN m.team1 = 'Australia' THEN m.team2 ELSE m.team1 END AS opponent,
  m.event_name                     AS tournament
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
ORDER  BY match_date DESC
LIMIT  3;

-- M3: Bottom 3 rows (oldest in window).
.print ''
.print 'M3 Bottom 3 rows (DESC tail):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                                AS match_date,
  CASE WHEN m.team1 = 'Australia' THEN m.team2 ELSE m.team1 END AS opponent,
  m.event_name                     AS tournament
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
ORDER  BY match_date ASC
LIMIT  3;
