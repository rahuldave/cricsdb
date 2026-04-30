#!/bin/bash
# club-tier team_class — per-page click-after-mount refetch.
#
# WHY THIS SCRIPT EXISTS: spec-filterbar-team-class-v3.md shipped with
# a silent bug — every page's hand-rolled `filterDeps` array forgot to
# include `team_class`, so clicking the FM toggle on intl pages (or
# the tier pill on club pages) wrote the URL state but didn't refetch
# the displayed data. Deep-link URLs worked because mount reads URL
# state. The pre-existing tests (filterbar / gating / persistence /
# compare) only asserted URL writes, ScopeStatusStrip text, and DOM
# class state — never the literal numeric output post-click. This
# script asserts displayed DOM values AFTER the click, on every page
# that surfaces the FilterBar tier pill.
#
# **SQL-DERIVED ANCHORS** (CLAUDE.md "Integration tests must
# self-anchor against SQL"). Every numeric expected value below is
# computed FROM cricket.db at test runtime — not hardcoded.
# Rationale: a hardcoded "548" silently matches a bug that drifts
# the API to "548-by-coincidence". The SQL extract is the single
# source of truth; sanity layer asserts SQL↔API; this layer asserts
# DOM↔SQL (via the running app). All three must agree, or the test
# fails on the divergent layer.
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

# Quote a DOM value to match SQL's plain-string output (the matchers
# eval to bare strings via agent-browser's JSON output, which already
# wraps in quotes — match by value).
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

# SQL helpers — extract anchor numbers from cricket.db at runtime.
sql() { sqlite3 "$DB" "$1" 2>&1; }

# Tier IN-lists — must mirror api/club_tiers.py exactly. If these
# drift from the Python sets, sanity tests will fail (different
# layer, same source DB) — surfacing the divergence at SQL layer.
PRI=$(cat <<'EOF'
'Indian Premier League','Big Bash League','Pakistan Super League',
'Bangladesh Premier League','Caribbean Premier League','SA20',
'International League T20','Lanka Premier League',
'Major League Cricket','The Hundred Men''s Competition',
'Women''s Big Bash League','Women''s Premier League',
'The Hundred Women''s Competition','Women''s Cricket Super League'
EOF
)
SEC=$(cat <<'EOF'
'Vitality Blast','Syed Mushtaq Ali Trophy','CSA T20 Challenge',
'Super Smash','Nepal Premier League','Women''s Super Smash',
'New Zealand Cricket Women''s Twenty20'
EOF
)
WIN_M="m.gender='male' AND m.team_type='club' AND m.season IN ('2024','2024/25','2025')"

# Click the All / Primary / Secondary tier button.
click_tier() {
  case "$1" in
    All)
      ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group button')).find(b => b.textContent.trim() === 'All' && b.title?.startsWith('Show every'))?.click()" >/dev/null
      ;;
    Primary)
      ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Primary' && b.title?.startsWith('Marquee'))?.click()" >/dev/null
      ;;
    Secondary)
      ab_eval "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Secondary' && b.title?.startsWith('Domestic'))?.click()" >/dev/null
      ;;
  esac
}

matches_dom() {
  ab_eval "document.body.textContent.match(/Matches(\d+)/)?.[1] || ''"
}

# Verify DB exists.
if [ ! -f "$DB" ]; then
  echo "ERROR: cricket.db not found at $DB" >&2
  exit 2
