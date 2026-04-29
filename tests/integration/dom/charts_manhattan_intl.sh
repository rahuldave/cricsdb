#!/bin/bash
# /matches/1551 ManhattanChart per-innings — Semiotic SVG bar chart.
# Anchor: WC 2024 Final (India v South Africa).
#
# Asserted via the Semiotic accessibility data summary panel (NOT
# SVG-positional text labels — those are fragile). See
# extract_chart_summary in _lib.sh for harness rationale.
#
# DOM has 3 semiotic-table containers in order:
#   ordinal 0 — WormChart (line, position-derived → not asserted here)
#   ordinal 1 — ManhattanChart innings 1 (India)
#   ordinal 2 — ManhattanChart innings 2 (South Africa)
#
# India:        Mean 8.8/over, range 3-17, first 5 = 15/8/3/6/7.
# South Africa: Mean 8.45/over, range 2-24, first 5 = 6/5/3/8/10.
#
# Numbers verified by independent SQL — see audit/charts_intl.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/charts_manhattan_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/matches/1551" \
  "Anchor — WC 2024 Final ManhattanChart"
sleep 5

# Innings 1 — India.
JSON_IND=$(extract_chart_summary 1 2>/dev/null)
python3 - "Manhattan India" "$JSON_IND" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

check(dom.get("exists") is True,
      f"[{label}] semiotic-table exists")
summary = dom.get("summary", "")
check("20 data points" in summary,
      f"[{label}] summary says '20 data points' (got '{summary}')")
check("3 to 17" in summary,
      f"[{label}] summary range '3 to 17' (got '{summary}')")
check("mean 8.8" in summary,
      f"[{label}] summary mean 8.8 (India 176/20=8.80)")

# First 5 over runs in audit order: 15, 8, 3, 6, 7.
EXPECTED = ["15", "8", "3", "6", "7"]
samples = dom.get("samples", [])
check(len(samples) == 5,
      f"[{label}] 5 sample rows (got {len(samples)})")
for i, exp_runs in enumerate(EXPECTED):
    if i < len(samples):
        # row format: ['Bar', '<over>', '<runs>']
        check(samples[i][1] == str(i+1),
              f"[{label}] sample {i} category = over {i+1}")
        check(samples[i][2] == exp_runs,
              f"[{label}] over {i+1} runs = {exp_runs} (got '{samples[i][2]}')")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

# Innings 2 — South Africa.
JSON_SA=$(extract_chart_summary 2 2>/dev/null)
python3 - "Manhattan SA" "$JSON_SA" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

summary = dom.get("summary", "")
check("20 data points" in summary,
      f"[{label}] summary says '20 data points'")
check("2 to 24" in summary,
      f"[{label}] summary range '2 to 24' (got '{summary}')")
check("mean 8.45" in summary,
      f"[{label}] summary mean 8.45 (SA 169/20=8.45)")

EXPECTED = ["6", "5", "3", "8", "10"]
samples = dom.get("samples", [])
check(len(samples) == 5,
      f"[{label}] 5 sample rows")
for i, exp_runs in enumerate(EXPECTED):
    if i < len(samples):
        check(samples[i][2] == exp_runs,
              f"[{label}] over {i+1} runs = {exp_runs} (got '{samples[i][2]}')")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
