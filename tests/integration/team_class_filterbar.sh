#!/bin/bash
# v3 team_class FilterBar — widget rendering + URL state plumbing.
#
# Asserts the FilterBar's "Full members only" pill behaves correctly:
#   - Renders only when team_type=international
#   - Hidden on team_type=club and team_type=''
#   - Toggle on writes ?team_class=full_member to URL
#   - Toggle off removes the param
#   - Status strip surfaces "team class: full members" chip
#   - "reset all" button clears team_class
#   - COPY LINK preserves team_class
#
# Skeleton — assertions stubbed. Fill in via commit 2 of v3 rollout.
#
# Prereqs: agent-browser, vite :5173.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

settle() { sleep "${1:-1.5}"; }

assert_pill_visible() {
  # TODO(commit-2): use agent-browser eval to query DOM for the pill.
  # Selector candidate: button containing text "Full members only".
  # Returns "true"/"false".
  echo "TODO: assert pill visible"
}

assert_pill_hidden() {
  # TODO(commit-2): same selector — should not be present in DOM.
  echo "TODO: assert pill hidden"
}

assert_url_has_param() {
  # TODO(commit-2): check current URL via agent-browser eval window.location.search.
  echo "TODO: assert URL contains team_class=full_member"
}

# --------------------------------------------------------------------
echo "Test 1 · Pill visibility — intl-only gating"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=international
#   2. assert_pill_visible
#   3. Switch Type to club via segmented control (or open a club URL)
#   4. assert_pill_hidden
#   5. Switch Type to '' (All)
#   6. assert_pill_hidden

# --------------------------------------------------------------------
echo "Test 2 · Toggle on/off writes/removes URL param"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=international (pill visible, no team_class on URL)
#   2. Click pill → URL gains ?team_class=full_member, pill shows ▣
#   3. Click pill again → URL drops team_class, pill shows ▢

# --------------------------------------------------------------------
echo "Test 3 · Status strip chip"
# TODO(commit-2):
#   1. Open URL with team_class=full_member
#   2. Read scope strip text — assert contains "full members" or "team class"

# --------------------------------------------------------------------
echo "Test 4 · 'reset all' clears team_class"
# TODO(commit-2):
#   1. Open URL with team_class=full_member + gender=male
#   2. Click 'reset all' button
#   3. Assert URL is clean (no team_class, no gender)

# --------------------------------------------------------------------
echo "Test 5 · COPY LINK preserves team_class"
# TODO(commit-2): if status-strip COPY LINK button writes URL to clipboard,
# verify that URL contains team_class=full_member.

# --------------------------------------------------------------------
echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
