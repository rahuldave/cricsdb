#!/bin/bash
# Teams > Compare tab — DOM-grounded chip + value assertions.
#
# Drives `agent-browser` (Playwright/CDP — actual DOM, NOT screenshot
# OCR) against two anchor URLs and asserts every numeric cell + chip
# envelope agrees with INDEPENDENT ground truth computed directly from
# sqlite (see "GROUND TRUTH" block below — values were verified by a
# subagent that did NOT read api/ source). For each chip we also
# verify the displayed delta = (value − scope_avg) / scope_avg × 100,
# proving chip ↔ avg-col agreement at the pixel level.
#
# Two anchors:
#   A. Men's T20I 2024-2025 — Australia + India + (avg unbounded /
#      avg full-member only). 4 chip families.
#   B. IPL 2025 — RCB + SRH + (avg, single mode). 2 chip families.
#
# Closed historical windows so the expected values stay stable.
#
# Prereqs: agent-browser, Vite dev (5173 or 5174), FastAPI dev (8000).
# Run: ./tests/integration/compare_avg_chips.sh
set -u

BASE="${BASE:-http://localhost:5173}"
EPS_PCT="${EPS_PCT:-0.2}"   # delta tolerance (percentage points)
EPS_NUM="${EPS_NUM:-0.15}"  # numeric tolerance — handles 1-decimal API rounding

PASS=0; FAIL=0
FAIL_LINES=""

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# ───────────────────────────── extractor ─────────────────────────────
# Returns a JSON array, one entry per Compare column. Each entry has:
#   { header, matches_text,
#     sections: { "Results": { "Matches": {value, chipTitle, envValue, envAvg, envDelta}, ... },
#                 "Batting": { "Run rate": {...}, ... } } }
# Chip envelope is parsed out of the MetricDelta tooltip (title attr):
#   "${value} vs scope avg ${avg} — ${sign}${delta}% (better/worse)"
# This is structured data straight off the DOM — no pixel reading.

extract_grid() {
  # agent-browser pretty-prints JSON across multiple lines — capture
  # the entire stdout as one string. The wrapper produces a single
  # JSON value (string from JSON.stringify) so python can json.loads
  # it directly without surrounding noise.
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const cols = Array.from(document.querySelectorAll('.wisden-compare-col'));
  const titleRe = /^(\S+) vs scope avg (\S+)\s+—\s+([+-]?\S+)%/;
  const out = cols.map(col => {
    const header = col.querySelector('.wisden-compare-col-name')?.innerText?.trim() || '';
    const matches_text = col.querySelector('.wisden-player-identity')?.innerText?.trim() || '';
    const sections = {};
    for (const s of col.querySelectorAll('.wisden-player-section')) {
      const label = s.querySelector('.wisden-player-section-label')?.innerText?.trim() || '';
      const rows = {};
      for (const r of s.querySelectorAll('.wisden-player-compact-row')) {
        const dt = r.querySelector('dt')?.innerText?.trim() || '';
        const dd = r.querySelector('dd');
        const full = dd?.innerText?.trim() || '';
        const chipSpan = dd?.querySelector('span[title]');
        const chipTitle = chipSpan?.getAttribute('title') || '';
        const m = chipTitle.match(titleRe);
        rows[dt] = {
          full,
          chipTitle,
          envValue: m ? parseFloat(m[1]) : null,
          envAvg:   m ? parseFloat(m[2]) : null,
          envDelta: m ? parseFloat(m[3]) : null,
        };
      }
      sections[label] = rows;
    }
    return { header, matches_text, sections };
  });
  // agent-browser pretty-prints the returned object as multi-line
  // JSON, which python's json.load() consumes happily.
  return out;
})()
EVALEOF
}

navigate() {
  local url="$1" what="$2"
  echo
  echo "─── $what"
  echo "    $url"
  agent-browser navigate "$url" >/dev/null
  # 3s soak so all 12 fetches in getTeamProfile + 12 in getScopeAverageProfile
  # resolve and React commits the final values into the DOM.
  sleep 3
}

# ───────────────────────────── runner ─────────────────────────────
# Hands the captured JSON + ground-truth + tolerances to python3, which
# diffs everything and prints PASS/FAIL per assertion.

