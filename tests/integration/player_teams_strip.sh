#!/bin/bash
# Player profile — "Teams played for" strip + /players/{id}/teams.
#
# Asserts:
#   1. /api/v1/players/{id}/teams returns a teams[] list (RED at HEAD:
#      endpoint 404s).
#   2. SQL-anchored at runtime: the top team's runs / wickets / catches
#      match direct sqlite counts using the canonical predicates
#      (runs exclude wides/no-balls + super-overs; wickets exclude
#      run-out/retired/obstructing; catches = caught + caught_and_bowled
#      non-substitute; all super_over=0), attributed by matchplayer.team.
#   3. Reconciliation: the strip's per-team runs == the team-filtered
#      batting /summary (filter_team) — proving the strip partitions the
#      page it links to.
#   4. Scope-respecting: narrowing to one closed season returns a
#      smaller, internally-consistent payload (no 5xx).
#   5. DOM: the strip renders "Teams played for", the team name, and a
#      Batting link whose href carries filter_team=<team>; the lead
#      "N matches @" link on /players points at the combined profile
#      scoped to that team.
#   6. DOM: the strip also mounts on /batting, /bowling, /fielding —
#      WITHOUT the per-discipline links — and its lead "N matches @"
#      link there points at THAT discipline scoped to the team (e.g. on
#      /batting it lands on /batting?...&filter_team=<team>, not back on
#      /players).
#
# Red-before-green (HEAD): the endpoint 404s (1,2,3 fail) and the strip
# is absent from the profile (5 fails). Section 6 is red until the strip
# is mounted on the discipline pages (strip-present assertions fail).

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

echo "=== /players · Teams played for ==="

TEAMS_JSON=$(curl -sS "$API/api/v1/players/$PLAYER/teams?gender=male")

