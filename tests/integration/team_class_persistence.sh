#!/bin/bash
# v3 team_class FilterBar — cross-tab persistence.
#
# Asserts team_class survives navigation across tabs:
#   /teams → /batting → /series → /matches → /venues → /head-to-head
#
# Plus: status strip chip persists across the tab nav. COPY LINK
# always preserves team_class.
#
# Skeleton — assertions stubbed. Fill via commit 2.
#
# Prereqs: agent-browser, vite :5173.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

settle() { sleep "${1:-1.5}"; }

assert_url_has_team_class() {
  # TODO(commit-2): agent-browser eval window.location.search.includes('team_class=full_member')
  echo "TODO: assert URL contains team_class=full_member"
}

# --------------------------------------------------------------------
echo "Test 1 · /teams → /batting nav preserves team_class"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=international&team_class=full_member
#   2. Click "Batting" in nav (or /batting Link)
#   3. assert URL still contains team_class=full_member

# --------------------------------------------------------------------
echo "Test 2 · /batting → /series → /matches → /venues → /head-to-head"
# TODO(commit-2): chain navigation, assert team_class survives every hop.

# --------------------------------------------------------------------
echo "Test 3 · Status strip chip persists across nav"
# TODO(commit-2): on each landing, read scope strip and verify
# "team class: full members" chip is present.

# --------------------------------------------------------------------
echo "Test 4 · Toggle off persists too"
# TODO(commit-2):
#   1. Open URL without team_class
#   2. Navigate /teams → /series → /matches
#   3. Verify URL never gained team_class

# --------------------------------------------------------------------
echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
