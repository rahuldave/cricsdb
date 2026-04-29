-- Ground-truth SQL for tests/integration/dom/charts_manhattan_club.sh.
--
-- Anchor: IPL 2025 Final (match_id=6018, RCB v PBKS).
--   RCB:  190/9 (20 ov)  → mean 9.50, range 3..23, first 5 = 13/6/11/9/7
--   PBKS: 184/7 (20 ov)  → mean 9.20, range 3..22, first 5 = 13/10/5/4/11
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/charts_manhattan_club.sql

.mode column
.headers on

.print 'M1 Per-over runs IPL 2025 Final innings 1 (RCB):'
SELECT
  d.over_number + 1 AS over_num,
  SUM(d.runs_total) AS runs
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 6018
  AND  i.innings_number = 1
  AND  i.super_over = 0
GROUP  BY d.over_number
ORDER  BY d.over_number;

.print ''
.print 'M2 Per-over runs IPL 2025 Final innings 2 (PBKS):'
SELECT
  d.over_number + 1 AS over_num,
  SUM(d.runs_total) AS runs
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 6018
  AND  i.innings_number = 2
  AND  i.super_over = 0
GROUP  BY d.over_number
ORDER  BY d.over_number;
