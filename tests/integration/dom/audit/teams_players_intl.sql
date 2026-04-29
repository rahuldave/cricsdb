-- Ground-truth SQL for tests/integration/dom/teams_players_intl.sh.
--
-- Closed window: Australia men_intl 2024-2025. The Players tab on
-- /teams renders one h3 section per season inside the window, with
-- a 3-col grid of player tiles (alphabetical). The audit pins:
--   • The set of seasons present (2025 / 2024/25 / 2024 — note the
--     "2024/25" mid-season entry covers the Australian summer
--     bridging two calendar years; appears alongside, not instead
--     of, calendar 2024 + 2025).
--   • Distinct-player count per season.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_players_intl.sql

.mode column
.headers on

-- P1: distinct Australia players per season in window.
SELECT m.season AS season, COUNT(DISTINCT mp.person_id) AS n_players
FROM   match m
JOIN   matchplayer mp ON mp.match_id = m.id
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2))
  AND  mp.team     = 'Australia'
GROUP  BY m.season
ORDER  BY m.season DESC;
