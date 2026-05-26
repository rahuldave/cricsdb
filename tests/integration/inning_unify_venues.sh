#!/bin/bash
# Inning unification (Option B) — VENUE dossier leaderboards (U14/U15, A10).
# spec-inning-unify-option-b.md §8.4.
#
# The Venue dossier Bowlers/Fielders tabs reuse the standalone
# /bowlers,/fielders/leaders endpoints with filter_venue. Under Option B
# those flip to the team's bowling innings (innings_number=1-N), and the
# bowling-POV InningToggle value-flips ("Bowling first" → inning=1).
#
# Asserts (DOM ↔ flipped API + label/value agreement) — mirror of
# inning_unify_series.sh for the venue dossier:
#   1. Toggle "Bowling first/second" + active pill matches URL inning.
#   2. DOM leaderboard flips across inning.
#   3. DOM inning=1 top bowler ∈ API inning=1 leaders (filter_venue).
#
# Prereqs: agent-browser, Vite dev (5173), FastAPI dev (8000).
set -u
BASE="${BASE:-http://localhost:5173}"; API="${API:-http://localhost:8000}"
VENUE="Wankhede Stadium"
VAPI=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$VENUE'))")
VUI=$(python3 -c "import urllib.parse;print(urllib.parse.quote_plus('$VENUE'))")
Q="filter_venue=$VAPI&gender=male&team_type=club"
PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_names(){ curl -s "$API/api/v1/bowlers/leaders?$Q&inning=$1&limit=10" \
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
echo "=== /venues · Bowlers leaderboard inning flip (Option B) — $VENUE ==="

nav "$BASE/venues?venue=$VUI&gender=male&team_type=club&tab=Bowlers&inning=0"
t0=$(toggle); r0=$(top_row | tr -d '"')
nav "$BASE/venues?venue=$VUI&gender=male&team_type=club&tab=Bowlers&inning=1"
t1=$(toggle); r1=$(top_row | tr -d '"')
echo "  toggle inn0: $t0"
echo "  toggle inn1: $t1"
echo "  DOM top: inn0='$r0' inn1='$r1'"

[[ "$t0" == *"[Bowling second]"* ]] && ok "inning=0 → 'Bowling second' active" || bad "inning=0 pill wrong: $t0"
[[ "$t1" == *"[Bowling first]"* ]]  && ok "inning=1 → 'Bowling first' active"  || bad "inning=1 pill wrong: $t1"
[ "$r0" != "$r1" ] && [ "$r0" != "NO_ROW" ] && ok "DOM leaderboard flips across inning ($r0 → $r1)" \
  || bad "DOM leaderboard did NOT flip ($r0 / $r1)"
names1=$(api_names 1)
[ -n "$r1" ] && [ "$r1" != "NO_ROW" ] && [[ "$names1" == *"$r1"* ]] && ok "DOM inning=1 top '$r1' ∈ API inning=1 leaders — not stale" \
  || bad "DOM inning=1 top '$r1' NOT in API inning=1 leaders ($names1)"

agent-browser close --all >/dev/null 2>&1 || true
echo; echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
