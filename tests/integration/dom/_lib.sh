# Shared library for tests/integration/dom/ scripts.
#
# DOM-grounded numeric assertions: drives `agent-browser` (Playwright/CDP
# — actual DOM, NOT screenshot OCR) against an anchor URL, walks the
# rendered DOM via JS, and diffs against an INDEPENDENT ground-truth
# dict (computed from sqlite, NOT the API code path under test).
#
# Source from each test:
#   source "$(dirname "$0")/_lib.sh"
#
# Then call:
#   navigate URL "what"
#   JSON=$(extract_grid)            # for /teams?...&tab=Compare
#   JSON=$(extract_data_table)      # for DataTable surfaces
#   JSON=$(extract_landing_tiles)   # for /series, /teams landings
#   run_assertions "label" "$JSON" "$EXPECTED_PY"
#   print_summary
#
# Conventions: closed historical anchor windows so values stay stable
# across DB rebuilds; if cricsheet retroactively edits the window, the
# script fails noisily — investigate via update_recent.py --dry-run,
# update the script's expected dict, commit.

set -u

BASE="${BASE:-http://localhost:5173}"
EPS_PCT="${EPS_PCT:-0.2}"   # delta tolerance (percentage points)
EPS_NUM="${EPS_NUM:-0.15}"  # numeric tolerance — 1-decimal API rounding

PASS=0; FAIL=0

# Reset agent-browser so previous-test DOM doesn't leak in.
agent-browser close --all >/dev/null 2>&1 || true
sleep 1

navigate() {
  local url="$1" what="$2"
  echo
  echo "─── $what"
  echo "    $url"
  agent-browser navigate "$url" >/dev/null
  # 3s soak so all async fetches resolve and React commits final values
  # into the DOM before we extract. compare_avg_chips.sh's empirical
  # baseline — 12 fetches per Compare slot + 12 for the avg endpoint.
  sleep 3
}

# ─────────────────────────── EXTRACTOR: compare grid ───────────────────────────
# For /teams?...&tab=Compare. Returns array, one entry per Compare column:
#   { header, matches_text, sections: { sectionLabel: { rowLabel: {full, chipTitle, envValue, envAvg, envDelta} } } }
extract_grid() {
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
  return out;
})()
EVALEOF
}

# ─────────────────────────── EXTRACTOR: DataTable ───────────────────────────
# For tabular surfaces (Match List, leaderboards, partnerships top-N).
# Returns: { headers: [str], rows: [[cell_text, ...]], total_rows: N,
#            total_label: "Showing M of N" or "N rows" }
extract_data_table() {
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  // Take the first DataTable on the page. If a page has multiple,
  // tests should narrow with a more specific selector wrapper.
  const tbl = document.querySelector('.wisden-table, table.data-table, table');
  if (!tbl) return { error: 'no table found' };

  const headers = Array.from(tbl.querySelectorAll('thead th')).map(
    th => th.innerText.trim()
  );
  const rows = Array.from(tbl.querySelectorAll('tbody tr')).map(tr =>
    Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
  );

  // "Showing N–M of T" lives under .wisden-pagination (DataTable.tsx).
  const totalEl = document.querySelector(
    '.wisden-pagination, .wisden-table-meta, .data-table-footer, .table-footer'
  );
  const total_label = totalEl?.innerText?.trim() || '';

  return { headers, rows, total_rows: rows.length, total_label };
})()
EVALEOF
}

# ─────────────────────────── EXTRACTOR: landing tiles ───────────────────────────
# For /series (TournamentsLanding) — sectioned tile directory.
# DOM:
#   .wisden-landing-section
#     > h3.wisden-section-title             ← section label
#     > .wisden-tile-grid
#         > .wisden-tile.tile-wrapper       ← one tile
#             > a.tile-stretched            ← stretched-link primary
#             > .wisden-tile-title          ← canonical name
#             > .wisden-tile-sub            ← "N editions · M matches" or "M matches"
#             > .wisden-tile-line           ← repeated stat lines
# Returns: { sections: [{ label, tiles: [{ name, matches, sub, href }] }] }
extract_landing_tiles() {
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const sections = [];
  const sectionEls = document.querySelectorAll('.wisden-landing-section');
  const matchesRe = /(\d[\d,]*)\s*match/;

  for (const sec of sectionEls) {
    const label = sec.querySelector('.wisden-section-title, h2, h3')
      ?.innerText?.trim() || '';
    const tiles = Array.from(sec.querySelectorAll('.wisden-tile')).map(t => {
      const name = t.querySelector('.wisden-tile-title')
        ?.innerText?.trim().replace(/\s+/g, ' ') || '';
      const sub = t.querySelector('.wisden-tile-sub')
        ?.innerText?.trim() || '';
      const stretched = t.querySelector('a.tile-stretched');
      const m = sub.match(matchesRe);
      const matches = m ? parseInt(m[1].replace(/,/g, ''), 10) : null;
      return {
        name,
        matches,
        sub,
        href: stretched?.getAttribute('href') || '',
      };
    });
    sections.push({ label, tiles });
  }

  return { sections };
})()
EVALEOF
}

