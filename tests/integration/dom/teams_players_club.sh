#!/bin/bash
# Teams > Players — club. Anchor: RCB IPL 2025 (single closed-league
# season → one h3 section, 19 distinct players who appeared in the
# XI across the 15-match campaign).
#
# Same custom extractor as teams_players_intl.sh (the tab is a per-
# season grid, not a DataTable).
#
# Closed historical window — values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_players_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_players_club.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — RCB IPL 2025 Players ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025&tab=Players" \
  "Anchor — RCB IPL 2025 Players tab"

JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const sections = Array.from(document.querySelectorAll('h3.wisden-section-title')).map(h3 => {
    const text = h3.innerText.replace(/\s+/g, ' ').trim();
    const seasonMatch = text.match(/^(\S+)\s*\((\d+)\)/);
    const season = seasonMatch ? seasonMatch[1] : null;
    const headerCount = seasonMatch ? parseInt(seasonMatch[2], 10) : null;
    const sib = h3.nextElementSibling;
    const tileNames = sib
      ? Array.from(sib.children).map(row =>
          row.querySelector('a.comp-link')?.innerText?.trim() || ''
        ).filter(Boolean)
      : [];
    return { season, headerCount, tileCount: tileNames.length };
  });
  return { sections };
})()
EVALEOF
)

python3 - "RCB Players IPL 2025" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

EXPECTED = [
    ("2025", 19),
]

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

check(len(dom["sections"]) == len(EXPECTED),
      f"[{label}] section count {len(dom['sections'])} == {len(EXPECTED)}")

for i, (season, count) in enumerate(EXPECTED):
    if i >= len(dom["sections"]):
        fails.append(f"[{label}] missing section {i} (expected season {season})")
        continue
    sec = dom["sections"][i]
    check(sec["season"] == season,
          f"[{label}] section {i} season '{sec['season']}' == '{season}'")
    check(sec["headerCount"] == count,
          f"[{label}] section {i} ({season}) header count {sec['headerCount']} == {count}")
    check(sec["tileCount"] == count,
          f"[{label}] section {i} ({season}) rendered tile count {sec['tileCount']} == {count}")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
