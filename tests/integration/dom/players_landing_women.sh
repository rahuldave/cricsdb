#!/bin/bash
# /players?gender=female — women landing. The women variant of
# players_landing.sh. Two sections render off CuratedLists.ts:
#
#   "Popular profiles"      — 9 PROFILE_WOMEN tiles
#   "Popular comparisons"   — 3 COMPARE_WOMEN pairs
#
# CuratedLists.ts displays "D Sharma" though the person table
# stores "DB Sharma" — the tile label is rendered from the curated
# constant directly, so the DOM assertion uses "D Sharma".
#
# Numbers verified by independent SQL — see audit/players_landing_women.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_landing_women.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — women landing ───────────────
navigate "$BASE/players?gender=female" \
  "Anchor — /players landing (women)"
sleep 4

JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const profileTiles = Array.from(
    document.querySelectorAll('.wisden-player-tile:not(.wisden-compare-tile)')
  ).map(t => ({
    name: t.querySelector('.wisden-player-tile-name, .wisden-player-tile-head')
      ?.innerText?.trim() || '',
    href: t.getAttribute('href') || '',
  }));
  const compareTiles = Array.from(
    document.querySelectorAll('.wisden-compare-tile')
  ).map(t => ({
    text: t.innerText.replace(/\s+/g, ' ').trim(),
    href: t.getAttribute('href') || '',
  }));
  const headings = Array.from(
    document.querySelectorAll('h2, h3, .wisden-section-title')
  ).map(h => h.innerText.trim());
  return { profileTiles, compareTiles, headings };
})()
EVALEOF
)

python3 - "Players landing (women)" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

# Expected from CuratedLists.ts (PROFILE_WOMEN order, COMPARE_WOMEN pairs).
EXPECTED_PROFILES = [
    ("S Mandhana",  "5d2eda89"),
    ("EA Perry",    "be150fc8"),
    ("HC Knight",   "4ba0289e"),
    ("BL Mooney",   "52d1dbc8"),
    ("MM Lanning",  "27e003ce"),
    ("D Sharma",    "201fef33"),
    ("AJ Healy",    "321644de"),
    ("SFM Devine",  "de69af96"),
    ("HK Matthews", "d32cf49a"),
]

EXPECTED_COMPARES = [
    ("S Mandhana", "BL Mooney",  "5d2eda89", "52d1dbc8"),
    ("EA Perry",   "HC Knight",  "be150fc8", "4ba0289e"),
    ("AJ Healy",   "S Mandhana", "321644de", "5d2eda89"),
]

EXPECTED_HEADINGS = ["Popular profiles", "Popular comparisons"]

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

for h in EXPECTED_HEADINGS:
    check(any(h in dh for dh in dom["headings"]),
          f"[{label}] heading '{h}' present")

check(len(dom["profileTiles"]) == len(EXPECTED_PROFILES),
      f"[{label}] profile tile count {len(dom['profileTiles'])} == {len(EXPECTED_PROFILES)}")

for i, (name, pid) in enumerate(EXPECTED_PROFILES):
    if i >= len(dom["profileTiles"]):
        fails.append(f"[{label}] missing profile tile {i} ({name})")
        continue
    t = dom["profileTiles"][i]
    check(name in t["name"],
          f"[{label}] profile {i} name '{t['name']}' contains '{name}'")
    check(f"player={pid}" in t["href"],
          f"[{label}] profile {i} href '{t['href']}' contains 'player={pid}'")
    check("gender=female" in t["href"],
          f"[{label}] profile {i} href contains 'gender=female'")

check(len(dom["compareTiles"]) == len(EXPECTED_COMPARES),
      f"[{label}] compare tile count {len(dom['compareTiles'])} == {len(EXPECTED_COMPARES)}")

for i, (a, b, pid_a, pid_b) in enumerate(EXPECTED_COMPARES):
    if i >= len(dom["compareTiles"]):
        fails.append(f"[{label}] missing compare tile {i} ({a} × {b})")
        continue
    t = dom["compareTiles"][i]
    check(a in t["text"] and b in t["text"],
          f"[{label}] compare {i} text '{t['text']}' contains '{a}' + '{b}'")
    check(f"player={pid_a}" in t["href"] and f"compare={pid_b}" in t["href"],
          f"[{label}] compare {i} href '{t['href']}' contains "
          f"'player={pid_a}' + 'compare={pid_b}'")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
