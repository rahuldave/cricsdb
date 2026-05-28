#!/bin/bash
# series_type FilterBar — cross-tab persistence.
#
# series_type ridges through every tab via FILTER_KEYS — assert it
# survives navigation across the 9 tabs AND the status strip surfaces
# it on each.
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

SELECTOR="Array.from(document.querySelectorAll('.wisden-filter-group')).find(g => g.querySelector('.wisden-filter-label')?.innerText?.trim() === 'Series Type')?.querySelector('select')"

assert_tab_carries_bilat() {
  local path="$1"
  ab open "$BASE${path}?gender=male&team_type=international&season_from=2024&season_to=2025&series_type=bilateral_only"
  settle
  v=$(ab_eval "new URL(location.href).searchParams.get('series_type')")
  [ "$v" = '"bilateral_only"' ] && ok "$path keeps series_type on load" || bad "$path lost series_type on load, got: $v"

  v=$(ab_eval "($SELECTOR)?.value")
  [ "$v" = '"bilateral_only"' ] && ok "$path select reflects series_type" || bad "$path select wrong value, got: $v"

  v=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s=>s.textContent).join(' | ')")
  case "$v" in
    *"Series"*) ok "$path status strip surfaces Series chip" ;;
    *) bad "$path status strip missing chip — got: $v" ;;
  esac
}

echo "Test · series_type is honoured across every tab"
assert_tab_carries_bilat "/teams"
assert_tab_carries_bilat "/batting"
assert_tab_carries_bilat "/bowling"
assert_tab_carries_bilat "/fielding"
assert_tab_carries_bilat "/matches"
assert_tab_carries_bilat "/series"
assert_tab_carries_bilat "/players"
assert_tab_carries_bilat "/venues"
assert_tab_carries_bilat "/head-to-head"

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
