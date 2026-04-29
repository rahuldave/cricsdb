-- Ground-truth SQL for tests/integration/dom/teams_players_club.sh.
--
-- Closed window: RCB, IPL 2025. Single closed-league season → exactly
-- one h3 section ("2025 (19)"). 19 distinct players appeared in RCB's
-- XI across the 15-match campaign.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_players_club.sql

.mode column
.headers on

-- P1: distinct RCB players in IPL 2025.
SELECT m.season AS season, COUNT(DISTINCT mp.person_id) AS n_players
FROM   match m
JOIN   matchplayer mp ON mp.match_id = m.id
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  ('Royal Challengers Bengaluru' IN (m.team1, m.team2))
  AND  mp.team       = 'Royal Challengers Bengaluru'
GROUP  BY m.season;
