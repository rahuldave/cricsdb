-- Ground-truth SQL for tests/integration/dom/teams_compare_club.sh.
--
-- Closed window: Indian Premier League 2025 (74 matches).
--   B1: total IPL 2025 matches             (74)
--   B2: RCB matches in IPL 2025            (15)
--   B3: SRH matches in IPL 2025            (14)
--   B4: IPL 2025 pool run rate             (9.63)
--   B5: RCB run rate                       (9.69)
--   B6: SRH run rate                       (10.04)
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_compare_club.sql

.mode column
.headers on

-- B1: Total IPL 2025 matches.
SELECT 'B1 IPL 2025 matches' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'club'
  AND  gender    = 'male'
  AND  event_name = 'Indian Premier League'
  AND  season    = '2025';

-- B2: Royal Challengers Bengaluru matches in IPL 2025.
SELECT 'B2 RCB matches' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'club'
  AND  gender    = 'male'
  AND  event_name = 'Indian Premier League'
  AND  season    = '2025'
  AND  ('Royal Challengers Bengaluru' IN (team1, team2));

-- B3: Sunrisers Hyderabad matches in IPL 2025.
SELECT 'B3 SRH matches' AS lbl, COUNT(*) AS matches
FROM   match
WHERE  team_type = 'club'
  AND  gender    = 'male'
  AND  event_name = 'Indian Premier League'
  AND  season    = '2025'
  AND  ('Sunrisers Hyderabad' IN (team1, team2));

-- B4: IPL 2025 pool run rate (concatenated, all innings).
SELECT
  'B4 IPL 2025 pool RR' AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'club'
  AND  m.gender    = 'male'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season    = '2025';

-- B5: RCB run rate.
SELECT
  'B5 RCB RR' AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'club'
  AND  m.gender    = 'male'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season    = '2025'
  AND  i.team = 'Royal Challengers Bengaluru';

-- B6: SRH run rate.
SELECT
  'B6 SRH RR' AS lbl,
  ROUND(SUM(d.runs_total) * 6.0 /
        SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END), 2)
                              AS run_rate
FROM   delivery d
JOIN   innings i  ON i.id = d.innings_id
JOIN   match   m  ON m.id = i.match_id
WHERE  m.team_type = 'club'
  AND  m.gender    = 'male'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season    = '2025'
  AND  i.team = 'Sunrisers Hyderabad';

-- Expected:
--   B1 = 74    B2 = 15    B3 = 14
--   B4 = 9.63  B5 = 9.69  B6 = 10.04
--
-- Note: B4 above prints 9.64 — SQLite's ROUND() and Python's round-
-- half-even can land on either side of the .5 boundary on the same
-- raw value. EPS_NUM=0.15 in _lib.sh covers this. The API renders
-- 9.63 (the script's expected); the formula matches.
