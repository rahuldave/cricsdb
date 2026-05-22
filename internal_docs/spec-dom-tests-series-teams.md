# Spec — agent-browser eval pattern: Series + Teams end-to-end

> **Status:** SHIPPED. Batch 2 wrap commit `4ace499`; tests live under
> `tests/integration/dom/series_*` and `tests/integration/dom/teams_*`.
> Pre-condition `team_class=full_member` on the FilterBar shipped via
> `spec-filterbar-team-class-v3.md` (5 commits 2026-04-28).

End-to-end DOM-grounded test inventory for the Series and Teams
tabs (and their sub-tabs). Companion to
`spec-dom-grounded-tests.md` (the umbrella) and
`spec-filterbar-team-class.md` (the FilterBar promotion this spec
ASSUMES is shipped).

## Pre-condition

This spec assumes `team_class=full_member` is on the FilterBar.
The intl-anchor URLs include `&team_class=full_member` so the
match pool is FM-only and the per-team scope on the team-side
matches what the avg col shows. Without that promotion, the
intl-anchor scripts would still run but the chip ↔ avg agreement
test (AXIS B) wouldn't hold for those URLs (per the
2026-04-27 chip_team_class follow-up — the per-slot mechanism
covers the asymmetric case but isn't ergonomic at scale).

## Coverage map

