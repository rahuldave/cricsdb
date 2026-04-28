#!/bin/bash
# v3 team_class FilterBar — widget rendering + URL state plumbing.
#
# Prereqs: agent-browser, vite :5173, uvicorn :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab() { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }

settle() { sleep "${1:-1.5}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  if [ "$3" = "$2" ]; then ok "$1"; else bad "$1 — expected $2, got $3"; fi
}

assert_contains() {
  case "$3" in *"$2"*) ok "$1" ;; *) bad "$1 — '$2' not in: $3" ;; esac
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ────────────────────────────────────────────
echo "Test 1 · Pill visibility (intl visible / club hidden / All hidden)"
ab open "$BASE/teams?gender=male&team_type=international&season_from=2024&season_to=2025"
settle
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "pill visible on intl" '"visible"' "$v"

ab open "$BASE/teams?gender=male&team_type=club"
settle
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "pill hidden on club" '"hidden"' "$v"

ab open "$BASE/teams?gender=male"
settle
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "pill hidden on type=All" '"hidden"' "$v"

# ────────────────────────────────────────────
echo "Test 2 · Toggle writes/removes URL param + is-active class"
ab open "$BASE/teams?gender=male&team_type=international&season_from=2024&season_to=2025"
settle
ab_eval "document.querySelector('button[title*=\"ICC full-member\"]').click()" >/dev/null
sleep 0.6
v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "click ON adds team_class=full_member" '"full_member"' "$v"

v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]').classList.contains('is-active')")
assert_eq "pill class is-active" 'true' "$v"

ab_eval "document.querySelector('button[title*=\"ICC full-member\"]').click()" >/dev/null
sleep 0.6
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "click OFF removes team_class" '""' "$v"

# ────────────────────────────────────────────
echo "Test 3 · Status strip chip"
ab open "$BASE/teams?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member"
settle
strip=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s => s.textContent).join(' | ')")
assert_contains "status strip shows full members chip" "full members" "$strip"

# ────────────────────────────────────────────
echo "Test 4 · 'reset all' clears team_class"
ab open "$BASE/teams?gender=male&team_type=international&team_class=full_member"
settle
ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'reset all')?.click()" >/dev/null
sleep 0.6
qs=$(ab_eval "location.search")
case "$qs" in
  *team_class=*) bad "reset all left team_class — qs=$qs" ;;
  *) ok "reset all cleared team_class" ;;
esac

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
