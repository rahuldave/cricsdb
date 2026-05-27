#!/bin/bash
# Player OWN values narrow by the toss_outcome aux param
# (spec-player-baseline-aux-fallback.md §7 / Phase 2, decision D12).
#
# player_toss_clause wired at every player_result_clause site (batting,
# bowling, fielding, keeping). URL-settable; no widget yet. This is the
# value-side mirror of player_result_filter.sh's ?result= assertions.
#
# Asserts (curl + SQL, no DOM — there is no toss widget yet):
#   1. Batting runs at ?toss_outcome=won / =lost == SQL won/lost-toss
#      runs exactly, and each is strictly less than the all-toss runs.
#   2. Bowling wickets, fielding catches, keeping dismissals each narrow
#      under ?toss_outcome=won (toss_won < all AND > 0).
#
# RED at HEAD: toss_outcome is parsed into AuxParams but nothing consumes
# it for player values, so the toss numbers == the all numbers (frozen).
# GREEN: they narrow and the batting anchor matches SQL.

set -u
API="${API:-http://localhost:8000}"
DB="${DB:-cricket.db}"
P=ba607b88        # V Kohli — batting/bowling/fielding
K=4a8a2e3b        # MS Dhoni — keeping

PASS=0; FAIL=0; FAILS=""
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
val() { curl -sS "$1" | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('$2');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }
narrows() { # name url-base field
  local name="$1" base="$2" f="$3"
  local a w; a=$(val "$base" "$f"); w=$(val "$base&toss_outcome=won" "$f")
  echo "  $name $f: all=$a toss_won=$w"
  if [ -n "$w" ] && [ "$w" != "None" ] && [ "$a" != "None" ] \
     && [ "$(python3 -c "print(1 if 0<$w<$a else 0)" 2>/dev/null)" = "1" ]; then
    ok "$name $f narrows under toss_outcome=won ($a -> $w)"
  else
    bad "$name $f did not narrow under toss (all=$a won=$w)"
  fi
}

echo "=== player OWN values · toss_outcome ==="

# --- 1. Batting runs SQL-anchored (won + lost) ---
all_runs=$(val "$API/api/v1/batters/$P/summary?gender=male" runs)
won_runs=$(val "$API/api/v1/batters/$P/summary?gender=male&toss_outcome=won" runs)
lost_runs=$(val "$API/api/v1/batters/$P/summary?gender=male&toss_outcome=lost" runs)
sql_won=$(sqlite3 "$DB" "
SELECT SUM(d.runs_batter) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id='$P'
WHERE d.batter_id='$P' AND m.gender='male' AND d.extras_wides=0 AND d.extras_noballs=0
  AND i.super_over=0 AND m.toss_winner=mp.team;")
sql_lost=$(sqlite3 "$DB" "
SELECT SUM(d.runs_batter) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id='$P'
WHERE d.batter_id='$P' AND m.gender='male' AND d.extras_wides=0 AND d.extras_noballs=0
  AND i.super_over=0 AND m.toss_winner IS NOT NULL AND m.toss_winner!=mp.team;")
echo "  batting runs all=$all_runs won=$won_runs lost=$lost_runs (SQL won=$sql_won lost=$sql_lost)"
[ "$won_runs" = "$sql_won" ]  && ok "batting won-toss runs match SQL ($won_runs)"  || bad "won-toss runs $won_runs != SQL $sql_won"
[ "$lost_runs" = "$sql_lost" ] && ok "batting lost-toss runs match SQL ($lost_runs)" || bad "lost-toss runs $lost_runs != SQL $sql_lost"
if [ "$won_runs" != "$all_runs" ]; then ok "?toss_outcome=won narrows batting runs ($all_runs -> $won_runs)"; else bad "?toss_outcome=won did NOT change batting runs (still $all_runs)"; fi

# --- 2. Other disciplines narrow under toss ---
narrows "bowling"  "$API/api/v1/bowlers/$P/summary?gender=male"        wickets
narrows "fielding" "$API/api/v1/fielders/$P/summary?gender=male"       catches
narrows "keeping"  "$API/api/v1/fielders/$K/keeping/summary?gender=male" dismissals_while_keeping

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then echo -e "Failures:$FAILS"; exit 1; fi
exit 0
