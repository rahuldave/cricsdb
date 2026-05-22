#!/bin/bash
# Bowling "vs Batters" tab — free-text batter search input above the
# matchups table. Mirrors the batting/vs-bowlers pattern. User-asked
# 2026-05-22.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=462411b3   # JJ Bumrah

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_count=$(curl -sS "$API/api/v1/bowlers/$PLAYER/vs-batters?gender=male&min_balls=6&limit=500" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)['matchups']))")
echo "  API matchups (limit=500): $api_count"

ab open "$BASE/bowling?player=$PLAYER&gender=male&tab=vs+Batters"
ab wait --load networkidle
ab wait 2500

ph=$(ab_eval "document.querySelector('.wisden-bowler-search-input')?.getAttribute('placeholder')")
echo "  placeholder: $ph"
if echo "$ph" | grep -q "$api_count batters faced"; then
  ok "search placeholder reports live batter count ($api_count)"
else
  bad "placeholder does not match live count ($api_count): $ph"
fi

ab fill ".wisden-bowler-search-input" "kohli"
ab wait 700
filtered=$(ab_eval "document.querySelectorAll('table tbody tr').length")
echo "  rows after filter: $filtered"
if [ "$filtered" = "1" ]; then
  ok "filtering by 'kohli' narrows the table to 1 row"
else
  bad "filtering by 'kohli' returned $filtered rows (expected 1)"
fi
name=$(ab_eval "document.querySelector('table tbody tr')?.children[0]?.textContent")
if echo "$name" | grep -qi "kohli"; then
  ok "filtered row is a Kohli row"
else
  bad "filtered row not a Kohli row: $name"
fi

if [ "$api_count" -gt 200 ]; then
  ok "backend cap > 200 (got $api_count)"
else
  bad "backend cap <=200 (got $api_count)"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
