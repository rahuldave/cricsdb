#!/bin/bash
# Matches tab: integration tests.
#
# Covers /matches list + /matches/:id scorecard. Migrated from
# back_button_history.sh:
#   - FilterBar clicks on /matches push a real back stack.
#
# Also verifies the scorecard highlight_batter flow (the match-list
# date cells on player innings pages carry this param; scorecard tints
# the matching row and scrolls).
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

MATCH_ID=13017
KOHLI=ba607b88

assert_url_eq() {
  local expected="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %s\n" "$expected"; PASS=$((PASS + 1))
  else
    printf "  ✗ expected: %s\n    got:      %s\n" "$expected" "$got"; FAIL=$((FAIL + 1))
  fi
}

assert_url_contains() {
  local needle="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"; PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n    got: %s\n" "$needle" "$got"; FAIL=$((FAIL + 1))
  fi
}

_innerText_has() {
  local needle_b64 js_b64
  needle_b64=$(printf '%s' "$1" | base64)
  js_b64=$(printf 'document.body.innerText.toLowerCase().includes(atob("%s").toLowerCase())' "$needle_b64" | base64)
  agent-browser eval -b "$js_b64" 2>/dev/null | tail -1 | tr -d '[:space:]'
}

assert_snapshot_contains() {
  local needle="$1" label="${2:-$1}" got
  got=$(_innerText_has "$needle")
  if [[ "$got" == "true" ]]; then
    printf "  ✓ page contains %s\n" "$label"; PASS=$((PASS + 1))
  else
    printf "  ✗ page missing %s\n" "$label"; FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

ref_for() {
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

reset() {
  agent-browser open "$BASE/" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.0
}

click_ref() { agent-browser click "$1" >/dev/null 2>&1; settle 1.0; }

# --------------------------------------------------------------------
echo "Test 1 · /matches list renders rows"
reset
agent-browser open "$BASE/matches" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# On /matches the date cell is a plain <td> and the <tr> has the
# is-clickable class (onClick navigates). Count those; team cells
# inside each row render as comp-link anchors.
ROWS=$(agent-browser eval 'String(document.querySelectorAll("tr.is-clickable").length)' 2>/dev/null | tr -d '"')
if [[ "$ROWS" =~ ^[0-9]+$ ]] && [ "$ROWS" -gt 0 ]; then
  echo "  ✓ $ROWS match rows rendered (tr.is-clickable)"; PASS=$((PASS + 1))
else
  echo "  ✗ no match rows found"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Filter clicks push a real back stack (migrated)"
reset
agent-browser open "$BASE/matches" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
MEN_REF=$(ref_for 'button "Men"')
click_ref "$MEN_REF"
assert_url_eq "$BASE/matches?gender=male"
INTL_REF=$(ref_for 'button "Intl"')
click_ref "$INTL_REF"
assert_url_eq "$BASE/matches?gender=male&team_type=international"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/matches?gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/matches"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Scorecard renders both innings"
agent-browser open "$BASE/matches/$MATCH_ID" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
# Every scorecard has a "Batting" + "Bowling" heading per innings.
_has_batting=$(_innerText_has "batting")
_has_bowling=$(_innerText_has "bowling")
if [[ "$_has_batting" == "true" && "$_has_bowling" == "true" ]]; then
  echo "  ✓ scorecard shows batting + bowling sections"; PASS=$((PASS + 1))
else
  echo "  ✗ scorecard missing batting/bowling"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 4 · Scorecard with highlight_batter tints the matching row"
# Find a match where Kohli played — use his by-innings response to get
# a real match_id. Fallback: any IPL match_id he played at Wankhede.
MATCH_FOR_KOHLI=$(curl -s "http://localhost:8000/api/v1/batters/$KOHLI/by-innings?limit=1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["innings"][0]["match_id"])' 2>/dev/null)
if [ -z "$MATCH_FOR_KOHLI" ]; then
  echo "  · could not derive a Kohli match_id (skipped)"
else
  agent-browser open "$BASE/matches/$MATCH_FOR_KOHLI?highlight_batter=$KOHLI" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 3.5
  HL_COUNT=$(agent-browser eval 'String(document.querySelectorAll(".is-highlighted").length)' 2>/dev/null | tr -d '"')
  if [[ "$HL_COUNT" =~ ^[0-9]+$ ]] && [ "$HL_COUNT" -gt 0 ]; then
    echo "  ✓ $HL_COUNT row(s) tinted (.is-highlighted)"; PASS=$((PASS + 1))
  else
    echo "  ✗ no .is-highlighted rows on scorecard for Kohli"; FAIL=$((FAIL + 1))
  fi
fi

# --------------------------------------------------------------------
echo ""
echo "Test 5 · filter_venue chip survives on /matches (Phase 2 fan-out)"
agent-browser open "$BASE/matches?filter_venue=Wankhede+Stadium%2C+Mumbai" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "Wankhede"                "venue chip visible"
assert_url_contains     "filter_venue="

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