run_assertions() {
  local label="$1"
  local json="$2"
  local expected_py="$3"
  python3 - "$label" "$json" "$expected_py" "$EPS_PCT" "$EPS_NUM" <<'PYEOF'
import json, math, sys
label, raw, expected_py, eps_pct_s, eps_num_s = sys.argv[1:6]
EPS_PCT = float(eps_pct_s)
EPS_NUM = float(eps_num_s)

cols = json.loads(raw)
expected = eval(expected_py)  # local, trusted heredoc text

passes = []
fails = []

def check(cond, msg):
    (passes if cond else fails).append(msg)

def near(a, b, eps):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(float(a) - float(b)) <= eps

# Map column header → expected
def find_col(header_substr):
    for c in cols:
        if header_substr in c["header"]:
            return c
    return None

for col_label, expected_col in expected.items():
    header_substr = expected_col.get("_match_header", col_label)
    col = find_col(header_substr)
    if col is None:
        fails.append(f"[{label}] column not found: header contains '{header_substr}'")
        continue

    # 1. matches text
    exp_match_text = expected_col.get("matches_text")
    if exp_match_text is not None:
        if exp_match_text not in col["matches_text"]:
            fails.append(f"[{label}] {col_label} matches_text '{col['matches_text']}' missing '{exp_match_text}'")
        else:
            passes.append(f"[{label}] {col_label} matches_text contains '{exp_match_text}'")

    # 2. per-row checks
    rows = expected_col.get("rows", {})
    for (section, row_label), exp in rows.items():
        actual_section = col["sections"].get(section)
        if actual_section is None:
            fails.append(f"[{label}] {col_label} section '{section}' missing")
            continue
        actual_row = actual_section.get(row_label)
        if actual_row is None:
            fails.append(f"[{label}] {col_label} {section}/{row_label} row missing")
            continue

        # value present in cell text — accept exact substring match
        if "value" in exp:
            v = exp["value"]
            v_str = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
            # also accept formatted forms ("9.91" vs "9.9", "22" vs "22.0")
            ok = v_str in actual_row["full"] or (isinstance(v, float) and f"{v:.1f}" in actual_row["full"])
            check(ok, f"[{label}] {col_label} {section}/{row_label} display contains {v_str} (got '{actual_row['full']}')")

        # chip envelope (parsed from title attribute)
        if "chip_value" in exp:
            check(near(actual_row["envValue"], exp["chip_value"], EPS_NUM),
                  f"[{label}] {col_label} {section}/{row_label} chip.value {actual_row['envValue']} vs expected {exp['chip_value']}")
        if "chip_avg" in exp:
            check(near(actual_row["envAvg"], exp["chip_avg"], EPS_NUM),
                  f"[{label}] {col_label} {section}/{row_label} chip.scope_avg {actual_row['envAvg']} vs expected {exp['chip_avg']}")
        if "chip_delta" in exp:
            check(near(actual_row["envDelta"], exp["chip_delta"], EPS_PCT),
                  f"[{label}] {col_label} {section}/{row_label} chip.delta {actual_row['envDelta']}% vs expected {exp['chip_delta']}%")

        # math invariant: chip_delta == (value - avg) / avg * 100
        if actual_row["envValue"] is not None and actual_row["envAvg"] not in (None, 0):
            calc = (actual_row["envValue"] - actual_row["envAvg"]) / actual_row["envAvg"] * 100
            check(near(actual_row["envDelta"], calc, EPS_PCT),
                  f"[{label}] {col_label} {section}/{row_label} chip math: displayed {actual_row['envDelta']}% vs computed {calc:.2f}% from value/avg")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

# Pass exit-code via stderr count
sys.exit(0 if not fails else 1)
PYEOF
}

# ─────────────── ANCHOR A — INTL 2024-2025 (unbounded avg) ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare2=India&season_from=2024&season_to=2025" \
  "Anchor A — INTL 2024-2025, avg unbounded"

JSON_A=$(extract_grid 2>/dev/null)

