-- Ground-truth SQL for tests/integration/dom/teams_match_list_club.sh.
--
-- Closed window: RCB, IPL 2025. The club twin of teams_match_list_intl_fm
-- — single closed-league season, no team_class filter (clubs don't carry
-- one). Pool: 15 matches (the league + playoff run that ended in the
-- final on 2025-06-03).
--
-- The Match List endpoint sorts by date DESC. We assert:
--   • Total row count = 15
--   • Pagination footer label contains "15"
--   • First (most recent) row's opponent + date — 2025-06-03 vs PBKS (the final)
--   • Last (oldest) row's opponent + date — 2025-03-22 vs KKR (opener)
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_match_list_club.sql

.mode column
.headers on

-- M1: RCB IPL 2025 match count.
SELECT 'M1 RCB IPL 2025 count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2));

-- M2: Top 3 rows (most recent first).
.print ''
.print 'M2 Top 3 rows (DESC):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                                AS match_date,
  CASE WHEN m.team1 = 'Royal Challengers Bengaluru'
       THEN m.team2 ELSE m.team1 END AS opponent,
  m.event_name                     AS tournament
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
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
  CASE WHEN m.team1 = 'Royal Challengers Bengaluru'
       THEN m.team2 ELSE m.team1 END AS opponent,
  m.event_name                     AS tournament
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
ORDER  BY match_date ASC
LIMIT  3;
