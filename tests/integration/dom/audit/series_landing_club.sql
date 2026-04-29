-- Ground-truth SQL for tests/integration/dom/series_landing_club.sh.
--
-- Closed window: men's club, calendar 2025. The /series landing
-- splits club events into Franchise / Domestic / Women_franchise /
-- Other; we assert tile presence + match count for the franchise
-- and domestic buckets. NO team_class filter — that's an intl-only
-- narrowing (clubs don't have full-member status).
--
-- Note: BBL 2024/25 lives under season "2024/25" (cricket-summer
-- spans two calendar years), NOT season "2025", so it does NOT
-- surface in this anchor. The intl twin (series_landing_intl_fm.sh)
-- exercises a season range; this anchor pins the single calendar
-- 2025 snapshot.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_landing_club.sql

.mode column
.headers on

-- L1: club tournaments + match counts in calendar 2025 (top by volume).
SELECT m.event_name AS event_name, COUNT(*) AS matches
FROM   match m
WHERE  m.team_type = 'club'
  AND  m.gender    = 'male'
  AND  m.season    = '2025'
GROUP  BY m.event_name
ORDER  BY matches DESC
LIMIT  12;
