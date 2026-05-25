#!/bin/bash
# Inning unification (Option B) — player surfaces.
# spec-inning-unify-option-b.md. inning=0 = team batted first;
# inning=1 = batted second — the SAME match subset for every discipline.
# Bowling/fielding pages keep "Bowled first/second" labels but the
# VALUE flips: "Bowling first" pill → inning=1.
#
# Asserts (DB-anchored at runtime):
#   1. Fielding `matches` under inning=0/1 == SQL batted-first/second
#      counts (the match subset; was 397/397 ignoring inning before).
#   2. Batting + bowling matches are subsets of the same match sets
#      (<= fielding) and complement across inning=0/1.
#   3. Bowling stats FLIP: inning=1 (bowled first) > inning=0 wickets
#      reproduces the old bowled-first number.
#   4. DOM: on /bowling, the "Bowling first" pill is active at
#      inning=1 (value-flip), and the scope strip reads "bowled first".

set -u
API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
DB="${DB:-cricket.db}"
P=ba607b88
PASS=0; FAIL=0; FAILS=""
ab(){ agent-browser "$@" >/dev/null 2>&1; }
ok(){ PASS=$((PASS+1)); echo "  PASS: $1"; }
bad(){ FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
m(){ curl -s "$API/api/v1/$1/$P/summary?gender=male&$2" | python3 -c "import sys,json;print(json.load(sys.stdin)['$3']['value'])" 2>/dev/null; }

echo "=== /players · inning unification (Option B) ==="

# SQL: matches where Kohli's team batted in innings 0 / 1.
read -r sql_bf sql_bs <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp JOIN innings i ON i.match_id=mp.match_id AND i.team=mp.team JOIN match m ON m.id=mp.match_id WHERE mp.person_id='$P' AND m.gender='male' AND i.innings_number=0 AND i.super_over=0),
 (SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp JOIN innings i ON i.match_id=mp.match_id AND i.team=mp.team JOIN match m ON m.id=mp.match_id WHERE mp.person_id='$P' AND m.gender='male' AND i.innings_number=1 AND i.super_over=0);" | tr '|' ' ')"

# 1. Fielding matches == match-subset.
f0=$(m fielders "inning=0" matches); f1=$(m fielders "inning=1" matches)
echo "  fielding matches inning0/1 = $f0/$f1 | SQL batted-first/second = $sql_bf/$sql_bs"
[ "$f0" = "$sql_bf" ] && [ "$f1" = "$sql_bs" ] && ok "fielding matches == batted-first/second subset ($f0/$f1)" \
  || bad "fielding matches $f0/$f1 != SQL $sql_bf/$sql_bs (inning ignored?)"

# 2. Batting/bowling matches are subsets (<= fielding) + non-degenerate.
b0=$(m batters "inning=0" matches); b1=$(m batters "inning=1" matches)
w0=$(m bowlers "inning=0" matches); w1=$(m bowlers "inning=1" matches)
echo "  batting $b0/$b1  bowling $w0/$w1  (both must be <= fielding $f0/$f1)"
if [ "$b0" -le "$f0" ] && [ "$b1" -le "$f1" ] && [ "$w0" -le "$f0" ] && [ "$w1" -le "$f1" ]; then
  ok "batting + bowling matches are subsets of the same match sets"
else
  bad "a discipline's matches exceed the fielding (whole-match) subset — inning not unified"
fi

# 3. Bowling wickets flip: inning=1 (bowled first) should equal the old
#    bowled-first value (raw innings_number=1 bowling).
sql_bowl1=$(sqlite3 "$DB" "SELECT COUNT(*) FROM wicket w JOIN delivery d ON d.id=w.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.bowler_id='$P' AND m.gender='male' AND i.innings_number=0 AND i.super_over=0 AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field');")
wk1=$(m bowlers "inning=1" wickets)
echo "  bowling wickets inning=1 (bowled first) = $wk1 | SQL innings_number-0 bowling = $sql_bowl1"
[ "$wk1" = "$sql_bowl1" ] && ok "bowling inning=1 == bowled-first wickets ($wk1)" || bad "bowling inning=1 $wk1 != bowled-first SQL $sql_bowl1"

# 4. DOM value-flip + scope-strip POV on /bowling.
ab open "$BASE/bowling?player=$P&gender=male&inning=1"
ab wait --text "Bowling first"; ab wait 800
active=$(agent-browser eval "JSON.stringify([...document.querySelectorAll('.wisden-seg.is-active')].map(b=>b.textContent.trim()))" 2>/dev/null)
case "$active" in *"Bowling first"*) ok "inning=1 activates the 'Bowling first' pill (value-flip)";; *) bad "inning=1 active pill not 'Bowling first' (got $active)";; esac
strip=$(agent-browser eval "(document.body.innerText.match(/bowled (first|second)/i)||['none'])[0]" 2>/dev/null)
case "$strip" in *"bowled first"*) ok "scope strip reads 'bowled first' at inning=1";; *) bad "scope strip POV wrong at inning=1 (got $strip)";; esac

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -gt 0 ] && { echo -e "Failures:$FAILS"; exit 1; }
exit 0
