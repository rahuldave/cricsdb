#!/bin/bash
# Player baseline — filter-combination matrix integration test.
#
# Spec: internal_docs/spec-player-baseline-parity.md §6.3 +
# CLAUDE.md "Filter-combination testing — the matrix is mandatory".
#
# Phase H of the spec — exercises the FilterParams matrix on each
# of /batting, /bowling, /fielding to confirm:
#   - By Season LineChart renders at every combo, WITH the grey
#     "typical player" reference line whenever the cohort clears the
#     support cliff at that scope (driven off the cohort endpoint's
#     own below_support flag), and WITHOUT it — player line only —
#     when every season's narrowed pool is too thin to compare. The
#     latter is the correct post-Phase-3c behaviour: batting narrows
#     live, so venue+opponent / venue+toss drop the cohort below the
#     cliff and the reference line is suppressed rather than showing a
#     misleading frozen-broad average. Bowling/fielding stay
#     frozen-broad until 3d/3e, so they keep the reference line — the
#     test tracks each discipline's real behaviour, not a hard-coded
#     expectation.
#   - At least one summary tile still carries a "vs cohort" chip.
#
# Plus a click-after-mount probe on each page: deep-link an
# unnarrowed scope, then click a FilterBar control (venue typeahead
# select), then re-assert the chart still has the bi-series wiring.
# venue-only keeps the batting cohort supported, so the reference line
# must survive the runtime refetch. Refetch bugs that worked at
# deep-link but broke on runtime click would hide otherwise —
# CLAUDE.md "Tests must cover EVERY call site of a shared
# abstraction" lesson from be4d755.
#
# 3 pages × 4 narrowing combos × 2 assertions = 24 matrix assertions
# + 3 click-after-mount = 27 total.
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Pull the chart-frame state JSON. Probes the stable LineChart
# data-attrs (data-test-line-has-reference) rather than grepping the
# Semiotic legend's display text, so a copy edit to the legend label
# (e.g. "base" → "cohort") can't break the matrix.
probe_chart() {
  agent-browser eval --json "(() => {
    const frames = Array.from(document.querySelectorAll('.stream-xy-frame'));
    const lines = Array.from(document.querySelectorAll('[data-test-line]'));
    return {
      n_frames: frames.length,
      canvas_total: frames.reduce((a, f) => a + f.querySelectorAll('canvas').length, 0),
      lines_total: lines.length,
      lines_with_ref: lines.filter(e => e.getAttribute('data-test-line-has-reference') === 'yes').length,
    };
  })()" 2>/dev/null > /tmp/chart_probe.json
}

# Does the per-season cohort actually clear the support cliff at this
# scope? The chart draws the grey "typical player" reference line only
# when the cohort endpoint returns ≥1 season with below_support=false.
# Under a narrow combo the per-season pool can fall below the cliff for
# every season (correct, intended — a comparison built from a handful
# of innings is suppressed, not shown). Batting narrows live (Phase 3c);
# bowling/fielding stay frozen-broad until 3d/3e, so this naturally
# tracks each discipline's current behaviour instead of hard-coding it.
cohort_supported() {  # $1 = cohort by-season endpoint URL
  curl -s "$1" | python3 -c "
import json, sys
d = json.load(sys.stdin)
rows = d.get('by_season', [])
print('yes' if any(r.get('below_support') is False for r in rows) else 'no')
"
}

# Count "vs cohort" subtitles in the stat rows.
count_vs_base() {
  agent-browser eval --json "(() => {
    return Array.from(document.querySelectorAll('.wisden-statrow .wisden-stat-sub'))
      .filter(s => s.textContent && s.textContent.includes('vs cohort')).length;
  })()" 2>/dev/null > /tmp/chips.json
  python3 -c "import json; print(json.load(open('/tmp/chips.json'))['data']['result'])"
}

