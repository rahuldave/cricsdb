#!/bin/bash
# /matches/:matchId scorecard — highlight + auto-scroll behavior.
# Anchor: WC 2024 Final (match_id=1551).
#
# The Batting/Bowling/Fielding pages link to the scorecard with a
# ?highlight_<role>=<person_id> param so cmd/ctrl-clicking from
# an innings list opens the scorecard already pinned to the right
# row. Per CLAUDE.md "Scorecard highlight auto-scroll", the scroll
# is page-level (NOT per-InningsCard) and waits for sibling async
# sections (WormChart / InningsGridChart / MatchupGridChart) to
# settle via a double rAF before firing.
#
# Three sub-anchors:
#
#   ?highlight_batter=ba607b88
#     → V Kohli's row in India batting card has class .is-highlighted
#     → page scrolled (scrollY > 0)
#
#   ?highlight_bowler=462411b3
#     → JJ Bumrah's row in SA bowling card highlighted
#     → page scrolled
#
#   ?highlight_fielder=271f83cd  (SA Yadav)
#     → TWO rows tinted: DA Miller + K Rabada (both caught by Yadav
#       off HH Pandya in the final over — including the famous
#       boundary catch on Miller). The fielder-credit join attribution
#       lights up every dismissal where the named fielder appears in
#       fieldingcredit.
#     → page scrolled
#
# This test is the keystone for the scorecard's auto-scroll
# workaround — if the scroll fires before sibling charts settle,
# scrollY ends up at 0 (scroll target out of viewport).
#
# Numbers verified by independent SQL — see
# audit/matches_scorecard_highlight.sql.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/matches_scorecard_highlight.sh

source "$(dirname "$0")/_lib.sh"

# ─────────────── ANCHOR 1 — highlight_batter ───────────────
navigate "$BASE/matches/1551?highlight_batter=ba607b88" \
  "Anchor 1 — highlight_batter=Kohli (1551)"
sleep 5

H1=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const rows = Array.from(document.querySelectorAll('tr.is-highlighted')).map(tr => ({
    cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()).slice(0, 4),
  }));
  return { count: rows.length, rows, scrollY: window.scrollY };
})()
EVALEOF
)

python3 - "highlight_batter" "$H1" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

check(dom["count"] == 1, f"[{label}] highlighted row count {dom['count']} == 1")
if dom["rows"]:
    cells = dom["rows"][0]["cells"]
    check("V Kohli" in cells[0],   f"[{label}] highlighted row[0] '{cells[0]}' == V Kohli")
    check("76" in cells[2],        f"[{label}] highlighted row runs '{cells[2]}' contains '76'")
    check("59" in cells[3],        f"[{label}] highlighted row balls '{cells[3]}' contains '59'")
check(dom["scrollY"] > 0, f"[{label}] page auto-scrolled (scrollY={dom['scrollY']} > 0)")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

# ─────────────── ANCHOR 2 — highlight_bowler ───────────────
navigate "$BASE/matches/1551?highlight_bowler=462411b3" \
  "Anchor 2 — highlight_bowler=Bumrah (1551)"
sleep 5

H2=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const rows = Array.from(document.querySelectorAll('tr.is-highlighted')).map(tr => ({
    cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()).slice(0, 5),
  }));
  return { count: rows.length, rows, scrollY: window.scrollY };
})()
EVALEOF
)

python3 - "highlight_bowler" "$H2" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

check(dom["count"] == 1, f"[{label}] highlighted row count {dom['count']} == 1")
if dom["rows"]:
    cells = dom["rows"][0]["cells"]
    check("JJ Bumrah" in cells[0], f"[{label}] highlighted bowler '{cells[0]}' == JJ Bumrah")
    check("4.0" in cells[1],       f"[{label}] overs '{cells[1]}' contains '4.0'")
    check("19" in cells[3],        f"[{label}] runs '{cells[3]}' contains '19'")
    check("2" in cells[4],         f"[{label}] wickets '{cells[4]}' contains '2'")
check(dom["scrollY"] > 0, f"[{label}] page auto-scrolled (scrollY={dom['scrollY']} > 0)")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

# ─────────────── ANCHOR 3 — highlight_fielder ───────────────
navigate "$BASE/matches/1551?highlight_fielder=271f83cd" \
  "Anchor 3 — highlight_fielder=SA Yadav (1551)"
sleep 5

H3=$(agent-browser eval --stdin <<'EVALEOF' 2>/dev/null
(() => {
  const rows = Array.from(document.querySelectorAll('tr.is-highlighted')).map(tr => ({
    cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()).slice(0, 4),
  }));
  return { count: rows.length, rows, scrollY: window.scrollY };
})()
EVALEOF
)

python3 - "highlight_fielder" "$H3" <<'PYEOF'
import json, sys
label, raw = sys.argv[1:3]
dom = json.loads(raw)
passes, fails = [], []
def check(cond, msg): (passes if cond else fails).append(msg)

# Yadav took 2 catches (Miller + Rabada). Both batter rows tint.
check(dom["count"] == 2, f"[{label}] highlighted row count {dom['count']} == 2 "
                          f"(both batters Yadav caught off Pandya)")
batters_seen = {r["cells"][0] for r in dom["rows"]} if dom["rows"] else set()
check("DA Miller" in batters_seen,
      f"[{label}] DA Miller row tinted (caught by Yadav)")
check("K Rabada" in batters_seen,
      f"[{label}] K Rabada row tinted (caught by Yadav)")
check(dom["scrollY"] > 0, f"[{label}] page auto-scrolled (scrollY={dom['scrollY']} > 0)")

print(f"\n=== {label}: {len(passes)} passed, {len(fails)} failed ===")
for p in passes: print(f"  ✓ {p}")
for f in fails: print(f"  ✗ {f}")
sys.exit(0 if not fails else 1)
PYEOF
record_result $?

print_summary
