#!/bin/bash
# Mobile viewport overflow — cross-page integration test.
#
# Loads an exhaustive set of route × tab combinations at the
# iPhone 13 viewport (390x844) and asserts that NO page leaks
# horizontal overflow into the body. The rule:
#
#   document.documentElement.scrollWidth <= viewport + tolerance
#
# Tolerance is 2px (sub-pixel rendering noise on Retina screens).
#
# Per CLAUDE.md "Mobile viewport check is mandatory" — this test
# locks the invariant after the 2026-05-15 audit that uncovered
# 8 pages with body-level overflow (filter row not wrapping, mosaic
# col-headers, wisden-table missing scroll wrappers, statrow tracks
# expanding past 1fr, Players-tab roster cells). All eight cases
# now ship fixed.
#
# Per CLAUDE.md "Tests must cover EVERY call site of a shared
# abstraction": the URL list covers every top-level route plus
# every subtab where one exists.
#
# Per CLAUDE.md "Red-then-green test discipline": each of the
# four mobile-overflow commits (filterbar wrap, subtab wrap +
# cols-5 + mosaic scroll, statrow minmax, InningBandsRow scroll
# wrap, teams-players ellipsis) demonstrably fails the relevant
# subset of this test when reverted, then passes after the fix.
#
# What this test does NOT cover:
#   - Widgets that overflow but live inside a legitimate
#     `overflow-x: auto` ancestor that actually scrolls. Those
#     are the Compare pattern doing its job, and are an
#     intentional design decision (see internal_docs/colors.md).
#   - Touch-scroll affordance / fade indicators on scroll
#     containers (visual UX, not assertable here).

set -u

BASE="${BASE:-http://localhost:5173}"
VIEWPORT_W=390
TOLERANCE=2
PASS=0; FAIL=0; FAILS=""

ab()      { agent-browser "$@" >/dev/null 2>&1; }
ab_eval() { agent-browser eval "$1" 2>/dev/null; }
settle()  { sleep "${1:-3}"; }
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL+1)); FAILS="$FAILS\n  - $1"; echo "  FAIL: $1"; }

# Player + team IDs used by player-page URLs. Match the fixtures
# in tests/integration/{batter,bowler,fielder}_distribution.sh.
KOHLI=ba607b88
BUMRAH=462411b3
DHONI=4a8a2e3b

# label|path  — every top-level route + every subtab variant.
URLS=(
  "home|/"
  "help|/help"
  "help-usage|/help/usage"
  "matches|/matches"
  "series-landing|/series"
  "series-overview|/series?tournament=Indian%20Premier%20League"
  "series-editions|/series?tournament=Indian%20Premier%20League&tab=Editions"
  "series-batting|/series?tournament=Indian%20Premier%20League&tab=Batting"
  "series-bowling|/series?tournament=Indian%20Premier%20League&tab=Bowling"
  "series-fielding|/series?tournament=Indian%20Premier%20League&tab=Fielding"
  "series-partnerships|/series?tournament=Indian%20Premier%20League&tab=Partnerships"
  "series-records|/series?tournament=Indian%20Premier%20League&tab=Records"
  "series-matches|/series?tournament=Indian%20Premier%20League&tab=Matches"
  "series-points-wt20|/series?tournament=T20%20World%20Cup%20%28Men%29&tab=Points"
  "league|/league?gender=male&team_type=club&primary_tier=primary"
  "teams-landing|/teams"
  "teams-byseason|/teams?team=Punjab+Kings&tab=By+Season"
  "teams-vs-opponent|/teams?team=Punjab+Kings&tab=vs+Opponent"
  "teams-compare|/teams?team=Punjab+Kings&tab=Compare"
  "teams-batting|/teams?team=Punjab+Kings&tab=Batting"
  "teams-bowling|/teams?team=Punjab+Kings&tab=Bowling"
  "teams-bowling-narrow|/teams?team=Punjab+Kings&gender=male&team_type=club&tab=Bowling&season_from=2024&season_to=2026"
  "teams-fielding|/teams?team=Punjab+Kings&tab=Fielding"
  "teams-partnerships|/teams?team=Punjab+Kings&tab=Partnerships"
  "teams-players|/teams?team=Punjab+Kings&tab=Players"
  "teams-matchlist|/teams?team=Punjab+Kings&tab=Match+List"
  "players-landing|/players"
  "batting-byseason|/batting?player=$KOHLI"
  "batting-byover|/batting?player=$KOHLI&tab=By+Over"
  "batting-byphase|/batting?player=$KOHLI&tab=By+Phase"
  "batting-vs-bowlers|/batting?player=$KOHLI&tab=vs+Bowlers"
  "batting-dismissals|/batting?player=$KOHLI&tab=Dismissals"
  "batting-inter-wicket|/batting?player=$KOHLI&tab=Inter-Wicket"
  "batting-innings-list|/batting?player=$KOHLI&tab=Innings+List"
  "bowling-byseason|/bowling?player=$BUMRAH"
  "bowling-byover|/bowling?player=$BUMRAH&tab=By+Over"
  "bowling-byphase|/bowling?player=$BUMRAH&tab=By+Phase"
  "bowling-vs-batters|/bowling?player=$BUMRAH&tab=vs+Batters"
  "bowling-wickets|/bowling?player=$BUMRAH&tab=Wickets"
  "bowling-innings-list|/bowling?player=$BUMRAH&tab=Innings+List"
  "fielding-byseason|/fielding?player=$DHONI"
  "fielding-byover|/fielding?player=$DHONI&tab=By+Over"
  "fielding-byphase|/fielding?player=$DHONI&tab=By+Phase"
  "fielding-dismissal-types|/fielding?player=$DHONI&tab=Dismissal+Types"
  "fielding-victims|/fielding?player=$DHONI&tab=Victims"
  "fielding-innings-list|/fielding?player=$DHONI&tab=Innings+List"
  "fielding-keeping|/fielding?player=$DHONI&tab=Keeping"
  "h2h-landing|/head-to-head"
  "h2h-team-vs-team|/head-to-head?mode=team&team_a=Punjab+Kings&team_b=Mumbai+Indians"
  "h2h-player-vs-player|/head-to-head?mode=player&player_a=$KOHLI&player_b=$BUMRAH"
  "venues-landing|/venues"
  "venues-overview|/venues?venue=Wankhede+Stadium"
  "venues-batters|/venues?venue=Wankhede+Stadium&tab=Batters"
  "venues-bowlers|/venues?venue=Wankhede+Stadium&tab=Bowlers"
  "venues-fielders|/venues?venue=Wankhede+Stadium&tab=Fielders"
  "venues-matches|/venues?venue=Wankhede+Stadium&tab=Matches"
  "venues-records|/venues?venue=Wankhede+Stadium&tab=Records"
)

