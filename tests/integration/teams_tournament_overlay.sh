#!/bin/bash
# Teams chart scope-baseline overlay from spec-series-trend-charts.md step 11.
#
# Asserts:
#  1. Rate-rate LineCharts on Teams → Batting/Bowling/Fielding render
#     a forest-green pool-weighted league reference line at EVERY
#     scope — visible via the in-chart legend ("<Team>" + auto-derived
#     `abbreviateScope(filters) + " avg"`).
#  2. With `tournament=IPL`, legend reads "<Team>" / "men's · Indian
#     Premier League avg".
#  3. Without tournament, legend reads "<Team>" / "men's · club avg"
#     (or whatever abbreviateScope renders for the broader scope).
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Read all SVG text nodes inside the named chart — Semiotic puts the
# legend labels in plain <text> tags, no dedicated class. Concatenated
# pipe-separated so we can grep for team + tournament-avg strings.
chart_legend() {
  local title="$1"
  ab_eval "(() => { const t = Array.from(document.querySelectorAll('.wisden-chart-title')).find(t => t.textContent?.trim() === '$title'); const wrap = t?.closest('.w-full'); return wrap ? Array.from(wrap.querySelectorAll('svg text')).map(e => e.textContent?.trim()).filter(Boolean).join('|') : 'NO_WRAP'; })()"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Test 1 · MI @ IPL — overlay visible on rate charts"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Batting"
sleep 5

for title in 'Run rate by season' 'Boundary % by season' 'Dot % by season'; do
  leg=$(unq "$(chart_legend "$title")")
  if [[ "$leg" == *"Mumbai Indians"* && "$leg" == *"Indian Premier League"* ]]; then
    ok "Batting · $title — legend has team + tournament-avg ($leg)"
  else
    bad "Batting · $title — legend missing overlay entries (got '$leg')"
  fi
done

echo "Test 2 · MI @ IPL on Bowling tab — overlay visible"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Bowling"
sleep 5
for title in 'Economy by season' 'Dot % by season'; do
  leg=$(unq "$(chart_legend "$title")")
  if [[ "$leg" == *"Mumbai Indians"* && "$leg" == *"Indian Premier League"* ]]; then
    ok "Bowling · $title — legend has overlay entries"
  else
    bad "Bowling · $title — legend missing overlay entries (got '$leg')"
  fi
done

echo "Test 3 · MI @ IPL on Fielding tab — overlay visible on catches/match"
ab open "$BASE/teams?team=Mumbai%20Indians&tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Fielding"
sleep 5
leg=$(unq "$(chart_legend "Catches per match by season")")
if [[ "$leg" == *"Mumbai Indians"* && "$leg" == *"Indian Premier League"* ]]; then
  ok "Fielding · Catches per match by season — legend has overlay entries"
else
  bad "Fielding · Catches per match by season — legend missing overlay entries (got '$leg')"
fi

echo "Test 4 · MI WITHOUT tournament filter — overlay still visible, scope-derived label"
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&tab=Batting"
sleep 5
leg=$(unq "$(chart_legend "Run rate by season")")
# Legend should now ALWAYS show both lines. Without tournament, the
# baseline label comes from abbreviateScope(filters) — for men's club
# scope, that's "men's · club avg".
if [[ "$leg" == *"Mumbai Indians"* && "$leg" == *"men's · club avg"* ]]; then
  ok "Batting · Run rate by season — overlay visible, label '$leg'"
else
  bad "Batting · Run rate by season — expected overlay + 'men's · club avg' label, got '$leg'"
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
