-- Ground-truth SQL for tests/integration/dom/charts_manhattan_intl.sh
-- and tests/integration/dom/charts_worm_intl.sh.
--
-- Anchor: WC 2024 Final (match_id=1551). Worm + Manhattan charts
-- consume scorecard by_over data; the audit derives those values
-- directly from delivery aggregates so the integration test
-- doesn't lean on the API.
--
-- Per-innings expected:
--   India 176/7 (20 ov)
--     Manhattan: 20 bars, range 3..17, mean 8.80
--     First 5 overs: 15, 8, 3, 6, 7
--   South Africa 169/8 (20 ov)
--     Manhattan: 20 bars, range 2..24, mean 8.45
--     First 5 overs: 6, 5, 3, 8, 10
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/charts_intl.sql

.mode column
.headers on

.print 'M1 Per-over runs for India (innings 1) WC 2024 Final:'
SELECT
  d.over_number + 1 AS over_num,
  SUM(d.runs_total) AS runs
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 1551
  AND  i.innings_number = 1
  AND  i.super_over = 0
GROUP  BY d.over_number
ORDER  BY d.over_number;

.print ''
.print 'M2 Per-over runs for South Africa (innings 2) WC 2024 Final:'
SELECT
  d.over_number + 1 AS over_num,
  SUM(d.runs_total) AS runs
FROM   delivery d
JOIN   innings  i ON i.id = d.innings_id
WHERE  i.match_id = 1551
  AND  i.innings_number = 2
  AND  i.super_over = 0
GROUP  BY d.over_number
ORDER  BY d.over_number;

.print ''
.print 'M3 Aggregate stats per innings (mean / range):'
SELECT
  i.innings_number,
  i.team,
  COUNT(DISTINCT d.over_number) AS overs,
  ROUND(AVG(over_runs.runs), 2) AS mean_per_over,
  MIN(over_runs.runs) AS min_over,
  MAX(over_runs.runs) AS max_over
FROM   innings i
JOIN   delivery d ON d.innings_id = i.id
JOIN (
  SELECT d2.innings_id, d2.over_number, SUM(d2.runs_total) AS runs
  FROM   delivery d2
  GROUP  BY d2.innings_id, d2.over_number
) over_runs ON over_runs.innings_id = i.id AND over_runs.over_number = d.over_number
WHERE  i.match_id = 1551
  AND  i.super_over = 0
GROUP  BY i.id;
