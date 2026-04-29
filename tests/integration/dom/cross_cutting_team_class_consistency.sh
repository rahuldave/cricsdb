#!/bin/bash
# Cross-cutting consistency anchor — the keystone of Batch 3c.
#
# Asserts the FilterBar's team_class=full_member narrowing fires
# consistently across FOUR distinct UI surfaces. Catches the
# bug-class where a tab's filter wiring drops `team_class` on a
# sub-fetch, OR where the team_class auto-clear effect fires too
# aggressively and silently strips the param.
#
# Two assertion flavors:
#   • CONSISTENCY (S1 == S2): the same Aus 24-25 FM number renders
#     identically as a row count on Match List AND in the Compare
#     tab's identity line.
#   • SENSITIVITY (S3, S4): two surfaces where the FM filter would
#     silently drop a number if it weren't wired through. Aus-vs-
#     Oman (S3) collapses 1 → 0 because Oman is associate. T20 WC
#     Men 2024 (S4) collapses 44 → 16 because 28 of the 44 matches
#     involve associate teams.
#
# Numbers verified by independent SQL — see audit/cross_cutting_team_class.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/cross_cutting_team_class_consistency.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── SURFACE 1 — /teams Match List ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member&tab=Match+List" \
  "S1 — /teams?team=Australia&...&team_class=full_member&tab=Match+List"

JSON_S1=$(extract_data_table 2>/dev/null)
EXPECTED_S1=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 16,
    "total_label_contains": "of 16",
}
PYEXPECT
)
run_data_table_assertions "S1 Aus FM Match List" "$JSON_S1" "$EXPECTED_S1"; record_result $?

# ─────────────── SURFACE 2 — /teams Compare ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member&tab=Compare" \
  "S2 — /teams?...&team_class=full_member&tab=Compare"
sleep 4

# Compare grid: Aus column should carry "16 matches" identity line.
S2_AUS_TEXT=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  for (const c of cols) {
    const header = c.querySelector('.wisden-compare-col-name')?.innerText?.trim() || '';
    if (header.includes('Australia')) {
      return c.querySelector('.wisden-player-identity')?.innerText?.trim() || '';
    }
  }
  return '';
})()
EVALEOF
)

python3 - "S2 Aus FM Compare" "$S2_AUS_TEXT" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
text = json.loads(raw)
ok = "16 matches" in text
print(f"\n=== {label}: {1 if ok else 0} passed, {0 if ok else 1} failed ===")
print(("  ✓ " if ok else "  ✗ ") +
      f"[{label}] Australia col identity '{text}' contains '16 matches'")
sys.exit(0 if ok else 1)
PYEOF
record_result $?

# ─────────────── SURFACE 3 — /head-to-head Aus-vs-Oman ───────────────
# Oman is an ICC associate. With FM filter, the 1 unbounded Aus-vs-
# Oman match (T20 WC group stage) drops out → 0. If team_class
# isn't wired through, the H2H StatCards would show 1.
navigate "$BASE/head-to-head?mode=team&team1=Australia&team2=Oman&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member" \
  "S3 — /head-to-head Aus-vs-Oman 24-25 FM (sensitive — collapses 1→0)"

JSON_S3=$(extract_team_overview 2>/dev/null)
EXPECTED_S3=$(cat <<'PYEXPECT'
{
    "stats": {
        "Matches":   {"value": "0"},
        "Australia": {"value": "0"},
        "Oman":      {"value": "0"},
        "Ties":      {"value": "0"},
        "No result": {"value": "0"},
    },
}
PYEXPECT
)
run_team_overview_assertions "S3 Aus-vs-Oman FM" "$JSON_S3" "$EXPECTED_S3"; record_result $?

# ─────────────── SURFACE 4 — /series Matches T20 WC 2024 FM ───────────────
# Without FM filter, T20 WC 2024 has 44 matches. With FM (drops the
# 28 group-stage matches involving associates), 16 remain.
navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&season_from=2024&season_to=2024&gender=male&team_type=international&team_class=full_member&tab=Matches" \
  "S4 — /series Matches T20 WC 2024 FM (sensitive — collapses 44→16)"

JSON_S4=$(extract_data_table 2>/dev/null)
EXPECTED_S4=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 16,
}
PYEXPECT
)
run_data_table_assertions "S4 T20 WC 2024 FM Matches" "$JSON_S4" "$EXPECTED_S4"; record_result $?

print_summary
