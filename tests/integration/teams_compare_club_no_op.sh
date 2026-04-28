#!/bin/bash
# v3 team_class FilterBar — Compare tab Anchor G (club no-op control).
#
# URL: /teams?team=Royal Challengers Bengaluru&tab=Compare
#      &compare1=__avg__&compare2=Sunrisers Hyderabad
#      &gender=male&team_type=club&tournament=Indian Premier League
#      &season_from=2025&season_to=2025
#
# Anchor G: with team_type=club, the FilterBar pill is HIDDEN. Even
# if a URL artificially injects team_class=full_member, the
# defensive backend gate makes it a no-op. RCB col + avg col + SRH
# col are byte-identical to HEAD baseline (no v3 change).
#
# Skeleton — fill via commit 5.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

URL_CLEAN="$BASE/teams?team=Royal%20Challengers%20Bengaluru&tab=Compare&compare1=__avg__&compare2=Sunrisers%20Hyderabad&gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2025&season_to=2025"
URL_DIRTY="$URL_CLEAN&team_class=full_member"

echo "Anchor G clean — $URL_CLEAN"
# TODO(commit-5):
#   1. open URL_CLEAN
#   2. capture: RCB Matches, Avg Matches, SRH Matches, plus 3 chip envelopes
#   3. assert FilterBar pill is HIDDEN (selector returns null)

echo "Anchor G with-team_class — $URL_DIRTY"
# TODO(commit-5):
#   1. open URL_DIRTY
#   2. capture: same cells as clean
#   3. assert URL was auto-cleaned on mount (team_class stripped via deep-link guard)
#      OR — if the guard doesn't strip — assert all cell values byte-identical to clean
#      (defensive backend gate makes team_class a no-op)
#   4. assert FilterBar pill is HIDDEN

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
