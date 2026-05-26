#!/bin/bash
# /teams/{team} Batting + Bowling — "By innings" table.
# Phase D of spec-series-precompute-followup.md — wires the
# /by-inning endpoints to bucketbaselinebatting + bucketbaselinebowling
# first_inn_* / second_inn_* columns. Asserts the rendered 1st/2nd
# innings row cells match SQL-derived expecteds, exercising both
# bucket path (tier-mode) and live path (filter_venue forces fallback).
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

# Read a cell from the "By innings" table by row label + column header.
inning_cell() {
  local row_label="$1" col_header="$2"
  ab_eval "(() => {
    const headers = Array.from(document.querySelectorAll('h2, h3'));
    const section = headers.find(h => h.textContent?.includes('By innings'));
    if (!section) return '';
    const table = section.parentElement?.querySelector('table');
    if (!table) return '';
    const cols = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent?.trim() || '');
    const colIdx = cols.indexOf('$col_header');
    if (colIdx < 0) return '';
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const row = rows.find(r => r.querySelector('th')?.textContent?.trim() === '$row_label');
    if (!row) return '';
    const tds = row.querySelectorAll('td');
    if (colIdx === 0) return tds[0]?.textContent?.trim() || '';
    return tds[colIdx - 1]?.textContent?.trim() || '';
  })()"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ── Scope 1 · India men's international all-time (bucket path) ────
echo "Test 1 · /teams/India Batting · men's international all-time (bucket path)"
ab open "$BASE/teams?team=India&gender=male&team_type=international&tab=Batting"
sleep 6

