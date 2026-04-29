-- Ground-truth SQL for tests/integration/dom/matches_scorecard_highlight.sh.
--
-- Confirms which rows on /matches/1551 SHOULD be tinted by each
-- highlight URL param. Pure DOM-behavior test (no numeric SQL
-- assertions on the tinted rows; just verify they exist and the
-- page scrolled to them).
--
-- Anchor: WC 2024 Final (match_id=1551, India v SA).
--
-- ?highlight_batter=ba607b88   → tints V Kohli's row in India batting
-- ?highlight_bowler=462411b3   → tints JJ Bumrah's row in SA bowling
-- ?highlight_fielder=271fa583cd → tints DA Miller AND K Rabada's
--                                 batting rows (both caught by SA
--                                 Yadav off HH Pandya — including
--                                 the famous boundary catch on Miller
--                                 in the last over). TWO highlighted
--                                 rows expected.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/matches_scorecard_highlight.sql

.mode column
.headers on

-- F1: SA Yadav fielding credits in 1551 (TWO catches expected).
.print 'F1 SA Yadav (271f83cd) catches in WC 2024 Final:'
SELECT
  fc.kind,
  d.batter AS batter_dismissed,
  d.bowler AS bowler
FROM   fieldingcredit fc
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id  = 1551
  AND  fc.fielder_id = '271f83cd';

.print ''
.print 'F2 Bumrah (462411b3) confirms he bowled in 1551:'
SELECT COUNT(*) AS deliveries_bowled
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 1551
  AND  d.bowler_id = '462411b3';

.print ''
.print 'F3 Kohli (ba607b88) batted in 1551 (76 runs):'
SELECT
  SUM(d.runs_batter) AS runs,
  COUNT(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 END) AS balls
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 1551
  AND  d.batter_id = 'ba607b88';
