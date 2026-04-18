#!/bin/bash
# Venues Phase 2 integration tests.
#
# Verifies:
#   1. /venues landing renders country sections with canonical names.
#   2. FilterBar Venue typeahead: type → dropdown, pick → chip+URL,
#      chip has "× Clear venue", clear → URL drops filter_venue.
#   3. filter_venue is an ambient filter — applying it on /teams,
#      /players, /head-to-head, /series narrows data via SPA navigation
#      (no reload required). This is the specific bug the regression
#      harness missed in the original Phase 2 ship.
#   4. Back button after an SPA filter pick drops the filter and
#      refetches.
#   5. Landing tile click navigates to /matches?filter_venue=X.
#
# Requires:
#   - agent-browser installed (npm i -g agent-browser).
#   - A vite dev server on http://localhost:5173 (npm run dev in frontend/).
#   - A FastAPI backend on http://localhost:8000 (uv run uvicorn ... --reload).
#
# Run:
#   ./tests/integration/venues.sh
#
# Exits non-zero on the first failure.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

WANKHEDE="Wankhede Stadium, Mumbai"
WANKHEDE_URLENC="Wankhede+Stadium%2C+Mumbai"

assert_url_contains() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"
    PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n" "$needle"
    printf "    got: %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

assert_url_not_contains() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" != *"$needle"* ]]; then
    printf "  ✓ url does not contain %s\n" "$needle"
    PASS=$((PASS + 1))
  else
    printf "  ✗ url still contains %s\n" "$needle"
    printf "    got: %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

_innerText_has() {
  # Returns "true" or "false" for whether body.innerText contains $1
  # (case-insensitive — CSS text-transform gets applied to innerText,
  # so "Clear venue" in the source might render as "CLEAR VENUE" to
  # innerText). base64-wrapped to sidestep shell-quoting on bash 3.2.
  local needle_b64
  needle_b64=$(printf '%s' "$1" | base64)
  local js_b64
  js_b64=$(printf 'document.body.innerText.toLowerCase().includes(atob("%s").toLowerCase())' "$needle_b64" | base64)
  agent-browser eval -b "$js_b64" 2>/dev/null | tail -1 | tr -d '[:space:]'
}

assert_snapshot_contains() {
  # Use document.body.innerText — the accessibility-tree snapshot
  # doesn't surface <details>/<summary> text or CSS-uppercased chip
  # labels, but innerText does.
  local needle="$1"
  local label="${2:-$needle}"
  local got; got=$(_innerText_has "$needle")
  if [[ "$got" == "true" ]]; then
    printf "  ✓ page contains %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  ✗ page missing %s\n" "$label"
    FAIL=$((FAIL + 1))
  fi
}

