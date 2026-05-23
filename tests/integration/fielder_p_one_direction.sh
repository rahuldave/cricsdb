#!/bin/bash
# Fielding catches P(=1) chip now carries `direction: "higher_better"`
# (was null / descriptive). Spec rationale: more single-catch matches
# lifts mass off the 0-catch tail, which is positive regardless of
# whether it converts into a 2+ haul. User-asked 2026-05-22.
#
# Asserts:
#   1. API returns direction="higher_better" + a non-null delta_pct
#      on the catches p_one record.
#   2. The frontend chip caption shows the cohort baseline + a green
#      arrow (good polarity, since player exceeds cohort).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_dir=$(curl -sS "$API/api/v1/fielders/$PLAYER/distribution?gender=male" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['lifetime']['catches']['milestones']['p_one']['direction'])")
echo "  API p_one direction: $api_dir"
if [ "$api_dir" = "higher_better" ]; then
  ok "API direction is higher_better"
else
  bad "API direction is $api_dir (expected higher_better)"
fi

api_delta=$(curl -sS "$API/api/v1/fielders/$PLAYER/distribution?gender=male" \
  | python3 -c "import json,sys; v=json.load(sys.stdin)['lifetime']['catches']['milestones']['p_one']['delta_pct']; print('null' if v is None else f'{v:.1f}')")
echo "  API p_one delta_pct: $api_delta"
if [ "$api_delta" != "null" ]; then
  ok "API p_one carries a non-null delta_pct ($api_delta)"
else
  bad "API delta_pct still null"
fi

ab open "$BASE/fielding?player=$PLAYER&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait 2500

# Find the P(=1) chip caption.
out=$(ab_eval "(() => {
  const labels = Array.from(document.querySelectorAll('span')).filter(el => {
    const t = (el.textContent || '').trim();
    return t === 'P(=1)' && el.children.length === 0;
  });
  if (labels.length === 0) return { found: false };
  let chip = labels[0].parentElement;
  while (chip && getComputedStyle(chip).borderRadius === '0px') chip = chip.parentElement;
  if (!chip) return { found: false, why: 'no chip ancestor' };
  // Caption is a sibling/descendant of the chip's flex column wrapper.
  let wrapper = chip.parentElement;
  const caption = wrapper && wrapper.querySelector('.prob-chip-caption');
  if (!caption) return { found: true, caption: null };
  const arrow = caption.querySelector('span');
  return {
    found: true,
    caption: caption.textContent,
    deltaColor: arrow ? getComputedStyle(arrow).color : null,
  };
})()")
echo "  caption probe: $out"
if echo "$out" | grep -q '↑'; then
  ok "P(=1) caption contains an up arrow"
else
  bad "P(=1) caption missing up arrow"
fi
# COLOR_GOOD = forest green ≈ rgb(63, 122, 77)
if echo "$out" | grep -qE '"deltaColor": *"rgb\(63, *122, *77\)"'; then
  ok "P(=1) delta rendered in green (good polarity)"
else
  bad "P(=1) delta not green: $out"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
