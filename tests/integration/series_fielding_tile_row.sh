#!/bin/bash
# Series → Fielding tile row + chart strip from spec-series-trend-charts.md step 9.
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

echo "Test 1 · Series/Fielding at IPL all-time — tile row + chart strip"
api_cpm=$(curl -sf "$API/api/v1/scope/averages/fielding/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; print(f\"{json.load(sys.stdin)['catches_per_match']:.2f}\")")
sd_cpm=$(curl -sf "$API/api/v1/scope/averages/fielding/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['by_season']
vals = [r['catches_per_match'] for r in rows if r.get('catches_per_match') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Fielding"
sleep 5
assert_eq "Series/Fielding · Catches/match value" "$api_cpm" "$(tile_value 'Catches/match')"
assert_eq "Series/Fielding · Catches/match σ" "$sd_cpm" "$(std_dom 'Catches/match')"

# Total dismissals tile present (volume — no σ)
td=$(tile_value 'Total dismissals')
if [ -n "$(unq "$td")" ]; then ok "Series/Fielding · Total dismissals tile present (=$(unq "$td"))"
else bad "Series/Fielding · Total dismissals tile missing"; fi
td_std=$(std_dom 'Total dismissals')
if [ -z "$(unq "$td_std")" ]; then ok "Series/Fielding · Total dismissals σ absent (correct)"
else bad "Series/Fielding · Total dismissals σ should be absent"; fi

charts=$(ab_eval "document.querySelectorAll('.wisden-chart-title').length")
if [ "$(unq "$charts")" -ge 4 ]; then
  ok "Series/Fielding · ≥4 charts rendered (got $(unq "$charts"))"
else
  bad "Series/Fielding · expected ≥4 charts, got $(unq "$charts")"
fi

echo "Test 2 · Series/Fielding at IPL 2024 — σ hides"
ab open "$BASE/series?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&tab=Fielding"
sleep 5
for label in 'Catches/match' 'Stumpings/match' 'Run-outs/match'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "Series/Fielding 2024 · $label σ hidden"
  else bad "Series/Fielding 2024 · $label σ should be hidden, got '$(unq "$got")'"; fi
done

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