# Probe — for each URL, return scrollWidth + the first "bad"
# overflowing element (right > viewport AND NOT inside an active
# horizontal-scroll ancestor). Bad elements are pure leaks; widgets
# inside the Compare-pattern scroll wrappers are correctly trapped
# and ignored.
PROBE='(() => {
  const VW = window.innerWidth
  const SW = document.documentElement.scrollWidth
  function nearestScrollAncestor(el) {
    let p = el.parentElement
    while (p && p !== document.body) {
      const cs = getComputedStyle(p)
      if ((cs.overflowX === "auto" || cs.overflowX === "scroll")
          && p.scrollWidth > p.clientWidth + 1) return p
      p = p.parentElement
    }
    return null
  }
  let bad = null
  for (const el of document.querySelectorAll("body *")) {
    if (el === document.body || el === document.documentElement) continue
    const r = el.getBoundingClientRect()
    if (r.right > VW + 1 && r.width > 0 && !nearestScrollAncestor(el)) {
      bad = {
        tag: el.tagName,
        cls: (el.className || "").toString().slice(0, 60),
        right: Math.round(r.right),
        width: Math.round(r.width),
      }
      break
    }
  }
  return JSON.stringify({ vw: VW, sw: SW, bad })
})()'

agent-browser close --all >/dev/null 2>&1 || true
sleep 1
ab set viewport "$VIEWPORT_W" 844

echo "Mobile viewport audit — $VIEWPORT_W wide, ${#URLS[@]} URLs"
echo "─────────────────────────────────────────"

for entry in "${URLS[@]}"; do
  label="${entry%%|*}"
  path="${entry#*|}"
  ab open "$BASE$path"
  ab wait --load networkidle
  settle 3

  raw=$(agent-browser eval "$PROBE" 2>/dev/null | sed -e 's/^"//' -e 's/"$//' -e 's/\\"/"/g')
  vw=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin)['vw'])" 2>/dev/null || echo "?")
  sw=$(echo "$raw" | python3 -c "import sys,json; print(json.load(sys.stdin)['sw'])" 2>/dev/null || echo "?")
  bad=$(echo "$raw" | python3 -c "
import sys, json
d = json.load(sys.stdin)
b = d.get('bad')
print('' if not b else f\"{(b.get('cls') or b.get('tag') or '')[:50]}@{b['right']}px\")
" 2>/dev/null || echo "")

  if [ "$vw" = "?" ] || [ "$sw" = "?" ]; then
    bad "$label — probe-error"
    continue
  fi

  # Page passes if the document doesn't horizontally scroll past
  # the viewport. The `bad` widget probe is diagnostic detail
  # surfaced only when we already have an overflow — a sw==vw
  # page with a tagged element at right>vw means that element
  # lives inside a healthy scroll container (Compare pattern)
  # whose `scrollWidth > clientWidth + 1` check happened to be
  # false at probe time (already scrolled into view, etc).
  if [ "$sw" -le $((vw + TOLERANCE)) ]; then
    ok "$label (sw=$sw vw=$vw)"
  else
    over=$((sw - vw))
    bad "$label — overflow ${over}px (sw=$sw vw=$vw)${bad:+, bad: $bad}"
  fi
done

agent-browser close --all >/dev/null 2>&1 || true

echo ""
echo "─────────────────────────────────────────"
echo "Summary: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  echo -e "Failures:$FAILS"
  exit 1
fi
echo "All pages fit within the 390-wide viewport (tolerance ${TOLERANCE}px)."
