# Spec — Unify the inning filter on "batted-first" semantics (Option B)

**Status:** PLAN — not yet implemented. Supersedes the per-discipline
"innings-number / bowled-first" framing in `spec-inning-split.md` §1,
§3.4, §7. Decision date: 2026-05-25.

## 1. The decision

Today the app uses **two clashing meanings** for `?inning=`:
- Match-level endpoints (teams `/summary`, By Season, vs Opponent,
  Match List) → `_inning_match_filter` → `inning=0` = **team batted
  first** (a match subset).
- Per-discipline surfaces (player `/batting`,`/bowling`,`/fielding`;
  teams Batting/Bowling/Fielding/Partnership bands; Compare slots) →
  central clause `i.innings_number = :inning` → `inning=0` = events in
  the match's first half, i.e. **bowled-first** for bowling/fielding.

Symptom (CSK Bowling, `inning=0`): scope strip says "batted first",
mosaic/toggle/chart say "bowled first", and the data is the 122
bowled-first matches (batted-first would be 144). One page, three
labels, one of them wrong.

**Unify on the match-level meaning everywhere:**

> `inning=0` ≡ the subject's team **batted first** (innings_number 0).
> `inning=1` ≡ the subject's team **batted second**.
> For bowling/fielding this is the team's activity in those matches —
> which is the *other* innings. So **"bowled first" = batted second =
> `inning=1`** and **"bowled second" = batted first = `inning=0`**.

### 1.1 Label ↔ value contract (the crux)

| POV (via `useDiscipline()`) | Pill "first" | writes | Pill "second" | writes |
|---|---|---|---|---|
| batting / neutral | "1st innings" / "Batted first" | `inning=0` | "2nd innings" / "Batted second" | `inning=1` |
| **bowling / fielding** | **"Bowled first"** | **`inning=1`** | **"Bowled second"** | **`inning=0`** |

So on bowling/fielding surfaces the toggle's *value is flipped* vs the
label's first/second — because the team bowls in the innings it did
NOT bat. Everywhere else the value matches the ordinal.

### 1.2 URL impact
- `inning` param key unchanged; values still `0|1`.
- **Batting** surfaces: meaning unchanged (`inning=0` was and stays
  batted-first). Old links stable.
- **Bowling/Fielding** surfaces: today's `inning=0` view (bowled-first)
  moves to `inning=1`. Old `inning=0` bowling links now show batted-
  first (2nd-innings) bowling. No errors, different numbers.

## 2. Backend mechanism

One shared idea: **inning narrows to the match subset where the
subject's team batted in innings_number = N**, never to the event's
own innings_number.

- **Teams** (subject = path team): already correct via
  `_inning_match_filter` (`api/routers/teams.py`). Audit that EVERY
  team discipline endpoint routes inning through it, not through the
  central `i.innings_number` clause.
- **Players** (subject = `matchplayer.team` per match): NEW
  `player_inning_match_clause(aux, person_id, params, match_id_expr)`
  in `api/filters.py`, sibling to `player_result_clause`:
  ```sql
  <match_id_expr> IN (
    SELECT i2.match_id FROM innings i2
    JOIN matchplayer mp2 ON mp2.match_id = i2.match_id
                        AND mp2.person_id = :pid AND mp2.team = i2.team
    WHERE i2.innings_number = :inn AND i2.super_over = 0)
  ```
  Inject into the 5 discipline filter helpers; REMOVE reliance on the
  central `i.innings_number = :inning` clause for player endpoints.
- **Central clause** (`FilterBarParams.build`) + `aux_clauses.InningClause`:
  must STOP emitting `i.innings_number = :inning` for these surfaces.
  Decide: gate it off for player/team discipline queries (they now use
  the match-subset clause) — keep only if a surface genuinely wants
  raw innings_number (none after this change; confirm none remain).

## 3. Call-site / tab table (USER-FACING — one integration test each)

Status legend: ☐ todo · ◑ code done · ✓ code+test green.

