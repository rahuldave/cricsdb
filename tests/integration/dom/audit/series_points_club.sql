-- Ground-truth SQL for tests/integration/dom/series_points_club.sh.
--
-- Closed window: Indian Premier League 2025 league stage (excludes
-- Final / Eliminator / Qualifier 1 / Qualifier 2 — the four
-- playoffs).
--
-- Top of league: Punjab Kings (15 P, 9 W, 4 L, 2 NR, 20 pts).
-- Wooden spoon: Chennai Super Kings (14 P, 4 W, 10 L, 8 pts).
-- Note PBKS + DC played 15 league matches each (IPL 2025 had a
-- replayed PBKS-DC match after the May 2025 mid-season pause); RCB
-- + KKR played 13 (their match was canceled and not rescheduled).
-- Other teams played 14 — the standard IPL format.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_points_club.sql

.mode column
.headers on

-- P1: per-team league-match count (excluding playoffs).
WITH league AS (
  SELECT *
  FROM match m
  WHERE m.team_type   = 'club'
    AND m.gender      = 'male'
    AND m.event_name  = 'Indian Premier League'
    AND m.season      = '2025'
    AND (m.event_stage IS NULL OR m.event_stage NOT IN
         ('Final','Semi Final','Eliminator','Qualifier 1',
          'Qualifier 2','Qualifier','Quarter Final','Play-Off',
          'Knockout'))
)
SELECT team, COUNT(*) AS played
FROM (
  SELECT team1 AS team FROM league
  UNION ALL
  SELECT team2 AS team FROM league
)
GROUP BY team
ORDER BY played DESC, team;

-- P2: PBKS league record (top of table).
.print ''
.print 'P2 PBKS league record:'
WITH pbks AS (
  SELECT *
  FROM match m
  WHERE m.team_type='club' AND m.gender='male'
    AND m.event_name='Indian Premier League' AND m.season='2025'
    AND (m.event_stage IS NULL OR m.event_stage NOT IN
         ('Final','Semi Final','Eliminator','Qualifier 1','Qualifier 2'))
    AND ('Punjab Kings' IN (m.team1, m.team2))
)
SELECT
  COUNT(*)                                          AS played,
  SUM(CASE WHEN outcome_winner='Punjab Kings'   THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN outcome_winner IS NOT NULL
            AND outcome_winner != 'Punjab Kings'  THEN 1 ELSE 0 END) AS losses,
  SUM(CASE WHEN outcome_result='tie'             THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN outcome_result='no result'       THEN 1 ELSE 0 END) AS no_results
FROM pbks;
