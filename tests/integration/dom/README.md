# tests/integration/dom/

DOM-grounded numeric tests. One script per **(tab, sub-tab,
scope-class)** triple — anchor an `agent-browser` (Playwright/CDP)
navigation at a closed historical window and assert every visible
number against an INDEPENDENT ground-truth dict (computed from
sqlite, NOT the API code path under test).

## Spec

- **Umbrella:** `internal_docs/spec-dom-grounded-tests.md`
- **Series + Teams inventory:** `internal_docs/spec-dom-tests-series-teams.md`

## Conventions

- **Closed-window anchors** — `season_from`/`season_to` pin both ends
  to a season that's already finished, so expected values stay stable
  across DB rebuilds. If cricsheet retroactively edits a window, the
  script fails noisily; investigate via
  `update_recent.py --dry-run`, update the expected dict, commit.
- **Ground-truth provenance** — every script's expected dict cites
  where its numbers came from. Two acceptable sources:
  1. A subagent that gets schema + metric definitions and writes its
     own SQL, NOT reading any `api/` source.
  2. A committed `audit/<script-name>.sql` runnable as
     `sqlite3 cricket.db < ...sql` producing the expected numbers.
  NEVER copy expected numbers from the running API and assert the
  API returns them — that's a tautology.
- **Math invariant** — every chip-bearing row asserts
  `delta_pct = (value − scope_avg) / scope_avg × 100 ± EPS_PCT`.
  Catches the bug class where the chip lies about the relationship
  between its displayed value + avg.
- **Per cell, assert at least one of:**
  - Display text matches expected.
  - Chip envelope (parsed from `MetricDelta`'s `title=` attr).
  - Math invariant.
  Tabular surfaces also assert FIRST and LAST visible row, not just
  the top.

## Running

```bash
# Prereqs:
#   uv run uvicorn api.app:app --reload --port 8000
#   cd frontend && npm run dev          # Vite on 5173

./tests/integration/dom/teams_compare_intl.sh
./tests/integration/dom/teams_compare_club.sh
./tests/integration/dom/teams_match_list_intl_fm.sh
./tests/integration/dom/series_landing_intl_fm.sh
```

Each script ~5–10s. Don't run on every commit — gate behind a make
target (`make dom-tests`) and run when:

- Touched `FilterParams` / `AuxParams` / scope-link URL builder /
  any filter clause builder → run all DOM tests.
- Touched a tab's components → run that tab's scripts (intl + club
  twins).
- Touched a shared discipline helper → run the affected discipline
  across every tab.
- Touched `populate_*.py` / `import_data.py` / `update_recent.py`
  → run all DOM tests against the rebuilt DB.

## Files

| Script | Coverage |
|---|---|
| `_lib.sh` | Shared harness: navigate, extractors, assert runners, summary |
| `teams_compare_intl.sh` | Teams > Compare, INTL anchors A / A' / E1 (FilterBar fm) |
| `teams_compare_club.sh` | Teams > Compare, CLUB anchor B (IPL 2025) |
| `teams_match_list_intl_fm.sh` | Teams > Match List with team_class=fm (Aus 22 → 16 narrowing) |
| `series_landing_intl_fm.sh` | /series landing tile counts narrow with team_class=fm |
| `audit/*.sql` | Independent ground-truth SQL per script |

## Phasing

- **Batch 1 (this PR):** the 4 above. Goal — prove the lifted
  harness works.
- **Batch 2 (next session):** `teams_overview_*`, `teams_batting_*`,
  `teams_bowling_*`, `teams_fielding_*`, `teams_partnerships_*`,
  `series_overview_*`, `series_records_*`. ~10 scripts.
- **Batch 3 (queue):** remaining tabs + `cross_cutting_team_class_consistency.sh`.

## Anti-pattern guardrails

PR-review blockers:

- A new DOM-test that reads expected numbers from the API.
- A script asserting only "page contains X" (presence — not enough).
- A new per-tab helper that duplicates an existing extractor in
  `_lib.sh`.
