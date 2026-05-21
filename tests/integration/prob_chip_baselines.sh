#!/bin/bash
# Prob-chip cohort baseline captions — DOM integration test.
#
# Spec: internal_docs/spec-prob-baselines.md PT5.T.
#
# For each of the three Distribution panel surfaces (batting / bowling /
# fielding), asserts:
#   1. Every directional chip renders an Option C caption below the pill.
#   2. Caption form is "vs XX% ↑+YY%" matching the API-side scope_avg
#      and delta_pct exactly.
#   3. Direction polarity matches API color (oxblood = bad, green = good).
#   4. Descriptive chips (fielding P(=1), direction=null) DO NOT render
#      a caption.
#   5. Mobile viewport (390×844) leaves no horizontal overflow.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL" /
# "anchor against /summary's scope_avg, not re-derived SQL" — caption
# numbers are pulled from the /api/v1/.../distribution endpoint at test
# runtime, not hardcoded.
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

# Stable closed-scope subjects — Kohli IPL all-time + Bumrah IPL all-
# time anchor against shipped data; numbers don't drift unless cricket.db
# is rebuilt. The Distribution panels return cohort fields uniformly
# across all 4 form windows + lifetime, so testing lifetime is enough.
KOHLI=ba607b88
BUMRAH=462411b3
IPL_SCOPE='gender=male&team_type=club&tournament=Indian%20Premier%20League'

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
ab set viewport 1280 800

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Batting (Kohli IPL) — 6 directional chips, 6 captions"

ab open "$BASE/batting?player=$KOHLI&$IPL_SCOPE"
settle 4

cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "6 batting chips render captions" "6" "$cap_count"

# Anchor against the API — pull scope_avg + delta_pct for P(≥50) from
# the API and check the DOM caption matches.
api_p50_sa=$(curl -s "$API/api/v1/batters/$KOHLI/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys,math
d = json.load(sys.stdin)
pr = d['lifetime']['milestones']['p_50_plus']
# Cohort scope_avg formatted with the same fmtPctSmart rule used by
# ProbChip: < 5% to 1 dp, >= 5% to 0 dp.
v = pr['scope_avg'] * 100
print(f'{v:.1f}%' if v < 5 else f'{v:.0f}%')
")
api_p50_dp=$(curl -s "$API/api/v1/batters/$KOHLI/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
dp = d['lifetime']['milestones']['p_50_plus']['delta_pct']
# Match fmtDelta: signed, 0 dp, '+'/'−' (Unicode minus sign).
mag = f'{abs(dp):.0f}'
print(f'+{mag}%' if dp > 0 else (f'−{mag}%' if dp < 0 else '0%'))
")

dom_captions=$(ab_eval "Array.from(document.querySelectorAll('.prob-chip-caption')).map(e => e.textContent).join('||')")
assert_contains "P(≥50) caption shows API scope_avg" "vs $api_p50_sa" "$dom_captions"
assert_contains "P(≥50) caption shows API delta_pct" "$api_p50_dp" "$dom_captions"

# Polarity: Kohli's P(≥50) is +Δ on a higher_better chip → green.
p50_color=$(ab_eval "Array.from(document.querySelectorAll('.prob-chip-caption')).filter(e => e.textContent.includes('+'))[0]; getComputedStyle(Array.from(document.querySelectorAll('.prob-chip-caption')).find(e => e.textContent.includes('+')) || document.body).color")
assert_contains "Above-cohort caption is forest-green" "63, 122, 77" "$p50_color"

# ─────────────────────────────────────────────────────────────────
echo "Test 2 · Bowling (Bumrah IPL) — chips render across 3 tab views"

ab open "$BASE/bowling?player=$BUMRAH&$IPL_SCOPE"
settle 4

# Wickets tab is default. 9 chips: P(0)/P(≥1..5) + P(≥3..5│≥2).
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "9 wickets-tab chips render captions" "9" "$cap_count"

# Bumrah's P(0) is +Δ on a lower_better chip → oxblood (bad).
p0_color=$(ab_eval "const cap = Array.from(document.querySelectorAll('.prob-chip-caption')).find(e => /vs \d+% ↑\+\d+%/.test(e.textContent)); cap ? getComputedStyle(cap).color : 'none'")
assert_contains "P(0) caption with +Δ on lower_better is oxblood" "122, 31, 31" "$p0_color"

# Click the Economy tab and verify 4 econ chips render captions.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Economy').click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "4 economy-tab chips render captions" "4" "$cap_count"

# Click the Runs conceded tab and verify 4 chips.
ab eval "Array.from(document.querySelectorAll('.wisden-seg')).find(b => b.textContent.trim() === 'Runs conceded').click()"
settle 2
cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "4 runs-conceded-tab chips render captions" "4" "$cap_count"

# ─────────────────────────────────────────────────────────────────
echo "Test 3 · Fielding (Kohli IPL) — P(=1) suppressed, 2 captions on the catches block"

ab open "$BASE/fielding?player=$KOHLI&$IPL_SCOPE"
settle 4

cap_count=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
# Catches block: P(=0) lower_better, P(=1) null (suppressed),
# P(≥2) higher_better → 2 captions.
assert_eq "2 fielding catch chips render captions (P(=1) suppressed)" "2" "$cap_count"

# Anchor against API.
api_pzero_sa=$(curl -s "$API/api/v1/fielders/$KOHLI/distribution?$IPL_SCOPE" \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
pr = d['lifetime']['catches']['milestones']['p_zero']
v = pr['scope_avg'] * 100
print(f'{v:.1f}%' if v < 5 else f'{v:.0f}%')
")
dom_captions=$(ab_eval "Array.from(document.querySelectorAll('.prob-chip-caption')).map(e => e.textContent).join('||')")
assert_contains "Fielding P(=0) caption matches API scope_avg" "vs $api_pzero_sa" "$dom_captions"

# ─────────────────────────────────────────────────────────────────
echo "Test 4 · Mobile viewport 390×844 — no horizontal overflow"

ab set viewport 390 844
ab open "$BASE/bowling?player=$BUMRAH&$IPL_SCOPE"
settle 4

overflow=$(ab_eval "document.documentElement.scrollWidth - 390")
assert_eq "No mobile overflow on bowling page" "0" "$overflow"

# Captions still render on mobile (default Wickets tab = 9 chips).
cap_count_mobile=$(ab_eval "document.querySelectorAll('.prob-chip-caption').length")
assert_eq "Captions still render on mobile (Wickets tab = 9 chips)" "9" "$cap_count_mobile"

ab set viewport 1280 800
ab close --all >/dev/null 2>&1 || true

echo
echo "RESULT: $PASS pass, $FAIL fail"
if [ "$FAIL" -ne 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
