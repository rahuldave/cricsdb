-- Ground-truth SQL for tests/integration/dom/teams_vs_opponent_intl.sh.
--
-- Closed window: India vs Sri Lanka, men_intl 2024-25.
-- Picked because all four StatCards (Matches/Wins/Losses/Ties) carry
-- non-zero values OR a meaningful zero — exercises the tied-match path
-- the WC 2024 SF rivalry (1-match window) wouldn't reach.
--
-- Pool: 4 matches, 2 wins, 0 losses, 2 ties.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_vs_opponent_intl.sql

.mode column
.headers on

-- VS1: total Ind-vs-SL matches in window.
SELECT 'VS1 Ind-vs-SL count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ((m.team1 = 'India'     AND m.team2 = 'Sri Lanka')
     OR (m.team1 = 'Sri Lanka' AND m.team2 = 'India'));

-- VS2: per-result breakdown from India's perspective.
.print ''
.print 'VS2 W/L/T/NR breakdown:'
SELECT
  SUM(CASE WHEN m.outcome_winner = 'India'      THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN m.outcome_winner = 'Sri Lanka'  THEN 1 ELSE 0 END) AS losses,
  SUM(CASE WHEN m.outcome_result = 'tie'        THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN m.outcome_result = 'no result'  THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ((m.team1 = 'India'     AND m.team2 = 'Sri Lanka')
     OR (m.team1 = 'Sri Lanka' AND m.team2 = 'India'));
