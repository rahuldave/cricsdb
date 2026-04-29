-- Ground-truth SQL for tests/integration/dom/venues_records_intl.sh.
--
-- Anchor: Eden Gardens men_intl all-time. The Records tab fans out
-- to 7 DataTables:
--   T0 Highest team totals
--   T1 Lowest all-out totals
--   T2 Biggest wins by runs
--   T3 Biggest wins by wickets
--   T4 Largest partnerships
--   T5 Best bowling figures
--   T6 Most sixes in a match
--
-- The audit anchors T0 + T1 (the two team-total endpoints whose
-- shape matches highest_total + lowest_all_out from the venue
-- summary endpoint, already cross-checked in venues_overview_intl).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_records_intl.sql

.mode column
.headers on

.print 'T0 Highest team totals at Eden men_intl:'
SELECT
  COALESCE((SELECT date FROM matchdate WHERE match_id=m.id ORDER BY date DESC LIMIT 1),'') AS d,
  i.team,
  CASE WHEN i.team=m.team1 THEN m.team2 ELSE m.team1 END AS opp,
  SUM(d_.runs_total) AS runs
FROM   innings i
JOIN   match m ON m.id = i.match_id
JOIN   delivery d_ ON d_.innings_id = i.id
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.venue       = 'Eden Gardens'
  AND  i.super_over  = 0
GROUP  BY i.id
ORDER  BY runs DESC
LIMIT  3;

.print ''
.print 'T1 Lowest all-out totals at Eden men_intl (≥10 wickets):'
WITH inn AS (
  SELECT i.id AS innings_id, i.team, m.id AS match_id,
         SUM(d_.runs_total) AS runs,
         COUNT(CASE WHEN w.id IS NOT NULL THEN 1 END) AS wkts
  FROM   innings i
  JOIN   match    m ON m.id = i.match_id
  JOIN   delivery d_ ON d_.innings_id = i.id
  LEFT   JOIN wicket w ON w.delivery_id = d_.id
  WHERE  m.team_type='international' AND m.gender='male'
    AND  m.venue='Eden Gardens' AND i.super_over = 0
  GROUP  BY i.id
)
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id=inn.match_id
     ORDER BY date DESC LIMIT 1), ''
  ) AS d,
  team, runs, wkts
FROM   inn
WHERE  wkts >= 10
ORDER  BY runs ASC
LIMIT  3;
