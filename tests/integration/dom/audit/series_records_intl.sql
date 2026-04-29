-- Ground-truth SQL for tests/integration/dom/series_records_intl.sh.
--
-- Closed window: T20 World Cup Men 2024. Asserts top + bottom of
-- the "Highest team totals" DataTable on the /series ?tab=Records
-- surface (first table on the page; extract_data_table grabs it).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_records_intl.sql

.mode column
.headers on

-- SR1: Top 10 highest team totals in T20 WC Men 2024 — the dossier
-- requests limit=10 from /series/records. Tiebreak by match_id ASC
-- (matches the API's ordering for tied scores).
SELECT 'SR1 highest team totals' AS lbl,
       i.team AS team,
       (SELECT SUM(d.runs_total) FROM delivery d WHERE d.innings_id = i.id) AS runs,
       (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date,
       CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS opponent
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  m.event_name = 'ICC Men''s T20 World Cup'
  AND  m.gender = 'male' AND m.team_type = 'international'
  AND  m.season = '2024'
ORDER  BY runs DESC, m.id ASC
LIMIT  10;

-- Expected (matches API with limit=10):
--    1. India        205 vs Australia    (2024-06-24)
--    2. Australia    201 vs England      (2024-06-08)
--    3. Sri Lanka    201 vs Netherlands  (2024-06-16)
--    4. USA          197 vs Canada       (2024-06-01)
--    5. India        196 vs Bangladesh   (2024-06-22)
--    6. Canada       194 vs USA          (2024-06-01)
--    7. South Africa 194 vs USA          (2024-06-19)
--    8. Australia    186 vs Scotland     (2024-06-15)
--    9. England      181 vs West Indies  (2024-06-19)
--   10. Australia    181 vs India        (2024-06-24)
