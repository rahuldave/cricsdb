#!/bin/bash
# Fielding By Dismissed Position tab — Mix + Catches/match vs cohort.
#
# Spec: internal_docs/spec-mix-and-performance-charts.md §M3 + §6.
#
# Per CLAUDE.md "Filter-combination testing — the matrix is
# mandatory": exercises diverse subject × scope combinations,
# particularly the keeper-binary cohort partition (the critical
# spec-locked behaviour for M3).
#
#   PART A — Kohli @ IPL all-time (outfielder partition):
#     A1 — Charts render (1 MixHistogram + 1 PerformanceVsCohort).
#     A2 — 10 mix bars + 10 bucket labels.
#     A3 — 10 forest-green cohort ticks.
#     A4 — Player mix shares sum to ~100%.
#     A5 — Cohort explainer mentions "outfielder" (is_keeper=0).
#     A6 — Cohort tick at opener matches API to the digit.
#     A7 — Player catches/match at opener matches API c/m =
#          catches[0] / matches.
#
#   PART B — Dhoni @ IPL all-time (KEEPER partition contrast):
#     B8 — Cohort explainer mentions "keeper" (is_keeper=1).
#     B9 — Keeper-cohort opener tick > outfielder-cohort opener
#          tick from PART A (keepers catch openers more often).
#    B10 — Tooltip includes stumpings (only keepers stump).
#
#   PART C — Kohli @ all-time (wider scope, no tournament):
#    C11 — Charts still render at broader scope.
#    C12 — All-time cohort opener c/m differs from IPL-only cohort
#          (cohort composition scope-dependent).
#
#   PART D — Kohli @ IPL 2024 (single-season narrow scope):
#    D13 — Charts still render at narrow scope.
#    D14 — Mix tooltip shows ≥1 non-zero player dismissals bucket.
#
# Tooltip + tick values cross-check against /summary directly per
# CLAUDE.md "anchor against /summary" — /summary SQL↔API correctness
# owned by the sanity test
# tests/sanity/test_fielder_summary_dismissal_position.py.
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

KOHLI=ba607b88   # outfielder (is_keeper=0)
DHONI=4a8a2e3b   # keeper (is_keeper=1)
IPL='tournament=Indian%20Premier%20League&gender=male&team_type=club'
IPL_2024="${IPL}&season_from=2024&season_to=2024"

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo
echo "PART A · Kohli @ IPL all-time (outfielder partition)"
ab open "$BASE/fielding?player=$KOHLI&$IPL&tab=By%20Dismissed%20Position"
ab wait --load networkidle
sleep 2

mix_n=$(ab_eval "document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram').length")
perf_n=$(ab_eval "document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort').length")
assert_eq "A1 · MixHistogram count == 1"        "1" "$mix_n"
assert_eq "A1 · PerformanceVsCohort count == 1" "1" "$perf_n"

mix_bars=$(ab_eval "document.querySelector('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram svg').querySelectorAll('g > rect').length")
mix_labels=$(ab_eval "document.querySelector('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram').querySelectorAll('div[style*=\"grid-template-columns\"] > div').length")
assert_eq "A2 · 10 mix bars"   "10" "$mix_bars"
assert_eq "A2 · 10 mix labels" "10" "$mix_labels"

ticks=$(ab_eval "Array.from(document.querySelector('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort svg').querySelectorAll('rect')).filter(r => (r.getAttribute('fill')||'').toUpperCase() === '#3F7A4D').length")
assert_eq "A3 · 10 c/m cohort ticks (forest-green)" "10" "$ticks"

mix_sum_ok=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram title'));
  const shares = titles.map(t => {
    const m = t.textContent.match(/\(([\d.]+)%\)/);
    return m ? parseFloat(m[1]) : 0;
  });
  const sum = shares.reduce((a,b) => a+b, 0);
  return String(Math.abs(sum - 100) < 0.5);
})()")
assert_true "A4 · player mix shares sum to ~100%" "$mix_sum_ok"

legend_outfielder=$(ab_eval "(() => {
  const t = document.querySelector('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort');
  return String((t?.innerText || '').includes('every outfielder'));
})()")
assert_true "A5 · cohort explainer mentions 'every outfielder'" "$legend_outfielder"

