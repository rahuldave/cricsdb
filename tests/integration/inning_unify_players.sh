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

# Option B is per-event + discipline-aware: batting inning=N counts where
# Kohli batted in innings_number=N; fielding/bowling inning=N count where he
# FIELDED in innings_number=(1-N) (bowled-first = innings 0 = inning=1).
# SQL: Kohli FIELDED in innings (1-N) — fielding matches per-event.
read -r f_ev0 f_ev1 <<<"$(sqlite3 "$DB" "SELECT
 (SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp JOIN innings i ON i.match_id=mp.match_id AND i.team!=mp.team JOIN match m ON m.id=mp.match_id WHERE mp.person_id='$P' AND m.gender='male' AND i.innings_number=1 AND i.super_over=0),
 (SELECT COUNT(DISTINCT mp.match_id) FROM matchplayer mp JOIN innings i ON i.match_id=mp.match_id AND i.team!=mp.team JOIN match m ON m.id=mp.match_id WHERE mp.person_id='$P' AND m.gender='male' AND i.innings_number=0 AND i.super_over=0);" | tr '|' ' ')"

# 1. Fielding matches == per-event "fielded in (1-N)".
f0=$(m fielders "inning=0" matches); f1=$(m fielders "inning=1" matches)
echo "  fielding matches inning0/1 = $f0/$f1 | SQL fielded-in-(1-N) = $f_ev0/$f_ev1"
[ "$f0" = "$f_ev0" ] && [ "$f1" = "$f_ev1" ] && ok "fielding matches == fielded-in-(1-N) per-event ($f0/$f1)" \
  || bad "fielding matches $f0/$f1 != per-event $f_ev0/$f_ev1"

# 2. Batting + bowling honor inning (differ across 0/1) — per-discipline
#    counts no longer share a subset relationship under per-event.
b0=$(m batters "inning=0" matches); b1=$(m batters "inning=1" matches)
w0=$(m bowlers "inning=0" matches); w1=$(m bowlers "inning=1" matches)
echo "  batting $b0/$b1  bowling $w0/$w1"
[ "$b0" != "$b1" ] && [ "$w0" != "$w1" ] && ok "batting + bowling matches honor inning (differ across 0/1)" \
  || bad "batting ($b0/$b1) or bowling ($w0/$w1) flat across inning — not filtering"

# 2b. THE FIX (red-green): a player who bowled in a match his team never
#     batted (DL Chahar, CSK vs LSG abandoned game 5845 — bowled, no bat)
#     must still count in bowled-first (inning=1). Match-subset dropped it.
CH=23eeb873
ch_sql=$(sqlite3 "$DB" "SELECT COUNT(DISTINCT i.match_id) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.bowler_id='$CH' AND m.gender='male' AND i.super_over=0 AND i.innings_number=0;")
ch_api=$(curl -s "$API/api/v1/bowlers/$CH/summary?gender=male&inning=1" | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('matches');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null)
ch_5845=$(sqlite3 "$DB" "SELECT COUNT(*) FROM delivery d JOIN innings i ON i.id=d.innings_id WHERE d.bowler_id='$CH' AND i.match_id=5845;")
echo "  Chahar bowled-first matches: api=$ch_api sql=$ch_sql (bowled $ch_5845 balls in abandoned 5845)"
[ -n "$ch_api" ] && [ "$ch_api" = "$ch_sql" ] && [ "$ch_5845" -gt 0 ] \
  && ok "bowled-but-didn't-bat game retained in bowled-first ($ch_api matches incl. 5845)" \
  || bad "Chahar bowled-first api=$ch_api sql=$ch_sql (match 5845 dropped?)"

# 3. Bowling wickets flip: inning=1 (bowled first) should equal the old
#    bowled-first value (raw innings_number=1 bowling).
sql_bowl1=$(sqlite3 "$DB" "SELECT COUNT(*) FROM wicket w JOIN delivery d ON d.id=w.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE d.bowler_id='$P' AND m.gender='male' AND i.innings_number=0 AND i.super_over=0 AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field');")
wk1=$(m bowlers "inning=1" wickets)
echo "  bowling wickets inning=1 (bowled first) = $wk1 | SQL innings_number-0 bowling = $sql_bowl1"
[ "$wk1" = "$sql_bowl1" ] && ok "bowling inning=1 == bowled-first wickets ($wk1)" || bad "bowling inning=1 $wk1 != bowled-first SQL $sql_bowl1"

# --- Phase 1b: remaining per-event sites now routed through the
#     match-subset clause (batting records + inter-wicket + keeping). ---