fi

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Teams › Mumbai Indians (primary subject)"
sql_mi_all=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians')")
sql_mi_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians') AND m.event_name IN ($PRI)")
sql_mi_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Mumbai Indians' OR m.team2='Mumbai Indians') AND m.event_name IN ($SEC)")
ab open "$BASE/teams?team=Mumbai%20Indians&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 4
assert_eq "MI · all-tier" "$sql_mi_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "MI · click Primary"   "$sql_mi_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "MI · click Secondary" "$sql_mi_sec" "$(matches_dom)"
click_tier All; settle
assert_eq "MI · click All → unbounded" "$sql_mi_all" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 2 · Teams › Surrey (secondary subject)"
sql_surrey_all=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Surrey' OR m.team2='Surrey')")
sql_surrey_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Surrey' OR m.team2='Surrey') AND m.event_name IN ($PRI)")
sql_surrey_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND (m.team1='Surrey' OR m.team2='Surrey') AND m.event_name IN ($SEC)")
ab open "$BASE/teams?team=Surrey&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 4
assert_eq "Surrey · all-tier" "$sql_surrey_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "Surrey · click Primary"   "$sql_surrey_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "Surrey · click Secondary" "$sql_surrey_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 3 · Venues › Kennington Oval (multi-tier)"
sql_oval_all=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Kennington Oval'")
sql_oval_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Kennington Oval' AND m.event_name IN ($PRI)")
sql_oval_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Kennington Oval' AND m.event_name IN ($SEC)")
ab open "$BASE/venues?venue=Kennington+Oval&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 4
assert_eq "Oval · all-tier"           "$sql_oval_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "Oval · click Primary"      "$sql_oval_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "Oval · click Secondary"    "$sql_oval_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 4 · Venues › Wankhede (primary-only)"
sql_w_all=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Wankhede Stadium'")
sql_w_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Wankhede Stadium' AND m.event_name IN ($PRI)")
sql_w_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.venue='Wankhede Stadium' AND m.event_name IN ($SEC)")
ab open "$BASE/venues?venue=Wankhede+Stadium&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 4
assert_eq "Wankhede · all-tier"       "$sql_w_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "Wankhede · click Primary"  "$sql_w_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "Wankhede · click Secondary" "$sql_w_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 5 · Venues › MCG (404→200 distinguish + primary-only)"
sql_mcg_all=$(sql "SELECT COUNT(*) FROM match m WHERE m.team_type='club' AND m.venue='Melbourne Cricket Ground'")
sql_mcg_pri=$(sql "SELECT COUNT(*) FROM match m WHERE m.team_type='club' AND m.venue='Melbourne Cricket Ground' AND m.event_name IN ($PRI)")
sql_mcg_sec=$(sql "SELECT COUNT(*) FROM match m WHERE m.team_type='club' AND m.venue='Melbourne Cricket Ground' AND m.event_name IN ($SEC)")
ab open "$BASE/venues?venue=Melbourne+Cricket+Ground&team_type=club"
settle 4
assert_eq "MCG · all-tier"             "$sql_mcg_all" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "MCG · click Secondary"      "$sql_mcg_sec" "$(matches_dom)"
v=$(ab_eval "document.body.textContent.toLowerCase().includes('venue not found')")
[ "$v" = "false" ] && ok "MCG · no 'Venue not found' error rendered" \
                  || bad "MCG · 'Venue not found' rendered (404 leaked)"
click_tier Primary; settle
assert_eq "MCG · click Primary"        "$sql_mcg_pri" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 6 · Player › SM Curran Batting (cross-tier player)"
# Player batting matches = matches in which he batted (delivery JOIN).
SMC_BATTED_BASE="
  SELECT COUNT(DISTINCT m.id) FROM delivery d
  JOIN innings i ON i.id = d.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE d.batter_id='e94915e6' AND $WIN_M AND i.super_over=0
"
sql_smc_all=$(sql "$SMC_BATTED_BASE")
sql_smc_pri=$(sql "$SMC_BATTED_BASE AND m.event_name IN ($PRI)")
sql_smc_sec=$(sql "$SMC_BATTED_BASE AND m.event_name IN ($SEC)")
ab open "$BASE/batting?player=e94915e6&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 5
assert_eq "SMC batting · all-tier"     "$sql_smc_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "SMC · click Primary"        "$sql_smc_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "SMC · click Secondary"      "$sql_smc_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 7 · Matches list (paginated total)"
sql_ml_all=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M")
sql_ml_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.event_name IN ($PRI)")
sql_ml_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $WIN_M AND m.event_name IN ($SEC)")
ab open "$BASE/matches?gender=male&team_type=club&season_from=2024&season_to=2025"
settle 5
assert_eq "Matches list · all-tier"    "$sql_ml_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "Matches list · click Primary" "$sql_ml_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "Matches list · click Secondary" "$sql_ml_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 8 · Head-to-Head (team mode, MI vs CSK)"
H2H_BASE="$WIN_M AND ((m.team1='Mumbai Indians' AND m.team2='Chennai Super Kings') OR (m.team1='Chennai Super Kings' AND m.team2='Mumbai Indians'))"
sql_h2h_all=$(sql "SELECT COUNT(*) FROM match m WHERE $H2H_BASE")
sql_h2h_pri=$(sql "SELECT COUNT(*) FROM match m WHERE $H2H_BASE AND m.event_name IN ($PRI)")
sql_h2h_sec=$(sql "SELECT COUNT(*) FROM match m WHERE $H2H_BASE AND m.event_name IN ($SEC)")
ab open "$BASE/head-to-head?mode=team&team1=Mumbai+Indians&team2=Chennai+Super+Kings&gender=male&team_type=club&season_from=2024&season_to=2025"
settle 5
assert_eq "H2H · all-tier"             "$sql_h2h_all" "$(matches_dom)"
click_tier Primary; settle
assert_eq "H2H · click Primary"        "$sql_h2h_pri" "$(matches_dom)"
click_tier Secondary; settle
assert_eq "H2H · click Secondary"      "$sql_h2h_sec" "$(matches_dom)"

