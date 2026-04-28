#!/bin/bash
# v3 team_class FilterBar — gating + auto-clear behaviour.
#
# Defense-in-depth tests for the three gating layers from spec §3:
#   1. FilterBar widget — pill only when team_type=international (covered by team_class_filterbar.sh)
#   2. Frontend deep-link guard — useEffect strips team_class on mount
#      when team_type is wrong (with replace-mode, no history pollution)
#   3. Backend defensive gate — full_member_clause only fires for
#      team_type='international' (tested via direct API call)
#
# Skeleton — assertions stubbed. Fill in via commit 2 (frontend gates)
# + commit 1 (backend gate via filters.build).
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

settle() { sleep "${1:-1.5}"; }

# --------------------------------------------------------------------
echo "Test 1 · Switching Type from intl to club auto-clears team_class"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=international&team_class=full_member
#   2. Verify URL has team_class
#   3. Click Type segmented "Club"
#   4. assert URL no longer contains team_class
#   5. Verify the auto-clear used replace mode (history.length unchanged)
#      via agent-browser: const before=history.length; click; const after=history.length;
#      after === before+1 (the team_type push) but team_class was cleared in same setUrlParams.

# --------------------------------------------------------------------
echo "Test 2 · Switching Type from intl to '' (All) auto-clears team_class"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=international&team_class=full_member
#   2. Click Type segmented "All"
#   3. assert URL no longer contains team_class

# --------------------------------------------------------------------
echo "Test 3 · Deep-link with bad combo cleans on mount"
# TODO(commit-2):
#   1. Open /teams?gender=male&team_type=club&team_class=full_member
#      (impossible state — backend guard prevents the SQL clause from firing,
#       but the URL is still wrong)
#   2. Wait for mount-time useEffect
#   3. assert URL no longer contains team_class
#   4. assert team_type is still 'club' (the guard cleaned the FILTER not the team_type)

# --------------------------------------------------------------------
echo "Test 4 · Deep-link with team_class but no team_type"
# TODO(commit-2):
#   1. Open /teams?team_class=full_member (no team_type)
#   2. assert URL no longer contains team_class on mount

# --------------------------------------------------------------------
echo "Test 5 · Backend defensive gate — direct API call"
# TODO(commit-1 verification):
#   1. curl '$API/api/v1/teams/Royal Challengers Bengaluru/summary?gender=male&team_type=club&tournament=Indian Premier League&season_from=2025&season_to=2025'
#      → response_a
#   2. curl SAME URL + '&team_class=full_member'
#      → response_b
#   3. assert response_a == response_b (defensive backend gate makes team_class no-op for clubs)

# --------------------------------------------------------------------
echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
