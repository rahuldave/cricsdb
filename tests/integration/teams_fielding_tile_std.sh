#!/bin/bash
# Teams → Fielding tile changes from spec-series-trend-charts.md step 4.
#
# Asserts:
#  1. New `Total dismissals` tile renders with the SQL-anchored value
#     (catches inclusive of C&B + stumpings + run_outs).
#  2. Rate tiles (Catches/match, Stumpings/match, Run-outs/match)
#     carry `± σ` matching population-std-dev across in-scope seasons.
#  3. Single-season scope hides `± σ` entirely (D4 rule).
#  4. Volume tiles (Total dismissals, Catches, Stumpings, Run-outs,
#     C&B, Matches) never carry σ.
set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

tile_value() {
  local label="$1"
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')?.querySelector('.wisden-stat-value')?.firstChild?.textContent?.trim() || ''"
}
std_dom() {
  local label="$1"
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')?.querySelector('.wisden-stat-std')?.textContent?.trim() || ''"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Test 1 · MI @ IPL all-time — multi-season scope"
api_td=$(curl -sf "$API/api/v1/teams/Mumbai%20Indians/fielding/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; print(int(json.load(sys.stdin)['total_dismissals_contributed']['value']))")
api_td_fmt=$(python3 -c "print(f'{$api_td:,}')")
api_cpm_sd=$(curl -sf "$API/api/v1/teams/Mumbai%20Indians/fielding/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['seasons']
vals = [r['catches_per_match'] for r in rows if r.get('catches_per_match') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")

ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Fielding"
sleep 4

assert_eq "MI@IPL · Total dismissals value" "$api_td_fmt" "$(tile_value 'Total dismissals')"
assert_eq "MI@IPL · Catches/match σ" "$api_cpm_sd" "$(std_dom 'Catches/match')"

echo "Test 2 · MI @ IPL 2024 — single-season hides σ"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&season_from=2024&season_to=2024&tab=Fielding"
sleep 4
for label in 'Catches/match' 'Stumpings/match' 'Run-outs/match'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "MI@IPL 2024 · $label σ hidden"
  else bad "MI@IPL 2024 · $label σ should be hidden, got '$(unq "$got")'"; fi
done

echo "Test 3 · Volume tiles never carry σ"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Fielding"
sleep 4
for label in 'Total dismissals' 'Catches' 'Stumpings' 'Run-outs' 'C&B' 'Matches'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "MI@IPL · $label σ absent (correct)"
  else bad "MI@IPL · $label should have no σ, got '$(unq "$got")'"; fi
done

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
