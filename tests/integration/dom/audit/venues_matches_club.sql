-- Ground-truth SQL for tests/integration/dom/venues_matches_club.sh.
--
-- Anchor: Wankhede Stadium IPL 2025. 7 matches DESC by date:
--   Row 0 — 2025-05-21 MI v DC          → MI won (the last home match)
--   Row 6 — 2025-03-31 KKR v MI          → MI won (the home opener)
--
-- Single DataTable, single page (≤ MATCHES_PAGE_SIZE = 50).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_matches_club.sql

.mode column
.headers on

.print 'Wankhede IPL 2025 matches DESC:'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  ) AS d,
  m.team1, m.team2, m.outcome_winner
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  m.venue       = 'Wankhede Stadium'
ORDER  BY d DESC;
