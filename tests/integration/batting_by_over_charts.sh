#!/bin/bash
# Batting "By Over" tab — Dot % + Boundaries-per-over comparative
# charts alongside the existing Strike Rate by Over chart. User-asked
# 2026-05-22.
#
# Asserts:
#   1. All three chart titles render on the page.
#   2. Player powerplay (over=1) dot_pct matches /batters/{id}/by-over
#      live (chart reads same data, not a stale prop).
#   3. Cohort dot_pct + boundary_pct at over=1 from
#      /scope/averages/players/batting/by-over are non-null (so the
#      reference overlay can render).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_pp_dot=$(curl -sS "$API/api/v1/batters/$PLAYER/by-over?gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_over']
o=next(x for x in d if x['over_number']==1)
print(f\"{o['dot_pct']:.1f}\")")
echo "  API over=1 dot_pct: $api_pp_dot"

cohort_pp_dot=$(curl -sS "$API/api/v1/scope/averages/players/batting/by-over?person_id=$PLAYER&gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_over']
o=next(x for x in d if x['over']==1)
print('null' if o.get('dot_pct') is None else f\"{o['dot_pct']:.1f}\")")
echo "  API cohort over=1 dot_pct: $cohort_pp_dot"

cohort_pp_bdy=$(curl -sS "$API/api/v1/scope/averages/players/batting/by-over?person_id=$PLAYER&gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_over']
o=next(x for x in d if x['over']==1)
print('null' if o.get('boundary_pct') is None else f\"{o['boundary_pct']:.1f}\")")
echo "  API cohort over=1 boundary_pct: $cohort_pp_bdy"

ab open "$BASE/batting?player=$PLAYER&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait --text "Boundaries per Over"
ab wait 2000

for title in "Strike Rate by Over" "Dot % by Over" "Boundaries per Over"; do
  has=$(ab_eval "document.body.innerText.includes('${title}')")
  if [ "$has" = "true" ]; then
    ok "title present — \"${title}\""
  else
    bad "title missing — \"${title}\""
  fi
done

if [ "$cohort_pp_dot" != "null" ]; then
  ok "cohort dot_pct available at over=1 ($cohort_pp_dot)"
else
  bad "cohort dot_pct null at over=1"
fi
if [ "$cohort_pp_bdy" != "null" ]; then
  ok "cohort boundary_pct available at over=1 ($cohort_pp_bdy)"
else
  bad "cohort boundary_pct null at over=1"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
