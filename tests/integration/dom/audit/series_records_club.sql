-- Ground-truth SQL for tests/integration/dom/series_records_club.sh.
--
-- Closed window: IPL 2025. Top 10 highest team totals (dossier
-- requests limit=10 from /series/records).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_records_club.sql

.mode column
.headers on

SELECT 'SR1 highest team totals' AS lbl,
       i.team AS team,
       (SELECT SUM(d.runs_total) FROM delivery d WHERE d.innings_id = i.id) AS runs,
       (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date,
       CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS opponent
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  m.event_name = 'Indian Premier League'
  AND  m.gender = 'male' AND m.team_type = 'club'
  AND  m.season = '2025'
ORDER  BY runs DESC, m.id ASC
LIMIT  10;

-- Expected (matches API):
--    1. SRH 286 vs RR        (2025-03-23)
--    2. SRH 278 vs KKR       (2025-05-25)
--    ...
--   10. KKR 234 vs LSG       (2025-04-08)
