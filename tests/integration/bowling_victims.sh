#!/bin/bash
# Bowling Victims tab — full uncapped list of batters this bowler has
# dismissed at scope. Mirrors the fielding Victims tab. User-asked
# 2026-05-22.
#
# Asserts:
#   1. New /bowlers/{id}/victims endpoint returns a non-empty list.
#   2. Total victim count matches a direct SQL COUNT(DISTINCT
#      player_out_id) against `cricket.db`.
#   3. The Victims tab on /bowling renders a row count equal to the
#      API count (uncapped — was top-10 only previously via the
#      Wickets summary).
#   4. Per-victim dismissals sum to the player's total wickets
#      (kind-by-kind aggregate equals the bowler's wicket total).

set -u

API="${API:-http://localhost:8000}"
BASE="${BASE:-http://localhost:5173}"
PLAYER=462411b3   # JJ Bumrah
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB="${DB:-$PROJECT_ROOT/cricket.db}"

PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

api_count=$(curl -sS "$API/api/v1/bowlers/$PLAYER/victims?gender=male" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)['victims']))")
echo "  API victim count: $api_count"
if [ "$api_count" -gt 0 ]; then
  ok "/bowlers/{id}/victims returns a non-empty list"
else
  bad "/bowlers/{id}/victims empty"
fi

sql_count=$(sqlite3 "$DB" <<SQL
SELECT COUNT(DISTINCT w.player_out_id)
FROM wicket w
JOIN delivery d ON d.id = w.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.bowler_id = '$PLAYER'
  AND m.gender = 'male'
  AND i.super_over = 0
  AND w.kind IN ('bowled','caught','lbw','stumped','hit wicket','caught and bowled');
SQL
)
echo "  SQL victim count: $sql_count"
if [ "$api_count" = "$sql_count" ]; then
  ok "API count matches SQL"
else
  bad "API count $api_count != SQL $sql_count"
fi

# Sum of victim.dismissals across the API list equals SQL wicket total.
api_total=$(curl -sS "$API/api/v1/bowlers/$PLAYER/victims?gender=male" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['victims']; print(sum(v['dismissals'] for v in d))")
sql_total=$(sqlite3 "$DB" <<SQL
SELECT COUNT(*) FROM wicket w
JOIN delivery d ON d.id = w.delivery_id
JOIN innings i ON i.id = d.innings_id
JOIN match m ON m.id = i.match_id
WHERE d.bowler_id = '$PLAYER'
  AND m.gender = 'male'
  AND i.super_over = 0
  AND w.kind IN ('bowled','caught','lbw','stumped','hit wicket','caught and bowled');
SQL
)
echo "  victim dismissals sum: api=$api_total sql=$sql_total"
if [ "$api_total" = "$sql_total" ]; then
  ok "victim dismissals sum to bowler's total wickets"
else
  bad "sum mismatch (api=$api_total, sql=$sql_total)"
fi

# Page renders a row per victim.
ab open "$BASE/bowling?player=$PLAYER&gender=male&tab=Victims"
ab wait --load networkidle
ab wait --text "Bowled"
ab wait 1500
rendered=$(ab_eval "document.querySelectorAll('table tbody tr').length")
echo "  rendered rows: $rendered"
if [ "$rendered" = "$api_count" ]; then
  ok "Victims tab renders all $api_count rows"
else
  bad "Victims tab rows $rendered != API $api_count"
fi

echo
echo "=========================================="
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