| Tab | Sub-tab | club anchor | intl anchor | bilateral anchor | comments |
|---|---|---|---|---|---|
| Teams | (Identity / By Season default) | RCB IPL 2025 | India men_intl 2024-25 + FM | — | summary + by-season chart |
| Teams | vs Opponent | RCB vs MI IPL 2025 | India vs Aus 2024-25 + FM | — | head-to-head subtab |
| Teams | Compare | RCB+SRH IPL 2025 | Aus+Ind 2024-25 + FM | — | the existing `compare_avg_chips.sh` covers this |
| Teams | Batting | RCB IPL 2025 | India 2024-25 + FM | — | per-discipline summary card stack |
| Teams | Bowling | RCB IPL 2025 | India 2024-25 + FM | — |  |
| Teams | Fielding | RCB IPL 2025 | India 2024-25 + FM | — |  |
| Teams | Partnerships | RCB IPL 2025 | India 2024-25 + FM | — | top-N partnerships + by-wicket grid |
| Teams | Players | RCB IPL 2025 | India 2024-25 + FM | — | roster grid |
| Teams | Match List | RCB IPL 2025 | India 2024-25 + FM | — | DataTable per-match row checks |
| Series | (Landing) | tournament directory club | tournament directory intl | — | filter-sensitive tile counts |
| Series | Overview | IPL 2025 dossier | T20 WC Men 2024 dossier | India vs Aus rivalry (filter_team+filter_opponent) | first-class dossier rendering |
| Series | Editions | IPL all editions | T20 WC Men all editions | — |  |
| Series | Batters | IPL 2025 batting leaders | T20 WC Men 2024 batting leaders | — | by-runs + by-avg sub-tables |
| Series | Bowlers | IPL 2025 bowling leaders | T20 WC Men 2024 bowling leaders | — |  |
| Series | Fielders | IPL 2025 fielders | T20 WC Men 2024 fielders | — |  |
| Series | Partnerships | IPL 2025 partnerships | T20 WC Men 2024 partnerships | — | per-wicket grid + records |
| Series | Records | IPL 2025 records | T20 WC Men 2024 records | — | highest, biggest wins, etc. |
| Series | Matches | IPL 2025 matches | T20 WC Men 2024 matches | — | DataTable per-match |
| Series | Champions | (n/a — IPL doesn't have a "champions" tab when single-season) | T20 WC Men all years | — | ICC events only |
| Series | Knockouts | (n/a) | T20 WC Men 2024 knockouts | — | ICC events only |
| Series | Points | IPL 2025 points table | (n/a — no league-table for ICC events) | — | club only |

Total per-tab files: ~22 club + ~22 intl + 1 bilateral = 45 scripts.
Run them all under `tests/integration/dom/` per the umbrella spec.

## Anchor URLs (canonical per scope-class)

### Club — IPL 2025 (74 matches, closed)

```
/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&season_from=2025&season_to=2025
/teams?team=Royal+Challengers+Bengaluru&gender=male&team_type=club&season_from=2025&season_to=2025&tab=<sub-tab>
/series?tournament=Indian+Premier+League&gender=male&team_type=club&season_from=2025&season_to=2025
/series?tournament=Indian+Premier+League&gender=male&team_type=club&season_from=2025&season_to=2025&tab=<sub-tab>
```

### International — Men's T20I 2024-2025 + FM-only (closed, FM=140 matches)

```
/teams?team=India&gender=male&team_type=international&season_from=2024&season_to=2025&team_class=full_member
/teams?team=India&...&team_class=full_member&tab=<sub-tab>
/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&season_from=2024&season_to=2024&team_class=full_member
/series?...&team_class=full_member&tab=<sub-tab>
```

### Bilateral — India vs Aus 2024-25 (closed)

```
/series?filter_team=India&filter_opponent=Australia&gender=male&team_type=international&series_type=bilateral&season_from=2024&season_to=2025
```

A single bilateral anchor — fewer sub-tabs apply (no Champions, no
Points, no Editions for a rivalry).

## Per-script structure

Lift the harness already proven in
`tests/integration/compare_avg_chips.sh` into a shared library
`tests/integration/dom/_lib.sh`. Each per-tab script becomes:

```bash
#!/bin/bash
set -u
source "$(dirname "$0")/_lib.sh"

ANCHOR="$BASE/teams?team=Royal+Challengers+Bengaluru&...&season_from=2025&season_to=2025&tab=Bowling"
GROUND_TRUTH=$(cat <<'PYEXPECT'
{
  "Royal Challengers Bengaluru": {
    "rows": {
      ("Headline", "Matches"): {"value": 15},
      ("Headline", "Innings bowled"): {"value": 15},
      ("Headline", "Wickets"): {"value": 87, "chip_value": 87, "chip_avg": 70.4},
      ("Headline", "Economy"): {"value": 9.24, "chip_value": 9.24, "chip_avg": 9.63},
      ...
    },
    "phase_bands": {
      "Powerplay":   {"economy": ..., "wickets": ...},
      "Middle":      {...},
      "Death":       {...},
    },
  },
}
PYEXPECT
)

navigate "$ANCHOR" "Bowling sub-tab — RCB IPL 2025"
JSON=$(extract_team_subtab)
run_assertions "RCB Bowling IPL 2025" "$JSON" "$GROUND_TRUTH"

print_summary
```

`_lib.sh` provides:
- `extract_team_subtab` — DOM extractor returning `{rows, phase_bands, partnerships_grid, ...}` for any tab on `/teams?team=…&tab=…`.
- `extract_series_subtab` — same shape for `/series?…&tab=…`.
- `extract_data_table` — for tabular sub-surfaces (Matches list, leaderboards, partnerships top-N).
- `run_assertions` — the python diff harness from
  `compare_avg_chips.sh` lifted out.
- `navigate` — wraps `agent-browser navigate` + 3s soak.
- `print_summary` — final pass/fail count.

## Coverage per cell

For every visible NUMBER on the anchor page, assert one of:
1. **Display text** matches expected (e.g. "Run rate ... 9.91↑ +24.9%").
2. **Chip envelope** (parsed from MetricDelta tooltip's `title=`)
   has the right value, scope_avg, delta_pct.
3. **Math invariant**: displayed delta = (value − avg) / avg × 100 ± 0.2 pp.

For tabular surfaces (DataTable rows), assert at least:
- Top-3 rows by (rank, value).
- Total row count (vs DataTable's "showing N of M").
- Cell-level on the FIRST and LAST row of the visible page (catches
  ordering bugs that show the right top row but wrong tail).

## Ground-truth provenance — hard rule

Every script MUST cite where its expected numbers came from. Two
acceptable sources:
1. **DB-only subagent** (the model used in `compare_avg_chips.sh`).
   The subagent gets the schema + prose metric definitions and
   writes its own SQL, NOT reading any `api/` source.
2. **`tests/integration/dom/audit/<script-name>.sql`** — committed
   audit SQL in the same PR. Script docstring points at it.

A test that takes its expected numbers from the live API is a
tautology — it asserts only that the API agrees with itself. Don't
do that.

## Inter-tab coherence (cross-cutting test)

Some numbers are repeated across tabs — Aus's 16 matches in FM-only
2024-25 should show on:
- `/teams?team=India&...&team_class=full_member` Match List total
- `/teams?team=India&...&team_class=full_member&tab=Compare` column header
- `/series?...&team_class=full_member` India tile match count
- `/head-to-head?team1=India&team2=Australia&...&team_class=full_member` rivalry by-team breakdown

Add **`tests/integration/dom/cross_cutting_team_class_consistency.sh`**
that anchors at four URLs and asserts the SAME number renders in
each of them. Catches the bug class where one tab's filter wiring
diverges from another's.

## Phasing — 3 batches

Don't ship 45 scripts in one commit. Phase as:

### Batch 1 — ✅ shipped 2026-04-28

- `teams_compare_intl.sh` — anchors A (unbounded), A' (FM-only avg
  slot), E1 (FilterBar fm — 3 cols inherit). 68 assertions.
- `teams_compare_club.sh` — anchor B (IPL 2025 + RCB + SRH + IPL
  avg). 26 assertions.
- `teams_match_list_intl_fm.sh` — anchors M1 (Aus unbounded → 22,
  oldest row vs Oman) and M2 (FM-only → 16, oldest vs England).
  Proves the FilterBar narrowing on the match-list endpoint.
  15 assertions.
- `series_landing_intl_fm.sh` — anchors L1 (T20 WC tile = 44, ACC
  Premier Cup tile = 24) and L2 (T20 WC narrows to 16, ACC tile
  vanishes — narrowed to 0 = endpoint omits). 4 assertions.

113 assertions across 9 anchors, all green. Harness lifted into
`tests/integration/dom/_lib.sh` (extractors for compare grids,
DataTables, landing tiles + 3 assert runners). Ground-truth SQL
under `tests/integration/dom/audit/`.

The original `tests/integration/compare_avg_chips.sh` was deleted
as part of the lift — its 4 anchors are split across the two new
`teams_compare_*.sh` files with the same harness body and updated
to reflect the 2026-04-28 per-team-transform DOM (avg col matches
identity now reads "N matches in scope" per-team, not absolute
pool).

### Batch 2 — ✅ shipped 2026-04-28

7 pairs (14 scripts), 240 assertions, all green. Each pair shares
extractor + ground-truth derivation; one new
`extract_team_overview` extractor added to `_lib.sh` (single-team
`.wisden-statrow`). Per-pair counts:

- `teams_overview_{intl,club}.sh` — 20 (Aus 2024-25, RCB IPL 2025).
- `teams_batting_{intl,club}.sh` — 72 (15 StatCards × 2, ~5 chip
  envelopes each).
- `teams_bowling_{intl,club}.sh` — 74 (12 StatCards × 2, ~5 chip
  envelopes each).
- `teams_fielding_{intl,club}.sh` — 42 (8 StatCards × 2, 3 chips).
- `teams_partnerships_{intl,club}.sh` — 18 (10-row by-wicket grid,
  asserts top + last). **UI bug caught + fixed:** the by-wicket
  DataTable rendered `n` and `avg_runs` chip envelopes as
  "[object Object]" because there was no `format` function —
  added narrow `.value` extractors with graceful fallback.
- `series_overview_{intl,club}.sh` — 14 (T20 WC Men 2024;
  IPL 2025).
- `series_records_{intl,club}.sh` — 18 (highest team totals
  table — first DataTable on the Records tab; required +4s soak
  for the 5+ DataTable fan-out).

Leaders cards (Most titles, Top scorer, Top wicket-taker on
Series Overview) deferred to Batch 3 leader-extractor — they
contain composed TeamLink/PlayerLink + subtitle compounds that
need a more careful parser.

### Batch 3 ✅ shipped 2026-04-29 (14 commits across 3a/3b/3c)

- 3a — Teams completion + Series Landing club twin (6 scripts).
- 3b — Series sub-tabs (12 scripts) + harness extension
       (`extract_data_table` accepts ordinal index 0..N).
- 3c — ICC-only specials, club-only Points, plus the keystone
       `cross_cutting_team_class_consistency.sh` test that exercises
       the FilterBar's `team_class=full_member` narrowing across 4
       distinct UI surfaces (consistency S1==S2==16, sensitivity
       S3 1→0 with FM, S4 44→16 with FM).

Full dom/ suite at end of Batch 3: **41 scripts, ~720 assertions**,
all PASS. See `internal_docs/spec-dom-tests-batch-3.md` for the
sub-batch-by-sub-batch playbook used.

## Anti-pattern guardrails

Block at PR-review time:
- A new DOM-test that reads expected numbers from the API.
- A script asserting only "page contains Aus" (presence — not enough).
- A new per-tab helper that duplicates an existing extractor.

Lift each script's expected dict from a comment block at the top
that says where numbers came from. PR diff makes provenance visible.

## Performance considerations

Each script does ≥1 navigation + ≥1 extraction + python diff.
~5s per script. 45 scripts ≈ 4 minutes. Don't run on every commit
— gate behind a make target like `make dom-tests` and run
selectively per the umbrella's "trigger conditions" rules.

For CI (when we have one), run the 4 Batch-1 scripts on every PR
that touches anything in `api/routers/`, `frontend/src/components/teams/`,
or `frontend/src/components/tournaments/`. Run the full 45 on
nightly runs against the snapshot DB.

## Snapshot DB caveat

These scripts are anchored to closed historical windows so the
expected values stay stable across DB rebuilds — but a cricsheet
retroactive edit (rare, audited via `update_recent.py --dry-run`)
WILL flip a number. When that happens the diff appears as
"NEW changed" on the regression suite (which mirrors the same
URLs with byte-level hashes); investigate, update the integration
script's expected dict (and re-derive ground truth), commit.

When closed-window numbers move, that's the audit trail —
we WANT the test to fail noisily so we know cricsheet has been
mutated.
