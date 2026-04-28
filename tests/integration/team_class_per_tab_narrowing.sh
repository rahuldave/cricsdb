#!/bin/bash
# v3 team_class FilterBar — per-tab narrowing assertions.
#
# Quick spot checks on the high-traffic surfaces. Asserts each tab
# narrows under team_class=full_member by hitting the API directly
# (the frontend's job is just to forward the param; the API
# narrowing was verified at the SQL layer in
# tests/sanity/test_team_class_baseline_numbers.py).
#
# This script's specific job: prove that GET requests to surface-
# representative endpoints with team_class=full_member return
# narrowed responses vs without.
set -u

API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Compare two JSON paths. expr should jq-extract a numeric or string value.
compare_narrowing() {
  local label="$1" url="$2" jq_expr="$3"
  local unb=$(curl -s "$API$url" | python3 -c "import json,sys; d=json.load(sys.stdin); $jq_expr")
  local fm=$(curl -s "$API${url}&team_class=full_member" | python3 -c "import json,sys; d=json.load(sys.stdin); $jq_expr")
  if [ -z "$unb" ] || [ -z "$fm" ]; then
    bad "$label — unable to extract values (unb='$unb' fm='$fm')"
    return
  fi
  if [ "$unb" = "$fm" ]; then
    bad "$label — FM did NOT narrow (unb=$unb == fm=$fm)"
  else
    ok "$label — narrowed: unb=$unb → fm=$fm"
  fi
}

compare_unchanged() {
  local label="$1" url="$2" jq_expr="$3"
  local unb=$(curl -s "$API$url" | python3 -c "import json,sys; d=json.load(sys.stdin); $jq_expr")
  local fm=$(curl -s "$API${url}&team_class=full_member" | python3 -c "import json,sys; d=json.load(sys.stdin); $jq_expr")
  if [ "$unb" = "$fm" ]; then
    ok "$label — defensive gate fires: unb=fm=$unb"
  else
    bad "$label — gate FAILED: unb=$unb ≠ fm=$fm"
  fi
}

scope="gender=male&team_type=international&season_from=2024&season_to=2025"

echo "Test · Intl surfaces narrow under FM"
compare_narrowing "/teams/Australia/summary matches" \
  "/api/v1/teams/Australia/summary?$scope" \
  "print(d['matches']['value'])"

compare_narrowing "/scope/averages/summary matches" \
  "/api/v1/scope/averages/summary?$scope" \
  "print(d['matches'])"

compare_narrowing "/teams/landing intl associate count (FM drops associates)" \
  "/api/v1/teams/landing?$scope" \
  "print(len(d['international']['men']['associate']))"

compare_narrowing "/series/landing icc events count" \
  "/api/v1/series/landing?$scope" \
  "print(d['international']['icc_events'][0]['matches'])"

compare_narrowing "/series/summary T20 WC matches" \
  "/api/v1/series/summary?$scope&tournament=T20%20World%20Cup%20%28Men%29" \
  "print(d['matches'])"

compare_narrowing "/tournaments dropdown count" \
  "/api/v1/tournaments?$scope" \
  "print(len(d['tournaments']))"

compare_narrowing "/teams typeahead with q=sco" \
  "/api/v1/teams?$scope&q=sco" \
  "print(len(d['teams']))"

echo
echo "Test · Club surface — defensive gate"
ipl_scope="gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2025&season_to=2025"
compare_unchanged "/teams/RCB/summary on IPL 2025" \
  "/api/v1/teams/Royal%20Challengers%20Bengaluru/summary?$ipl_scope" \
  "print(d['matches']['value'])"

compare_unchanged "/scope/averages/summary IPL 2025 (gate noop)" \
  "/api/v1/scope/averages/summary?$ipl_scope" \
  "print(d['matches'])"

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
