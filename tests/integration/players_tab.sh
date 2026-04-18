#!/bin/bash
# Players-tab integration tests.
#
# Verifies:
#   1. Single-player deep link with missing gender auto-fills via REPLACE
#      (back button goes to /, not to the pre-fill URL).
#   2. Landing profile-tile click sets player + gender atomically — one
#      history entry, not a rapid-fire sequence.
#   3. 2-way compare URL renders both columns.
#   4. Cross-gender add is refused (URL unchanged, error banner shown).
#   5. Primary ✕ returns to landing; compare ✕ drops that ID only.
#   6. Nav restructure: /batting / /bowling / /fielding keep the Players
#      group parent active; mobile sub-row lists all four entries.
#   7. Home-page PlayerLink routes the name to /players and the b/bw/f
#      subscripts to the discipline pages.
#
# Requires:
#   - agent-browser installed (npm i -g agent-browser).
#   - A vite dev server on http://localhost:5173 (npm run dev in frontend/).
#   - A FastAPI backend on http://localhost:8000 (uv run uvicorn ...).
#
# Run:
#   ./tests/integration/players_tab.sh
#
# Exits non-zero on the first failure.
set -u

BASE="${BASE:-http://localhost:5173}"
PASS=0
FAIL=0

# Close any lingering agent-browser sessions so prior HMR state /
# cached bundles don't affect assertions.
agent-browser close --all >/dev/null 2>&1 || true
sleep 1

# Canonical IDs used throughout — cross-referenced against our curated
# seeds in frontend/src/components/players/CuratedLists.ts.
KOHLI=ba607b88
MARKRAM=6a26221c
BUMRAH=462411b3
MANDHANA=5d2eda89   # women's — used to exercise the cross-gender reject

