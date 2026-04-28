#!/bin/bash
# v3 team_class FilterBar — Compare tab Anchor E1.
#
# URL: /teams?team=Australia&tab=Compare&compare1=__avg__&compare2=India
#      &gender=male&team_type=international&season_from=2024&season_to=2026
#      &team_class=full_member
#
# Mode E1: FilterBar narrows team data; compare slots inherit team_class
# via useCompareSlots:50 fix. All three columns narrow:
#   - Aus col: 16 matches (anchor A4)
#   - Avg col: 140 matches (anchor A2)
#   - India col: 31 matches (anchor A6)
#
# Chip alignment is NATIVE — both team-side and avg-side requests
# carry filters.team_class=full_member. No chip_team_class hint sent.
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

URL="$BASE/teams?team=Australia&tab=Compare&compare1=__avg__&compare2=India&gender=male&team_type=international&season_from=2024&season_to=2026&team_class=full_member"

echo "Anchor E1 — $URL"
# TODO(commit-5):
#   1. agent-browser open "$URL"
#   2. wait networkidle
#   3. Read Aus col Matches cell → assert == 16
#   4. Read Avg col Matches cell → assert == 140
#   5. Read India col Matches cell → assert == 31
#   6. Read Aus col Run Rate → assert numerical match to anchor C2
#   7. For each chip-bearing metric (RR, Boundary %, Dot %):
#      - Read chip.value, chip.scope_avg from team col
#      - Read displayed value from avg col
#      - assert chip.scope_avg == avg col displayed value
#      - assert chip math: displayed delta% == (value - scope_avg) / scope_avg * 100
#   8. Verify FilterBar pill is "Full members only" with ▣ filled
#   9. Verify status strip chip "team class: full members" is visible

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
exit $((FAIL > 0 ? 1 : 0))
