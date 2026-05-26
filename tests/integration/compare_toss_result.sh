#!/bin/bash
# Teams · Compare tab — toss_outcome + result aux (spec-compare-toss-result.md).
#
# Before this feature the Compare tab dropped toss_outcome/result on EVERY
# column (both team columns AND the league-average column), and the cohort
# endpoint no-oped them server-side. Now:
#   - every column carries the page-level toss/result (inherited),
#   - team columns narrow via the subject-team clause,
#   - the league-average column narrows per-row (cohort subject = i.team),
#     so the team-vs-league chips stay apples-to-apples.
#
# Asserts (DOM vs inning/aux-scoped team API + direction, at runtime):
#   1. toss=won  → primary + slot bowling wickets == their /teams API
#      @toss_outcome=won (NOT the unfiltered total). Strips show "Toss: won".
#   2. result=won → primary bowling wickets == API @result=won.
#   3. league-average column economy NARROWS under result and in the right
#      direction (won < none < lost — winners concede fewer runs). This is
#      the chip↔baseline-symmetry guard: the cohort that no-oped before.
#
# Prereqs: agent-browser, Vite dev (5173), FastAPI dev (8000).
# Run: ./tests/integration/compare_toss_result.sh
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
T1="Chennai Super Kings"; T2="Mumbai Indians"
T1E=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$T1'))")
T2E=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$T2'))")

PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_wk(){ curl -s "$API/api/v1/teams/$1/bowling/summary?gender=male&$2" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['wickets']['value'])" 2>/dev/null; }

# Per-column {name, strip, wk, econ} from the rendered grid.
extract(){
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  return cols.map(col => {
    const secs = Array.from(col.querySelectorAll('.wisden-player-section'));
    const bs = secs.find(s => (s.querySelector('.wisden-player-section-label')?.innerText||'').toUpperCase().includes('BOWL'));
    const cell = (label) => {
      if (!bs) return '';
      const r = Array.from(bs.querySelectorAll('.wisden-player-compact-row'))
        .find(r => (r.querySelector('dt')?.innerText||'').trim() === label);
      return r ? (r.querySelector('dd')?.innerText||'').trim().split('\n')[0].replace(/,/g,'') : '';
    };
    return {
      name: col.querySelector('.wisden-compare-col-name')?.innerText?.trim() || '',
      strip: (col.querySelector('.wisden-col-scope')?.innerText||'').replace(/\n/g,' '),
      wk: cell('Wickets'), econ: cell('Economy'),
    };
  });
})()
EVALEOF
}
nav(){ agent-browser open "$1" >/dev/null && agent-browser wait --load networkidle >/dev/null && sleep 3; }

agent-browser close --all >/dev/null 2>&1 || true; sleep 1
echo "=== /teams · Compare — toss/result aux — CSK vs MI ==="

# ── 1. toss_outcome=won ──
w1=$(api_wk "$T1E" "toss_outcome=won"); w2=$(api_wk "$T2E" "toss_outcome=won")
nav "$BASE/teams?team=$T1E&tab=Compare&toss_outcome=won&gender=male&compare2=$T2E"
J=$(extract 2>/dev/null)
PW=$(echo "$J"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["wk"])')
PS=$(echo "$J"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["strip"])')
SW=$(echo "$J"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["wk"])')
SS=$(echo "$J"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["strip"])')
echo "  toss=won  API CSK/MI wkts = $w1/$w2 ; rendered primary=$PW slot=$SW"
[ "$PW" = "$w1" ] && ok "primary narrows by toss=won ($PW == API $w1)" || bad "primary wk $PW != API $w1 (toss dropped on Compare?)"
[ "$SW" = "$w2" ] && ok "slot narrows by toss=won ($SW == API $w2)" || bad "slot wk $SW != API $w2"
[[ "$PS" == *"Toss: won"* ]] && [[ "$SS" == *"Toss: won"* ]] && ok "both scope strips show Toss: won" || bad "strips missing Toss: won (primary='$PS' slot='$SS')"

# ── 2. result=won ──
r1=$(api_wk "$T1E" "result=won")
nav "$BASE/teams?team=$T1E&tab=Compare&result=won&gender=male&compare2=$T2E"
J2=$(extract 2>/dev/null)
P2W=$(echo "$J2"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["wk"])')
P2S=$(echo "$J2"|python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["strip"])')
echo "  result=won API CSK wkts = $r1 ; rendered primary=$P2W"
[ "$P2W" = "$r1" ] && ok "primary narrows by result=won ($P2W == API $r1)" || bad "primary wk $P2W != API $r1"
[[ "$P2S" == *"Result: won"* ]] && ok "scope strip shows Result: won" || bad "strip missing Result: won ('$P2S')"

# ── 3. league-average column narrows + correct direction ──
avg_econ(){
  nav "$BASE/teams?team=$T1E&tab=Compare&$1&gender=male&compare1=__avg__"
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  const avg = cols.find(c => (c.querySelector('.wisden-compare-col-name')?.innerText||'').includes('average'));
  if (!avg) return '';
  const secs = Array.from(avg.querySelectorAll('.wisden-player-section'));
  const bs = secs.find(s => (s.querySelector('.wisden-player-section-label')?.innerText||'').toUpperCase().includes('BOWL'));
  const r = bs && Array.from(bs.querySelectorAll('.wisden-player-compact-row')).find(r=>(r.querySelector('dt')?.innerText||'').trim()==='Economy');
  return r ? (r.querySelector('dd')?.innerText||'').trim().split('\n')[0] : '';
})()
EVALEOF
}
# agent-browser eval serializes the string result with surrounding quotes — strip them.
en=$(avg_econ "" | tr -d '"'); ew=$(avg_econ "result=won" | tr -d '"'); el=$(avg_econ "result=lost" | tr -d '"')
echo "  league-avg econ: none=$en won=$ew lost=$el"
if [ -n "$en" ] && [ "$ew" != "$en" ] && [ "$el" != "$en" ]; then
  ok "league-avg econ narrows with result ($en → won $ew / lost $el) — cohort no longer no-ops"
else
  bad "league-avg econ frozen across result ($en/$ew/$el) — chip↔baseline asymmetry"
fi
if python3 -c "import sys;sys.exit(0 if float('$ew')<float('$en')<float('$el') else 1)" 2>/dev/null; then
  ok "direction correct: won ($ew) < none ($en) < lost ($el) — winners concede fewer runs"
else
  bad "direction wrong: expected won<none<lost, got $ew/$en/$el"
fi

agent-browser close --all >/dev/null 2>&1 || true
echo; echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
