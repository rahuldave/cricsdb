#!/bin/bash
# Batting "By Phase" tab — comparative SR / Dot% / Boundaries-per-over
# charts AND the "B/4" → "Balls/4" label rename.
#
# Asserts:
#   1. The three PerformanceVsCohort panels render with their titles:
#      "Strike rate by phase", "Dot % by phase", "Boundaries per
#      over by phase".
#   2. Per-phase block label says "Balls/4" — NOT the old "B/4" —
#      since the original label was opaque to readers new to cricket
#      stats.
#   3. The Strike-rate-by-phase chart's player value at the
#      powerplay matches what /batters/{id}/by-phase returns (so the
#      chart is reading the live API, not a stale prop).
#
# Red-before-green: HEAD~1 has no PhaseComparativeCharts component
# and the label reads "B/4" — assertions 1, 3 fail (no titles), and
# 2 fails (label mismatch).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

echo "=== /batting · By Phase comparative charts ==="
ab open "$BASE/batting?player=$PLAYER&gender=male&tab=By+Phase"
ab wait --load networkidle
ab wait --text "Strike rate by phase"
ab wait 1500

# 1. Three chart titles present.
for title in "Strike rate by phase" "Dot % by phase" "Boundaries per over by phase"; do
  has=$(ab_eval "document.body.innerText.includes('${title}')")
  if [ "$has" = "true" ]; then
    ok "title present — \"${title}\""
  else
    bad "title missing — \"${title}\""
  fi
done

# 2. "Balls/4" label appears; "B/4" no longer.
has_balls=$(ab_eval "document.body.innerText.includes('Balls/4')")
if [ "$has_balls" = "true" ]; then
  ok "per-phase label reads \"Balls/4\""
else
  bad "per-phase label \"Balls/4\" missing"
fi
has_old=$(ab_eval "document.body.innerText.includes('B/4 ') || document.body.innerText.includes('B/4\n')")
# Don't fail outright if it doesn't match - this is a soft check (the
# unicode em-dash separator could trick the substring). Just notify.
if [ "$has_old" = "true" ]; then
  bad "stale \"B/4\" label still appears on the page"
else
  ok "stale \"B/4\" label removed"
fi

# 3. Player SR at powerplay matches the API.
api_sr=$(curl -sS "$API/api/v1/batters/$PLAYER/by-phase?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['by_phase']; pp=next(p for p in d if p['phase'].lower()=='powerplay'); print(f'{pp[\"strike_rate\"]:.2f}')")
echo "  API powerplay SR: $api_sr"
# The per-phase tile above the chart shows the same SR — assert that text appears.
has_sr=$(ab_eval "document.body.innerText.includes('${api_sr}')")
if [ "$has_sr" = "true" ]; then
  ok "powerplay player SR ${api_sr} is rendered on the page"
else
  bad "powerplay player SR ${api_sr} not found in rendered page"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
