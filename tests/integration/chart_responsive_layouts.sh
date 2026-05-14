#!/bin/bash
# Chart responsive layouts — HeatmapChart + BubbleMatrix at both
# desktop and mobile viewports.
#
# THE INVARIANTS THIS GUARDS AGAINST
#
# HeatmapChart and BubbleMatrix were rewritten 2026-05-14 to use pure
# CSS Grid (no fixed-pixel margins, no JS measuredWidth, no absolute-
# positioned cells). On mobile (≤ 720px):
#
#   HeatmapChart PIVOTS: y=phase, x=season → y=season, x=phase.
#     Required because the X axis has 17+ season values vs 3 phases —
#     pivoting puts the dense dimension on the (scrollable) Y axis.
#
#   BubbleMatrix DOES NOT pivot (both axes are dense) but swaps the
#     y-label formatter for shortTeam() — "Royal Challengers Bengaluru"
#     → "RCB". Defunct-team collisions (Deccan Chargers / Delhi
#     Capitals both → "DC") resolved via SHORTNAME_OVERRIDES (defuncts
#     take the longer code: "DECC").
#
# This test asserts those two behaviours haven't drifted. A future
# refactor that breaks the pivot, removes the short-name swap, or
# loses the DECC override fails here on the next CI run.

set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Read all y-label texts from the first .wisden-heatmap on the page.
heatmap_ylabels() {
  ab_eval "(() => {
    const grid = document.querySelector('.wisden-heatmap');
    if (!grid) return '[]';
    // Y-labels are the first column children at grid positions
    // (col 1, row 2..N+1). The grid container's direct DIV children
    // alternate: [corner, x1, x2, ..., xN, y1, c11, c12, ..., y2, c21, ...].
    // Walk every CSS-Grid row's first cell.
    const cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
    const children = Array.from(grid.children);
    // skip first 'cols' children (header row), then y-label is every cols-th child
    const ylabels = [];
    for (let i = cols; i < children.length; i += cols) {
      ylabels.push(children[i].textContent.trim());
    }
    return JSON.stringify(ylabels);
  })()"
}

# Read all y-label texts from the first .wisden-bubble-matrix.
bubble_ylabels() {
  ab_eval "(() => {
    const grid = document.querySelector('.wisden-bubble-matrix');
    if (!grid) return '[]';
    const cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
    const children = Array.from(grid.children);
    const ylabels = [];
    for (let i = cols; i < children.length; i += cols) {
      const txt = children[i]?.textContent?.trim();
      if (!txt) break;  // legend trailing div has no label structure
      ylabels.push(txt);
    }
    return JSON.stringify(ylabels);
  })()"
}

assert_array_contains() {
  local label="$1" needle="$2" haystack="$3"
  # haystack arrives as JSON-string ["foo","bar"...] with backslash-
  # escaped quotes when piped through agent-browser. Unescape and
  # extract values between quotes for an exact-element membership
  # check (avoids substring false-positives like 'MI' matching 'AMIN').
  local items
  items=$(echo "$haystack" | sed -e 's/\\"/"/g' -e 's/^"//' -e 's/"$//' \
                                  -e 's/^\[//' -e 's/\]$//' \
                                  -e 's/","/\n/g' -e 's/^"//' -e 's/"$//')
  if echo "$items" | grep -Fxq "$needle"; then
    ok "$label · contains $needle"
  else
    bad "$label · expected $needle in $haystack"
  fi
}

assert_array_NOT_contains() {
  local label="$1" needle="$2" haystack="$3"
  local items
  items=$(echo "$haystack" | sed -e 's/\\"/"/g' -e 's/^"//' -e 's/"$//' \
                                  -e 's/^\[//' -e 's/\]$//' \
                                  -e 's/","/\n/g' -e 's/^"//' -e 's/"$//')
  if echo "$items" | grep -Fxq "$needle"; then
    bad "$label · should NOT contain $needle, got $haystack"
  else
    ok "$label · correctly absent: $needle"
  fi
}

