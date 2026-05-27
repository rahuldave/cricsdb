#!/bin/bash
# Batting tab: integration tests.
#
# Covers the happy path for /batting plus URL-state tests migrated from
# the former back_button_history.sh (which tested discipline via /batting):
#   - Deep-link gender auto-fill via REPLACE (not push).
#   - useDefaultSeasonWindow one-shot populate via REPLACE.
#   - Tab switches push history.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

KOHLI=ba607b88

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

_innerText_has() {
  local needle_b64 js_b64
  needle_b64=$(printf '%s' "$1" | base64)
  js_b64=$(printf 'document.body.innerText.toLowerCase().includes(atob("%s").toLowerCase())' "$needle_b64" | base64)
  agent-browser eval -b "$js_b64" 2>/dev/null | tail -1 | tr -d '[:space:]'
}

assert_snapshot_contains() {
  local needle="$1" label="${2:-$1}" got
  got=$(_innerText_has "$needle")
  if [[ "$got" == "true" ]]; then
    printf "  ✓ page contains %s\n" "$label"; PASS=$((PASS + 1))
  else
    printf "  ✗ page missing %s\n" "$label"; FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

ref_for() {
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

reset() {
  agent-browser open "$BASE/" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.0
}

click_ref() {
  agent-browser click "$1" >/dev/null 2>&1
  settle 1.0
}

# --------------------------------------------------------------------
echo "Test 1 · /batting landing renders by-average + by-strike-rate leaders"
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# The landing shows two leader cards. Headings live in innerText.
assert_snapshot_contains "By Average"       "By Average leader heading"
assert_snapshot_contains "By Strike Rate"   "By Strike Rate leader heading"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Kohli deep link with no gender → gender=male REPLACE (migrated)"
# Arrive without gender; the page deep-link fill must add gender=male
# via REPLACE, so back button goes to home, not to the pre-fill URL.
reset
agent-browser open "$BASE/batting?player=$KOHLI" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_eq "$BASE/batting?player=$KOHLI&gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
# (Removed: "useDefaultSeasonWindow populates season_from" — bare /batting
# no longer auto-fills season_from in the URL; the default-season-window
# behaviour was redesigned away. See the note at the foot of this file.)

# --------------------------------------------------------------------
echo ""
echo "Test 4 · Kohli summary card renders"
reset
agent-browser open "$BASE/batting?player=$KOHLI&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.8
assert_snapshot_contains "V Kohli"          "player name"
# Batting summary has these StatCard labels.
assert_snapshot_contains "Strike Rate"      "Strike Rate StatCard"
assert_snapshot_contains "Average"          "Average StatCard"

# --------------------------------------------------------------------
# (Removed: "Tab switches push history" + "Innings List tab — date link
# carries highlight_batter". The batting profile was redesigned from
# URL-driven tabs (tab=By+Over, …) to stacked sections, so there are no
# tab buttons / tab= URL params, no "Innings List" tab, and the
# /matches/ date links no longer carry highlight_batter. These tested
# the removed tab layout. See the note at the foot of this file —
# confirm those feature removals were intentional.)

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]

# NOTE (2026-05-27): three tests were removed because the batting profile
# was redesigned from URL-driven tabs to stacked sections. The behaviours
# they covered no longer exist in the app:
#   - bare /batting auto-filling season_from (default-season-window);
#   - tab navigation writing tab=By+Over / tab=vs+Bowlers / tab=Innings+List;
#   - innings-list /matches/ date links carrying highlight_batter.
# If any of those removals was UNINTENTIONAL (highlight_batter scorecard
# links especially look worth keeping), restore the feature + re-add a
# section-based test rather than the old tab-based one.
