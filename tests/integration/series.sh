#!/bin/bash
# Series tab: integration tests.
#
# Happy-path + URL-state tests for /series. Migrated from
# back_button_history.sh:
#   - series_type invalid auto-reset (REPLACE) when team_type flips.
#   - /tournaments → /series legacy redirect does NOT push.
#   - ?rivalry=A,B legacy param migration does NOT push.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

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
echo "Test 1 · /series landing renders ICC + franchise + rivalry sections"
reset
agent-browser open "$BASE/series" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "Indian Premier League"   "IPL franchise tile"
assert_snapshot_contains "T20 World Cup"           "T20 World Cup ICC tile"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · IPL dossier — summary + by-season tabs render"
agent-browser open "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
assert_snapshot_contains "Indian Premier League"   "tournament header"
# The Records / Batters / Bowlers tabs live above the scroll; any of
# them presence indicates the dossier rendered.
assert_snapshot_contains "Records"                 "Records tab label"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · IND vs AUS rivalry dossier via filter_team + filter_opponent"
agent-browser open "$BASE/series?filter_team=India&filter_opponent=Australia&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
assert_snapshot_contains "India"                   "team1"
assert_snapshot_contains "Australia"               "team2"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · series_type invalid auto-reset on team_type flip (migrated)"
# Open with series_type=bilateral on team_type=international. Flip to
# Club — the bilateral option becomes invalid and a REPLACE strips it.
reset
agent-browser open "$BASE/series?filter_team=India&filter_opponent=Australia&gender=male&team_type=international&series_type=bilateral" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
CLUB_REF=$(ref_for 'button "Club"')
click_ref "$CLUB_REF"
assert_url_contains "team_type=club"
if agent-browser get url 2>/dev/null | grep -q "series_type="; then
  echo "  ✗ series_type should have been stripped"; FAIL=$((FAIL + 1))
else
  echo "  ✓ series_type stripped"; PASS=$((PASS + 1))
fi
# Back should restore the pre-click state (series_type=bilateral) —
# the strip was a REPLACE, not a push.
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "series_type=bilateral"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Legacy /tournaments → /series redirect does NOT push (migrated)"
reset
agent-browser open "$BASE/tournaments?tournament=Indian+Premier+League" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "/series?tournament=Indian+Premier+League"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 5a · series_type=bilateral narrows the FilterBar tournament dropdown"
# Before the FilterBar ↔ refs refactor, the tournament dropdown on a
# rivalry page ignored series_type and offered ICC events even under
# series_type=bilateral. After the refactor, /tournaments accepts
# series_type and narrows accordingly, so the dropdown hides WC etc.
reset
agent-browser open "$BASE/series?filter_team=Australia&filter_opponent=India&gender=male&team_type=international&series_type=bilateral" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
# The dropdown options live in <select>. Collect option labels.
OPTS=$(agent-browser eval "Array.from(document.querySelectorAll('select option')).map(o=>o.text).join('|')" 2>/dev/null | tail -1)
# ICC tournaments should be absent; bilateral series names should be present.
if [[ "$OPTS" == *"Australia tour of India"* ]]; then
  echo "  ✓ bilateral 'Australia tour of India' option present"; PASS=$((PASS + 1))
else
  echo "  ✗ bilateral option missing; OPTS=$OPTS"; FAIL=$((FAIL + 1))
fi
if [[ "$OPTS" == *"T20 World Cup"* ]]; then
  echo "  ✗ T20 World Cup should NOT appear under series_type=bilateral; OPTS=$OPTS"; FAIL=$((FAIL + 1))
else
  echo "  ✓ T20 World Cup correctly hidden under series_type=bilateral"; PASS=$((PASS + 1))
fi

# Flip to series_type=icc — the inverse narrowing must kick in.
echo ""
echo "Test 5b · series_type=icc shows ICC events, hides bilateral tours"
reset
agent-browser open "$BASE/series?filter_team=Australia&filter_opponent=India&gender=male&team_type=international&series_type=icc" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
OPTS_ICC=$(agent-browser eval "Array.from(document.querySelectorAll('select option')).map(o=>o.text).join('|')" 2>/dev/null | tail -1)
if [[ "$OPTS_ICC" == *"T20 World Cup"* ]]; then
  echo "  ✓ T20 World Cup present under series_type=icc"; PASS=$((PASS + 1))
else
  echo "  ✗ T20 World Cup missing under series_type=icc; OPTS=$OPTS_ICC"; FAIL=$((FAIL + 1))
fi
if [[ "$OPTS_ICC" == *"Australia tour of India"* ]]; then
  echo "  ✗ bilateral tour should NOT appear under series_type=icc; OPTS=$OPTS_ICC"; FAIL=$((FAIL + 1))
else
  echo "  ✓ bilateral tours correctly hidden under series_type=icc"; PASS=$((PASS + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 6 · Legacy ?rivalry= param migration does NOT push (migrated)"
reset
agent-browser open "$BASE/series?rivalry=India,Australia" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "filter_team=India"
assert_url_contains "filter_opponent=Australia"
if agent-browser get url 2>/dev/null | grep -q "rivalry="; then
  echo "  ✗ rivalry= should have been stripped"; FAIL=$((FAIL + 1))
else
  echo "  ✓ rivalry= stripped"; PASS=$((PASS + 1))
fi
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
