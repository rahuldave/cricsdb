# Integration tests

End-to-end tests that exercise the actual running app via
[`agent-browser`](https://www.npmjs.com/package/agent-browser) (a
thin CDP-driver CLI over Chromium). These aren't unit tests — they
drive the real Vite dev server against the real FastAPI backend
against the real SQLite DB, and assert behaviour at the URL level.

> Previously at repo-root `integration_tests/`; renamed to
> `tests/integration/` on 2026-04-17 alongside a new
> `tests/regression/` sibling. See `tests/README.md` for the split.

## Script layout

Scripts split into **per-tab** (happy-path for a single tab) and
**cross-cutting** (concerns that span multiple tabs — URL-state
contract, React mount/unmount hygiene). Cross-cutting scripts carry
a `cross_cutting_` prefix so their nature is obvious at a glance.

```
integration/
  README.md
  teams.sh          — Teams landing, tabs, Compare, match list
  batting.sh        — Batting leaders, player page, tabs, innings-list highlight
  bowling.sh        — Bowling leaders, player page, tabs, innings-list highlight
  fielding.sh       — Fielders, Keeping tab (conditional), filter_team auto-narrow
  series.sh         — Series landing, dossier, series_type reset, legacy redirects
  head_to_head.sh   — Player H2H + Team H2H (mode=team), series_type toggle
  matches.sh        — Matches list, FilterBar push, scorecard, highlight_batter
  players.sh        — Players landing, compare, ScopeIndicator, nav group
  players_hygiene.sh — Players-tab mount/unmount (companion to players.sh)
  venues.sh         — Venues landing + filter_venue fan-out
  cross_cutting_url_state.sh       — ScopeIndicator + PlayerLink across tabs
  cross_cutting_mount_unmount.sh   — React hygiene on rapid nav / fetch cancel
```

## When to write one here

When correctness depends on multiple layers cooperating. The
per-tab scripts cover each tab's own happy path (landing, filters,
sub-tabs, page-specific URL state); the cross-cutting scripts cover
concerns that span the whole app (URL-state contract, React mount/
unmount hygiene). Concrete examples:

- `cross_cutting_url_state.sh` — URL-state discipline: every user-
  initiated param change must push; every auto-correction must
  replace. See `internal_docs/url-state.md`. The tab-specific
  instances (e.g. `/batting` gender fill, `/series` series_type
  reset, `/matches` filter push) live in the per-tab scripts —
  this file keeps only the cross-tab widgets (ScopeIndicator,
  PlayerLink).
- `cross_cutting_mount_unmount.sh` — React hygiene: rapid navigation,
  fast filter clicks, in-flight search fetches, ResizeObserver-heavy
  chart unmounts. Catches missing `useEffect` cleanup, leftover
  listeners, setState-after-unmount, stale-response leaks. Asserts on
  negative signals (no page errors, no React warnings).
- `players.sh` — Players tab URL / behaviour discipline: deep-link
  gender auto-fill uses `replace`, landing tile clicks set
  `player`+`gender` atomically, 2-way compare renders both columns,
  cross-gender adds are refused in-place, ✕ drops the right column,
  ScopeIndicator CLEAR works, nav marks the Players group active on
  `/batting` / `/bowling` / `/fielding`, mobile sub-row has all four
  entries, Home-page PlayerLink routes the name to `/players` and
  the `b`/`bw`/`f` subscripts to the discipline pages.
- `players_hygiene.sh` — Players tab mount/unmount (companion to
  `players.sh`): rapid filter toggling with a 2-way compare mounted,
  add-then-remove compare with fetches in flight, rapid route hops
  across the Players group, 3-way → 2-way via ✕, and fast landing
  tile clicks — all asserted against negative signals.

Each script closes any lingering agent-browser session at the top so
prior HMR state / cached bundles don't bleed in.

Things that DON'T need integration tests (unit tests or API-level
curl suffice):

- Pure SQL logic (add to `tests/integration/` only if the JSON
  response shape matters across many routes — then the approach in
  `internal_docs/regression-testing-api.md` is better).
- Component rendering (TS type-check + manual browser-agent poke
  during dev is enough).

## When to run

**Not on every commit.** Integration tests are slow (they drive a
real browser) and they only break when a cooperating change across
layers goes wrong — not every refactor. Run them:

- After a substantial frontend or URL-state change.
- After a backend + frontend change that together affect what URLs
  are produced or consumed.
- Before a deploy that ships either of the above.
- When touching the FilterBar, router, or any of the setter-calling
  sites listed in `internal_docs/url-state.md`.

Between those, TypeScript + the build are enough. No need to run
after a small copy edit, a docs pass, or a backend-only change that
doesn't alter URL shape.

## Running

Prerequisites:

- `agent-browser` on PATH (`npm i -g agent-browser` or `brew install
  agent-browser`).
- Vite dev server running: `cd frontend && npm run dev`
  (default http://localhost:5173).
- FastAPI backend running: `uv run uvicorn api.app:app --reload
  --port 8000`.

```bash
./tests/integration/venues.sh
./tests/integration/cross_cutting_url_state.sh
# Or run them all (verbose; ~20 minutes total):
for s in tests/integration/*.sh; do bash "$s"; done
```

Output is a per-assertion `✓` / `✗` followed by a `Passed: N / Failed:
M` summary. Exits 0 on all-pass, 1 otherwise — fits into CI.

Set `BASE` to test a non-default origin (prod sanity checks):

```bash
BASE=https://t20.rahuldave.com ./tests/integration/venues.sh
```

## Writing a new one

Copy `teams.sh` (or any per-tab script) and edit. The helpers at
the top (`reset`, `click_ref`, `ref_for`, `assert_url_eq`,
`assert_url_contains`, `_innerText_has`, `assert_snapshot_contains`,
`settle`) cover the common patterns.

Two things worth remembering:

1. **`agent-browser snapshot -i` uses `[ref=eN]`; `click` uses `@eN`.**
   `ref_for` translates between them. If you need the raw ref string,
   extract `ref=eN` and prefix with `@`.
2. **Settle after every state-changing action.** The page needs a
   tick for React to re-render and for the URL to update. `settle
   0.8` is usually enough; `settle 2.5` is safer after an
   `agent-browser open` that triggers data fetches.

## Why not Playwright / Vitest / etc.

`agent-browser` is the same tool we already use for manual UI
verification during development (see the `agent-browser` skill in
`.claude/skills/`). Reusing it keeps "manual spot-check" and
"integration test" in the same dialect — a passing manual session
can be promoted to a script without learning a new framework.
