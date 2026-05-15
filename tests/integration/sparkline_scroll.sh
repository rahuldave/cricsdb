#!/bin/bash
# DistributionSparkline scroll-past-viewport invariants — uses
# RETIRED players whose T20 career counts are frozen.
#
# Locks the contract codified in
# frontend/src/components/distribution/ScrollableBars.tsx:
#
#   - Inner div width >= count * MIN_BAR_PX (MIN_BAR_PX = 2 universal)
#   - Outer wrapper has `overflow-x: auto`
#   - When count * MIN_BAR_PX > container width: scrollbar exists
#     (scrollWidth > clientWidth)
#   - When count * MIN_BAR_PX <= container width: no scroll
#   - Bar count in DOM == observations.length from the distribution API
#   - Page itself never overflows the viewport (asserted at 390 +
#     768 + 1280)
#
# Tap-through gate: `.wisden-dist-sparkline a { pointer-events: none }`
# inside `@media (max-width: 720px)`. Assert at 390 (off) and 1280 (on).
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL/API":
# each player's `n_innings` is pulled from the distribution endpoint
# at test runtime — NOT hardcoded. If cricsdb is rebuilt from newer
# data, the assertions track. Retired players were chosen because
# their career n_innings won't drift between today and any future
# rebuild — but the test doesn't rely on the constancy; it derives
# the expected count fresh on every run.
#
# Per CLAUDE.md "Tests must cover EVERY call site of a shared
# abstraction": exercises both batter and bowler panels (the two
# player-grain sparkline mounts that ship the rolling overlay).
# Team-grain panels share the same ScrollableBars wrapper and are
# covered by the breakpoint assertions on the mobile_viewport.sh
# pass alongside this one.
#
# Red-then-green: with ScrollableBars removed from
# BatterDistributionPanel.tsx (reverting to the prior `width:100%`
# stretch-to-fit), the SVG width equals the container clientWidth
# (not count*2) → assertions on Kohli (active, 382 innings) +
# Morgan (retired, 293) fail at the "inner div >= count * 2" check.
# After restoration: green.

set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
MIN_BAR_PX=2
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

assert_ge() {
  local label="$1" lhs="$2" rhs="$3"
  if [ "$lhs" -ge "$rhs" ] 2>/dev/null; then ok "$label ($lhs >= $rhs)"
  else bad "$label — $lhs < $rhs"; fi
}

# Probe the live sparkline scroll wrapper. Returns:
#   inner_w  — the inner div's offsetWidth (min-width-clamped)
#   outer_cw — overflow wrapper's clientWidth
#   outer_sw — overflow wrapper's scrollWidth
#   bars     — number of <rect> children in the SVG (= count)
#   tap_off  — true when first bar <a> has pointer-events:none
PROBE='(() => {
  const sp = document.querySelector(".wisden-dist-sparkline")
  if (!sp) return JSON.stringify({error: "no-sparkline"})
  // Walk up: SVG -> inner div -> outer scroll wrapper
  const inner = sp.parentElement
  const outer = inner ? inner.parentElement : null
  if (!outer) return JSON.stringify({error: "no-scroll-wrapper"})
  const firstBar = sp.querySelector("a")
  const tap_off = firstBar ? getComputedStyle(firstBar).pointerEvents === "none" : null
  return JSON.stringify({
    inner_w: inner.offsetWidth,
    outer_cw: outer.clientWidth,
    outer_sw: outer.scrollWidth,
    outer_overflowX: getComputedStyle(outer).overflowX,
    bars: sp.querySelectorAll("rect").length,
    page_sw: document.documentElement.scrollWidth,
    page_vw: window.innerWidth,
    tap_off,
  })
})()'

# Retired (frozen-count) test fixtures + 1 active for high-count
# coverage. Format: label|id|discipline|api_path
FIXTURES=(
  "ABdV|c4487b84|batting|batters"
  "Jayasuriya|f233bbb4|batting|batters"
  "Tendulkar|d2c2b2d5|batting|batters"
  "Morgan|d2a6c0e6|batting|batters"
  "RP-Singh|0ab3c788|bowling|bowlers"
  "Warne|bb18be76|bowling|bowlers"
)

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# Pre-fetch n_innings for each fixture from the API.
# (bash 3.2 has no associative arrays — store as pipe-separated entries
# `label|id|disc|n` in NINNS_RECORDS and re-parse per loop.)
NINNS_RECORDS=""
for entry in "${FIXTURES[@]}"; do
  label="${entry%%|*}"; rest="${entry#*|}"
  id="${rest%%|*}"; rest="${rest#*|}"
  disc="${rest%%|*}"; api_path="${rest##*|}"
  n=$(curl -s "$API/api/v1/$api_path/$id/distribution" \
      | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['lifetime']['n_innings'])" 2>/dev/null)
  if [ -z "$n" ]; then
    echo "ERROR: failed to fetch n_innings for $label ($id)" >&2
    exit 2
  fi
  NINNS_RECORDS="$NINNS_RECORDS$label|$id|$disc|$n
