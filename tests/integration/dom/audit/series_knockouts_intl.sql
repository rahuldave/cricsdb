-- Ground-truth SQL for tests/integration/dom/series_knockouts_intl.sh.
--
-- Closed window: ICC Men's T20 World Cup 2024 — exactly two
-- knockout matches, both won by India:
--   Final:      India v South Africa  → India (7 runs)
--   Semi Final: India v England       → India (68 runs)
--
-- The Knockouts table is at idx 0 of the Series Overview tab's
-- DataTables; the Champions by-season table is at idx 1. With a
-- single-season filter the Knockouts table shrinks to that
-- season's SFs + Final and the Champions table to that season's
-- single Final.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_knockouts_intl.sql

.mode column
.headers on

.print 'T20 WC Men 2024 knockouts (Final + SFs):'
SELECT
  m.season,
  m.event_stage,
  m.team1,
  m.team2,
  m.outcome_winner
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  m.event_stage IN ('Final', 'Semi Final')
ORDER  BY m.event_stage DESC,
  COALESCE(
    (SELECT date FROM matchdate WHERE match_id = m.id ORDER BY date DESC LIMIT 1),
    ''
  ) DESC;