# SQL anchor for 1st innings wickets_lost (India batting in inning 0)
ind_wkts_1st=$(sql "
  SELECT COUNT(*)
  FROM wicket w
  JOIN delivery d ON d.id=w.delivery_id
  JOIN innings i ON i.id=d.innings_id
  JOIN match m ON m.id=i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND i.team='India' AND i.innings_number=0
    AND w.kind NOT IN ('retired hurt','retired not out');
")
ind_4s_1st=$(sql "
  SELECT SUM(CASE WHEN d.runs_batter=4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END)
  FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND i.team='India' AND i.innings_number=0;
")
ind_6s_2nd=$(sql "
  SELECT SUM(CASE WHEN d.runs_batter=6 THEN 1 ELSE 0 END)
  FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND i.team='India' AND i.innings_number=1;
")

actual=$(unq "$(inning_cell 'Batted first' 'Wkts')")
if [ "$actual" = "$ind_wkts_1st" ]; then ok "India batting 1st innings · Wkts (=$ind_wkts_1st)"; else bad "India batting 1st · Wkts — expected '$ind_wkts_1st', got '$actual'"; fi

actual=$(unq "$(inning_cell 'Batted first' '4s')")
if [ "$actual" = "$ind_4s_1st" ]; then ok "India batting 1st innings · 4s (=$ind_4s_1st)"; else bad "India batting 1st · 4s — expected '$ind_4s_1st', got '$actual'"; fi

actual=$(unq "$(inning_cell 'Batted second' '6s')")
if [ "$actual" = "$ind_6s_2nd" ]; then ok "India batting 2nd innings · 6s (=$ind_6s_2nd)"; else bad "India batting 2nd · 6s — expected '$ind_6s_2nd', got '$actual'"; fi

# ── Scope 2 · India men's international bowling (bucket path) ─────
echo "Test 2 · /teams/India Bowling · men's international all-time (bucket path)"
ab open "$BASE/teams?team=India&gender=male&team_type=international&tab=Bowling"
sleep 6

ind_bowl_wkts_2nd=$(sql "
  WITH mt AS (SELECT DISTINCT match_id FROM matchplayer WHERE team='India')
  SELECT COUNT(*)
  FROM wicket w
  JOIN delivery d ON d.id=w.delivery_id
  JOIN innings i ON i.id=d.innings_id
  JOIN match m ON m.id=i.match_id
  JOIN mt ON mt.match_id=m.id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND i.team != 'India' AND i.innings_number=1
    AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field','retired not out');
")
ind_bowl_4s_1st=$(sql "
  WITH mt AS (SELECT DISTINCT match_id FROM matchplayer WHERE team='India')
  SELECT SUM(CASE WHEN d.runs_batter=4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END)
  FROM delivery d JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id JOIN mt ON mt.match_id=m.id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND i.team != 'India' AND i.innings_number=0;
")

actual=$(unq "$(inning_cell 'Bowled second' 'Wickets')")
if [ "$actual" = "$ind_bowl_wkts_2nd" ]; then ok "India bowling 2nd innings · Wickets (=$ind_bowl_wkts_2nd)"; else bad "India bowling 2nd · Wickets — expected '$ind_bowl_wkts_2nd', got '$actual'"; fi

actual=$(unq "$(inning_cell 'Bowled first' '4s')")
if [ "$actual" = "$ind_bowl_4s_1st" ]; then ok "India bowling 1st innings · 4s (=$ind_bowl_4s_1st)"; else bad "India bowling 1st · 4s — expected '$ind_bowl_4s_1st', got '$actual'"; fi

# ── Scope 3 · India batting + filter_venue (live path) ────────────
# filter_venue forces is_precomputed_scope=False, exercising the live
# fallback after Phase D wiring.
echo "Test 3 · /teams/India Batting · filter_venue=Eden Gardens (live fallback)"
ab open "$BASE/teams?team=India&gender=male&team_type=international&filter_venue=Eden+Gardens&tab=Batting"
sleep 6

ind_wkts_1st_eden=$(sql "
  SELECT COUNT(*)
  FROM wicket w
  JOIN delivery d ON d.id=w.delivery_id
  JOIN innings i ON i.id=d.innings_id
  JOIN match m ON m.id=i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND m.venue='Eden Gardens'
    AND i.team='India' AND i.innings_number=0
    AND w.kind NOT IN ('retired hurt','retired not out');
")
actual=$(unq "$(inning_cell 'Batted first' 'Wkts')")
if [ "$actual" = "$ind_wkts_1st_eden" ]; then ok "India batting 1st @ Eden · Wkts (=$ind_wkts_1st_eden, live path)"; else bad "India batting 1st @ Eden · Wkts — expected '$ind_wkts_1st_eden', got '$actual'"; fi

# ── Scope 4 · India bowling + filter_venue (live path) ────────────
# Mirrors Scope 3 for the bowling-side _live aggregator. The bowling
# live path runs DISTINCT delivery + wicket scans with i.team != team
# narrowing — exercising it specifically here so a future refactor
# that only fixes the batting helper can't silently break bowling.
echo "Test 4 · /teams/India Bowling · filter_venue=Eden Gardens (live fallback)"
ab open "$BASE/teams?team=India&gender=male&team_type=international&filter_venue=Eden+Gardens&tab=Bowling"
sleep 6

ind_bowl_wkts_1st_eden=$(sql "
  WITH mt AS (SELECT DISTINCT match_id FROM matchplayer WHERE team='India')
  SELECT COUNT(*)
  FROM wicket w
  JOIN delivery d ON d.id=w.delivery_id
  JOIN innings i ON i.id=d.innings_id
  JOIN match m ON m.id=i.match_id
  JOIN mt ON mt.match_id=m.id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND m.venue='Eden Gardens'
    AND i.team != 'India' AND i.innings_number=0
    AND w.kind NOT IN ('run out','retired hurt','retired out','obstructing the field','retired not out');
")
actual=$(unq "$(inning_cell 'Bowled first' 'Wickets')")
if [ "$actual" = "$ind_bowl_wkts_1st_eden" ]; then
  ok "India bowling 1st @ Eden · Wickets (=$ind_bowl_wkts_1st_eden, live path)"
else
  bad "India bowling 1st @ Eden · Wickets — expected '$ind_bowl_wkts_1st_eden', got '$actual'"
fi

ind_bowl_4s_2nd_eden=$(sql "
  WITH mt AS (SELECT DISTINCT match_id FROM matchplayer WHERE team='India')
  SELECT SUM(CASE WHEN d.runs_batter=4 AND COALESCE(d.runs_non_boundary,0)=0 THEN 1 ELSE 0 END)
  FROM delivery d
  JOIN innings i ON i.id=d.innings_id
  JOIN match m ON m.id=i.match_id
  JOIN mt ON mt.match_id=m.id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.gender='male' AND m.team_type='international'
    AND m.venue='Eden Gardens'
    AND i.team != 'India' AND i.innings_number=1;
")
actual=$(unq "$(inning_cell 'Bowled second' '4s')")
if [ "$actual" = "$ind_bowl_4s_2nd_eden" ]; then
  ok "India bowling 2nd @ Eden · 4s (=$ind_bowl_4s_2nd_eden, live path)"
else
  bad "India bowling 2nd @ Eden · 4s — expected '$ind_bowl_4s_2nd_eden', got '$actual'"
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
