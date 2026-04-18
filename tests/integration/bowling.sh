#!/bin/bash
# Bowling tab: integration tests.
#
# Happy-path coverage for /bowling: landing renders, player page
# renders with bowling-specific StatCards, Wickets + vs Batters tabs
# work. Bowling uses runs_conceded + wickets naming — assertions
# reference the labels the page actually displays.
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

BUMRAH=462411b3

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

click_ref() { agent-browser click "$1" >/dev/null 2>&1; settle 1.0; }

# --------------------------------------------------------------------
echo "Test 1 · /bowling landing renders leader lists"
reset
agent-browser open "$BASE/bowling" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "By Strike Rate"   "SR leader heading"
assert_snapshot_contains "By Economy"       "Economy leader heading"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Bumrah page renders — bowling StatCards"
agent-browser open "$BASE/bowling?player=$BUMRAH&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.8
assert_snapshot_contains "JJ Bumrah"        "player name"
assert_snapshot_contains "Economy"          "Economy StatCard"
assert_snapshot_contains "Strike Rate"      "Strike Rate StatCard"
assert_snapshot_contains "Wickets"          "Wickets StatCard"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Wickets tab — tab switch pushes URL"
WICK_REF=$(ref_for 'button "WICKETS"')
click_ref "$WICK_REF"
assert_url_contains "tab=Wickets"
assert_snapshot_contains "JJ Bumrah"        "still on Bumrah page"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · vs Batters tab — tab URL + matchup rendering"
VSB_REF=$(ref_for 'button "VS BATTERS"')
click_ref "$VSB_REF"
assert_url_contains "tab=vs+Batters"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Innings List — date link carries highlight_bowler"
INN_REF=$(ref_for 'button "INNINGS LIST"')
click_ref "$INN_REF"
settle 1.5
assert_url_contains "tab=Innings+List"
HAS_HIGHLIGHT=$(agent-browser eval '(() => {
  const links = document.querySelectorAll("a.comp-link[href*=\"/matches/\"]");
  for (const a of links) {
    if (a.getAttribute("href").includes("highlight_bowler=462411b3")) return "yes";
  }
  return "no";
})()' 2>/dev/null | tr -d '"')
if [[ "$HAS_HIGHLIGHT" == "yes" ]]; then
  echo "  ✓ innings-list date link carries highlight_bowler=$BUMRAH"; PASS=$((PASS + 1))
else
  echo "  ✗ innings-list date link missing highlight_bowler"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
