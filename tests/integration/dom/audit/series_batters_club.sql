-- Ground-truth SQL for tests/integration/dom/series_batters_club.sh.
--
-- Closed window: Indian Premier League 2025.
--
-- Same shape as the intl twin — anchors by_runs row 0 (B Sai
-- Sudharsan, 759). The by_average and by_strike_rate top rows are
-- thresholded (min_balls=100, min_dismissals=3 on average), so
-- replicating those in SQL means duplicating the threshold logic;
-- the API correctness for those is covered by the by_runs anchor +
-- the DOM render assertions.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_batters_club.sql

.mode column
.headers on

.print 'Top 3 batters by runs (matches Table 0 rows 0-2):'
SELECT
  p.name,
  SUM(d.runs_batter) AS runs,
  COUNT(CASE WHEN d.extras_wides = 0
              AND d.extras_noballs = 0
             THEN 1 END) AS balls
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
JOIN   person  p ON p.id = d.batter_id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
GROUP  BY d.batter_id, p.name
ORDER  BY runs DESC
LIMIT  3;
