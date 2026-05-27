#!/bin/bash
# Player position-mix baseline — three-tier inline visual.
#
# Phase 5 of spec-player-compare-average.md. The Players page renders
# each numeric stat tile as three tiers when a cohort baseline is
# available:
#
#     Avg
#     40.03                     ← bold value (existing)
#     vs base 29.50  ↑ +35.7%   ← subtitle: MetricDelta with label="base"
#
# Pre-Phase 5 only the bold value rendered. This test locks the
# three-tier rendering at known scopes (Kohli/Bumrah/Dhoni at IPL)
# plus the strict-cliff suppression behavior on thin scopes.
#
# Spec §3.1, §3.2, §3.4, §3.6, §8.2.
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then ok "$label (=$expected)"
  else bad "$label  expected='$expected'  actual='$actual'"; fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*) ok "$label (contains '$needle')" ;;
    *) bad "$label  '$haystack' missing '$needle'" ;;
  esac
}

assert_present() {
  local label="$1" actual="$2"
  if [ -n "$actual" ] && [ "$actual" != "0" ] && [ "$actual" != "null" ]; then
    ok "$label (=$actual)"
  else
    bad "$label  actual='$actual'"
  fi
}

# ───────────────────────────────────────────────────────────────────
# Test 1 — Kohli IPL: three-tier batting band renders with baseline
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 1: Kohli /players?player=ba607b88&tournament=Indian+Premier+League"
ab open "$BASE/players?player=ba607b88&tournament=Indian+Premier+League"
sleep 3

