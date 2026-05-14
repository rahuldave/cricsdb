#!/bin/bash
# Charts · rotated x-axis labels must sit OUTSIDE the chart drawing
# area, not inside it.
#
# THE BUG THIS GUARDS AGAINST
#
# Commit eb8e69f (May 2026) inserted <ChartHeader> as the first child
# of the BarChart wrapper. The wrapper was `position: relative`; the
# rotated-label overlay was `position: absolute; top: NN`. That made
# the overlay measure from the WRAPPER top — which now sat header-
# height pixels ABOVE the SVG top. Labels drifted UP into the plot
# area (visible as year labels appearing inside the bars).
#
# Fix (commit TBD): extract <ChartContainer> that wraps the chart's
# SVG + overlays in their own `position: relative` block, with the
# header rendered OUTSIDE that block. The class of bug becomes
# structurally impossible: the overlay's containing block is now a
# div that contains the SVG only — header lives elsewhere.
#
# THE INVARIANT
#
# For every chart on the page that emits rotated-text labels:
#   1. Walk up from the label to its nearest `position: relative`
#      ancestor (its containing block for `top: NN`).
#   2. That ancestor must NOT contain any ChartHeader element
#      (.wisden-chart-title / .wisden-section-title / .section-label).
#      If it does, the overlay's `top` measures from a wrapper that
#      includes the header → labels drift into the plot area → bug.
#
# This invariant is structural, not pixel-arithmetic, so it doesn't
# couple to BarChart's bottom-margin / rotation-angle constants. Any
# new chart wrapper that re-introduces the "header inside the
# positioning context" pattern fails the test on the next CI run.
#
# Spec: internal_docs/spec-chart-wrapper-regression.md (TBD).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

PROBE='(() => {
  const allRot = Array.from(document.querySelectorAll("div")).filter(d => {
    const s = d.getAttribute("style") || "";
    return /rotate\(-?\d+deg\)/.test(s) && d.children.length === 0 && d.textContent.trim().length > 0;
  });
  // Group rotated labels by their nearest position:relative ancestor (their containing block).
  const groups = new Map();
  for (const label of allRot) {
    let p = label.parentElement;
    let ctx = null;
    while (p && p !== document.body) {
      const s = window.getComputedStyle(p);
      if (s.position === "relative" || s.position === "absolute") { ctx = p; break; }
      p = p.parentElement;
    }
    if (!ctx) continue;
    if (!groups.has(ctx)) groups.set(ctx, []);
    groups.get(ctx).push(label);
  }
  // For each group, check whether the containing block also contains a chart header.
  const findings = [];
  for (const [ctx, labels] of groups) {
    const header = ctx.querySelector(".wisden-chart-title, .wisden-section-title, .section-label, .wisden-kicker");
    const headerText = header ? header.textContent.slice(0, 40) : null;
    if (!header) continue;  // OK — header outside the positioning context
    findings.push({
      bug: "header_in_positioning_context",
      header_text: headerText,
      sample_label: labels[0].textContent.trim().slice(0, 14),
      label_count: labels.length,
    });
  }
  return JSON.stringify(findings);
})()'

run_page() {
  local url="$1" label="$2"
  agent-browser close --all >/dev/null 2>&1
  ab open "$url"
  sleep 4
  # Scroll the page to force lazy-mounted charts to render
  ab_eval "window.scrollTo(0, document.body.scrollHeight); 'sb'" >/dev/null
  sleep 2
  ab_eval "window.scrollTo(0, 0); 't'" >/dev/null
  sleep 1
  local out=$(ab_eval "$PROBE" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
  if [ "$out" = "[]" ]; then
    ok "$label · no chart-header-in-positioning-context bugs"
  else
    bad "$label · header-in-context detected: $out"
  fi
}

agent-browser close --all >/dev/null 2>&1
sleep 1

# Pages that were broken pre-fix (confirmed via probe on 2026-05-14).
run_page "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Batting"  "/teams CSK Batting"
run_page "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Bowling"  "/teams CSK Bowling"
run_page "$BASE/series?tab=Batting"                                                      "/series tier-all Batting"
run_page "$BASE/batting?player=ba607b88&gender=male"                                     "/batting V Kohli"

# Mobile-viewport check on one representative page.
agent-browser set viewport 390 844 >/dev/null 2>&1
run_page "$BASE/batting?player=ba607b88&gender=male"                                     "/batting V Kohli (mobile 390×844)"
agent-browser set viewport 1280 800 >/dev/null 2>&1

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