# ─────────────────────────── EXTRACTOR: team overview ───────────────────────────
# For /teams?team=X (default tab "By Season" — the always-on summary
# band rendered above every tab). DOM:
#   h2.wisden-page-title          ← team name
#   .wisden-statrow > .wisden-stat ← StatCard entries (Matches, Wins, etc.)
#       > .wisden-stat-label       ← "Matches"
#       > .wisden-stat-value       ← "22"
#       > .wisden-stat-sub         ← optional <MetricDelta> chip
#           > span[title]          ← "${value} vs scope avg ${avg} — ±${delta}%"
#   p.wisden-tab-help              ← keepers list (when present)
#       > a.comp-link              ← per-keeper link
# Returns: { team_name, stats: {label: {value, chipTitle, envValue, envAvg, envDelta}}, keepers: [...] }
extract_team_overview() {
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const titleRe = /^(\S+) vs scope avg (\S+)\s+—\s+([+-]?\S+)%/;
  const team_name = document.querySelector('.wisden-page-title')
    ?.innerText?.trim().split('\n')[0] || '';

  const stats = {};
  for (const card of document.querySelectorAll('.wisden-statrow .wisden-stat')) {
    const label = card.querySelector('.wisden-stat-label')?.innerText?.trim() || '';
    const value = card.querySelector('.wisden-stat-value')?.innerText?.trim() || '';
    const chipSpan = card.querySelector('.wisden-stat-sub span[title]');
    const chipTitle = chipSpan?.getAttribute('title') || '';
    const m = chipTitle.match(titleRe);
    stats[label] = {
      value,
      chipTitle,
      envValue: m ? parseFloat(m[1]) : null,
      envAvg:   m ? parseFloat(m[2]) : null,
      envDelta: m ? parseFloat(m[3]) : null,
    };
  }

  // Keepers paragraph: find the <p> whose first child <span> reads
  // "Keepers used:". Each keeper is name + " (" + innings + ")".
  const keepers = [];
  const keeperP = Array.from(document.querySelectorAll('p.wisden-tab-help')).find(p =>
    p.innerText.startsWith('Keepers used:')
  );
  if (keeperP) {
    for (const a of keeperP.querySelectorAll('a.comp-link')) {
      const name = a.innerText.trim();
      // The "(N)" innings count lives in the next sibling span.
      const sib = a.nextSibling;
      const sibText = sib ? (sib.textContent || '') : '';
      // Find the span after this anchor with the (N) text.
      let count = null;
      let n = a.nextElementSibling;
      if (n && n.tagName === 'SPAN') {
        const m = n.innerText.match(/\((\d+)\)/);
        if (m) count = parseInt(m[1], 10);
      }
      keepers.push({ name, innings_kept: count });
    }
  }

  return { team_name, stats, keepers };
})()
EVALEOF
}

# ─────────────────────────── ASSERT RUNNER: team overview ───────────────────────────
# Expected dict shape:
#   {
#       "team_name": "Australia",        # exact match on page-title
#       "stats": {
#           "Matches": {"value": "22"},  # value substring match
#           "Wins": {"value": "19"},
#           "Win %": {                   # value + chip envelope
#               "value": "86.4%",
#               "chip_value": 86.4,
#               "chip_avg": 48.45,
#               "chip_delta": 78.3,
#           },
#       },
#       "min_keepers": 0,                # optional — assert at least N keepers rendered
#   }
run_team_overview_assertions() {
  local label="$1"
  local json="$2"
  local expected_py="$3"
  python3 - "$label" "$json" "$expected_py" "$EPS_PCT" "$EPS_NUM" <<'PYEOF'
import json, sys
label, raw, expected_py, eps_pct_s, eps_num_s = sys.argv[1:6]
EPS_PCT = float(eps_pct_s)
EPS_NUM = float(eps_num_s)

dom = json.loads(raw)
expected = eval(expected_py)

passes, fails = [], []
def check(cond, msg):
    (passes if cond else fails).append(msg)

def near(a, b, eps):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(float(a) - float(b)) <= eps

exp_team = expected.get("team_name")
if exp_team is not None:
    check(exp_team in dom["team_name"],
          f"[{label}] team_name '{dom['team_name']}' contains '{exp_team}'")

for stat_label, exp in expected.get("stats", {}).items():
    actual = dom["stats"].get(stat_label)
    if actual is None:
        fails.append(f"[{label}] stat '{stat_label}' missing from page")
        continue
    if "value" in exp:
        check(exp["value"] in actual["value"],
              f"[{label}] stat '{stat_label}' value '{actual['value']}' contains '{exp['value']}'")
    if "chip_value" in exp:
        check(near(actual["envValue"], exp["chip_value"], EPS_NUM),
              f"[{label}] stat '{stat_label}' chip.value {actual['envValue']} vs expected {exp['chip_value']}")
    if "chip_avg" in exp:
        check(near(actual["envAvg"], exp["chip_avg"], EPS_NUM),
              f"[{label}] stat '{stat_label}' chip.scope_avg {actual['envAvg']} vs expected {exp['chip_avg']}")
    if "chip_delta" in exp:
        check(near(actual["envDelta"], exp["chip_delta"], EPS_PCT),
              f"[{label}] stat '{stat_label}' chip.delta {actual['envDelta']}% vs expected {exp['chip_delta']}%")
    # Math invariant for chip-bearing stats.
    if actual["envValue"] is not None and actual["envAvg"] not in (None, 0):
        calc = (actual["envValue"] - actual["envAvg"]) / actual["envAvg"] * 100
        check(near(actual["envDelta"], calc, EPS_PCT),
              f"[{label}] stat '{stat_label}' chip math: displayed {actual['envDelta']}% vs computed {calc:.2f}% from value/avg")

if "min_keepers" in expected:
    n = expected["min_keepers"]
    check(len(dom["keepers"]) >= n,
          f"[{label}] keepers count {len(dom['keepers'])} >= {n}")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
}

