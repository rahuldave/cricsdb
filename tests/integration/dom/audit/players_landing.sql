-- Ground-truth SQL for tests/integration/dom/players_landing.sh.
--
-- The /players landing renders curated tiles whose person_ids come
-- from `frontend/src/components/players/CuratedLists.ts` — NOT from
-- a backend endpoint. The audit confirms each curated id resolves
-- to a real person in the DB AND has match activity (otherwise the
-- tile's stat-strip would render '0 m').
--
-- Curated MEN profile tiles (PROFILE_MEN, 9):
--   ba607b88 V Kohli       (batter)
--   462411b3 JJ Bumrah     (bowler)
--   30a45b23 SPD Smith     (batter)
--   740742ef RG Sharma     (batter)
--   99b75528 JC Buttler    (batter)
--   e798611a HM Amla       (batter)
--   8a75e999 Babar Azam    (batter)
--   d027ba9f KS Williamson (batter)
--   0f721006 JO Holder     (bowler)
--
-- Curated MEN compare pairs (COMPARE_MEN, 5):
--   ba607b88 × 6a26221c  V Kohli × AK Markram
--   30a45b23 × a343262c  SPD Smith × JE Root
--   462411b3 × e62dd25d  JJ Bumrah × K Rabada
--   e087956b × fe93fd9d  BA Stokes × RA Jadeja
--   99b75528 × 2b6e6dec  JC Buttler × AC Gilchrist
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/players_landing.sql

.mode column
.headers on

-- L1: every curated id resolves to a person.
.print 'L1 Curated ids exist:'
SELECT id, name
FROM   person
WHERE  id IN (
  -- Profile tiles
  'ba607b88','462411b3','30a45b23','740742ef','99b75528',
  'e798611a','8a75e999','d027ba9f','0f721006',
  -- Compare-only second-side ids
  '6a26221c','a343262c','e62dd25d','e087956b','fe93fd9d','2b6e6dec'
)
ORDER  BY id;

-- L2: each curated id has match activity (matchplayer presence).
-- A tile with 0 matches across the entire DB would render '0 m'
-- on the stat-strip — caught here.
.print ''
.print 'L2 Curated ids match counts:'
SELECT mp.person_id AS id, COUNT(DISTINCT mp.match_id) AS matches
FROM   matchplayer mp
WHERE  mp.person_id IN (
  'ba607b88','462411b3','30a45b23','740742ef','99b75528',
  'e798611a','8a75e999','d027ba9f','0f721006',
  '6a26221c','a343262c','e62dd25d','e087956b','fe93fd9d','2b6e6dec'
)
GROUP  BY mp.person_id
ORDER  BY matches DESC;
