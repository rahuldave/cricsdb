# Narrowing audit — findings (frozen-surface work items)

Companion to `narrowing-audit-coverage.md`. This is where any surface that
**should** narrow under the six (venue/opponent/team/inning/toss/result) but
was found **frozen** at the DOM level gets recorded — URL + what's frozen +
suspected source + fix options — for a decision AFTER the audit, without
fixing mid-audit.

## Status (2026-05-29): no open frozen surfaces

The DOM-level audit found **zero** frozen surfaces. Every headline tile,
graph, and sparkline that should narrow was confirmed moving on screen; the
per-position / per-over mix histograms correctly stay coarse. Nothing here to
revisit.

### Resolved watch-item — the sparkline green cohort line

The post-3e plan flagged the Distribution-panel **sparkline green "cohort at
scope" line** as the likely-remaining Tier-3 (frozen) surface — it was "not
touched by 3b–3e / Phase B".

**Resolved: it already narrows.** The green line (`line[data-ref=league]`)
reads the same `scope_avg` envelope as the headline "vs cohort" chip
(`leagueReferenceValue` ← `leagueSR`/`leagueRuns`/`leagueWpi`/`leagueEcon`/
`refs.league`), and 3b/3d/3e made that envelope narrow live. DOM-verified the
line's `y1` and legend move under inning (and the other axes) on:
- batting (y1 24.44→24.18; legend 26.7→27.6 runs/inn),
- bowling (y1 25.42→23.98; 1.03→1.00 wkts/inn),
- fielding (y1 27.33→26.73; 0.58→0.49 catches/match),
- teams batting panel (y1 11.05→9.82).

The only gap was **test coverage** (no test asserted the movement) — closed by
`tests/integration/sparkline_narrowing.sh` (Phase 4), not a code change.

### Intentionally-coarse surfaces (NOT findings — leave as-is)

- Per-position mix histogram (batting By Position) and per-over mix histogram
  (bowling By Over) — the weighting; coarse by design (Tier 2). Verified
  unchanged under inning ("Open 52.0%" identical).
- The gender-global grey static sparkline line — scope-independent by design.
