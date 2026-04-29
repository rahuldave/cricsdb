-- Ground-truth SQL for tests/integration/dom/teams_vs_opponent_club.sh.
--
-- Closed window: RCB vs Punjab Kings, IPL 2025. Picked because they
-- met FOUR times in IPL 2025 (rare for a single season — included two
-- league legs + Qualifier 1 + the Final on 2025-06-03 which RCB won
-- by 6 runs). Richer than RCB-vs-MI (1 match in 2025).
--
-- Pool: 4 matches, 3 wins, 1 loss, 0 ties.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_vs_opponent_club.sql

.mode column
.headers on

-- VS1: RCB-vs-PBKS IPL 2025 match count.
SELECT 'VS1 RCB-vs-PBKS IPL 2025 count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ((m.team1 = 'Royal Challengers Bengaluru' AND m.team2 = 'Punjab Kings')
     OR (m.team1 = 'Punjab Kings'                AND m.team2 = 'Royal Challengers Bengaluru'));

-- VS2: per-result breakdown from RCB's perspective.
.print ''
.print 'VS2 W/L/T/NR breakdown:'
SELECT
  SUM(CASE WHEN m.outcome_winner = 'Royal Challengers Bengaluru' THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN m.outcome_winner = 'Punjab Kings'                THEN 1 ELSE 0 END) AS losses,
  SUM(CASE WHEN m.outcome_result = 'tie'                         THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN m.outcome_result = 'no result'                   THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ((m.team1 = 'Royal Challengers Bengaluru' AND m.team2 = 'Punjab Kings')
     OR (m.team1 = 'Punjab Kings'                AND m.team2 = 'Royal Challengers Bengaluru'));