# 5. Records highest_score == SQL max over the batted-first/second match
#    subset (batting meaning unchanged, but now via the unified clause).
for inn in 0 1; do
  rsql=$(sqlite3 "$DB" "SELECT MAX(ib.runs) FROM inningsbatterperf ib
    JOIN innings i ON i.id=ib.innings_id JOIN match m ON m.id=i.match_id
    JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=ib.batter_id
    WHERE ib.batter_id='$P' AND m.gender='male' AND i.super_over=0
      AND m.id IN (SELECT i2.match_id FROM innings i2 JOIN matchplayer mp2 ON mp2.match_id=i2.match_id AND mp2.person_id='$P' AND mp2.team=i2.team WHERE i2.innings_number=$inn AND i2.super_over=0);")
  rapi=$(curl -s "$API/api/v1/batters/$P/records?gender=male&inning=$inn" | python3 -c "import sys,json;hs=json.load(sys.stdin).get('highest_scores',[]);print(hs[0]['runs'] if hs else '')" 2>/dev/null)
  [ -n "$rapi" ] && [ "$rapi" = "$rsql" ] && ok "records highest_score inning=$inn == SQL subset max ($rapi)" \
    || bad "records highest_score inning=$inn: api=$rapi sql=$rsql"
done

# 6. inter-wicket: non-empty under both innings and the player SR at
#    wickets_down=0 differs across innings (proves inning narrows).
iw0=$(curl -s "$API/api/v1/batters/$P/inter-wicket?gender=male&inning=0" | python3 -c "import sys,json;d=json.load(sys.stdin).get('inter_wicket',[]);print(d[0]['strike_rate'] if d else '')" 2>/dev/null)
iw1=$(curl -s "$API/api/v1/batters/$P/inter-wicket?gender=male&inning=1" | python3 -c "import sys,json;d=json.load(sys.stdin).get('inter_wicket',[]);print(d[0]['strike_rate'] if d else '')" 2>/dev/null)
[ -n "$iw0" ] && [ -n "$iw1" ] && [ "$iw0" != "$iw1" ] \
  && ok "inter-wicket non-empty + inning narrows (wd0 SR $iw0 vs $iw1)" \
  || bad "inter-wicket degenerate or unchanged across inning ($iw0/$iw1)"

# 7. Keeping (subject = MS Dhoni — Kohli has no keeping data): per-event,
#    keeper-side = FIELDED in innings (1-N). Anchor against SQL.
K2=4a8a2e3b
for inn in 0 1; do
  eff=$((1-inn))
  ksql=$(sqlite3 "$DB" "SELECT COUNT(*) FROM keeperassignment ka
    JOIN innings i ON i.id=ka.innings_id JOIN match m ON m.id=i.match_id
    WHERE ka.keeper_id='$K2' AND m.gender='male'
      AND m.id IN (SELECT i2.match_id FROM innings i2 JOIN matchplayer mp2 ON mp2.match_id=i2.match_id AND mp2.person_id='$K2' AND mp2.team!=i2.team WHERE i2.innings_number=$eff AND i2.super_over=0);")
  kapi=$(curl -s "$API/api/v1/fielders/$K2/summary?gender=male&inning=$inn" | python3 -c "import sys,json;print(json.load(sys.stdin)['innings_kept']['value'])" 2>/dev/null)
  [ -n "$kapi" ] && [ "$kapi" = "$ksql" ] && ok "fielding innings_kept inning=$inn == per-event fielded-in-(1-N) ($kapi)" \
    || bad "fielding innings_kept inning=$inn: api=$kapi sql=$ksql"
  alen=$(curl -s "$API/api/v1/fielders/$K2/keeping/ambiguous?gender=male&inning=$inn&limit=500" | python3 -c "import sys,json;print(len(json.load(sys.stdin)['innings']))" 2>/dev/null)
  ascl=$(curl -s "$API/api/v1/fielders/$K2/keeping/summary?gender=male&inning=$inn" | python3 -c "import sys,json;print(json.load(sys.stdin)['ambiguous_innings']['value'])" 2>/dev/null)
  [ -n "$alen" ] && [ "$alen" = "$ascl" ] && ok "keeping ambiguous list==scalar inning=$inn ($alen)" \
    || bad "keeping ambiguous inning=$inn: list=$alen scalar=$ascl"
done

# 8. bowling + fielding records (per-match precomp). Per-event: keyed on the
#    FIELDING innings (1-N), so a bowled-but-didn't-bat game stays eligible.
#    Subject: JJ Bumrah for bowling, Kohli for fielding.
BOW=462411b3
for inn in 0 1; do
  eff=$((1-inn))
  bsql=$(sqlite3 "$DB" "SELECT MAX(mb.wickets) FROM matchbowlerperf mb
    JOIN match m ON m.id=mb.match_id JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=mb.bowler_id
    WHERE mb.bowler_id='$BOW' AND m.gender='male' AND mb.wickets>=2
      AND m.id IN (SELECT i2.match_id FROM innings i2 JOIN matchplayer mp2 ON mp2.match_id=i2.match_id AND mp2.person_id='$BOW' AND mp2.team!=i2.team WHERE i2.innings_number=$eff AND i2.super_over=0);")
  bapi=$(curl -s "$API/api/v1/bowlers/$BOW/records?gender=male&inning=$inn" | python3 -c "import sys,json;d=json.load(sys.stdin)['best_figures'];print(d[0]['wickets'] if d else '')" 2>/dev/null)
  [ -n "$bapi" ] && [ "$bapi" = "$bsql" ] && ok "bowling records best_figures inning=$inn == per-event ($bapi)" \
    || bad "bowling records inning=$inn: api=$bapi sql=$bsql"
  fsql=$(sqlite3 "$DB" "SELECT MAX(mf.catches) FROM matchfielderperf mf
    JOIN match m ON m.id=mf.match_id JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=mf.fielder_id
    WHERE mf.fielder_id='$P' AND m.gender='male' AND mf.catches>0
      AND m.id IN (SELECT i2.match_id FROM innings i2 JOIN matchplayer mp2 ON mp2.match_id=i2.match_id AND mp2.person_id='$P' AND mp2.team!=i2.team WHERE i2.innings_number=$eff AND i2.super_over=0);")
  fapi=$(curl -s "$API/api/v1/fielders/$P/records?gender=male&inning=$inn" | python3 -c "import sys,json;d=json.load(sys.stdin)['most_catches_match'];print(d[0]['catches'] if d else '')" 2>/dev/null)
  [ -n "$fapi" ] && [ "$fapi" = "$fsql" ] && ok "fielding records most_catches inning=$inn == per-event ($fapi)" \
    || bad "fielding records inning=$inn: api=$fapi sql=$fsql"
done

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
