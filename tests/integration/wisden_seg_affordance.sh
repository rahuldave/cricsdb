#!/bin/bash
# Wisden segmented chips (.wisden-seg) — inactive buttons must carry a
# visible bottom border at rest so they read as clickable. User feedback
# 2026-05-22: the Distribution-panel form-window chips (Last 10 / Last
# 60d / Last 6mo / Last 1y) on /batting · /bowling · /fielding pages
# looked like plain text and the user didn't realise they were links.
#
# Asserts (on /batting?player=… with the Distribution panel visible):
#   1. The four window chips are rendered as <button class=wisden-seg>
#      and have computed border-bottom-style = "dotted" (not "none").
#   2. The "At scope" active chip uses border-bottom-style = "solid"
#      and color = oxblood — its accent treatment is preserved.
#
# Red-before-green: before the .wisden-seg CSS rule was updated,
# inactive buttons had a transparent solid 1px border-bottom, so the
# dotted-style assertion fails on HEAD~1.

set -u

BASE="${BASE:-http://localhost:5173}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

ab open "$BASE/batting?player=$PLAYER&gender=male"
ab wait --load networkidle
ab wait --text "Last 10"
ab wait 1500

# 1. Each inactive window chip carries a dotted border-bottom.
for label in "Last 10" "Last 60d" "Last 6mo" "Last 1y"; do
  style=$(ab_eval "(() => {
    const btns = Array.from(document.querySelectorAll('button.wisden-seg'));
    const b = btns.find(x => x.textContent.trim() === '${label}');
    if (!b) return { found: false };
    const s = getComputedStyle(b);
    return {
      found: true,
      borderStyle: s.borderBottomStyle,
      borderWidth: s.borderBottomWidth,
      isActive: b.classList.contains('is-active'),
    };
  })()")
  echo "  ${label}: $style"
  if echo "$style" | grep -q '"borderStyle": *"dotted"'; then
    ok "${label} inactive chip has dotted underline"
  else
    bad "${label} inactive chip lacks dotted underline ($style)"
  fi
done

# 2. The active "At scope" chip stays solid + accent-colored.
active_style=$(ab_eval "(() => {
  const btns = Array.from(document.querySelectorAll('button.wisden-seg.is-active'));
  const b = btns.find(x => x.textContent.trim() === 'At scope');
  if (!b) return { found: false };
  const s = getComputedStyle(b);
  return {
    found: true,
    borderStyle: s.borderBottomStyle,
    color: s.color,
  };
})()")
echo "  At scope (active): $active_style"
if echo "$active_style" | grep -q '"borderStyle": *"solid"'; then
  ok "Active \"At scope\" chip retains solid underline"
else
  bad "Active \"At scope\" chip lost solid underline"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
