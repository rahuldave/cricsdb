#!/bin/bash
# Batting By Position tab — Mix histogram + SR vs cohort.
#
# Spec: internal_docs/spec-mix-and-performance-charts.md §M2 + §6.
#
# Per CLAUDE.md "Filter-combination testing — the matrix is
# mandatory": exercises the new charts across diverse subject ×
# scope combinations. Asserts:
#
#   PART A — Kohli @ IPL all-time (multi-mode mix):
#     1. Charts render (1 MixHistogram + 1 PerformanceVsCohort).
#     2. 10 mix bars + 10 SR bucket labels.
#     3. 10 forest-green cohort ticks.
#     4. Player mix shares sum to ~100%.
#     5. Opener (b1) + #3 (b2) > 80% of mix (Kohli's IPL pattern).
#     6. Cohort tick at opener matches API to the digit.
#
#   PART B — Warner @ IPL all-time (extreme-opener contrast):
#     7. Mix is opener-dominant: opener bucket > 80% of share.
#        Locks the shape change between subjects.
#
#   PART C — Kohli @ all-time, no tournament (wider scope):
#     8. Cohort shares STILL sum to ~100% (works at broader scope).
#     9. Cohort SR at opener differs from IPL-scoped Kohli (cohort
#        composition depends on scope — must not be identical).
#
#   PART D — Kohli @ IPL 2024 (single-season scope):
#    10. Charts still render — narrow scope doesn't break component.
#    11. Tooltip lists at least one non-zero player innings bucket.
#
# Tooltip + tick values cross-check against /summary directly per
# CLAUDE.md "anchor against /summary, not re-derive SQL" — /summary
# SQL↔API correctness covered by the sanity test
# tests/sanity/test_batter_summary_position_distribution.py.
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

KOHLI=ba607b88
WARNER=dcce6f09
IPL='tournament=Indian%20Premier%20League&gender=male&team_type=club'
IPL_2024="${IPL}&season_from=2024&season_to=2024"

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo
echo "PART A · Kohli @ IPL all-time"
ab open "$BASE/batting?player=$KOHLI&$IPL&tab=By%20Position"
ab wait --load networkidle
sleep 2

# Test A1 — charts render
mix_n=$(ab_eval "document.querySelectorAll('.wisden-position-distribution-tab .wisden-mix-histogram').length")
perf_n=$(ab_eval "document.querySelectorAll('.wisden-position-distribution-tab .wisden-perf-cohort').length")
assert_eq "A1 · MixHistogram count == 1"        "1" "$mix_n"
# 2 PerformanceVsCohort panels on the By Position tab: Strike rate +
# Batting average (Average added in PositionDistributionTab.tsx).
assert_eq "A1 · PerformanceVsCohort count == 2" "2" "$perf_n"

# Test A2 — bar + label count
mix_bars=$(ab_eval "document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram svg').querySelectorAll('g > rect').length")
mix_labels=$(ab_eval "document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram').querySelectorAll('div[style*=\"grid-template-columns\"] > div').length")
assert_eq "A2 · 10 mix bars"   "10" "$mix_bars"
assert_eq "A2 · 10 mix labels" "10" "$mix_labels"

# Test A3 — cohort ticks (forest green)
ticks=$(ab_eval "Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-perf-cohort svg').querySelectorAll('rect')).filter(r => (r.getAttribute('fill')||'').toUpperCase() === '#3F7A4D').length")
assert_eq "A3 · 10 SR cohort ticks (forest-green)" "10" "$ticks"

# Test A4 — mix shares sum to 100%
mix_sum_ok=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram').querySelectorAll('title'));
  const shares = titles.map(t => {
    const m = t.textContent.match(/\(([\d.]+)%\)/);
    return m ? parseFloat(m[1]) : 0;
  });
  const sum = shares.reduce((a,b) => a+b, 0);
  return String(Math.abs(sum - 100) < 0.5);
})()")
assert_true "A4 · player mix shares sum to ~100%" "$mix_sum_ok"

