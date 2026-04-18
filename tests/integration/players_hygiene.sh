#!/bin/bash
# Players-tab mount / unmount hygiene tests.
#
# Asserts on NEGATIVE signals — no React warnings, no uncaught page
# errors — under the conditions most likely to surface setState-after-
# unmount, stale-fetch-leaks, or leaked listeners:
#
#   1. Rapid filter toggling with a 2-way compare mounted (two
#      parallel 4-way getPlayerProfile fetches redone per filter click).
#   2. Adding then immediately removing a compare column while its
#      fetches are still in flight.
#   3. Rapid navigation across /players ↔ /batting ↔ /bowling ↔ back
#      to /players with a player selected — the URL transition unmounts
#      and remounts fetch-driven components each time.
#   4. Hover dropdown + mobile sub-row render without runtime errors.
#
# Prerequisites + how to run: see README.md.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

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
  warnings=$(agent-browser console 2>/dev/null | grep -cE 'Warning:|unmounted component|state update|Maximum update depth')
  if [[ "$warnings" == "0" ]]; then
    echo "  ✓ $label: no react warnings"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $label: react warnings detected"
    agent-browser console 2>&1 | grep -E 'Warning:|unmounted component|state update|Maximum update depth' | head -5
    FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.0}"; }

ref_for() {
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

KOHLI=ba607b88
MARKRAM=6a26221c
SMITH=30a45b23

# --------------------------------------------------------------------
echo "Test 1 · Rapid filter toggles with 2-way compare mounted"
clear_console
agent-browser open "$BASE/players?player=$KOHLI&compare=$MARKRAM&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
# Flip gender and team-type chips rapidly — each click re-fires four
# parallel profile fetches per column, so stale-result race conditions
# would surface as setState-after-unmount or console warnings.
for i in 1 2 3 4 5; do
  WOMEN=$(ref_for 'button "Women"'); agent-browser click "$WOMEN" >/dev/null 2>&1
  sleep 0.25
  MEN=$(ref_for 'button "Men"'); agent-browser click "$MEN" >/dev/null 2>&1
  sleep 0.25
  INTL=$(ref_for 'button "Intl"'); agent-browser click "$INTL" >/dev/null 2>&1
  sleep 0.25
  ALL_TYPE=$(agent-browser snapshot -i 2>&1 | grep -E 'button "All"' | sed -n '2p' | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/')
  [ -n "$ALL_TYPE" ] && agent-browser click "$ALL_TYPE" >/dev/null 2>&1
  sleep 0.25
done
settle 2.0
assert_no_page_errors "rapid filter toggles"
assert_no_react_warnings "rapid filter toggles"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Add then quickly remove a compare column (in-flight unmount)"
clear_console
agent-browser open "$BASE/players?player=$KOHLI&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
# Type a name into the compare picker and click, then within ~300ms
# click the new column's ✕. The fetch for the newly-added column will
# likely still be in flight when the column unmounts.
agent-browser eval '(() => {
  const input = document.querySelector(".wisden-compare-picker input");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  setter.call(input, "Markram");
  input.dispatchEvent(new Event("input", { bubbles: true }));
})()' >/dev/null 2>&1
settle 1.2
agent-browser eval '(() => {
  const lis = document.querySelectorAll(".wisden-playersearch-list li");
  for (const li of lis) {
    if (li.textContent.includes("Markram")) { li.click(); return; }
  }
})()' >/dev/null 2>&1
# Remove column ASAP — before the profile fetches complete.
sleep 0.3
REMOVE=$(ref_for 'button "Remove AK Markram"')
[ -n "$REMOVE" ] && agent-browser click "$REMOVE" >/dev/null 2>&1
settle 2.0
assert_no_page_errors "add+remove compare mid-flight"
assert_no_react_warnings "add+remove compare mid-flight"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Rapid nav across /players → /batting → /bowling → /players"
clear_console
agent-browser open "$BASE/players?player=$KOHLI&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
for route in batting bowling fielding players; do
  agent-browser open "$BASE/$route?player=$KOHLI&gender=male" >/dev/null 2>&1
  sleep 0.4
done
settle 2.0
assert_no_page_errors "rapid route switches"
assert_no_react_warnings "rapid route switches"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · 3-way compare → drop a column → back to 2-way"
clear_console
agent-browser open "$BASE/players?player=$KOHLI&compare=$MARKRAM,$SMITH&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
REMOVE_SMITH=$(ref_for 'button "Remove SPD Smith"')
[ -n "$REMOVE_SMITH" ] && agent-browser click "$REMOVE_SMITH" >/dev/null 2>&1
settle 1.5
# URL-side sanity plus negative-signal assertions.
URL=$(agent-browser get url 2>/dev/null)
if [[ "$URL" == *"compare=$MARKRAM"* && "$URL" != *"$SMITH"* ]]; then
  echo "  ✓ 3-way drop leaves 2-way"
  PASS=$((PASS + 1))
else
  echo "  ✗ 3-way drop URL wrong: $URL"
  FAIL=$((FAIL + 1))
fi
assert_no_page_errors "3-way → 2-way"
assert_no_react_warnings "3-way → 2-way"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Rapid tile clicks on landing"
clear_console
agent-browser open "$BASE/players" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# Click a couple of profile tiles in quick succession so the primary
# useFetch for the profile restarts mid-flight.
K_REF=$(ref_for 'link.*V Kohli')
[ -n "$K_REF" ] && agent-browser click "$K_REF" >/dev/null 2>&1
sleep 0.4
agent-browser back >/dev/null 2>&1
sleep 0.4
B_REF=$(ref_for 'link.*JJ Bumrah')
[ -n "$B_REF" ] && agent-browser click "$B_REF" >/dev/null 2>&1
settle 2.0
assert_no_page_errors "landing rapid tiles"
assert_no_react_warnings "landing rapid tiles"

# --------------------------------------------------------------------
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
