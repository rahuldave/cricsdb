#!/bin/bash
# Rolling-mean overlay window — cross-panel integration test.
#
# Locks the per-grain × per-discipline windows codified in
# internal_docs/colors.md "Rolling-mean windows by grain":
#
#   Player batting  N=5    bowling N=5    (fielder has no overlay)
#   Team   batting  N=7    bowling N=7
#   Team   fielding  catches  N=7
#                    run_outs N=12
#                    stumpings N=12
#
# Three assertions per panel/metric:
#   1. The legend reads "rolling-N mean" with the exact N
#      configured for that panel/metric — drift between
#      ROLLING_WINDOW const, the gate threshold, and the legend
#      text would surface here.
#   2. The oxblood polyline (`[data-ref="rolling"]`) draws.
#   3. The polyline point count equals (bar count − N + 1).
#      This validates that the gate `points.length >= N` and
#      the rolling math both use the same N — if the gate used
#      10 but the const said 5, we'd see 5 extra points
#      compared to the bars count and this would fail.
#
# Per CLAUDE.md "Red-then-green test discipline" + "Tests must
# cover EVERY call site of a shared abstraction": exercises all
# 5 panels that ship the overlay and all 3 metrics on the
# per-metric team-fielding panel — 7 cells total.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL":
# the bar counts on each panel are themselves derived from the
# observation arrays the API returns, so the only anchors needed
# here are the rolling-mean math invariants (polyline_pts =
# bars − N + 1).

set -u

BASE="${BASE:-http://localhost:5173}"
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

# Probe the rolling overlay on whatever sparkline is currently
# mounted. Returns JSON {bars, polyline_pts, legend_n}.
probe_rolling='
(() => {
  const sp = document.querySelector(".wisden-dist-sparkline")
  if (!sp) return JSON.stringify({error: "no-sparkline"})
  const rl = sp.querySelector("[data-ref=\"rolling\"]")
  // Bar rects only — exclude reference lines and the baseline rule.
  const bars = sp.querySelectorAll("rect").length
  const polyline_pts = rl ? rl.getAttribute("points").trim().split(/\s+/).length : 0
  const legendSpan = Array.from(document.querySelectorAll("span"))
    .find(s => /^rolling-\d+ mean$/.test((s.textContent || "").trim()))
  const m = legendSpan ? (legendSpan.textContent || "").match(/rolling-(\d+) mean/) : null
  const legend_n = m ? parseInt(m[1], 10) : null
  return JSON.stringify({bars, polyline_pts, legend_n})
})()
'

# Verify (panel_label, expected_N) given the page is already loaded.
verify_panel() {
  local label="$1" expected_n="$2"
  local raw n bars pts
  raw=$(ab_eval "$probe_rolling" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
  n=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin).get('legend_n'))")
  bars=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin).get('bars'))")
  pts=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin).get('polyline_pts'))")

  assert_eq "$label · legend reads rolling-$expected_n mean" "$expected_n" "$n"
  # Polyline must actually be drawn (pts > 0).
  if [ "$pts" -gt 0 ] 2>/dev/null; then
    ok "$label · oxblood polyline draws (pts=$pts)"
  else
    bad "$label · oxblood polyline did NOT draw (pts=$pts)"
  fi
  # bars includes the value bars only — reference lines are <line>
  # not <rect>. polyline_pts should equal bars - N + 1.
  local expected_pts=$((bars - expected_n + 1))
  assert_eq "$label · polyline_pts == bars - N + 1" "$expected_pts" "$pts"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
ab set viewport 1280 800

KOHLI=ba607b88
BUMRAH=462411b3
MI_URL='team=Mumbai+Indians'

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Player batting (Kohli) — runs tab, N=5"

ab open "$BASE/batting?player=$KOHLI"
settle 4
verify_panel "Batter runs" 5

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Player batting (Kohli) — SR tab, N=5"

ab open "$BASE/batting?player=$KOHLI&dist_metric=sr"
settle 4
verify_panel "Batter SR" 5

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · Player bowling (Bumrah) — wickets tab, N=5"

ab open "$BASE/bowling?player=$BUMRAH"
settle 4
verify_panel "Bowler wickets" 5

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · Player bowling (Bumrah) — economy tab, N=5"

ab open "$BASE/bowling?player=$BUMRAH&dist_metric=economy"
settle 4
verify_panel "Bowler economy" 5

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · Team batting (MI) — runs tab, N=7"

ab open "$BASE/teams?$MI_URL&tab=Batting"
settle 4
verify_panel "Team batting runs" 7

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · Team batting (MI) — run_rate tab, N=7"

ab open "$BASE/teams?$MI_URL&tab=Batting&dist_metric_t_bat=run_rate"
settle 4
verify_panel "Team batting RR" 7

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 7 · Team bowling (MI) — wickets tab, N=7"

ab open "$BASE/teams?$MI_URL&tab=Bowling"
settle 4
verify_panel "Team bowling wickets" 7

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 8 · Team bowling (MI) — economy tab, N=7"

ab open "$BASE/teams?$MI_URL&tab=Bowling&dist_metric_t_bowl=economy"
settle 4
verify_panel "Team bowling economy" 7

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 9 · Team fielding (MI) — catches tab, N=7"

ab open "$BASE/teams?$MI_URL&tab=Fielding"
settle 4
verify_panel "Team fielding catches" 7

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 10 · Team fielding (MI) — run_outs tab, N=12"

ab open "$BASE/teams?$MI_URL&tab=Fielding&dist_metric_t_field=run_outs"
settle 4
verify_panel "Team fielding run_outs" 12

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 11 · Team fielding (MI) — stumpings tab, N=12"

ab open "$BASE/teams?$MI_URL&tab=Fielding&dist_metric_t_field=stumpings"
settle 4
verify_panel "Team fielding stumpings" 12

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 12 · Non-Scope windows do NOT draw the overlay"
# Per the panel logic: showRolling = window === 'scope' && ...
# Last_60d / last_6mo / last_1yr never draw the polyline regardless
# of N.

ab open "$BASE/batting?player=$KOHLI&dist_window=last_1yr"
settle 4
raw=$(ab_eval "$probe_rolling" | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
pts_last1y=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin).get('polyline_pts'))")
assert_eq "Batter last_1yr: polyline NOT drawn" "0" "$pts_last1y"
legend_n_last1y=$(echo "$raw" | python3 -c "import sys,json; v=json.load(sys.stdin).get('legend_n'); print(v if v is not None else 'None')")
assert_eq "Batter last_1yr: legend has no rolling-N entry" "None" "$legend_n_last1y"

agent-browser close --all >/dev/null 2>&1 || true

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────"
echo "Summary: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "All rolling-window assertions green."
