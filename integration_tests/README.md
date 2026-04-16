# Integration tests

End-to-end tests that exercise the actual running app via
[`agent-browser`](https://www.npmjs.com/package/agent-browser) (a
thin CDP-driver CLI over Chromium). These aren't unit tests — they
drive the real Vite dev server against the real FastAPI backend
against the real SQLite DB, and assert behaviour at the URL level.

## When to write one here

When correctness depends on multiple layers cooperating. Concrete
examples we have:

- `back_button_history.sh` — URL-state discipline: every user-
  initiated param change must push; every auto-correction must
  replace. See `internal_docs/url-state.md` for the rules.

Things that DON'T need integration tests (unit tests or API-level
curl suffice):

- Pure SQL logic (add to `integration_tests` only if the JSON
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
./integration_tests/back_button_history.sh
```

Output is a per-assertion `✓` / `✗` followed by a `Passed: N / Failed:
M` summary. Exits 0 on all-pass, 1 otherwise — fits into CI.

Set `BASE` to test a non-default origin (prod sanity checks):

```bash
BASE=https://t20.rahuldave.com ./integration_tests/back_button_history.sh
```

## Writing a new one

Copy `back_button_history.sh` and edit. The helpers at the top
(`reset`, `click_ref`, `ref_for`, `assert_url_eq`,
`assert_url_contains`, `settle`) cover the common patterns.

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
