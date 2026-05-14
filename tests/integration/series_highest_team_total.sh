#!/bin/bash
# /series Overview · Highest total tile.
# Phase B of spec-series-precompute-followup.md — wires the tile to
# the precomputed bucketbaselinebatting.highest_inn_* in baseline regime.
# This integration anchors the rendered tile (team + total + opponent)
# against SQL-derived expecteds at multiple scopes — future
# precompute changes that drift the wiring will surface here.
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

# Read the "Highest total: X (team v opponent)" line from the dossier
# overview. Selector targets the `.wisden-tile-em` value alongside
# `.wisden-tile-faint` that contains the label "Highest total:".
ht_total_dom() {
  ab_eval "(() => {
    const faints = Array.from(document.querySelectorAll('.wisden-tile-faint'));
    const label = faints.find(n => n.textContent && n.textContent.trim().startsWith('Highest total'));
    if (!label) return '';
    const em = label.nextElementSibling;
    return em && em.classList && em.classList.contains('wisden-tile-em')
      ? em.textContent.trim() : '';
  })()"
}
ht_pair_dom() {
  ab_eval "(() => {
    const faints = Array.from(document.querySelectorAll('.wisden-tile-faint'));
    const label = faints.find(n => n.textContent && n.textContent.trim().startsWith('Highest total'));
    if (!label) return '';
    const em = label.nextElementSibling;
    const tail = em ? em.nextElementSibling : null;
    return tail ? tail.textContent.replace(/\s+/g, ' ').trim() : '';
  })()"
}

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ── Scope 1 · IPL 2023 (single cell — bucket path) ────────────────
echo "Test 1 · /series IPL 2023 — Highest total"
ipl23=$(sql "
  SELECT i.team || '|' || tot.total || '|' ||
         CASE WHEN m.team1=i.team THEN m.team2 ELSE m.team1 END
  FROM (SELECT d.innings_id, SUM(d.runs_total) AS total
        FROM delivery d GROUP BY d.innings_id) tot
  JOIN innings i ON i.id = tot.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.event_name='Indian Premier League' AND m.season='2023'
  ORDER BY tot.total DESC, m.id ASC LIMIT 1;
")
exp_team=$(echo "$ipl23" | cut -d'|' -f1)
exp_total=$(echo "$ipl23" | cut -d'|' -f2)
exp_opp=$(echo "$ipl23" | cut -d'|' -f3)

ab open "$BASE/series?tournament=Indian%20Premier%20League&season_from=2023&season_to=2023"
sleep 5

assert_eq "IPL 2023 · total" "$exp_total" "$(ht_total_dom)"
pair=$(unq "$(ht_pair_dom)")
case "$pair" in
  *"$exp_team"*"$exp_opp"*) ok "IPL 2023 · team-vs-opp ($exp_team v $exp_opp)" ;;
  *)                        bad "IPL 2023 · team-vs-opp — expected '$exp_team v $exp_opp', got '$pair'" ;;
esac

# ── Scope 2 · IPL all-time (multi-cell — bucket SUM path) ─────────
echo "Test 2 · /series IPL all-time — Highest total"
ipl=$(sql "
  SELECT i.team || '|' || tot.total || '|' ||
         CASE WHEN m.team1=i.team THEN m.team2 ELSE m.team1 END
  FROM (SELECT d.innings_id, SUM(d.runs_total) AS total
        FROM delivery d GROUP BY d.innings_id) tot
  JOIN innings i ON i.id = tot.innings_id
  JOIN match m ON m.id = i.match_id
  WHERE i.super_over=0 AND m.match_type IN ('T20','IT20')
    AND m.event_name='Indian Premier League'
  ORDER BY tot.total DESC, m.id ASC LIMIT 1;
")
exp_team=$(echo "$ipl" | cut -d'|' -f1)
exp_total=$(echo "$ipl" | cut -d'|' -f2)
exp_opp=$(echo "$ipl" | cut -d'|' -f3)

ab open "$BASE/series?tournament=Indian%20Premier%20League"
sleep 5

assert_eq "IPL all-time · total" "$exp_total" "$(ht_total_dom)"
pair=$(unq "$(ht_pair_dom)")
case "$pair" in
  *"$exp_team"*"$exp_opp"*) ok "IPL all-time · team-vs-opp ($exp_team v $exp_opp)" ;;
  *)                        bad "IPL all-time · team-vs-opp — expected '$exp_team v $exp_opp', got '$pair'" ;;
esac

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "FAIL: $FAIL/$((PASS+FAIL))"
  echo -e "$FAILS"
  exit 1
fi
echo "PASS: $PASS/$PASS"
