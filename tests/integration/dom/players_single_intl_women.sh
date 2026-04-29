#!/bin/bash
# /players?player=X — single-player profile, women intl scope.
# Anchor: S Mandhana (5d2eda89), women_intl 2024-25 (the women's
# T20 World Cup 2024 cycle + bilaterals). Specialist batter — only
# BATTING + FIELDING bands render.
#
# DOM:
#   Identity: "specialist batter · 25 matches"  (matches via
#                                                matchplayer; she
#                                                played all 25,
#                                                batted in 23, fielded
#                                                in 25)
#   BATTING:  Runs 877, Avg 43.85, SR 133.69, 100s 1, 50s 8, HS 112
#   FIELDING: Catches 10, Stumpings 0, Run-outs 2, Total 12
#
# Numbers verified by independent SQL — see audit/players_single_intl_women.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_single_intl_women.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Mandhana women_intl 24-25 ───────────────
navigate "$BASE/players?player=5d2eda89&gender=female&team_type=international&season_from=2024&season_to=2025" \
  "Anchor — S Mandhana profile (women_intl 24-25)"
sleep 4

JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const title = document.querySelector('.wisden-page-title')
    ?.innerText?.trim().split('\n')[0] || '';
  const identity = document.querySelector('.wisden-player-identity')
    ?.innerText?.trim() || '';
  const sections = {};
  for (const sec of document.querySelectorAll('.wisden-player-section')) {
    const label = sec.querySelector('.wisden-player-section-label')
      ?.innerText?.trim() || '';
    const rows = {};
    for (const card of sec.querySelectorAll('.wisden-statrow .wisden-stat')) {
      const k = card.querySelector('.wisden-stat-label')?.innerText?.trim() || '';
      const v = card.querySelector('.wisden-stat-value')?.innerText?.trim() || '';
      if (k) rows[k] = v;
    }
    sections[label] = rows;
  }
  return { title, identity, sections };
})()
EVALEOF
)

python3 - "Mandhana women_intl 24-25" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

check("S Mandhana" in dom["title"],
      f"[{label}] title '{dom['title']}' contains 'S Mandhana'")
check("specialist batter" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains 'specialist batter'")
check("25 matches" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains '25 matches'")

batting = dom["sections"].get("BATTING") or {}
check(bool(batting), f"[{label}] BATTING section present")
EXPECTED_BATTING = {
    "Runs": "877",
    "Avg":  "43.85",
    "SR":   "133.69",
    "100s": "1",
    "50s":  "8",
    "HS":   "112",
}
for k, v in EXPECTED_BATTING.items():
    actual = batting.get(k, "")
    check(v in actual, f"[{label}] BATTING/{k} '{actual}' contains '{v}'")

fielding = dom["sections"].get("FIELDING") or {}
check(bool(fielding), f"[{label}] FIELDING section present")
EXPECTED_FIELDING = {
    "Catches":   "10",
    "Stumpings": "0",
    "Run-outs":  "2",
    "Total":     "12",
}
for k, v in EXPECTED_FIELDING.items():
    actual = fielding.get(k, "")
    check(v in actual, f"[{label}] FIELDING/{k} '{actual}' contains '{v}'")

for absent in ("BOWLING", "KEEPING"):
    check(absent not in dom["sections"],
          f"[{label}] {absent} section absent (specialist batter)")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
