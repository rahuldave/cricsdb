-- Ground-truth SQL for tests/integration/dom/venues_batters_club.sh.
--
-- Anchor: Wankhede Stadium IPL 2025 — 7 matches, very thin batter
-- pool (3 rows in each leaderboard mode). SA Yadav tops both
-- by_average and by_strike_rate.
--
-- Top 3 batters at Wankhede IPL 2025 by raw runs:
--   SA Yadav      311r / 175b   → by_avg + by_SR #1 (SR 177.71)
--   RD Rickelton  219r / 143b
--   WG Jacks      177r / 130b
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_batters_club.sql

.mode column
.headers on

.print 'Top 3 batters by raw runs (legal balls only):'
SELECT
  p.name,
  SUM(d.runs_batter) AS runs,
  SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS balls
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
JOIN   person   p ON p.id = d.batter_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  m.venue       = 'Wankhede Stadium'
  AND  d.extras_wides = 0 AND d.extras_noballs = 0
GROUP  BY d.batter_id, p.name
ORDER  BY runs DESC
LIMIT  3;
