# Regression tests — backend URL md5-diff

Checked-in versions of the HEAD-vs-patched harness described in
`internal_docs/regression-testing-api.md`. Run before shipping any
backend change with high blast radius — a shared `FilterParams`
update, a router filter-helper refactor, a SQL-generator change —
to prove queries you didn't intend to change still return byte-
identical responses, and queries you DID intend to change differ
in the right direction.

## Layout

```
regression/
  README.md               — this file
  run.sh                  — the runner
  venues/
    urls.txt              — Phase 2 filter_venue coverage
  <feature>/
    urls.txt
```

Each feature subdir owns one `urls.txt`. Line format:

```
# <kind> <label> <url-path-and-query>
REG bat_summary_plain                /api/v1/batters/ba607b88/summary
NEW bat_summary_venue_wankhede       /api/v1/batters/ba607b88/summary?filter_venue=Wankhede%20Stadium%2C%20Mumbai
```

- **`REG`** — this URL SHOULD be byte-identical before/after. Any
  drift is a regression.
- **`NEW`** — this URL SHOULD differ. Byte-identical is suspicious
  (maybe the fix is inert, or the URL is a typo).

`label` must be filesystem-safe (`[a-z0-9_]+`) — it becomes a file
name.

## Running

```bash
./tests/regression/run.sh venues
```

The runner:
1. Reads `tests/regression/venues/urls.txt`.
2. Smokes the current (patched) server so we know every URL resolves.
3. `git stash push` on the code under test, waits for uvicorn to
   pick up HEAD, captures every URL's response (pretty JSON in
   `/tmp/regression-test/head/<label>.json`, md5 of sorted compact
   form in a manifest).
4. `git stash pop`, waits for uvicorn, captures again into
   `/tmp/regression-test/patched/`.
5. Diffs the two manifests and prints:
   - `REG matched` / `REG DRIFTED` (drifted = regression failure).
   - `NEW changed` / `NEW unchanged` (unchanged = suspicious).

Exit 0 on zero REG drifts + zero NEW unchanged; non-zero otherwise.

## Prerequisites

- `uvicorn api.app:app --reload --port 8000` running. The `--reload`
  flag is what lets the runner stash/pop without restarting manually.
- `curl`, `python3`, `md5` (macOS) or `md5sum` (Linux).
- Clean working tree — the only uncommitted change should be the
  code under test. Anything else (half-edited docs, scratch files)
  will be stashed and restored alongside, which muddies the diff.

## Adding a new feature suite

1. `mkdir tests/regression/<feature>`
2. Enumerate URLs in `<feature>/urls.txt`. Guidelines:
   - At least one REG + one NEW per endpoint your change touches.
   - A control sample of REG URLs in unrelated routers (e.g. `/api/v1/tournaments`, `/api/v1/seasons`) — they must never drift.
   - Use real subject IDs (Kohli = ba607b88, Bumrah = 462411b3, India = team name). Typo'd names silently return zero rows, which looks like a bug.
3. Run once without any code changes to smoke-test — expect zero
   errors in the manifest.
4. Make your change. Run `./tests/regression/run.sh <feature>`.
5. Inspect any drift. Fix and re-run until REG:0 drifted.
