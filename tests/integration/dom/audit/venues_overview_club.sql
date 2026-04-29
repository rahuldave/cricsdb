-- Ground-truth SQL for tests/integration/dom/venues_overview_club.sh.
--
-- Anchor: Wankhede Stadium (Mumbai), IPL 2025. 7 matches at MI's
-- home ground in 2025. All 7 toss winners chose to FIELD (the
-- modern dew-friendly chase preference); 4 chasing teams won (57.1%).
--
-- Run: sqlite3 cricket.db < tests/integration/dom/audit/venues_overview_club.sql

.mode column
.headers on

.print 'V1 Wankhede IPL 2025 total + toss-decision split:'
SELECT
  COUNT(*) AS matches,
  SUM(CASE WHEN m.toss_decision = 'bat'   THEN 1 ELSE 0 END) AS chose_bat,
  SUM(CASE WHEN m.toss_decision = 'field' THEN 1 ELSE 0 END) AS chose_field,
  SUM(CASE WHEN m.outcome_result = 'tie'        THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN m.outcome_result = 'no result'  THEN 1 ELSE 0 END) AS no_results
FROM   match m
WHERE  m.team_type   = 'club'
  AND  m.gender      = 'male'
  AND  m.event_name  = 'Indian Premier League'
  AND  m.season      = '2025'
  AND  m.venue       = 'Wankhede Stadium';

.print ''
.print 'V2 Bat-first vs chase decided:'
SELECT
  COUNT(*) AS decided_matches,
  SUM(CASE WHEN
    (m.toss_decision='bat'   AND m.outcome_winner = m.toss_winner) OR
    (m.toss_decision='field' AND m.outcome_winner != m.toss_winner)
    THEN 1 ELSE 0 END) AS bat_first_wins
FROM match m
WHERE m.team_type='club' AND m.gender='male'
  AND m.event_name='Indian Premier League' AND m.season='2025'
  AND m.venue='Wankhede Stadium'
  AND m.outcome_winner IS NOT NULL;
