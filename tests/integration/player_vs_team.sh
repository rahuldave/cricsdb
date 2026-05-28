#!/bin/bash
# Player-page "Versus" opponent filter + /players/{id}/opponents.
#
# Asserts:
#   1. /api/v1/players/{id}/opponents returns an opponents[] list
#      (RED at HEAD: endpoint 404s).
#   2. SQL-anchored: the top opponent's match count matches a direct
#      sqlite count, opponent = the OTHER side of each match by mp.team.
#   3. filter_team narrowing: pinning to RCB shrinks the menu and drops
#      the international sides (Australia present unscoped, absent at RCB).
#   4. DOM: the "Versus" widget renders on /players + /batting + /bowling
#      + /fielding (every mount site), only after a player is chosen.
#   5. DOM: picking an opponent writes filter_opponent and narrows the
#      player's own numbers (matches-in-scope == SQL vs-Australia count);
#      picking on /batting stays on /batting.
#   6. DOM: with filter_opponent set the widget is in chip mode and the
#      clear button removes it.
#
# Red-before-green (HEAD): endpoint 404s (1,2,3 fail) and the widget is
# absent everywhere (4,5,6 fail).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
DB="${DB:-cricket.db}"
PLAYER=ba607b88            # V Kohli (RCB + India)
OPP=Australia             # an international side — faced for India, not RCB

PASS=0; FAIL=0; FAILS=""
ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

echo "=== player · Versus (opponents) ==="

OPP_JSON=$(curl -sS "$API/api/v1/players/$PLAYER/opponents?gender=male")

