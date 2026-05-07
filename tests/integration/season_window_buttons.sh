#!/bin/bash
# FilterBar season-window quick-select buttons integration test.
#
# Spec: internal_docs/design-decisions.md "FilterBar season-window
# quick-select buttons — scope-aware AND player-aware".
#
# Asserts:
# 1. Button order on a player page: first-3 | all-time | prev-3 |
#    last-3 | latest.
# 2. first-3 button sets season range to seasons[0..3] (FROM the
#    player's career, not the dataset's earliest seasons —
#    player-aware via /api/v1/seasons?person_id=).
# 3. last-3 button on a RETIRED player ends at the player's actual
#    last season (NOT today's calendar last) — fixes the latent
#    retired-player gap.
# 4. prev-3 button slices seasons[-6:-3].
# 5. all-time button clears season_from/to (URL-clean — derived
#    range computed by status bar instead).
# 6. Backend /api/v1/seasons?person_id= narrows to player's career.
#
# Per CLAUDE.md "Integration tests must self-anchor against SQL"
# — every numeric expected value derives from cricket.db at runtime.
set -u

DB="${DB:-/Users/rahul/Projects/cricsdb/cricket.db}"
BASE="${BASE:-http://localhost:5173}"
API="${API:-http://localhost:8000}"
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-2}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }
unq() { echo "$1" | sed -e 's/^"//' -e 's/"$//'; }

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  local au=$(unq "$actual")
  if [ "$au" = "$expected" ]; then ok "$label (=$expected)"
  else bad "$label — expected '$expected', got '$au'"; fi
}

assert_contains() {
  local label="$1" needle="$2" actual="$3"
  local au=$(unq "$actual")
  if [[ "$au" == *"$needle"* ]]; then ok "$label"
  else bad "$label — '$needle' not in: $au"; fi
}

[ -f "$DB" ] || { echo "ERROR: cricket.db not found at $DB" >&2; exit 2; }

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

KOHLI=ba607b88
ABDV=c4487b84

# ─────────────────────────────────────────────────────────────────
echo "Test 1 · Backend /api/v1/seasons?person_id= narrows to player's career"

