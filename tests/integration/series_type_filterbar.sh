#!/bin/bash
# series_type FilterBar — widget rendering + URL state plumbing.
#
# Companion to test_series_type_baseline_numbers.py (which pins the
# backend SQL output). This script verifies the UI surface:
#   - <select> renders on every tab (no team_type gate, unlike v3).
#   - Changing the select writes the URL param.
#   - Status strip renders the chip from filters.series_type.
#   - 'reset all' clears the param.
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

SELECTOR="Array.from(document.querySelectorAll('.wisden-filter-group')).find(g => g.querySelector('.wisden-filter-label')?.innerText?.trim() === 'Show')?.querySelector('select')"

# ────────────────────────────────────────────
echo "Test 1 · Show select renders on /teams + /series + /batting"
for path in '/teams?gender=male&team_type=international' '/series?gender=male&team_type=international' '/batting?gender=male&team_type=international'; do
  ab open "$BASE$path"
  settle
  v=$(ab_eval "($SELECTOR) ? 'visible' : 'hidden'")
  assert_eq "select visible on $path" '"visible"' "$v"
done

# ────────────────────────────────────────────
echo "Test 2 · Select reflects URL state on initial load"
ab open "$BASE/teams?gender=male&team_type=international&series_type=bilateral_only"
settle
v=$(ab_eval "($SELECTOR)?.value")
assert_eq "value=bilateral_only on URL load" '"bilateral_only"' "$v"

# ────────────────────────────────────────────
echo "Test 3 · Change writes URL param"
ab open "$BASE/teams?gender=male&team_type=international"
settle
ab_eval "const s = $SELECTOR; s.value='tournament_only'; s.dispatchEvent(new Event('change', {bubbles: true}))" >/dev/null
sleep 0.6
v=$(ab_eval "new URL(location.href).searchParams.get('series_type')")
assert_eq "change adds series_type=tournament_only" '"tournament_only"' "$v"
# 'change to empty' is exercised by Test 5 (reset all) — dispatching
# a change event with value='' on the same DOM-instance can race the
# React re-render and produce a stale read here.

# ────────────────────────────────────────────
echo "Test 4 · Status strip shows the Series chip"
ab open "$BASE/teams?gender=male&team_type=international&series_type=bilateral_only"
settle
strip=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s => s.textContent).join(' | ')")
assert_contains "strip shows Series chip" "Series" "$strip"
assert_contains "strip shows bilateral T20Is" "bilateral" "$strip"

ab open "$BASE/teams?gender=male&team_type=international&series_type=tournament_only"
settle
strip=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s => s.textContent).join(' | ')")
assert_contains "tournament_only renders as 'ICC events'" "ICC events" "$strip"

# ────────────────────────────────────────────
echo "Test 5 · 'reset all' clears series_type"
ab open "$BASE/teams?gender=male&team_type=international&series_type=bilateral_only"
settle
ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'reset all')?.click()" >/dev/null
sleep 0.6
qs=$(ab_eval "location.search")
case "$qs" in
  *series_type=*) bad "reset all left series_type — qs=$qs" ;;
  *) ok "reset all cleared series_type" ;;
esac

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
