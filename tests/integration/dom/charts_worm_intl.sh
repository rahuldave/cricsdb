#!/bin/bash
# /matches/1551 WormChart — Semiotic SVG line chart of cumulative
# runs by over (one series per innings).
#
# Worm summaries are POSITION-derived (Semiotic emits x_pixel /
# y_pixel coords for line charts), NOT data-derived. So we can't
# assert the cricket data values here — only that the chart
# rendered with the expected number of data points.
#
# WC 2024 Final has 247 legal balls (India 119 + SA 128 — both
# innings ≤ 20 ov × 6 = 120, minus extras). Each ball is a data
# point on the worm. The summary reports 57 data points for the
# WC 2024 Final at this snapshot — likely Semiotic's downsampled
# point count for rendering. The test asserts the existence /
# point-count to catch the regression class where the worm
# silently fails to render (chart container empty, summary gone).
#
# This is an EXISTENCE-class assertion, not a value assertion.
# Per the spec, chart-DOM testing is fragile — use sparingly.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/charts_worm_intl.sh

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/matches/1551" \
  "Anchor — WC 2024 Final WormChart"
sleep 5

JSON=$(extract_chart_summary 0 2>/dev/null)
python3 - "Worm WC 2024" "$JSON" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

check(dom.get("exists") is True,
      f"[{label}] worm semiotic-table exists")

summary = dom.get("summary", "")
check(summary.startswith("57 data points"),
      f"[{label}] summary starts with '57 data points' (got '{summary[:80]}')")
# Worm summary describes pixel coords (x: 0..1042, y: 29..320 — approx
# canvas-pixel ranges given the 1152×480 SVG). Check the structural
# shape rather than exact values; a font/scale change would shift y
# a tick, but x/y bounds and "data points" count are stable.
check("x:" in summary and "y:" in summary,
      f"[{label}] summary describes both x and y axes")
check("mean" in summary,
      f"[{label}] summary includes mean stat (Semiotic line-chart format)")

# 5 sample rows, each with 3 cells (Line, x_pixel, y_pixel).
samples = dom.get("samples", [])
check(len(samples) == 5,
      f"[{label}] 5 sample rows present")
for i, row in enumerate(samples):
    check(len(row) == 3 and row[0] == "Line point",
          f"[{label}] sample {i} is a 'Line point' row with 3 cells")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