# ── Test 1 · HeatmapChart DESKTOP (1280×800) — y=phase, x=season ──
agent-browser close --all >/dev/null 2>&1
sleep 1
agent-browser set viewport 1280 800 >/dev/null 2>&1
echo "Test 1 · HeatmapChart @ 1280×800 — y=phase (no pivot)"
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Batting"
sleep 6
# Scroll heatmap into view (forces measuredWidth+layout)
ab_eval "
(() => {
  const h = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('Run rate — phase × season'));
  h?.scrollIntoView({block:'start'});
})()" >/dev/null
sleep 1
ylabels=$(heatmap_ylabels)
assert_array_contains "Desktop heatmap" "powerplay" "$ylabels"
assert_array_contains "Desktop heatmap" "middle"    "$ylabels"
assert_array_contains "Desktop heatmap" "death"     "$ylabels"
# Years should NOT appear as row labels on desktop (they're columns)
assert_array_NOT_contains "Desktop heatmap" "2024" "$ylabels"

# ── Test 2 · HeatmapChart MOBILE (390×844) — y=season pivot ──
agent-browser close --all >/dev/null 2>&1
sleep 1
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Batting"
sleep 2
agent-browser set viewport 390 844 >/dev/null 2>&1
sleep 3
echo "Test 2 · HeatmapChart @ 390×844 — y=season (pivoted)"
ab_eval "
(() => {
  const h = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('Run rate — phase × season'));
  h?.scrollIntoView({block:'start'});
})()" >/dev/null
sleep 1
ylabels=$(heatmap_ylabels)
# After pivot, years are row labels
assert_array_contains "Mobile heatmap pivoted" "2024" "$ylabels"
assert_array_contains "Mobile heatmap pivoted" "2007/08" "$ylabels"
# Phases should NOT be row labels on mobile (they moved to columns)
assert_array_NOT_contains "Mobile heatmap pivoted" "powerplay" "$ylabels"

agent-browser set viewport 1280 800 >/dev/null 2>&1

# ── Test 3 · BubbleMatrix DESKTOP — full team names ──
agent-browser close --all >/dev/null 2>&1
sleep 1
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=vs+Opponent"
sleep 6
echo "Test 3 · BubbleMatrix @ 1280×800 — full team names"
ab_eval "
(() => {
  const h = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('opponent × season'));
  h?.scrollIntoView({block:'start'});
})()" >/dev/null
sleep 1
ylabels=$(bubble_ylabels)
assert_array_contains "Desktop bubble" "Mumbai Indians" "$ylabels"
assert_array_contains "Desktop bubble" "Royal Challengers Bengaluru" "$ylabels"
assert_array_contains "Desktop bubble" "Deccan Chargers" "$ylabels"
# Short codes should NOT appear on desktop
assert_array_NOT_contains "Desktop bubble" "MI" "$ylabels"
assert_array_NOT_contains "Desktop bubble" "DECC" "$ylabels"

# ── Test 4 · BubbleMatrix MOBILE — short team codes ──
agent-browser close --all >/dev/null 2>&1
sleep 1
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=vs+Opponent"
sleep 2
agent-browser set viewport 390 844 >/dev/null 2>&1
sleep 3
echo "Test 4 · BubbleMatrix @ 390×844 — short team codes"
ab_eval "
(() => {
  const h = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('opponent × season'));
  h?.scrollIntoView({block:'start'});
})()" >/dev/null
sleep 1
ylabels=$(bubble_ylabels)
assert_array_contains "Mobile bubble" "MI"   "$ylabels"
assert_array_contains "Mobile bubble" "RCB"  "$ylabels"
# CSK isn't in the list — the path team doesn't appear as its own opponent.
# DECC override — Deccan Chargers should be DECC, not DC
assert_array_contains "Mobile bubble DECC override" "DECC" "$ylabels"
# Active "DC" = Delhi Capitals (not Deccan Chargers)
assert_array_contains "Mobile bubble DC = Delhi Capitals" "DC" "$ylabels"
# Full team names should NOT appear on mobile
assert_array_NOT_contains "Mobile bubble" "Mumbai Indians" "$ylabels"
assert_array_NOT_contains "Mobile bubble" "Deccan Chargers" "$ylabels"

agent-browser set viewport 1280 800 >/dev/null 2>&1

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
