#!/bin/bash
# Batting "Dismissals" tab — three normalized player-vs-cohort
# distribution charts (mode of dismissal, by over, by phase).
#
# Asserts:
#   1. The three PerformanceVsCohort panels render with their titles
#      and the "Not Out" modality + "cohort at scope" legend.
#   2. Player /batters/{id}/dismissals now carries `innings` +
#      `not_outs`, and not_outs == innings − total_dismissals.
#   3. Player by_kind.caught + total_dismissals match a direct
#      sqlite3 count at the male scope (SQL-anchored at runtime).
#   4. The new cohort endpoint /scope/averages/batting/dismissals
#      exists and its denominator is BATTER-innings, not team-innings:
#      innings > total_dismissals (the bug that made not_outs=0).
#   5. All three cohort distributions sum to ~1.0:
#        mode  = Σ(by_kind)/innings + not_outs/innings
#        over  = Σ(by_over)/total_dismissals
#        phase = Σ(by_phase)/total_dismissals
#
# Red-before-green (HEAD~1): the cohort endpoint 404s (assert 4/5
# fail), the player endpoint has no innings/not_outs keys (assert 2
# fails), and the three chart titles are absent (assert 1 fails).

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

echo "=== /batting · Dismissals cohort charts ==="

PLAYER_JSON=$(curl -sS "$API/api/v1/batters/$PLAYER/dismissals?gender=male")
COHORT_JSON=$(curl -sS "$API/api/v1/scope/averages/batting/dismissals?gender=male")

# --- 2. Player innings + not_outs present and self-consistent. ---
read -r p_inn p_no p_tot <<<"$(echo "$PLAYER_JSON" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('innings','MISSING'), d.get('not_outs','MISSING'), d.get('total_dismissals','MISSING'))
")"
if [ "$p_inn" != "MISSING" ] && [ "$p_no" != "MISSING" ]; then
  ok "player dismissals carries innings ($p_inn) + not_outs ($p_no)"
  if [ "$p_no" -eq "$((p_inn - p_tot))" ]; then
    ok "player not_outs == innings − total_dismissals ($p_no == $p_inn − $p_tot)"
  else
    bad "player not_outs $p_no != innings−dismissals $((p_inn - p_tot))"
  fi
else
  bad "player dismissals missing innings/not_outs keys"
fi

# --- 3. SQL-anchored player by_kind.caught + total_dismissals. ---
sql_caught=$(sqlite3 "$DB" "SELECT COUNT(*) FROM wicket w JOIN delivery d ON d.id=w.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE w.player_out_id='$PLAYER' AND m.gender='male' AND w.kind='caught' AND w.kind NOT IN('retired hurt','retired out');")
sql_total=$(sqlite3 "$DB" "SELECT COUNT(*) FROM wicket w JOIN delivery d ON d.id=w.delivery_id JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id WHERE w.player_out_id='$PLAYER' AND m.gender='male' AND w.kind NOT IN('retired hurt','retired out');")
api_caught=$(echo "$PLAYER_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['by_kind'].get('caught',0))")
echo "  SQL caught=$sql_caught total=$sql_total  |  API caught=$api_caught total=$p_tot"
[ "$api_caught" = "$sql_caught" ] && ok "player caught matches SQL ($api_caught)" || bad "player caught $api_caught != SQL $sql_caught"
[ "$p_tot" = "$sql_total" ] && ok "player total_dismissals matches SQL ($p_tot)" || bad "player total $p_tot != SQL $sql_total"

# --- 4. Cohort endpoint exists with batter-innings denominator. ---
c_inn=$(echo "$COHORT_JSON" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('innings','ERR'))
except: print('ERR')")
c_tot=$(echo "$COHORT_JSON" | python3 -c "import sys,json
try: print(json.load(sys.stdin).get('total_dismissals','ERR'))
except: print('ERR')")
if [ "$c_inn" = "ERR" ] || [ "$c_inn" = "MISSING" ]; then
  bad "cohort endpoint /scope/averages/batting/dismissals not returning innings"
elif [ "$c_inn" -gt "$c_tot" ]; then
  ok "cohort denominator is batter-innings ($c_inn > $c_tot dismissals)"
else
  bad "cohort innings ($c_inn) <= dismissals ($c_tot) — wrong (team-innings) denominator"
fi

# --- 5. All three cohort distributions sum to ~1.0. ---
echo "$COHORT_JSON" | python3 -c "
import sys,json
d=json.load(sys.stdin)
inn=d['innings']; tot=d['total_dismissals']
mode=(sum(d['by_kind'].values())+d['not_outs'])/inn
over=sum(r['dismissals'] for r in d['by_over'])/tot
phase=sum(d['by_phase'].values())/tot
def chk(name,v):
    print(('OK' if abs(v-1.0)<1e-6 else 'BAD')+f' {name} sum={v:.6f}')
chk('mode',mode); chk('over',over); chk('phase',phase)
" | while read -r verdict rest; do
  if [ "$verdict" = "OK" ]; then ok "cohort $rest"; else bad "cohort $rest"; fi
done
# `while` runs in a subshell — re-derive PASS/FAIL contribution via a
# direct re-check so the counters in THIS shell stay accurate.
sums_ok=$(echo "$COHORT_JSON" | python3 -c "
import sys,json
d=json.load(sys.stdin)
inn=d['innings']; tot=d['total_dismissals']
mode=(sum(d['by_kind'].values())+d['not_outs'])/inn
over=sum(r['dismissals'] for r in d['by_over'])/tot
phase=sum(d['by_phase'].values())/tot
print('1' if all(abs(x-1.0)<1e-6 for x in (mode,over,phase)) else '0')")
if [ "$sums_ok" = "1" ]; then ok "all three cohort distributions sum to 1.0"; else bad "a cohort distribution does not sum to 1.0"; fi

# --- 1. Chart titles + modality label + legend render. ---
ab open "$BASE/batting?player=$PLAYER&gender=male&tab=Dismissals"
ab wait --load networkidle
ab wait --text "How you get out vs the cohort"
ab wait 1500
for needle in "How you get out vs the cohort" "When you get out, by over" "When you get out, by phase" "Not Out" "cohort at scope"; do
  has=$(ab_eval "document.body.innerText.includes('${needle}')")
  if [ "$has" = "true" ]; then ok "rendered — \"${needle}\""; else bad "missing — \"${needle}\""; fi
done

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
