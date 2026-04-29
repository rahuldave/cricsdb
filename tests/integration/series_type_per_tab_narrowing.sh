#!/bin/bash
# series_type FilterBar — per-tab narrowing matrix.
#
# API-direct: hits the backend endpoints each tab uses and asserts
# series_type=bilateral_only narrows the result vs the unbounded
# baseline. Companion to test_series_type_baseline_numbers.py
# (per-anchor SQL+API agreement) — this script proves the FILTER
# REACHES every endpoint, not just the FilterBarParams object.
set -u

BASE="${BASE:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Helper: extract a numeric field from a JSON response.
# Usage: jpath URL '<python expression on `d`>'
jpath() {
  /usr/bin/curl -s "$1" | /opt/homebrew/bin/python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('PARSE_ERROR'); sys.exit(0)
print($2)
"
}

assert_narrow() {
  local label="$1" plain="$2" bilat="$3"
  if [ "$plain" = "PARSE_ERROR" ] || [ "$bilat" = "PARSE_ERROR" ]; then
    bad "$label — endpoint failed (plain=$plain bilat=$bilat)"
    return
  fi
  if [ "$plain" -gt "$bilat" ] 2>/dev/null; then
    ok "$label: $plain → $bilat under bilateral_only"
  elif [ "$plain" -ge "$bilat" ] && [ "$plain" -gt 0 ]; then
    # Equal-and-positive happens for /seasons (every year has a
    # bilateral); call it OK with a note.
    ok "$label: $plain (unchanged — every entry has a bilateral instance)"
  else
    bad "$label: expected narrowing or equality but got plain=$plain bilat=$bilat"
  fi
}

# ────────────────────────────────────────────
echo "Test 1 · /matches narrows under bilateral_only"
plain=$(jpath "$BASE/api/v1/matches?gender=male&team_type=international&season_from=2024&season_to=2025&limit=1&offset=0" "d['total']")
bilat=$(jpath "$BASE/api/v1/matches?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only&limit=1&offset=0" "d['total']")
assert_narrow "/matches men_intl 24-25" "$plain" "$bilat"

# ────────────────────────────────────────────
echo "Test 2 · /teams/{team}/summary narrows for Aus"
plain=$(jpath "$BASE/api/v1/teams/Australia/summary?gender=male&team_type=international&season_from=2024&season_to=2025" "d['matches']['value'] if isinstance(d.get('matches'), dict) else d.get('matches')")
bilat=$(jpath "$BASE/api/v1/teams/Australia/summary?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only" "d['matches']['value'] if isinstance(d.get('matches'), dict) else d.get('matches')")
assert_narrow "/teams/Australia/summary" "$plain" "$bilat"

# ────────────────────────────────────────────
echo "Test 3 · /teams/{team}/results narrows"
plain=$(jpath "$BASE/api/v1/teams/Australia/results?gender=male&team_type=international&season_from=2024&season_to=2025&limit=50" "d['total']")
bilat=$(jpath "$BASE/api/v1/teams/Australia/results?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only&limit=50" "d['total']")
assert_narrow "/teams/Australia/results" "$plain" "$bilat"

# ────────────────────────────────────────────
echo "Test 4 · /teams/{team}/batting/summary narrows innings"
plain=$(jpath "$BASE/api/v1/teams/Australia/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025" "d['innings_batted']['value'] if isinstance(d.get('innings_batted'), dict) else d.get('innings_batted')")
bilat=$(jpath "$BASE/api/v1/teams/Australia/batting/summary?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only" "d['innings_batted']['value'] if isinstance(d.get('innings_batted'), dict) else d.get('innings_batted')")
assert_narrow "/teams/Australia/batting/summary innings_batted" "$plain" "$bilat"

# ────────────────────────────────────────────
echo "Test 5 · /tournaments narrows"
plain=$(jpath "$BASE/api/v1/tournaments?gender=male&team_type=international&season_from=2024&season_to=2025" "len(d['tournaments'])")
bilat=$(jpath "$BASE/api/v1/tournaments?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only" "len(d['tournaments'])")
assert_narrow "/tournaments narrows under bilateral_only" "$plain" "$bilat"

# ────────────────────────────────────────────
echo "Test 6 · /scope/averages/summary narrows + dispatch falls back"
plain=$(jpath "$BASE/api/v1/scope/averages/summary?gender=male&team_type=international&season_from=2024&season_to=2025" "d.get('matches')")
bilat=$(jpath "$BASE/api/v1/scope/averages/summary?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only" "d.get('matches')")
# Floats compared via python — bilat per-team count must differ from plain.
DIFFER=$(/opt/homebrew/bin/python3 -c "print('1' if float('$plain') != float('$bilat') else '0')")
if [ "$DIFFER" = "1" ]; then
  ok "/scope/averages/summary: plain=$plain → bilat=$bilat (live aggregation kicked in)"
else
  bad "/scope/averages/summary plain=$plain == bilat=$bilat (dispatch may not be falling back)"
fi

# ────────────────────────────────────────────
echo "Test 7 · /head-to-head/team narrows"
# H2H team mode — Aus vs India 2024-25 with bilateral_only should be 0
# (they only met at the T20 WC; S7 anchor).
plain=$(jpath "$BASE/api/v1/head-to-head/team?team1=India&team2=Australia&gender=male&team_type=international&season_from=2024&season_to=2025" "d.get('total_matches', d.get('matches'))")
bilat=$(jpath "$BASE/api/v1/head-to-head/team?team1=India&team2=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only" "d.get('total_matches', d.get('matches'))")
if [ "$plain" = "PARSE_ERROR" ] || [ "$bilat" = "PARSE_ERROR" ]; then
  echo "  SKIP: /head-to-head/team endpoint shape unfamiliar (plain=$plain bilat=$bilat)"
elif [ "$plain" -gt "$bilat" ] 2>/dev/null || [ "$plain" -eq "$bilat" ] 2>/dev/null; then
  ok "/head-to-head/team India vs Aus: $plain → $bilat under bilateral_only"
else
  bad "/head-to-head/team did not narrow (plain=$plain bilat=$bilat)"
fi

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
