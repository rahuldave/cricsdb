#!/bin/bash
# Player page — standalone match-result aux filter (won/lost/tied).
#
# Player-POV: the subject team is matchplayer.team per match, so "won"
# = matches the player's own side won, across every team they played
# for. Writes the `result` aux param; player /summary endpoints scope to
# it via filters.player_result_clause.
#
# Asserts:
#   1. /players/{id}/result-counts exists; wins/losses/tied SQL-anchored
#      at runtime (RED at HEAD: 404).
#   2. Batting /summary respects ?result=won — runs == SQL won-runs AND
#      strictly less than the all-results runs (RED at HEAD: result is
#      ignored, so won-runs == all-runs).
#   3. Fielding /summary catches also drop under ?result=won.
#   4. DOM: a "Result" pill row renders next to "Innings"; clicking Won
#      sets ?result=won in the URL.
#   5. The same Result row is mounted on the three discipline pages
#      (/batting, /bowling, /fielding) beside their InningToggle, but
#      ONLY for a selected player — the landing leaderboard view must
#      show Innings alone (RED at HEAD: discipline pages had no Result
#      row at all). Clicking Won writes ?result=won on each.
#
# Red-before-green via an isolated old-code worktree at HEAD.

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
val() { curl -sS "$1" | python3 -c "import sys,json;d=json.load(sys.stdin);v=d.get('$2');print(v.get('value') if isinstance(v,dict) else v)" 2>/dev/null; }

echo "=== /players · result filter ==="

# --- 1. result-counts endpoint + SQL anchors ---
CJSON=$(curl -sS "$API/api/v1/players/$PLAYER/result-counts?gender=male")
read -r api_w api_l api_t <<<"$(echo "$CJSON" | python3 -c "
import sys,json
try: d=json.load(sys.stdin); print(d['wins'],d['losses'],d['ties'])
except: print('ERR ERR ERR')")"
read -r sql_w sql_l sql_t <<<"$(sqlite3 "$DB" "
SELECT
  COUNT(DISTINCT CASE WHEN mm.outcome_winner=mp.team THEN mp.match_id END),
  COUNT(DISTINCT CASE WHEN mm.outcome_winner IS NOT NULL AND mm.outcome_winner!=mp.team THEN mp.match_id END),
  COUNT(DISTINCT CASE WHEN mm.outcome_winner IS NULL THEN mp.match_id END)
FROM matchplayer mp JOIN match mm ON mm.id=mp.match_id
WHERE mp.person_id='$PLAYER' AND mm.gender='male';" | tr '|' ' ')"
echo "  counts API w/l/t = $api_w/$api_l/$api_t | SQL = $sql_w/$sql_l/$sql_t"
if [ "$api_w" = "ERR" ]; then
  bad "result-counts endpoint missing"
else
  [ "$api_w" = "$sql_w" ] && [ "$api_l" = "$sql_l" ] && [ "$api_t" = "$sql_t" ] \
    && ok "result-counts wins/losses/tied match SQL ($api_w/$api_l/$api_t)" \
    || bad "result-counts $api_w/$api_l/$api_t != SQL $sql_w/$sql_l/$sql_t"
fi

