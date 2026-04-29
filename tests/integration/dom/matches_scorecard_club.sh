#!/bin/bash
# /matches/:matchId scorecard. Anchor: IPL 2025 Final (match_id=6018,
# Royal Challengers Bengaluru v Punjab Kings, Narendra Modi Stadium
# Ahmedabad, 2025-06-03 — RCB won by 6 runs in a low-scoring
# 190/9 vs 184/7 final).
#
# Same DOM layout as matches_scorecard_intl: 6 .wisden-table elements:
#   T0, T1 — MatchupGridChart (one per innings)
#   T2     — RCB batting card     (10 batters)
#   T3     — RCB bowling card     (5 PBKS bowlers)
#   T4     — PBKS batting         (9 batters)
#   T5     — PBKS bowling         (6 RCB bowlers)
#
# Numbers verified by independent SQL — see audit/matches_scorecard_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/matches_scorecard_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/matches/6018" \
  "Anchor — IPL 2025 Final scorecard (match_id=6018)"
sleep 5

HEADER_JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => ({
  title: document.querySelector('.wisden-match-header h2')?.innerText?.trim() || '',
  result: document.querySelector('.wisden-match-result')?.innerText?.trim() || '',
}))()
EVALEOF
)

python3 - "Header" "$HEADER_JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

check("Royal Challengers Bengaluru" in dom["title"] and "Punjab Kings" in dom["title"],
      f"[{label}] title '{dom['title']}' contains both teams")
check("Royal Challengers Bengaluru won by 6 runs" in dom["result"],
      f"[{label}] result '{dom['result']}' == 'RCB won by 6 runs'")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

# T2 — RCB batting (10 rows; openers PD Salt + V Kohli).
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # cols: Batter | Dismissal | R | B | 4s | 6s | SR
        (0, [(0, "PD Salt"), (1, "c SS Iyer"), (1, "KA Jamieson"),
             (2, "16"), (3, "9")]),
        (1, [(0, "V Kohli"), (1, "c & b Azmatullah Omarzai"),
             (2, "43"), (3, "35")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 1 batting (RCB)" "$JSON_T2" "$EXPECTED_T2"; record_result $?

# T3 — RCB bowling (PBKS bowlers, 5 rows).
JSON_T3=$(extract_data_table 3 2>/dev/null)
EXPECTED_T3=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 5,
    "row_assertions": [
        # cols: Bowler | O | M | R | W | Econ | wd | nb
        (0, [(0, "Arshdeep Singh"), (1, "4.0"), (3, "40"), (4, "3")]),
        (1, [(0, "KA Jamieson"),    (1, "4.0"), (3, "48"), (4, "3")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 1 bowling (PBKS)" "$JSON_T3" "$EXPECTED_T3"; record_result $?

# T4 — PBKS batting (9 rows).
JSON_T4=$(extract_data_table 4 2>/dev/null)
EXPECTED_T4=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 9,
    "row_assertions": [
        (0, [(0, "Priyansh Arya"),  (2, "24"), (3, "19")]),
        (1, [(0, "P Simran Singh"), (2, "26"), (3, "22")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 2 batting (PBKS)" "$JSON_T4" "$EXPECTED_T4"; record_result $?

# T5 — PBKS bowling (RCB bowlers, 6 rows).
JSON_T5=$(extract_data_table 5 2>/dev/null)
EXPECTED_T5=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 6,
    "row_assertions": [
        (0, [(0, "B Kumar"),    (1, "4.0"), (3, "38"), (4, "2")]),
        (1, [(0, "Yash Dayal"), (1, "3.0"), (3, "24"), (4, "1")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 2 bowling (RCB)" "$JSON_T5" "$EXPECTED_T5"; record_result $?

print_summary
