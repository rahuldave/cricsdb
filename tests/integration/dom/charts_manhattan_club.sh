#!/bin/bash
# /matches/6018 ManhattanChart per-innings — club anchor.
# IPL 2025 Final (RCB v PBKS).
#
# Same shape as charts_manhattan_intl.sh; uses the
# extract_chart_summary harness to read Semiotic's accessibility
# data summary panel.
#
# RCB:  190/9 → mean 9.50, range 3-23, first 5 = 13/6/11/9/7
# PBKS: 184/7 → mean 9.20, range 3-22, first 5 = 13/10/5/4/11
#
# Numbers verified by independent SQL — see audit/charts_manhattan_club.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/charts_manhattan_club.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/matches/6018" \
  "Anchor — IPL 2025 Final ManhattanChart"
sleep 5

# Innings 1 — RCB.
JSON_RCB=$(extract_chart_summary 1 2>/dev/null)
python3 - "Manhattan RCB" "$JSON_RCB" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

summary = dom.get("summary", "")
check("20 data points" in summary,
      f"[{label}] '20 data points'")
check("3 to 23" in summary,
      f"[{label}] range '3 to 23' (got '{summary}')")
check("mean 9.5" in summary,
      f"[{label}] mean 9.5 (RCB 190/20=9.50)")

EXPECTED = ["13", "6", "11", "9", "7"]
samples = dom.get("samples", [])
check(len(samples) == 5, f"[{label}] 5 sample rows")
for i, exp_runs in enumerate(EXPECTED):
    if i < len(samples):
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

# Innings 2 — PBKS.
JSON_PBKS=$(extract_chart_summary 2 2>/dev/null)
python3 - "Manhattan PBKS" "$JSON_PBKS" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

summary = dom.get("summary", "")
check("20 data points" in summary,
      f"[{label}] '20 data points'")
check("3 to 22" in summary,
      f"[{label}] range '3 to 22' (got '{summary}')")
check("mean 9.2" in summary,
      f"[{label}] mean 9.2 (PBKS 184/20=9.20)")

EXPECTED = ["13", "10", "5", "4", "11"]
samples = dom.get("samples", [])
check(len(samples) == 5, f"[{label}] 5 sample rows")
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
