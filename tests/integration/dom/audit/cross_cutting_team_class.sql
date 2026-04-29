-- Ground-truth SQL for tests/integration/dom/cross_cutting_team_class_consistency.sh.
--
-- The keystone test of Batch 3c — asserts the FilterBar's
-- team_class=full_member narrowing fires consistently across four
-- distinct UI surfaces. Numbers derived independently of the API
-- code path:
--
-- Surface 1: /teams Match List, Aus 24-25 FM → 16
-- Surface 2: /teams Compare,    Aus 24-25 FM → 16 (identity line)
-- Surface 3: /h2h Aus-vs-Oman 24-25 FM       → 0  (Oman is associate;
--                                                  FM filter drops the
--                                                  one match they had
--                                                  in scope. WITHOUT
--                                                  FM filter, this
--                                                  would be 1.)
-- Surface 4: /series Matches T20 WC Men 2024 FM → 16 (28 matches drop
--                                                     under FM, leaving
--                                                     16 of the 44).
--
-- The surface-3 + surface-4 numbers are sensitive: if a tab's
-- filter wiring forgets to pass team_class through, the count
-- jumps to its unbounded value and the test fails. Surfaces 1 + 2
-- are the consistency check (same number, two different DOM
-- locations).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/cross_cutting_team_class.sql

.mode column
.headers on

-- S1+2: Aus 24-25 FM-only match count.
SELECT 'S1/S2 Aus 24-25 FM' AS surface, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024' AND m.season <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.team1 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe')
  AND  m.team2 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe');

-- S3: Aus-vs-Oman 24-25, with + without FM.
.print ''
.print 'S3 Aus-vs-Oman 24-25:'
SELECT
  'unbounded' AS variant, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024' AND m.season <= '2025'
  AND  ((m.team1 = 'Australia' AND m.team2 = 'Oman')
     OR (m.team1 = 'Oman'      AND m.team2 = 'Australia'))
UNION ALL
SELECT
  'fm_only' AS variant, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024' AND m.season <= '2025'
  AND  ((m.team1 = 'Australia' AND m.team2 = 'Oman')
     OR (m.team1 = 'Oman'      AND m.team2 = 'Australia'))
  AND  m.team1 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe')
  AND  m.team2 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe');

-- S4: T20 WC Men 2024, with + without FM.
.print ''
.print 'S4 T20 WC Men 2024:'
SELECT
  'unbounded' AS variant, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
UNION ALL
SELECT
  'fm_only' AS variant, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.event_name  = "ICC Men's T20 World Cup"
  AND  m.season      = '2024'
  AND  m.team1 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe')
  AND  m.team2 IN ('Afghanistan','Australia','Bangladesh','England',
                   'India','Ireland','New Zealand','Pakistan',
                   'South Africa','Sri Lanka','West Indies','Zimbabwe');
