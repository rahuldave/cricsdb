#!/bin/bash
# Cross-cutting URL-state discipline tests.
#
# The push-vs-replace URL contract applies to every page; this file
# keeps only the tests whose assertions exercise cross-cutting widgets
# (ScopeIndicator, PlayerLink) rather than a single tab's own URL
# behaviour. Tab-specific URL-state tests live in the per-tab scripts:
#
#   /matches filter push                → matches.sh
#   /batting deep-link gender fill      → batting.sh
#   /batting default season window      → batting.sh
#   /batting tab-switch push            → batting.sh
#   /fielding filter_team auto-narrow   → fielding.sh
#   /series series_type invalid reset   → series.sh
#   /tournaments → /series redirect     → series.sh
#   /series rivalry= migration          → series.sh
#
# Requires:
#   - agent-browser installed (npm i -g agent-browser).
#   - Vite dev server on http://localhost:5173.
#   - FastAPI backend on http://localhost:8000 (uv run ... --reload).
#
# Run:  ./tests/integration/cross_cutting_url_state.sh
# Exits non-zero on any failure.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

assert_url_eq() {
  local expected="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %s\n" "$expected"; PASS=$((PASS + 1))
  else
    printf "  ✗ expected: %s\n    got:      %s\n" "$expected" "$got"; FAIL=$((FAIL + 1))
  fi
}

assert_url_contains() {
  local needle="$1" got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"; PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n    got: %s\n" "$needle" "$got"; FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

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
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

# --------------------------------------------------------------------
echo "Test 1 · ScopeIndicator CLEAR strips ALL narrowing; back restores"
# ScopeIndicator is used on every player-discipline page (batting /
# bowling / fielding / players). Exercise it on /batting as a
# representative — the rule is cross-page, the widget is shared.
reset
agent-browser open "$BASE/batting?player=ba607b88&gender=male&filter_team=India&filter_opponent=Australia&team_type=international&tournament=T20+World+Cup+%28Men%29" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
CLEAR_REF=$(ref_for 'button "Clear scope')
click_ref "$CLEAR_REF"
for p in filter_team filter_opponent tournament team_type season_from season_to; do
  agent-browser get url 2>/dev/null | grep -q "$p=" && {
    echo "  ✗ $p should have been cleared"; FAIL=$((FAIL + 1))
  } || {
    echo "  ✓ $p cleared"; PASS=$((PASS + 1))
  }
done
assert_url_contains "player=ba607b88"
assert_url_contains "gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_contains "filter_team=India"
assert_url_contains "filter_opponent=Australia"
assert_url_contains "tournament=T20+World+Cup"
assert_url_contains "team_type=international"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · PlayerLink (series dossier tile → player page) pushes + carries scope"
# PlayerLink is a cross-tab widget: click a player name on a Series
# dossier, land on their discipline page with tournament preserved.
# The target route varies by discipline; we test the batting flavour.
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
