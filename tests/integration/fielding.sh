#!/bin/bash
# Fielding tab: integration tests.
#
# Covers /fielding happy path — landing, Tier-1 fielder page, Tier-2
# keeper page (Keeping tab is conditional on innings_kept > 0), plus
# URL-state test migrated from back_button_history.sh:
#   - FilterBar auto-narrow when filter_team + filter_opponent collapse
#     to a single tournament (MI × CSK → IPL).
#
# Prereqs: agent-browser, vite :5173, fastapi :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

KOHLI=ba607b88
DHONI=4a8a2e3b
POLLARD=a757b0d8

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

click_ref() { agent-browser click "$1" >/dev/null 2>&1; settle 1.0; }

# --------------------------------------------------------------------
echo "Test 1 · /fielding landing renders dismissals + keeper leaders"
reset
agent-browser open "$BASE/fielding" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "Dismissals"           "Dismissals leader heading"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Kohli fielding page — Tier-1 fielder, NO Keeping tab"
agent-browser open "$BASE/fielding?player=$KOHLI&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_snapshot_contains "V Kohli"              "player name"
# Kohli's innings_kept = 0 so Keeping tab should NOT be present.
KEEPING_PRESENT=$(agent-browser eval '(() => {
  const btns = document.querySelectorAll("button");
  for (const b of btns) {
    if (b.textContent.trim().toUpperCase() === "KEEPING") return "yes";
  }
  return "no";
})()' 2>/dev/null | tr -d '"')
if [[ "$KEEPING_PRESENT" == "no" ]]; then
  echo "  ✓ Keeping tab absent for Kohli (non-keeper)"; PASS=$((PASS + 1))
else
  echo "  ✗ Keeping tab should be absent for Kohli"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 3 · Dhoni fielding page — Keeping tab present + renders"
agent-browser open "$BASE/fielding?player=$DHONI&gender=male&team_type=international" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.8
assert_snapshot_contains "MS Dhoni"             "player name"
KEEP_REF=$(ref_for 'button "KEEPING"')
if [ -n "$KEEP_REF" ]; then
  echo "  ✓ Keeping tab present for Dhoni"; PASS=$((PASS + 1))
  click_ref "$KEEP_REF"
  assert_url_contains "tab=Keeping"
  # Keeping-summary StatCards — stumpings is keeper-only.
  assert_snapshot_contains "Stumpings"          "Stumpings StatCard"
else
  echo "  ✗ Keeping tab missing for Dhoni"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 4 · FilterBar auto-narrow on filter_team + filter_opponent (migrated)"
# Club-team pair (MI × CSK) collapses tournament list to IPL — the
# FilterBar auto-sets tournament + team_type + gender in one REPLACE,
# so back goes to home.
reset
agent-browser open "$BASE/fielding?player=$POLLARD&filter_team=Mumbai+Indians&filter_opponent=Chennai+Super+Kings" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
assert_url_contains "tournament=Indian+Premier+League"
assert_url_contains "team_type=club"
assert_url_contains "gender=male"
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Innings List — date link carries highlight_fielder"
agent-browser open "$BASE/fielding?player=$KOHLI&gender=male&team_type=international&tab=Innings+List" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
HAS_HIGHLIGHT=$(agent-browser eval '(() => {
  const links = document.querySelectorAll("a.comp-link[href*=\"/matches/\"]");
  for (const a of links) {
    if (a.getAttribute("href").includes("highlight_fielder=ba607b88")) return "yes";
  }
  return "no";
})()' 2>/dev/null | tr -d '"')
if [[ "$HAS_HIGHLIGHT" == "yes" ]]; then
  echo "  ✓ innings-list date link carries highlight_fielder=$KOHLI"; PASS=$((PASS + 1))
else
  echo "  ✗ innings-list date link missing highlight_fielder"; FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
agent-browser close >/dev/null 2>&1 || true
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
