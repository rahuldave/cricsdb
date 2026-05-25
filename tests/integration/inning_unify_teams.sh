#!/bin/bash
# Inning unification (Option B) — TEAM per-discipline surfaces (U5/U6/U7).
# spec-inning-unify-option-b.md §8.3. inning=N = matches where :team
# BATTED in innings N — the SAME match subset for every discipline.
#
# The CSK bug this guards against: bowling/fielding inning=0 used to show
# the BOWLED-FIRST data (innings_number=0 fielding = 122 matches) while the
# scope strip said "batted first". After Option B, inning=0 bowling/fielding
# shows the team's work in matches it BATTED FIRST (144 matches) — the same
# subset batting uses. All disciplines agree on the match count.
#
# Asserts (DB-anchored at runtime):
#   1. bowling + fielding `matches` at inning=0/1 == SQL batted-in-N subset
#      (was bowled-first 122/144 before the flip).
#   2. batting `innings_batted` at inning=0/1 == same subset (UNCHANGED
#      meaning — batting was always batted-first).
#   3. All three disciplines agree: bowling matches == fielding matches ==
#      the subset (the Option-B unification guarantee).
#   4. Cohort scope_avg (bowling econ) is present and DIFFERS across
#      inning — the league baseline flips in lockstep with the team value
#      (chip↔baseline symmetry), not frozen.

set -u
API="${API:-http://localhost:8000}"
DB="${DB:-cricket.db}"
T="Chennai Super Kings"
TE=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$T'))")
PASS=0; FAIL=0; FAILS=""
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
# field value (envelope or scalar) from a summary endpoint
fv(){ curl -s "$API/api/v1/teams/$TE/$1/summary?gender=male&inning=$2" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('$3');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }
fsa(){ curl -s "$API/api/v1/teams/$TE/$1/summary?gender=male&inning=$2" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('$3');print(v.get('scope_avg') if isinstance(v,dict) else '')" 2>/dev/null; }

echo "=== /teams · inning unification (Option B) — CSK ==="

# SQL: matches where CSK batted in innings 0 / 1 (the unified subset).
read -r bf bs <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team='$T' AND i.super_over=0 AND m.gender='male' AND i.innings_number=0),
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team='$T' AND i.super_over=0 AND m.gender='male' AND i.innings_number=1);" | tr '|' ' ')"
echo "  SQL batted-in-0 / batted-in-1 subset = $bf / $bs"

# 1+3. bowling + fielding matches == subset (the flip + cross-discipline agreement).
bw0=$(fv bowling 0 matches); bw1=$(fv bowling 1 matches)
fd0=$(fv fielding 0 matches); fd1=$(fv fielding 1 matches)
echo "  bowling matches $bw0/$bw1   fielding matches $fd0/$fd1"
[ "$bw0" = "$bf" ] && [ "$bw1" = "$bs" ] && ok "bowling matches == batted-in-N subset ($bw0/$bw1) — flipped off bowled-first" \
  || bad "bowling matches $bw0/$bw1 != subset $bf/$bs (still bowled-first?)"
[ "$fd0" = "$bf" ] && [ "$fd1" = "$bs" ] && ok "fielding matches == batted-in-N subset ($fd0/$fd1)" \
  || bad "fielding matches $fd0/$fd1 != subset $bf/$bs"
[ "$bw0" = "$fd0" ] && [ "$bw1" = "$fd1" ] && ok "bowling matches == fielding matches (disciplines agree on the subset)" \
  || bad "bowling vs fielding match counts disagree ($bw0/$bw1 vs $fd0/$fd1) — inning not unified"

# 2. batting innings_batted == subset (unchanged meaning).
ib0=$(fv batting 0 innings_batted); ib1=$(fv batting 1 innings_batted)
echo "  batting innings_batted $ib0/$ib1"
[ "$ib0" = "$bf" ] && [ "$ib1" = "$bs" ] && ok "batting innings_batted == subset ($ib0/$ib1) — unchanged" \
  || bad "batting innings_batted $ib0/$ib1 != subset $bf/$bs"

# 4. Cohort scope_avg (bowling econ) present + differs across inning.
sa0=$(fsa bowling 0 economy); sa1=$(fsa bowling 1 economy)
echo "  bowling econ scope_avg inning0/1 = $sa0 / $sa1"
if [ -n "$sa0" ] && [ "$sa0" != "None" ] && [ "$sa0" != "$sa1" ]; then
  ok "cohort scope_avg flips with inning ($sa0 vs $sa1) — baseline tracks the team value"
else
  bad "cohort scope_avg frozen/empty across inning ($sa0/$sa1) — chip↔baseline asymmetry"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
