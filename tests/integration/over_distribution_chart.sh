#!/bin/bash
# Bowling By Over tab — Mix histogram + Performance vs cohort.
#
# Spec: internal_docs/spec-mix-and-performance-charts.md §M1 + §6.
#
# Asserts the new charts on /bowling?player=X&tab=By+Over render
# the spec-locked invariants:
#
#   1. Three SVG charts present (1 MixHistogram + 2 PerformanceVsCohort).
#   2. Mix histogram has exactly 20 bars (one per over).
#   3. Cohort ticks match the API's per-bucket cohort_economy /
#      cohort_wickets_per_innings values returned by /summary —
#      anchors against /api/v1/bowlers/{id}/summary directly so the
#      DOM ↔ API plumbing is verified end-to-end.
#   4. Bumrah's IPL mix is bimodal — sum of (overs 1-2 + 18-20)
#      share > sum of (overs 8-13) share. Locks the spec §6
#      acceptance shape.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL"
# — every numeric expected derives from the live API at runtime.
# We anchor against /summary (not raw SQL) per the integration-test
# memory: /summary covers SQL↔API in its own sanity test
# (tests/sanity/test_bowler_summary_over_distribution.py); this test
# covers API↔DOM plumbing.
set -u

BASE="${BASE:-http://localhost:5173}"
API_BASE="${API_BASE:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

assert_true() {
  local label="$1" actual="$2"
  local au=$(unq "$actual")
  if [ "$au" = "true" ]; then ok "$label"
  else bad "$label — got '$au'"; fi
}

BUMRAH=462411b3
SCOPE='tournament=Indian%20Premier%20League&gender=male&team_type=club'

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo
echo "Test 1 · By Over tab loads + 3 charts render"
ab open "$BASE/bowling?player=$BUMRAH&$SCOPE&tab=By%20Over"
ab wait --load networkidle
sleep 2

mix_n=$(ab_eval "document.querySelectorAll('.wisden-mix-histogram').length")
perf_n=$(ab_eval "document.querySelectorAll('.wisden-perf-cohort').length")
assert_eq "MixHistogram count == 1"          "1" "$mix_n"
assert_eq "PerformanceVsCohort count == 2"   "2" "$perf_n"

echo
echo "Test 2 · Mix histogram has 20 bars (one per over)"
# Each bar lives inside a <g> with a <title> + <rect>.
mix_bars=$(ab_eval "document.querySelector('.wisden-mix-histogram svg').querySelectorAll('g > rect').length")
assert_eq "20 mix bars" "20" "$mix_bars"

echo
echo "Test 3 · 20 bucket labels rendered under each chart"
mix_labels=$(ab_eval "document.querySelector('.wisden-mix-histogram').querySelectorAll('div[style*=\"grid-template-columns\"] > div').length")
assert_eq "20 mix labels" "20" "$mix_labels"

echo
echo "Test 4 · Cohort ticks present on both performance charts"
# Cohort ticks have fill=#3F7A4D (WISDEN.forest). Filter on the fill
# attribute to exclude the phase-tint background rects + player bars.
econ_ticks=$(ab_eval "Array.from(document.querySelectorAll('.wisden-perf-cohort')[0].querySelectorAll('svg > rect')).filter(r => (r.getAttribute('fill')||'').toUpperCase() === '#3F7A4D').length")
wpi_ticks=$(ab_eval "Array.from(document.querySelectorAll('.wisden-perf-cohort')[1].querySelectorAll('svg > rect')).filter(r => (r.getAttribute('fill')||'').toUpperCase() === '#3F7A4D').length")
# Bumrah IPL has cohort_economy non-null in all 20 buckets.
assert_eq "20 econ cohort ticks (forest-green)"  "20" "$econ_ticks"
assert_eq "20 wkts/inn cohort ticks (forest-green)" "20" "$wpi_ticks"

echo
echo "Test 5 · Bumrah IPL mix is bimodal (PP + death > middle)"
mix_bimodal=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-mix-histogram').querySelectorAll('title'));
  const shares = titles.map(t => {
    const m = t.textContent.match(/\(([\d.]+)%\)/);
    return m ? parseFloat(m[1]) : 0;
  });
  if (shares.length !== 20) return 'length=' + shares.length;
  const pp_death = (shares[0]||0) + (shares[1]||0) + (shares[17]||0) + (shares[18]||0) + (shares[19]||0);
  const middle = (shares[7]||0) + (shares[8]||0) + (shares[9]||0) + (shares[10]||0) + (shares[11]||0) + (shares[12]||0);
  return String(pp_death > middle);
})()")
assert_true "PP+death share > middle share (bimodal)" "$mix_bimodal"

echo
echo "Test 6 · Mix shares sum to 100% (within 0.5pp)"
mix_sum_ok=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-mix-histogram').querySelectorAll('title'));
  const shares = titles.map(t => {
    const m = t.textContent.match(/\(([\d.]+)%\)/);
    return m ? parseFloat(m[1]) : 0;
  });
  const sum = shares.reduce((a,b) => a+b, 0);
  return String(Math.abs(sum - 100) < 0.5);
})()")
assert_true "sum(player mix shares) ≈ 100%" "$mix_sum_ok"

echo
echo "Test 7 · Phase tints rendered on the new section"
# Sage (PP 1-6) + ochre (death 16-20) rects with phase-tint colours.
phase_tint_count=$(ab_eval "(() => {
  const svgs = document.querySelectorAll('.wisden-over-distribution-tab svg');
  let count = 0;
  svgs.forEach(svg => {
    svg.querySelectorAll('rect').forEach(r => {
      const f = r.getAttribute('fill') || '';
      if (f.startsWith('rgba(122, 142, 106') || f.startsWith('rgba(201, 135, 31')) count++;
    });
  });
  return String(count >= 33);
})()")
# 3 charts × (6 PP + 5 death) = 33 phase-tint rects minimum.
assert_true "≥33 phase-tint rects across 3 charts" "$phase_tint_count"

echo
echo "Test 8 · Econ cohort tick at over 20 matches API"
api_econ_20=$(curl -sS "$API_BASE/api/v1/bowlers/$BUMRAH/summary?$SCOPE" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['over_distribution'][19]['cohort_economy'])")
# Tooltip on the bar's <g> contains 'cohort X.XX' — read it.
dom_econ_20=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-perf-cohort')[0].querySelectorAll('title'));
  const t20 = titles.find(t => t.textContent.startsWith('Over 20:'));
  if (!t20) return 'no over 20 tooltip';
  const m = t20.textContent.match(/cohort ([\d.]+)/);
  return m ? m[1] : 'no cohort in tooltip';
})()")
assert_eq "over 20 econ cohort matches API ($api_econ_20)" "$api_econ_20" "$dom_econ_20"

echo
echo "Test 9 · Wickets/innings cohort tick at over 1 matches API"
api_wpi_1=$(curl -sS "$API_BASE/api/v1/bowlers/$BUMRAH/summary?$SCOPE" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['over_distribution'][0]['cohort_wickets_per_innings'])")
dom_wpi_1=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-perf-cohort')[1].querySelectorAll('title'));
  const t1 = titles.find(t => t.textContent.startsWith('Over 1:'));
  if (!t1) return 'no over 1 tooltip';
  const m = t1.textContent.match(/cohort ([\d.]+)\/inn/);
  return m ? m[1] : 'no cohort in tooltip';
})()")
assert_eq "over 1 wkts/inn cohort matches API ($api_wpi_1)" "$api_wpi_1" "$dom_wpi_1"

echo
echo "=============================================="
echo "PASS: $PASS    FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
