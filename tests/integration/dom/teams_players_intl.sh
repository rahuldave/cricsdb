#!/bin/bash
# Teams > Players — intl. Anchor: Australia men_intl 2024-25.
# Backed by /api/v1/teams/Australia/players-by-season. The tab is NOT
# a DataTable — it renders one h3 section per season + a 3-col grid
# of player tiles (alphabetical). 2024-25 spans THREE seasons in the
# data (calendar 2024, mid-season 2024/25, calendar 2025) so the
# anchor exercises that ordering + the per-section player counts.
#
# Per-season distinct counts (SQL-verified):
#   2025     — 18 players
#   2024/25  — 11 players
#   2024     — 22 players
#
# Custom extractor (inline below) — the generic extract_data_table
# doesn't apply since this isn't a tbody. Walks h3.wisden-section-title
# headers, parses the "(N)" count, and sub-walks the next sibling to
# count player-name links.
#
# Closed historical window — values stay stable across rebuilds.
# Numbers verified by independent SQL — see
# audit/teams_players_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/teams_players_intl.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR — Australia 24-25 Players ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&season_from=2024&season_to=2025&tab=Players" \
  "Anchor — Australia men_intl 24-25 Players tab"

JSON=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const sections = Array.from(document.querySelectorAll('h3.wisden-section-title')).map(h3 => {
    const text = h3.innerText.replace(/\s+/g, ' ').trim();
    const seasonMatch = text.match(/^(\S+)\s*\((\d+)\)/);
    const season = seasonMatch ? seasonMatch[1] : null;
    const headerCount = seasonMatch ? parseInt(seasonMatch[2], 10) : null;
    // Sibling div is the 3-col grid of player tiles.
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

python3 - "Aus Players 24-25" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)

EXPECTED = [
    ("2025",    18),
    ("2024/25", 11),
    ("2024",    22),
]

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

# Total section count must match expected number of seasons.
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
