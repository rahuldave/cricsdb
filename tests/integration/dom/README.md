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

## Inventory (41 scripts post-Batch-3)

| Script | Coverage |
|---|---|
| `_lib.sh` | Harness: `navigate`, 4 extractors (`extract_grid`, `extract_data_table` ord-arg, `extract_landing_tiles`, `extract_team_overview`), 4 assert runners |
| **Teams** ||
| `teams_compare_{intl,club}.sh` | Teams > Compare grid (Aus FM / IPL 2025) |
| `teams_overview_{intl,club}.sh` | Teams > Overview StatCards + keepers |
| `teams_batting_{intl,club}.sh` | Teams > Batting band — totals + by-phase |
| `teams_bowling_{intl,club}.sh` | Teams > Bowling band — totals + by-phase |
| `teams_fielding_{intl,club}.sh` | Teams > Fielding band — catches/stumpings/run-outs |
| `teams_partnerships_{intl,club}.sh` | Teams > Partnerships — best pair + by-wicket grid |
| `teams_match_list_intl_fm.sh` | Teams > Match List, FM-narrowing (Aus 22 → 16) |
| `teams_match_list_club.sh` | Teams > Match List club twin (RCB IPL 25, 15) |
| `teams_vs_opponent_{intl,club}.sh` | Teams > vs Opponent rivalry StatCards |
| `teams_players_{intl,club}.sh` | Teams > Players per-season grid (custom inline extractor) |
| **Series** ||
| `series_landing_{intl_fm,club}.sh` | /series landing tile counts |
| `series_overview_{intl,club}.sh` | Series > Overview StatCards (tournament-scoped) |
| `series_overview_intl_bilateral.sh` | Series > Overview bilateral rivalry (Ind-vs-Eng 24-25) |
| `series_records_{intl,club}.sh` | Series > Records (highest/lowest, top batters/bowlers) |
| `series_editions_{intl,club}.sh` | Series > Editions, full DESC list |
| `series_matches_{intl,club}.sh` | Series > Matches (paginated for IPL 25, single-page for WC 24) |
| `series_partnerships_{intl,club}.sh` | Series > Partnerships — by-wicket + top-N (12 tables; uses ord arg) |
| `series_batters_{intl,club}.sh` | Series > Batters — 3 modes (by_runs/avg/SR) |
| `series_bowlers_{intl,club}.sh` | Series > Bowlers — 3 modes (by_W/SR/econ) |
| `series_fielders_{intl,club}.sh` | Series > Fielders — 3 modes (by_dismissals/keeper/RO) |
| `series_champions_intl.sh` | Series > Overview Champions table (4 finals) |
| `series_knockouts_intl.sh` | Series > Overview Knockouts table (T20 WC 24 SF + F) |
| `series_points_club.sh` | Series > Points (IPL 25 standings, 10 rows) |
| **Cross-cutting** ||
| `cross_cutting_team_class_consistency.sh` | FM filter narrowing across 4 surfaces |
| `audit/*.sql` | Independent ground-truth SQL per script |

## Phasing

- **Batch 1 (shipped):** harness + 4 anchor scripts.
- **Batch 2 (shipped 2026-04-28):** Teams sub-tabs +
  `series_overview_*` + `series_records_*` (14 scripts).
- **Batch 3 (shipped 2026-04-29):** rest of Teams + all Series
  sub-tabs + cross-cutting consistency (23 scripts +
  ordinal-index harness ext.). Total = 41 scripts.
- **Batch 4+ (open queue):** Players standalone, Matches
  scorecard, Venues sub-tabs, chart-DOM extractor for Semiotic
  charts. Out of scope for the original spec.

## Anti-pattern guardrails

PR-review blockers:

- A new DOM-test that reads expected numbers from the API.
- A script asserting only "page contains X" (presence — not enough).
- A new per-tab helper that duplicates an existing extractor in
  `_lib.sh`.
