#!/bin/bash
# club-tier team_class FilterBar — pill rendering + URL state plumbing.
# Polymorphic counterpart to team_class_filterbar.sh (intl FM toggle).
#
# Subjects: Mumbai Indians (primary), Surrey (secondary). Anchor counts
# pinned to spec-filterbar-team-class-club.md §5 (P5-P10).
#
# Prereqs: agent-browser, vite (any port — auto-discovered), uvicorn :8000.
set -u

# Auto-discover vite port (sometimes 5173, sometimes 5174+ when in use)
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  if [ "$3" = "$2" ]; then ok "$1"; else bad "$1 — expected $2, got $3"; fi
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ────────────────────────────────────────────
echo "Test 1 · Pill rendering by team_type"
ab open "$BASE/teams?gender=male&team_type=club"
settle
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Marquee\"]') ? 'visible' : 'hidden'")
assert_eq "club: Primary tier button visible" '"visible"' "$v"
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Domestic\"]') ? 'visible' : 'hidden'")
assert_eq "club: Secondary tier button visible" '"visible"' "$v"
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "club: FM toggle hidden" '"hidden"' "$v"

ab open "$BASE/teams?gender=male&team_type=international"
settle
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Marquee\"]') ? 'visible' : 'hidden'")
assert_eq "intl: Primary tier button hidden" '"hidden"' "$v"
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "intl: FM toggle visible" '"visible"' "$v"

ab open "$BASE/teams?gender=male"
settle
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Marquee\"]') ? 'visible' : 'hidden'")
assert_eq "type=All: Primary tier button hidden" '"hidden"' "$v"

# ────────────────────────────────────────────
echo "Test 2 · Click flow on club: All / Primary / Secondary"
ab open "$BASE/teams?gender=male&team_type=club&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Primary' && b.title?.startsWith('Marquee')).click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "click Primary → URL gains team_class=primary_club" '"primary_club"' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b=>b.textContent.trim()==='Primary' && b.title?.startsWith('Marquee'))[0]?.classList.contains('is-active')")
assert_eq "Primary button is-active" 'true' "$v"

ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Secondary' && b.title?.startsWith('Domestic')).click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class')")
assert_eq "click Secondary → URL = secondary_club" '"secondary_club"' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b=>b.textContent.trim()==='Primary' && b.title?.startsWith('Marquee'))[0]?.classList.contains('is-active')")
assert_eq "Primary button no longer active" 'false' "$v"
v=$(ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b=>b.textContent.trim()==='Secondary' && b.title?.startsWith('Domestic'))[0]?.classList.contains('is-active')")
assert_eq "Secondary button is-active" 'true' "$v"

ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b => b.textContent.trim() === 'All' && b.title?.startsWith('Show every'))[0]?.click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "click All → team_class cleared from URL" '""' "$v"

# ────────────────────────────────────────────
echo "Test 3 · ScopeStatusStrip chip renders for each value"
ab open "$BASE/teams?gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club"
settle
v=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent.includes('Team class: primary clubs')")
assert_eq "strip shows 'primary clubs' chip" 'true' "$v"

ab open "$BASE/teams?gender=male&team_type=club&season_from=2024&season_to=2025&team_class=secondary_club"
settle
v=$(ab_eval "document.querySelector('.wisden-scope-strip')?.textContent.includes('Team class: secondary clubs')")
assert_eq "strip shows 'secondary clubs' chip" 'true' "$v"

# ────────────────────────────────────────────
echo "Test 4 · Per-team narrowing (P5-P10 anchors via DOM)"
# Mumbai Indians ⊂ primary: P5=30, P6=30 (no-op), P7=0 (cross-tier)
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=primary_club"
sleep 4
v=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "MI + primary_club → 30 matches (P6)" '"30"' "$v"

ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Secondary' && b.title?.startsWith('Domestic')).click()" >/dev/null
sleep 4
v=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "MI + secondary_club → 0 matches (P7 cross-tier)" '"0"' "$v"

# Surrey ⊂ secondary: P8=30, P9=0 (cross-tier), P10=30 (no-op)
ab open "$BASE/teams?team=Surrey&gender=male&team_type=club&season_from=2024&season_to=2025&team_class=secondary_club"
sleep 4
v=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "Surrey + secondary_club → 30 matches (P10)" '"30"' "$v"

ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Primary' && b.title?.startsWith('Marquee')).click()" >/dev/null
sleep 4
v=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "Surrey + primary_club → 0 matches (P9 cross-tier)" '"0"' "$v"

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
