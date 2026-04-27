# Spec — DOM-grounded numeric tests across all tabs

Companion roadmap to `tests/integration/compare_avg_chips.sh`. The
pattern there (Playwright/CDP DOM extraction → independent
sqlite-derived ground truth → cell-by-cell numeric agreement) is the
one we want everywhere a number renders. This file lists the wanted
tests per tab/sub-tab and the conventions every script should follow.

## Status (2026-04-27)

- ✅ Compare tab: `tests/integration/compare_avg_chips.sh` (82
  assertions, 2 anchors).
- 🔲 Series tab + sub-tabs: spec-only (see `spec-dom-tests-series.md`).
- 🔲 Teams tab + sub-tabs: spec-only (see `spec-dom-tests-teams.md`).
- 🔲 Players, Head-to-Head, Matches, Venues, Batting/Bowling/Fielding
  pages, scorecard: open queue, lower priority.

## File-naming convention

One shell file per **(tab, sub-tab, scope-class)** triple. `scope-
class` ∈ `{club, intl}` so each test exercises exactly one match
universe. Two files per (tab, subtab) — same script body, different
anchor URL + ground-truth dict.

```
tests/integration/dom/
  README.md
  series_landing_intl.sh
  series_landing_club.sh
  series_dossier_overview_intl.sh
  series_dossier_overview_club.sh
  series_dossier_records_intl.sh
  series_dossier_records_club.sh
  series_dossier_batters_intl.sh
  series_dossier_batters_club.sh
  series_dossier_bowlers_intl.sh
  series_dossier_bowlers_club.sh
  series_dossier_fielders_intl.sh
  series_dossier_fielders_club.sh
  series_dossier_partnerships_intl.sh
  series_dossier_partnerships_club.sh
  series_dossier_matches_intl.sh
  series_dossier_matches_club.sh
  series_dossier_champions_intl.sh    (ICC events; no club twin)
  series_dossier_knockouts_intl.sh    (ICC events; no club twin)
  series_dossier_points_club.sh       (league-table; no intl twin)
  teams_landing_intl.sh
  teams_landing_club.sh
  teams_overview_intl.sh
  teams_overview_club.sh
  teams_match_list_intl.sh
  teams_match_list_club.sh
  teams_vs_opponent_intl.sh
  teams_vs_opponent_club.sh
  teams_compare_intl.sh    (= existing compare_avg_chips, intl half)
  teams_compare_club.sh    (= existing compare_avg_chips, club half)
  teams_partnerships_intl.sh
  teams_partnerships_club.sh
  teams_records_intl.sh
  teams_records_club.sh
  teams_keepers_intl.sh    (international only — keeper inference)
  teams_players_intl.sh
  teams_players_club.sh
```

For tabs with a `series_type` axis (Series, H2H), a third per-(tab,
subtab) test exists for `bilateral` scope (bilateral-vs-tournament
distinction is structural for that subtab):

```
  series_dossier_overview_intl_bilateral.sh
  series_dossier_overview_intl_tournament.sh
  head_to_head_team_intl_bilateral.sh
  head_to_head_team_intl_tournament.sh
```

## Per-script structure (DRY this when we extract)

Every script follows the layout established by
`compare_avg_chips.sh`:

