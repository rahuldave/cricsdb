#!/bin/bash
# v3 team_class FilterBar — defensive intl gating.
#
# Asserts:
#   - Switching team_type to club via segmented control auto-clears
#     team_class (replace mode, no history pollution).
#   - Switching team_type to '' (All) auto-clears.
#   - Deep link with team_class + team_type=club self-corrects on mount.
#   - Pill disappears immediately after Type change.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab() { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }

settle() { sleep "${1:-1.5}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ────────────────────────────────────────────
echo "Test 1 · Type→Club auto-clears team_class"
ab open "$BASE/teams?gender=male&team_type=international&team_class=full_member&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'Club').click()" >/dev/null
sleep 0.7
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
[ "$v" = '""' ] && ok "Type→Club removed team_class" || bad "team_class should be empty after Type→Club, got: $v"

tt=$(ab_eval "new URL(location.href).searchParams.get('team_type')")
[ "$tt" = '"club"' ] && ok "Type→Club kept team_type=club" || bad "team_type should be club, got: $tt"

# ────────────────────────────────────────────
echo "Test 2 · Type→All auto-clears team_class"
ab open "$BASE/teams?gender=male&team_type=international&team_class=full_member&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b => b.textContent.trim() === 'All')[1]?.click()" >/dev/null
sleep 0.7
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
[ "$v" = '""' ] && ok "Type→All removed team_class" || bad "team_class should be empty after Type→All, got: $v"

# ────────────────────────────────────────────
echo "Test 3 · Deep link club+team_class self-corrects"
ab open "$BASE/teams?gender=male&team_type=club&team_class=full_member&tournament=Indian%20Premier%20League&season_from=2025&season_to=2025"
settle
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
[ "$v" = '""' ] && ok "club deep link stripped team_class" || bad "club deep link kept team_class, got: $v"

# ────────────────────────────────────────────
echo "Test 4 · Pill auto-disappears after Type change (no stale render)"
ab open "$BASE/teams?gender=male&team_type=international&team_class=full_member"
settle
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
[ "$v" = '"visible"' ] && ok "pill visible pre-switch" || bad "pill should be visible pre-switch, got: $v"

ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'Club').click()" >/dev/null
sleep 0.7
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
[ "$v" = '"hidden"' ] && ok "pill hidden post-switch" || bad "pill should be hidden post-switch, got: $v"

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
