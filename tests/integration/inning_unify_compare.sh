#!/bin/bash
# Inning unification (Option B) — TEAMS · Compare tab (U11).
# spec-inning-unify-option-b.md §5.3 + §8.3.
#
# The bug this guards against (found 2026-05-25): the Compare tab's
# PRIMARY (left) column was built by primarySlotOf(), which copied only
# the FilterBar fields and DROPPED the `inning` aux — while peer slots
# inherited it via useCompareSlots.inheritedScope(). So a URL carrying
# ?inning=0 rendered the primary column at ALL innings (266 matches)
# beside a 1st-innings-only slot (150 matches) — an unfair comparison
# with disagreeing per-column scope strips.
#
# After the fix primarySlotOf carries `inning`, so BOTH columns (and the
# league-average column, which narrows per-event server-side) honor the
# carried-over inning. Per-slot overrides (compareN_inning) still win.
#
# Asserts (DOM vs inning-scoped team API, derived at runtime):
#   1. Primary column bowling wickets @inning=0 == /teams API @inning=0
#      (NOT the unfiltered total — the regression guard for the fix).
#   2. Slot column bowling wickets @inning=0 == its team API @inning=0.
#   3. Both per-column scope strips show "Innings: 1st".
#   4. Per-slot override: page inning=0 + compare2_inning=1 → primary
#      stays 1st while the slot flips to 2nd (independent resolution).
#   5. inning=0 primary differs from the unfiltered primary (proves the
#      filter actually narrowed the left column).
#
# Prereqs: agent-browser, Vite dev (5173), FastAPI dev (8000).
# Run: ./tests/integration/inning_unify_compare.sh
set -u

BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
T1="Chennai Super Kings"
T2="Mumbai Indians"
T1E=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$T1'))")
T2E=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$T2'))")

PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Bowling wickets for a team at a given inning, off the SAME team
# endpoint getTeamProfile() drives — the inning-scoped contract the grid
# must reproduce. inning_unify_teams.sh SQL-anchors this endpoint; here
# we anchor the GRID against it.
api_wk(){ curl -s "$API/api/v1/teams/$1/bowling/summary?gender=male&inning=$2" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['wickets']['value'])" 2>/dev/null; }
api_wk_all(){ curl -s "$API/api/v1/teams/$1/bowling/summary?gender=male" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['wickets']['value'])" 2>/dev/null; }

# Extract per-column {name, innStrip, wickets} from the rendered grid.
extract(){
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  return cols.map(col => {
    const strip = col.querySelector('.wisden-col-scope')?.innerText || '';
    const inn = strip.includes('Innings:') ? strip.split('Innings:')[1].trim().split('\n')[0] : '';
    const secs = Array.from(col.querySelectorAll('.wisden-player-section'));
    const bs = secs.find(s => (s.querySelector('.wisden-player-section-label')?.innerText||'').toUpperCase().includes('BOWL'));
    let wk = '';
    if (bs) {
      const r = Array.from(bs.querySelectorAll('.wisden-player-compact-row'))
        .find(r => (r.querySelector('dt')?.innerText||'').trim() === 'Wickets');
      if (r) wk = (r.querySelector('dd')?.innerText||'').trim().split('\n')[0].replace(/,/g,'');
    }
    return { name: col.querySelector('.wisden-compare-col-name')?.innerText?.trim() || '', inn, wk };
  });
})()
EVALEOF
}

navigate(){ agent-browser open "$1" >/dev/null && agent-browser wait --load networkidle >/dev/null && sleep 3; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

echo "=== /teams · Compare — inning unification (Option B) — CSK vs MI ==="

w1_0=$(api_wk "$T1E" 0); w2_0=$(api_wk "$T2E" 0); w1_all=$(api_wk_all "$T1E"); w2_1=$(api_wk "$T2E" 1)
echo "  API CSK bowling wkts: inning0=$w1_0 all=$w1_all | MI: inning0=$w2_0 inning1=$w2_1"

# ── 1+2+3+5. inning=0 carried into Compare — both columns narrow ──
navigate "$BASE/teams?team=$T1E&tab=Compare&inning=0&gender=male&compare2=$T2E"
J=$(extract 2>/dev/null)
P_NAME=$(echo "$J" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["name"])')
P_WK=$(echo "$J"   | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["wk"])')
P_INN=$(echo "$J"  | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["inn"])')
S_WK=$(echo "$J"   | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["wk"])')
S_INN=$(echo "$J"  | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["inn"])')
echo "  rendered: primary($P_NAME) wk=$P_WK inn=$P_INN ; slot wk=$S_WK inn=$S_INN"

[ "$P_WK" = "$w1_0" ] && ok "primary column honors inning=0 ($P_WK == API $w1_0)" \
  || bad "primary column wickets $P_WK != inning-scoped API $w1_0 (primarySlotOf dropping inning?)"
[ "$P_WK" != "$w1_all" ] && ok "primary inning=0 ($P_WK) != unfiltered ($w1_all) — left column actually narrowed" \
  || bad "primary inning=0 == unfiltered ($w1_all) — inning NOT applied to primary"
[ "$S_WK" = "$w2_0" ] && ok "slot column honors inning=0 ($S_WK == API $w2_0)" \
  || bad "slot column wickets $S_WK != inning-scoped API $w2_0"
[ "$P_INN" = "1st" ] && [ "$S_INN" = "1st" ] && ok "both scope strips show Innings: 1st (agree)" \
  || bad "scope strips disagree on innings (primary='$P_INN' slot='$S_INN')"

# ── 4. Per-slot override beats the page inning, independently ──
navigate "$BASE/teams?team=$T1E&tab=Compare&inning=0&gender=male&compare2=$T2E&compare2_inning=1"
J2=$(extract 2>/dev/null)
P2_WK=$(echo "$J2" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["wk"])')
P2_INN=$(echo "$J2"| python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[0]["inn"])')
S2_WK=$(echo "$J2" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["wk"])')
S2_INN=$(echo "$J2"| python3 -c 'import sys,json;print(json.loads(sys.stdin.read())[1]["inn"])')
echo "  override: primary wk=$P2_WK inn=$P2_INN ; slot wk=$S2_WK inn=$S2_INN"
[ "$P2_WK" = "$w1_0" ] && [ "$P2_INN" = "1st" ] && ok "primary keeps page inning=0 ($P2_WK, 1st) under slot override" \
  || bad "primary changed under slot override (wk=$P2_WK inn=$P2_INN, want $w1_0/1st)"
[ "$S2_WK" = "$w2_1" ] && [ "$S2_INN" = "2nd" ] && ok "slot override inning=1 wins ($S2_WK, 2nd)" \
  || bad "slot override not applied (wk=$S2_WK inn=$S2_INN, want $w2_1/2nd)"

agent-browser close --all >/dev/null 2>&1 || true
echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