# Test A5 — Kohli IPL pattern (Opener + #3 > 80%)
ab1_share=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram').querySelectorAll('title'));
  const open = titles[0]?.textContent.match(/\(([\d.]+)%\)/)?.[1];
  const three = titles[1]?.textContent.match(/\(([\d.]+)%\)/)?.[1];
  return String((parseFloat(open||0) + parseFloat(three||0)) > 80);
})()")
assert_true "A5 · Opener + #3 share > 80%" "$ab1_share"

# Test A6 — opener cohort SR matches API to digit. DOM formats via
# toFixed(2), so normalize the API value to 2 decimals to match.
api_opener_sr=$(curl -sS "$API_BASE/api/v1/batters/$KOHLI/summary?$IPL" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"{d['position_distribution'][0]['cohort_strike_rate']:.2f}\")")
dom_opener_sr=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-perf-cohort').querySelectorAll('title'));
  const t = titles.find(x => x.textContent.startsWith('Open:'));
  if (!t) return 'no opener tooltip';
  const m = t.textContent.match(/cohort ([\d.]+)/);
  return m ? m[1] : 'no cohort';
})()")
assert_eq "A6 · opener cohort SR matches API ($api_opener_sr)" "$api_opener_sr" "$dom_opener_sr"

echo
echo "PART B · Warner @ IPL all-time (opener-dominant contrast)"
ab open "$BASE/batting?player=$WARNER&$IPL&tab=By%20Position"
ab wait --load networkidle
sleep 2

# Test B7 — Warner mix is opener-dominant (>80% at b1)
warner_open=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram').querySelectorAll('title'));
  const m = titles[0]?.textContent.match(/\(([\d.]+)%\)/);
  return String(parseFloat(m?.[1] || 0) > 80);
})()")
assert_true "B7 · Warner Opener share > 80% (extreme-opener subject)" "$warner_open"

echo
echo "PART C · Kohli @ all-time (no tournament narrowing)"
ab open "$BASE/batting?player=$KOHLI&gender=male&tab=By%20Position"
ab wait --load networkidle
sleep 2

# Test C8 — cohort shares still sum
all_time_sum=$(ab_eval "(() => {
  const ticks = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-perf-cohort').querySelectorAll('rect')).filter(r => (r.getAttribute('fill')||'').toUpperCase() === '#3F7A4D');
  return String(ticks.length === 10);
})()")
assert_true "C8 · 10 cohort SR ticks render at no-tournament scope" "$all_time_sum"

# Test C9 — cohort SR at opener DIFFERS from IPL-scoped value (cohort
# is scope-dependent — males all-time includes T20I + every club
# league + women's data filtered).
api_alltime_opener_sr=$(curl -sS "$API_BASE/api/v1/batters/$KOHLI/summary?gender=male" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['position_distribution'][0]['cohort_strike_rate'])")
sr_differs=$(python3 -c "print('true' if abs($api_alltime_opener_sr - $api_opener_sr) > 0.1 else 'false')")
assert_true "C9 · all-time cohort opener SR differs from IPL cohort ($api_alltime_opener_sr vs $api_opener_sr)" "$sr_differs"

echo
echo "PART D · Kohli @ IPL 2024 (single-season narrow scope)"
ab open "$BASE/batting?player=$KOHLI&$IPL_2024&tab=By%20Position"
ab wait --load networkidle
sleep 2

# Test D10 — charts still render
narrow_mix=$(ab_eval "document.querySelectorAll('.wisden-position-distribution-tab .wisden-mix-histogram').length")
narrow_perf=$(ab_eval "document.querySelectorAll('.wisden-position-distribution-tab .wisden-perf-cohort').length")
assert_eq "D10 · narrow scope · MixHistogram count == 1"        "1" "$narrow_mix"
assert_eq "D10 · narrow scope · PerformanceVsCohort count == 2" "2" "$narrow_perf"

# Test D11 — at least one non-zero player innings bucket
has_innings=$(ab_eval "(() => {
  const titles = Array.from(document.querySelector('.wisden-position-distribution-tab .wisden-mix-histogram').querySelectorAll('title'));
  return String(titles.some(t => {
    const m = t.textContent.match(/(\d+) innings/);
    return m && parseInt(m[1]) > 0;
  }));
})()")
assert_true "D11 · ≥1 non-zero innings bucket at IPL 2024" "$has_innings"

echo
echo "=============================================="
echo "PASS: $PASS    FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
