-- Ground-truth SQL for tests/integration/dom/matches_scorecard_club.sh.
--
-- Anchor: IPL 2025 Final (match_id=6018). Royal Challengers
-- Bengaluru v Punjab Kings, Narendra Modi Stadium Ahmedabad,
-- 2025-06-03. RCB won by 6 runs in a classic low-scoring final.
--
-- DOM-asserted scorecard values:
--   Header / banner:
--     title = "Royal Challengers Bengaluru v Punjab Kings"
--     result = "Royal Challengers Bengaluru won by 6 runs"
--   Innings 1 — RCB 190/9 (20.0):
--     Batter row 0: PD Salt   16 (9) c SS Iyer b KA Jamieson
--     Batter row 1: V Kohli   43 (35) c & b Azmatullah Omarzai
--     Bowler row 0: Arshdeep Singh 4-0-40-3
--     Bowler row 1: KA Jamieson    4-0-48-3
--   Innings 2 — Punjab Kings 184/7 (20.0):
--     Batter row 0: Priyansh Arya  24 (19)
--     Batter row 1: P Simran Singh 26 (22)
--     Bowler row 0: B Kumar    4-0-38-2
--     Bowler row 1: Yash Dayal 3-0-24-1
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/matches_scorecard_club.sql

.mode column
.headers on

.print 'M1 Match identity:'
SELECT id, team1, team2, event_name, season, event_stage,
       outcome_winner, outcome_by_runs
FROM   match
WHERE  id = 6018;

.print ''
.print 'M2 Innings totals:'
SELECT
  i.innings_number,
  i.team,
  SUM(d.runs_total) AS total_runs,
  COUNT(CASE WHEN w.id IS NOT NULL THEN 1 END) AS wickets
FROM   innings i
JOIN   delivery d ON d.innings_id = i.id
LEFT   JOIN wicket w ON w.delivery_id = d.id
WHERE  i.match_id = 6018
  AND  i.super_over = 0
GROUP  BY i.id
ORDER  BY i.innings_number;
