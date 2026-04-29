-- Ground-truth SQL for tests/integration/dom/teams_batting_intl.sh.
--
-- Closed window: Australia, men's T20I 2024-2025. Asserts the
-- foundational numbers behind the Batting tab's StatCard grid.
-- Derived metrics (boundary %, dot %, etc.) are downstream of the
-- same delivery query — the chip math invariant in the DOM test
-- catches drift on those.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_batting_intl.sql

.mode column
.headers on

-- B1: Aus innings_batted in window.
SELECT 'B1 Aus innings_batted' AS lbl,
       COUNT(*) AS innings
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- B2: Aus total runs + legal balls + run rate.
-- run_rate = SUM(runs_total) × 6 / count(legal_balls)  (CLAUDE.md
-- "Run rate: Concatenated rate"). Legal = wides=0 AND noballs=0.
SELECT 'B2 Aus runs/balls/RR' AS lbl,
       SUM(d.runs_total) AS total_runs,
       SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                THEN 1 ELSE 0 END) AS legal_balls,
       ROUND(SUM(d.runs_total) * 6.0 /
             SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                      THEN 1 ELSE 0 END), 2) AS run_rate
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- B3: Aus 4s + 6s.
-- Fours: runs_batter=4 AND runs_non_boundary=0 (excludes all-run 4s
-- where batters ran four between wickets — cricsheet's
-- runs_non_boundary flag marks these). Sixes: runs_batter=6 (every
-- 6 is a boundary by definition; no flag check). 6s on no-balls
-- count (the ball was illegal but the bat made contact). Run-rate
-- denominators DON'T count no-balls. Same formula
-- populate_bucket_baseline.py uses.
SELECT 'B3 Aus 4s + 6s' AS lbl,
       SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0
                THEN 1 ELSE 0 END) AS fours,
       SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Australia'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- Expected:
--   B1 = 22
--   B2 = total_runs:3614 (matches API), RR:9.91
--   B3 = 4s:304, 6s:201 (one of the 201 was hit off a no-ball)
