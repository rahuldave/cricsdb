-- Ground-truth SQL for tests/integration/dom/series_matches_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024 (44 matches across
-- the group + super-eight + knockouts). DOM sorts DESC by date.
--   Most recent: 2024-06-29 — Final, India beat South Africa.
--   Oldest:      2024-06-01 — Opener, USA beat Canada.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_matches_intl.sql

.mode column
.headers on

-- M1: T20 WC Men 2024 match count.
SELECT 'M1 T20 WC Men 2024 count' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024';

-- M2: Top 3 rows (DESC by date) — final + last two leadup.
.print ''
.print 'M2 Top 3 rows (DESC):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                            AS match_date,
  m.team1                      AS team1,
  m.team2                      AS team2,
  m.outcome_winner             AS winner
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
ORDER  BY match_date DESC
LIMIT  3;

-- M3: Bottom 3 rows (oldest in window).
.print ''
.print 'M3 Bottom 3 rows (oldest):'
SELECT
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  )                            AS match_date,
  m.team1                      AS team1,
  m.team2                      AS team2,
  m.outcome_winner             AS winner
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
ORDER  BY match_date ASC
LIMIT  3;
