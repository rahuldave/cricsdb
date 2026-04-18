#!/bin/bash
# Teams tab: integration tests.
#
# Covers the happy path for /teams: landing renders, team selection
# drives the URL atomically, tab switching works, and the core tabs
# (By Season / vs Opponent / Match List / Compare) render.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

assert_url_contains() {
  local needle="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"; PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n    got: %s\n" "$needle" "$got"; FAIL=$((FAIL + 1))
  fi
}

assert_url_missing() {
  local needle="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" != *"$needle"* ]]; then
    printf "  ✓ url missing %s\n" "$needle"; PASS=$((PASS + 1))
  else
    printf "  ✗ url unexpectedly contains %s\n" "$needle"; FAIL=$((FAIL + 1))
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

# --------------------------------------------------------------------
echo "Test 1 · /teams landing renders men's / women's + franchise sections"
reset
agent-browser open "$BASE/teams" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
assert_snapshot_contains "India"                "India (international tile)"
assert_snapshot_contains "Mumbai Indians"       "Mumbai Indians (IPL tile)"
assert_snapshot_contains "Indian Premier League" "IPL section header"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · India team page: By Season default tab renders"
agent-browser open "$BASE/teams?team=India&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "team=India"
# Wins-by-season axis or chart rendered — "By Season" heading or
# matches summary number should appear.
assert_snapshot_contains "India"                "team header"
assert_snapshot_contains "By Season"            "By Season tab label"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Switch to Match List tab — URL updates, list renders"
TAB=$(ref_for 'button "MATCH LIST"')
if [ -n "$TAB" ]; then
  agent-browser click "$TAB" >/dev/null 2>&1
  settle 1.5
  assert_url_contains "tab=Match+List"
  assert_snapshot_contains "Opponent"           "match-list header"
else
  echo "  ✗ Match List tab not found"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 4 · Switch to vs Opponent tab + pick Australia"
TAB=$(ref_for 'button "VS OPPONENT"')
if [ -n "$TAB" ]; then
  agent-browser click "$TAB" >/dev/null 2>&1
  settle 1.5
  assert_url_contains "tab=vs+Opponent"
  # The opponent picker uses TeamSearch; type in and pick Australia.
  OPP_INPUT=$(agent-browser snapshot -i 2>&1 | grep -E 'textbox "Search.+opponent"' | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
  if [ -n "$OPP_INPUT" ]; then
    agent-browser fill "$OPP_INPUT" "Australia" >/dev/null 2>&1
    settle 1.5
    PICK=$(agent-browser snapshot -i 2>&1 | grep "listitem" | grep -F "Australia" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
    if [ -n "$PICK" ]; then
      agent-browser click "$PICK" >/dev/null 2>&1
      settle 2.0
      assert_url_contains "vs=Australia"
      assert_snapshot_contains "Australia"      "opponent page"
    else
      echo "  · could not find Australia in dropdown (skipped)"
    fi
  else
    echo "  · opponent search box not found (skipped)"
  fi
fi

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Switch to Batting tab — team-batting summary renders"
TAB=$(ref_for 'button "BATTING"')
if [ -n "$TAB" ]; then
  agent-browser click "$TAB" >/dev/null 2>&1
  settle 2.0
  assert_url_contains "tab=Batting"
  # Run rate or total runs should appear — both are StatCard labels.
  _has_rr=$(_innerText_has "run rate")
  _has_runs=$(_innerText_has "total runs")
  if [[ "$_has_rr" == "true" || "$_has_runs" == "true" ]]; then
    echo "  ✓ Batting tab shows run-rate / runs StatCards"; PASS=$((PASS + 1))
  else
    echo "  ✗ Batting tab content missing"; FAIL=$((FAIL + 1))
  fi
fi

# --------------------------------------------------------------------
echo ""
echo "Test 6 · Compare tab URL with one additional team shows 2 columns"
agent-browser open "$BASE/teams?team=India&compare=Australia&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
# The self-correcting effect promotes compare= → tab=Compare.
assert_url_contains "tab=Compare"
COL_COUNT=$(agent-browser eval 'String(document.querySelectorAll(".wisden-compare-col").length)' 2>/dev/null | tr -d '"')
if [[ "$COL_COUNT" == "2" ]]; then
  echo "  ✓ two compare columns rendered"; PASS=$((PASS + 1))
else
  echo "  ✗ compare column count is $COL_COUNT (expected 2)"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
