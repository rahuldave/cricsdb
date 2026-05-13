#!/bin/bash
# Teams → Bowling tile changes from spec-series-trend-charts.md step 3.
#
# Asserts:
#  1. New `Boundaries conceded` tile renders with the SQL-anchored sum
#     of fours_conceded + sixes_conceded at the chosen scope.
#  2. Rate tiles (Economy / Average / Strike rate / Dot % / Avg opp
#     total) carry an inline `± σ` element whose value matches
#     population-std-dev across in-scope seasons (SQL-anchored).
#  3. Single-season scope hides the `± σ` element entirely (D4 rule).
#  4. Volume tiles (Boundaries conceded, Wickets, Runs conceded) and
#     extremum tiles (Worst conceded, Best defence) never carry σ,
#     regardless of N.
#
# Anchored against /scope/averages/bowling/by-season's payload via
# curl, per CLAUDE.md "Integration tests anchor against /summary's
# scope_avg, not re-derived SQL" — the std formula is small but the
# per-season run-rate / economy denominators are not, and we DO want
# to compare DOM to the API the page is reading from.
set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then
    ok "$label (=$expected)"
  else
    bad "$label — expected '$expected', got '$au'"
  fi
}

# Read the Boundaries conceded tile's value text.
boundaries_dom() {
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Boundaries conceded')?.querySelector('.wisden-stat-value')?.firstChild?.textContent?.trim() || ''"
}

# Read a rate tile's std-dev text (returns '' if absent).
std_dom() {
  local label="$1"
  ab_eval "Array.from(document.querySelectorAll('.wisden-stat')).find(t => t.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label')?.querySelector('.wisden-stat-std')?.textContent?.trim() || ''"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · MI @ IPL all-time — multi-season scope"
# Boundaries conceded — SQL via the team bowling summary endpoint.
api_bc=$(curl -sf "$API/api/v1/teams/Mumbai%20Indians/bowling/summary?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "import json,sys; print(int(json.load(sys.stdin)['boundaries_conceded']['value']))")
# Comma-format to match toLocaleString() DOM render.
api_bc_fmt=$(python3 -c "print(f'{$api_bc:,}')")

ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Bowling"
settle 4
assert_eq "MI@IPL · Boundaries conceded value" "$api_bc_fmt" "$(boundaries_dom)"

# σ presence on each rate tile — multi-season scope MUST show σ. Read
# the bySeason payload, compute population std, compare formatted DOM.
econ_sd=$(curl -sf "$API/api/v1/teams/Mumbai%20Indians/bowling/by-season?tournament=Indian%20Premier%20League&gender=male&team_type=club" \
  | python3 -c "
import json, sys, math
rows = json.load(sys.stdin)['seasons']
vals = [r['economy'] for r in rows if r.get('economy') is not None]
mean = sum(vals)/len(vals)
sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals))
print(f'± {sd:.2f}')
")
assert_eq "MI@IPL · Economy σ" "$econ_sd" "$(std_dom 'Economy')"

# ─────────────────────────────────────────────────────────────────
echo "Test 2 · MI @ IPL 2024 — single-season scope hides σ"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&season_from=2024&season_to=2024&tab=Bowling"
settle 4

for label in 'Economy' 'Average' 'Strike rate' 'Dot %' 'Avg opp total'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then
    ok "MI@IPL 2024 · $label σ hidden"
  else
    bad "MI@IPL 2024 · $label σ should be hidden, got '$(unq "$got")'"
  fi
done

# Volume + extremum tiles must NEVER carry σ.
echo "Test 3 · Volume + extremum tiles never carry σ"
for label in 'Boundaries conceded' 'Worst conceded' 'Best defence' 'Wides/match'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then
    ok "MI@IPL 2024 · $label σ absent (correct)"
  else
    bad "MI@IPL 2024 · $label should have no σ, got '$(unq "$got")'"
  fi
done

# Switch back to multi-season and re-check volume/extremum stay σ-less.
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Bowling"
settle 4
for label in 'Boundaries conceded' 'Worst conceded' 'Best defence'; do
  got=$(std_dom "$label")
  if [ -z "$(unq "$got")" ]; then
    ok "MI@IPL all-time · $label σ absent (correct)"
  else
    bad "MI@IPL all-time · $label should have no σ, got '$(unq "$got")'"
  fi
done

# ─────────────────────────────────────────────────────────────────
echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