# Active player Kohli — span starts at his debut (~2007/08).
kohli_first=$(curl -sS "$API/api/v1/seasons?person_id=$KOHLI" | python3 -c "import json,sys; print(json.load(sys.stdin)['seasons'][0])")
sql_kohli_first=$(sqlite3 "$DB" "
  SELECT MIN(m.season) FROM match m
  JOIN matchplayer mp ON mp.match_id = m.id
  WHERE mp.person_id = '$KOHLI'
")
assert_eq "Kohli first season (player-aware) matches SQL" "$sql_kohli_first" "$kohli_first"

# Retired player ABdV — span ENDS at 2021 (his actual last season).
abdv_last=$(curl -sS "$API/api/v1/seasons?person_id=$ABDV" | python3 -c "import json,sys; s=json.load(sys.stdin)['seasons']; print(s[-1])")
sql_abdv_last=$(sqlite3 "$DB" "
  SELECT MAX(m.season) FROM match m
  JOIN matchplayer mp ON mp.match_id = m.id
  WHERE mp.person_id = '$ABDV'
")
assert_eq "ABdV last season (player-aware) matches SQL" "$sql_abdv_last" "$abdv_last"

# Without person_id, /seasons returns the dataset's full span.
dataset_last=$(curl -sS "$API/api/v1/seasons" | python3 -c "import json,sys; s=json.load(sys.stdin)['seasons']; print(s[-1])")
if [ "$dataset_last" = "$abdv_last" ]; then
  bad "Dataset last == ABdV last (=$abdv_last) — test fixture broken (need a retired player)"
else
  ok "Dataset last ($dataset_last) ≠ ABdV last ($abdv_last) — fixture verified"
fi

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 · Button order on player page: first-3 | all-time | prev-3 | last-3 | latest"

ab open "$BASE/batting?player=$KOHLI&gender=male"
settle 3

button_labels=$(ab_eval "Array.from(document.querySelectorAll('.wisden-reset')).filter(b => /first-3|all-time|prev-3|last-3|latest/.test(b.textContent)).map(b => b.textContent.trim()).join('|')")
assert_eq "Buttons in order" "first-3|all-time|prev-3|last-3|latest" "$button_labels"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 · first-3 button — player-aware (Kohli's earliest, not dataset's)"

ab open "$BASE/batting?player=$KOHLI&gender=male"
settle 2

ab_eval "Array.from(document.querySelectorAll('.wisden-reset')).find(b => b.textContent.trim() === 'first-3')?.click()" >/dev/null
settle 1

url_after=$(ab_eval "location.search")
# Kohli's first 3 seasons across all cricket
kohli_first3_from=$(curl -sS "$API/api/v1/seasons?person_id=$KOHLI" | python3 -c "import json,sys; print(json.load(sys.stdin)['seasons'][0])")
kohli_first3_to=$(curl -sS "$API/api/v1/seasons?person_id=$KOHLI" | python3 -c "import json,sys; print(json.load(sys.stdin)['seasons'][2])")
# URL-encoded slash — match the encoded form
assert_contains "first-3 sets season_from to Kohli's first season" "season_from=$(echo "$kohli_first3_from" | sed 's|/|%2F|g')" "$url_after"
assert_contains "first-3 sets season_to to Kohli's third season" "season_to=$(echo "$kohli_first3_to" | sed 's|/|%2F|g')" "$url_after"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 · last-3 button — retired player gap fixed"

ab open "$BASE/batting?player=$ABDV&gender=male"
settle 2

ab_eval "Array.from(document.querySelectorAll('.wisden-reset')).find(b => b.textContent.trim() === 'last-3')?.click()" >/dev/null
settle 1

url_l3=$(ab_eval "location.search")
abdv_last3_from=$(curl -sS "$API/api/v1/seasons?person_id=$ABDV" | python3 -c "import json,sys; s=json.load(sys.stdin)['seasons']; print(s[-3])")
assert_contains "ABdV last-3 starts at his 3rd-last season" "season_from=$(echo "$abdv_last3_from" | sed 's|/|%2F|g')" "$url_l3"
assert_contains "ABdV last-3 ends at his actual last season ($abdv_last)" "season_to=$(echo "$abdv_last" | sed 's|/|%2F|g')" "$url_l3"
# Negative: should NOT contain dataset's recent (2026 etc.) since ABdV retired.
case "$url_l3" in
  *season_to=2026*|*season_to=2025*) bad "ABdV last-3 set season_to into 2025-26 — retired-player gap re-broken: $url_l3" ;;
  *) ok "ABdV last-3 does NOT use dataset-recent seasons (gap fixed)" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 · prev-3 button — three seasons before last-3"

ab open "$BASE/batting?player=$KOHLI&gender=male"
settle 2

ab_eval "Array.from(document.querySelectorAll('.wisden-reset')).find(b => b.textContent.trim() === 'prev-3')?.click()" >/dev/null
settle 1

url_p3=$(ab_eval "location.search")
kohli_prev3_from=$(curl -sS "$API/api/v1/seasons?person_id=$KOHLI" | python3 -c "import json,sys; s=json.load(sys.stdin)['seasons']; print(s[-6])")
kohli_prev3_to=$(curl -sS "$API/api/v1/seasons?person_id=$KOHLI" | python3 -c "import json,sys; s=json.load(sys.stdin)['seasons']; print(s[-4])")
assert_contains "Kohli prev-3 starts at seasons[-6]" "season_from=$(echo "$kohli_prev3_from" | sed 's|/|%2F|g')" "$url_p3"
assert_contains "Kohli prev-3 ends at seasons[-4]" "season_to=$(echo "$kohli_prev3_to" | sed 's|/|%2F|g')" "$url_p3"

# ─────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 · all-time button — clears season_from/to (URL-clean)"

# Land already with a season range set
ab open "$BASE/batting?player=$ABDV&gender=male&season_from=2018&season_to=2019"
settle 2

ab_eval "Array.from(document.querySelectorAll('.wisden-reset')).find(b => b.textContent.trim() === 'all-time')?.click()" >/dev/null
settle 1

url_all=$(ab_eval "location.search")
case "$url_all" in
  *season_from*|*season_to*) bad "all-time should clear season params; URL still has them: $url_all" ;;
  *) ok "all-time clears season_from / season_to (URL-clean)" ;;
esac

# ─────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────"
echo "Season-window buttons integration: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
exit 0
