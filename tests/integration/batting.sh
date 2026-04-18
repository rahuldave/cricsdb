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
echo ""
echo "Test 3 · useDefaultSeasonWindow populates season_from via REPLACE (migrated)"
# Bare /batting (no player) triggers the default-season-window hook:
# populates season_from + season_to pointing at the last 3 seasons.
# The one-shot effect must REPLACE so back goes to /, not to the
# pre-window URL.
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.8
assert_url_contains "season_from="
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

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
echo ""
echo "Test 5 · Tab switches push history (migrated)"
# Already on Kohli batting page. Click By Over, then vs Bowlers. Each
# click should push one history entry.
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
echo "Test 6 · Innings List tab — date link carries highlight_batter"
INN_REF=$(ref_for 'button "INNINGS LIST"')
click_ref "$INN_REF"
settle 1.5
assert_url_contains "tab=Innings+List"
# Every date cell is a Link to /matches/:id with highlight_batter=<kohli id>.
HAS_HIGHLIGHT=$(agent-browser eval '(() => {
  const links = document.querySelectorAll("a.comp-link[href*=\"/matches/\"]");
  for (const a of links) {
    if (a.getAttribute("href").includes("highlight_batter=ba607b88")) return "yes";
  }
  return "no";
})()' 2>/dev/null | tr -d '"')
if [[ "$HAS_HIGHLIGHT" == "yes" ]]; then
  echo "  ✓ innings-list date link carries highlight_batter=$KOHLI"; PASS=$((PASS + 1))
else
  echo "  ✗ innings-list date link missing highlight_batter"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
