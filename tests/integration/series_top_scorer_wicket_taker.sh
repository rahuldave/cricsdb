#!/bin/bash
# /series Overview · Top scorer + Top wicket-taker tiles.
# Phase A of spec-series-precompute-followup.md — wires the tiles to
# playerscopestats in baseline regime. Anchors rendered tile (player +
# runs/wickets) against SQL-derived expecteds.
set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
DB="${DB:-cricket.db}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
sql()     { sqlite3 "$DB" "$1"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

stat_value() {
  local label="$1"
  ab_eval "(() => {
    const stats = Array.from(document.querySelectorAll('.wisden-stat'));
    const card = stats.find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label');
    if (!card) return '';
    return card.querySelector('.wisden-stat-value')?.textContent?.trim() || '';
  })()"
}
stat_sub() {
  local label="$1"
  ab_eval "(() => {
    const stats = Array.from(document.querySelectorAll('.wisden-stat'));
    const card = stats.find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === '$label');
    if (!card) return '';
    return card.querySelector('.wisden-stat-sub')?.textContent?.trim() || '';
  })()"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ── Scope 1 · IPL all-time ────────────────────────────────────────
echo "Test 1 · /series IPL all-time — top scorer + top wicket-taker"
ts=$(sql "
  SELECT person_id || '|' || SUM(runs) FROM playerscopestats
  WHERE tournament='Indian Premier League'
  GROUP BY person_id ORDER BY SUM(runs) DESC, person_id ASC LIMIT 1;
")
ts_pid=$(echo "$ts" | cut -d'|' -f1)
ts_runs=$(echo "$ts" | cut -d'|' -f2)
ts_name=$(sql "SELECT name FROM person WHERE id='$ts_pid';")
ts_runs_fmt=$(printf "%'d" "$ts_runs")

tw=$(sql "
  SELECT person_id || '|' || SUM(wickets) FROM playerscopestats
  WHERE tournament='Indian Premier League'
  GROUP BY person_id ORDER BY SUM(wickets) DESC, person_id ASC LIMIT 1;
")
tw_pid=$(echo "$tw" | cut -d'|' -f1)
tw_wkts=$(echo "$tw" | cut -d'|' -f2)
tw_name=$(sql "SELECT name FROM person WHERE id='$tw_pid';")

ab open "$BASE/series?tournament=Indian%20Premier%20League"
sleep 5

ts_val=$(unq "$(stat_value 'Top scorer')")
case "$ts_val" in
  *"$ts_name"*) ok "IPL all-time · top scorer name ($ts_name)" ;;
  *)            bad "IPL all-time · top scorer name — expected '$ts_name', got '$ts_val'" ;;
esac
ts_sub=$(unq "$(stat_sub 'Top scorer')")
case "$ts_sub" in
  *"$ts_runs_fmt runs"*) ok "IPL all-time · top scorer runs ($ts_runs_fmt)" ;;
  *)                     bad "IPL all-time · top scorer runs — expected '$ts_runs_fmt runs', got '$ts_sub'" ;;
esac

tw_val=$(unq "$(stat_value 'Top wicket-taker')")
case "$tw_val" in
  *"$tw_name"*) ok "IPL all-time · top wicket-taker name ($tw_name)" ;;
  *)            bad "IPL all-time · top wicket-taker name — expected '$tw_name', got '$tw_val'" ;;
esac
tw_sub=$(unq "$(stat_sub 'Top wicket-taker')")
case "$tw_sub" in
  *"$tw_wkts wickets"*) ok "IPL all-time · top wicket-taker wickets ($tw_wkts)" ;;
  *)                    bad "IPL all-time · top wicket-taker wickets — expected '$tw_wkts wickets', got '$tw_sub'" ;;
esac

# ── Scope 2 · Men's International all-time ────────────────────────
echo "Test 2 · /series Men's intl all-time — top scorer + top wicket-taker"
ts=$(sql "
  SELECT person_id || '|' || SUM(runs) FROM playerscopestats
  WHERE gender='male' AND team_type='international'
  GROUP BY person_id ORDER BY SUM(runs) DESC, person_id ASC LIMIT 1;
")
ts_pid=$(echo "$ts" | cut -d'|' -f1)
ts_runs=$(echo "$ts" | cut -d'|' -f2)
ts_name=$(sql "SELECT name FROM person WHERE id='$ts_pid';")
ts_runs_fmt=$(printf "%'d" "$ts_runs")

ab open "$BASE/series?gender=male&team_type=international"
sleep 5

ts_val=$(unq "$(stat_value 'Top scorer')")
case "$ts_val" in
  *"$ts_name"*) ok "Men's intl · top scorer name ($ts_name)" ;;
  *)            bad "Men's intl · top scorer name — expected '$ts_name', got '$ts_val'" ;;
esac
ts_sub=$(unq "$(stat_sub 'Top scorer')")
case "$ts_sub" in
  *"$ts_runs_fmt runs"*) ok "Men's intl · top scorer runs ($ts_runs_fmt)" ;;
  *)                     bad "Men's intl · top scorer runs — expected '$ts_runs_fmt runs', got '$ts_sub'" ;;
esac

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