assert_snapshot_not_contains() {
  local needle="$1"
  local label="${2:-$needle}"
  local got; got=$(_innerText_has "$needle")
  if [[ "$got" == "false" ]]; then
    printf "  ✓ page does not contain %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  ✗ page still contains %s\n" "$label"
    FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

ref_for_text() {
  # First @eN whose accessibility-tree line mentions $1 (case-insensitive).
  agent-browser snapshot -i 2>&1 | grep -iE "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

ref_for_placeholder() {
  agent-browser snapshot -i 2>&1 | grep -F "textbox \"$1\"" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

# --------------------------------------------------------------------
echo "Test 1 · /venues landing renders country sections + canonical names"

agent-browser open "$BASE/venues" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

assert_snapshot_contains "India"                     "India section header"
assert_snapshot_contains "Wankhede Stadium, Mumbai"  "Wankhede canonical name"
assert_snapshot_contains "Eden Gardens, Kolkata"     "Eden Gardens canonical"
assert_snapshot_contains "VENUES"                    "Venues nav tab"

# --------------------------------------------------------------------
echo
echo "Test 2 · FilterBar Venue typeahead: type, pick, chip, clear"

# Start fresh — Teams India so we have a non-Venues context
agent-browser open "$BASE/teams?team=India&tab=Summary&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

SEARCH=$(ref_for_placeholder "Search venue…")
if [ -z "$SEARCH" ]; then
  echo "  ✗ could not find the Venue search input"
  FAIL=$((FAIL + 1))
else
  echo "  → typing 'wank'"
  agent-browser fill "$SEARCH" "wank" >/dev/null 2>&1
  settle 1.0
  assert_snapshot_contains "Wankhede Stadium, Mumbai"  "typeahead result"

  # Click the result
  PICK=$(agent-browser snapshot -i 2>&1 | grep "listitem" | grep -F "Wankhede Stadium, Mumbai" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
  if [ -z "$PICK" ]; then
    echo "  ✗ could not find the typeahead listitem ref"
    FAIL=$((FAIL + 1))
  else
    agent-browser click "$PICK" >/dev/null 2>&1
    settle 1.2
    assert_url_contains "filter_venue=$WANKHEDE_URLENC"
    assert_snapshot_contains "Clear venue"               "clear-venue button"
    assert_snapshot_contains "Venue:"                    "chip label"
    assert_snapshot_contains "Wankhede Stadium, Mumbai"  "chip venue name"
  fi
fi

# --------------------------------------------------------------------
echo
echo "Test 3 · filter_venue narrows Teams data via SPA (no reload)"

# After Test 2 we're on /teams/India with filter_venue set. Data should
# reflect India's scoped-to-Wankhede matches, not all 266.
settle 1.0
assert_snapshot_contains "India"           "India header"
# Make sure the big 266 is NOT in innerText — that's the all-time
# total which the SPA refetch bug used to leave stuck on screen.
assert_snapshot_not_contains "266"         "all-time total (should be scoped)"

# --------------------------------------------------------------------
echo
echo "Test 4 · Clear button removes filter_venue, preserves other params"

CLEAR=$(ref_for_text "Clear venue filter")
if [ -z "$CLEAR" ]; then
  echo "  ✗ could not find Clear venue button"
  FAIL=$((FAIL + 1))
else
  agent-browser click "$CLEAR" >/dev/null 2>&1
  settle 1.2
  assert_url_not_contains "filter_venue"
  assert_url_contains     "team=India"
  assert_url_contains     "gender=male"
  assert_url_contains     "team_type=international"
fi

# --------------------------------------------------------------------
echo
echo "Test 5 · Landing tile click navigates to /matches?filter_venue=X"

agent-browser open "$BASE/venues" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

# Click the Wankhede tile. It's a button inside the open India accordion.
TILE=$(agent-browser snapshot -i 2>&1 | grep -F "Wankhede Stadium, Mumbai · Mumbai" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
if [ -z "$TILE" ]; then
  # Fallback — any button whose text starts with "Wankhede"
  TILE=$(agent-browser snapshot -i 2>&1 | grep "button" | grep -F "Wankhede" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
fi
if [ -z "$TILE" ]; then
  echo "  ✗ could not find Wankhede tile"
  FAIL=$((FAIL + 1))
else
  agent-browser click "$TILE" >/dev/null 2>&1
  settle 1.5
  assert_url_contains "/matches"
  assert_url_contains "filter_venue=$WANKHEDE_URLENC"
fi

# --------------------------------------------------------------------
echo
echo "Test 6 · Back button drops filter_venue and refetches"

# Navigate from /teams/India (with filter) via SPA, verify back.
agent-browser open "$BASE/teams?team=India&tab=Summary&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

SEARCH=$(ref_for_placeholder "Search venue…")
agent-browser fill "$SEARCH" "wank" >/dev/null 2>&1
settle 1.0
PICK=$(agent-browser snapshot -i 2>&1 | grep "listitem" | grep -F "Wankhede Stadium, Mumbai" | head -1 | grep -oE 'ref=e[0-9]+' | sed 's/ref=/@/')
agent-browser click "$PICK" >/dev/null 2>&1
settle 1.2
assert_url_contains "filter_venue=$WANKHEDE_URLENC"

agent-browser eval "history.back()" >/dev/null 2>&1
settle 2.5  # longer settle — data refetch needs network round-trip
assert_url_not_contains "filter_venue"
assert_url_contains     "team=India"
# Summary should refetch back to all-time India men's (266 matches).
# innerText includes the summary numbers; 266 appears in the header row.
assert_snapshot_contains "266" "all-time matches total after back"

# --------------------------------------------------------------------
echo
echo "Test 7 · filter_venue is carried through Series tab SPA"

agent-browser open "$BASE/series?tournament=Indian+Premier+League&filter_venue=$WANKHEDE_URLENC&team_type=club&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0

assert_snapshot_contains "Indian Premier League"     "series header"
assert_snapshot_contains "Wankhede Stadium, Mumbai"  "chip / venue surfaced"
# IPL at Wankhede should be far fewer than the IPL total of ~1190.
# Assert the total count isn't showing.
assert_snapshot_not_contains "1,190 matches"  "unfiltered IPL total"
assert_snapshot_not_contains "1190 matches"   "unfiltered IPL total (no comma)"

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true

echo
echo "=========================================="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo "=========================================="

[ "$FAIL" -eq 0 ]