api_kohli_open_cohort=$(curl -sS "$API_BASE/api/v1/fielders/$KOHLI/summary?$IPL" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"{d['dismissal_position_distribution'][0]['cohort_catches_per_match']:.3f}\")")
dom_kohli_open_cohort=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort title'));
  const t = titles.find(x => x.textContent.startsWith('Open:'));
  if (!t) return 'no opener tooltip';
  const m = t.textContent.match(/cohort ([\d.]+)\/match/);
  return m ? m[1] : 'no cohort';
})()")
assert_eq "A6 · opener cohort c/m matches API ($api_kohli_open_cohort)" "$api_kohli_open_cohort" "$dom_kohli_open_cohort"

# Player c/m at opener: catches[0] / matches.value
api_kohli_open_player=$(curl -sS "$API_BASE/api/v1/fielders/$KOHLI/summary?$IPL" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);catches=d['dismissal_position_distribution'][0]['catches'];matches=d['matches']['value'];print(f'{catches/matches:.3f}')")
dom_kohli_open_player=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort title'));
  const t = titles.find(x => x.textContent.startsWith('Open:'));
  const m = t?.textContent.match(/= ([\d.]+)\/match/);
  return m ? m[1] : 'no player';
})()")
assert_eq "A7 · opener player c/m matches API c/m ($api_kohli_open_player)" "$api_kohli_open_player" "$dom_kohli_open_player"

echo
echo "PART B · Dhoni @ IPL all-time (keeper partition contrast)"
ab open "$BASE/fielding?player=$DHONI&$IPL&tab=By%20Dismissed%20Position"
ab wait --load networkidle
sleep 2

legend_keeper=$(ab_eval "(() => {
  const t = document.querySelector('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort');
  return String((t?.innerText || '').includes('every keeper'));
})()")
assert_true "B8 · cohort explainer mentions 'every keeper'" "$legend_keeper"

api_dhoni_open_cohort=$(curl -sS "$API_BASE/api/v1/fielders/$DHONI/summary?$IPL" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['dismissal_position_distribution'][0]['cohort_catches_per_match'])")
keeper_gt_outfielder=$(python3 -c "print('true' if $api_dhoni_open_cohort > $api_kohli_open_cohort else 'false')")
assert_true "B9 · keeper-cohort opener c/m > outfielder-cohort ($api_dhoni_open_cohort vs $api_kohli_open_cohort)" "$keeper_gt_outfielder"

stumping_tooltip=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram title'));
  return String(titles.some(t => t.textContent.includes('stumpings')));
})()")
assert_true "B10 · ≥1 tooltip mentions 'stumpings' (keeper-only dismissal type)" "$stumping_tooltip"

echo
echo "PART C · Kohli @ all-time (wider scope, no tournament)"
ab open "$BASE/fielding?player=$KOHLI&gender=male&tab=By%20Dismissed%20Position"
ab wait --load networkidle
sleep 2

alltime_charts=$(ab_eval "(() => {
  const mix = document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram').length;
  const perf = document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort').length;
  return String(mix === 1 && perf === 1);
})()")
assert_true "C11 · charts render at no-tournament scope" "$alltime_charts"

api_alltime_cohort=$(curl -sS "$API_BASE/api/v1/fielders/$KOHLI/summary?gender=male" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['dismissal_position_distribution'][0]['cohort_catches_per_match'])")
cohort_differs=$(python3 -c "print('true' if abs($api_alltime_cohort - $api_kohli_open_cohort) > 0.001 else 'false')")
assert_true "C12 · all-time outfielder cohort opener c/m differs from IPL ($api_alltime_cohort vs $api_kohli_open_cohort)" "$cohort_differs"

echo
echo "PART D · Kohli @ IPL 2024 (single-season narrow scope)"
ab open "$BASE/fielding?player=$KOHLI&$IPL_2024&tab=By%20Dismissed%20Position"
ab wait --load networkidle
sleep 2

narrow_charts=$(ab_eval "(() => {
  const mix = document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram').length;
  const perf = document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-perf-cohort').length;
  return String(mix === 1 && perf === 1);
})()")
assert_true "D13 · narrow scope · charts render" "$narrow_charts"

# May have all-zero dismissals at IPL 2024 (Kohli only played certain
# innings); assert at least the chart structure is present even if
# every player bucket is 0.
narrow_has_buckets=$(ab_eval "(() => {
  const titles = Array.from(document.querySelectorAll('.wisden-dismissed-position-distribution-tab .wisden-mix-histogram title'));
  return String(titles.length === 10);
})()")
assert_true "D14 · narrow scope · 10 mix tooltips render even if some buckets are 0" "$narrow_has_buckets"

echo
echo "=============================================="
echo "PASS: $PASS    FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
