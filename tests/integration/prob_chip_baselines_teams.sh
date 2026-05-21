#!/bin/bash
# Prob-chip scope-avg baseline captions — DOM integration test for
# the team Distribution panels.
#
# Spec: internal_docs/spec-prob-baselines-teams.md TT4.F.
#
# For each of the three team Distribution panel surfaces (batting /
# bowling / fielding), asserts:
#   1. Every directional chip renders an Option C caption.
#   2. Caption text matches the API-side scope_avg + delta_pct.
#   3. The single "vs avg" row prefix renders once per chip row
#      (matching the per-page "vs cohort" prefix on player panels).
#   4. Descriptive chips (fielding 3-simple P(=1)) DO NOT render a
#      caption.
#   5. Mobile viewport 390×844 leaves no horizontal overflow.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL" —
# caption numbers anchor against the /api/v1/teams/.../distribution
# endpoint at test runtime, not hardcoded.
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not in: $au"; fi
}

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

# Stable subject scope — Mumbai Indians at IPL all-time. The shape
# is constant across closed-scope subjects; we anchor on whatever
# the API returns at test time.
TEAM="Mumbai%20Indians"
IPL_SCOPE='gender=male&team_type=club&tournament=Indian%20Premier%20League'

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Team Batting (Mumbai Indians IPL) — Runs tab + Run Rate tab"

ab open "$BASE/teams?team=Mumbai+Indians&$IPL_SCOPE&tab=Batting"
settle 4

cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "9 directional captions on Runs row" "9" "$cap_count"

prefix_count=$(ab_eval "Array.from(document.querySelectorAll('span')).filter(s => s.textContent === 'vs avg').length")
assert_eq "1 'vs avg' prefix on batting Runs row" "1" "$prefix_count"

# Anchor against API — P(≥150) scope_avg + delta_pct.
api_p150_sa=$(curl -s "$API/api/v1/teams/$TEAM/batting/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
pr = d['lifetime']['runs']['milestones']['p_geq_150']
v = pr['scope_avg'] * 100
print(f'{v:.1f}%' if v < 5 else f'{v:.0f}%')
")
api_p150_dp=$(curl -s "$API/api/v1/teams/$TEAM/batting/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
dp = d['lifetime']['runs']['milestones']['p_geq_150']['delta_pct']
mag = f'{abs(dp):.0f}'
print(f'+{mag}%' if dp > 0 else (f'−{mag}%' if dp < 0 else '0%'))
")
dom_captions=$(ab_eval "Array.from(document.querySelectorAll('.prob-chip-caption')).map(e => e.textContent).join('||')")
assert_contains "Batting P(≥150) caption shows API scope_avg" "$api_p150_sa" "$dom_captions"
assert_contains "Batting P(≥150) caption shows API delta_pct" "$api_p150_dp" "$dom_captions"

# Switch to Run Rate tab — 4 directional captions + 1 prefix.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Run Rate')?.click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "4 captions on Run Rate row" "4" "$cap_count"
prefix_count=$(ab_eval "Array.from(document.querySelectorAll('span')).filter(s => s.textContent === 'vs avg').length")
assert_eq "1 'vs avg' prefix on Run Rate row" "1" "$prefix_count"

# ─────────────────────────────────────────────────────────────────
echo "Test 2 · Team Bowling — Wickets / Runs Conceded / Economy tabs"

ab open "$BASE/teams?team=Mumbai+Indians&$IPL_SCOPE&tab=Bowling"
settle 4

# Default tab is Wickets (8 directional chips).
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "8 captions on Wickets row" "8" "$cap_count"
prefix_count=$(ab_eval "Array.from(document.querySelectorAll('span')).filter(s => s.textContent === 'vs avg').length")
assert_eq "1 'vs avg' prefix on Wickets row" "1" "$prefix_count"

# Anchor against API — wickets P(=10) scope_avg + delta.
api_p10_sa=$(curl -s "$API/api/v1/teams/$TEAM/bowling/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
pr = d['lifetime']['wickets']['milestones']['p_eq_10']
v = pr['scope_avg'] * 100
print(f'{v:.1f}%' if v < 5 else f'{v:.0f}%')
")
dom_captions=$(ab_eval "Array.from(document.querySelectorAll('.prob-chip-caption')).map(e => e.textContent).join('||')")
assert_contains "Wickets P(=10) caption shows API scope_avg" "$api_p10_sa" "$dom_captions"

# Runs Conceded tab — 9 directional chips.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Runs Conceded')?.click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "9 captions on Runs Conceded row" "9" "$cap_count"

# Economy tab — 4 directional chips.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Economy')?.click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "4 captions on Economy row" "4" "$cap_count"

# ─────────────────────────────────────────────────────────────────
echo "Test 3 · Team Fielding — P(=1) suppressed on 3-simple blocks"

ab open "$BASE/teams?team=Mumbai+Indians&$IPL_SCOPE&tab=Fielding"
settle 4

# Catches block (default): 4 directional chips → 4 captions.
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "4 captions on Catches row" "4" "$cap_count"
prefix_count=$(ab_eval "Array.from(document.querySelectorAll('span')).filter(s => s.textContent === 'vs avg').length")
assert_eq "1 'vs avg' prefix on Catches row" "1" "$prefix_count"

# Run-outs block: 3 chips, P(=1) is direction=null → 2 captions.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Run-outs')?.click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "2 captions on Run-outs row (P(=1) suppressed)" "2" "$cap_count"

# Stumpings block: same 3-simple shape.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Stumpings')?.click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "2 captions on Stumpings row (P(=1) suppressed)" "2" "$cap_count"

# ─────────────────────────────────────────────────────────────────
echo "Test 4 · Mobile viewport 390×844 — no horizontal overflow"

ab set viewport 390 844
ab open "$BASE/teams?team=Mumbai+Indians&$IPL_SCOPE&tab=Batting"
settle 4

overflow=$(ab_eval "document.documentElement.scrollWidth - 390")
assert_eq "No mobile overflow on Batting page" "0" "$overflow"
cap_count_mobile=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "Captions still render on mobile (Runs tab = 9)" "9" "$cap_count_mobile"

ab set viewport 1280 800
ab close --all >/dev/null 2>&1 || true

echo
echo "RESULT: $PASS pass, $FAIL fail"
if [ "$FAIL" -ne 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
