#!/bin/bash
# Cross-cutting integration test for the inning-split spec —
# §A toggle partition + §D status strip + §E URL roundtrip from
# spec-inning-split.md §10.3.
#
# Anchor: RCB Batting tab in IPL 2025 (men's, club). Closed window —
# numbers stable across DB rebuilds. Asserts at the rendered DOM
# level (NOT the API directly) so wiring bugs between the toggle
# pills, the URL state, and the fetch pipeline get caught.
#
# Three blocks:
#
#   §A — Toggle partition (single team).
#     • Headline `total_runs` partitions across 1st + 2nd innings.
#     • run_rate differs across the three pill states (catches a
#       silent no-op where the URL flips but the data doesn't).
#
#   §D — Status strip rendering.
#     • inning=0 in URL → "Innings: 1st innings" segment present.
#     • inning=1 → "Innings: 2nd innings".
#     • inning absent → no Innings segment.
#
#   §E — Pill ↔ URL roundtrip.
#     • Click "1st innings" → URL gains inning=0.
#     • Click "All innings" → URL drops the param.
#
# Sibling §B (Compare-slot dual-meaning) and §C (chip alignment under
# inning override) are covered by tests/sanity/test_slot_override_
# alignment.py at the math level — see scenarios F + G.
#
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev
# Run: ./tests/integration/dom/cross_cutting_inning_split.sh

set -u
BASE="${BASE:-http://localhost:5173}"
PASS=0; FAIL=0

agent-browser close --all >/dev/null 2>&1 || true
sleep 1

ANCHOR_BASE="$BASE/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&season_from=2025&season_to=2025&tab=Batting"

navigate() {
  local url="$1" what="$2"
  echo
  echo "─── $what"
  echo "    $url"
  agent-browser navigate "$url" >/dev/null
  sleep 3   # let async fetches + React commits settle
}

extract_state() {
  # Returns JSON: { url, inning_param, run_rate, total_runs, status_strip, pills: [{text, active}] }
  agent-browser eval --stdin <<'EVALEOF'
(() => {
  const lines = document.body.innerText.split('\n');
  // Headline values come from the Batting tab's first stat row. The
  // tab structure is: "Run rate" \n "<value>" pattern.
  const findValueAfter = (label) => {
    const idx = lines.findIndex(s => s === label);
    if (idx === -1) return null;
    const v = lines[idx + 1];
    if (!v) return null;
    // Strip any trailing chip (e.g. "9.43↑ +0.6%"). Keep just the number.
    const m = v.match(/^([+-]?\d+(?:\.\d+)?)/);
    return m ? parseFloat(m[1]) : null;
  };
  const params = new URL(window.location.href).searchParams;
  const pills = Array.from(document.querySelectorAll('.wisden-seg'))
    .filter(b => /innings/.test(b.innerText))
    .map(b => ({ text: b.innerText.trim(), active: b.classList.contains('is-active') }));
  const strip = document.querySelector('.wisden-scope-strip');
  return JSON.stringify({
    url: window.location.href,
    inning_param: params.get('inning'),
    run_rate: findValueAfter('Run rate'),
    total_runs: findValueAfter('Total runs') || findValueAfter('Runs'),
    matches: findValueAfter('Matches'),
    status_strip: strip ? strip.textContent.replace(/\s+/g, ' ').trim() : null,
    pills,
  });
})()
EVALEOF
}

assert() {
  local label="$1"
  local cond="$2"
  if eval "$cond"; then
    echo "  PASS: $label"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $label  ($cond)"
    FAIL=$((FAIL+1))
  fi
}

# Pill selectors — relies on .wisden-seg buttons whose visible text
# matches the pill labels.
click_pill() {
  local label="$1"
  agent-browser eval --stdin >/dev/null <<EVALEOF
(() => {
  const btn = Array.from(document.querySelectorAll('.wisden-seg'))
    .find(b => /innings/.test(b.innerText) && b.innerText.trim() === '$label');
  if (btn) btn.click();
})()
EVALEOF
  sleep 2
}