# ─────────────────────────── ASSERT RUNNER ───────────────────────────
# Diffs the extracted JSON against an expected python-literal dict.
# Expected dict shape for compare grid:
#   {
#     "ColLabel": {
#       "_match_header": "substring",        # which DOM column to match
#       "matches_text": "<substring>",       # optional identity-line check
#       "rows": {
#         (section, row_label): {
#           "value": <num>,                  # display text contains
#           "chip_value": <num>,             # MetricDelta env.value
#           "chip_avg": <num>,               # MetricDelta env.scope_avg
#           "chip_delta": <num>,             # MetricDelta env.delta_pct (optional)
#         }, ...
#       }
#     }, ...
#   }
#
# Asserts each cell + the math invariant
# (delta = (value − avg) / avg × 100 ± EPS_PCT).
run_assertions() {
  local label="$1"
  local json="$2"
  local expected_py="$3"
  python3 - "$label" "$json" "$expected_py" "$EPS_PCT" "$EPS_NUM" <<'PYEOF'
import json, sys
label, raw, expected_py, eps_pct_s, eps_num_s = sys.argv[1:6]
EPS_PCT = float(eps_pct_s)
EPS_NUM = float(eps_num_s)

cols = json.loads(raw)
expected = eval(expected_py)

passes, fails = [], []

def check(cond, msg):
    (passes if cond else fails).append(msg)

def near(a, b, eps):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(float(a) - float(b)) <= eps

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

    exp_match_text = expected_col.get("matches_text")
    if exp_match_text is not None:
        if exp_match_text not in col["matches_text"]:
            fails.append(f"[{label}] {col_label} matches_text '{col['matches_text']}' missing '{exp_match_text}'")
        else:
            passes.append(f"[{label}] {col_label} matches_text contains '{exp_match_text}'")

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

        if "value" in exp:
            v = exp["value"]
            v_str = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
            ok = v_str in actual_row["full"] or (isinstance(v, float) and f"{v:.1f}" in actual_row["full"])
            check(ok, f"[{label}] {col_label} {section}/{row_label} display contains {v_str} (got '{actual_row['full']}')")

        if "chip_value" in exp:
            check(near(actual_row["envValue"], exp["chip_value"], EPS_NUM),
                  f"[{label}] {col_label} {section}/{row_label} chip.value {actual_row['envValue']} vs expected {exp['chip_value']}")
        if "chip_avg" in exp:
            check(near(actual_row["envAvg"], exp["chip_avg"], EPS_NUM),
                  f"[{label}] {col_label} {section}/{row_label} chip.scope_avg {actual_row['envAvg']} vs expected {exp['chip_avg']}")
        if "chip_delta" in exp:
            check(near(actual_row["envDelta"], exp["chip_delta"], EPS_PCT),
                  f"[{label}] {col_label} {section}/{row_label} chip.delta {actual_row['envDelta']}% vs expected {exp['chip_delta']}%")

        # Math invariant: delta = (value - avg) / avg × 100
        if actual_row["envValue"] is not None and actual_row["envAvg"] not in (None, 0):
            calc = (actual_row["envValue"] - actual_row["envAvg"]) / actual_row["envAvg"] * 100
            check(near(actual_row["envDelta"], calc, EPS_PCT),
                  f"[{label}] {col_label} {section}/{row_label} chip math: displayed {actual_row['envDelta']}% vs computed {calc:.2f}% from value/avg")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
}

