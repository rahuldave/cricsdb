#!/bin/bash
# Bowling "By Phase" tab — comparative Dot %/SR/Economy charts.
# Mirrors the batting equivalent. User-asked 2026-05-22.
#
# Asserts:
#   1. Three PerformanceVsCohort panels render with their titles:
#      "Dot % by phase", "Strike rate by phase", "Economy by phase".
#   2. Player powerplay economy matches the API (/by-phase) — chart
#      should be reading the live data, not stale props.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=462411b3  # JJ Bumrah

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

echo "=== /bowling · By Phase comparative charts ==="
ab open "$BASE/bowling?player=$PLAYER&gender=male&tab=By+Phase"
ab wait --load networkidle
ab wait --text "Dot % by phase"
ab wait 1500

for title in "Dot % by phase" "Strike rate by phase" "Economy by phase"; do
  has=$(ab_eval "document.body.innerText.includes('${title}')")
  if [ "$has" = "true" ]; then
    ok "title present — \"${title}\""
  else
    bad "title missing — \"${title}\""
  fi
done

# Player powerplay economy must match the live API.
api_econ=$(curl -sS "$API/api/v1/bowlers/$PLAYER/by-phase?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['by_phase']; pp=next(p for p in d if p['phase']=='powerplay'); print(f\"{pp['economy']:.2f}\")")
echo "  API powerplay econ: $api_econ"
has_econ=$(ab_eval "document.body.innerText.includes('${api_econ}')")
if [ "$has_econ" = "true" ]; then
  ok "powerplay player economy ${api_econ} is rendered on the page"
else
  bad "powerplay player economy ${api_econ} not found"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
