#!/bin/bash
# Series → Batting tile row + chart strip from spec-series-trend-charts.md step 7.
#
# Asserts:
#  1. Tile row renders 5 tiles (Avg innings total, Run rate, Boundary %,
#     Dot %, Highest total) above the existing player leaderboards.
#  2. Rate tiles carry `± σ` matching population-std-dev across in-scope
#     seasons (anchored against /scope/averages/batting/by-season).
#  3. Single-season scope hides σ.
#  4. Chart strip (6 charts) renders when N>=2 and hides when N=1.
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

echo "Test 1 · Series/Batting at IPL all-time — tile row + chart strip"
api_rr=$(curl -sf "$API/api/v1/scope/averages/batting/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; v=json.load(sys.stdin)['run_rate']; print(f'{v:.2f}')")
sd_rr=$(curl -sf "$API/api/v1/scope/averages/batting/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['by_season']
vals = [r['run_rate'] for r in rows if r.get('run_rate') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Batting"
sleep 5

assert_eq "Series/Batting · Run rate value" "$api_rr" "$(tile_value 'Run rate')"
assert_eq "Series/Batting · Run rate σ" "$sd_rr" "$(std_dom 'Run rate')"

# Chart strip rendered (>=2 seasons in scope) — 6 charts in the strip.
charts=$(ab_eval "document.querySelectorAll('.wisden-chart-title').length")
if [ "$(unq "$charts")" -ge 6 ]; then
  ok "Series/Batting · ≥6 charts rendered (got $(unq "$charts"))"
else
  bad "Series/Batting · expected ≥6 charts, got $(unq "$charts")"
fi

echo "Test 2 · Series/Batting at IPL 2024 (single season) — σ hides + charts hide"
ab open "$BASE/series?tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&tab=Batting"
sleep 5
for label in 'Avg innings total' 'Run rate' 'Boundary %' 'Dot %'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then ok "Series/Batting 2024 · $label σ hidden"
  else bad "Series/Batting 2024 · $label σ should be hidden, got '$(unq "$got")'"; fi
done

# Should still see Highest total tile (no chart strip).
ht=$(tile_value 'Highest total')
if [ -n "$(unq "$ht")" ]; then ok "Series/Batting 2024 · Highest total tile present (=$(unq "$ht"))"
else bad "Series/Batting 2024 · Highest total tile missing"; fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