# ─────────────────────────────────────────────────────────────────
echo "Test 9 · Compare-tab avg-baseline values"
# Both columns surface a per-team-avg matches count = total*2/unique_teams.
# col 1 (default avg, scope_to_team auto-narrow): pool = IPL only
# col 2 (team_class=primary_club override, scope_to_team disabled): pool = all primary men's
# Pre-fix bug: scope_to_team narrowed both to IPL → both 160.93.
ipl_total=$(sql   "SELECT COUNT(*) FROM match WHERE event_name='Indian Premier League'")
ipl_teams=$(sql   "SELECT COUNT(DISTINCT t) FROM (SELECT team1 t FROM match WHERE event_name='Indian Premier League' UNION SELECT team2 FROM match WHERE event_name='Indian Premier League')")
pri_m_total=$(sql "SELECT COUNT(*) FROM match WHERE gender='male' AND team_type='club' AND event_name IN ($PRI)")
pri_m_teams=$(sql "SELECT COUNT(DISTINCT t) FROM (SELECT team1 t FROM match WHERE gender='male' AND team_type='club' AND event_name IN ($PRI) UNION SELECT team2 FROM match WHERE gender='male' AND team_type='club' AND event_name IN ($PRI))")
csk_total=$(sql   "SELECT COUNT(*) FROM match WHERE gender='male' AND team_type='club' AND (team1='Chennai Super Kings' OR team2='Chennai Super Kings')")
# Per-team-avg formula: round(total * 2 / unique_teams, 2).
expect_ipl_avg=$(printf '%.2f' "$(echo "scale=4; $ipl_total * 2 / $ipl_teams" | bc -l)")
expect_pri_avg=$(printf '%.2f' "$(echo "scale=4; $pri_m_total * 2 / $pri_m_teams" | bc -l)")

ab open "$BASE/teams?team=Chennai+Super+Kings&gender=male&team_type=club&tab=Compare&compare1=__avg__&compare2=__avg__&compare2_team_class=primary_club"
settle 6
read_col() {
  ab_eval "(() => {
    const cols = document.querySelectorAll('.wisden-compare-col');
    if (!cols[$1]) return '';
    const m = cols[$1].textContent.replace(/\\s+/g,' ').match(/Matches([0-9.,]+)/);
    return m ? m[1] : '';
  })()"
}
read_label() {
  ab_eval "(() => {
    const cols = document.querySelectorAll('.wisden-compare-col');
    return cols[$1]?.querySelector('.wisden-compare-col-name')?.textContent.trim() || '';
  })()"
}
assert_eq "CSK Compare col 0 (CSK matches)"           "$csk_total"        "$(read_col 0)"
assert_eq "CSK Compare col 1 (IPL avg = $ipl_total*2/$ipl_teams)"     "$expect_ipl_avg"   "$(read_col 1)"
assert_eq "CSK Compare col 2 (primary avg = $pri_m_total*2/$pri_m_teams)" "$expect_pri_avg" "$(read_col 2)"

v=$(read_label 1)
case "$v" in *Indian*Premier*League*) ok "Compare col 1 label mentions IPL" ;;
            *) bad "col 1 label expected IPL, got: $v" ;;
esac
v=$(read_label 2)
case "$v" in *rimary*) ok "Compare col 2 label mentions Primary" ;;
            *) bad "col 2 label expected Primary, got: $v" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo
if [ $FAIL -eq 0 ]; then
  echo "✅ $PASS PASS / 0 FAIL  (anchors derived from $DB at runtime)"
  exit 0
else
  echo "❌ $PASS PASS / $FAIL FAIL"
  echo -e "FAILS:$FAILS"
  exit 1
fi
