#!/bin/bash
# /players?player=X — single-player profile, club scope. Anchor:
# B Sai Sudharsan (d5130a30) IPL 2025 (Orange Cap holder, 759 runs).
#
# Same DOM shape as players_single_intl.sh. SudharsanIPL 2025 numbers
# already cross-checked in series_batters_club.sh (Table 0 row 0 there);
# this script confirms they render identically on the player profile.
#
# Numbers verified by independent SQL — see audit/players_single_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_single_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Sudharsan IPL 2025 ───────────────
navigate "$BASE/players?player=d5130a30&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025" \
  "Anchor — B Sai Sudharsan profile (IPL 2025)"
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

python3 - "Sudharsan IPL 2025" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

check("B Sai Sudharsan" in dom["title"],
      f"[{label}] title '{dom['title']}' contains 'B Sai Sudharsan'")
check("specialist batter" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains 'specialist batter'")
check("15 matches" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains '15 matches'")

batting = dom["sections"].get("BATTING") or {}
check(bool(batting), f"[{label}] BATTING section present")
EXPECTED_BATTING = {
    "Runs": "759",
    "Avg":  "54.21",
    "SR":   "156.17",
    "100s": "1",
    "50s":  "6",
    "HS":   "108",
}
for k, v in EXPECTED_BATTING.items():
    actual = batting.get(k, "")
    check(v in actual, f"[{label}] BATTING/{k} '{actual}' contains '{v}'")

fielding = dom["sections"].get("FIELDING") or {}
check(bool(fielding), f"[{label}] FIELDING section present")
EXPECTED_FIELDING = {
    "Catches":   "7",
    "Stumpings": "0",
    "Run-outs":  "0",
    "Total":     "7",
}
for k, v in EXPECTED_FIELDING.items():
    actual = fielding.get(k, "")
    check(v in actual, f"[{label}] FIELDING/{k} '{actual}' contains '{v}'")

# Specialist batter — no BOWLING / KEEPING bands.
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
