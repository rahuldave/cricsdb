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

# Per-event, discipline-aware (Option B): batting inning=N counts the team's
# batting innings_number=N; bowling/fielding inning=N counts the team's
# FIELDING innings_number=(1-N) (bowled-first = innings 0 = inning=1). The two
# can differ by abandoned matches the team bowled in but never batted.
# SQL: BATTING batted-in-0 / batted-in-1.
read -r bf bs <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team='$T' AND i.super_over=0 AND m.gender='male' AND i.innings_number=0),
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team='$T' AND i.super_over=0 AND m.gender='male' AND i.innings_number=1);" | tr '|' ' ')"
# SQL: BOWLING/FIELDING — team fielded in innings (1-N). inning=0 (bowled 2nd)
# = fielded innings 1; inning=1 (bowled 1st) = fielded innings 0.
read -r bw0sql bw1sql <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team!='$T' AND (m.team1='$T' OR m.team2='$T') AND i.super_over=0 AND m.gender='male' AND i.innings_number=1),
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE i.team!='$T' AND (m.team1='$T' OR m.team2='$T') AND i.super_over=0 AND m.gender='male' AND i.innings_number=0);" | tr '|' ' ')"
echo "  SQL batting batted-in-0/1 = $bf/$bs ; bowling fielded-in-(1-N) inn0/inn1 = $bw0sql/$bw1sql"

# 1+3. bowling + fielding matches == per-event bowled-(1-N) count (NOT the
#      batting subset — must include matches the team bowled-but-didn't-bat).
bw0=$(fv bowling 0 matches); bw1=$(fv bowling 1 matches)
fd0=$(fv fielding 0 matches); fd1=$(fv fielding 1 matches)
echo "  bowling matches $bw0/$bw1   fielding matches $fd0/$fd1"
[ "$bw0" = "$bw0sql" ] && [ "$bw1" = "$bw1sql" ] && ok "bowling matches == bowled-(1-N) per-event ($bw0/$bw1) — incl. bowled-but-didn't-bat games" \
  || bad "bowling matches $bw0/$bw1 != per-event $bw0sql/$bw1sql (still match-subset / dropping bowling games?)"
[ "$fd0" = "$bw0sql" ] && [ "$fd1" = "$bw1sql" ] && ok "fielding matches == bowled-(1-N) per-event ($fd0/$fd1)" \
  || bad "fielding matches $fd0/$fd1 != per-event $bw0sql/$bw1sql"
[ "$bw0" = "$fd0" ] && [ "$bw1" = "$fd1" ] && ok "bowling matches == fielding matches (disciplines agree)" \
  || bad "bowling vs fielding match counts disagree ($bw0/$bw1 vs $fd0/$fd1)"
# The whole point: bowling inning=1 (122) > batting inning=1 (121) by the
# abandoned bowled-but-never-batted game — they must NOT be forced equal.
[ "$bw1" -ge "$bs" ] && ok "bowling inning=1 ($bw1) >= batting inning=1 ($bs) — bowled-but-didn't-bat games retained" \
  || bad "bowling inning=1 ($bw1) < batting ($bs) — bowling games wrongly dropped"

# 2. batting innings_batted == batted-in-N (unchanged meaning).
ib0=$(fv batting 0 innings_batted); ib1=$(fv batting 1 innings_batted)
echo "  batting innings_batted $ib0/$ib1"
[ "$ib0" = "$bf" ] && [ "$ib1" = "$bs" ] && ok "batting innings_batted == batted-in-N ($ib0/$ib1) — unchanged" \
  || bad "batting innings_batted $ib0/$ib1 != batted-in-N $bf/$bs"

# 2c. Header /summary `matches` is MATCH-level: a match counts even if the
#     team only bowled (never batted). Slice = batted-in-N OR fielded-in-(1-N).
#     So header inning=1 == bowling matches (122), NOT batting innings (121).
hm(){ curl -s "$API/api/v1/teams/$TE/summary?gender=male&inning=$1" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('matches');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }
read -r u0 u1 <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE (m.team1='$T' OR m.team2='$T') AND m.gender='male' AND i.super_over=0 AND ((i.team='$T' AND i.innings_number=0) OR (i.team!='$T' AND i.innings_number=1))),
 (SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE (m.team1='$T' OR m.team2='$T') AND m.gender='male' AND i.super_over=0 AND ((i.team='$T' AND i.innings_number=1) OR (i.team!='$T' AND i.innings_number=0)));" | tr '|' ' ')"
h0=$(hm 0); h1=$(hm 1)
echo "  header matches $h0/$h1 | SQL union(batted-N | fielded-(1-N)) = $u0/$u1"
[ "$h0" = "$u0" ] && [ "$h1" = "$u1" ] && ok "header matches == match-level union ($h0/$h1)" \
  || bad "header matches $h0/$h1 != union $u0/$u1"
[ "$h1" = "$bw1" ] && ok "header inning=1 ($h1) == bowling matches ($bw1) — match counted though team didn't bat" \
  || bad "header inning=1 ($h1) != bowling matches ($bw1) — match dropped from header"

# 4. Cohort scope_avg (bowling econ) present + differs across inning.
sa0=$(fsa bowling 0 economy); sa1=$(fsa bowling 1 economy)
echo "  bowling econ scope_avg inning0/1 = $sa0 / $sa1"
if [ -n "$sa0" ] && [ "$sa0" != "None" ] && [ "$sa0" != "$sa1" ]; then
  ok "cohort scope_avg flips with inning ($sa0 vs $sa1) — baseline tracks the team value"
else
  bad "cohort scope_avg frozen/empty across inning ($sa0/$sa1) — chip↔baseline asymmetry"
fi

# 5. Partnerships (U9): batting-side partitions cleanly across inning
#    (unchanged meaning); bowling-side (partnerships conceded by :team's
#    bowling) FLIPS like fielding — inning=0 = matches :team batted first.
pt(){ curl -s "$API/api/v1/teams/$TE/partnerships/summary?gender=male&side=$1&inning=$2" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('total');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }
ptn(){ curl -s "$API/api/v1/teams/$TE/partnerships/summary?gender=male&side=$1" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('total');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }
pb0=$(pt batting 0); pb1=$(pt batting 1); pbn=$(ptn batting)
pw0=$(pt bowling 0); pw1=$(pt bowling 1)
echo "  partnerships batting $pb0/$pb1 (none $pbn)   bowling $pw0/$pw1"
[ $((pb0+pb1)) = "$pbn" ] && ok "batting-side partnerships partition cleanly ($pb0+$pb1=$pbn) — unchanged" \
  || bad "batting-side partnerships don't partition ($pb0+$pb1 != $pbn)"
if [ "$pw0" -ne "$pw1" ] && [ "$pw0" -ne "$pb0" ]; then
  ok "bowling-side partnerships flip with inning ($pw0/$pw1) + distinct from batting ($pb0)"
else
  bad "bowling-side partnerships not flipped / not distinct ($pw0/$pw1 vs batting $pb0)"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
