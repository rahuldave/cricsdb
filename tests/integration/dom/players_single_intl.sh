#!/bin/bash
# /players?player=X — single-player profile, intl scope. Anchor:
# V Kohli (ba607b88), men_intl 2024-25 (his post-WC return year).
#
# DOM:
#   .wisden-page-title       → "V Kohli"
#   .wisden-player-identity  → "specialist batter · 7 matches"
#   .wisden-player-section   (one per discipline that has data; for
#                             Kohli in this scope: BATTING + FIELDING.
#                             No BOWLING, no KEEPING — they're hidden.)
#     .wisden-player-section-label  → "BATTING" / "FIELDING"
#     .wisden-player-compact-row    → dt + dd pairs (Runs / Avg / etc.)
#
# Asserted values (SQL-verified):
#   BATTING: Runs 127, Avg 18.14, SR 116.51, 100s 0, 50s 1, HS 76
#   FIELDING: Catches 2, Stumpings 0, Run-outs 0, Total 2
#
# Numbers verified by independent SQL — see audit/players_single_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_single_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Kohli men_intl 24-25 ───────────────
navigate "$BASE/players?player=ba607b88&gender=male&team_type=international&season_from=2024&season_to=2025" \
  "Anchor — V Kohli profile (men_intl 24-25)"
sleep 4   # +4s soak — getPlayerProfile parallel-fetches 4 summaries

JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const title = document.querySelector('.wisden-page-title')
    ?.innerText?.trim().split('\n')[0] || '';
  const identity = document.querySelector('.wisden-player-identity')
    ?.innerText?.trim() || '';

  // Each .wisden-player-section contains a head (.wisden-player-section-label)
  // + a .wisden-statrow with .wisden-stat children (label/value pairs).
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

python3 - "Kohli intl 24-25" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

check("V Kohli" in dom["title"],
      f"[{label}] title '{dom['title']}' contains 'V Kohli'")
check("specialist batter" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains 'specialist batter'")
check("7 matches" in dom["identity"],
      f"[{label}] identity '{dom['identity']}' contains '7 matches'")

# BATTING band assertions.
batting = dom["sections"].get("BATTING") or {}
check(bool(batting), f"[{label}] BATTING section present")
EXPECTED_BATTING = {
    "Runs": "127",
    "Avg":  "18.14",
    "SR":   "116.51",
    "100s": "0",
    "50s":  "1",
    "HS":   "76",
}
for k, v in EXPECTED_BATTING.items():
    actual = batting.get(k, "")
    check(v in actual, f"[{label}] BATTING/{k} '{actual}' contains '{v}'")

# FIELDING band assertions.
fielding = dom["sections"].get("FIELDING") or {}
check(bool(fielding), f"[{label}] FIELDING section present")
EXPECTED_FIELDING = {
    "Catches":   "2",
    "Stumpings": "0",
    "Run-outs":  "0",
    "Total":     "2",
}
for k, v in EXPECTED_FIELDING.items():
    actual = fielding.get(k, "")
    check(v in actual, f"[{label}] FIELDING/{k} '{actual}' contains '{v}'")

# BOWLING + KEEPING should be ABSENT (Kohli is specialist batter).
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
