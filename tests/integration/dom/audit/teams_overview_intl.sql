-- Ground-truth SQL for tests/integration/dom/teams_overview_intl.sh.
--
-- Closed window: Aus T20Is 2024-2025. Asserts the always-on summary
-- band on /teams?team=Australia (the headline matches/wins/losses/
-- win% StatCards above the tabs).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/teams_overview_intl.sql

.mode column
.headers on

-- O1: Aus matches + wins + losses + ties + NRs in window.
SELECT 'O1 Aus 24-25 results' AS lbl,
       COUNT(*) AS matches,
       SUM(CASE WHEN m.outcome_winner = 'Australia' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN m.outcome_winner IS NOT NULL
                 AND m.outcome_winner != 'Australia' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
       SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025'
  AND  ('Australia' IN (m.team1, m.team2));

-- O2: Win % derived from O1 — the team-side rate is a simple
-- wins / matches × 100 (not the per-team avg formula). Assert
-- 19 / 22 × 100 = 86.4 (rounded to 1 decimal).

-- O3: Number of distinct keeper_ids that kept for Aus in window.
-- (The summary band's keepers list is sourced from
-- keeperassignment ∩ matchplayer with confidence ≠ NULL — see
-- internal_docs/spec-fielding-tier2.md.)
SELECT 'O3 Aus keepers in window' AS lbl,
       COUNT(DISTINCT ka.keeper_id) AS distinct_keepers
FROM   keeperassignment ka
JOIN   innings i ON i.id = ka.innings_id
JOIN   match   m ON m.id = i.match_id
WHERE  ka.keeper_id IS NOT NULL
  AND  i.team = 'Australia'
  AND  m.gender    = 'male'
  AND  m.team_type = 'international'
  AND  m.season   >= '2024'
  AND  m.season   <= '2025';

-- Expected:
--   O1 = matches:22 wins:19 losses:3 ties:0 no_results:0
--   O2 = win% = 19*100/22 = 86.36 → 86.4 (1-decimal)
--   O3 = at least 1 (the API summary returns 3 — Inglis, Wade, Carey)
