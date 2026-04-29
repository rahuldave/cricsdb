-- Ground-truth SQL for tests/integration/dom/venues_batters_intl.sh.
--
-- Anchor: Eden Gardens men_intl all-time. Backed by /api/v1/batters/
-- leaders?filter_venue=Eden+Gardens&... — same endpoint as
-- Series Batters with `filter_venue` appended.
--
-- Important — Venues Batters renders 2 tables (by_average +
-- by_strike_rate), NOT 3 like Series Batters. The "by_runs" mode
-- is omitted at venue scope: at low match volumes (Eden = 18
-- matches), by_runs would just rank everyone with the most
-- appearances; the threshold-applying modes (min_balls/dismissals
-- on avg, min_balls on SR) yield meaningful leaderboards.
--
-- Top batters at Eden men_intl by raw runs (threshold-free
-- baseline — the by_average DOM table puts Pooran #1 because
-- 61.33 = 184/3, well above other contenders):
--   N Pooran  184r / 131b   → by_avg #1, SR 140.46
--   R Powell  166r / 108b   → by_SR  #1, SR 153.70 (top)
--   SD Hope   148r / 115b
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_batters_intl.sql

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
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.venue       = 'Eden Gardens'
  AND  d.extras_wides = 0 AND d.extras_noballs = 0
GROUP  BY d.batter_id, p.name
ORDER  BY runs DESC
LIMIT  3;