# ─── §A — Toggle partition ──────────────────────────────────────
echo
echo "════════ §A — Toggle partition ════════"

navigate "$ANCHOR_BASE" "All innings (default)"
ALL_JSON=$(extract_state)
echo "$ALL_JSON" | python3 -m json.tool | head -10

navigate "${ANCHOR_BASE}&inning=0" "1st innings"
INN0_JSON=$(extract_state)
echo "$INN0_JSON" | python3 -m json.tool | head -10

navigate "${ANCHOR_BASE}&inning=1" "2nd innings"
INN1_JSON=$(extract_state)
echo "$INN1_JSON" | python3 -m json.tool | head -10

# Write the JSONs to /tmp so Python doesn't have to dodge shell
# quoting on the heredoc body.
echo "$ALL_JSON" > /tmp/inning_split_all.json
echo "$INN0_JSON" > /tmp/inning_split_inn0.json
echo "$INN1_JSON" > /tmp/inning_split_inn1.json
RESULT=$(python3 - <<'PYEOF'
import json
def load(p):
    with open(p) as fh:
        r = json.load(fh)
    return json.loads(r) if isinstance(r, str) else r
all_s = load('/tmp/inning_split_all.json')
inn0  = load('/tmp/inning_split_inn0.json')
inn1  = load('/tmp/inning_split_inn1.json')

results = []

# §A.1 run_rate differs across all three (catches silent no-op).
rrs = (all_s.get('run_rate'), inn0.get('run_rate'), inn1.get('run_rate'))
ok_rr = (
    rrs[0] is not None and rrs[1] is not None and rrs[2] is not None
    and len(set(round(r, 2) for r in rrs)) == 3
)
results.append(('§A.1 run_rate differs across All/1st/2nd', ok_rr, f"got {rrs}"))

# §A.2 matches partitions: 1st + 2nd == all.
ms = (all_s.get('matches'), inn0.get('matches'), inn1.get('matches'))
ok_m = (
    ms[0] is not None and ms[1] is not None and ms[2] is not None
    and ms[1] + ms[2] == ms[0]
)
results.append(('§A.2 matches partition: 1st + 2nd = all', ok_m,
                f"{ms[1]} + {ms[2]} = {(ms[1] or 0)+(ms[2] or 0)} vs all={ms[0]}"))

# §A.3 active pill matches URL state (per state).
expected = {None: 'All innings', '0': '1st innings', '1': '2nd innings'}
for s, label in [(all_s, 'All'), (inn0, '1st'), (inn1, '2nd')]:
    actives = [p['text'] for p in s.get('pills', []) if p.get('active')]
    want = expected[s.get('inning_param')]
    ok = actives == [want]
    results.append((f'§A.3 active pill on {label} URL', ok,
                    f"got {actives}, want [{want!r}]"))

# Print pass/fail lines + a counter line the shell parses.
n_pass = n_fail = 0
for label, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}: {label} ({detail})")
    if ok: n_pass += 1
    else:  n_fail += 1
print(f"COUNTER §A: {n_pass} pass, {n_fail} fail")
PYEOF
)
echo "$RESULT"
A_PASS=$(echo "$RESULT" | awk '/^COUNTER §A:/{print $3}')
A_FAIL=$(echo "$RESULT" | awk '/^COUNTER §A:/{print $5}')
PASS=$((PASS + ${A_PASS:-0}))
FAIL=$((FAIL + ${A_FAIL:-0}))

# ─── §D — Status strip rendering ────────────────────────────────
echo
echo "════════ §D — Status strip rendering ════════"

