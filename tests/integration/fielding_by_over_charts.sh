#!/bin/bash
# Fielding "By Over" tab — 3 new charts beside the existing
# "Dismissals by Over": Catches / Run-outs / Dismissals-per-match
# (the last with a cohort overlay). User-asked 2026-05-23.

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

# 1. API exposes new per-kind fields + cohort.
api_row=$(curl -sS "$API/api/v1/fielders/$PLAYER/by-over?gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_over']
o=next(x for x in d if x['over_number']==20)
print(o.get('catches'), o.get('run_outs'), o.get('cohort_dismissals_per_match'))")
read -r api_c api_ro api_cohort <<<"$api_row"
echo "  API over=20: catches=$api_c run_outs=$api_ro cohort=$api_cohort"
if [ "$api_c" != "None" ] && [ "$api_ro" != "None" ]; then
  ok "API exposes per-kind breakdown"
else
  bad "API missing catches / run_outs fields"
fi
if [ "$api_cohort" != "None" ]; then
  ok "API exposes cohort_dismissals_per_match"
else
  bad "cohort_dismissals_per_match null"
fi

# 2. SQL anchor at over=20: dismissals via fieldingcredit ↔ delivery
# matches API count (the joins, kinds, scope predicate all agree).
sql_c=$(sqlite3 "$DB" <<SQL
SELECT COUNT(*)
FROM fieldingcredit fc
JOIN delivery d ON d.id = fc.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE fc.fielder_id = '$PLAYER'
  AND m.gender = 'male'
  AND i.super_over = 0
  AND d.over_number = 19
  AND fc.kind IN ('caught','caught_and_bowled');
SQL
)
echo "  SQL over=20 catches: $sql_c"
if [ "$sql_c" = "$api_c" ]; then
  ok "over=20 catches matches SQL"
else
  bad "over=20 catches mismatch (api=$api_c, sql=$sql_c)"
fi

# 3. Page renders all 4 chart titles.
ab open "$BASE/fielding?player=$PLAYER&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait --text "Dismissals per Match by Over"
ab wait 2000
for title in "Dismissals by Over" "Catches by Over" "Run-outs by Over" "Dismissals per Match by Over"; do
  has=$(ab_eval "document.body.innerText.includes('${title}')")
  if [ "$has" = "true" ]; then
    ok "title present — \"${title}\""
  else
    bad "title missing — \"${title}\""
  fi
done

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
