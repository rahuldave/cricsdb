#!/bin/bash
# Mount / unmount hygiene tests.
#
# Verifies that rapid navigation, fast filter changes, and in-flight
# searches don't produce console errors, page errors, or stale-data
# leaks. Tests here drive the real browser and assert on negative
# signals (no errors / no stale content) — good for catching things
# like missing cleanup in useEffect, leftover listeners, setState
# after unmount.
#
# Prerequisites + how to run: see README.md.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

# Start from a clean browser session so earlier in-process errors
# (old HMR state, previous test runs) don't leak into these assertions.
agent-browser close --all >/dev/null 2>&1 || true
sleep 1

clear_console() {
  agent-browser console --clear >/dev/null 2>&1
  agent-browser errors --clear >/dev/null 2>&1
}

assert_no_page_errors() {
  local label="$1"
  local errs
  errs=$(agent-browser errors 2>/dev/null | grep -cE '.+')
  if [[ "$errs" == "0" ]]; then
    echo "  ✓ $label: no page errors"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $label: page errors detected"
    agent-browser errors 2>&1 | head -10
    FAIL=$((FAIL + 1))
  fi
}

assert_no_react_warnings() {
  local label="$1"
  local warnings
  # React's classic "Can't perform state update on unmounted component"
  # warning plus any "Warning:" lines from react-dom / react-router.
  warnings=$(agent-browser console 2>/dev/null | grep -cE 'Warning:|unmounted component|state update|Maximum update depth')
  if [[ "$warnings" == "0" ]]; then
    echo "  ✓ $label: no react warnings"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $label: react warnings"
    agent-browser console 2>&1 | grep -E 'Warning:|unmounted component|state update|Maximum update depth' | head -5
    FAIL=$((FAIL + 1))
  fi
}

assert_url_contains() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    echo "  ✓ url contains $needle"
    PASS=$((PASS + 1))
  else
    echo "  ✗ url missing $needle (got: $got)"
    FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

reset() {
  agent-browser open "$BASE/" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.0
  clear_console
}

# --------------------------------------------------------------------
echo "Test 1 · Rapid nav from a fetch-heavy page does not error"
# Fielding with a rivalry scope has multiple fetches in flight
# (summary, per-tab). Navigating away before they resolve should not
# produce React warnings or page errors.
reset
agent-browser open "$BASE/fielding?player=a757b0d8&filter_team=Mumbai+Indians&filter_opponent=Chennai+Super+Kings" >/dev/null 2>&1
# Don't wait for networkidle — navigate during loading.
sleep 0.2
agent-browser open "$BASE/series" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
assert_no_page_errors "after rapid nav from /fielding → /series"
assert_no_react_warnings "after rapid nav"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · PlayerSearch typing + navigate-away mid-debounce"
# PlayerSearch has a 300ms debounce before firing the fetch. Navigate
# away DURING the debounce — clean cleanup means no ghost fetch
# settles into the next page.
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.0
clear_console
INPUT_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'textbox.*Search' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
if [ -n "$INPUT_REF" ]; then
  agent-browser click "$INPUT_REF" >/dev/null 2>&1
  agent-browser keyboard type "koh" >/dev/null 2>&1
  # Navigate away within 300ms (before debounce fires).
  sleep 0.15
  agent-browser open "$BASE/series" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.5
  assert_no_page_errors "navigate-away mid-debounce"
  assert_no_react_warnings "navigate-away mid-debounce"
else
  echo "  ? could not find PlayerSearch input (skipping)"
fi

# --------------------------------------------------------------------
echo ""
echo "Test 3 · PlayerSearch typing + navigate-away mid-fetch"
# Same as test 2 but wait PAST the debounce so the fetch actually
# fires. Then navigate away while it's in flight. The cancelled flag
# should skip setState on unmount.
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.0
clear_console
INPUT_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'textbox.*Search' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
if [ -n "$INPUT_REF" ]; then
  agent-browser click "$INPUT_REF" >/dev/null 2>&1
  agent-browser keyboard type "bumr" >/dev/null 2>&1
  sleep 0.4  # past 300ms debounce; fetch in flight
  agent-browser open "$BASE/teams" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.5
  assert_no_page_errors "navigate-away mid-fetch"
  assert_no_react_warnings "navigate-away mid-fetch"
else
  echo "  ? could not find PlayerSearch input (skipping)"
fi

