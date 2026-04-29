#!/bin/bash
# Cross-cutting consistency anchor — chip alignment under SLOT-OVERRIDE
# BROADEN-DIRECTION. Sibling of cross_cutting_team_class_consistency.sh
# which exercises the narrowing-direction case.
#
# Anchor: RCB primary 2025 (men's club) with an avg slot that overrides
# season_from + season_to to the __any__ sentinel — the avg column
# displays IPL all-time (scope_to_team=RCB auto-narrow + season-broad).
#
# Two assertion flavors mirror the team_class consistency test:
#
#   • CHIP ALIGNMENT (S1):  RCB 2025 col's chip scope_avg for
#     run_rate / boundary_pct numerically equals the avg col's
#     displayed value for the SAME metrics. Math invariant —
#     `chip_baseline_scope_json` must propagate the avg slot's scope
#     to the team col's league-side baseline. Failure here = chip
#     reads contradicts the avg-col number a column over.
#
#   • SENSITIVITY (S2):  Same scope WITHOUT the __any__ overrides
#     should yield a NARROWER chip baseline (RCB 2025 IPL avg, not
#     IPL all-time). The two scope_avg values must differ — proves
#     the override flows through the URL → scope → backend → chip
#     path end-to-end.
#
# Numbers derived from the API (chip alignment is a math invariant —
# the test asserts EQUALITY between two values from the rendered DOM,
# not absolute values that drift across DB rebuilds).
#
# Spec: internal_docs/spec-slot-override-chip-alignment.md §7.4.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/cross_cutting_slot_override_chip_align.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── S1 — broaden-direction chip alignment ───────────────
# RCB 2025 + avg slot with both seasons overridden to __any__ →
# avg col displays IPL all-time, RCB chips MUST baseline against same.
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&season_from=2025&season_to=2025&tab=Compare&compare1=__avg__&compare1_season_from=__any__&compare1_season_to=__any__" \
  "S1 — RCB 2025 + avg slot season=__any__"

JSON_S1=$(extract_grid 2>/dev/null)

# Pull the avg col's displayed values + RCB col's chip envelopes
# entirely from the rendered DOM, then assert numeric equality.
python3 - <<PY
import json, sys

EPS = 0.15

cols = json.loads('''$JSON_S1''')
by_header = {c["header"]: c for c in cols}

rcb = None; avg = None
for h, c in by_header.items():
    if "Royal Challengers Bengaluru" in h:
        rcb = c
    elif "average" in h.lower() or "Premier League" in h:
        avg = c

if not rcb or not avg:
    print(f"FAIL: missing column. Headers: {list(by_header.keys())}")
    sys.exit(1)

errors = []

# Walk the BATTING section. avg col's displayed run_rate / boundary_pct
# vs RCB col's chip scope_avg for the same metrics.
def avg_displayed(metric_label):
    row = avg.get("sections", {}).get("BATTING", {}).get(metric_label, {})
    full = row.get("full", "")
    # avg cells render as bare numbers like "8.42" or "17.5%". Strip %
    # and parse.
    s = full.replace("%", "").strip()
    # First numeric token
    import re
    m = re.search(r"[-+]?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None

def chip_scope_avg(metric_label):
    row = rcb.get("sections", {}).get("BATTING", {}).get(metric_label, {})
    return row.get("envAvg")

for metric in ("Run rate", "Boundary %"):
    a = avg_displayed(metric)
    c = chip_scope_avg(metric)
    if a is None:
        errors.append(f"S1: avg col missing display value for {metric!r}")
        continue
    if c is None:
        errors.append(f"S1: RCB col missing chip scope_avg for {metric!r}")
        continue
    if abs(a - c) > EPS:
        errors.append(f"S1 BROKE: {metric!r} avg.displayed={a} ≠ RCB.chip.scope_avg={c}")
    else:
        print(f"  ✓ S1 {metric}: avg.displayed={a} == RCB.chip.scope_avg={c}")

if errors:
    print()
    for e in errors: print(f"  ✗ {e}")
    sys.exit(1)
print("=== S1 PASS — chip alignment matches avg col under broaden override ===")
PY
record_result $?

# ─────────────── S2 — sensitivity: NO __any__, narrower chip baseline ───────────────
# Same primary scope, avg slot inherits primary's season → IPL 2025 only.
# RCB chip's scope_avg should DIFFER from S1 (narrower pool).
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&season_from=2025&season_to=2025&tab=Compare&compare1=__avg__" \
  "S2 — RCB 2025 + avg slot inheriting (no __any__) — chip baseline narrower"

JSON_S2=$(extract_grid 2>/dev/null)

python3 - <<PY
import json, sys

EPS = 0.15

cols_s1 = json.loads('''$JSON_S1''')
cols_s2 = json.loads('''$JSON_S2''')

def chip_scope_avg(cols, metric_label):
    for c in cols:
        if "Royal Challengers Bengaluru" in c["header"]:
            return c.get("sections", {}).get("BATTING", {}).get(metric_label, {}).get("envAvg")
    return None

errors = []
for metric in ("Run rate", "Boundary %"):
    s1 = chip_scope_avg(cols_s1, metric)
    s2 = chip_scope_avg(cols_s2, metric)
    if s1 is None or s2 is None:
        errors.append(f"S2: missing chip scope_avg for {metric!r} (s1={s1}, s2={s2})")
        continue
    if abs(s1 - s2) <= EPS:
        errors.append(
            f"S2 INSENSITIVE: {metric!r} chip baseline didn't change between "
            f"__any__ broaden ({s1}) and inherit-primary ({s2}) — override "
            f"isn't propagating through to the chip's scope_avg."
        )
    else:
        print(f"  ✓ S2 {metric}: chip baseline shifted s1={s1} → s2={s2} ({abs(s1-s2):.2f} delta)")

if errors:
    print()
    for e in errors: print(f"  ✗ {e}")
    sys.exit(1)
print("=== S2 PASS — chip baseline IS sensitive to __any__ override ===")
PY
record_result $?

print_summary