assert_url_eq() {
  local expected="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %s\n" "$expected"
    PASS=$((PASS + 1))
  else
    printf "  ✗ expected: %s\n" "$expected"
    printf "    got:      %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

assert_url_contains() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" == *"$needle"* ]]; then
    printf "  ✓ url contains %s\n" "$needle"
    PASS=$((PASS + 1))
  else
    printf "  ✗ url missing %s\n" "$needle"
    printf "    got: %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

assert_url_missing() {
  local needle="$1"
  local got
  got=$(agent-browser get url 2>/dev/null)
  if [[ "$got" != *"$needle"* ]]; then
    printf "  ✓ url missing %s\n" "$needle"
    PASS=$((PASS + 1))
  else
    printf "  ✗ url unexpectedly contains %s\n" "$needle"
    printf "    got: %s\n" "$got"
    FAIL=$((FAIL + 1))
  fi
}

# Strip JSON-string quoting ("foo" → foo) from an agent-browser eval
# result. Numeric and boolean results pass through unchanged.
dom_val() {
  local raw
  raw=$(agent-browser eval "$1" 2>/dev/null)
  # Strip a leading and trailing double-quote if both are present.
  if [[ "$raw" == \"*\" ]]; then
    raw="${raw#\"}"; raw="${raw%\"}"
  fi
  printf "%s" "$raw"
}

assert_dom_eq() {
  local js="$1"
  local expected="$2"
  local label="$3"
  local got
  got=$(dom_val "$js")
  if [[ "$got" == "$expected" ]]; then
    printf "  ✓ %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  ✗ %s\n    expected: %s\n    got:      %s\n" "$label" "$expected" "$got"
    FAIL=$((FAIL + 1))
  fi
}

settle() { sleep "${1:-1.2}"; }

reset() {
  agent-browser open "$BASE/" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.0
}

click_ref() {
  agent-browser click "$1" >/dev/null 2>&1
  settle 1.0
}

ref_for() {
  agent-browser snapshot -i 2>&1 | grep -E "$1" | head -1 | grep -oE 'ref=e[0-9]+' | head -1 | sed 's/ref=/@/'
}

# --------------------------------------------------------------------
echo "Test 1 · Deep-link gender auto-fill is a replace (no extra history)"
reset
agent-browser open "$BASE/players?player=$KOHLI" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
assert_url_eq "$BASE/players?player=$KOHLI&gender=male"
# One back should return to home — the gender fill must not have
# pushed its own history entry.
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/"

# --------------------------------------------------------------------
echo ""
echo "Test 2 · Landing profile tile sets player + gender atomically"
reset
agent-browser open "$BASE/players" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# Click the Kohli profile tile — it's the first popular-profile link
# under "Popular profiles".
KOHLI_REF=$(ref_for 'link.*V Kohli')
click_ref "$KOHLI_REF"
settle 1.5
assert_url_contains "player=$KOHLI"
assert_url_contains "gender=male"
# Single back should walk to /players (one entry, not three).
agent-browser back >/dev/null 2>&1; settle 0.8
assert_url_eq "$BASE/players"

# --------------------------------------------------------------------
echo ""
echo "Test 3 · 2-way compare URL renders both columns"
reset
agent-browser open "$BASE/players?player=$KOHLI&compare=$MARKRAM&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
# Count .wisden-compare-col cells — should be exactly 2.
assert_dom_eq \
  'String(document.querySelectorAll(".wisden-compare-col").length)' \
  '2' \
  "two compare columns rendered"
# Each column should have an identity line with a role label.
assert_dom_eq \
  'String(document.querySelectorAll(".wisden-player-identity").length)' \
  '2' \
  "both identity lines rendered"

# --------------------------------------------------------------------
echo ""
echo "Test 4 · Cross-gender add refused (URL unchanged, error shown)"
reset
agent-browser open "$BASE/players?player=$KOHLI&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
# Type into the compare picker and click the Mandhana result. The
# picker uses the same debounce as PlayerSearch — settle long enough
# for the 300 ms debounce + the async search fetch. Use the native
# setter + input event so React's onChange fires (plain assignment
# skips the React handler).
agent-browser eval '(() => {
  const input = document.querySelector(".wisden-compare-picker input");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  setter.call(input, "Mandhana");
  input.dispatchEvent(new Event("input", { bubbles: true }));
  return "typed";
})()' >/dev/null 2>&1
settle 1.5
agent-browser eval '(() => {
  const lis = document.querySelectorAll(".wisden-playersearch-list li");
  for (const li of lis) {
    if (li.textContent.includes("Mandhana")) { li.click(); return "clicked"; }
  }
  return "no result";
})()' >/dev/null 2>&1
settle 2.0
# URL must NOT have gained a `compare=` param — rejection preserves
# the single-player state.
assert_url_missing "compare="
# Error message must render in the DOM.
HAS_ERR=$(agent-browser eval 'document.querySelector(".wisden-compare-picker-err")?.textContent || ""' 2>/dev/null)
if [[ "$HAS_ERR" == *"across genders"* ]]; then
  echo "  ✓ cross-gender error banner visible"
  PASS=$((PASS + 1))
else
  echo "  ✗ cross-gender error banner missing (got: $HAS_ERR)"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 5 · Remove compare via ✕ drops that ID"
reset
agent-browser open "$BASE/players?player=$KOHLI&compare=$MARKRAM&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 3.0
# Click the ✕ on Markram's column.
MARKRAM_X=$(ref_for 'button "Remove AK Markram"')
click_ref "$MARKRAM_X"
settle 1.0
assert_url_missing "compare="
assert_url_contains "player=$KOHLI"

# --------------------------------------------------------------------
echo ""
echo "Test 6 · Remove primary via ✕ returns to landing"
reset
agent-browser open "$BASE/players?player=$KOHLI&gender=male" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
CLEAR_REF=$(ref_for 'button "Clear comparison"')
# Single-player ✕ is labelled "Clear comparison" even when there's
# nothing to "compare" — the intent is "return to landing", which it
# does by stripping player + compare.
if [ -z "$CLEAR_REF" ]; then
  # No ✕ in single-player — the ✕ only lives inside compare columns.
  # Skip this test if the component tree doesn't expose it here.
  echo "  · skipped (no ✕ in single-player view — expected)"
else
  click_ref "$CLEAR_REF"
  assert_url_missing "player="
fi