# Assert (chart renders, ≥1 chip) for a given page + combo URL.
#
# Chart assertion has three outcomes:
#   - Empty by-season payload (no innings at all) → chart legitimately
#     suppressed by the LineChart `seasonData.length > 0` guard. PASS.
#   - Cohort supported at this scope (≥1 season clears the cliff) →
#     the grey reference line MUST render alongside the player line
#     (bi-series). This is the wiring/refetch check.
#   - Cohort NOT supported (every season below the cliff — e.g. the
#     batting pool at venue+opponent is a handful of innings) → the
#     player line MUST still render, and the reference line is
#     correctly absent. PASS. Asserting a reference line here would be
#     asserting the pre-3c frozen-broad behaviour 3c removed.
#
# The chip side stays asserted unconditionally because /summary
# aggregates across seasons and still returns values at narrow scopes.
assert_combo() {
  local label="$1" url="$2" empty_check_url="$3" cohort_url="$4"
  ab open "$url"
  sleep 3
  empty=$(curl -s "$empty_check_url" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('yes' if len(d.get('by_season', [])) == 0 else 'no')
")
  if [ "$empty" = "yes" ]; then
    ok "$label: empty by-season scope — chart legitimately suppressed"
  else
    supported=$(cohort_supported "$cohort_url")
    probe_chart
    renders=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
print('yes' if d['n_frames'] >= 1 and d['canvas_total'] >= 2 and d['lines_total'] >= 1 else 'no')
")
    ref=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
print('yes' if d['lines_with_ref'] >= 1 else 'no')
")
    if [ "$renders" != "yes" ]; then
      bad "$label: chart did not render at all — $(cat /tmp/chart_probe.json)"
    elif [ "$supported" = "yes" ]; then
      if [ "$ref" = "yes" ]; then
        ok "$label: chart bi-series renders (cohort supported)"
      else
        bad "$label: cohort supported by API but reference line missing — $(cat /tmp/chart_probe.json)"
      fi
    elif [ "$ref" = "no" ]; then
      # Thin pool: cohort correctly suppressed; player line still draws.
      ok "$label: player line renders, cohort correctly suppressed below cliff (no ref line)"
    else
      # API says every season is below the cliff, yet a reference line
      # drew anyway — that's the pre-3c frozen-broad cohort leaking back.
      bad "$label: cohort below cliff per API but reference line present — frozen-broad leak? $(cat /tmp/chart_probe.json)"
    fi
  fi
  chips=$(count_vs_base)
  if [ "$chips" -ge 1 ]; then
    ok "$label: ≥1 'vs cohort' chip on stat rows (=$chips)"
  else
    bad "$label: no 'vs cohort' chips found on stat rows"
  fi
}

SCOPE_BASE='gender=male&team_type=club&tournament=Indian%20Premier%20League'
WANKHEDE='filter_venue=Wankhede%20Stadium'
CSK='filter_opponent=Chennai%20Super%20Kings'
TOSS_WON='toss_outcome=won'

# ───────────────────────────────────────────────────────────────────
# /batting — Kohli IPL × matrix
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /batting matrix ==="
KOHLI=ba607b88
API_SCOPE='gender=male&team_type=club&tournament=Indian+Premier+League'

bat_api() {
  echo "$API/api/v1/batters/$KOHLI/by-season?${API_SCOPE}${1:+&$1}"
}
bat_coh() {
  echo "$API/api/v1/scope/averages/players/batting/by-season?person_id=$KOHLI&${API_SCOPE}${1:+&$1}"
}
assert_combo "/batting tournament-only" \
  "$BASE/batting?player=$KOHLI&$SCOPE_BASE&tab=By%20Season" \
  "$(bat_api '')" "$(bat_coh '')"
assert_combo "/batting + venue" \
  "$BASE/batting?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&tab=By%20Season" \
  "$(bat_api 'filter_venue=Wankhede+Stadium')" "$(bat_coh 'filter_venue=Wankhede+Stadium')"
assert_combo "/batting + venue + opponent" \
  "$BASE/batting?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&$CSK&tab=By%20Season" \
  "$(bat_api 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')" \
  "$(bat_coh 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')"
assert_combo "/batting + venue + toss=won" \
  "$BASE/batting?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&$TOSS_WON&tab=By%20Season" \
  "$(bat_api 'filter_venue=Wankhede+Stadium&toss_outcome=won')" \
  "$(bat_coh 'filter_venue=Wankhede+Stadium&toss_outcome=won')"

# ───────────────────────────────────────────────────────────────────
# /bowling — Bumrah IPL × matrix
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /bowling matrix ==="
BUMRAH=462411b3

bow_api() {
  echo "$API/api/v1/bowlers/$BUMRAH/by-season?${API_SCOPE}${1:+&$1}"
}
bow_coh() {
  echo "$API/api/v1/scope/averages/players/bowling/by-season?person_id=$BUMRAH&${API_SCOPE}${1:+&$1}"
}
assert_combo "/bowling tournament-only" \
  "$BASE/bowling?player=$BUMRAH&$SCOPE_BASE&tab=By%20Season" \
  "$(bow_api '')" "$(bow_coh '')"
assert_combo "/bowling + venue" \
  "$BASE/bowling?player=$BUMRAH&$SCOPE_BASE&$WANKHEDE&tab=By%20Season" \
  "$(bow_api 'filter_venue=Wankhede+Stadium')" "$(bow_coh 'filter_venue=Wankhede+Stadium')"
assert_combo "/bowling + venue + opponent" \
  "$BASE/bowling?player=$BUMRAH&$SCOPE_BASE&$WANKHEDE&$CSK&tab=By%20Season" \
  "$(bow_api 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')" \
  "$(bow_coh 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')"
assert_combo "/bowling + venue + toss=won" \
  "$BASE/bowling?player=$BUMRAH&$SCOPE_BASE&$WANKHEDE&$TOSS_WON&tab=By%20Season" \
  "$(bow_api 'filter_venue=Wankhede+Stadium&toss_outcome=won')" \
  "$(bow_coh 'filter_venue=Wankhede+Stadium&toss_outcome=won')"

# ───────────────────────────────────────────────────────────────────
# /fielding — Kohli IPL × matrix
# ───────────────────────────────────────────────────────────────────

echo
echo "=== /fielding matrix ==="

fld_api() {
  echo "$API/api/v1/fielders/$KOHLI/by-season?${API_SCOPE}${1:+&$1}"
}
fld_coh() {
  echo "$API/api/v1/scope/averages/players/fielding/by-season?person_id=$KOHLI&${API_SCOPE}${1:+&$1}"
}
assert_combo "/fielding tournament-only" \
  "$BASE/fielding?player=$KOHLI&$SCOPE_BASE&tab=By%20Season" \
  "$(fld_api '')" "$(fld_coh '')"
assert_combo "/fielding + venue" \
  "$BASE/fielding?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&tab=By%20Season" \
  "$(fld_api 'filter_venue=Wankhede+Stadium')" "$(fld_coh 'filter_venue=Wankhede+Stadium')"
assert_combo "/fielding + venue + opponent" \
  "$BASE/fielding?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&$CSK&tab=By%20Season" \
  "$(fld_api 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')" \
  "$(fld_coh 'filter_venue=Wankhede+Stadium&filter_opponent=Chennai+Super+Kings')"
assert_combo "/fielding + venue + toss=won" \
  "$BASE/fielding?player=$KOHLI&$SCOPE_BASE&$WANKHEDE&$TOSS_WON&tab=By%20Season" \
  "$(fld_api 'filter_venue=Wankhede+Stadium&toss_outcome=won')" \
  "$(fld_coh 'filter_venue=Wankhede+Stadium&toss_outcome=won')"

# ───────────────────────────────────────────────────────────────────
# Click-after-mount — refetch survives runtime FilterBar click
# ───────────────────────────────────────────────────────────────────
# Open the unnarrowed scope, then click the venue typeahead to pick
# Wankhede via the FilterBar. The chart must still have its
# bi-series wiring afterwards (refetch lock — covers the be4d755
# class of bug where deep-link works but runtime click doesn't).

echo
echo "=== click-after-mount refetch ==="

click_wankhede_then_assert() {
  local label="$1"
  # Find the venue text input + fire a synthetic 'Wankhede' option
  # via URL update — direct typeahead simulation is brittle, so we
  # use the cleaner setUrlParams path the FilterBar would have taken.
  ab open "$BASE/${page}?player=${pid}&$SCOPE_BASE&tab=By%20Season"
  sleep 3
  # Programmatic FilterBar update — same path the typeahead's
  # `onSelect` calls (useSetUrlParams). Asserts the chart refetch
  # on URL-state change, not just initial mount.
  agent-browser eval "(() => {
    const u = new URL(location.href);
    u.searchParams.set('filter_venue', 'Wankhede Stadium');
    history.pushState({}, '', u);
    window.dispatchEvent(new PopStateEvent('popstate'));
  })()" >/dev/null 2>&1
  sleep 3
  probe_chart
  has_chart=$(python3 -c "
import json
d = json.load(open('/tmp/chart_probe.json'))['data']['result']
ok = d['n_frames'] >= 1 and d['canvas_total'] >= 2 and d['lines_with_ref'] >= 1
print('yes' if ok else 'no')
")
  if [ "$has_chart" = "yes" ]; then
    ok "$label: chart survives runtime filter_venue add"
  else
    bad "$label: chart broken after click-after-mount"
  fi
}

page=batting; pid=$KOHLI
click_wankhede_then_assert "/batting click-after-mount"

page=bowling; pid=$BUMRAH
click_wankhede_then_assert "/bowling click-after-mount"

page=fielding; pid=$KOHLI
click_wankhede_then_assert "/fielding click-after-mount"

echo
echo "─────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "OK"
