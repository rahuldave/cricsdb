#!/bin/bash
# Batting "vs Bowlers" tab — free-text bowler search above the matchups
# table. Typing in the input filters the table to bowlers whose name
# contains the query (case-insensitive substring match) and updates a
# "N matches" count next to the input.
#
# Asserts:
#   1. The search input renders on the tab and the placeholder
#      reports the bowler-count Kohli has faced live (anchored
#      against /vs-bowlers).
#   2. Typing "bumrah" filters the table down to JJ Bumrah only.
#   3. Backend limit cap was raised so the long tail is reachable —
#      `getBatterVsBowlers` with limit=500 returns more than the old
#      200 ceiling.
#
# Red-before-green: HEAD~1 has no `.wisden-bowler-search-input` in
# the DOM and no `limit` parameter on the api.ts helper.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

echo "=== /batting · vs Bowlers search ==="

# Count bowlers Kohli has faced at limit=500 (the new cap).
api_count=$(curl -sS "$API/api/v1/batters/$PLAYER/vs-bowlers?gender=male&min_balls=6&limit=500" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)['matchups']))")
echo "  API matchups (limit=500): $api_count"

ab open "$BASE/batting?player=$PLAYER&gender=male&tab=vs+Bowlers"
ab wait --load networkidle
ab wait 2500
ab_eval "document.querySelectorAll('.wisden-bowler-search-input').length"

# 1. Search input renders with the live bowler count in its placeholder.
ph=$(ab_eval "document.querySelector('.wisden-bowler-search-input')?.getAttribute('placeholder')")
echo "  placeholder: $ph"
if echo "$ph" | grep -q "$api_count bowlers faced"; then
  ok "search input placeholder reports live bowler count ($api_count)"
else
  bad "placeholder does not match live bowler count ($api_count): $ph"
fi

# 2. Typing "bumrah" filters to one row.
ab fill ".wisden-bowler-search-input" "bumrah"
ab wait 700
filtered=$(ab_eval "document.querySelectorAll('table tbody tr').length")
echo "  rows after filter: $filtered"
if [ "$filtered" = "1" ]; then
  ok "filtering by 'bumrah' narrows the table to 1 row"
else
  bad "filtering by 'bumrah' returned $filtered rows (expected 1)"
fi
count_label=$(ab_eval "document.querySelector('.wisden-bowler-search-count')?.textContent")
echo "  count label: $count_label"
if echo "$count_label" | grep -q "1 match"; then
  ok "count label reads \"1 match\""
else
  bad "count label not \"1 match\": $count_label"
fi

# 3. The bumrah row's first cell contains "Bumrah".
name=$(ab_eval "document.querySelector('table tbody tr')?.children[0]?.textContent")
echo "  first cell: $name"
if echo "$name" | grep -qi "bumrah"; then
  ok "filtered row is a Bumrah row"
else
  bad "filtered row is not a Bumrah row: $name"
fi

# 4. Backend cap raised: limit=500 returns >200 (the old cap).
if [ "$api_count" -gt 200 ]; then
  ok "backend limit cap > 200 (got $api_count)"
else
  bad "backend still capped at <=200 (got $api_count)"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
