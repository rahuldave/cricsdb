-- Ground-truth SQL for tests/integration/dom/teams_batting_club.sh.
--
-- Closed window: Royal Challengers Bengaluru, IPL 2025. Foundational
-- numbers (innings, runs, RR, 4s/6s) for the Batting tab StatCard
-- grid. Derived metrics (boundary %, dot %, etc.) are downstream of
-- the same delivery query — chip math invariant in the DOM test
-- catches drift on those.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_batting_club.sql

.mode column
.headers on

-- B1: RCB innings_batted in IPL 2025.
SELECT 'B1 RCB innings_batted' AS lbl, COUNT(*) AS innings
FROM   innings i
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Royal Challengers Bengaluru'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- B2: RCB total runs + legal balls + run rate.
SELECT 'B2 RCB runs/balls/RR' AS lbl,
       SUM(d.runs_total) AS total_runs,
       SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                THEN 1 ELSE 0 END) AS legal_balls,
       ROUND(SUM(d.runs_total) * 6.0 /
             SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                      THEN 1 ELSE 0 END), 2) AS run_rate
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Royal Challengers Bengaluru'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- B3: RCB 4s + 6s. Same formula as audit/teams_batting_intl.sql B3:
-- runs_batter=4 AND runs_non_boundary=0 for fours; runs_batter=6 for
-- sixes. Mirrors populate_bucket_baseline.py's per-cell aggregation.
SELECT 'B3 RCB 4s + 6s' AS lbl,
       SUM(CASE WHEN d.runs_batter = 4 AND COALESCE(d.runs_non_boundary, 0) = 0
                THEN 1 ELSE 0 END) AS fours,
       SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
FROM   delivery d
JOIN   innings i ON i.id = d.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  i.team = 'Royal Challengers Bengaluru'
  AND  i.super_over = 0
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- Expected:
--   B1 = 15
--   B2 = total_runs:2653, legal_balls:1644, RR:9.69
--   B3 = 4s:238, 6s:125
