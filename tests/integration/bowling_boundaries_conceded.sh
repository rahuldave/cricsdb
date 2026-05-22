#!/bin/bash
# Bowling page surfaces boundaries-conceded — user flagged 2026-05-22
# that the metric was missing from the page despite the data being on
# /bowlers/{id}/summary.
#
# Asserts: the "Bdys Cnd" StatCard renders with the live API count.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=462411b3  # JJ Bumrah

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_bdys=$(curl -sS "$API/api/v1/bowlers/$PLAYER/summary?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['boundaries_conceded']['value'])")
api_4s=$(curl -sS "$API/api/v1/bowlers/$PLAYER/summary?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['fours_conceded']['value'])")
api_6s=$(curl -sS "$API/api/v1/bowlers/$PLAYER/summary?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['sixes_conceded']['value'])")
echo "  API: boundaries=$api_bdys (${api_4s} 4s, ${api_6s} 6s)"

ab open "$BASE/bowling?player=$PLAYER&gender=male"
ab wait --load networkidle
ab wait --text "Bdys Cnd"
ab wait 1500

has_label=$(ab_eval "document.body.innerText.includes('Bdys Cnd')")
if [ "$has_label" = "true" ]; then
  ok "Bdys Cnd label renders"
else
  bad "Bdys Cnd label missing"
fi

has_count=$(ab_eval "document.body.innerText.includes('${api_bdys}')")
if [ "$has_count" = "true" ]; then
  ok "boundaries-conceded count ${api_bdys} on page"
else
  bad "boundaries count not found"
fi

# StatCard subtitle is text-transform: uppercase, so the rendered DOM
# shows "630 4S, 191 6S". Match case-insensitively.
has_subtitle=$(ab_eval "document.body.innerText.toLowerCase().includes('${api_4s} 4s, ${api_6s} 6s')")
if [ "$has_subtitle" = "true" ]; then
  ok "subtitle reads \"${api_4s} 4s, ${api_6s} 6s\""
else
  bad "subtitle wrong"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
