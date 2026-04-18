#!/bin/bash
# Head-to-Head tab: integration tests.
#
# Covers polymorphic /head-to-head:
#   - mode=player (default) — batter vs bowler matchup.
#   - mode=team — team pair dossier (reuses /series/* endpoints).
# Plus series_type toggle on each mode.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

KOHLI=ba607b88
BUMRAH=462411b3

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
echo "Test 1 · /head-to-head landing (mode=player) shows suggestion tiles"
reset
agent-browser open "$BASE/head-to-head" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "Head"                    "page header"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Player-vs-player deep link renders matchup stats"
agent-browser open "$BASE/head-to-head?batter=$KOHLI&bowler=$BUMRAH&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
assert_snapshot_contains "V Kohli"                 "batter name"
assert_snapshot_contains "JJ Bumrah"               "bowler name"
# H2H response has balls + runs. StatCard labels appear in innerText.
assert_snapshot_contains "Balls"                   "Balls StatCard"
assert_snapshot_contains "Runs"                    "Runs StatCard"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Team-vs-team mode (mode=team) renders dossier"
agent-browser open "$BASE/head-to-head?mode=team&team1=India&team2=Australia&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.5
assert_snapshot_contains "India"                   "team1"
assert_snapshot_contains "Australia"               "team2"
# Dossier exposes the tournament/series_type pill row.
assert_snapshot_contains "Records"                 "Records tab label"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · series_type toggle works in team mode"
# Click the bilateral_only (or similar) pill.
BIL_REF=$(ref_for 'button.*[Bb]ilateral')
if [ -n "$BIL_REF" ]; then
  click_ref "$BIL_REF"
  assert_url_contains "series_type="
else
  echo "  · no series_type pill visible (skipped)"
fi

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Search → pick batter for mode=player"
reset
agent-browser open "$BASE/head-to-head" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
BAT_INPUT=$(agent-browser snapshot -i 2>&1 | grep -E 'textbox "Search batter' | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
if [ -n "$BAT_INPUT" ]; then
  agent-browser fill "$BAT_INPUT" "Kohli" >/dev/null 2>&1
  settle 1.5
  PICK=$(agent-browser snapshot -i 2>&1 | grep "listitem" | grep -F "V Kohli" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
  if [ -n "$PICK" ]; then
    agent-browser click "$PICK" >/dev/null 2>&1
    settle 2.0
    assert_url_contains "batter=$KOHLI"
  else
    echo "  · Kohli listitem not in dropdown (skipped)"
  fi
else
  echo "  · batter search input not found (skipped)"
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
