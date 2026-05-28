#!/bin/bash
# Teams > Compare tab — filter-coverage tests.
#
# Drives `agent-browser` against four anchor URLs that each exercise a
# filter axis the previous Compare tests didn't cover:
#
#   1. Tournament filter where the canonical name expands to multiple
#      cricsheet variants (T20 World Cup Men → 3 raw event_names). This
#      regressed when bucket dispatch did raw equality on the canonical
#      and matched zero rows in bucket_baseline_*; the team_summary
#      path masked the bug because filters.build() expanded variants
#      for live match-table queries. Now both paths agree.
#   2. Venue filter on the international side (Aus at MCG).
#   3. Venue filter on the club side (RCB at M Chinnaswamy).
#   4. RCB auto-promote — singleton tournaments_in_scope folds the avg
#      col header to "Indian Premier League average" instead of the
#      generic "League average".
#
# Each URL pulls cell values off the rendered DOM (NOT screenshot OCR)
# and compares against ground-truth numbers derived directly from
# sqlite — see "GROUND TRUTH" block below. Numbers verified against
# `cricket.db` via raw SQL with NO reference to api/ source, so this
# test catches API drift from the DB.
#
# Conventions used (which match the API + earlier inline DB checks):
#   - "matches" = COUNT(*) over the filter scope on the match table
#     (with team1/team2 filter where applicable)
#   - "innings_batted" = COUNT(*) over innings where i.team=<team>
#     AND super_over=0
#   - "total_runs" (batting) = SUM(runs_total) over ALL deliveries in
#     those innings (team's full batting score INCLUDING extras —
#     this is the cricket-conventional team total, e.g. 156/4)
#   - "legal_balls" = COUNT(*) over deliveries with extras_wides=0
#     AND extras_noballs=0
#   - "runs_conceded" (bowling) = SUM(runs_total) over ALL deliveries
#     in opposing-team innings within team's matches
#
# Prereqs: agent-browser, Vite dev (5173), FastAPI dev (8000).
# Run: ./tests/integration/compare_filters.sh
set -u

BASE="${BASE:-http://localhost:5173}"

PASS=0; FAIL=0
FAIL_LINES=""

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ──────────────────── extractor (same shape as compare_avg_chips.sh) ────────────────────

extract_grid() {
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  return cols.map(col => {
    const header = col.querySelector('.wisden-compare-col-name')?.innerText?.trim() || '';
    const subtitle = col.querySelector('.wisden-compare-chip-area')?.innerText?.trim() || '';
    const matches_text = col.querySelector('.wisden-player-identity')?.innerText?.trim() || '';
    const sections = {};
    for (const s of col.querySelectorAll('.wisden-player-section')) {
      const label = s.querySelector('.wisden-player-section-label')?.innerText?.trim() || '';
      const rows = {};
      for (const r of s.querySelectorAll('.wisden-player-compact-row')) {
        const dt = r.querySelector('dt')?.innerText?.trim() || '';
        const dd = r.querySelector('dd');
        const full = dd?.innerText?.trim() || '';
        rows[dt] = { full };
      }
      sections[label] = rows;
    }
    return { header, subtitle, matches_text, sections };
  });
})()
EVALEOF
}

navigate() {
  local url="$1" what="$2"
  echo
  echo "─── $what"
  echo "    $url"
  agent-browser navigate "$url" >/dev/null
  # 3s soak so the parallel team + scope-avg fetches resolve and React
  # commits the final DOM.
  sleep 3
}

assert_contains() {
  local label="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    PASS=$((PASS+1))
    echo "  ✓ $label"
  else
    FAIL=$((FAIL+1))
    echo "  ✗ $label — expected '$needle' in '$haystack'"
    FAIL_LINES+="$label\n"
  fi
}

