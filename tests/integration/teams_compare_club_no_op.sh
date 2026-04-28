#!/bin/bash
# v3 Compare tab — Anchor G (RCB + __avg__ + SRH on IPL 2025).
#
# Club mode → pill must be hidden, all numbers byte-identical to HEAD
# (defensive backend gate ensures team_class would be a no-op even if
# the URL accidentally carried it).
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab() { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }

settle() { sleep "${1:-2.5}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "Anchor G — RCB + __avg__ + SRH on IPL 2025"
ab open "$BASE/teams?team=Royal%20Challengers%20Bengaluru&compare1=__avg__&compare2=Sunrisers%20Hyderabad&gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2025&season_to=2025&tab=Compare"
settle 3

# Pill MUST be hidden on club
pill=$(ab_eval "document.querySelector('button[title*=\"ICC full-member\"]') ? 'visible' : 'hidden'")
[ "$pill" = '"hidden"' ] && ok "pill hidden on club" || bad "pill should be hidden on club, got: $pill"

# Status strip should NOT show full members chip
strip=$(ab_eval "Array.from(document.querySelectorAll('.wisden-scope-strip-seg')).map(s=>s.textContent).join(' | ')")
case "$strip" in
  *"full members"*) bad "status strip showed full members chip on club — got: $strip" ;;
  *) ok "status strip omits team_class chip on club" ;;
esac

# Three columns with exact match counts
result=$(ab_eval "(() => Array.from(document.querySelectorAll('.wisden-compare-col')).map(c => ({name: c.querySelector('.wisden-compare-col-name')?.textContent.trim(), matches: c.querySelector('.num')?.textContent.trim()})))()")
rcb=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if 'Royal' in c['name']][0]['matches'])")
avg=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if 'verage' in c['name']][0]['matches'])")
srh=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if 'Sunrisers' in c['name']][0]['matches'])")

[ "$rcb" = "15" ] && ok "RCB col: 15 matches" || bad "RCB col expected 15, got $rcb"
[ "$avg" = "74" ] && ok "IPL avg col: 74 matches" || bad "IPL avg col expected 74, got $avg"
[ "$srh" = "14" ] && ok "SRH col: 14 matches" || bad "SRH col expected 14, got $srh"

# Defensive gate proof: same URL with &team_class=full_member must
# strip team_class (autoclear effect) AND counts must stay 15/74/14.
echo
echo "Anchor G' — same URL with &team_class=full_member tacked on"
ab open "$BASE/teams?team=Royal%20Challengers%20Bengaluru&compare1=__avg__&compare2=Sunrisers%20Hyderabad&gender=male&team_type=club&tournament=Indian%20Premier%20League&season_from=2025&season_to=2025&team_class=full_member&tab=Compare"
settle 3

v=$(ab_eval "new URL(location.href).searchParams.get('team_class') || ''")
[ "$v" = '""' ] && ok "auto-clear stripped team_class" || bad "team_class should be cleared on club, got: $v"

result=$(ab_eval "(() => Array.from(document.querySelectorAll('.wisden-compare-col')).map(c => ({name: c.querySelector('.wisden-compare-col-name')?.textContent.trim(), matches: c.querySelector('.num')?.textContent.trim()})))()")
rcb=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print([c for c in d if 'Royal' in c['name']][0]['matches'])")
[ "$rcb" = "15" ] && ok "RCB col still 15 matches (gate noop)" || bad "RCB expected 15 (gate failure?), got $rcb"

echo
echo "────────────────────────────────────────"
echo "Passed: $PASS  Failed: $FAIL"
[ $FAIL -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