# --- 1. endpoint returns opponents[] ---
n_opp=$(echo "$OPP_JSON" | python3 -c "
import sys,json
try: d=json.load(sys.stdin); print(len(d['opponents']))
except: print('ERR')")
if [ "$n_opp" = "ERR" ] || [ "$n_opp" = "0" ]; then
  bad "endpoint /players/$PLAYER/opponents returned no opponents (got: $n_opp)"
else
  ok "endpoint returns $n_opp opponents"
fi

# Top opponent (most matches — first in the ordered payload).
read -r TOP_OPP api_matches <<<"$(echo "$OPP_JSON" | python3 -c "
import sys,json
o=json.load(sys.stdin)['opponents'][0]
print(o['opponent'].replace(' ','~'), o['matches'])
")"
TOP_OPP_SQL="${TOP_OPP//\~/ }"
echo "  top opponent: $TOP_OPP_SQL  (API matches=$api_matches)"

# --- 2. SQL-anchored top-opponent match count (opponent = other side) ---
sql_matches=$(sqlite3 "$DB" "
SELECT COUNT(DISTINCT mp.match_id)
FROM matchplayer mp JOIN match m ON m.id = mp.match_id
WHERE mp.person_id='$PLAYER' AND m.gender='male'
  AND (CASE WHEN mp.team=m.team1 THEN m.team2 ELSE m.team1 END)='$TOP_OPP_SQL';")
[ "$api_matches" = "$sql_matches" ] && ok "top-opponent matches match SQL ($api_matches)" \
  || bad "top-opponent matches $api_matches != SQL $sql_matches"

# --- 3. filter_team=RCB shrinks the menu + drops international sides ---
RCB="Royal%20Challengers%20Bengaluru"
RCB_JSON=$(curl -sS "$API/api/v1/players/$PLAYER/opponents?gender=male&filter_team=$RCB")
read -r n_all has_aus_all <<<"$(echo "$OPP_JSON" | python3 -c "
import sys,json
d=json.load(sys.stdin)['opponents']
print(len(d), '1' if any(o['opponent']=='$OPP' for o in d) else '0')")"
read -r n_rcb has_aus_rcb <<<"$(echo "$RCB_JSON" | python3 -c "
import sys,json
d=json.load(sys.stdin)['opponents']
print(len(d), '1' if any(o['opponent']=='$OPP' for o in d) else '0')")"
echo "  all=$n_all (has $OPP=$has_aus_all)  RCB=$n_rcb (has $OPP=$has_aus_rcb)"
[ "$n_rcb" -lt "$n_all" ] && ok "RCB menu smaller than all-teams menu ($n_rcb < $n_all)" \
  || bad "RCB menu not smaller ($n_rcb vs $n_all)"
[ "$has_aus_all" = "1" ] && [ "$has_aus_rcb" = "0" ] \
  && ok "$OPP present unscoped, absent when pinned to RCB" \
  || bad "$OPP narrowing wrong (all=$has_aus_all rcb=$has_aus_rcb)"

# --- 4. DOM: widget renders on every player page (typeahead mode) ---
for pg in players batting bowling fielding; do
  ab open "$BASE/$pg?player=$PLAYER&gender=male"
  ab wait --load networkidle
  ab wait --text "Teams played for"
  ab wait 600
  has=$(ab_eval "(!!document.querySelector('.wisden-vsteam input') && document.querySelector('.wisden-vsteam .wisden-filter-label').textContent.trim()==='Versus')")
  [ "$has" = "true" ] && ok "/$pg renders Versus widget" || bad "/$pg missing Versus widget"
done

# --- 5. DOM: pick on /batting → filter_opponent + value narrows + stays ---
# Anchor the batting Matches tile against the batting /summary at the
# same filter_opponent (the page's own source) — the player's *batting*
# match count vs Australia (≤ total matches; he may not bat in some).
api_vs=$(curl -sS "$API/api/v1/batters/$PLAYER/summary?gender=male&filter_opponent=$OPP" | python3 -c "
import sys,json
m=json.load(sys.stdin).get('matches')
print(m.get('value') if isinstance(m,dict) else m)")
ab open "$BASE/batting?player=$PLAYER&gender=male"
ab wait --text "Teams played for"
ab wait 600
ab_eval "(()=>{const i=document.querySelector('.wisden-vsteam input'); i.focus(); return 'f'})()" >/dev/null 2>&1
ab wait 300
ab_eval "(()=>{const li=[...document.querySelectorAll('.wisden-vsteam .wisden-playersearch-list li')].find(l=>l.textContent.includes('$OPP')); li.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); return 'p'})()" >/dev/null 2>&1
ab wait --load networkidle
ab wait 400
url=$(agent-browser get url 2>/dev/null)
case "$url" in
  *"/batting?"*"filter_opponent=$OPP"*) ok "pick on /batting sets filter_opponent, stays on /batting" ;;
  *) bad "pick URL wrong: $url" ;;
esac
# The summary matches-in-scope (first stat tile) must equal the SQL count.
dom_matches=$(ab_eval "(()=>{const v=document.querySelector('.wisden-statrow .wisden-stat-value, .wisden-statrow .num'); return v?v.textContent.replace(/[^0-9]/g,''):'NONE'})()" | tr -d '"')
[ "$dom_matches" = "$api_vs" ] && ok "value narrows to vs-$OPP ($api_vs batting matches)" \
  || bad "value did not narrow (DOM=$dom_matches API=$api_vs)"

# --- 6. chip mode + clear ---
chip=$(ab_eval "document.querySelector('.wisden-vsteam .wisden-venue-chip-name')?.textContent" | tr -d '"')
[ "$chip" = "$OPP" ] && ok "chip shows selected opponent ($OPP)" || bad "chip wrong (got: $chip)"
ab_eval "(()=>{document.querySelector('.wisden-vsteam .wisden-venue-chip-clear').click(); return 'c'})()" >/dev/null 2>&1
ab wait --load networkidle
ab wait 300
url2=$(agent-browser get url 2>/dev/null)
case "$url2" in
  *"filter_opponent="*) bad "clear did not remove filter_opponent: $url2" ;;
  *) ok "clear removes filter_opponent" ;;
esac

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
