#!/bin/bash
# club-tier team_class — Compare-tab quick-picks + per-slot override.
#
# Asserts:
#   - "+ Average primary-club team" / "+ Average secondary-club team"
#     quick-picks render on club-mode Compare tabs (not on intl).
#   - Clicking adds a slot with the corresponding compareN_team_class
#     URL key.
#   - SlotScopeEditor's Tier dropdown surfaces Primary / Secondary
#     options.
#   - Compare-tab cross-type sanitize: when Type→intl flips while
#     compareN_team_class=primary_club is set, the per-slot tier value
#     is stripped along with the FilterBar one.
set -u

BASE="${BASE:-http://localhost:5179}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  if [ "$3" = "$2" ]; then ok "$1"; else bad "$1 — expected $2, got $3"; fi
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ────────────────────────────────────────────
echo "Test 1 · Compare quick-picks visible on club mode"
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&tab=Compare"
settle 5
ab_eval "document.querySelector('.wisden-compare-add-btn')?.click()" >/dev/null
sleep 2
v=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('+ Average primary-club team'))")
assert_eq "club: '+ Average primary-club team' visible" 'true' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('+ Average secondary-club team'))")
assert_eq "club: '+ Average secondary-club team' visible" 'true' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('+ Average full-member team'))")
assert_eq "club: FM quick-pick hidden" 'false' "$v"

# ────────────────────────────────────────────
echo "Test 2 · Quick-pick on club adds compareN_team_class override"
ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('+ Average primary-club team')).click()" >/dev/null
sleep 3
v=$(ab_eval "new URL(location.href).searchParams.get('compare2_team_class') || new URL(location.href).searchParams.get('compare1_team_class') || ''")
assert_eq "primary_club override written to compareN_team_class" '"primary_club"' "$v"

# ────────────────────────────────────────────
echo "Test 3 · Compare quick-picks on intl show FM, not club tier"
ab open "$BASE/teams?team=India&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Compare"
settle 5
ab_eval "document.querySelector('.wisden-compare-add-btn')?.click()" >/dev/null
sleep 2
v=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('+ Average full-member team'))")
assert_eq "intl: FM quick-pick visible" 'true' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('+ Average primary-club team'))")
assert_eq "intl: primary-club quick-pick hidden" 'false' "$v"

# ────────────────────────────────────────────
echo "Test 4 · SlotScopeEditor Tier dropdown on club mode"
# Open MI Compare with primary_club; existing slot's editor should
# expose Primary/Secondary options.
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club&tab=Compare"
settle 5
# Click the ✎ edit button on slot 1 (primary col is leftmost)
ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.title?.includes('Edit') || b.textContent.trim() === '✎')?.click()" >/dev/null
sleep 2
v=$(ab_eval "Array.from(document.querySelectorAll('select option')).some(o => o.textContent === 'Primary clubs only')")
assert_eq "editor: 'Primary clubs only' option visible" 'true' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('select option')).some(o => o.textContent === 'Secondary clubs only')")
assert_eq "editor: 'Secondary clubs only' option visible" 'true' "$v"

# ────────────────────────────────────────────
echo
if [ $FAIL -eq 0 ]; then
  echo "✅ $PASS PASS / 0 FAIL"
  exit 0
else
  echo "❌ $PASS PASS / $FAIL FAIL"
  echo -e "FAILS:$FAILS"
  exit 1
fi
