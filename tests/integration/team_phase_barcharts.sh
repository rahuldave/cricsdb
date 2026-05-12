#!/bin/bash
# Team Phase BarCharts — DOM integration test.
#
# Covers two call sites in frontend/src/pages/Teams.tsx that pass
# MetricEnvelope-typed phase metrics to BarChart via the string
# valueAccessor path:
#
#   Teams.tsx:780  Batting "Run rate by phase"   valueAccessor="run_rate"
#   Teams.tsx:983  Bowling "Economy by phase"    valueAccessor="economy"
#
# Both fields are MetricEnvelope objects (types.ts:1600 + 1642). When
# BarChart.getValue's string-accessor branch reads them via
# `(d as Record<string, unknown>)[key]`, it sees an object, falls
# through to `return 0`, and the chart silently degenerates to
# maxValue=0 — Semiotic emits only a single "0" y-axis tick and
# renders no bars.
#
# Red-then-green: written ALONGSIDE the fix to BarChart.getValue
# (auto-unwrap MetricEnvelope). Snapshot before the fix:
#   Run rate by phase:  numeric_y_ticks = 1 ("0" only)
#   Economy by phase:   numeric_y_ticks = 1 ("0" only)
# After the fix:
#   Run rate by phase:  numeric_y_ticks ≥ 3 (e.g. "0", "2", "4", "6", "8", "10")
#   Economy by phase:   numeric_y_ticks ≥ 3 (similar scale)
#
# Regression history: commit 2d9e335 (Apr 25 2026, "by-phase + by-wicket:
# envelope migration + delta chips on phase / wicket rows") wrapped
# run_rate / economy in MetricEnvelope on backend + types but did NOT
# update the BarChart call sites. TypeScript missed it because the
# string-accessor path erases field types via Record<string, unknown>.
# Per CLAUDE.md "API ↔ frontend type contract" — type-API divergence
# turns a missing field into a silent fall-through.
#
# Why y-axis ticks instead of bar count: Semiotic v3 renders BarChart
# bars to a CANVAS element, so we can't enumerate SVG <rect>s. The
# Y-axis tick text lives in the axis SVG and faithfully reflects
# maxValue: when maxValue=0, Semiotic emits only the zero tick.
set -u

BASE="${BASE:-http://localhost:5173}"
TEAM_URL="Chennai+Super+Kings"
SCOPE_URL='gender=male&team_type=club'

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Count numeric Y-axis tick text in the BarChart with the given title.
# Returns the count as a bare integer string.
count_y_ticks() {
  local chart_title="$1"
  ab_eval "(() => {
    const svgs = Array.from(document.querySelectorAll('svg'));
    const titleSvg = svgs.find(s => s.textContent && s.textContent.includes('${chart_title}'));
    if (!titleSvg) return 'NO-SVG';
    let wrapper = titleSvg.parentElement;
    while (wrapper && !(wrapper.tagName === 'DIV' && wrapper.classList && wrapper.classList.contains('w-full'))) {
      wrapper = wrapper.parentElement;
    }
    if (!wrapper) return 'NO-WRAPPER';
    const ticks = Array.from(wrapper.querySelectorAll('svg text'))
      .map(t => (t.textContent || '').trim())
      .filter(t => /^[0-9]+(\.[0-9]+)?$/.test(t));
    return String(ticks.length);
  })()"
}

assert_min() {
  local label="$1" minval="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" =~ ^[0-9]+$ ]] && [ "$au" -ge "$minval" ]; then
    ok "$label (=$au, min=$minval)"
  else
    bad "$label — expected ≥$minval, got '$au'"
  fi
}

echo "## team_phase_barcharts — Run rate / Economy by phase render non-empty"

echo ""
echo "### Test 1 — Batting tab 'Run rate by phase' (Teams.tsx:780)"
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Batting"
ab wait --load networkidle
sleep 2  # let Semiotic paint
n1=$(count_y_ticks "Run rate by phase")
# Working: y-ticks ~5+ (run rate scale 0..10+); Broken: just "0".
assert_min "Run rate by phase numeric y-ticks" 3 "$n1"

echo ""
echo "### Test 2 — Bowling tab 'Economy by phase' (Teams.tsx:983)"
ab open "$BASE/teams?team=$TEAM_URL&$SCOPE_URL&tab=Bowling"
ab wait --load networkidle
sleep 2
n2=$(count_y_ticks "Economy by phase")
assert_min "Economy by phase numeric y-ticks" 3 "$n2"

echo ""
echo "## Summary: $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
  printf 'Failures:%s\n' "$FAILS"
  exit 1
fi
exit 0
