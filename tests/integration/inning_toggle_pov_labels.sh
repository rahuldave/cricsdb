#!/bin/bash
# InningToggle — POV-aware pill labels + ambiguous-page polysemy lock.
#
# WHY THIS SCRIPT EXISTS: 2026-05-12 we made the InningToggle pill
# labels POV-aware via useDiscipline():
#
#   - batting / Partnerships → "Batting first" / "Batting second"
#   - bowling | fielding     → "Bowling first" / "Bowling second"
#   - null (Records, single-player profile) → keep neutral
#       "1st innings" / "2nd innings" (no single POV label can be
#       accurate when batting+bowling+fielding stats coexist on
#       one page under one toggle)
#
# Two-part test:
#
#   PART A: rendered DOM at each of 13 mount sites matches the POV
#   rule. Asserts literal pill text (Audit prompt discipline — assert
#   text, not verdicts).
#
#   PART B: ambiguous-page polysemy lock. On Players profile + Venue
#   Records + Tournament Records, ONE ?inning=0 URL simultaneously
#   means:
#     • batted-first for batting stats,
#     • bowled-first for bowling stats,
#     • fielded-first for fielding stats.
#   Each verified via SQL-anchored counts against the discipline's
#   matching predicate.
#
# Both parts SQL-anchor numeric expecteds at runtime per CLAUDE.md
# "Integration tests must self-anchor against SQL".
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
sql()     { sqlite3 "$DB" "$1" 2>&1; }
unq()     { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au; au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

# Read the InningToggle's pill text (single "Innings…" group).
inning_group_text() {
  ab_eval "Array.from(document.querySelectorAll('.wisden-filter-group')).find(g => g.textContent?.startsWith('Innings'))?.textContent?.trim() || 'NOT_MOUNTED'"
}

# Subjects (resolved live so renames don't quietly mask drift):
KOHLI_ID=$(sql "SELECT id FROM person WHERE name='V Kohli' LIMIT 1")
BUMRAH_ID=$(sql "SELECT id FROM person WHERE name='JJ Bumrah' LIMIT 1")
RAHUL_ID=$(sql "SELECT id FROM person WHERE name='KL Rahul' LIMIT 1")

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }
[ -n "$KOHLI_ID" ] && [ -n "$BUMRAH_ID" ] && [ -n "$RAHUL_ID" ] \
  || { echo "ERROR: subject lookup failed" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ─────────────────────────────────────────────────────────────────
# PART A — POV-aware pill text at each of 13 mount sites.
# ─────────────────────────────────────────────────────────────────
BATTING_PILLS='InningsAll inningsBatting firstBatting second'
BOWLING_PILLS='InningsAll inningsBowling firstBowling second'
NEUTRAL_PILLS='InningsAll innings1st innings2nd innings'

probe_site() {
  local site="$1" url="$2" expected="$3"
  ab open "$url"; sleep 6   # 6s soak — dossier subtabs (esp. Records,
                            # which fires an extra /series/records fetch)
                            # need this for the InningToggle group to
                            # mount before the assertion runs.
  assert_eq "$site" "$expected" "$(inning_group_text)"
}

echo "PART A · Pill text per site (13 sites)"
probe_site "1.  Batting.tsx"               "$BASE/batting?player=$KOHLI_ID"                                              "$BATTING_PILLS"
probe_site "2.  Bowling.tsx"               "$BASE/bowling?player=$BUMRAH_ID"                                             "$BOWLING_PILLS"
probe_site "3.  Fielding.tsx"              "$BASE/fielding?player=$RAHUL_ID"                                             "$BOWLING_PILLS"
probe_site "4.  Players.tsx (ambig)"       "$BASE/players?player=$KOHLI_ID"                                              "$NEUTRAL_PILLS"
probe_site "5.  Venue/Batters"             "$BASE/venues?venue=Wankhede%20Stadium&tab=Batters"                           "$BATTING_PILLS"
probe_site "6.  Venue/Bowlers"             "$BASE/venues?venue=Wankhede%20Stadium&tab=Bowlers"                           "$BOWLING_PILLS"
probe_site "7.  Venue/Fielders"            "$BASE/venues?venue=Wankhede%20Stadium&tab=Fielders"                          "$BOWLING_PILLS"
probe_site "8.  Venue/Records (ambig)"     "$BASE/venues?venue=Wankhede%20Stadium&tab=Records"                           "$NEUTRAL_PILLS"
probe_site "9.  Series/Batting"            "$BASE/series?tournament=Indian%20Premier%20League&tab=Batting"               "$BATTING_PILLS"
probe_site "10. Series/Bowling"            "$BASE/series?tournament=Indian%20Premier%20League&tab=Bowling"               "$BOWLING_PILLS"
probe_site "11. Series/Fielding"           "$BASE/series?tournament=Indian%20Premier%20League&tab=Fielding"              "$BOWLING_PILLS"
probe_site "12. Series/Partnerships"       "$BASE/series?tournament=Indian%20Premier%20League&tab=Partnerships"          "$BATTING_PILLS"
probe_site "13. Series/Records (ambig)"    "$BASE/series?tournament=Indian%20Premier%20League&tab=Records"               "$NEUTRAL_PILLS"

# ─────────────────────────────────────────────────────────────────
# PART B — Ambiguous-page polysemy lock.
#
# On the 3 ambiguous pages, a single `?inning=0` URL simultaneously
# scopes batting stats to the 1st innings (batted first), bowling
# stats to the 1st innings (bowled first), and fielding stats to the
# 1st innings (fielded first). We hit the discipline-specific API
# endpoints that the page consumes under the same ?inning=0 and
# verify each matches an independent SQL count.
# ─────────────────────────────────────────────────────────────────
echo
echo "PART B · Polysemy lock — same ?inning=0 == three POVs simultaneously"

# Site 11 (Test 4 above): Players.tsx — Kohli profile under ?inning=0
echo
echo "Players.tsx (Kohli, ?inning=0):"

# batting axis — matches batted-first
sql_bat=$(sql "SELECT COUNT(DISTINCT i.match_id) FROM delivery d JOIN innings i ON i.id=d.innings_id WHERE d.batter_id='$KOHLI_ID' AND i.innings_number=0 AND i.super_over=0")
api_bat=$(curl -s "$API/api/v1/batters/$KOHLI_ID/summary?inning=0" | python3 -c "import json,sys; r=json.load(sys.stdin); v=r.get('matches'); print(v.get('value') if isinstance(v,dict) else v)")
assert_eq "Players · batting matches @ inning=0 = batted-first matches" "$sql_bat" "$api_bat"

# bowling axis — matches bowled-first
sql_bowl=$(sql "SELECT COUNT(DISTINCT i.match_id) FROM delivery d JOIN innings i ON i.id=d.innings_id WHERE d.bowler_id='$KOHLI_ID' AND i.innings_number=0 AND i.super_over=0")
api_bowl=$(curl -s "$API/api/v1/bowlers/$KOHLI_ID/summary?inning=0" | python3 -c "import json,sys; r=json.load(sys.stdin); v=r.get('matches'); print(v.get('value') if isinstance(v,dict) else v)")
assert_eq "Players · bowling matches @ inning=0 = bowled-first matches" "$sql_bowl" "$api_bowl"

# fielding axis — catches in fielded-first innings (inclusive of C&B per Convention 3)
sql_field=$(sql "SELECT SUM(CASE WHEN fc.kind IN ('caught','caught_and_bowled') AND COALESCE(fc.is_substitute,0)=0 THEN 1 ELSE 0 END) FROM fieldingcredit fc JOIN delivery d ON d.id=fc.delivery_id JOIN innings i ON i.id=d.innings_id WHERE fc.fielder_id='$KOHLI_ID' AND i.innings_number=0 AND i.super_over=0")
api_field=$(curl -s "$API/api/v1/fielders/$KOHLI_ID/summary?inning=0" | python3 -c "import json,sys; r=json.load(sys.stdin); v=r.get('catches'); print(v.get('value') if isinstance(v,dict) else v)")
assert_eq "Players · fielding catches @ inning=0 = fielded-first catches" "$sql_field" "$api_field"

# Sites 8 + 13: Records subtabs.
# /series/records aggregates best_individual_batting + best_bowling_figures
# + largest_partnerships under one query. Pull the top entry from the live
# API + verify its innings_number=0 in the DB. (Endpoint resolves equally
# for venues — filter_venue arg used in lieu of tournament arg.)
records_pov_block() {
  local label="$1" qstr="$2"
  echo
  echo "$label:"

  # best_individual_batting (batting axis) — should be in innings_number=0
  read -r pid mid <<< "$(curl -s "$API/api/v1/series/records?$qstr&inning=0&limit=3" | python3 -c "import json,sys; r=json.load(sys.stdin); e=r['best_individual_batting'][0]; print(e['person_id'], e['match_id'])")"
  inn=$(sql "SELECT i.innings_number FROM delivery d JOIN innings i ON i.id=d.innings_id WHERE d.batter_id='$pid' AND i.match_id=$mid GROUP BY i.innings_number ORDER BY SUM(d.runs_batter) DESC LIMIT 1")
  assert_eq "$label · best_individual_batting in innings_number=0 (batted first)" "0" "$inn"

  # best_bowling_figures (bowling axis) — should be in innings_number=0
  read -r pid mid <<< "$(curl -s "$API/api/v1/series/records?$qstr&inning=0&limit=3" | python3 -c "import json,sys; r=json.load(sys.stdin); e=r['best_bowling_figures'][0]; print(e['person_id'], e['match_id'])")"
  inn=$(sql "SELECT i.innings_number FROM delivery d JOIN innings i ON i.id=d.innings_id WHERE d.bowler_id='$pid' AND i.match_id=$mid GROUP BY i.innings_number ORDER BY COUNT(*) DESC LIMIT 1")
  assert_eq "$label · best_bowling_figures in innings_number=0 (bowled first)" "0" "$inn"

  # largest_partnerships (batting-side axis) — innings_number=0 of the batting team
  read -r mid team <<< "$(curl -s "$API/api/v1/series/records?$qstr&inning=0&limit=3" | python3 -c "import json,sys; r=json.load(sys.stdin); e=r['largest_partnerships'][0]; print(e['match_id'], e['batting_team'])")"
  inn=$(sql "SELECT innings_number FROM innings WHERE match_id=$mid AND team=\"$team\"")
  assert_eq "$label · largest_partnerships team batted in innings_number=0" "0" "$inn"
}

records_pov_block "VenueDossier/Records (Wankhede)"        "filter_venue=Wankhede%20Stadium"
records_pov_block "TournamentDossier/Records (IPL)"        "tournament=Indian%20Premier%20League"

# ─────────────────────────────────────────────────────────────────
echo
echo "─────────────────────────────────────"
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
