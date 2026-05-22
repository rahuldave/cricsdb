#!/bin/bash
# Batting · vertical "mean position" markers on two charts:
#   /batting?tab=By+Position    — oxblood dashed line at the player's
#                                  mean batting BUCKET on the Position-mix
#                                  histogram (so the reader sees where
#                                  the player typically operates).
#   /batting?tab=Inter-Wicket   — same marker, in WICKETS-DOWN units, on
#                                  the Strike-Rate-by-Wickets-Down chart
#                                  (wickets-down = position − 1, where
#                                  bucket 1 / Opener averages to 0.5).
#
# Asserts:
#   1. Marker renders on the Position-mix chart with a hover tooltip
#      containing the computed mean.
#   2. Marker renders on the Inter-Wicket SR chart with a visible
#      "mean entry: N wkts" caption.
#   3. The mean BUCKET reported in the Position-mix tooltip matches a
#      direct recompute against /batters/{id}/summary's
#      `position_distribution` (weighted average of bucket × innings).
#
# Red-before-green: HEAD~1 lacks `verticalMarker` on MixHistogram /
# LineChart and lacks the meanPositionBucket/meanWicketsDown helpers,
# so no markers render.

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Anchor against the live API: recompute the SQL-anchored mean.
api_mean=$(curl -sS "$API/api/v1/batters/$PLAYER/summary?gender=male" \
  | python3 -c "
import json,sys
pd=json.load(sys.stdin)['position_distribution']
tot=sum(e['innings'] or 0 for e in pd)
m=sum((e['innings'] or 0)*e['bucket'] for e in pd)/tot
print(f'{m:.2f}')")
echo "  API mean bucket: $api_mean"

echo "=== /batting · By Position · Position-mix marker ==="
ab open "$BASE/batting?player=$PLAYER&gender=male&tab=By+Position"
ab wait --load networkidle
ab wait --text "Position mix"
ab wait 2000
out=$(ab_eval "(() => {
  const ln = document.querySelector('[data-testid=\"wisden-vertical-marker\"]');
  if (!ln) return { found: false };
  const titleEl = ln.parentElement && ln.parentElement.querySelector('title');
  return { found: true, label: titleEl && titleEl.textContent };
})()")
echo "  $out"
if echo "$out" | grep -q '"found": *true'; then
  ok "By Position chart has a vertical marker"
else
  bad "By Position chart missing the vertical marker"
fi
if echo "$out" | grep -q "Mean position: bucket ${api_mean}"; then
  ok "By Position marker label matches API-derived mean bucket ($api_mean)"
else
  bad "By Position marker label does NOT match API mean ($api_mean)"
fi

echo
echo "=== /batting · Inter-Wicket · SR marker ==="
ab open "$BASE/batting?player=$PLAYER&gender=male&tab=Inter-Wicket"
ab wait --load networkidle
ab wait --text "Strike Rate by Wickets Down"
ab wait 2000
out=$(ab_eval "(() => {
  // The HTML overlay uses a dashed left-border; find any descendant of
  // .wisden-chart-title’s ancestor LineChart container with that style.
  const headers = Array.from(document.querySelectorAll('.wisden-chart-title')).filter(h => h.textContent && h.textContent.includes('Strike Rate by Wickets Down'));
  if (headers.length === 0) return { found: false, why: 'no chart' };
  let p = headers[0].parentElement;
  while (p && !p.querySelector('svg')) p = p.parentElement;
  if (!p) return { found: false, why: 'no svg ancestor' };
  // The marker label sits in an absolute div with color '#7A1F1F'.
  const labels = Array.from(p.querySelectorAll('div')).filter(d => d.style && d.style.color === 'rgb(122, 31, 31)');
  const label = labels.find(d => d.textContent && d.textContent.includes('mean entry'));
  return { found: !!label, label: label && label.textContent };
})()")
echo "  $out"
if echo "$out" | grep -q '"found": *true'; then
  ok "Inter-Wicket chart has the mean-entry marker label"
else
  bad "Inter-Wicket chart missing the mean-entry marker"
fi
if echo "$out" | grep -q "mean entry:"; then
  ok "Inter-Wicket marker label format reads \"mean entry: …\""
else
  bad "Inter-Wicket marker label format wrong"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
