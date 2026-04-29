-- Ground-truth SQL for tests/integration/dom/series_matches_club.sh.
--
-- Closed window: Indian Premier League 2025 — 74 matches across the
-- league + playoff run. The dossier's match-list table is paginated
-- at 50 rows per page (MATCHES_PAGE_SIZE in TournamentDossier.tsx),
-- so the script asserts page 1 (50 visible) + page 2 (24 visible)
-- separately:
--   Page 1, row 0  — the Final (2025-06-03 RCB v PBKS, RCB won)
--   Page 2, row 23 — the Opener (2025-03-22 KKR v RCB, RCB won)
-- Total = 50 + 24 = 74.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_matches_club.sql

.mode column
.headers on

-- M1: IPL 2025 total match count.
SELECT 'M1 IPL 2025 count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025';

-- M2: most-recent (top of page 1) — the Final.
.print ''
.print 'M2 Most recent (page 1, row 0):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                            AS match_date,
  m.team1                      AS team1,
  m.team2                      AS team2,
  m.outcome_winner             AS winner
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
ORDER  BY match_date DESC
LIMIT  1;

-- M3: oldest (bottom of page 2) — the Opener.
.print ''
.print 'M3 Oldest (page 2, last row):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                            AS match_date,
  m.team1                      AS team1,
  m.team2                      AS team2,
  m.outcome_winner             AS winner
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
ORDER  BY match_date ASC
LIMIT  1;
