-- Ground-truth SQL for tests/integration/dom/matches_scorecard_intl.sh.
--
-- Anchor: ICC Men's T20 World Cup 2024 Final (match_id=1551).
-- India v South Africa, Kensington Oval, Bridgetown, 2024-06-29.
-- India won by 7 runs after a famous Bumrah/Pandya defense of
-- 176 against SA chasing 30 from 30 balls.
--
-- DOM-asserted scorecard values:
--   Header / banner:
--     title = "India v South Africa"
--     result = "India won by 7 runs"
--   Innings 1 — India 176/7 (20.0):
--     Batter row 0: RG Sharma 9 (5)   c H Klaasen b KA Maharaj
--     Batter row 1: V Kohli   76 (59) c K Rabada  b M Jansen
--     Bowler row 0: M Jansen   4-0-49-1
--     Bowler row 1: KA Maharaj 3-0-23-2
--   Innings 2 — South Africa 169/8 (20.0):
--     Batter row 0: RR Hendricks  4  (5)
--     Batter row 1: Q de Kock    39 (31)
--     Bowler row 0: Arshdeep Singh 4-0-21-2
--     Bowler row 1: JJ Bumrah     4-0-19-2
--
-- Note: DOM table layout has TWO matchup-grid charts at indices
-- 0+1 (per-innings batter × bowler grids); the actual scorecard
-- batting/bowling cards live at indices 2-5.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/matches_scorecard_intl.sql

.mode column
.headers on

.print 'M1 Match identity:'
SELECT id, team1, team2, event_name, season, event_stage,
       outcome_winner, outcome_by_runs
FROM   match
WHERE  id = 1551;

.print ''
.print 'M2 Innings totals (computed from delivery aggregates):'
SELECT
  i.innings_number,
  i.team,
  SUM(d.runs_total) AS total_runs,
  COUNT(CASE WHEN w.id IS NOT NULL THEN 1 END) AS wickets
FROM   innings i
JOIN   delivery d ON d.innings_id = i.id
LEFT   JOIN wicket w ON w.delivery_id = d.id
WHERE  i.match_id = 1551
  AND  i.super_over = 0
GROUP  BY i.id
ORDER  BY i.innings_number;

.print ''
.print 'M3 Top 3 batters per innings (by batting position = first appearance):'
SELECT
  i.innings_number,
  d.batter_id,
  p.name,
  SUM(d.runs_batter) AS runs,
  SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls,
  MIN(d.id) AS first_delivery
FROM   innings i
JOIN   delivery d ON d.innings_id = i.id
JOIN   person   p ON p.id = d.batter_id
WHERE  i.match_id = 1551 AND i.super_over = 0
GROUP  BY i.innings_number, d.batter_id
ORDER  BY i.innings_number, first_delivery
LIMIT  6;
