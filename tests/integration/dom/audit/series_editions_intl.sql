-- Ground-truth SQL for tests/integration/dom/series_editions_intl.sh.
--
-- Coverage anchor: ICC Men's T20 World Cup, all editions in the DB.
-- Cricsheet's coverage of pre-2021 T20 WCs is sparse — we have 5
-- editions: 2025/26, 2024, 2022/23, 2021/22, plus a single match
-- from 2013/14 (one early-era recorded match — not a full edition).
-- The DOM table is unsorted by spec; the API returns DESC by season.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_editions_intl.sql

.mode column
.headers on

-- E1: T20 WC Men editions + match counts (DESC by season).
SELECT m.season AS season, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
GROUP  BY m.season
ORDER  BY m.season DESC;

-- E2: Cross-check finals-row champions (the per-edition champion
-- comes from the Final-stage outcome).
.print ''
.print 'E2 Final stage outcomes per edition:'
SELECT
  m.season,
  m.outcome_winner AS champion
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.event_stage = 'Final'
ORDER  BY m.season DESC;
