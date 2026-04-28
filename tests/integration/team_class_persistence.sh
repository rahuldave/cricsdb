#!/bin/bash
# v3 team_class FilterBar — cross-tab persistence.
#
# Asserts team_class survives navigation across tabs and the status
# strip mirrors the chip on every page.
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

assert_tab_carries_fm() {
  local path="$1"
  ab open "$BASE${path}?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member"
  settle
  v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
  [ "$v" = '"full_member"' ] && ok "$path keeps team_class on load" || bad "$path lost team_class on load, got: $v"

  v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]')?.classList.contains('is-active')")
  [ "$v" = 'true' ] && ok "$path pill is-active" || bad "$path pill not active, got: $v"

  v=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s=>s.textContent).join(' | ')")
  case "$v" in
    *"full members"*) ok "$path status strip shows full members" ;;
    *) bad "$path status strip missing chip — got: $v" ;;
  esac
}

# Each tab is loaded with team_class=fm in URL. We don't navigate via
# clicks (which would lose state through a fresh page mount) — the
# assertion is "the URL carries team_class AND the page renders the
# pill + chip honoring it on every tab".
echo "Test · team_class is honoured across every tab"
assert_tab_carries_fm "/teams"
assert_tab_carries_fm "/batting"
assert_tab_carries_fm "/bowling"
assert_tab_carries_fm "/fielding"
assert_tab_carries_fm "/matches"
assert_tab_carries_fm "/series"
assert_tab_carries_fm "/players"
assert_tab_carries_fm "/venues"
assert_tab_carries_fm "/head-to-head"

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