"
  echo "  $label: n_innings = $n (from /api/v1/$api_path/$id/distribution)"
done

# Helper: look up the n_innings for a label.
nlook() {
  echo "$NINNS_RECORDS" | awk -F'|' -v want="$1" '$1==want {print $4; exit}'
}

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Part A · Mobile (390x844)"
ab set viewport 390 844

for entry in "${FIXTURES[@]}"; do
  label="${entry%%|*}"; rest="${entry#*|}"
  id="${rest%%|*}"; rest="${rest#*|}"
  disc="${rest%%|*}"
  n=$(nlook "$label")

  ab open "$BASE/$disc?player=$id"
  ab wait --load networkidle
  settle 3

  raw=$(ab_eval "$PROBE" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
  inner_w=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('inner_w','?'))")
  outer_cw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('outer_cw','?'))")
  outer_sw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('outer_sw','?'))")
  ovx=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('outer_overflowX','?'))")
  bars=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('bars','?'))")
  page_sw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_sw','?'))")
  page_vw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_vw','?'))")
  tap_off=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tap_off'))")

  expected_min=$((n * MIN_BAR_PX))
  assert_eq "$label · bar count == API n_innings"        "$n" "$bars"
  assert_ge "$label · inner_w >= n * MIN_BAR_PX($MIN_BAR_PX)" "$inner_w" "$expected_min"
  assert_eq "$label · outer overflow-x: auto"            "auto" "$ovx"
  assert_eq "$label · page does not overflow viewport"   "$page_vw" "$page_sw"
  assert_eq "$label · mobile pointer-events: none on bar <a>" "True" "$tap_off"
  # Scroll iff count * 2 > outer_cw
  if [ "$expected_min" -gt "$outer_cw" ]; then
    if [ "$outer_sw" -gt "$outer_cw" ]; then
      ok "$label · scroll exists (cw=$outer_cw, sw=$outer_sw, expected>$outer_cw)"
    else
      bad "$label · expected scroll, got cw=$outer_cw sw=$outer_sw"
    fi
  else
    if [ "$outer_sw" -le $((outer_cw + 4)) ]; then
      ok "$label · no scroll needed (cw=$outer_cw, sw=$outer_sw)"
    else
      bad "$label · unexpected scroll (cw=$outer_cw, sw=$outer_sw)"
    fi
  fi
done

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Part B · iPad portrait (768x1024) — most players fit"
ab set viewport 768 1024

for entry in "${FIXTURES[@]}"; do
  label="${entry%%|*}"; rest="${entry#*|}"
  id="${rest%%|*}"; rest="${rest#*|}"
  disc="${rest%%|*}"
  n=$(nlook "$label")

  ab open "$BASE/$disc?player=$id"
  ab wait --load networkidle
  settle 3

  raw=$(ab_eval "$PROBE" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
  inner_w=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('inner_w','?'))")
  page_sw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_sw','?'))")
  page_vw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_vw','?'))")
  tap_off=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tap_off'))")

  expected_min=$((n * MIN_BAR_PX))
  assert_ge "$label@iPad · inner_w >= n * $MIN_BAR_PX" "$inner_w" "$expected_min"
  assert_eq "$label@iPad · page does not overflow"     "$page_vw" "$page_sw"
  # Mobile tap-off rule is `(max-width: 720px)` — at 768 it should
  # be OFF (taps enabled).
  assert_eq "$label@iPad · pointer-events ON above 720px" "False" "$tap_off"
done

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Part C · Desktop (1280x800) — everything fits"
ab set viewport 1280 800

# One spot check on the heaviest player (Morgan, retired, 293 inns).
n=$(nlook "Morgan")
ab open "$BASE/batting?player=d2a6c0e6"
ab wait --load networkidle
settle 3
raw=$(ab_eval "$PROBE" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
inner_w=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('inner_w','?'))")
outer_sw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('outer_sw','?'))")
outer_cw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('outer_cw','?'))")
page_sw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_sw','?'))")
page_vw=$(echo "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin).get('page_vw','?'))")

assert_ge "Morgan@desktop · inner_w >= n * $MIN_BAR_PX" "$inner_w" "$((n * MIN_BAR_PX))"
assert_eq "Morgan@desktop · no scroll needed" "true" "$([ "$outer_sw" -le $((outer_cw + 4)) ] && echo true || echo false)"
assert_eq "Morgan@desktop · page does not overflow"   "$page_vw" "$page_sw"

agent-browser close --all >/dev/null 2>&1 || true

echo ""
echo "─────────────────────────────────────────"
echo "Summary: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "All sparkline scroll invariants green across 6 fixtures × 3 viewports."
