#!/bin/bash
# TossFilter control — reusable won/lost toss-outcome pill row
# (spec-player-baseline-aux-fallback.md §6.1, decision D2).
#
# The control is built now but its real mount surface is deferred, so it
# is exercised on the unlisted /dev/toss-filter test surface, which feeds
# it a player's toss counts from /players/{id}/result-counts.
#
# Asserts:
#   1. result-counts now returns toss_won / toss_lost, SQL-anchored
#      (RED at HEAD: fields absent -> null).
#   2. No "tied" toss bucket; toss_won + toss_lost == matches with a
#      recorded toss (NULL toss_winner excluded from both).
#   3. DOM: a "Toss" pill row renders on /dev/toss-filter with Won/Lost
#      counts matching the API (RED at HEAD: route + control absent).
#   4. Clicking "Won toss" writes ?toss_outcome=won in the URL.
#
# Red-before-green: at HEAD the result-counts toss fields, the
# /dev/toss-filter route and the TossFilter component all do not exist.

set -u
API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
DB="${DB:-cricket.db}"
PLAYER=ba607b88

PASS=0; FAIL=0; FAILS=""
ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

echo "=== /dev/toss-filter · toss control ==="

# --- 1. result-counts toss_won/toss_lost + SQL anchors ---
CJSON=$(curl -sS "$API/api/v1/players/$PLAYER/result-counts?gender=male")
read -r api_tw api_tl api_m <<<"$(echo "$CJSON" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin); print(d.get('toss_won','MISSING'),d.get('toss_lost','MISSING'),d.get('matches'))
except: print('ERR ERR ERR')")"
read -r sql_tw sql_tl <<<"$(sqlite3 "$DB" "
SELECT
  COUNT(DISTINCT CASE WHEN m.toss_winner=mp.team THEN mp.match_id END),
  COUNT(DISTINCT CASE WHEN m.toss_winner IS NOT NULL AND m.toss_winner!=mp.team THEN mp.match_id END)
FROM matchplayer mp JOIN match m ON m.id=mp.match_id
WHERE mp.person_id='$PLAYER' AND m.gender='male';" | tr '|' ' ')"
echo "  toss API won/lost = $api_tw/$api_tl | SQL = $sql_tw/$sql_tl | matches = $api_m"
if [ "$api_tw" = "MISSING" ] || [ "$api_tw" = "ERR" ]; then
  bad "result-counts toss_won/toss_lost missing"
else
  [ "$api_tw" = "$sql_tw" ] && [ "$api_tl" = "$sql_tl" ] \
    && ok "result-counts toss_won/toss_lost match SQL ($api_tw/$api_tl)" \
    || bad "toss counts $api_tw/$api_tl != SQL $sql_tw/$sql_tl"
fi

# --- 2. recorded-toss reconciliation (NULL excluded; no tied bucket) ---
sql_recorded=$(sqlite3 "$DB" "
SELECT COUNT(DISTINCT CASE WHEN m.toss_winner IS NOT NULL THEN mp.match_id END)
FROM matchplayer mp JOIN match m ON m.id=mp.match_id
WHERE mp.person_id='$PLAYER' AND m.gender='male';")
if [ "$api_tw" != "MISSING" ] && [ "$api_tw" != "ERR" ]; then
  sum=$((api_tw + api_tl))
  [ "$sum" = "$sql_recorded" ] \
    && ok "toss_won+toss_lost == recorded-toss matches ($sum)" \
    || bad "toss_won+toss_lost ($sum) != recorded-toss matches ($sql_recorded)"
fi

# --- 3. DOM: Toss pill row on the dev surface, counts match API ---
ab open "$BASE/dev/toss-filter?player=$PLAYER&gender=male"
ab wait --load networkidle
ab wait --text "Toss"
ab wait 1000
labels=$(ab_eval "JSON.stringify([...document.querySelectorAll('.wisden-filter-group .wisden-filter-label')].map(e=>e.textContent))")
echo "  filter labels: $labels"
case "$labels" in
  *Toss*) ok "Toss pill row renders on /dev/toss-filter" ;;
  *) bad "Toss pill row absent (got: $labels)" ;;
esac
# No "Tied" pill in the toss row.
hastied=$(ab_eval "[...document.querySelectorAll('.wisden-filter-group button')].some(b=>/Tied/.test(b.textContent))")
[ "$hastied" = "false" ] && ok "no Tied toss pill (toss has no tie)" || bad "unexpected Tied pill in toss row"
# Rendered Won/Lost counts equal the API.
# Number() so agent-browser returns a bare int (not a JSON-quoted string).
dom_w=$(ab_eval "(()=>{const b=[...document.querySelectorAll('.wisden-filter-group button')].find(x=>/^Won toss/.test(x.textContent.trim()));return b?Number(b.querySelector('.num').textContent.trim()):-1})()")
dom_l=$(ab_eval "(()=>{const b=[...document.querySelectorAll('.wisden-filter-group button')].find(x=>/^Lost toss/.test(x.textContent.trim()));return b?Number(b.querySelector('.num').textContent.trim()):-1})()")
echo "  DOM won/lost = $dom_w/$dom_l"
if [ "$dom_w" = "$api_tw" ] && [ "$dom_l" = "$api_tl" ]; then
  ok "rendered toss counts match API ($dom_w/$dom_l)"
else
  bad "rendered toss counts $dom_w/$dom_l != API $api_tw/$api_tl"
fi

# --- 4. clicking Won toss writes ?toss_outcome=won ---
ab_eval "(()=>{const b=[...document.querySelectorAll('.wisden-filter-group button')].find(x=>/^Won toss/.test(x.textContent.trim()));b&&b.click();return 1})()" >/dev/null
ab wait 600
url_now=$(ab_eval "location.search")
case "$url_now" in
  *toss_outcome=won*) ok "clicking Won toss sets ?toss_outcome=won (url: $url_now)" ;;
  *) bad "Won toss click did not set toss_outcome=won (url: $url_now)" ;;
esac

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then echo -e "Failures:$FAILS"; exit 1; fi
exit 0