# --- 1. endpoint returns teams[] ---
n_teams=$(echo "$TEAMS_JSON" | python3 -c "
import sys,json
try: d=json.load(sys.stdin); print(len(d['teams']))
except: print('ERR')")
if [ "$n_teams" = "ERR" ] || [ "$n_teams" = "0" ]; then
  bad "endpoint /players/$PLAYER/teams returned no teams (got: $n_teams)"
else
  ok "endpoint returns $n_teams teams"
fi

# Top team (by matches — first in the ordered payload).
read -r TOP_TEAM api_runs api_wkts api_catches <<<"$(echo "$TEAMS_JSON" | python3 -c "
import sys,json
t=json.load(sys.stdin)['teams'][0]
print(t['team'].replace(' ','~'), t['runs'], t['wickets'], t['catches'])
")"
TOP_TEAM_SQL="${TOP_TEAM//\~/ }"
echo "  top team: $TOP_TEAM_SQL  (API runs=$api_runs wkts=$api_wkts catches=$api_catches)"

# --- 2. SQL-anchored per-team totals (canonical predicates) ---
# All-ball runs (spec-batting-allball-runs-single-source.md §2): no legal gate on the runs sum.
sql_runs=$(sqlite3 "$DB" "
SELECT COALESCE(SUM(d.runs_batter),0)
FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=d.batter_id
WHERE d.batter_id='$PLAYER' AND m.gender='male'
  AND i.super_over=0 AND mp.team='$TOP_TEAM_SQL';")
sql_wkts=$(sqlite3 "$DB" "
SELECT COUNT(*)
FROM wicket w JOIN delivery d ON d.id=w.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=d.bowler_id
WHERE d.bowler_id='$PLAYER' AND m.gender='male' AND i.super_over=0 AND mp.team='$TOP_TEAM_SQL'
  AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field');")
sql_catches=$(sqlite3 "$DB" "
SELECT COUNT(*)
FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
JOIN matchplayer mp ON mp.match_id=m.id AND mp.person_id=fc.fielder_id
WHERE fc.fielder_id='$PLAYER' AND m.gender='male' AND i.super_over=0 AND mp.team='$TOP_TEAM_SQL'
  AND fc.kind IN ('caught','caught_and_bowled') AND COALESCE(fc.is_substitute,0)=0;")
echo "  SQL runs=$sql_runs wkts=$sql_wkts catches=$sql_catches"
[ "$api_runs" = "$sql_runs" ]       && ok "runs match SQL ($api_runs)"       || bad "runs $api_runs != SQL $sql_runs"
[ "$api_wkts" = "$sql_wkts" ]       && ok "wickets match SQL ($api_wkts)"    || bad "wickets $api_wkts != SQL $sql_wkts"
[ "$api_catches" = "$sql_catches" ] && ok "catches match SQL ($api_catches)" || bad "catches $api_catches != SQL $sql_catches"

# --- 3. Reconcile with the team-filtered batting /summary ---
TE=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote('$TOP_TEAM_SQL'))")
sum_runs=$(curl -sS "$API/api/v1/batters/$PLAYER/summary?gender=male&filter_team=$TE" | python3 -c "
import sys,json
r=json.load(sys.stdin).get('runs')
print(r.get('value') if isinstance(r,dict) else r)")
[ "$api_runs" = "$sum_runs" ] && ok "strip runs == filter_team batting summary ($api_runs)" \
  || bad "strip runs $api_runs != batting summary $sum_runs"

# --- 4. Scope-respecting: one closed season is smaller + consistent ---
season_ok=$(curl -sS "$API/api/v1/players/$PLAYER/teams?gender=male&season_from=2016&season_to=2016" | python3 -c "
import sys,json
try:
  d=json.load(sys.stdin)['teams']
  print('1' if all(t['runs']>=0 and t['matches']>0 for t in d) else '0')
except: print('ERR')")
[ "$season_ok" = "1" ] && ok "season-scoped payload internally consistent" \
  || bad "season-scoped payload bad (got: $season_ok)"

# --- 5. DOM: strip + team name + team-filtered Batting link ---
ab open "$BASE/players?player=$PLAYER&gender=male"
ab wait --load networkidle
ab wait --text "Teams played for"
ab wait 1200
for needle in "Teams played for" "$TOP_TEAM_SQL"; do
  has=$(ab_eval "document.body.innerText.includes('${needle}')")
  [ "$has" = "true" ] && ok "rendered — \"${needle}\"" || bad "missing — \"${needle}\""
done
# No redundant scope-echo subtitle under the "Teams played for" heading
# (SectionHeader's auto abbreviateScope subtitle is suppressed — the
# page SCOPE line + clearable scope box already carry it).
no_sub=$(ab_eval "!document.querySelector('.wisden-teams-strip .wisden-section-sub')")
[ "$no_sub" = "true" ] && ok "no redundant scope subtitle under heading" \
  || bad "scope-echo subtitle present under Teams-played-for heading"
href_ok=$(ab_eval "[...document.querySelectorAll('.wisden-team-links a')].some(a => a.getAttribute('href').includes('/batting') && a.getAttribute('href').includes('filter_team='))")
[ "$href_ok" = "true" ] && ok "Batting link carries filter_team in href" || bad "Batting link missing filter_team href"

lead_players=$(ab_eval "(()=>{const a=document.querySelector('.wisden-teams-strip a.wisden-team-matches'); if(!a) return 'NONE'; const h=a.getAttribute('href'); return (h.startsWith('/players?') && h.includes('filter_team='))})()")
[ "$lead_players" = "true" ] && ok "/players lead link → combined profile scoped to team" \
  || bad "/players lead link wrong (got: $lead_players)"

# --- 6. Strip mounts on the discipline pages, no discipline links,
#        discipline-scoped lead link ---
for disc in batting bowling fielding; do
  ab open "$BASE/$disc?player=$PLAYER&gender=male"
  ab wait --load networkidle
  ab wait --text "Teams played for"
  ab wait 800
  strip_present=$(ab_eval "(!!document.querySelector('.wisden-teams-strip') && document.body.innerText.includes('${TOP_TEAM_SQL}'))")
  [ "$strip_present" = "true" ] && ok "/$disc renders Teams strip ($TOP_TEAM_SQL)" \
    || bad "/$disc missing Teams strip"
  no_disc_links=$(ab_eval "document.querySelectorAll('.wisden-teams-strip .wisden-team-links').length === 0")
  [ "$no_disc_links" = "true" ] && ok "/$disc strip drops per-discipline links" \
    || bad "/$disc strip still shows per-discipline links"
  lead_ok=$(ab_eval "(()=>{const a=document.querySelector('.wisden-teams-strip a.wisden-team-matches'); if(!a) return 'NONE'; const h=a.getAttribute('href'); return (h.startsWith('/$disc?') && h.includes('filter_team='))})()")
  [ "$lead_ok" = "true" ] && ok "/$disc lead link → /$disc scoped to team" \
    || bad "/$disc lead link wrong (got: $lead_ok)"
done

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
