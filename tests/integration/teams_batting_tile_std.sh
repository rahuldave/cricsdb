#!/bin/bash
# Teams → Batting tile σ wiring from spec-series-trend-charts.md step 5.
#
# No new tiles. Asserts:
#  1. Run rate / Boundary % / Dot % / Avg innings total carry `± σ`
#     matching population-std-dev across in-scope seasons.
#  2. Volume tiles (Runs, 4s, 6s, 50s, 100s) + extremum tiles
#     (Highest total, Lowest all-out) never carry σ.
#  3. Single-season scope hides σ entirely.
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

std_dom() {
  local label="$1"
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')?.querySelector('.wisden-stat-std')?.textContent?.trim() || ''"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Test 1 · MI @ IPL all-time — σ on rate tiles"
sd_rr=$(curl -sf "$API/api/v1/teams/Mumbai%20Indians/batting/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['seasons']
vals = [r['run_rate'] for r in rows if r.get('run_rate') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Batting"
sleep 4
assert_eq "MI@IPL · Run rate σ" "$sd_rr" "$(std_dom 'Run rate')"

echo "Test 2 · Volume + extremum tiles never carry σ"
for label in 'Runs' '4s' '6s' '50s' '100s' 'Highest total' 'Lowest all-out' 'Innings'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "MI@IPL · $label σ absent (correct)"
  else bad "MI@IPL · $label should have no σ, got '$(unq "$got")'"; fi
done

echo "Test 3 · MI @ IPL 2024 — single-season hides σ"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&season_from=2024&season_to=2024&tab=Batting"
sleep 4
for label in 'Run rate' 'Boundary %' 'Dot %' 'Avg innings total'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "MI@IPL 2024 · $label σ hidden"
  else bad "MI@IPL 2024 · $label σ should be hidden, got '$(unq "$got")'"; fi
done

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