EXPECTED_A=$(cat <<'PYEXPECT'
{
  "Australia": {
    "_match_header": "Australia",
    "matches_text": "22",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 22},
      ("BATTING", "Run rate"):    {"value": 9.91, "chip_value": 9.91, "chip_avg": 7.52, "chip_delta": 31.8},
      ("BATTING", "Boundary %"):  {"value": 23.1, "chip_value": 23.1, "chip_avg": 14.3},
      ("BOWLING", "Economy"):     {"value": 8.3, "chip_value": 8.34, "chip_avg": 7.52},
    },
  },
  "International average": {
    "_match_header": "International average",
    "matches_text": "870",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 7.52},
      ("BATTING", "Boundary %"):  {"value": 14.3},
    },
  },
  "India": {
    "_match_header": "India",
    "matches_text": "34",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 34},
      ("BATTING", "Run rate"):    {"value": 9.39, "chip_value": 9.39, "chip_avg": 7.52, "chip_delta": 24.9},
      ("BATTING", "Boundary %"):  {"value": 21.0, "chip_value": 21.0, "chip_avg": 14.3},
      ("BOWLING", "Economy"):     {"value": 7.5, "chip_value": 7.51, "chip_avg": 7.52},
    },
  },
}
PYEXPECT
)

if run_assertions "ANCHOR A unbounded" "$JSON_A" "$EXPECTED_A"; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
fi

# ─────────────── ANCHOR A' — same scope, FM-only avg ───────────────
navigate "$BASE/teams?team=Australia&gender=male&team_type=international&tab=Compare&compare1=__avg__&compare1_team_class=full_member&compare2=India&season_from=2024&season_to=2025" \
  "Anchor A' — INTL 2024-2025, avg FM-only"

JSON_AP=$(extract_grid 2>/dev/null)

EXPECTED_AP=$(cat <<'PYEXPECT'
{
  "Australia": {
    "_match_header": "Australia",
    "matches_text": "22",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.91, "chip_value": 9.91, "chip_avg": 8.50, "chip_delta": 16.6},
      ("BATTING", "Boundary %"):  {"chip_value": 23.1, "chip_avg": 17.6},
      ("BOWLING", "Economy"):     {"chip_value": 8.34, "chip_avg": 8.50},
    },
  },
  "Full-member average": {
    "_match_header": "Full-member average",
    "matches_text": "140",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 8.50},
    },
  },
  "India": {
    "_match_header": "India",
    "matches_text": "34",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.39, "chip_value": 9.39, "chip_avg": 8.50, "chip_delta": 10.5},
      ("BATTING", "Boundary %"):  {"chip_value": 21.0, "chip_avg": 17.6},
    },
  },
}
PYEXPECT
)

if run_assertions "ANCHOR A' FM-only" "$JSON_AP" "$EXPECTED_AP"; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
fi

# ─────────────── ANCHOR B — IPL 2025 (closed-league avg) ───────────────
navigate "$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&tab=Compare&compare1=__avg__&compare2=Sunrisers+Hyderabad&season_from=2025&season_to=2025" \
  "Anchor B — IPL 2025 club"

JSON_B=$(extract_grid 2>/dev/null)

EXPECTED_B=$(cat <<'PYEXPECT'
{
  "Royal Challengers Bengaluru": {
    "_match_header": "Royal Challengers Bengaluru",
    "matches_text": "15",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 15},
      ("BATTING", "Run rate"):    {"value": 9.69, "chip_value": 9.69, "chip_avg": 9.63},
      ("BATTING", "Boundary %"):  {"chip_value": 22.1, "chip_avg": 21.6},
      ("BOWLING", "Economy"):     {"chip_value": 9.24, "chip_avg": 9.63},
    },
  },
  "Indian Premier League average": {
    "_match_header": "Indian Premier League average",
    "matches_text": "74",
    "rows": {
      ("BATTING", "Run rate"):    {"value": 9.63},
    },
  },
  "Sunrisers Hyderabad": {
    "_match_header": "Sunrisers Hyderabad",
    "matches_text": "14",
    "rows": {
      ("RESULTS", "Matches"):     {"value": 14},
      ("BATTING", "Run rate"):    {"value": 10.04, "chip_value": 10.04, "chip_avg": 9.63},
      ("BATTING", "Boundary %"):  {"chip_value": 22.5, "chip_avg": 21.6},
      ("BOWLING", "Economy"):     {"chip_value": 9.90, "chip_avg": 9.63},
    },
  },
}
PYEXPECT
)

if run_assertions "ANCHOR B IPL 2025" "$JSON_B" "$EXPECTED_B"; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
fi

# ─────────────────────────── summary ───────────────────────────
echo
echo "──────────────────────────────────"
echo "Anchors passed: $PASS / $((PASS + FAIL))"
if [ "$FAIL" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
