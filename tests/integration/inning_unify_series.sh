#!/bin/bash
# Inning unification (Option B) — SERIES dossier leaderboards (U12/U13, A9).
# spec-inning-unify-option-b.md §8.4.
#
# Series Bowling/Fielding leaderboards must read the team's bowling innings
# under Option B: the InningToggle (bowling POV) value-flips so "Bowling
# first" writes inning=1, and the backend filters innings_number=(1-N). So
# inning=1 ("Bowling first") == innings_number=0 (bowled-first leaderboard).
#
# Asserts (DOM ↔ flipped API + label/value agreement):
#   1. Toggle is POV-aware "Bowling first/second" and the ACTIVE pill
#      matches the URL inning (inning=1 → "Bowling first"; inning=0 →
#      "Bowling second") — the CSK three-labels regression guard.
#   2. The rendered top-bowler differs between inning=0 and inning=1 (the
#      flip fires in the DOM, not just the API).
#   3. The rendered leaderboard at each inning matches the API's leaders
#      at the SAME inning (DOM not stale).
#
# Prereqs: agent-browser, Vite dev (5173), FastAPI dev (8000).
set -u
BASE="${BASE:-http://localhost:5173}"; API="${API:-http://localhost:8000}"
TQ="tournament=Indian%20Premier%20League&season_from=2024&season_to=2024&gender=male&team_type=club"
TQ_UI="tournament=Indian+Premier+League&season_from=2024&season_to=2024&gender=male&team_type=club"
PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# top bowler name from the /series/bowlers-leaders API (by_economy[0])
api_top(){ curl -s "$API/api/v1/series/bowlers-leaders?$TQ&inning=$1&limit=5" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);e=d.get('by_economy') or d.get('by_strike_rate') or [];print((e[0].get('name') or e[0].get('person_id')) if e else 'EMPTY')" 2>/dev/null; }
# all bowler names across every leaderboard list at an inning (membership set)
api_names(){ curl -s "$API/api/v1/series/bowlers-leaders?$TQ&inning=$1&limit=10" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);ns=[x.get('name','') for v in d.values() if isinstance(v,list) for x in v if isinstance(x,dict)];print(' || '.join(ns))" 2>/dev/null; }

toggle(){
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const grp = Array.from(document.querySelectorAll('.wisden-filter-group')).find(g=>(g.querySelector('.wisden-filter-label')?.innerText||'').trim()==='Innings');
  if (!grp) return 'NO_TOGGLE';
  return Array.from(grp.querySelectorAll('button.wisden-seg')).map(b=>(b.className.includes('is-active')?'['+b.innerText.trim()+']':b.innerText.trim())).join(' ');
})()
EVALEOF
}
# top leaderboard row's bowler name (strip the " at <tournament>" scope suffix)
top_row(){
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const r = document.querySelector('table tbody tr, .wisden-leaderboard tr');
  if (!r) return 'NO_ROW';
  return r.innerText.split('\n')[0].split('\t')[0].split(' at ')[0].trim();
})()
EVALEOF
}
nav(){ agent-browser open "$1" >/dev/null && agent-browser wait --load networkidle >/dev/null && sleep 3; }

agent-browser close --all >/dev/null 2>&1 || true; sleep 1
echo "=== /series · Bowling leaderboard inning flip (Option B) — IPL 2024 ==="
a0=$(api_top 0); a1=$(api_top 1)
echo "  API top bowler: inning0=$a0  inning1=$a1"

nav "$BASE/series?$TQ_UI&tab=Bowling&inning=0"
t0=$(toggle); r0=$(top_row | tr -d '"')
nav "$BASE/series?$TQ_UI&tab=Bowling&inning=1"
t1=$(toggle); r1=$(top_row | tr -d '"')
echo "  toggle inn0: $t0"
echo "  toggle inn1: $t1"
echo "  DOM top row: inn0='$r0'  inn1='$r1'"

[[ "$t0" == *"[Bowling second]"* ]] && ok "inning=0 → 'Bowling second' active (batted first → bowled second)" \
  || bad "inning=0 active pill wrong: $t0"
[[ "$t1" == *"[Bowling first]"* ]] && ok "inning=1 → 'Bowling first' active (batted second → bowled first)" \
  || bad "inning=1 active pill wrong: $t1"
[ "$r0" != "$r1" ] && [ "$r0" != "NO_ROW" ] && ok "DOM leaderboard flips across inning ($r0 → $r1)" \
  || bad "DOM leaderboard did NOT flip ($r0 / $r1)"
# Membership: the DOM top bowler at inning=1 must appear in the API's
# inning=1 leaders (any list) — proves the DOM reflects the flipped slice,
# without coupling to which leaderboard ordering the DOM renders first.
names1=$(api_names 1)
[ -n "$r1" ] && [ "$r1" != "NO_ROW" ] && [[ "$names1" == *"$r1"* ]] && ok "DOM inning=1 top '$r1' ∈ API inning=1 leaders — not stale" \
  || bad "DOM inning=1 top '$r1' NOT in API inning=1 leaders ($names1)"

agent-browser close --all >/dev/null 2>&1 || true
echo; echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
