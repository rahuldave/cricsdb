#!/bin/bash
# /series Partnerships · Top partnerships by wicket — Phase C of
# spec-series-precompute-followup.md. Asserts that top-1 partnership
# per wicket-number renders the SQL-derived runs value, exercising
# both bucketbaselinepartnershiptop (tier-mode all-cricket) and live
# SQL (tournament-mode IPL).
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

# Read the rendered first-row runs for the Nth wicket DataTable, in
# the order they appear under "Top partnerships by wicket".
top_runs_for_wicket() {
  local wn="$1"
  ab_eval "(() => {
    // Find the h4 'Nth wicket' header, then the immediately-following
    // DataTable's first row's 'Runs' cell.
    const headers = Array.from(document.querySelectorAll('h4'));
    const ordinals = ['1st','2nd','3rd','4th','5th','6th','7th','8th','9th','10th'];
    const target = ordinals[$wn - 1] + ' wicket';
    const h = headers.find(x => x.textContent?.trim() === target);
    if (!h) return '';
    const table = h.parentElement?.querySelector('table');
    if (!table) return '';
    const firstRow = table.querySelector('tbody tr');
    if (!firstRow) return '';
    return firstRow.querySelector('td')?.textContent?.trim() || '';
  })()"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ── Scope 1 · tier-mode all-cricket (precomputed path) ────────────
echo "Test 1 · /series Partnerships at all-cricket (bucket path)"
ab open "$BASE/series?tab=Partnerships"
sleep 6

for wn in 1 5 10; do
  expected=$(sql "
    WITH ranked AS (
      SELECT p.partnership_runs AS runs,
             ROW_NUMBER() OVER (
               ORDER BY p.partnership_runs DESC,
                        p.partnership_balls ASC,
                        p.id ASC
             ) AS rnk
      FROM partnership p
      JOIN innings i ON i.id=p.innings_id
      JOIN match m ON m.id=i.match_id
      WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
        AND p.wicket_number=$wn
    )
    SELECT runs FROM ranked WHERE rnk=1;
  ")
  actual=$(unq "$(top_runs_for_wicket $wn)")
  if [ "$actual" = "$expected" ]; then
    ok "all-cricket · ${wn} wicket top-1 runs (=$expected)"
  else
    bad "all-cricket · ${wn} wicket top-1 runs — expected '$expected', got '$actual'"
  fi
done

# ── Scope 2 · tournament-mode IPL (live path) ─────────────────────
echo "Test 2 · /series Partnerships at IPL (live path)"
ab open "$BASE/series?tournament=Indian%20Premier%20League&tab=Partnerships"
sleep 6

for wn in 1 5 10; do
  expected=$(sql "
    WITH ranked AS (
      SELECT p.partnership_runs AS runs,
             ROW_NUMBER() OVER (
               ORDER BY p.partnership_runs DESC,
                        p.partnership_balls ASC
             ) AS rnk
      FROM partnership p
      JOIN innings i ON i.id=p.innings_id
      JOIN match m ON m.id=i.match_id
      WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
        AND m.event_name='Indian Premier League'
        AND p.wicket_number=$wn
    )
    SELECT runs FROM ranked WHERE rnk=1;
  ")
  actual=$(unq "$(top_runs_for_wicket $wn)")
  if [ "$actual" = "$expected" ]; then
    ok "IPL · ${wn} wicket top-1 runs (=$expected)"
  else
    bad "IPL · ${wn} wicket top-1 runs — expected '$expected', got '$actual'"
  fi
done

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
