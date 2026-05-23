#!/bin/bash
# Bowling By Over tab — Boundaries-conceded-per-over comparative chart.
# User-asked 2026-05-22 follow-up to the per-phase boundaries chart.
#
# Asserts:
#   1. /bowlers/{id}/summary's over_distribution entries carry a new
#      `cohort_boundaries_per_over` field (non-null at over=1, the
#      most-bowled over in the population).
#   2. SQL anchor: cohort_boundaries_per_over at over=1 matches a
#      direct aggregate over `playerscopestatsover`.
#   3. The "Boundaries conceded per over" chart title renders on the
#      By Over tab.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=462411b3
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB="${DB:-$PROJECT_ROOT/cricket.db}"

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_bpo=$(curl -sS "$API/api/v1/bowlers/$PLAYER/summary?gender=male" \
  | python3 -c "
import json,sys
od=json.load(sys.stdin)['over_distribution']
e=next(x for x in od if x['over']==1)
v=e.get('cohort_boundaries_per_over')
print('MISSING' if v is None else f'{v:.3f}')")
echo "  API cohort_boundaries_per_over (over=1): $api_bpo"
if [ "$api_bpo" = "MISSING" ]; then
  bad "field missing from API"
else
  ok "API exposes cohort_boundaries_per_over"
fi

sql_bpo=$(sqlite3 "$DB" <<'SQL'
SELECT ROUND(SUM(psso.boundaries) * 6.0 / SUM(psso.legal_balls), 3)
FROM playerscopestatsover psso
WHERE psso.over_number = 1
  AND psso.scope_key IN (
    SELECT scope_key FROM playerscopestats pss
    WHERE pss.gender = 'male'
  );
SQL
)
echo "  SQL cohort_boundaries_per_over (over=1): $sql_bpo"
diff_abs=$(python3 -c "print(round(abs(float('$api_bpo') - float('$sql_bpo')), 3))" 2>/dev/null || echo MISMATCH)
if [ "$diff_abs" != "MISMATCH" ] && python3 -c "import sys; sys.exit(0 if float('$diff_abs') < 0.01 else 1)"; then
  ok "API matches SQL (diff $diff_abs)"
else
  bad "API !~ SQL ($api_bpo vs $sql_bpo)"
fi

ab open "$BASE/bowling?player=$PLAYER&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait --text "Boundaries conceded per over"
ab wait 2000
has_title=$(ab_eval "document.body.innerText.includes('Boundaries conceded per over')")
if [ "$has_title" = "true" ]; then
  ok "Boundaries conceded per over chart renders on By Over tab"
else
  bad "chart title missing"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