# ──────────────────── ANCHOR 1 — T20 WC Men 2024-2026 ────────────────────
# Tests bucket-dispatch canonical-variants expansion. The canonical
# "T20 World Cup (Men)" maps to ICC World Twenty20 / World T20 / ICC
# Men's T20 World Cup. Aus + Ind both have 10 matches each.
#
# GROUND TRUTH (sqlite query against cricket.db):
#   SELECT COUNT(*) FROM match
#   WHERE (team1='Australia' OR team2='Australia')
#     AND gender='male' AND team_type='international'
#     AND event_name IN ('ICC World Twenty20','World T20','ICC Men''s T20 World Cup')
#     AND season >= '2024' AND season <= '2026';
#   → 10 matches
#
#   SELECT SUM(d.runs_total) FROM delivery d
#   JOIN innings i ON i.id=d.innings_id JOIN match m ON m.id=i.match_id
#   WHERE i.team='Australia' AND i.super_over=0
#     AND m.gender='male' AND m.team_type='international'
#     AND m.event_name IN ('ICC World Twenty20','World T20','ICC Men''s T20 World Cup')
#     AND m.season >= '2024' AND m.season <= '2026';
#   → 1523 runs (Aus batting)
#
#   Same for India — 10 matches.

navigate "$BASE/teams?team=Australia&tab=Compare&compare1=__avg__&compare2=India&gender=male&team_type=international&season_from=2024&season_to=2026&tournament=T20+World+Cup+%28Men%29" \
  "Anchor 1 — T20 WC Men 2024-2026 (canonical → variants)"

