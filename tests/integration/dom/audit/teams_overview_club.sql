-- Ground-truth SQL for tests/integration/dom/teams_overview_club.sh.
--
-- Closed window: Royal Challengers Bengaluru, IPL 2025 (74-match
-- season). Asserts the always-on summary band on /teams?team=RCB.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_overview_club.sql

.mode column
.headers on

-- O1: RCB matches + wins + losses + ties + NRs in IPL 2025.
SELECT 'O1 RCB IPL 2025 results' AS lbl,
       COUNT(*) AS matches,
       SUM(CASE WHEN m.outcome_winner = 'Royal Challengers Bengaluru' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN m.outcome_winner IS NOT NULL
                 AND m.outcome_winner != 'Royal Challengers Bengaluru' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
       SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2));

-- O2: RCB win % = 11/15 × 100 = 73.33 → 73.3 (1-decimal)

-- O3: Distinct keepers used by RCB in IPL 2025.
SELECT 'O3 RCB IPL 2025 keepers' AS lbl,
       COUNT(DISTINCT ka.keeper_id) AS distinct_keepers
FROM   keeperassignment ka
JOIN   innings i ON i.id = ka.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  ka.keeper_id IS NOT NULL
  AND  i.team = 'Royal Challengers Bengaluru'
  AND  m.gender    = 'male'
  AND  m.team_type = 'club'
  AND  m.event_name = 'Indian Premier League'
  AND  m.season   = '2025';

-- Expected:
--   O1 = matches:15 wins:11 losses:4 ties:0 no_results:0
--   O2 = 11*100/15 = 73.33 → 73.3
--   O3 = at least 1 (API summary returns 1 — Jitesh Sharma)
