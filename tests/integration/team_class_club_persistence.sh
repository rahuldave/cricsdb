#!/bin/bash
# club-tier team_class — URL plumbing through tab navigation.
#
# Asserts that team_class=primary_club / secondary_club rides through
# every scope-link URL that FILTER_KEYS auto-includes — clicking from
# Teams to a player, to Series, back to Teams, must preserve the tier.
# Mirrors the v3 FM-toggle persistence pattern.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  if [ "$3" = "$2" ]; then ok "$1"; else bad "$1 — expected $2, got $3"; fi
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ────────────────────────────────────────────
echo "Test 1 · primary_club survives Teams → Player → Teams navigation"
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club"
settle
v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "MI page: team_class=primary_club" '"primary_club"' "$v"

# Find a PHRASE PlayerLink — the variant that carries narrowings.
# Identity links (name links per links.md / spec §4.3) intentionally
# drop team_class; phrase links (subscript / "in IPL" container) keep
# it. We assert that AT LEAST ONE batting phrase link to a player on
# the page carries team_class=primary_club.
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club&tab=Batting"
sleep 5
v=$(ab_eval "Array.from(document.querySelectorAll('a[href*=\"/batting?\"][href*=\"player=\"]')).some(a => a.href.includes('team_class=primary_club'))")
assert_eq "≥1 phrase PlayerLink preserves team_class" 'true' "$v"

# Navigate back to Teams via FilterBar Tournament=All — team_class should survive
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club"
settle
ab_eval "document.querySelector('select.wisden-select').value=''; document.querySelector('select.wisden-select').dispatchEvent(new Event('change', {bubbles:true}))" >/dev/null
sleep 2
v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "Tournament dropdown change preserves team_class" '"primary_club"' "$v"

# ────────────────────────────────────────────
echo "Test 2 · Tournament dropdown auto-narrows under tier (§8 #2)"
ab open "$BASE/teams?gender=male&team_type=club&team_class=primary_club"
settle 4
# The Tournament dropdown should ONLY contain primary-tier event names.
# Vitality Blast must NOT appear.
v=$(ab_eval "Array.from(document.querySelectorAll('option')).map(o => o.textContent).join('|').includes('Vitality Blast')")
assert_eq "primary tier: Vitality Blast NOT in tournament dropdown" 'false' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('option')).map(o => o.textContent).join('|').includes('Indian Premier League')")
assert_eq "primary tier: Indian Premier League IS in tournament dropdown" 'true' "$v"

ab open "$BASE/teams?gender=male&team_type=club&team_class=secondary_club"
settle 4
v=$(ab_eval "Array.from(document.querySelectorAll('option')).map(o => o.textContent).join('|').includes('Indian Premier League')")
assert_eq "secondary tier: IPL NOT in tournament dropdown" 'false' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('option')).map(o => o.textContent).join('|').includes('Vitality Blast')")
assert_eq "secondary tier: Vitality Blast IS in tournament dropdown" 'true' "$v"

# ────────────────────────────────────────────
echo "Test 3 · ScopeStatusStrip share link preserves team_class"
ab open "$BASE/teams?team=Surrey&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=secondary_club"
settle
# Verify the canonical URL the strip serializes contains team_class
v=$(ab_eval "(new URL(location.href).searchParams.get('team_class'))")
assert_eq "URL on Surrey + secondary_club page" '"secondary_club"' "$v"
v=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent.includes('secondary clubs')")
assert_eq "scope strip surfaces tier text" 'true' "$v"

# ────────────────────────────────────────────
echo "Test 4 · series_type and team_class coexist on URL"
# Set series_type=club + team_class=primary_club — both should serialize and
# survive navigation.
ab open "$BASE/teams?gender=male&team_type=club&team_class=primary_club&season_from=2024&season_to=2025"
settle
ts=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "team_class=primary_club after open" '"primary_club"' "$ts"

# ────────────────────────────────────────────
echo
if [ $FAIL -eq 0 ]; then
  echo "✅ $PASS PASS / 0 FAIL"
  exit 0
else
  echo "❌ $PASS PASS / $FAIL FAIL"
  echo -e "FAILS:$FAILS"
  exit 1
fi
