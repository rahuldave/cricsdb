#!/bin/bash
# inning toggle — per-page click-after-mount refetch.
#
# WHY THIS SCRIPT EXISTS: commit be4d755 ("filterDeps: migrate every
# consumer to useFilterDeps()") silently dropped `filters.inning` from
# every page's deps array. `useFilterDeps()` iterates FILTER_KEYS, and
# `inning` is an AuxParam (not in FILTER_KEYS), so the migration
# erased the inning-toggle refetch path on every page that mounts an
# InningToggle. Deep-link with ?inning=0 still worked (mount reads
# URL); CLICKING the pill after mount silently no-op'd on EVERY page.
#
# Prior inning coverage deep-linked via `agent-browser navigate` to
# &inning=0 — fresh mount each time, deps issue invisible. Pill
# clicks were asserted only at the URL-write layer, not against
# data refetch. The bug lived in the click-after-mount + DOM-refetch
# gap on every mount site.
#
# This script asserts displayed DOM values AFTER the inning click on
# EVERY page that mounts InningToggle:
#
#   1. Player Batting   (Batting.tsx)
#   2. Player Bowling   (Bowling.tsx)
#   3. Player Fielding  (Fielding.tsx)
#   4. Players dossier  (Players.tsx → SinglePlayerView)
#   5. Teams subtab Batting       \ each subtab gates the toggle and
#   6. Teams subtab Bowling        \ has its own per-tab fetches that
#   7. Teams subtab Fielding       / share filterDeps; visiting each
#   8. Teams subtab Partnerships  / confirms the deps actually flow
#   9. Tournament dossier Batters tab
#  10. Venue dossier Batters tab
#
# **SQL-DERIVED ANCHORS** (CLAUDE.md "Integration tests must
# self-anchor against SQL"). Every numeric expected value below is
# computed FROM cricket.db at test runtime — not hardcoded. A
# hardcoded "120" silently matches a bug that drifts the API to
# "120-by-coincidence" (e.g. the page rendering stale cache). The
# SQL extract is the single source of truth.
#
# Per CLAUDE.md "Audit prompt discipline" — assert literal text, not
# yes/no verdicts. Per "browser-agent run mandatory" — every control
# gets clicked, not just deep-linked.
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then
    ok "$label (=$expected)"
  else
    bad "$label — expected '$expected' (from SQL), got '$au'"
  fi
}

assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not found in: $au"; fi
}

assert_lacks() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" != *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' still present in: $au"; fi
}

sql() { sqlite3 "$DB" "$1" 2>&1; }

# Click the All / 1st / 2nd innings pill (page-local InningToggle).
# Position-based selector because pill TEXT is POV-aware as of
# 2026-05-12 — Batting pages render "Batting first" not "1st innings".
# The "Innings"-labelled wisden-filter-group is stable; its 3 segs
# are always [All, innings_number=0, innings_number=1] in that order.
click_inning() {
  case "$1" in
    All) idx=0;;
    0)   idx=1;;
    1)   idx=2;;
  esac
  ab_eval "(() => { const g = Array.from(document.querySelectorAll('.wisden-filter-group')).find(g => g.querySelector('.wisden-filter-label')?.textContent === 'Innings'); g?.querySelectorAll('.wisden-seg')[$idx]?.click(); })()" >/dev/null
}

# DOM extractors. Match label-then-value — same shape as cross_
# cutting_inning_split.sh's findValueAfter.
matches_dom() {
  ab_eval "document.body.textContent.match(/Matches(\d+)/)?.[1] || ''"
}

# Player Fielding header doesn't show "Matches"-on-line — it shows
# "Catches" and "Stumpings"; the matches counter that shows up there
# is constant across innings filters because the player's *match*
# count doesn't depend on which-innings-they-fielded-in. So we anchor
# fielding on Catches.
catches_dom() {
  ab_eval "(() => { const ls = document.body.innerText.split('\n'); const i = ls.findIndex(s => s.trim() === 'Catches'); if (i === -1) return ''; const v = ls[i+1] || ''; const m = v.match(/^(\d+)/); return m ? m[1] : ''; })()"
}

# Runs counter (Players.tsx PlayerProfile shows it without a Matches
# stat-card on the dossier landing). Strips comma (DOM: '4,853' →
# '4853').
runs_dom() {
  ab_eval "(() => { const ls = document.body.innerText.split('\n'); const i = ls.findIndex(s => s.trim() === 'Runs'); if (i === -1) return ''; const v = (ls[i+1] || '').replace(/,/g, ''); const m = v.match(/^(\d+)/); return m ? m[1] : ''; })()"
}

