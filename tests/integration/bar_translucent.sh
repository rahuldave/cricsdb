#!/bin/bash
# Translucent BarChart bars — verifies the `barOpacity` prop on
# BarChart propagates a `wisden-bar-translucent` class and a
# `--wisden-bar-opacity` CSS variable onto the chart's outer block.
# The global rule in index.css then fades whatever bar elements
# Semiotic renders (which vary between versions — line / rect / path
# — so we don't assert on them directly).
#
# Sites under test:
#   /batting?tab=By+Over       — barOpacity={0.8} (Strike Rate by Over)
#   /batting?tab=Dismissals    — barOpacity={0.8} (Dismissals by Over)
#
# Red-before-green evidence: before the `barOpacity` prop / CSS rule
# were added, no chart wrapper carried `wisden-bar-translucent` — the
# class-presence assertion fails on HEAD~1.

set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Probe: find the wisden-bar-translucent chart wrapper whose header
# matches the given title, then return its class presence + the
# computed --wisden-bar-opacity CSS variable.
PROBE_TEMPLATE='(() => {
  const title = TITLE;
  const containers = Array.from(document.querySelectorAll(".wisden-bar-translucent"));
  for (const c of containers) {
    const h = c.querySelector(".wisden-chart-title, h2, h3");
    if (h && (h.textContent || "").trim().includes(title)) {
      return {
        ok: true,
        hasClass: c.classList.contains("wisden-bar-translucent"),
        cssVar: getComputedStyle(c).getPropertyValue("--wisden-bar-opacity").trim(),
      };
    }
  }
  return { ok: false, why: "no wisden-bar-translucent wrapper carries this title" };
})()'

probe() {
  local title="$1"
  local js
  js="${PROBE_TEMPLATE/TITLE/\"$title\"}"
  ab_eval "$js"
}

echo "=== By Over · Strike Rate by Over ==="
ab open "$BASE/batting?player=ba607b88&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait --text "Strike Rate by Over"
ab wait 1500
out=$(probe "Strike Rate by Over")
echo "  probe: $out"
if echo "$out" | grep -q '"hasClass": *true'; then
  ok "By Over chart carries wisden-bar-translucent class"
else
  bad "By Over chart missing wisden-bar-translucent class"
fi
if echo "$out" | grep -q '"cssVar": *"0.8"'; then
  ok "By Over chart resolves --wisden-bar-opacity to 0.8"
else
  bad "By Over chart --wisden-bar-opacity not 0.8"
fi

echo
echo "=== Dismissals · Dismissals by Over ==="
ab open "$BASE/batting?player=ba607b88&gender=male&tab=Dismissals"
ab wait --load networkidle
ab wait --text "Dismissals by Over"
ab wait 1500
out=$(probe "Dismissals by Over")
echo "  probe: $out"
if echo "$out" | grep -q '"hasClass": *true'; then
  ok "Dismissals by Over carries wisden-bar-translucent class"
else
  bad "Dismissals by Over missing wisden-bar-translucent class"
fi
if echo "$out" | grep -q '"cssVar": *"0.8"'; then
  ok "Dismissals chart resolves --wisden-bar-opacity to 0.8"
else
  bad "Dismissals chart --wisden-bar-opacity not 0.8"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
