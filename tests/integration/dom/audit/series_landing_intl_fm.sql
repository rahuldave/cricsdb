-- Ground-truth SQL for tests/integration/dom/series_landing_intl_fm.sh.
--
-- The /series ICC-events tile counts narrow when team_class=full_member
-- is on the FilterBar:
--   • UNBOUNDED 2024-2025 men intl:
--       - T20 World Cup (Men)            44 matches
--       - ACC Men's Premier Cup          24 matches  (associate-only)
--   • FM-ONLY 2024-2025 men intl:
--       - T20 World Cup (Men)            16 matches
--       - ACC Men's Premier Cup          DROPS OUT (no FM v FM games)
--
-- The "absent tile" assertion (ACC Premier Cup gone under FM) is the
-- proof that team_class is wired into the series-landing endpoint.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_landing_intl_fm.sql

.mode column
.headers on

-- L1: T20 WC Men 2024-2025 unbounded match count.
SELECT 'L1 T20 WC unbounded' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  m.event_name = 'ICC Men''s T20 World Cup';

-- L2: T20 WC Men 2024-2025 FM-only.
SELECT 'L2 T20 WC FM-only' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  m.event_name = 'ICC Men''s T20 World Cup'
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- L3: ACC Men's Premier Cup unbounded — control showing it exists.
SELECT 'L3 ACC Premier unbounded' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  m.event_name = 'ACC Men''s Premier Cup';

-- L4: ACC Men's Premier Cup FM-only — proof of disappearance (= 0).
SELECT 'L4 ACC Premier FM-only' AS lbl, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  m.event_name = 'ACC Men''s Premier Cup'
  AND  m.team1 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe')
  AND  m.team2 IN (
        'Afghanistan','Australia','Bangladesh','England','India',
        'Ireland','New Zealand','Pakistan','South Africa','Sri Lanka',
        'West Indies','Zimbabwe');

-- Expected:
--   L1 = 44   L2 = 16
--   L3 = 24   L4 = 0     ← under FM, the tile vanishes from /series landing