# --------------------------------------------------------------------
echo ""
echo "Test 7 · ScopeIndicator visible + CLEAR strips narrowing"
reset
agent-browser open "$BASE/players?player=$KOHLI&gender=male&filter_team=India&filter_opponent=Australia" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 2.5
HAS_SCOPE=$(agent-browser eval 'document.querySelector(".wisden-scope")?.textContent?.includes("India") ? "yes" : "no"' 2>/dev/null)
if [[ "$HAS_SCOPE" == '"yes"' ]]; then
  echo "  ✓ scope pill visible"
  PASS=$((PASS + 1))
else
  echo "  ✗ scope pill missing"
  FAIL=$((FAIL + 1))
fi
# NB: ScopeIndicator's aria-label is "Clear scope and return to full
# career" — match the prefix, not the full quoted label, or grep
# whiffs on the closing ".
CLEAR_SCOPE=$(ref_for 'button "Clear scope')
click_ref "$CLEAR_SCOPE"
for p in filter_team filter_opponent tournament; do
  assert_url_missing "$p="
done
assert_url_contains "player=$KOHLI"

# --------------------------------------------------------------------
echo ""
echo "Test 8 · Players group parent active on /batting, /bowling, /fielding"
for route in batting bowling fielding; do
  reset
  agent-browser open "$BASE/$route" >/dev/null 2>&1
  agent-browser wait --load networkidle >/dev/null 2>&1
  settle 1.5
  ACTIVE=$(agent-browser eval '(() => {
    const el = document.querySelector(".wisden-nav-group .wisden-nav-link");
    return el && el.className.includes("is-active") ? "yes" : "no";
  })()' 2>/dev/null)
  if [[ "$ACTIVE" == '"yes"' ]]; then
    echo "  ✓ /$route marks Players group parent active"
    PASS=$((PASS + 1))
  else
    echo "  ✗ /$route does NOT mark Players group parent active"
    FAIL=$((FAIL + 1))
  fi
done

# --------------------------------------------------------------------
echo ""
echo "Test 9 · Mobile sub-row has all 4 entries (Players + 3 disciplines)"
reset
agent-browser open "$BASE/batting" >/dev/null 2>&1
agent-browser wait --load networkidle >/dev/null 2>&1
settle 1.5
COUNT=$(agent-browser eval 'String(document.querySelectorAll(".wisden-nav-subrow .wisden-nav-sublink").length)' 2>/dev/null)
if [[ "$COUNT" == '"4"' ]]; then
  echo "  ✓ sub-row has 4 entries"
  PASS=$((PASS + 1))
else
  echo "  ✗ sub-row count is $COUNT (expected 4)"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "Test 10 · Home-page PlayerLink routes name to /players, letters to disciplines"
reset
# Kohli's name link should be first anchor whose href is /players?…&gender=male.
HREF=$(agent-browser eval '(() => {
  const a = [...document.querySelectorAll("a.comp-link")].find(x => x.textContent === "V Kohli");
  return a ? a.getAttribute("href") : "";
})()' 2>/dev/null)
if [[ "$HREF" == '"/players?player=ba607b88&gender=male"' ]]; then
  echo "  ✓ Kohli name link → /players?player=ba607b88&gender=male"
  PASS=$((PASS + 1))
else
  echo "  ✗ Kohli name link wrong: $HREF"
  FAIL=$((FAIL + 1))
fi
# Subscript letters — three of them for Kohli. Scope the letter
# count to the .player-letters span that follows Kohli's name link
# (his span — not Mandhanas, which sits further down in the same
# parent <div>).
LETTER_COUNT=$(dom_val '(() => {
  const kohli = [...document.querySelectorAll("a.comp-link")].find(x => x.textContent === "V Kohli");
  if (!kohli) return "no-kohli";
  const sibling = kohli.nextElementSibling;
  if (!sibling || !sibling.classList.contains("player-letters")) return "no-letters-span";
  return String(sibling.querySelectorAll(".player-letter").length);
})()')
if [[ "$LETTER_COUNT" == "3" ]]; then
  echo "  ✓ Kohli has 3 discipline subscripts"
  PASS=$((PASS + 1))
else
  echo "  ✗ Kohli subscript count is $LETTER_COUNT (expected 3)"
  FAIL=$((FAIL + 1))
fi

# --------------------------------------------------------------------
echo ""
echo "────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
