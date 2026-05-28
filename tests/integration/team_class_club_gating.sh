#!/bin/bash
# club-tier team_class — defensive gating (auto-clear + deep-link self-correct).
#
# Asserts the polymorphic auto-clear logic in FilterBar.tsx:
#   - intl→club clears full_member
#   - club→intl clears primary_club / secondary_club
#   - any→All clears any value
#   - Deep-link with cross-type team_class self-corrects on mount
#   - Backend silent-no-op proof (curl-side)
#
# Subject anchors: G2/G3 (cross-type intl + club tier values, must == 34),
# G5 (MI club + full_member, must == 30 not 0).
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
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
echo "Test 1 · Type→Club auto-clears full_member"
ab open "$BASE/teams?gender=male&team_type=international&team_class=full_member&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'Club').click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "intl→club: team_class cleared" '""' "$v"
v=$(ab_eval "new URL(location.href).searchParams.get('team_type')")
assert_eq "intl→club: team_type updated" '"club"' "$v"
v=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
assert_eq "intl→club: FM toggle hidden" '"hidden"' "$v"
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Marquee\"]') ? 'visible' : 'hidden'")
assert_eq "intl→club: Primary tier button visible" '"visible"' "$v"

# ────────────────────────────────────────────
echo "Test 2 · Type→International auto-clears primary_club"
ab open "$BASE/teams?gender=male&team_type=club&team_class=primary_club&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'Intl').click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "club→intl: team_class cleared (was primary_club)" '""' "$v"
v=$(ab_eval "document.querySelector('.wisden-filter-group button[title*=\"Marquee\"]') ? 'visible' : 'hidden'")
assert_eq "club→intl: Primary button hidden" '"hidden"' "$v"

echo "Test 2b · Type→International auto-clears secondary_club"
ab open "$BASE/teams?gender=male&team_type=club&team_class=secondary_club&season_from=2024&season_to=2025"
settle
ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'Intl').click()" >/dev/null
sleep 1
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "club→intl: team_class cleared (was secondary_club)" '""' "$v"

# ────────────────────────────────────────────
echo "Test 3 · Type→All auto-clears any team_class value"
for val in full_member primary_club secondary_club; do
  case $val in
    full_member) tt=international ;;
    *)           tt=club ;;
  esac
  ab open "$BASE/teams?gender=male&team_type=$tt&team_class=$val"
  settle
  ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).filter(b => b.textContent.trim() === 'All' && b.previousElementSibling?.classList.contains('wisden-filter-label') && b.previousElementSibling?.textContent === 'Type')[0]?.click()" >/dev/null
  sleep 1
  v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
  assert_eq "Type→All: cleared $val" '""' "$v"
done

# ────────────────────────────────────────────
echo "Test 4 · Deep-link with cross-type value self-corrects on mount"
ab open "$BASE/teams?team_type=club&team_class=full_member"
settle
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "deep-link club + full_member self-corrects (cleared)" '""' "$v"

ab open "$BASE/teams?team_type=international&team_class=primary_club"
settle
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "deep-link intl + primary_club self-corrects (cleared)" '""' "$v"

ab open "$BASE/teams?team_type=international&team_class=secondary_club"
settle
v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
assert_eq "deep-link intl + secondary_club self-corrects (cleared)" '""' "$v"

# ────────────────────────────────────────────
echo "Test 5 · Backend silent-no-op proof (curl-direct)"
n_intl=$(curl -s "$API/api/v1/teams/India/summary?gender=male&team_type=international&season_from=2024&season_to=2025" | python3 -c 'import json,sys;d=json.load(sys.stdin);v=d.get("matches");print(v.get("value") if isinstance(v,dict) else v)')
n_intl_pri=$(curl -s "$API/api/v1/teams/India/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=primary_club" | python3 -c 'import json,sys;d=json.load(sys.stdin);v=d.get("matches");print(v.get("value") if isinstance(v,dict) else v)')
n_intl_sec=$(curl -s "$API/api/v1/teams/India/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=secondary_club" | python3 -c 'import json,sys;d=json.load(sys.stdin);v=d.get("matches");print(v.get("value") if isinstance(v,dict) else v)')
assert_eq "G2: intl+primary_club == intl unbounded ($n_intl)" "$n_intl" "$n_intl_pri"
assert_eq "G3: intl+secondary_club == intl unbounded ($n_intl)" "$n_intl" "$n_intl_sec"

n_mi=$(curl -s "$API/api/v1/teams/Mumbai%20Indians/summary?gender=male&team_type=club&season_from=2024&season_to=2025" | python3 -c 'import json,sys;d=json.load(sys.stdin);v=d.get("matches");print(v.get("value") if isinstance(v,dict) else v)')
n_mi_fm=$(curl -s "$API/api/v1/teams/Mumbai%20Indians/summary?gender=male&team_type=club&season_from=2024&season_to=2025&team_class=full_member" | python3 -c 'import json,sys;d=json.load(sys.stdin);v=d.get("matches");print(v.get("value") if isinstance(v,dict) else v)')
assert_eq "G5: club+full_member == club unbounded ($n_mi)" "$n_mi" "$n_mi_fm"

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
