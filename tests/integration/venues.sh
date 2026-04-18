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
echo "Test 5 · Landing tile click opens the per-venue dossier (Phase 3)"

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
  assert_url_contains "/venues"
  assert_url_contains "venue=$WANKHEDE_URLENC"
  # filter_venue should NOT be set — dossier pins via path, not ambient
  assert_url_not_contains "filter_venue="
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
echo
echo "Test 8 · Phase 3 dossier — Overview stats + tabs + back-to-landing"

agent-browser open "$BASE/venues?venue=$WANKHEDE_URLENC" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

assert_snapshot_contains "Wankhede Stadium, Mumbai" "dossier headline"
assert_snapshot_contains "All venues"               "back-to-landing link"
assert_snapshot_contains "view all matches"        "view-all-matches escape hatch"
assert_snapshot_contains "Bat-first win %"         "Overview StatCard"
assert_snapshot_contains "Avg 1st-inn total"       "Avg 1st-inn StatCard"
assert_snapshot_contains "Powerplay"               "phase table row"
assert_snapshot_contains "Highest total"           "ground-record tile"
assert_snapshot_contains "Matches hosted"          "by-season table"

# Tab strip
for tab in Overview Batters Bowlers Fielders Matches Records; do
  assert_snapshot_contains "$tab" "$tab tab"
done

# Batters tab — should render a PlayerLink with contextual "at Wankhede" suffix
agent-browser eval "document.querySelectorAll('.wisden-tab')[1].click()" >/dev/null 2>&1
settle 1.5
assert_snapshot_contains "By average"                  "Batters tab header"
assert_snapshot_contains "at Wankhede Stadium, Mumbai" "PlayerLink context suffix"

# Records tab — tournament records endpoint reused with filter_venue.
# Records needs a longer settle — the endpoint is heavier than leaders.
agent-browser eval "document.querySelectorAll('.wisden-tab')[5].click()" >/dev/null 2>&1
settle 3.5
assert_snapshot_contains "Highest team totals" "Records section"
assert_snapshot_contains "Lowest all-out"      "Records section"
assert_snapshot_contains "Best bowling figures" "Records section"

# Back-to-landing link → /venues (no venue= param)
agent-browser eval "document.querySelector('.wisden-breadcrumb a').click()" >/dev/null 2>&1
settle 1.5
assert_url_contains     "/venues"
assert_url_not_contains "venue="
assert_snapshot_contains "Pick a venue to open" "landing blurb after back"

# --------------------------------------------------------------------
echo
echo "Test 9a · /venues auto-promotes filter_venue to ?venue= (dossier mode)"

# Arriving at /venues with filter_venue= set (e.g. shared link from the
# FilterBar on another tab) should open the dossier rather than being a
# no-op. Venues.tsx has a useEffect that rewrites the URL.
agent-browser open "$BASE/venues?filter_venue=$WANKHEDE_URLENC" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
assert_url_contains     "venue=$WANKHEDE_URLENC"
assert_url_not_contains "filter_venue"
assert_snapshot_contains "Bat-first win %" "dossier rendered after promotion"

# --------------------------------------------------------------------
echo
echo "Test 9b · Landing search box narrows country grid client-side"

agent-browser open "$BASE/venues" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5

# Default state: 88 countries, top-3 open
COUNT_ALL=$(agent-browser eval "document.querySelectorAll('details').length" 2>/dev/null | tail -1)
OPEN_ALL=$(agent-browser eval "Array.from(document.querySelectorAll('details')).filter(d=>d.open).length" 2>/dev/null | tail -1)
if [ "$COUNT_ALL" -gt 50 ] 2>/dev/null && [ "$OPEN_ALL" = "3" ]; then
  printf "  ✓ default landing: %s countries / %s open\n" "$COUNT_ALL" "$OPEN_ALL"
  PASS=$((PASS + 1))
else
  printf "  ✗ unexpected default state: countries=%s open=%s\n" "$COUNT_ALL" "$OPEN_ALL"
  FAIL=$((FAIL + 1))
fi

# Type "mumbai" — React-safe value+input dispatch
SET_JS='const i=document.querySelector("input[placeholder^=\"Filter\"]"); const ns=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; ns.call(i,"mumbai"); i.dispatchEvent(new Event("input",{bubbles:true}));'
SET_B64=$(printf '%s' "$SET_JS" | base64)
agent-browser eval -b "$SET_B64" >/dev/null 2>&1
settle 0.6

COUNT_Q=$(agent-browser eval "document.querySelectorAll('details').length" 2>/dev/null | tail -1)
OPEN_Q=$(agent-browser eval "Array.from(document.querySelectorAll('details')).filter(d=>d.open).length" 2>/dev/null | tail -1)
VENUE_Q=$(agent-browser eval "document.querySelectorAll('.wisden-collapse-body button').length" 2>/dev/null | tail -1)

if [ "$COUNT_Q" = "1" ] && [ "$OPEN_Q" = "1" ] && [ "$VENUE_Q" -ge 3 ] 2>/dev/null; then
  printf "  ✓ 'mumbai' narrows to %s country / %s venues (all open)\n" "$COUNT_Q" "$VENUE_Q"
  PASS=$((PASS + 1))
else
  printf "  ✗ 'mumbai' narrow mis-behaved: countries=%s opens=%s venues=%s\n" "$COUNT_Q" "$OPEN_Q" "$VENUE_Q"
  FAIL=$((FAIL + 1))
fi

assert_snapshot_contains "Wankhede Stadium, Mumbai" "Wankhede surfaces under 'mumbai'"
assert_snapshot_contains "Brabourne"                "Brabourne surfaces under 'mumbai'"

# "xyzqqq" — no matches → empty-state message. Reopen the page between
# queries so we exercise the "type into a fresh landing" path; the
# controlled-input React cycle doesn't always settle mid-run when we
# dispatch two value-setter updates in quick succession.
agent-browser open "$BASE/venues" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
SET_JS='const i=document.querySelector("input[placeholder^=\"Filter\"]"); const ns=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set; ns.call(i,"xyzqqq"); i.dispatchEvent(new Event("input",{bubbles:true}));'
SET_B64=$(printf '%s' "$SET_JS" | base64)
agent-browser eval -b "$SET_B64" >/dev/null 2>&1
settle 1.2
assert_snapshot_contains "No venues match" "empty-state on unmatched query"

# --------------------------------------------------------------------
echo
echo "Test 9 · Dossier respects FilterBar — gender=female narrows the sample"

agent-browser open "$BASE/venues?venue=$WANKHEDE_URLENC" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
# Extract matches number from first StatCard
M_ALL=$(agent-browser eval "document.querySelectorAll('.wisden-stat-value')[0].innerText.replace(/,/g,'')" 2>/dev/null | tail -1 | tr -d '"')

agent-browser open "$BASE/venues?venue=$WANKHEDE_URLENC&gender=female" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
M_F=$(agent-browser eval "document.querySelectorAll('.wisden-stat-value')[0].innerText.replace(/,/g,'')" 2>/dev/null | tail -1 | tr -d '"')

if [ -n "$M_ALL" ] && [ -n "$M_F" ] && [ "$M_F" -lt "$M_ALL" ] 2>/dev/null; then
  printf "  ✓ gender filter narrows match count (all=%s female=%s)\n" "$M_ALL" "$M_F"
  PASS=$((PASS + 1))
else
  printf "  ✗ gender filter did not narrow (all=%s female=%s)\n" "$M_ALL" "$M_F"
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
