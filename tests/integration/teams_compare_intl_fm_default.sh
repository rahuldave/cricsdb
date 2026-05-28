#!/bin/bash
# v3 Compare tab — Anchor E1 (FilterBar fm narrows all 3 columns via
# inheritance, no per-slot override needed).
#
# Asserts the URL E1 anchor: Aus 16 / FM avg 140 / India 31.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab() { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }

settle() { sleep "${1:-2.5}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Anchor E1 — Aus + __avg__ + India + FilterBar team_class=fm"
ab open "$BASE/teams?team=Australia&compare1=__avg__&compare2=India&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member&tab=Compare"
settle 3

result=$(ab_eval "(() => Array.from(document.querySelectorAll('.wisden-compare-col')).map(c => ({name: c.querySelector('.wisden-compare-col-name')?.textContent.trim(), matches: c.querySelector('.num')?.textContent.trim()})))()")

# Extract values from the JSON output
aus=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if c['name']=='Australia'][0]['matches'])")
avg=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if 'Full-member' in c['name']][0]['matches'])")
ind=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if c['name']=='India'][0]['matches'])")

[ "$aus" = "16" ] && ok "Australia col: 16 matches" || bad "Australia col expected 16, got $aus"
# Avg col shows per-team-avg matches, not raw pool total — anchor
# against the API. (Same rationale as compare_filters Anchor 5.)
api_avg=$(curl -s "${BASE/5173/8000}/api/v1/scope/averages/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('matches'))")
[ "$avg" = "$api_avg" ] && ok "Full-member avg col: $api_avg per-team-avg matches" || bad "FM avg col expected $api_avg (per-team avg from API), got $avg"
[ "$ind" = "31" ] && ok "India col: 31 matches" || bad "India col expected 31, got $ind"

# Avg col label should be "Full-member average"
label=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c['name'] for c in d if 'verage' in c['name']][0])")
case "$label" in
  *"Full-member"*) ok "avg col label: Full-member average" ;;
  *) bad "avg col label expected 'Full-member average', got: $label" ;;
esac

# FilterBar pill should be active
pill=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]')?.classList.contains('is-active')")
[ "$pill" = 'true' ] && ok "FilterBar pill is-active" || bad "pill not active, got: $pill"

# Status strip should mirror
strip=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s=>s.textContent).join(' | ')")
case "$strip" in
  *"full members"*) ok "status strip mirrors team_class chip" ;;
  *) bad "status strip missing full members chip — got: $strip" ;;
esac

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