# Top-by-average batter on Tournament/Venue dossier Batters tab.
# The inning-sensitive surface — top runs / strike rate change with
# inning_number, so name flips between innings.
top_batter_dom() {
  ab_eval "(() => { const tbls = document.querySelectorAll('table'); for (const t of tbls) { const heads = Array.from(t.querySelectorAll('thead th')).map(th => th.textContent.trim()); if (heads.includes('Average') || heads.includes('Avg')) { const r = t.querySelector('tbody tr'); if (!r) return ''; return Array.from(r.querySelectorAll('th,td'))[0]?.textContent.trim() || ''; } } return ''; })()"
}

url_dom() { ab_eval "window.location.href"; }

# Verify DB exists.
[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Player Batting page (Batting.tsx)"
SMC_BAT="
  SELECT COUNT(DISTINCT i.match_id) FROM innings i
  JOIN match m ON m.id = i.match_id
  JOIN delivery d ON d.innings_id = i.id
  WHERE d.batter_id='e94915e6' AND m.gender='male'
    AND m.team_type='club' AND i.super_over=0
"
sql_smc_bat_all=$(sql "$SMC_BAT")
sql_smc_bat_in0=$(sql "$SMC_BAT AND i.innings_number=0")
sql_smc_bat_in1=$(sql "$SMC_BAT AND i.innings_number=1")

ab open "$BASE/batting?player=e94915e6&gender=male&team_type=club"
settle 4
assert_eq "Player Batting · mount (all innings)" "$sql_smc_bat_all" "$(matches_dom)"
click_inning 0; settle
assert_eq "Player Batting · click 1st innings"   "$sql_smc_bat_in0" "$(matches_dom)"
click_inning 1; settle
assert_eq "Player Batting · click 2nd innings"   "$sql_smc_bat_in1" "$(matches_dom)"
click_inning All; settle
assert_eq "Player Batting · click All"           "$sql_smc_bat_all" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 2 · Player Bowling page (Bowling.tsx)"
SMC_BOW="
  SELECT COUNT(DISTINCT i.match_id) FROM innings i
  JOIN match m ON m.id = i.match_id
  JOIN delivery d ON d.innings_id = i.id
  WHERE d.bowler_id='e94915e6' AND m.gender='male'
    AND m.team_type='club' AND i.super_over=0
"
sql_smc_bow_all=$(sql "$SMC_BOW")
sql_smc_bow_in0=$(sql "$SMC_BOW AND i.innings_number=0")
sql_smc_bow_in1=$(sql "$SMC_BOW AND i.innings_number=1")

ab open "$BASE/bowling?player=e94915e6&gender=male&team_type=club"
settle 4
assert_eq "Player Bowling · mount (all innings)" "$sql_smc_bow_all" "$(matches_dom)"
click_inning 0; settle
assert_eq "Player Bowling · click 1st innings"   "$sql_smc_bow_in0" "$(matches_dom)"
click_inning 1; settle
assert_eq "Player Bowling · click 2nd innings"   "$sql_smc_bow_in1" "$(matches_dom)"
click_inning All; settle
assert_eq "Player Bowling · click All"           "$sql_smc_bow_all" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 3 · Player Fielding page (Fielding.tsx)"
# Use catches as the inning-sensitive anchor — Matches doesn't change
# with inning on a fielding page (the player appears in the same
# matches regardless of which innings their team fielded in).
SMC_CTC="
  SELECT COUNT(*) FROM fieldingcredit fc
  JOIN delivery d ON d.id = fc.delivery_id
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE fc.fielder_id='e94915e6' AND fc.kind='caught'
    AND fc.is_substitute=0 AND m.gender='male'
    AND m.team_type='club' AND i.super_over=0
"
sql_smc_ctc_all=$(sql "$SMC_CTC")
sql_smc_ctc_in0=$(sql "$SMC_CTC AND i.innings_number=0")
sql_smc_ctc_in1=$(sql "$SMC_CTC AND i.innings_number=1")

ab open "$BASE/fielding?player=e94915e6&gender=male&team_type=club"
settle 4
assert_eq "Player Fielding · mount (catches all)" "$sql_smc_ctc_all" "$(catches_dom)"
click_inning 0; settle
assert_eq "Player Fielding · click 1st innings"   "$sql_smc_ctc_in0" "$(catches_dom)"
click_inning 1; settle
assert_eq "Player Fielding · click 2nd innings"   "$sql_smc_ctc_in1" "$(catches_dom)"
click_inning All; settle
assert_eq "Player Fielding · click All"           "$sql_smc_ctc_all" "$(catches_dom)"

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 4 · Players multi-tab dossier (Players.tsx → SinglePlayerView)"
# The dossier landing renders PlayerProfile (no Matches stat-card)
# — anchor on the Runs counter instead. SQL mirrors api/routers/
# batting.py's _batting_filter (extras_wides=0, extras_noballs=0).
SMC_RUNS="
  SELECT SUM(d.runs_batter) FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE d.batter_id='e94915e6' AND m.gender='male'
    AND m.team_type='club' AND i.super_over=0
    AND d.extras_wides=0 AND d.extras_noballs=0
"
sql_smc_runs_all=$(sql "$SMC_RUNS")
sql_smc_runs_in0=$(sql "$SMC_RUNS AND i.innings_number=0")
sql_smc_runs_in1=$(sql "$SMC_RUNS AND i.innings_number=1")

ab open "$BASE/players?player=e94915e6&gender=male&team_type=club"
settle 4
assert_eq "Players dossier · mount (all innings)" "$sql_smc_runs_all" "$(runs_dom)"
click_inning 0; settle
assert_eq "Players dossier · click 1st innings"   "$sql_smc_runs_in0" "$(runs_dom)"
click_inning 1; settle
assert_eq "Players dossier · click 2nd innings"   "$sql_smc_runs_in1" "$(runs_dom)"
click_inning All; settle
assert_eq "Players dossier · click All"           "$sql_smc_runs_all" "$(runs_dom)"

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 5 · Teams page subtabs (Batting / Bowling / Fielding / Partnerships)"
# The team-summary header drives every subtab's Matches counter.
# Visiting each subtab confirms (a) the InningToggle is actually
# mounted on that subtab (gating list in Teams.tsx) AND (b) clicking
# it triggers a refetch in the per-subtab fetches (each TabComponent
# uses the page-level filterDeps prop).
#
# All-innings count comes from the match table directly (260) since
# the team-summary endpoint counts all matches the team played,
# including ones with no innings rows for that team. With inning=N,
# the API switches to innings-row-based counting.
sql_csk_all=$(sql "SELECT COUNT(*) FROM match WHERE gender='male' AND team_type='club' AND (team1='Chennai Super Kings' OR team2='Chennai Super Kings')")
sql_csk_in0=$(sql "SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE m.gender='male' AND m.team_type='club' AND i.team='Chennai Super Kings' AND i.super_over=0 AND i.innings_number=0")
sql_csk_in1=$(sql "SELECT COUNT(DISTINCT i.match_id) FROM innings i JOIN match m ON m.id=i.match_id WHERE m.gender='male' AND m.team_type='club' AND i.team='Chennai Super Kings' AND i.super_over=0 AND i.innings_number=1")

for sub in Batting Bowling Fielding Partnerships; do
  echo "  ── subtab: $sub"
  ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=$sub"
  settle 4
  assert_eq "Teams [$sub] · mount (all)"           "$sql_csk_all" "$(matches_dom)"
  click_inning 0; settle
  assert_eq "Teams [$sub] · click 1st innings"     "$sql_csk_in0" "$(matches_dom)"
  click_inning 1; settle
  assert_eq "Teams [$sub] · click 2nd innings"     "$sql_csk_in1" "$(matches_dom)"
  click_inning All; settle
  assert_eq "Teams [$sub] · click All"             "$sql_csk_all" "$(matches_dom)"
done

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 6 · Tournament dossier Batters tab (TournamentDossier.tsx)"
# Anchor: top-by-average batter NAME flips between inning_number=0
# and inning_number=1 — innings-specific top-runs orderings differ
# enough that the leader changes. This makes the assertion robust
# to data drift while still catching the deps-broken case (where
# the click would NO-OP and all three reads would be identical).
#
# We compute expected top names from SQL (mirror api/routers/series.py
# batters-leaders by_average ordering: average DESC, runs DESC,
# strike_rate DESC, dismissals_qualifier).
top_by_avg_sql() {
  local where_extra="$1"
  sql "
    WITH per_player AS (
      SELECT d.batter_id AS pid,
             SUM(d.runs_batter) AS runs,
             SUM(CASE WHEN d.extras_wides=0 THEN 1 ELSE 0 END) AS balls,
             SUM(CASE WHEN d.extras_wides=0 AND d.extras_noballs=0 THEN 1 ELSE 0 END) AS legal_balls,
             COUNT(DISTINCT i.id) AS innings,
             SUM(CASE WHEN w.player_out_id = d.batter_id THEN 1 ELSE 0 END) AS dismissals
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
       WHERE m.event_name='Indian Premier League'
         AND m.gender='male' AND m.team_type='club'
         AND i.super_over=0
         $where_extra
       GROUP BY d.batter_id
       HAVING dismissals > 0 AND innings >= 8
    )
    SELECT p.short_name FROM per_player pp
    JOIN person p ON p.person_id = pp.pid
    ORDER BY (CAST(runs AS REAL)/dismissals) DESC, runs DESC
    LIMIT 1
  "
}
sql_ipl_top_all=$(top_by_avg_sql "")
sql_ipl_top_in0=$(top_by_avg_sql "AND i.innings_number=0")
sql_ipl_top_in1=$(top_by_avg_sql "AND i.innings_number=1")

ab open "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&tab=Batters"
settle 8
# We don't assert the literal SQL-top name (the API's by-average
# tiebreaker uses strike_rate which we'd need to mirror exactly).
# Instead we assert that the rendered top-batter NAME differs across
# the three states — the click-after-mount no-op bug would render
# identical names for all three.
top_all=$(top_batter_dom)
click_inning 0; settle
top_in0=$(top_batter_dom)
click_inning 1; settle
top_in1=$(top_batter_dom)
click_inning All; settle
top_back=$(top_batter_dom)

[ -n "$(unq "$top_all")" ] && [ -n "$(unq "$top_in0")" ] && [ -n "$(unq "$top_in1")" ] \
  && ok "Tournament Batters · top-by-avg name extracted (all=$top_all, in0=$top_in0, in1=$top_in1)" \
  || bad "Tournament Batters · top name extraction failed"

if [ "$(unq "$top_in0")" != "$(unq "$top_in1")" ]; then
  ok "Tournament Batters · 1st innings top != 2nd innings top (refetch fired)"
else
  bad "Tournament Batters · 1st innings top == 2nd innings top: $top_in0 — refetch likely no-op'd"
fi
if [ "$(unq "$top_back")" = "$(unq "$top_all")" ]; then
  ok "Tournament Batters · click All restored mount-time top"
else
  bad "Tournament Batters · click All gave '$top_back' but mount was '$top_all'"
fi

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 7 · Venue dossier Batters tab (VenueDossier.tsx)"
ab open "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&tab=Batters"
settle 8
top_all=$(top_batter_dom)
click_inning 0; settle
top_in0=$(top_batter_dom)
click_inning 1; settle
top_in1=$(top_batter_dom)
click_inning All; settle
top_back=$(top_batter_dom)

[ -n "$(unq "$top_all")" ] && [ -n "$(unq "$top_in0")" ] && [ -n "$(unq "$top_in1")" ] \
  && ok "Venue Batters · top name extracted (all=$top_all, in0=$top_in0, in1=$top_in1)" \
  || bad "Venue Batters · top name extraction failed"

if [ "$(unq "$top_in0")" != "$(unq "$top_in1")" ]; then
  ok "Venue Batters · 1st innings top != 2nd innings top (refetch fired)"
else
  bad "Venue Batters · 1st innings top == 2nd innings top: $top_in0 — refetch likely no-op'd"
fi
if [ "$(unq "$top_back")" = "$(unq "$top_all")" ]; then
  ok "Venue Batters · click All restored mount-time top"
else
  bad "Venue Batters · click All gave '$top_back' but mount was '$top_all'"
fi

# ─────────────────────────────────────────────────────────────────
echo
echo "Test 8 · Compare-param URL discipline (Teams page)"
# (a) Deep-link with explicit non-Compare tab + compare params.
#     Page should honour the tab AND strip the stale compare params.
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Batting&compare1=__avg__&compare2=__avg__&compare2_team_class=primary_club"
settle 3
url=$(url_dom)
assert_contains "deep-link tab=Batting · honoured"     "tab=Batting" "$url"
assert_lacks    "deep-link tab=Batting · compare1 stripped" "compare1=" "$url"
assert_lacks    "deep-link tab=Batting · compare2 stripped" "compare2=" "$url"

# (b) Deep-link with NO tab + compare params. Page should redirect
#     to tab=Compare and PRESERVE the compare params.
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&compare1=__avg__&compare2=__avg__&compare2_team_class=primary_club"
settle 3
url=$(url_dom)
assert_contains "no-tab deep-link · redirected to tab=Compare" "tab=Compare" "$url"
assert_contains "no-tab deep-link · compare1 preserved"        "compare1="    "$url"
assert_contains "no-tab deep-link · compare2 preserved"        "compare2="    "$url"

# (c) Start on Compare, click Batting subtab — compare stripped.
ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Compare&compare1=__avg__&compare2=__avg__&compare2_team_class=primary_club"
settle 3
ab_eval "Array.from(document.querySelectorAll('.wisden-tab')).find(b => b.textContent.trim() === 'Batting')?.click()" >/dev/null
settle 2
url=$(url_dom)
assert_contains "Compare → Batting click · tab=Batting" "tab=Batting" "$url"
assert_lacks    "Compare → Batting click · compare1 stripped" "compare1=" "$url"
assert_lacks    "Compare → Batting click · compare2 stripped" "compare2=" "$url"

# ─────────────────────────────────────────────────────────────────
echo
echo "═════════ Summary ═════════"
TOTAL=$((PASS+FAIL))
echo "  $PASS / $TOTAL pass, $FAIL fail"
[ $FAIL -gt 0 ] && echo -e "Failures:$FAILS"
exit $((FAIL > 0 ? 1 : 0))
