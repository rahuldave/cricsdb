#!/bin/bash
# Series → Bowling tile row + chart strip from spec-series-trend-charts.md step 8.
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
tile_value() {
  local label="$1"
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')?.querySelector('.wisden-stat-value')?.firstChild?.textContent?.trim() || ''"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Test 1 · Series/Bowling at IPL all-time — tile row"
api_econ=$(curl -sf "$API/api/v1/scope/averages/bowling/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; print(f\"{json.load(sys.stdin)['economy']:.2f}\")")
sd_econ=$(curl -sf "$API/api/v1/scope/averages/bowling/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['by_season']
vals = [r['economy'] for r in rows if r.get('economy') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Bowling"
sleep 5
assert_eq "Series/Bowling · Economy value" "$api_econ" "$(tile_value 'Economy')"
assert_eq "Series/Bowling · Economy σ" "$sd_econ" "$(std_dom 'Economy')"

api_bc=$(curl -sf "$API/api/v1/scope/averages/bowling/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; print(f\"{json.load(sys.stdin)['boundaries_conceded']:.1f}\")")
assert_eq "Series/Bowling · Boundaries conceded value" "$api_bc" "$(tile_value 'Boundaries conceded')"

# Boundaries conceded is volume; σ absent.
bc_std=$(std_dom 'Boundaries conceded')
if [ -z "$(unq "$bc_std")" ]; then ok "Series/Bowling · Boundaries conceded σ absent (correct)"
else bad "Series/Bowling · Boundaries conceded σ should be absent, got '$(unq "$bc_std")'"; fi

charts=$(ab_eval "document.querySelectorAll('.wisden-chart-title').length")
if [ "$(unq "$charts")" -ge 5 ]; then
  ok "Series/Bowling · ≥5 charts rendered (got $(unq "$charts"))"
else
  bad "Series/Bowling · expected ≥5 charts, got $(unq "$charts")"
fi

echo "Test 2 · Series/Bowling at IPL 2024 (single season) — σ hides"
ab open "$BASE/series?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&tab=Bowling"
sleep 5
for label in 'Economy' 'Average' 'Strike rate' 'Dot %'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "Series/Bowling 2024 · $label σ hidden"
  else bad "Series/Bowling 2024 · $label σ should be hidden, got '$(unq "$got")'"; fi
done

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
