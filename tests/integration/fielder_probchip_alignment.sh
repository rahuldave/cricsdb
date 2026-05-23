#!/bin/bash
# Fielding probability chips align at the top of the chip row.
#
# The P(=1) chip is descriptive (direction === null — ticked-over once
# is neither good nor bad), so ProbChip renders no cohort caption
# beneath it. P(=0) + P(≥2) ARE directional and render a caption.
# With the chip row's old `alignItems: 'flex-end'`, the caption-less
# middle pill dropped 18px below the others. User-flagged 2026-05-22.
#
# Asserts: the bounding-box `top` of all three pills on
# /fielding?tab=By+Over matches within 1px.

set -u

BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

ab open "$BASE/fielding?player=$PLAYER&gender=male&tab=By+Over"
ab wait --load networkidle
ab wait 2500

out=$(ab_eval "(() => {
  const labels = Array.from(document.querySelectorAll('span')).filter(el => {
    const t = (el.textContent || '').trim();
    return /^P\(/.test(t) && el.children.length === 0;
  });
  if (labels.length < 3) return { found: labels.length };
  const tops = labels.slice(0, 3).map(label => {
    let chip = label.parentElement;
    while (chip && chip !== document.body) {
      const cs = getComputedStyle(chip);
      if (cs.borderRadius && parseInt(cs.borderRadius) > 5) break;
      chip = chip.parentElement;
    }
    return Math.round(chip.getBoundingClientRect().top);
  });
  return { found: labels.length, tops, diff: Math.max(...tops) - Math.min(...tops) };
})()")
echo "  probe: $out"

found=$(echo "$out" | grep -oE '"found": *[0-9]+' | grep -oE '[0-9]+')
if [ "$found" = "3" ]; then
  ok "three P() chips render"
else
  bad "expected 3 chips, found $found"
fi

diff=$(echo "$out" | grep -oE '"diff": *[0-9]+' | grep -oE '[0-9]+')
if [ -n "$diff" ] && [ "$diff" -le "1" ]; then
  ok "all three pills align (max top-diff = ${diff}px)"
else
  bad "pill tops differ by ${diff}px (expected ≤1)"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
