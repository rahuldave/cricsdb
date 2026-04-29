-- Ground-truth SQL for tests/integration/dom/series_champions_intl.sh.
--
-- Closed-window snapshot: ICC Men's T20 World Cup, ALL editions
-- (no season filter). The Series Overview tab renders a "Champions
-- by season" table at index 1 of the page's DataTables, with one
-- row per Final outcome. 4 rows total in the DB:
--
--   2025/26  India v New Zealand    → India       (most recent)
--   2024     India v South Africa   → India
--   2022/23  Pakistan v England     → England
--   2021/22  New Zealand v Australia → Australia  (oldest in DB)
--
-- Cricsheet doesn't carry pre-2021 T20 WC editions in full (we have
-- a single 2013/14 match, no Final entry — see series_editions_intl.sh).
--
-- The DOM table at idx 0 is "Knockouts" (semis + finals across all
-- editions, 11 rows); table at idx 1 is "Champions by season" (4
-- rows). Same /series/summary endpoint backs both — `knockouts` and
-- `champions_by_season` fields.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_champions_intl.sql

.mode column
.headers on

.print 'All T20 WC Men finals (DESC by season):'
SELECT
  m.season,
  m.team1,
  m.team2,
  m.outcome_winner AS champion
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.event_stage = 'Final'
ORDER  BY m.season DESC;