# ─────────────────────────── ASSERT RUNNER: data table ───────────────────────────
# For DataTable surfaces — match list, leaderboards, partnerships top-N.
# Expected dict shape:
#   {
#     "expected_total_rows": <int>,           # tbody tr count
#     "total_label_contains": "<substring>",  # optional, e.g. "16 of 16"
#     "row_assertions": [                     # zero-indexed row, exact cell text checks
#       (0, [("col_idx", "expected substring"), ...]),
#       (15, [...]),                          # last-row check
#     ]
#   }
run_data_table_assertions() {
  local label="$1"
  local json="$2"
  local expected_py="$3"
  python3 - "$label" "$json" "$expected_py" <<'PYEOF'
import json, sys
label, raw, expected_py = sys.argv[1:4]

dom = json.loads(raw)
expected = eval(expected_py)

passes, fails = [], []

def check(cond, msg):
    (passes if cond else fails).append(msg)

if dom.get("error"):
    fails.append(f"[{label}] extractor error: {dom['error']}")
else:
    actual_rows = dom["rows"]

    expected_total = expected.get("expected_total_rows")
    if expected_total is not None:
        check(dom["total_rows"] == expected_total,
              f"[{label}] total_rows {dom['total_rows']} == {expected_total}")

    label_substr = expected.get("total_label_contains")
    if label_substr is not None:
        check(label_substr in dom["total_label"],
              f"[{label}] total_label '{dom['total_label']}' contains '{label_substr}'")

    for row_idx, cell_assertions in expected.get("row_assertions", []):
        if row_idx >= len(actual_rows):
            fails.append(f"[{label}] row {row_idx} out of range (have {len(actual_rows)})")
            continue
        row = actual_rows[row_idx]
        for col_idx, expected_substr in cell_assertions:
            if col_idx >= len(row):
                fails.append(f"[{label}] row {row_idx} col {col_idx} out of range (have {len(row)})")
                continue
            cell = row[col_idx]
            check(expected_substr in cell,
                  f"[{label}] row {row_idx} col {col_idx} '{cell}' contains '{expected_substr}'")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
}

# ─────────────────────────── ASSERT RUNNER: landing tiles ───────────────────────────
# Expected dict shape:
#   {
#     "tile_assertions": [
#       ("name substring", expected_matches),    # tile MUST exist + count matches
#     ],
#     "absent_tiles": [                           # tile MUST NOT exist
#       "name substring",
#     ],
#     "section_min_tiles": [                      # optional
#       ("section label substring", min_tile_count),
#     ],
#   }
run_landing_assertions() {
  local label="$1"
  local json="$2"
  local expected_py="$3"
  python3 - "$label" "$json" "$expected_py" <<'PYEOF'
import json, sys
label, raw, expected_py = sys.argv[1:4]

dom = json.loads(raw)
expected = eval(expected_py)

passes, fails = [], []

def check(cond, msg):
    (passes if cond else fails).append(msg)

all_tiles = [t for s in dom["sections"] for t in s["tiles"]]

for name_substr, exp_matches in expected.get("tile_assertions", []):
    found = [t for t in all_tiles if name_substr in t["name"]]
    if not found:
        fails.append(f"[{label}] tile '{name_substr}' not found")
        continue
    t = found[0]
    check(t["matches"] == exp_matches,
          f"[{label}] tile '{name_substr}' matches {t['matches']} == {exp_matches} (sub='{t['sub']}')")

for name_substr in expected.get("absent_tiles", []):
    found = [t for t in all_tiles if name_substr in t["name"]]
    check(not found,
          f"[{label}] tile '{name_substr}' must be absent (got {len(found)})")

for sec_substr, min_tiles in expected.get("section_min_tiles", []):
    secs = [s for s in dom["sections"] if sec_substr in s["label"]]
    if not secs:
        fails.append(f"[{label}] section '{sec_substr}' not found")
        continue
    s = secs[0]
    check(len(s["tiles"]) >= min_tiles,
          f"[{label}] section '{sec_substr}' has {len(s['tiles'])} tiles >= {min_tiles}")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes:
    print(f"  ✓ {p}")
for f in fails:
    print(f"  ✗ {f}")

sys.exit(0 if not fails else 1)
PYEOF
}

# ─────────────────────────── BOOKKEEPING ───────────────────────────
record_result() {
  if [ "$1" -eq 0 ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
}

print_summary() {
  echo
  echo "──────────────────────────────────"
  echo "Anchors passed: $PASS / $((PASS + FAIL))"
  if [ "$FAIL" -ne 0 ]; then
    echo "FAIL"
    exit 1
  fi
  echo "PASS"
}
