-- Ground-truth SQL for tests/integration/dom/players_landing_women.sh.
--
-- The /players?gender=female landing renders curated tiles whose
-- person_ids come from `frontend/src/components/players/CuratedLists.ts`
-- (PROFILE_WOMEN, COMPARE_WOMEN). Audit confirms each ID resolves +
-- has match activity.
--
-- Note: cricsheet's stored name for "D Sharma" in CuratedLists is
-- "DB Sharma" in the person table. The TILE shows "D Sharma" (the
-- curated label CuratedLists explicitly chose), so the DOM
-- assertion checks "D Sharma" — this audit confirms 201fef33 is
-- DB Sharma in the DB, and the tile-strip data fetched via the
-- batter/bowler summary will resolve to her stats correctly.
--
-- Curated WOMEN profile tiles (PROFILE_WOMEN, 9):
--   5d2eda89 S Mandhana   (batter)
--   be150fc8 EA Perry     (batter)
--   4ba0289e HC Knight    (batter)
--   52d1dbc8 BL Mooney    (batter)
--   27e003ce MM Lanning   (batter)
--   201fef33 D Sharma     (bowler)        ← person.name = 'DB Sharma'
--   321644de AJ Healy     (batter)
--   de69af96 SFM Devine   (batter)
--   d32cf49a HK Matthews  (batter)
--
-- Curated WOMEN compare pairs (COMPARE_WOMEN, 3):
--   5d2eda89 × 52d1dbc8  Mandhana × Mooney
--   be150fc8 × 4ba0289e  Perry × Knight
--   321644de × 5d2eda89  Healy × Mandhana
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_landing_women.sql

.mode column
.headers on

.print 'L1 Curated women IDs exist:'
SELECT id, name
FROM   person
WHERE  id IN (
  '5d2eda89','be150fc8','4ba0289e','52d1dbc8','27e003ce',
  '201fef33','321644de','de69af96','d32cf49a'
)
ORDER  BY id;

.print ''
.print 'L2 Curated women IDs match counts (via matchplayer):'
SELECT mp.person_id AS id, COUNT(DISTINCT mp.match_id) AS matches
FROM   matchplayer mp
JOIN   match m ON m.id = mp.match_id
WHERE  m.gender = 'female'
  AND  mp.person_id IN (
    '5d2eda89','be150fc8','4ba0289e','52d1dbc8','27e003ce',
    '201fef33','321644de','de69af96','d32cf49a'
  )
GROUP  BY mp.person_id
ORDER  BY matches DESC;
