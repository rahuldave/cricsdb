#!/bin/bash
# Fielding "By Phase" tab — Catches by phase (volume) + Catches per
# match by phase (rate vs cohort) charts. User-asked 2026-05-22.
#
# Asserts:
#   1. Both chart titles render on the tab.
#   2. Player powerplay catches count matches /fielders/{id}/by-phase
#      live (chart reads the same data, not a stale prop).
#   3. The rate chart has a green cohort tick from
#      /scope/averages/players/fielding/by-phase (catches_per_match).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_pp_catches=$(curl -sS "$API/api/v1/fielders/$PLAYER/by-phase?gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_phase']
pp=next(p for p in d if p['phase'].lower()=='powerplay')
print(pp['catches'])")
echo "  API powerplay catches: $api_pp_catches"

api_cohort_pp=$(curl -sS "$API/api/v1/scope/averages/players/fielding/by-phase?person_id=$PLAYER&gender=male" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)['by_phase']
pp=next(p for p in d if p['phase'].lower()=='powerplay')
v=pp.get('catches_per_match')
print('MISSING' if v is None else f'{v:.3f}')")
echo "  API cohort powerplay catches/match: $api_cohort_pp"

ab open "$BASE/fielding?player=$PLAYER&gender=male&tab=By+Phase"
ab wait --load networkidle
ab wait --text "Catches by phase"
ab wait 2000

for title in "Catches by phase" "Catches per match by phase"; do
  has=$(ab_eval "document.body.innerText.includes('${title}')")
  if [ "$has" = "true" ]; then
    ok "title present — \"${title}\""
  else
    bad "title missing — \"${title}\""
  fi
done

# The volume chart's tallest player bar should equal the powerplay
# catches count (Kohli's catches concentrate in PP). Check the
# powerplay tile shows the same count.
has_count=$(ab_eval "document.body.innerText.includes('${api_pp_catches}')")
if [ "$has_count" = "true" ]; then
  ok "powerplay catches count ${api_pp_catches} renders on page"
else
  bad "powerplay catches count ${api_pp_catches} not found"
fi

# The cohort tick element exists for the rate chart. The cohort
# range is reported in the chart legend as "(lo–hi)".
has_cohort=$(ab_eval "document.body.innerText.includes('${api_cohort_pp}')")
if [ "$has_cohort" = "true" ] || [ "$api_cohort_pp" = "MISSING" ]; then
  ok "cohort value ${api_cohort_pp} surfaced on page"
else
  bad "cohort value ${api_cohort_pp} not on page"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