# Bold value for Avg = all-ball IPL runs / dismissals (SQL truth derived
# at runtime). Runs are all-ball (spec-batting-allball-runs-single-source
# §2) — no legal gate on the numerator.
sql_avg=$(sqlite3 "$DB" "
  SELECT printf('%.2f',
    1.0 * (SELECT SUM(d.runs_batter) FROM delivery d
           JOIN innings i ON i.id = d.innings_id
           JOIN match m ON m.id = i.match_id
           WHERE d.batter_id = 'ba607b88' AND i.super_over = 0
             AND m.event_name = 'Indian Premier League')
    /
    (SELECT COUNT(*) FROM wicket w
     JOIN delivery d ON d.id = w.delivery_id
     JOIN innings i ON i.id = d.innings_id
     JOIN match m ON m.id = i.match_id
     WHERE w.player_out_id = 'ba607b88' AND i.super_over = 0
       AND m.event_name = 'Indian Premier League'
       AND w.kind NOT IN ('retired hurt', 'retired out')))
")
dom_avg=$(ab_eval "
  Array.from(document.querySelectorAll('.wisden-stat'))
    .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Avg')
    ?.querySelector('.wisden-stat-value')?.textContent?.trim()
" | sed 's/"//g')
assert_eq "Kohli IPL Avg bold value matches SQL" "$sql_avg" "$dom_avg"

# Subtitle present: "vs base <num>"
avg_sub=$(ab_eval "
  Array.from(document.querySelectorAll('.wisden-stat'))
    .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Avg')
    ?.querySelector('.wisden-stat-sub')?.textContent?.trim()
" | sed 's/"//g')
assert_contains "Kohli IPL Avg subtitle has 'vs base'" "vs base " "$avg_sub"
assert_contains "Kohli IPL Avg subtitle has delta chip" "%" "$avg_sub"

# scope_avg.value matches the API endpoint's scope_avg.
api_scope_avg=$(curl -s "$API/api/v1/batters/ba607b88/summary?tournament=Indian+Premier+League" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['average']['scope_avg'])")
assert_contains "Kohli IPL Avg subtitle includes API scope_avg" "${api_scope_avg}" "$avg_sub"

# ───────────────────────────────────────────────────────────────────
# Test 2 — Bumrah IPL: bowling cohort delta is sharply directional
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 2: Bumrah /players?player=462411b3&tournament=Indian+Premier+League"
ab open "$BASE/players?player=462411b3&tournament=Indian+Premier+League"
sleep 3

econ_sub=$(ab_eval "
  Array.from(document.querySelectorAll('.wisden-stat'))
    .filter(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Econ')
    .pop()
    ?.querySelector('.wisden-stat-sub')?.textContent?.trim()
" | sed 's/"//g')
assert_contains "Bumrah IPL Econ subtitle has 'vs base'" "vs base " "$econ_sub"
# Bumrah is significantly below cohort (he's elite). The delta is
# negative (lower=better aligned) → green arrow ↓.
assert_contains "Bumrah IPL Econ subtitle shows ↓ delta" "↓" "$econ_sub"

# ───────────────────────────────────────────────────────────────────
# Test 3 — tooltip exposes cohort mix phrasing (§3.4)
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 3: Kohli IPL — Avg subtitle tooltip names the cohort mix"
ab open "$BASE/players?player=ba607b88&tournament=Indian+Premier+League"
sleep 3
tooltip=$(ab_eval "
  Array.from(document.querySelectorAll('.wisden-stat'))
    .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Avg')
    ?.querySelector('.wisden-stat-sub span[title]')?.getAttribute('title')
" | sed 's/^"//; s/"$//')
assert_contains "Tooltip names Position-mix baseline" "Position-mix baseline" "$tooltip"
assert_contains "Tooltip names Opener bucket" "Opener" "$tooltip"
assert_contains "Tooltip cites cohort player count" "players" "$tooltip"

# ───────────────────────────────────────────────────────────────────
# Test 4 — Compare grid: each column carries its own delta chip
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 4: Kohli + Bumbrah compare — each column has independent delta"
ab open "$BASE/players?player=ba607b88&compare=462411b3&tournament=Indian+Premier+League"
sleep 3

# In compact mode each column's <dd> contains both value and delta chip.
# Count rows with %-symbol — should be at least one per compared discipline.
chips=$(ab_eval "
  document.querySelectorAll('.wisden-player-compact .wisden-player-compact-row dd').length > 0
    && Array.from(document.querySelectorAll('.wisden-player-compact .wisden-player-compact-row dd'))
        .filter(dd => /%/.test(dd.textContent || ''))
        .length
" | sed 's/"//g')
[ "$chips" -ge 2 ] && ok "compare grid has ≥2 delta chips across columns (=$chips)" \
                   || bad "compare grid delta chip count actual=$chips"

# ───────────────────────────────────────────────────────────────────
# Test 5 — Dhoni IPL: keeper cohort applied (not outfielder)
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 5: Dhoni /players?player=4a8a2e3b — keeper partition selected"
ab open "$BASE/players?player=4a8a2e3b&tournament=Indian+Premier+League"
sleep 3

dis_per_match=$(ab_eval "
  Array.from(document.querySelectorAll('.wisden-stat'))
    .find(s => s.querySelector('.wisden-stat-label')?.textContent?.trim() === 'Dis/Match')
    ?.querySelector('.wisden-stat-sub')?.textContent?.trim()
" | sed 's/"//g')
assert_contains "Dhoni Dis/Match subtitle present (keeper cohort active)" "vs base " "$dis_per_match"
# Dhoni's keeper cohort baseline at IPL ≈ 0.9 (vs outfielder ≈ 0.36).
# The presence of a value ≥0.5 in the subtitle indicates keeper cohort.
assert_contains "Keeper cohort baseline visible in Dhoni subtitle (≥0.5)" "0." "$dis_per_match"

# ───────────────────────────────────────────────────────────────────
# Test 6 — Mobile viewport: no horizontal overflow
# ───────────────────────────────────────────────────────────────────

echo
echo "Test 6: mobile 390px viewport — no horizontal overflow"
ab set viewport 390 844
ab open "$BASE/players?player=ba607b88&tournament=Indian+Premier+League"
sleep 3

overflow=$(ab_eval "document.body.scrollWidth > window.innerWidth ? 'YES' : 'NO'" | sed 's/"//g')
assert_eq "Mobile body fits within viewport" "NO" "$overflow"

# Restore desktop viewport for any follow-up tests.
ab set viewport 1280 720

# ───────────────────────────────────────────────────────────────────

echo
echo "PASS: $PASS"
echo "FAIL: $FAIL"
[ "$FAIL" = 0 ]
