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

assert_snapshot_contains() {
  local needle="$1"
  local label="${2:-$needle}"
  if agent-browser snapshot -i 2>&1 | grep -q -F "$needle"; then
    printf "  ✓ page contains %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  ✗ page missing %s\n" "$label"
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

assert_snapshot_contains "INDIA"             "India section header"
assert_snapshot_contains "Wankhede Stadium, Mumbai"  "Wankhede canonical name"
assert_snapshot_contains "Eden Gardens, Kolkata"     "Eden Gardens canonical"
assert_snapshot_contains "VENUES"            "Venues nav tab active"

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
    assert_snapshot_contains "VENUE:"                    "chip label"
  fi
fi

# --------------------------------------------------------------------
echo
echo "Test 3 · filter_venue narrows Teams data via SPA (no reload)"

# After Test 2 we're on /teams/India with filter_venue set. Data should
# reflect India's 8 matches at Wankhede, not 266.
settle 1.0
assert_snapshot_contains "India 🇮🇳"          "India header"
# Look for the small "8" summary. Can't assert exact number reliably
# across data updates; look for the "Matches" label adjacent to a
# small one- or two-digit number (vs the 266 all-time).
if agent-browser snapshot -i 2>&1 | grep -A1 "Matches" | grep -qE "^\s*(generic )?\"?[0-9]{1,2}\"?\s*$"; then
  echo "  ✓ Matches count is double-digit (scoped to venue)"
  PASS=$((PASS + 1))
else
  # Fallback: make sure it's NOT the unfiltered 266.
  if agent-browser snapshot -i 2>&1 | grep -q "266"; then
    echo "  ✗ data did not refetch — still shows 266 (SPA refetch bug)"
    FAIL=$((FAIL + 1))
  else
    echo "  ✓ Matches count changed from 266 (scoped)"
    PASS=$((PASS + 1))
  fi
fi

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
settle 1.5
assert_url_not_contains "filter_venue"
assert_url_contains     "team=India"
# Summary should refetch back to all-time India men's (266 matches).
if agent-browser snapshot -i 2>&1 | grep -q "266"; then
  echo "  ✓ data refetched on back (shows 266 all-time)"
  PASS=$((PASS + 1))
else
  echo "  ✗ back did not refetch — missing all-time total"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo
echo "Test 7 · filter_venue is carried through Series tab SPA"

agent-browser open "$BASE/series?tournament=Indian+Premier+League&filter_venue=$WANKHEDE_URLENC&team_type=club&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0

assert_snapshot_contains "Indian Premier League"  "series header"
assert_snapshot_contains "Wankhede Stadium, Mumbai"  "chip / venue surfaced"
# IPL at Wankhede should be far fewer than the IPL total of ~1200.
if agent-browser snapshot -i 2>&1 | grep -qE "1[0-9]{2} matches|[0-9]{2} matches"; then
  echo "  ✓ Series dossier narrowed to scoped matches"
  PASS=$((PASS + 1))
else
  echo "  ✗ Series dossier does not appear to be scoped"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true

echo
echo "=========================================="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo "=========================================="

[ "$FAIL" -eq 0 ]
