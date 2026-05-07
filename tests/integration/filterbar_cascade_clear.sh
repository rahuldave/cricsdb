#!/bin/bash
# FilterBar cascade-clear + auto-correct tests.
#
# Covers the bug fixed in commit 8a40375 (cascade-clear tournament
# when user clears gender/team_type) and the symmetric auto-correct
# deep-link logic that fights it.
#
# Bug class: when the user clicks the "All" pill on a coupled
# filter (gender or team_type), the dependent narrowing
# (tournament) must also clear, otherwise the auto-correct
# deep-link effect re-asserts the value the user just cleared
# from the tournament's metadata. "Spring-back" UX bug.
#
# This test suite asserts:
#   1. Cascade-clear on team_type=All click — tournament also clears
#   2. Cascade-clear on gender=All click — tournament also clears
#   3. Mismatched-pick still clears the tournament (preserved behavior)
#   4. team_type=club WITHOUT tournament still clears cleanly on All
#   5. Auto-correct deep-link still fills missing fields from
#      tournament metadata (the legitimate use of the loop)
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_url_contains() {
  local label="$1" needle="$2"
  local url=$(unq "$(ab_eval "location.search")")
  if [[ "$url" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not in URL: $url"; fi
}

assert_url_lacks() {
  local label="$1" needle="$2"
  local url=$(unq "$(ab_eval "location.search")")
  if [[ "$url" != *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' unexpectedly in URL: $url"; fi
}

# Click a wisden-seg button by its visible label, scoped to the
# global filter group so we don't accidentally hit the InningToggle
# or the panel's metric-tabs (which share .wisden-seg).
click_filter_seg() {
  local label="$1" position_after="$2"
  ab_eval "(() => {
    const all = Array.from(document.querySelectorAll('button.wisden-seg'))
    // 'position_after' is the label of a known sibling; the filter group
    // is the one whose buttons sit just before it in DOM order.
    const anchor = all.findIndex(b => b.textContent.trim() === '${position_after}')
    if (anchor < 0) return 'no-anchor'
    // Find the matching label in the SAME group as anchor (= preceding
    // few elements). Walk backwards from anchor until we find label.
    for (let i = anchor; i >= Math.max(0, anchor - 4); i--) {
      if (all[i].textContent.trim() === '${label}') { all[i].click(); return 'clicked' }
    }
    return 'not-found'
  })()" >/dev/null
}

agent-browser close --all >/dev/null 2>&1 || true
agent-browser set viewport 1280 1024 >/dev/null 2>&1
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · team_type=All click cascades to clear tournament"

ab open "$BASE/batting?player=ba607b88&gender=male&tournament=Indian+Premier+League&team_type=club"
settle 3
# 'Intl' is the type-pill positioned right after the (current) Club.
# Click the type-group's 'All' (just before Intl).
click_filter_seg "All" "Intl"
settle 2
assert_url_contains "team_type cleared (URL lacks team_type=club)" "gender=male"
assert_url_lacks    "team_type=club cleared on All click" "team_type=club"
assert_url_lacks    "tournament=IPL cascade-cleared too"  "tournament=Indian"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · gender=All click cascades to clear tournament"

# Use /matches (no player-nationality auto-fill effect) to isolate
# the FilterBar cascade behavior. On /batting?player=X, the page-
# level effect in Batting.tsx re-asserts gender from the player's
# nationality after the FilterBar clears it — that's a separate
# auto-fill, intentionally not in scope for this test.
ab open "$BASE/matches?gender=male&tournament=Indian+Premier+League&team_type=club"
settle 3
click_filter_seg "All" "Men"
settle 2
assert_url_lacks "gender=male cleared on All click (no player auto-fill)" "gender=male"
assert_url_lacks "tournament=IPL cascade-cleared on gender=All" "tournament=Indian"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Mismatched type pick still clears tournament"

ab open "$BASE/batting?player=ba607b88&gender=male&tournament=Indian+Premier+League&team_type=club"
settle 3
click_filter_seg "Intl" "Club"
settle 2
assert_url_contains "team_type=international after Intl click" "team_type=international"
assert_url_lacks    "tournament cleared (IPL is club, mismatch)" "tournament=Indian"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · team_type=All without tournament — clean clear"

ab open "$BASE/batting?player=ba607b88&gender=male&team_type=club"
settle 3
click_filter_seg "All" "Intl"
settle 2
assert_url_lacks "team_type=club cleared without spurious tournament addition" "team_type"
assert_url_lacks "no tournament added by accident" "tournament"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Auto-correct deep-link still fills missing type from tournament"

# URL has tournament=IPL but no team_type — auto-correct should
# fill team_type=club (because IPL is unambiguously a club tournament).
# This is the LEGITIMATE use of the auto-correct effect; it should
# still fire on initial load.
ab open "$BASE/batting?player=ba607b88&tournament=Indian+Premier+League"
settle 3
assert_url_contains "auto-correct fills team_type=club from tournament metadata" "team_type=club"
assert_url_contains "auto-correct fills gender=male from tournament metadata" "gender=male"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo "$PASS pass · $FAIL fail"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
