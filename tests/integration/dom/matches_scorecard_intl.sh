#!/bin/bash
# /matches/:matchId scorecard. Anchor: T20 World Cup 2024 Final
# (match_id=1551, India v South Africa, 2024-06-29 — India won by
# 7 runs in the famous Bumrah/Pandya defense of 176).
#
# DOM layout: 6 .wisden-table elements on the page:
#   T0, T1 — MatchupGridChart (batter × bowler grids; one per innings)
#   T2     — India batting card     (8 batters)
#   T3     — India bowling card     (6 SA bowlers)
#   T4     — South Africa batting   (10 batters)
#   T5     — South Africa bowling   (6 India bowlers)
#
# Asserts the title banner + result line + top-2 rows of each
# batting / bowling card. The matchup grids are cosmetic — not
# pinned here (chart-DOM extractor work is Batch 4d).
#
# Numbers verified by independent SQL — see audit/matches_scorecard_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/matches_scorecard_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/matches/1551" \
  "Anchor — WC 2024 Final scorecard (match_id=1551)"
sleep 5   # +5s soak — scorecard page fans out to 4 charts + 2 fetches

# Header banner. The match-page H2 carries no class — find it inside
# .wisden-match-header.
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

check("India" in dom["title"] and "South Africa" in dom["title"],
      f"[{label}] title '{dom['title']}' contains both teams")
check("India won by 7 runs" in dom["result"],
      f"[{label}] result '{dom['result']}' == 'India won by 7 runs'")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

# T2 — India batting card (8 rows; top 2: Sharma 9(5), Kohli 76(59)).
JSON_T2=$(extract_data_table 2 2>/dev/null)
EXPECTED_T2=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 8,
    "row_assertions": [
        # cols: Batter | Dismissal | R | B | 4s | 6s | SR
        (0, [(0, "RG Sharma"),
             (1, "c H Klaasen"), (1, "KA Maharaj"),
             (2, "9"), (3, "5")]),
        (1, [(0, "V Kohli"),
             (1, "c K Rabada"), (1, "M Jansen"),
             (2, "76"), (3, "59"), (4, "6"), (5, "2")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 1 batting (India)" "$JSON_T2" "$EXPECTED_T2"; record_result $?

# T3 — India bowling card (SA bowlers).
JSON_T3=$(extract_data_table 3 2>/dev/null)
EXPECTED_T3=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        # cols: Bowler | O | M | R | W | Econ | wd | nb
        (0, [(0, "M Jansen"),   (1, "4.0"), (2, "0"), (3, "49"), (4, "1")]),
        (1, [(0, "KA Maharaj"), (1, "3.0"), (2, "0"), (3, "23"), (4, "2")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 1 bowling (SA)" "$JSON_T3" "$EXPECTED_T3"; record_result $?

# T4 — SA batting card (10 rows).
JSON_T4=$(extract_data_table 4 2>/dev/null)
EXPECTED_T4=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        (0, [(0, "RR Hendricks"), (2, "4"),  (3, "5")]),
        (1, [(0, "Q de Kock"),    (2, "39"), (3, "31")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 2 batting (SA)" "$JSON_T4" "$EXPECTED_T4"; record_result $?

# T5 — SA bowling card (India bowlers).
JSON_T5=$(extract_data_table 5 2>/dev/null)
EXPECTED_T5=$(cat <<'PYEXPECT'
{
    "row_assertions": [
        (0, [(0, "Arshdeep Singh"), (1, "4.0"), (3, "21"), (4, "2")]),
        (1, [(0, "JJ Bumrah"),      (1, "4.0"), (3, "19"), (4, "2")]),
    ],
}
PYEXPECT
)
run_data_table_assertions "Inn 2 bowling (India)" "$JSON_T5" "$EXPECTED_T5"; record_result $?

print_summary
