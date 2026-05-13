#!/bin/bash
# Series subtab rename + URL alias from spec-series-trend-charts.md step 6.
#
# Asserts:
#  1. Series tab bar renders the renamed labels (Batting / Bowling /
#     Fielding) instead of the old player-noun versions.
#  2. Deep-linking to the old slug (?tab=Batters) lands on the new
#     tab AND normalises the URL to the new slug — replace mode, no
#     extra history entry.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  local hu=$(unq "$haystack")
  if [[ "$hu" == *"$needle"* ]]; then ok "$label contains '$needle'"
  else bad "$label — '$hu' missing '$needle'"; fi
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Test 1 · Series tab labels show Batting/Bowling/Fielding"
ab open "$BASE/series?tournament=Indian%20Premier%20League"
sleep 4
labels=$(ab_eval "JSON.stringify(Array.from(document.querySelectorAll('.wisden-tab')).map(t => t.textContent?.trim()))")
assert_contains "Series tab list" "Batting" "$labels"
assert_contains "Series tab list" "Bowling" "$labels"
assert_contains "Series tab list" "Fielding" "$labels"
# Old labels gone.
if echo "$labels" | grep -q '"Batters"\|"Bowlers"\|"Fielders"'; then
  bad "Old player-noun labels still present in tab list: $labels"
else
  ok "Old player-noun labels absent from tab list"
fi

echo "Test 2 · ?tab=Batters alias lands on Batting + URL normalised"
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Batters"
sleep 4
active=$(ab_eval "document.querySelector('.wisden-tab.is-active')?.textContent?.trim() ?? ''")
assert_eq "Active tab from ?tab=Batters" "Batting" "$active"
url=$(ab_eval "window.location.href")
assert_contains "URL normalised to tab=Batting" "tab=Batting" "$url"
if echo "$url" | grep -q "tab=Batters"; then
  bad "URL still contains tab=Batters after alias normalise"
else
  ok "URL no longer contains tab=Batters"
fi

echo "Test 3 · ?tab=Bowlers alias lands on Bowling"
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Bowlers"
sleep 4
got=$(ab_eval "document.querySelector('.wisden-tab.is-active')?.textContent?.trim() ?? ''")
assert_eq "Active tab from ?tab=Bowlers" "Bowling" "$got"

echo "Test 4 · ?tab=Fielders alias lands on Fielding"
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Fielders"
sleep 4
got=$(ab_eval "document.querySelector('.wisden-tab.is-active')?.textContent?.trim() ?? ''")
assert_eq "Active tab from ?tab=Fielders" "Fielding" "$got"

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
