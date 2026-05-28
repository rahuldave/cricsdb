#!/bin/bash
# /series — embedded TournamentsLanding deduplication + hero-omitted tile surfacing.
#
# Context: TournamentDossier (mounted on /series) embeds
# TournamentsLanding for the long-tail directory. Until 2026-05-28 both
# rendered their own full tile sections — so /series showed every
# Recently-Played-Editions strip, International Events grid, Franchise
# Leagues grid etc. twice. We now gate every visible tile section in
# TournamentsLanding behind `!embedded` (flag-at-top pattern), leaving:
#
#   - the 3 long-tail accordion buttons (always render — unique to the
#     embedded landing)
#   - a small "secondary events" tile grid surfacing the tournaments
#     deliberately omitted from the hero's "Top events" marquee
#     (HERO_OMITTED_TOURNAMENTS in TournamentsLanding.tsx).
#
# This script locks the de-duplication + the deliberate cross-section
# moves so a future refactor can't re-introduce either bug silently.
#
# Prereqs: agent-browser, vite :5173, FastAPI :8000.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(echo "$actual" | sed -e 's/^"//' -e 's/"$//')
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
agent-browser set viewport 1280 800 >/dev/null 2>&1

echo "## /series — embedded landing de-duplication"

ab open "$BASE/series"
ab wait --load networkidle
sleep 3

# ── Test 1 — exactly one "Recently played editions" strip ──
# Before the fix the page rendered TWO RecentEditionsStrip components
# (hero's + embedded landing's). The headings were identical, so users
# saw the same 5 tiles twice on the page.
echo ""
echo "### Test 1 — exactly one .wisden-recent-editions strip"
strip_n=$(ab_eval "document.querySelectorAll('.wisden-recent-editions').length")
assert_eq "Single .wisden-recent-editions strip" "1" "$strip_n"

# Heading uniqueness check — defensive against a future refactor that
# renames the wrapper class but leaves the duplicate H3.
h3_recent=$(ab_eval "Array.from(document.querySelectorAll('h3')).filter(h => (h.textContent||'').trim() === 'Recently played editions').length")
assert_eq "Single 'Recently played editions' H3" "1" "$h3_recent"

# ── Test 2 — exactly 3 hero-omitted tiles in the embedded landing ──
# The hero deliberately drops these 3 tournaments from its top-4 slices
# (so the marquee stays focused) and surfaces them lower down in the
# embedded landing's small "secondary" grid. The grid is keyed by
# data-test-section="hero-omitted-tiles" — stable structural id.
echo ""
echo "### Test 2 — 3 hero-omitted tiles in embedded section"
omit_n=$(ab_eval "document.querySelectorAll('[data-test-section=\"hero-omitted-tiles\"] > *').length")
assert_eq "Hero-omitted tile count" "3" "$omit_n"

# Each named tile is present. Match on tile-title text (the TournamentTile
# always renders the canonical name as a heading inside the tile).
for needle in \
  "The Hundred Women's Competition" \
  "ICC Men's T20 World Cup Qualifier" \
  "ICC Women's T20 World Cup Qualifier"
do
  needle_b64=$(printf '%s' "$needle" | base64)
  present=$(ab_eval "(() => {
    const root = document.querySelector('[data-test-section=\"hero-omitted-tiles\"]');
    if (!root) return 'no-section';
    return root.textContent.includes(atob('$needle_b64')) ? 'yes' : 'no';
  })()" | sed -e 's/^"//' -e 's/"$//')
  if [ "$present" = "yes" ]; then ok "Embedded tile present: $needle"
  else bad "Embedded tile missing: $needle (got '$present')"; fi
done

# ── Test 3 — same tiles NOT in the hero's "Top events" marquee ──
# Hero's "Top events" sits between the "Recently played editions" strip
# and the "Top teams by win %" section. We scope the check to that
# textual span so a later page restructure can't trick the test.
echo ""
echo "### Test 3 — hero 'Top events' does NOT contain the omitted tournaments"
for needle in \
  "The Hundred Women's Competition" \
  "ICC Men's T20 World Cup Qualifier" \
  "ICC Women's T20 World Cup Qualifier"
do
  needle_b64=$(printf '%s' "$needle" | base64)
  in_hero_top=$(ab_eval "(() => {
    const txt = document.body.innerText;
    const a = txt.indexOf('Top events');
    const b = txt.indexOf('Top teams by win %');
    if (a < 0 || b < 0 || b <= a) return 'no-span';
    return txt.slice(a, b).includes(atob('$needle_b64')) ? 'leaked' : 'clean';
  })()" | sed -e 's/^"//' -e 's/"$//')
  if [ "$in_hero_top" = "clean" ]; then ok "Hero Top events excludes: $needle"
  else bad "Hero Top events LEAKED: $needle (got '$in_hero_top')"; fi
done

# ── Test 4 — 3 long-tail accordions still render ──
# These are the one thing only the embedded TournamentsLanding
# contributes. If a future change tightens the embedded view further
# and accidentally hides them, this test fires.
echo ""
echo "### Test 4 — 3 long-tail accordion buttons render"
accordions=$(ab_eval "Array.from(document.querySelectorAll('button')).filter(b => /\\b(Show \\d+ other|Other international tournaments \\(\\d+\\))/.test((b.textContent||'').trim())).length")
assert_eq "Accordion button count (men's rivalries + women's rivalries + other intl tournaments)" "3" "$accordions"

for label in \
  "Show 157 other men's rivalries" \
  "Show 83 other women's rivalries" \
  "Other international tournaments (669)"
do
  label_b64=$(printf '%s' "$label" | base64)
  present=$(ab_eval "Array.from(document.querySelectorAll('button')).some(b => (b.textContent||'').includes(atob('$label_b64'))) ? 'yes' : 'no'" | sed -e 's/^"//' -e 's/"$//')
  if [ "$present" = "yes" ]; then ok "Accordion present: $label"
  else bad "Accordion missing: $label"; fi
done

echo ""
echo "## Summary: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  printf 'Failures:%s\n' "$FAILS"
  exit 1
fi
exit 0