# --- 2. batting summary respects ?result=won ---
all_runs=$(val "$API/api/v1/batters/$PLAYER/summary?gender=male" runs)
won_runs=$(val "$API/api/v1/batters/$PLAYER/summary?gender=male&result=won" runs)
sql_won=$(sqlite3 "$DB" "
SELECT SUM(d.runs_batter) FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id='$PLAYER'
WHERE d.batter_id='$PLAYER' AND m.gender='male' AND d.extras_wides=0 AND d.extras_noballs=0
  AND i.super_over=0 AND m.outcome_winner=mp.team;")
echo "  batting runs all=$all_runs won=$won_runs (SQL won=$sql_won)"
[ "$won_runs" = "$sql_won" ] && ok "batting won-runs match SQL ($won_runs)" || bad "won-runs $won_runs != SQL $sql_won"
if [ "$won_runs" != "$all_runs" ]; then ok "?result=won narrows batting runs ($all_runs -> $won_runs)"; else bad "?result=won did NOT change batting runs (still $all_runs)"; fi

# --- 3. fielding catches drop under ?result=won ---
all_c=$(val "$API/api/v1/fielders/$PLAYER/summary?gender=male" catches)
won_c=$(val "$API/api/v1/fielders/$PLAYER/summary?gender=male&result=won" catches)
echo "  fielding catches all=$all_c won=$won_c"
if [ -n "$won_c" ] && [ "$won_c" != "$all_c" ] && [ "$won_c" -lt "$all_c" ]; then
  ok "?result=won narrows fielding catches ($all_c -> $won_c)"
else
  bad "?result=won did not narrow fielding catches (all=$all_c won=$won_c)"
fi

# --- 3b. Per-discipline matches count is filter-specific. Fielding
#         matches comes from a separate matchplayer query that must ALSO
#         honour result (it bypassed _fielding_filter — regression guard). ---
fmatch_all=$(val "$API/api/v1/fielders/$PLAYER/summary?gender=male" matches)
fmatch_won=$(val "$API/api/v1/fielders/$PLAYER/summary?gender=male&result=won" matches)
echo "  fielding matches all=$fmatch_all won=$fmatch_won"
if [ -n "$fmatch_won" ] && [ "$fmatch_won" -lt "$fmatch_all" ]; then
  ok "?result=won narrows fielding MATCHES ($fmatch_all -> $fmatch_won)"
else
  bad "fielding matches not result-aware (all=$fmatch_all won=$fmatch_won)"
fi

# --- 4. DOM: Result row next to Innings; Won click sets ?result=won ---
ab open "$BASE/players?player=$PLAYER&gender=male"
ab wait --load networkidle
ab wait --text "Result"
ab wait 1200
# The player profile surfaces a match count in the "Matches in scope"
# block (per-discipline section heads dropped their own count in an
# earlier redesign — class wisden-player-section-matches no longer
# exists; this assertion tracks the current realization).
headmatch=$(ab_eval "(()=>{const e=document.querySelector('.wisden-overall-matches-value');return !!e&&/[0-9]/.test(e.textContent)})()")
[ "$headmatch" = "true" ] && ok "player profile shows a 'Matches in scope' count" || bad "no 'Matches in scope' count on player profile"
labels=$(ab_eval "JSON.stringify([...document.querySelectorAll('.wisden-aux-filter-row .wisden-filter-label')].map(e=>e.textContent))")
echo "  aux-row labels: $labels"
case "$labels" in
  *Innings*Result*) ok "Result row renders next to Innings" ;;
  *) bad "Result row not adjacent to Innings (got: $labels)" ;;
esac
ab_eval "(()=>{const b=[...document.querySelectorAll('.wisden-aux-filter-row button')].find(x=>x.textContent.trim().startsWith('Won'));b&&b.click();return 1})()" >/dev/null
ab wait 600
url_now=$(ab_eval "location.search")
case "$url_now" in
  *result=won*) ok "clicking Won sets ?result=won (url: $url_now)" ;;
  *) bad "Won click did not set result=won (url: $url_now)" ;;
esac

# --- 5. Result row mounted on the 3 discipline pages (spec §6.2) ---
# Profile view: Result beside Innings + clicking Won writes the URL.
# Landing view (no player): Innings alone — the result filter needs a
# subject player and must NOT leak onto the leaderboard.
for page in batting bowling fielding; do
  ab open "$BASE/$page?player=$PLAYER&gender=male"
  ab wait --load networkidle
  ab wait --text "Result"
  ab wait 1000
  dlabels=$(ab_eval "JSON.stringify([...document.querySelectorAll('.wisden-aux-filter-row .wisden-filter-label')].map(e=>e.textContent))")
  echo "  /$page aux labels (profile): $dlabels"
  case "$dlabels" in
    *Innings*Result*) ok "/$page: Result row renders next to Innings" ;;
    *) bad "/$page: Result row not adjacent to Innings (got: $dlabels)" ;;
  esac
  ab_eval "(()=>{const b=[...document.querySelectorAll('.wisden-aux-filter-row button')].find(x=>x.textContent.trim().startsWith('Won'));b&&b.click();return 1})()" >/dev/null
  ab wait 500
  durl=$(ab_eval "location.search")
  case "$durl" in
    *result=won*) ok "/$page: clicking Won sets ?result=won" ;;
    *) bad "/$page: Won click did not set result=won (url: $durl)" ;;
  esac

  ab open "$BASE/$page?gender=male"
  ab wait --load networkidle
  ab wait 800
  llabels=$(ab_eval "JSON.stringify([...document.querySelectorAll('.wisden-aux-filter-row .wisden-filter-label')].map(e=>e.textContent))")
  echo "  /$page aux labels (landing): $llabels"
  case "$llabels" in
    *Result*) bad "/$page landing: Result row leaked onto leaderboard (got: $llabels)" ;;
    *) ok "/$page landing: Innings only, no Result row ($llabels)" ;;
  esac
done

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then echo -e "Failures:$FAILS"; exit 1; fi
exit 0
