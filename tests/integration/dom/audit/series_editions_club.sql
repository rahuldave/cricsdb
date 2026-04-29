-- Ground-truth SQL for tests/integration/dom/series_editions_club.sh.
--
-- Coverage anchor: Indian Premier League, all editions in the DB
-- (19 rows: 2007/08 through 2026 — including 2026 which is in
-- progress so champion is still null at this snapshot).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_editions_club.sql

.mode column
.headers on

-- E1: IPL editions + match counts (DESC by season).
SELECT m.season AS season, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
GROUP  BY m.season
ORDER  BY m.season DESC;

-- E2: Cross-check finals-row champions per edition.
.print ''
.print 'E2 Final stage outcomes per edition:'
SELECT
  m.season,
  m.outcome_winner AS champion
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.event_stage = 'Final'
ORDER  BY m.season DESC;