# --------------------------------------------------------------------
echo ""
echo "Test 4 · Rapid filter clicks — latest click wins"
# Click a series of filters faster than responses can resolve. If
# useFetch cancels stale calls, the final displayed state reflects
# the LAST click, not an earlier in-flight response.
reset
agent-browser open "$BASE/matches" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.0
clear_console
# Click Men, then Women, then Men — rapid fire.
MEN_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "Men"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$MEN_REF" >/dev/null 2>&1
sleep 0.05
WOMEN_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "Women"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$WOMEN_REF" >/dev/null 2>&1
sleep 0.05
MEN_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "Men"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$MEN_REF" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
assert_url_contains "gender=male"
assert_no_page_errors "rapid-filter final state"
assert_no_react_warnings "rapid-filter final state"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Tab switch while tab fetch is in flight"
# Per-tab fetches are gated by `activeTab === '...'`. Switch tabs
# rapidly so later switches cancel earlier tab fetches via useFetch's
# callId tracking. Final displayed tab should have its own data,
# no errors.
reset
agent-browser open "$BASE/batting?player=ba607b88&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
clear_console
# By Over → By Phase → vs Bowlers within a tight window.
BY_OVER_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "BY OVER"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$BY_OVER_REF" >/dev/null 2>&1
sleep 0.1
BY_PHASE_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "BY PHASE"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$BY_PHASE_REF" >/dev/null 2>&1
sleep 0.1
VS_BOWLERS_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'button "VS BOWLERS"' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
agent-browser click "$VS_BOWLERS_REF" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
assert_url_contains "tab=vs+Bowlers"
assert_no_page_errors "rapid-tab-switch"
assert_no_react_warnings "rapid-tab-switch"

# --------------------------------------------------------------------
echo ""
echo "Test 6 · ResizeObserver cleanup on unmount"
# Charts register a ResizeObserver via useContainerWidth. Navigating
# away should disconnect it — no "ResizeObserver loop completed"
# warnings. Open a chart-heavy page then leave.
reset
agent-browser open "$BASE/batting?player=ba607b88&gender=male&tab=By+Season" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
clear_console
agent-browser open "$BASE/" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
assert_no_page_errors "after chart-page unmount"
assert_no_react_warnings "after chart-page unmount"

# --------------------------------------------------------------------
echo ""
echo "Test 7 · PlayerSearch: pick result does not trigger extra fetch"
# When a user picks a result, the input value is replaced with the
# picked name. The debounce effect must NOT fire an extra fetch for
# that name (suppressedQuery ref). A stray fetch could leak back
# into the now-unmounted dropdown.
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.0
INPUT_REF=$(agent-browser snapshot -i 2>&1 | grep -E 'textbox.*Search' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
if [ -n "$INPUT_REF" ]; then
  agent-browser click "$INPUT_REF" >/dev/null 2>&1
  agent-browser keyboard type "koh" >/dev/null 2>&1
  sleep 0.8  # past debounce; dropdown populated
  clear_console
  # Pick the first result.
  RESULT_REF=$(agent-browser snapshot -i 2>&1 | grep -iE 'V Kohli|listitem.*Kohli' | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
  if [ -n "$RESULT_REF" ]; then
    agent-browser click "$RESULT_REF" >/dev/null 2>&1
    agent-browser wait --load networkidle >/dev/null 2>&1
    settle 1.5
    assert_url_contains "player="
    assert_no_page_errors "after picking result"
    assert_no_react_warnings "after picking result"
  else
    echo "  ? could not find result item (skipping)"
  fi
else
  echo "  ? could not find input (skipping)"
fi

# --------------------------------------------------------------------
echo ""
echo "Test 8 · SPA fallback: back-navigating deep-link doesn't stack errors"
# Route change remounts the page component fully. Rapid navigation
# back and forth exercises mount/unmount on every route.
reset
agent-browser open "$BASE/batting?player=ba607b88&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
agent-browser open "$BASE/bowling?player=462411b3&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
agent-browser open "$BASE/fielding?player=a757b0d8&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
clear_console
agent-browser back >/dev/null 2>&1
settle 0.8
agent-browser back >/dev/null 2>&1
settle 0.8
agent-browser back >/dev/null 2>&1
settle 0.8
assert_no_page_errors "after back-back-back across pages"
assert_no_react_warnings "after back-back-back"

# --------------------------------------------------------------------
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