# inning absent
navigate "$ANCHOR_BASE" "no inning param"
JSON=$(extract_state)
strip=$(echo "$JSON" | python3 -c "import sys,json; r=json.load(sys.stdin); r=json.loads(r) if isinstance(r,str) else r; print(r.get('status_strip') or '')")
if [[ "$strip" != *"Innings:"* ]]; then
  echo "  PASS: §D.1 no Innings segment when param absent"
  PASS=$((PASS+1))
else
  echo "  FAIL: §D.1 unexpected Innings segment: $strip"
  FAIL=$((FAIL+1))
fi

# inning=0 → "1st innings"
navigate "${ANCHOR_BASE}&inning=0" "inning=0"
JSON=$(extract_state)
strip=$(echo "$JSON" | python3 -c "import sys,json; r=json.load(sys.stdin); r=json.loads(r) if isinstance(r,str) else r; print(r.get('status_strip') or '')")
if [[ "$strip" == *"Innings: 1st innings"* ]]; then
  echo "  PASS: §D.2 'Innings: 1st innings' on inning=0"
  PASS=$((PASS+1))
else
  echo "  FAIL: §D.2 expected 'Innings: 1st innings'; got: $strip"
  FAIL=$((FAIL+1))
fi

# inning=1 → "2nd innings"
navigate "${ANCHOR_BASE}&inning=1" "inning=1"
JSON=$(extract_state)
strip=$(echo "$JSON" | python3 -c "import sys,json; r=json.load(sys.stdin); r=json.loads(r) if isinstance(r,str) else r; print(r.get('status_strip') or '')")
if [[ "$strip" == *"Innings: 2nd innings"* ]]; then
  echo "  PASS: §D.3 'Innings: 2nd innings' on inning=1"
  PASS=$((PASS+1))
else
  echo "  FAIL: §D.3 expected 'Innings: 2nd innings'; got: $strip"
  FAIL=$((FAIL+1))
fi

# ─── §E — Pill ↔ URL roundtrip ──────────────────────────────────
echo
echo "════════ §E — Pill ↔ URL roundtrip ════════"

navigate "$ANCHOR_BASE" "fresh load — All innings"
url=$(agent-browser eval --stdin <<<'window.location.href' 2>/dev/null | tr -d '"')
if [[ "$url" != *"inning="* ]]; then
  echo "  PASS: §E.1 fresh URL has no inning param"
  PASS=$((PASS+1))
else
  echo "  FAIL: §E.1 fresh URL unexpectedly has inning: $url"
  FAIL=$((FAIL+1))
fi

click_pill "1st innings"
url=$(agent-browser eval --stdin <<<'window.location.href' 2>/dev/null | tr -d '"')
if [[ "$url" == *"inning=0"* ]]; then
  echo "  PASS: §E.2 click '1st innings' → URL gains inning=0"
  PASS=$((PASS+1))
else
  echo "  FAIL: §E.2 expected inning=0; got: $url"
  FAIL=$((FAIL+1))
fi

click_pill "2nd innings"
url=$(agent-browser eval --stdin <<<'window.location.href' 2>/dev/null | tr -d '"')
if [[ "$url" == *"inning=1"* ]]; then
  echo "  PASS: §E.3 click '2nd innings' → URL gains inning=1"
  PASS=$((PASS+1))
else
  echo "  FAIL: §E.3 expected inning=1; got: $url"
  FAIL=$((FAIL+1))
fi

click_pill "All innings"
url=$(agent-browser eval --stdin <<<'window.location.href' 2>/dev/null | tr -d '"')
if [[ "$url" != *"inning="* ]]; then
  echo "  PASS: §E.4 click 'All innings' → URL drops inning"
  PASS=$((PASS+1))
else
  echo "  FAIL: §E.4 expected inning param dropped; got: $url"
  FAIL=$((FAIL+1))
fi

# ─── Summary ────────────────────────────────────────────────────
echo
echo "════════ Summary ════════"
TOTAL=$((PASS+FAIL))
echo "  $PASS / $TOTAL pass, $FAIL fail"
exit $((FAIL > 0 ? 1 : 0))
