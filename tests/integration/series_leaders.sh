#!/bin/bash
# /series Batting / Bowling / Fielding · leader tables.
# Phase A parts 2-4 of spec-series-precompute-followup.md — these
# endpoints read from playerscopestats in tier-mode + precomputed
# regime, fall back to live SQL otherwise.
#
# Asserts the TOP ROW of each leader table matches SQL-derived
# expecteds across:
#   - tier-mode IPL all-time (bucket path: tournament URL not set →
#     is_tier=True, FilterBar carries the IPL narrowing through
#     baseline_where's tournament= clause).
#   - tournament-mode IPL all-time (live path: tournament URL param
#     set → is_tier=False).
#
# SQL anchors are pulled from playerscopestats (matches the bucket
# path's predicate) — equivalent to live SQL because the sanity
# test_bucket_baseline.py:check_*_roundtrip locks SUM-from-playerscopestats
# byte-identical to live SQL across 5 scopes.
set -u

BASE="${BASE:-http://localhost:5173}"
DB="${DB:-cricket.db}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
sql()     { sqlite3 "$DB" "$1"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

# Read first row of the DataTable under a SectionHeader matching the
# given title. Returns the text of cell N (0-indexed).
section_first_row_cell() {
  local title="$1" col_idx="$2"
  ab_eval "(() => {
    const heads = Array.from(document.querySelectorAll('h3, .wisden-section-title'));
    const h = heads.find(el => el.textContent.trim() === '$title');
    if (!h) return '';
    // Walk forward to find the next table (skip subtitle divs)
    let n = h.nextElementSibling;
    while (n && !n.querySelector('table')) n = n.nextElementSibling;
    if (!n) return '';
    const row = n.querySelector('tbody tr');
    const cells = row?.querySelectorAll('td');
    return cells?.[$col_idx]?.textContent?.trim() || '';
  })()"
}

agent-browser close --all >/dev/null 2>&1
sleep 1

# ── Batters ── /series Batting tab ────────────────────────────────
echo "Test 1 · /series Batting · IPL tier-mode (bucket path)"
ab open "$BASE/series?tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Batting"
sleep 6

# By runs — top batter
top_runs_pid=$(sql "
  SELECT person_id FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club'
  GROUP BY person_id ORDER BY SUM(runs) DESC, person_id ASC LIMIT 1;
")
top_runs_name=$(sql "SELECT name FROM person WHERE id='$top_runs_pid';")
top_runs=$(sql "
  SELECT SUM(runs) FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club' AND person_id='$top_runs_pid';
")
top_runs_fmt=$(printf "%'d" "$top_runs")

actual_name=$(unq "$(section_first_row_cell 'By runs scored' 0)")
case "$actual_name" in
  *"$top_runs_name"*) ok "Batters · by-runs top name = $top_runs_name" ;;
  *)                  bad "Batters · by-runs top name — expected '$top_runs_name', got '$actual_name'" ;;
esac
actual_runs=$(unq "$(section_first_row_cell 'By runs scored' 1)")
if [ "$actual_runs" = "$top_runs_fmt" ] || [ "$actual_runs" = "$top_runs" ]; then
  ok "Batters · by-runs top runs = $top_runs_fmt"
else
  bad "Batters · by-runs top runs — expected '$top_runs_fmt', got '$actual_runs'"
fi

# ── Bowlers ── /series Bowling tab ────────────────────────────────
echo "Test 2 · /series Bowling · IPL tier-mode (bucket path)"
ab open "$BASE/series?tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Bowling"
sleep 6

top_wkts_pid=$(sql "
  SELECT person_id FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club'
  GROUP BY person_id ORDER BY SUM(wickets) DESC, person_id ASC LIMIT 1;
")
top_wkts_name=$(sql "SELECT name FROM person WHERE id='$top_wkts_pid';")
top_wkts=$(sql "
  SELECT SUM(wickets) FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club' AND person_id='$top_wkts_pid';
")

actual_name=$(unq "$(section_first_row_cell 'By wickets taken' 0)")
case "$actual_name" in
  *"$top_wkts_name"*) ok "Bowlers · by-wickets top name = $top_wkts_name" ;;
  *)                  bad "Bowlers · by-wickets top name — expected '$top_wkts_name', got '$actual_name'" ;;
esac
actual_wkts=$(unq "$(section_first_row_cell 'By wickets taken' 1)")
if [ "$actual_wkts" = "$top_wkts" ]; then
  ok "Bowlers · by-wickets top wkts = $top_wkts"
else
  bad "Bowlers · by-wickets top wkts — expected '$top_wkts', got '$actual_wkts'"
fi

# ── Fielders ── /series Fielding tab ──────────────────────────────
echo "Test 3 · /series Fielding · IPL tier-mode (bucket path)"
ab open "$BASE/series?tournament=Indian%20Premier%20League&gender=male&team_type=club&tab=Fielding"
sleep 6

# Top by total dismissals (catches+stumpings+runouts). Convention 3:
# catches in playerscopestats already includes caught_and_bowled (the
# populate script writes the inclusive predicate).
top_disp_pid=$(sql "
  SELECT person_id FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club'
  GROUP BY person_id
  HAVING (SUM(catches) + SUM(stumpings) + SUM(runouts)) > 0
  ORDER BY (SUM(catches) + SUM(stumpings) + SUM(runouts)) DESC, person_id ASC LIMIT 1;
")
top_disp_name=$(sql "SELECT name FROM person WHERE id='$top_disp_pid';")
top_disp=$(sql "
  SELECT SUM(catches) + SUM(stumpings) + SUM(runouts) FROM playerscopestats
  WHERE tournament='Indian Premier League' AND gender='male' AND team_type='club' AND person_id='$top_disp_pid';
")

actual_name=$(unq "$(section_first_row_cell 'By dismissals (all)' 0)")
case "$actual_name" in
  *"$top_disp_name"*) ok "Fielders · by-dismissals top name = $top_disp_name" ;;
  *)                  bad "Fielders · by-dismissals top name — expected '$top_disp_name', got '$actual_name'" ;;
esac
actual_disp=$(unq "$(section_first_row_cell 'By dismissals (all)' 1)")
if [ "$actual_disp" = "$top_disp" ]; then
  ok "Fielders · by-dismissals top total = $top_disp"
else
  bad "Fielders · by-dismissals top total — expected '$top_disp', got '$actual_disp'"
fi

# ── Tier-mode all-cricket ── exercise pure bucket path ────────────
echo "Test 4 · /series Batting · tier-mode all-cricket (no tournament param)"
ab open "$BASE/series?tab=Batting"
sleep 6

all_top_runs_pid=$(sql "
  SELECT person_id FROM playerscopestats
  GROUP BY person_id ORDER BY SUM(runs) DESC, person_id ASC LIMIT 1;
")
all_top_runs_name=$(sql "SELECT name FROM person WHERE id='$all_top_runs_pid';")

actual_name=$(unq "$(section_first_row_cell 'By runs scored' 0)")
case "$actual_name" in
  *"$all_top_runs_name"*) ok "all-cricket · by-runs top name = $all_top_runs_name" ;;
  *)                      bad "all-cricket · by-runs top name — expected '$all_top_runs_name', got '$actual_name'" ;;
esac

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
