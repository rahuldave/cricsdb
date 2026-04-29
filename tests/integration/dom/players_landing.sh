#!/bin/bash
# /players landing — curated tile audit. The landing renders TWO
# sections from `frontend/src/components/players/CuratedLists.ts`:
#
#   "Popular profiles"      — 9 single-player tiles (men, profiles)
#   "Popular comparisons"   — 5 compare-pair tiles
#
# Each tile is a stretched-link <a> with class .wisden-player-tile;
# compare tiles additionally carry .wisden-compare-tile. Curated
# IDs are checked-in front-end constants — not API output — so the
# test value-add is "did the CuratedLists.ts ID resolve correctly +
# does the page render every expected tile?"
#
# Numbers verified by independent SQL — see audit/players_landing.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/players_landing.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — male landing ───────────────
navigate "$BASE/players?gender=male" \
  "Anchor — /players landing (men)"
sleep 4   # +4s soak — each profile tile fetches a summary

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

python3 - "Players landing" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

# Expected from CuratedLists.ts (PROFILE_MEN order, COMPARE_MEN pairs).
EXPECTED_PROFILES = [
    ("V Kohli",       "ba607b88"),
    ("JJ Bumrah",     "462411b3"),
    ("SPD Smith",     "30a45b23"),
    ("RG Sharma",     "740742ef"),
    ("JC Buttler",    "99b75528"),
    ("HM Amla",       "e798611a"),
    ("Babar Azam",    "8a75e999"),
    ("KS Williamson", "d027ba9f"),
    ("JO Holder",     "0f721006"),
]

EXPECTED_COMPARES = [
    ("V Kohli",   "AK Markram",   "ba607b88", "6a26221c"),
    ("SPD Smith", "JE Root",      "30a45b23", "a343262c"),
    ("JJ Bumrah", "K Rabada",     "462411b3", "e62dd25d"),
    ("BA Stokes", "RA Jadeja",    "e087956b", "fe93fd9d"),
    ("JC Buttler","AC Gilchrist", "99b75528", "2b6e6dec"),
]

EXPECTED_HEADINGS = ["Popular profiles", "Popular comparisons"]

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

# Headings present.
for h in EXPECTED_HEADINGS:
    check(any(h in dh for dh in dom["headings"]),
          f"[{label}] heading '{h}' present")

# Profile tile count + content (order matters per CuratedLists.ts).
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

# Compare tile count + content.
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
