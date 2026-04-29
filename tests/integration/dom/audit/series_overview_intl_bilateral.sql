-- Ground-truth SQL for tests/integration/dom/series_overview_intl_bilateral.sh.
--
-- Closed window: India vs England men_intl 2024-25, bilateral-only.
-- Picked because:
--   - Aus-vs-Ind 24-25 has 0 bilateral matches (the only meeting was
--     a T20 WC SF) — too thin to anchor.
--   - Ind-vs-Eng 24-25 = 5 bilateral matches across the England
--     tour of India in Jan/Feb 2025. India won 4, England won 1.
--     Rich enough to assert the rivalry h2h cards + the by_team
--     break-out blocks.
--
-- "bilateral-only" semantically means: same two teams playing each
-- other in something OTHER than an ICC event. The audit pins this
-- with `event_name NOT LIKE 'ICC%'`.
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/series_overview_intl_bilateral.sql

.mode column
.headers on

-- B1: Ind-vs-Eng bilateral count + result split.
SELECT 'B1 Ind-vs-Eng bilateral 24-25' AS lbl,
  COUNT(*)                                                AS matches,
  SUM(CASE WHEN m.outcome_winner = 'India'   THEN 1 ELSE 0 END) AS ind_wins,
  SUM(CASE WHEN m.outcome_winner = 'England' THEN 1 ELSE 0 END) AS eng_wins,
  SUM(CASE WHEN m.outcome_result = 'tie'     THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.team_type = 'international'
  AND  m.gender    = 'male'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ((m.team1 = 'India'   AND m.team2 = 'England')
     OR (m.team1 = 'England' AND m.team2 = 'India'))
  AND  m.event_name NOT LIKE 'ICC%';