1. **Anchor URL** — points at a closed historical window so the
   expected values stay stable across DB rebuilds. Recommended
   anchors:
   - INTL: `gender=male&team_type=international&season_from=2024&season_to=2025`
     (Aus + India for team-coverage; Men's T20I 2024-2025 for pool).
   - CLUB: `gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2025&season_to=2025`
     (RCB + SRH for team-coverage; IPL 2025 for pool — 74 matches).
   - WOMEN'S CLUB: `gender=female&team_type=club&tournament=Women's+Premier+League&season_from=2024&season_to=2024`
     (closed; small but useful as a non-male sanity).
2. **Extractor** — `agent-browser eval --stdin` with an IIFE that
   walks the rendered DOM, pulls labels + values + (where present)
   chip tooltips, returns a structured object. Pretty-printed JSON
   is fine — `python3 -c 'json.load(...)'` consumes it.
3. **Expected dict** — Python literal in a heredoc. Keys are
   "section / row" labels matching the rendered text. Values are
   `{value, chip_value, chip_avg, chip_delta}` where chip components
   are present.
4. **Ground truth provenance** — comment block at top of every
   script citing **how the expected numbers were derived** + a
   pointer to the SQL audit (linked or inline). Numbers come from
   an independent SQL implementation, NOT from the API. The
   `compare_avg_chips.sh` doc-comment is the template.
5. **Tolerances** — `EPS_PCT` (chip delta, percentage points) and
   `EPS_NUM` (numeric values, single-decimal rounding). Defaults
   `0.2` and `0.15` cover all observed cases.
6. **Math invariant** — every chip-bearing row asserts `delta_pct =
   (value - scope_avg) / scope_avg × 100 ± EPS_PCT`. This catches
   the bug class where the chip lies about the relationship between
   value and avg (the original 2026-04-27 reproducer).

## Ground-truth provenance — hard rule

The expected numbers MUST be computed by something other than the
API code path under test. Three acceptable sources:

1. **Subagent isolation** — a subagent gets explicit "do NOT read
   `api/` or `tests/sanity/`" instructions and writes its own SQL
   from the schema. Used for the Compare tab; pattern in the
   `compare_avg_chips.sh` ground-truth derivation. This is the
   gold-standard.
2. **Hand-written SQL audit** — a `audit/<test-name>.sql` file
   alongside the script, runnable as `sqlite3 cricket.db < ...sql`,
   producing the expected numbers in a printable form. Each script
   cites its audit file.
3. **Cross-window comparison** — for trend assertions, the same
   computation across two windows. Doesn't establish absolute
   correctness but catches regressions that affect both windows
   uniformly.

NEVER copy expected numbers from the running API and then assert
the API returns them — that's a tautology, not a test.

## What gets covered per tab/sub-tab

The intent is to lock down EVERY visible number on the chosen
anchor URL. A script that asserts only headers and section
presence is incomplete. Per cell:

- Display text (rounded value as user sees it).
- Chip envelope (parsed from `MetricDelta` `title=` attr — NOT
  re-derived).
- Chip math invariant.
- Where applicable, identity-line text (`X matches`, `Y wickets`,
  etc.).

For tabular surfaces (DataTable, leaderboards), every visible row
on the first page is asserted by (rank, value), not just the top
row. A "top scorer" leaderboard with a wrong order shows the right
top row; the assertion catches the misorder by checking row 5 too.

## Trigger conditions — when to run each script

These scripts are heavyweight (browser navigation + DOM extraction
+ python diff per anchor). Don't run all of them on every commit.
Run the relevant ones:

- Touched FilterParams, AuxParams, scope-link URL builder, or any
  filter clause builder → run **all** DOM tests.
- Touched a specific tab's components → run that tab's scripts
  (both intl + club twins).
- Touched a shared discipline helper (`_compute_batting_summary`
  etc.) → run the affected discipline's scripts across every tab.
- Touched `populate_*.py` / `import_data.py` / `update_recent.py`
  → run all DOM tests against the rebuilt DB.

## Cross-cutting patterns to extract

Once 4-5 scripts exist, lift the shared bits into
`tests/integration/dom/_lib.sh`:
- `extract_grid_columns` — for `wisden-compare-col` based pages.
- `extract_data_table` — for `DataTable` based pages (Series,
  Records, Matches, partnerships).
- `extract_band_metrics` — for `wisden-player-section` based pages
  (single-team summaries).
- `run_python_diff` — the heredoc'd python diff harness.

Until then, copy the harness from `compare_avg_chips.sh` per script
— easier to read than a stub.

## Open questions (for next-session decisions)

- **Series-tab `series_type` axis** — bilateral vs tournament are
  semantically different rollups. Three scripts per subtab
  (`_intl.sh` for unset, `_intl_bilateral.sh`, `_intl_tournament.sh`)
  or one script with three navigations? Lean: three scripts —
  surface-area is the same and isolation is cheap.
- **Anchor URL stability** — the IPL 2025 anchor relies on the
  2025 season being closed. As soon as IPL 2026 starts, the
  "tournament=Indian Premier League&season_from=2025&season_to=2025"
  numbers stay locked (closed window) — but if any 2025 match was
  retroactively rebuilt, the script catches the change. That's the
  point. Don't migrate anchors forward unless a number changes
  intentionally.
- **DB-grounded vs DOM-grounded for backend-only tests** — for
  endpoints that don't render in the UI (admin, internal), the
  same pattern applies but skip the agent-browser layer. They
  belong in `tests/sanity/`, not here.

## Pre-requisite: full-member on FilterBar

Several of the wanted scripts (especially Teams ones for
internationals) become more interesting once `team_class=full_member`
is on the FilterBar — see `spec-filterbar-team-class.md`. The same
DOM-grounded pattern applies, just with a wider FilterBar surface.
The numbers for Aus/India CHANGE when team_class is on the
FilterBar (Aus matches 22 → 16 since Scotland/Namibia matches drop
out), so the spec for that change includes test-update line items.
