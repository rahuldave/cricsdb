-- Ground-truth SQL for tests/integration/dom/venues_overview_intl.sh.
--
-- Anchor: Eden Gardens (Kolkata), men_intl all-time. 18 men's
-- international T20s on cricsheet record at this venue, spanning
-- ICC events + bilateral tours from 2011/12 through 2025/26.
--
-- The Overview StatCard band renders:
--   Matches        18
--   Avg 1st-inn    164.6
--   Bat-first win% 50.0%   (4 of 8 decided)
--   Chase win %    50.0%   (4 of 8)
--   Tie / NR        0
--   Chose to bat    5
--   Chose to field 13
--   Won toss + bat 80.0%   (4/5)
--   Won toss + field 61.5% (8/13)
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_overview_intl.sql

.mode column
.headers on

.print 'V1 Eden men_intl total + toss-decision split:'
SELECT
  COUNT(*) AS matches,
  SUM(CASE WHEN m.toss_decision = 'bat'   THEN 1 ELSE 0 END) AS chose_bat,
  SUM(CASE WHEN m.toss_decision = 'field' THEN 1 ELSE 0 END) AS chose_field,
  SUM(CASE WHEN m.outcome_result = 'tie'        THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN m.outcome_result = 'no result'  THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.team_type   = 'international'
  AND  m.gender      = 'male'
  AND  m.venue       = 'Eden Gardens';

-- Bat-first / chase decided count (decided = match has outcome_winner).
.print ''
.print 'V2 Bat-first vs chase decided:'
WITH match_innings AS (
  SELECT
    m.id,
    m.outcome_winner,
    m.toss_winner,
    m.toss_decision
  FROM match m
  WHERE m.team_type='international' AND m.gender='male'
    AND m.venue='Eden Gardens'
    AND m.outcome_winner IS NOT NULL
)
SELECT
  COUNT(*) AS decided_matches,
  -- bat-first wins: toss winner chose bat AND won, OR toss winner
  -- chose field AND lost (the other side batted first and won).
  SUM(CASE WHEN
    (toss_decision='bat'   AND outcome_winner = toss_winner) OR
    (toss_decision='field' AND outcome_winner != toss_winner)
    THEN 1 ELSE 0 END) AS bat_first_wins
FROM match_innings;
