# tests

Two kinds of automated test live here, each under its own subdir:

- **`integration/`** — bash scripts that drive the actual running app
  via `agent-browser` (Chromium over CDP). They run against the real
  Vite dev server + real FastAPI + real SQLite and assert behaviour
  at the URL / DOM level. Reserved for *cross-layer* correctness:
  URL-state discipline, mount-unmount hygiene, compare-view flows,
  nav restructures. One script per feature or concern.
- **`regression/`** — per-feature URL inventories (`urls.txt`) + a
  runner that does HEAD-vs-patched md5-diff. Designed for backend
  changes with high blast radius — shared helpers like
  `FilterParams.build()`, router filter fns, SQL generators. Proves
  "queries I didn't intend to change still return byte-identical
  responses; queries I did intend to change differ sensibly."

Both are opt-in — they're not CI-enforced. Run `integration/` after
a substantial frontend or URL-state change, or before a deploy that
ships one. Run `regression/` before a deploy that ships a shared-
helper refactor.

## Layout

```
tests/
  README.md               — this file
  integration/            — agent-browser bash scripts
    README.md
    # per-tab happy paths
    teams.sh
    batting.sh
    bowling.sh
    fielding.sh
    series.sh
    head_to_head.sh
    matches.sh
    players.sh
    players_hygiene.sh    — Players-tab mount/unmount companion
    venues.sh
    # cross-cutting (span multiple tabs)
    cross_cutting_url_state.sh       — ScopeIndicator + PlayerLink
    cross_cutting_mount_unmount.sh   — React hygiene on rapid nav
  regression/             — backend URL md5-diff regression
    README.md
    run.sh                — generalised runner: stash → capture HEAD,
                            pop → capture patched, diff.
    teams/    urls.txt
    batting/  urls.txt
    bowling/  urls.txt
    fielding/ urls.txt
    series/   urls.txt
    head_to_head/ urls.txt
    matches/  urls.txt
    players/  urls.txt
    venues/   urls.txt
```

## Running

Prerequisites for `integration/`:
- `agent-browser` on PATH
- Vite dev: `cd frontend && npm run dev` (http://localhost:5173)
- FastAPI: `uv run uvicorn api.app:app --reload --port 8000`

```bash
./tests/integration/venues.sh
BASE=https://t20.rahuldave.com ./tests/integration/venues.sh  # prod sanity
```

Prerequisites for `regression/`:
- FastAPI running on port 8000 with `--reload` (the stash/pop cycle
  depends on uvicorn auto-reloading between runs).
- Working tree where the only uncommitted change is the code under
  test.

```bash
./tests/regression/run.sh venues
# runs tests/regression/venues/urls.txt
```

See each subdir's README for the full details + how to add a new
feature's suite.

## Roadmap

Backfill landed 2026-04-17 — every top-level tab has a
`regression/<tab>/urls.txt` and an `integration/<tab>.sh`. The
cross-cutting tests were also reorganised: page-specific URL-state
assertions moved from the former `back_button_history.sh` into the
relevant per-tab script, and the file itself was renamed
`cross_cutting_url_state.sh` to keep only ScopeIndicator + PlayerLink
(which span multiple tabs). `mount_unmount.sh` was similarly renamed
`cross_cutting_mount_unmount.sh`.
