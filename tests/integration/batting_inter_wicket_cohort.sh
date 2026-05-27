#!/bin/bash
# Batting · Inter-Wicket SR chart now carries a cohort SR reference
# line — drawn from the new `cohort_strike_rate` field attached to
# every entry of /batters/{id}/inter-wicket.
#
# Asserts:
#   1. API: each inter_wicket entry has a `cohort_strike_rate` field
#      (non-null for at least the early wickets-down buckets where
#      every batter has had a turn).
#   2. SQL anchor: cohort_strike_rate at wickets_down=0 matches a
#      direct delivery-level recompute against `cricket.db`.
#   3. Chart: the player line + cohort line both render — the
#      LineChart's reference-overlay merges them into a single chart,
#      so we look for the legend showing "cohort SR at scope" + the
#      "player" label.
#
# Red-before-green: HEAD~1 (the regression-flip commit) lacks the
# cohort field on the response, so assertions 1 + 2 fail and 3 fails
# because LineChart has no referenceData to draw.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB="${DB:-$PROJECT_ROOT/cricket.db}"

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# 1. API field present.
api_payload=$(curl -sS "$API/api/v1/batters/$PLAYER/inter-wicket?gender=male&team_type=international")
api_csr_wd0=$(echo "$api_payload" | python3 -c "
import json,sys
arr=json.load(sys.stdin)['inter_wicket']
row=next(r for r in arr if r['wickets_down']==0)
v=row.get('cohort_strike_rate')
print(v if v is not None else 'MISSING')")
echo "  API cohort_strike_rate at wd=0: $api_csr_wd0"
if [ "$api_csr_wd0" = "MISSING" ]; then
  bad "/inter-wicket response missing cohort_strike_rate field"
else
  ok "/inter-wicket response carries cohort_strike_rate at wd=0"
fi

# 2. SQL anchor at wd=0 — same window-function aggregate the endpoint
# uses, against the same scope (gender=male, team_type=international).
# All-ball convention (spec-batting-allball-runs-single-source.md §X9):
# runs summed over ALL deliveries at this wickets-down state, balls the
# legal-only count — matching _inter_wicket_cohort_sr after the fix.
sql_csr_wd0=$(sqlite3 "$DB" <<'SQL'
WITH delivery_wd AS (
  SELECT
    d.runs_batter,
    d.extras_wides,
    d.extras_noballs,
    (
      SUM(CASE WHEN w.id IS NOT NULL
                   AND COALESCE(w.kind, '') NOT IN ('retired hurt','retired out')
              THEN 1 ELSE 0 END)
        OVER (PARTITION BY d.innings_id ORDER BY d.id
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
      - CASE WHEN w.id IS NOT NULL
                 AND COALESCE(w.kind, '') NOT IN ('retired hurt','retired out')
            THEN 1 ELSE 0 END
    ) AS wickets_down
  FROM delivery d
  LEFT JOIN wicket w ON w.delivery_id = d.id
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE m.gender = 'male' AND m.team_type = 'international'
    AND i.super_over = 0
)
SELECT ROUND(
         SUM(COALESCE(runs_batter,0)) * 100.0
         / SUM(CASE WHEN extras_wides = 0 AND extras_noballs = 0 THEN 1 ELSE 0 END), 2)
FROM delivery_wd
WHERE wickets_down = 0;
SQL
)
echo "  SQL cohort_strike_rate at wd=0: $sql_csr_wd0"
diff_abs=$(python3 -c "print(round(abs(float('$api_csr_wd0') - float('$sql_csr_wd0')), 2))" 2>/dev/null || echo MISMATCH)
if [ "$diff_abs" != "MISMATCH" ] && python3 -c "import sys; sys.exit(0 if float('$diff_abs') < 0.05 else 1)"; then
  ok "API cohort_strike_rate matches direct SQL (diff $diff_abs)"
else
  bad "API cohort_strike_rate does NOT match SQL (api=$api_csr_wd0, sql=$sql_csr_wd0)"
fi

# 3. Chart renders both lines (legend contains both labels).
ab open "$BASE/batting?player=$PLAYER&gender=male&team_type=international&tab=Inter-Wicket"
ab wait --load networkidle
ab wait --text "Strike Rate by Wickets Down"
ab wait 2500
has_cohort_label=$(ab_eval "document.body.innerText.includes('cohort SR at scope')")
has_player_label=$(ab_eval "document.body.innerText.includes('player')")
if [ "$has_cohort_label" = "true" ] && [ "$has_player_label" = "true" ]; then
  ok "chart legend shows both player + cohort series"
else
  bad "chart legend missing one of player / cohort labels (player=$has_player_label, cohort=$has_cohort_label)"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