| # | Surface · tab | Widget | inning=0 today | inning=0 target | Label change | Integration test | Status |
|---|---|---|---|---|---|---|---|
| U1 | `/batting?player` (all tabs) | InningToggle | batted 1st | batted 1st | none (already "Batting first") | `inning_unify_players.sh` | ✓ toggle+summary; ◑ deep tabs (1b) |
| U2 | `/bowling?player` (all tabs) | InningToggle | bowled 1st | **batted 1st** (bowled 2nd) | "Bowling first" → inning=1 (value-flip) | `inning_unify_players.sh` | ✓ toggle+summary+by-X; ◑ vs-Batters (1b) |
| U3 | `/fielding?player` (all tabs) | InningToggle | fielded 1st | **batted 1st** (fielded 2nd) | "Bowling first" → inning=1 | `inning_unify_players.sh` | ✓ toggle+summary+matches; ◑ victims/keeping (1b) |
| U4 | `/players?player` summary | InningToggle (neutral) | mixed/polysemy | batted 1st (all 4 tiles + matches) | neutral "1st innings" = batted 1st | `inning_unify_players.sh` | ✓ (matches 206/190 = SQL) |

> **Phase 1 (players) progress — 2026-05-25:** A1 (clause+flag), the 5
> discipline filter helpers, fielding `matches`, batting dismissals,
> the toggle value-flip (U1–U4), ScopeStatusStrip + abbreviateScope POV
> (U16/U17) — all DONE + green (`inning_unify_players.sh` 5/5).
> **Phase 1b (players remainder, still per-event):** batting
> dismiss-overlay subqueries (by-over/phase/season), vs-Bowlers
> (1274), Inter-Wicket (1327), Distribution (1875); fielding Victims +
> keeping sub-stats (fielding 424); keeping endpoints (140/394); the
> cohort dismissals endpoint (A8). These show old per-event inning
> under the flipped toggle until wired. Phases 3–5 (teams/series/
> venues) untouched.
| U5 | `/teams?team` Batting | SplitsMosaic + scope strip | batted 1st | batted 1st | none | `inning_unify_teams_batting.sh` | ☐ |
| U6 | `/teams?team` Bowling | SplitsMosaic + scope strip | bowled 1st | **batted 1st** | scope strip + mosaic + chart all "batted first" | `inning_unify_teams_bowling.sh` | ☐ |
| U7 | `/teams?team` Fielding | SplitsMosaic + scope strip | bowled/fielded 1st | **batted 1st** | unify labels | `inning_unify_teams_fielding.sh` | ☐ |
| U8 | `/teams?team` By Season / vs Opp / Match List | (match-level) | batted 1st | batted 1st | none | covered by U5 harness | ☐ |
| U9 | `/teams?team` Partnerships | SplitsMosaic | batted 1st | batted 1st | none | `inning_unify_teams_pship.sh` | ☐ |
| U10 | `/teams?team` Players | SplitsMosaic | per-row inning | batted 1st (each row's team subset) | none | `inning_unify_teams_players.sh` | ☐ |
| U11 | `/teams?team` Compare | SlotScopeEditor | dual-meaning (§3.4) | single batted-1st subset per slot | drop dual-meaning tooltip | `inning_unify_compare.sh` | ☐ |
| U12 | `/series?tournament` Bowling/Fielding | InningToggle | bowled 1st | batted 1st | flip value | `inning_unify_series.sh` | ☐ |
| U13 | `/series?tournament` Batting/Pship/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ☐ |
| U14 | `/venues?venue` Bowlers/Fielders | InningToggle | bowled 1st | batted 1st | flip value | `inning_unify_venues.sh` | ☐ |
| U15 | `/venues?venue` Batters/Records | InningToggle | batted 1st | batted 1st | none | (same harness) | ☐ |
| U16 | ScopeStatusStrip (every tab) | label only | POV mislabel (CSK bug) | matches the toggle's POV phrase | fix POV derivation | asserted in each U* harness | ☐ |
| U17 | abbreviateScope (chart subtitles) | label only | POV "bowled first" | POV consistent w/ toggle | align | asserted in U2/U6 harnesses | ☐ |
| U18 | user-help.md "Innings toggle" | docs | bowled-first examples | batted-first examples | rewrite §Innings toggle | n/a (content) | ☐ |

## 4. API table (endpoint consistency — one regression test each)

Regression = `tests/regression/` URL list; DB-anchored = a sanity test
that re-derives the expected match subset from sqlite at runtime.

| # | Endpoint(s) | inning today | inning target | Change | Test | Status |
|---|---|---|---|---|---|---|
| A1 | `filters.player_inning_match_clause` (NEW) + `build(apply_inning=…)` flag | — | match subset (player team batted in N) | add helper + flag | `test_inning_clause.py` (DB-anchored) | ◑ inert (added, unwired) |
| A2 | `/batters/{id}/summary` (+ by-season/over/phase/innings/dismissals) | innings_number | match subset | inject A1, drop central inning | `regression/batting` + `inning_unify_batting.sh` | ☐ |
| A3 | `/bowlers/{id}/*` | innings_number (bowled 1st) | match subset | inject A1 | `regression/bowling` | ☐ |
| A4 | `/fielders/{id}/*` (+ keeping) | innings_number | match subset | inject A1 | `regression/fielding` | ☐ |
| A5 | `/teams/{team}/summary,by-season,vs,match-list` | batted 1st (`_inning_match_filter`) | unchanged | audit only | `regression/teams` | ☐ |
| A6 | `/teams/{team}/{batting,bowling,fielding,partnerships}/{summary,by-phase,by-season,top-*}` | innings_number | `_inning_match_filter` subset | route through match filter | `regression/teams` | ☐ |
| A7 | `/teams/{team}/{...}/by-inning` band endpoints | innings_number band | RE-FRAME: band keyed by team-batting-innings | redefine band axis | `inning_band.sh` | ☐ |
| A8 | `/scope/averages/...` cohort (inning-aware) | innings_number | match subset (cohort weighting) | audit + align | `regression/scope` | ☐ |
| A9 | `/tournaments/*` (series dossier leaderboards) | innings_number | match subset | inject | `regression/series` | ☐ |
| A10 | `/venues/*` leaderboards | innings_number | match subset | inject | `regression/venues` | ☐ |
| A11 | `aux_clauses.InningClause` | `i.innings_number=:inning` | remove/repurpose | retire for these surfaces | covered by A2-A10 | ☐ |
| A12 | `bucket_baseline_dispatch.py` | innings_number gate | match subset / live fallback | audit precompute path | `regression/*` drift | ☐ |

## 5. Resolved decisions (2026-05-25)

1. **`/by-inning` band charts (A7) — RESOLVED: label audit only.** The
   bands are a display of both halves (not toggle-driven). On
   bowling/fielding pages they read "Bowled first / Bowled second"
   (unambiguous per §1 discipline-page rule); on batting, "Batted
   first / second." No re-aggregation — just audit the bar label +
   order so "Bowled first" sits on the innings_number-0 bowling data.
2. **Cohort baselines under inning (A8) — RESOLVED: recompute to align
   language.** Precompute already exists; it may need re-running so the
   stored split matches the unified meaning. Acceptable to fall to the
   live path where precompute can't express the match-subset.
3. **Compare dual-meaning (U11/§3.4) — RESOLVED: DROP it.** A Compare
   slot is multi-discipline (same shape as the main `/players` page),
   so one slot = one batted-first/second **match subset** across batting
   AND bowling rows. To compare a team's 1st vs 2nd innings you set one
   slot `inning=0` and the other `inning=1` — unambiguous. The §3.4
   same-token cross-read is intentionally retired.

### Governing rule (locked)
- **Multi-discipline surfaces, one neutral toggle** (main `/players`;
  Teams Compare slots): "1st innings" = team **batted first**; bowling/
  fielding tiles draw from those matches = their 2nd-innings work
  (`inning=1` data). Verbally "1st innings" but bowling comes from the
  2nd innings — coherent because one toggle governs all disciplines.
- **Single-discipline pages** (`/batting`,`/bowling`,`/fielding` for
  players AND teams): POV-specific unambiguous labels — "Bat first/
  second" on batting, "Bowl first/second" on bowling+fielding.
  "Bowl first" = `inning=1`; "Bowl second" = `inning=0`.

## 6. Sequencing

1. Backend A1 + A2–A4 (players) + DB-anchored test → players coherent first.
2. Frontend U1–U4 (toggle value-flip + labels + scope strip) + tests.
3. Backend A5–A7 (teams) + A8.
4. Frontend U5–U11 (teams mosaic/scope/compare) + tests.
5. Series + venues A9/A10 + U12–U15.
6. Docs: rewrite `spec-inning-split.md` §1/§3.4/§7, CLAUDE.md inning rule,
   `inning-controls-mount-sites.md`, user-help.md (U18).
7. Regression REG→NEW flips (A2–A10) in a PRECEDING commit per the
   regression-before-shape rule.

## 7. Test doctrine
- Every U-row: load the page in agent-browser at `inning=0` and
  `inning=1`, assert the rendered headline matches a sqlite-derived
  match-subset count, AND assert the toggle/scope-strip/mosaic labels
  agree with each other (the CSK-mismatch regression guard).
- Every A-row: curl endpoint at `inning=0|1`, assert value == sqlite
  match-subset re-derivation; add the URL to the matching
  `tests/regression/*/urls.txt` (flip REG→NEW first).