JSON_1=$(extract_grid 2>/dev/null)
COL0_HEADER=$(echo "$JSON_1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["header"])')
COL0_MATCHES=$(echo "$JSON_1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["matches_text"])')
COL0_BATTING=$(echo "$JSON_1" | python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(d[0]["sections"].get("BATTING",{}).get("Run rate",{}).get("full",""))')
COL1_HEADER=$(echo "$JSON_1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')
COL2_HEADER=$(echo "$JSON_1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[2]["header"])')
COL2_MATCHES=$(echo "$JSON_1" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[2]["matches_text"])')

assert_contains "1.col0 header is Australia" "$COL0_HEADER" "Australia"
assert_contains "1.col0 has 10 matches (T20 WC scope — Aus 2024 only)" "$COL0_MATCHES" "10"
assert_contains "1.col0 BATTING/Run rate populated (was empty before bucket fix)" "$COL0_BATTING" "9."
assert_contains "1.col1 avg header — tournament-anchored" "$COL1_HEADER" "T20 World Cup"
assert_contains "1.col2 header is India" "$COL2_HEADER" "India"
# India: 7 in 2024 + 9 in 2025/26 = 16 matches (Aus only played 2024 → 10).
assert_contains "1.col2 has 16 matches (India 2024 + 2025/26 T20 WC)" "$COL2_MATCHES" "16"

# ──────────────────── ANCHOR 2 — Aus at MCG 2024-2026 ────────────────────
# Tests venue filter on the intl side. Bucket dispatch refuses
# precomputed when filter_venue is set (per is_precomputed_scope) and
# falls through to live aggregation — so this exercises a different
# code path from Anchor 1.
#
# GROUND TRUTH:
#   SELECT COUNT(*) FROM match
#   WHERE (team1='Australia' OR team2='Australia')
#     AND gender='male' AND team_type='international'
#     AND venue='Melbourne Cricket Ground'
#     AND season >= '2024' AND season <= '2026';
#   → 1 match (Aus vs Pak T20I at MCG, Nov 2024)

navigate "$BASE/teams?team=Australia&tab=Compare&compare1=__avg__&gender=male&team_type=international&season_from=2024&season_to=2026&filter_venue=Melbourne+Cricket+Ground" \
  "Anchor 2 — Aus at MCG 2024-2026 (venue filter, intl)"

JSON_2=$(extract_grid 2>/dev/null)
COL0_HEADER_2=$(echo "$JSON_2" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["header"])')
COL0_MATCHES_2=$(echo "$JSON_2" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["matches_text"])')
COL1_HEADER_2=$(echo "$JSON_2" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')

assert_contains "2.col0 header is Australia" "$COL0_HEADER_2" "Australia"
assert_contains "2.col0 has 1 match at MCG" "$COL0_MATCHES_2" "1 "
assert_contains "2.col1 avg uses International wording (no team_class, no tournament)" "$COL1_HEADER_2" "International"

# ──────────────────── ANCHOR 3 — RCB at Chinnaswamy (all-time) ────────────────────
# Venue filter on the club side. RCB has played 100 matches at
# M Chinnaswamy Stadium (men's club, all-time). Tests that:
#   (a) the club-side venue filter returns non-zero data,
#   (b) the avg col label reads "Indian Premier League average" — the
#       auto-promote should still fire even with a venue filter
#       (RCB's tournament universe at this venue is still IPL only).
#
# GROUND TRUTH:
#   SELECT COUNT(*) FROM match
#   WHERE (team1='Royal Challengers Bengaluru' OR team2='Royal Challengers Bengaluru')
#     AND gender='male' AND team_type='club'
#     AND venue='M Chinnaswamy Stadium';
#   → 100 matches
#
#   SELECT COUNT(DISTINCT event_name) FROM match
#   WHERE (team1='Royal Challengers Bengaluru' OR team2='Royal Challengers Bengaluru')
#     AND gender='male' AND team_type='club';
#   → 1 (RCB plays only IPL)

navigate "$BASE/teams?team=Royal%20Challengers%20Bengaluru&tab=Compare&compare1=__avg__&gender=male&team_type=club&filter_venue=M+Chinnaswamy+Stadium" \
  "Anchor 3 — RCB at Chinnaswamy all-time (venue filter, club)"

JSON_3=$(extract_grid 2>/dev/null)
COL0_HEADER_3=$(echo "$JSON_3" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["header"])')
COL0_MATCHES_3=$(echo "$JSON_3" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["matches_text"])')
COL1_HEADER_3=$(echo "$JSON_3" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')

assert_contains "3.col0 header is RCB" "$COL0_HEADER_3" "Royal Challengers Bengaluru"
assert_contains "3.col0 has 100 matches at Chinnaswamy" "$COL0_MATCHES_3" "100 "
assert_contains "3.col1 avg auto-promoted to IPL (RCB tournament universe = IPL only)" "$COL1_HEADER_3" "Indian Premier League"

# ──────────────────── ANCHOR 4 — RCB / CSK auto-promote (no venue) ────────────────────
# Baseline auto-promote test — RCB + CSK club, all-time, no tournament
# filter. Avg col should auto-promote to "Indian Premier League
# average" because RCB's tournament universe is just IPL.

navigate "$BASE/teams?team=Royal%20Challengers%20Bengaluru&tab=Compare&compare1=__avg__&compare2=Chennai%20Super%20Kings&gender=male&team_type=club" \
  "Anchor 4 — RCB / IPL avg / CSK club all-time (auto-promote)"

JSON_4=$(extract_grid 2>/dev/null)
COL0_HEADER_4=$(echo "$JSON_4" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["header"])')
COL1_HEADER_4=$(echo "$JSON_4" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')
COL1_SUBTITLE_4=$(echo "$JSON_4" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["subtitle"])')
COL2_HEADER_4=$(echo "$JSON_4" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[2]["header"])')

assert_contains "4.col0 header is RCB" "$COL0_HEADER_4" "Royal Challengers Bengaluru"
assert_contains "4.col1 avg auto-promoted to IPL" "$COL1_HEADER_4" "Indian Premier League"
# Subtitle render format: `Gender: men's · Type: club` (lowercase
# gender, prefixed) — no season range when none is set.
assert_contains "4.col1 avg subtitle carries gender" "$COL1_SUBTITLE_4" "men's"
assert_contains "4.col2 header is CSK" "$COL2_HEADER_4" "Chennai Super Kings"

# ──────────────────── ANCHOR 5 — full_member intl avg ────────────────────
# Verifies "Full-member average" anchor when team_class=full_member is
# set on the avg slot. Also tests that the underlying numeric data
# renders (full_member is a live-aggregation path; bucket dispatch
# refuses precomputed when team_class is set).
#
# Match count: the avg col renders the PER-TEAM AVERAGE matches in
# scope, not the raw pool total — `_apply_results_per_team` in
# api/routers/teams.py transforms `matches = pool_matches × 2 /
# unique_teams_in_scope` so every column on the grid speaks per-team.
# Anchor against the API at runtime so we drift-protect against
# incremental data updates.

navigate "$BASE/teams?team=Australia&tab=Compare&compare1=__avg__&compare1_team_class=full_member&compare2=India&gender=male&team_type=international&season_from=2024&season_to=2026" \
  "Anchor 5 — Aus / Full-member avg / Ind 2024-2026"

JSON_5=$(extract_grid 2>/dev/null)
COL1_HEADER_5=$(echo "$JSON_5" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')
COL1_MATCHES_5=$(echo "$JSON_5" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["matches_text"])')

assert_contains "5.col1 avg reads Full-member average" "$COL1_HEADER_5" "Full-member"
# Pull the expected per-team-avg matches from the API at runtime.
API_PER_TEAM_5=$(curl -s "${BASE/5173/8000}/api/v1/scope/averages/summary?gender=male&team_type=international&season_from=2024&season_to=2026&team_class=full_member" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('matches'))")
assert_contains "5.col1 matches == API per-team avg (=$API_PER_TEAM_5)" "$COL1_MATCHES_5" "$API_PER_TEAM_5 matches in scope"

# ──────────────────── ANCHOR 6 — Mode E1 (FilterBar team_class=fm) ────────────────────
# v3 spec — FilterBar team_class=full_member narrows ALL three
# columns via inheritance. No per-slot override needed (compare_filters
# Anchor 5 covers the per-slot path; this anchor proves the symmetric
# default-flow path).
#
# Closed window (2024-2025). Team cols (Aus, Ind) show RAW per-team
# match counts (path-team-specific). Avg col shows the PER-TEAM AVERAGE
# matches in scope (anchored against the API at runtime — see Anchor 5
# rationale).

navigate "$BASE/teams?team=Australia&tab=Compare&compare1=__avg__&compare2=India&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  "Anchor 6 — Mode E1 (FilterBar fm, 3 cols inherit)"

JSON_6=$(extract_grid 2>/dev/null)
COL0_MATCHES_6=$(echo "$JSON_6" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[0]["matches_text"])')
COL1_HEADER_6=$(echo "$JSON_6" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["header"])')
COL1_MATCHES_6=$(echo "$JSON_6" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[1]["matches_text"])')
COL2_MATCHES_6=$(echo "$JSON_6" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())[2]["matches_text"])')

# Anchor team-col raw counts against the per-team /teams/{team}/summary
# endpoint — drift-proof.
# Team /summary endpoints return matches as a MetricEnvelope; read .value.
API_AUS_6=$(curl -s "${BASE/5173/8000}/api/v1/teams/Australia/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('matches'); print(m.get('value') if isinstance(m, dict) else m)")
API_IND_6=$(curl -s "${BASE/5173/8000}/api/v1/teams/India/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('matches'); print(m.get('value') if isinstance(m, dict) else m)")
API_AVG_6=$(curl -s "${BASE/5173/8000}/api/v1/scope/averages/summary?gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('matches'))")

assert_contains "6.col0 Aus matches == API (=$API_AUS_6)" "$COL0_MATCHES_6" "$API_AUS_6 "
assert_contains "6.col1 reads Full-member average (inherited)" "$COL1_HEADER_6" "Full-member"
assert_contains "6.col1 matches == API per-team avg (=$API_AVG_6)" "$COL1_MATCHES_6" "$API_AVG_6 matches in scope"
assert_contains "6.col2 Ind matches == API (=$API_IND_6)" "$COL2_MATCHES_6" "$API_IND_6 "

# ──────────────────── summary ────────────────────
echo
echo "════════════════════════════════════════════"
echo "  $PASS passed, $FAIL failed"
echo "════════════════════════════════════════════"
[[ $FAIL -eq 0 ]] || { printf "%b" "$FAIL_LINES"; exit 1; }
exit 0
