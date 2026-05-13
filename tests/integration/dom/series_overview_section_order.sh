#!/bin/bash
# Series > Overview — section-order invariant. 2026-05-12 we hoisted
# the "Teams at <X>" chips out of the bottom of the dossier and into
# the headline strip, just after Best moments. Spec-series-trend-charts
# step 10 (2026-05-13) then moved "Run rate by season" and
# "Boundary % by season" OFF Overview to the Series → Batting subtab
# (which carries the full discipline-level chart strip now).
#
#   Best moments  →  Teams at IPL  →  Champions by season
#
# Run rate / Boundary % charts AND Knockouts must NOT appear on
# Overview — first two moved to Batting, last to Editions.
#
# Anchor: IPL (all editions, men's, club) — the marquee dossier with
# Best moments + Teams + trend charts + Champions table all present.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/series_overview_section_order.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club" \
  "Anchor — IPL Overview section order"
sleep 4

agent-browser eval --stdin <<'EVALEOF' > /tmp/overview_order.json
(() => {
  const text = document.body.innerText;
  const ix = (k) => text.indexOf(k);
  return JSON.stringify({
    best_moments:        ix('Best moments'),
    teams_at:            ix('Teams at'),
    run_rate:            ix('Run rate by season'),
    boundary_pct:        ix('Boundary % by season'),
    champions_by_season: ix('Champions by season'),
    knockouts:           ix('Knockouts'),
  });
})()
EVALEOF

python3 - <<'PYEOF'
import json, sys

with open('/tmp/overview_order.json') as fh:
    raw = json.load(fh)
# agent-browser eval wraps the return in JSON string; outer is wrapping again.
ix = json.loads(raw) if isinstance(raw, str) else raw

passes = 0
fails = 0

def present(label, key):
    global passes, fails
    if ix[key] >= 0:
        print(f"  ✓ '{label}' present (index {ix[key]})")
        passes += 1
    else:
        print(f"  ✗ '{label}' missing")
        fails += 1

def before(label_a, key_a, label_b, key_b):
    global passes, fails
    a, b = ix[key_a], ix[key_b]
    if a >= 0 and b >= 0 and a < b:
        print(f"  ✓ '{label_a}' (@{a}) precedes '{label_b}' (@{b})")
        passes += 1
    else:
        print(f"  ✗ '{label_a}' must precede '{label_b}' (got {a}, {b})")
        fails += 1

def absent(label, key):
    global passes, fails
    if ix[key] == -1:
        print(f"  ✓ '{label}' is absent from Overview (correct — moved to Editions)")
        passes += 1
    else:
        print(f"  ✗ '{label}' should be absent but found at index {ix[key]}")
        fails += 1

# All required sections present.
present("Best moments",        "best_moments")
present("Teams at",            "teams_at")
present("Champions by season", "champions_by_season")

# Section order: Best moments → Teams at → Champions by season.
before("Best moments",        "best_moments",        "Teams at",            "teams_at")
before("Teams at",            "teams_at",            "Champions by season", "champions_by_season")

# Run rate + Boundary % charts moved to Series → Batting subtab — must
# NOT appear on Overview.
absent("Run rate by season",   "run_rate")
absent("Boundary % by season", "boundary_pct")

# Knockouts moved to Editions tab — must NOT appear on Overview.
absent("Knockouts", "knockouts")

print()
print("──────────────────────────────────")
print(f"Passed: {passes}  Failed: {fails}")
sys.exit(0 if fails == 0 else 1)
PYEOF
