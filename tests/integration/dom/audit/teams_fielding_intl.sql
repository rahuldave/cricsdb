-- Ground-truth SQL for tests/integration/dom/teams_fielding_intl.sh.
--
-- Closed window: Australia, men's T20I 2024-2025. Fielding credits
-- link wicket → delivery → innings; the fielding team is the opponent
-- of the BATTING innings (i.team != team AND team in m.team1/m.team2).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_fielding_intl.sql

.mode column
.headers on

-- F1: Aus fielding-credit counts by kind. The fielding TEAM is the
-- non-batting side of any innings in an Aus match (i.team != 'Aus'
-- AND 'Aus' ∈ m.team1/m.team2). API's `catches` field is INCLUSIVE
-- (catches_only + caught_and_bowled) per CLAUDE.md "wides/noballs/
-- catches semantic". `caught_and_bowled` is exposed separately;
-- consumers MUST NOT add catches + c&b (would double-count).
SELECT 'F1 Aus fielding by kind' AS lbl,
       SUM(CASE WHEN fc.kind = 'caught'             THEN 1 ELSE 0 END) AS catches_only,
       SUM(CASE WHEN fc.kind = 'caught_and_bowled'  THEN 1 ELSE 0 END) AS caught_and_bowled,
       SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled')
                                                    THEN 1 ELSE 0 END) AS catches_inclusive,
       SUM(CASE WHEN fc.kind = 'stumped'            THEN 1 ELSE 0 END) AS stumpings,
       SUM(CASE WHEN fc.kind = 'run_out'            THEN 1 ELSE 0 END) AS run_outs
FROM   fieldingcredit fc
JOIN   wicket   w ON w.id = fc.wicket_id
JOIN   delivery d ON d.id = fc.delivery_id
JOIN   innings  i ON i.id = d.innings_id
JOIN   match    m ON m.id = i.match_id
WHERE  i.super_over = 0
  AND  i.team != 'Australia'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- F2: Derived per-match rates from F1 + matches=22 (from O1 in
-- audit/teams_overview_intl.sql):
--   catches_per_match  = 125 / 22 = 5.68
--   stumpings/match    =   2 / 22 = 0.09
--   run-outs/match     =   9 / 22 = 0.41

-- Expected:
--   F1 = catches_only:124, caught_and_bowled:1, catches_inclusive:125
--        stumpings:2, run_outs:9
--   The DOM's "Catches" StatCard reads catches_inclusive (125).
