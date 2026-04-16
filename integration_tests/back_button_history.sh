#!/bin/bash
# Back-button / history-discipline integration tests.
#
# Verifies:
#   1. User-initiated filter / tab / button changes push history.
#   2. Programmatic auto-corrections (deep-link fills, default season
#      window, invalid-state repair, URL-shape migration) do NOT push.
#   3. The series_type setState-during-render anti-pattern stays fixed.
#
# Requires:
#   - agent-browser installed (npm i -g agent-browser).
#   - A vite dev server on http://localhost:5173 (npm run dev in frontend/).
#   - A FastAPI backend on http://localhost:8000 (uv run uvicorn ... --reload).
#
# Run:
#   ./integration_tests/back_button_history.sh
#
# Exits non-zero on the first failure.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

# Close any lingering agent-browser sessions so prior HMR state /
# cached bundles don't affect assertions. Harmless if no session open.
agent-browser close --all >/dev/null 2>&1 || true
sleep 1

assert_url_eq() {
  local expected="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %s\n" "$expected"
    PASS=$((PASS + 1))
  else
    printf "  ✗ expected: %s\n" "$expected"
    printf "    got:      %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

assert_url_contains() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"
    PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n" "$needle"
    printf "    got: %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

# --------------------------------------------------------------------
# Go home to reset history for each test block.
reset() {
  agent-browser open "$BASE/" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.0
}

click_ref() {
  agent-browser click "$1" >/dev/null 2>&1
  settle 1.0
}

ref_for() {
  # Grab the first @eNN ref whose line matches the given regex.
  # agent-browser snapshot prints [ref=eN]; click expects @eN.
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

# --------------------------------------------------------------------
echo "Test 1 · Filter clicks push a real back stack"
reset
agent-browser open "$BASE/matches" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.2
MEN_REF=$(ref_for 'button "Men"')
click_ref "$MEN_REF"
assert_url_eq "$BASE/matches?gender=male"
INTL_REF=$(ref_for 'button "Intl"')
click_ref "$INTL_REF"
assert_url_eq "$BASE/matches?gender=male&team_type=international"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/matches?gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/matches"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Self-correcting deep-link (gender fill) does NOT push"
reset
agent-browser open "$BASE/batting?player=ba607b88" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.0
assert_url_eq "$BASE/batting?player=ba607b88&gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · useDefaultSeasonWindow (one-shot default) does NOT push"
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# Latest 3 seasons lie in the recent window. Exact values drift with
# the data — just confirm the params appear and back returns to /.
assert_url_contains "season_from="
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · FilterBar auto-narrow on filter_team (MI × CSK → IPL)"
reset
agent-browser open "$BASE/fielding?player=a757b0d8&filter_team=Mumbai+Indians&filter_opponent=Chennai+Super+Kings" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "tournament=Indian+Premier+League"
assert_url_contains "team_type=club"
assert_url_contains "gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · series_type invalid auto-reset (the fixed anti-pattern)"
reset
agent-browser open "$BASE/series?filter_team=India&filter_opponent=Australia&gender=male&team_type=international&series_type=bilateral" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# Flip to Club; the series_type=bilateral option disappears and the
# effect should replace it away (no extra history entry).
CLUB_REF=$(ref_for 'button "Club"')
click_ref "$CLUB_REF"
assert_url_contains "team_type=club"
agent-browser get url 2>/dev/null | grep -q "series_type=" && {
  echo "  ✗ series_type should have been stripped"
  FAIL=$((FAIL + 1))
} || {
  echo "  ✓ series_type stripped"
  PASS=$((PASS + 1))
}
# Back: should return to the bilateral-valid state (one history entry
# for the Club click, plus the initial load — NOT multiple per-render
# pushes).
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "series_type=bilateral"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 6 · ScopeIndicator CLEAR strips ALL narrowing; back restores"
reset
# Arrive with a rivalry lens AND a tournament the user added on top
# of it. CLEAR must drop BOTH — not just filter_team / filter_opponent
# but also tournament and team_type. The rule: CLEAR returns the
# player to their full career; back button walks to any past narrowed
# state.
agent-browser open "$BASE/batting?player=ba607b88&gender=male&filter_team=India&filter_opponent=Australia&team_type=international&tournament=T20+World+Cup+%28Men%29" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# NB: ScopeIndicator's aria-label is "Clear scope and return to full
# career" — match by prefix, not by the full quoted label, or grep
# whiffs on the trailing ".
CLEAR_REF=$(ref_for 'button "Clear scope')
click_ref "$CLEAR_REF"
# Every narrowing param must be gone. Only player + gender stay.
for p in filter_team filter_opponent tournament team_type season_from season_to; do
  agent-browser get url 2>/dev/null | grep -q "$p=" && {
    echo "  ✗ $p should have been cleared"
    FAIL=$((FAIL + 1))
  } || {
    echo "  ✓ $p cleared"
    PASS=$((PASS + 1))
  }
done
assert_url_contains "player=ba607b88"
assert_url_contains "gender=male"
# Back returns to the full scoped URL — everything restored.
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "filter_team=India"
assert_url_contains "filter_opponent=Australia"
assert_url_contains "tournament=T20+World+Cup"
assert_url_contains "team_type=international"

# --------------------------------------------------------------------
echo ""
echo "Test 7 · Tab switches push history"
reset
agent-browser open "$BASE/batting?player=ba607b88&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
BY_OVER_REF=$(ref_for 'button "BY OVER"')
click_ref "$BY_OVER_REF"
assert_url_contains "tab=By+Over"
VS_BOWLERS_REF=$(ref_for 'button "VS BOWLERS"')
click_ref "$VS_BOWLERS_REF"
assert_url_contains "tab=vs+Bowlers"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "tab=By+Over"

# --------------------------------------------------------------------
echo ""
echo "Test 8 · Legacy /tournaments → /series redirect does NOT push"
reset
agent-browser open "$BASE/tournaments?tournament=Indian+Premier+League" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "/series?tournament=Indian+Premier+League"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 9 · Legacy ?rivalry= param migration does NOT push"
reset
agent-browser open "$BASE/series?rivalry=India,Australia" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_contains "filter_team=India"
assert_url_contains "filter_opponent=Australia"
agent-browser get url 2>/dev/null | grep -q "rivalry=" && {
  echo "  ✗ rivalry= should have been stripped"
  FAIL=$((FAIL + 1))
} || {
  echo "  ✓ rivalry= stripped"
  PASS=$((PASS + 1))
}
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 10 · PlayerLink (dossier tile → player page) pushes"
reset
agent-browser open "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&tab=Batters" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
CTX_REF=$(ref_for 'link "· in Indian Premier League ›"')
click_ref "$CTX_REF"
assert_url_contains "/batting?player="
assert_url_contains "tournament=Indian+Premier+League"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "/series?tournament=Indian+Premier+League"
assert_url_contains "tab=Batters"

# --------------------------------------------------------------------
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
