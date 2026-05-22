# Absolute vs Per-Innings Audit + Fix Spec

**Status:** SHIPPED 2026-05-20 (21 commits). Fixes 8 ⚠️ tiles + 3 wrong chart overlays + adds 12 new tiles + 5 new charts across the player pages. Memory: `spec_rate_vs_volume_audit.md`.
**Triggered by:** Kohli IPL profile after `spec-player-baseline-parity.md` Phase F — tiles like "100s 9 — vs base 0.006 ↑+450%" pair an absolute count (9) with a per-innings rate chip (0.006), which makes no sense to a reader.

## 1. The rule

Every stat tile is one of two things:

- **Absolute** — a count over scope. Magnitude reflects opportunity; not directly comparable across players. Examples: `Runs`, `100s`, `Catches`, `Maiden Overs`, `Wickets`, `Innings`.
- **Per-innings (or per-match)** — a rate. Comparable across players regardless of career length. Examples: `Avg`, `SR`, `100s/Inn`, `Catches/Match`, `Econ`, `Wkts/Inn`.

**Display rule:**
- Absolute tile → bold value only; no baseline chip.
- Per-innings tile → bold rate + "vs base N · ↑+M%" chip.

**Coverage rule:**
- Every absolute on the page should have a sibling per-innings tile (where the rate is meaningful) so the reader gets both the count AND the comparison.
- "Show both" — the user requirement.

**Plots follow the same rule:**
- Absolute-per-season chart (e.g. Runs by Season) → no baseline overlay.
- Per-innings-per-season chart → green baseline overlay.

Same logic for by-phase / by-over charts.

---

## 2. Backend foundation (ships first)

The new per-innings tiles + per-rate charts need data on both the **player side** endpoints AND the **cohort side** endpoints. Cohort side largely already has the per-innings rates (shipped session 1 of `spec-player-baseline-parity.md`); the player side needs them threaded through.

### 2.1 Inventory — what exists vs what's missing

#### Player `/summary` endpoints (envelopes)

| Endpoint | Field | Exists? | Action |
|---|---|---|---|
| `/batters/{id}/summary` | `runs_per_innings` | NO | **Add envelope** (numerator: runs; denominator: innings_total) |
| `/batters/{id}/summary` | `hundreds_per_innings` `fifties_per_innings` `thirties_per_innings` `ducks_per_innings` `fours_per_innings` `sixes_per_innings` `boundaries_per_innings` | YES (Phase F) | None |
| `/bowlers/{id}/summary` | `four_wicket_hauls_per_innings` | NO | **Add envelope** (numerator: 4-fers; denominator: innings) |
| `/bowlers/{id}/summary` | `wickets_per_innings` `maidens_per_innings` | YES (Phase F) | None |
| `/fielders/{id}/summary` | `catches_per_match` `stumpings_per_match` `run_outs_per_match` `dismissals_per_match` | YES (Phase E) | None |

#### Cohort `/scope/averages/players/*/summary` endpoints

| Endpoint | Field | Exists? | Action |
|---|---|---|---|
| `/players/batting/summary` | `runs_per_innings` | NO | **Add** mirror of player-side |
| `/players/batting/summary` | hundreds_per_innings etc. | YES (Phase F) | None |
| `/players/bowling/summary` | `four_wicket_hauls_per_innings` | NO | **Add** mirror |
| `/players/bowling/summary` | wickets/maidens per innings | YES (Phase F) | None |
| `/players/fielding/summary` | catches/stumpings/run_outs/dismissals per match | YES (Phase E) | None |

#### Player `/by-season` endpoints

Currently emit volume counts + already-rate fields (Avg, SR, Econ, etc.) per season. Missing: per-innings/per-match rate counterparts.

| Endpoint | Currently has | Missing — needs adding |
|---|---|---|
| `/batters/{id}/by-season` | runs, balls, average, strike_rate, fours, sixes, fifties, hundreds, dismissals, balls_per_*, dot_pct, boundary_pct, boundaries, dots, innings, season | `runs_per_innings`, `hundreds_per_innings`, `fifties_per_innings`, `thirties_per_innings`, `ducks_per_innings`, `fours_per_innings`, `sixes_per_innings`, `boundaries_per_innings` (all per-season) |
| `/bowlers/{id}/by-season` | wickets, runs_conceded, balls, dots, fours, sixes, economy, average, strike_rate, dot_pct, boundary_pct, balls_per_*, overs, innings, season | `wickets_per_innings`, `maidens_per_innings`, `four_wicket_hauls_per_innings` (all per-season) |
| `/fielders/{id}/by-season` | catches, stumpings, run_outs, caught_and_bowled, total, matches, season | `dismissals_per_match`, `catches_per_match`, `stumpings_per_match`, `run_outs_per_match` (all per-season; trivially derivable from existing volume / matches) |

#### Cohort `/scope/averages/players/*/by-season`

| Endpoint | Currently has | Missing — needs adding |
|---|---|---|
| `/players/batting/by-season` | total_runs, run_rate, strike_rate, boundary_pct, dot_pct, balls_per_*, fours_per_innings, sixes_per_innings, boundaries_per_innings, n_players, n_innings, mix, below_support, cliff_buckets, season | `runs_per_innings`, `hundreds_per_innings`, `fifties_per_innings`, `thirties_per_innings`, `ducks_per_innings` |
| `/players/bowling/by-season` | economy, bowling_avg, strike_rate, dot_pct, boundary_pct, balls_per_boundary, wickets_per_over, wickets_per_innings, maidens_per_innings, n_players, n_balls, mix, below_support, cliff_overs, season | `four_wicket_hauls_per_innings` |
| `/players/fielding/by-season` | catches_per_match, stumpings_per_match, run_outs_per_match, dismissals_per_match, n_players, n_matches, is_keeper, below_support, season | **Nothing missing** |

#### Player `/by-phase` endpoints

| Endpoint | Currently has | Missing |
|---|---|---|
| `/batters/{id}/by-phase` | phase, overs, runs, balls, fours, sixes, dots, dismissals, strike_rate, dot_pct, boundary_pct, balls_per_four/six/boundary, average, boundaries | `runs_per_innings_in_phase`, `fours_per_innings`, `sixes_per_innings`, `boundaries_per_innings` per phase (denominator = innings the player batted in this phase) |
| `/bowlers/{id}/by-phase` | phase, overs_range, balls, runs_conceded, wickets, dots, fours, sixes, average, economy, strike_rate, dot_pct, boundary_pct, balls_per_* | `wickets_per_innings_in_phase`, optionally `runs_conceded_per_innings_in_phase` (denominator = innings the player bowled in this phase) |
| `/fielders/{id}/by-phase` | phase, overs, catches, stumpings, run_outs, caught_and_bowled, total | `total_per_match`, `catches_per_match`, `stumpings_per_match`, `run_outs_per_match` per phase (denominator = player's matches in scope, NOT innings — fielding is match-grain) |

#### Cohort `/scope/averages/players/*/by-phase`

All required per-phase rate fields already exist (shipped session 1 of `spec-player-baseline-parity.md`):
- batting: `runs_per_innings_in_phase`, `fours_per_innings`, `sixes_per_innings`, `boundaries_per_innings`
- bowling: `wickets_per_innings_in_phase`
- fielding: `catches_per_match`, `stumpings_per_match`, `run_outs_per_match`, `dismissals_per_match`

**Nothing missing on cohort by-phase side.**

### 2.2 Backend work plan

**Group A — `/summary` envelopes (small):**

| # | Endpoint | Field | Source |
|---|---|---|---|
| A1 | `/batters/{id}/summary` | `runs_per_innings` envelope | derive: `runs.value / innings_total.value` |
| A2 | `/scope/averages/players/batting/summary` | `runs_per_innings` | derive from cohort SQL aggregates already in scope |
| A3 | `/bowlers/{id}/summary` | `four_wicket_hauls_per_innings` envelope | derive: `four_wicket_hauls.value / innings.value` |
| A4 | `/scope/averages/players/bowling/summary` | `four_wicket_hauls_per_innings` | new SQL aggregate over `playerscopestats.four_wicket_hauls` / `n_innings` — verify column exists; if not, schema add (see 2.3) |

**Group B — Player `/by-season` rate fields:**

| # | Endpoint | New per-season fields |
|---|---|---|
| B1 | `/batters/{id}/by-season` | 8 rates: runs/inn, hundreds/inn, fifties/inn, thirties/inn, ducks/inn, fours/inn, sixes/inn, boundaries/inn |
| B2 | `/bowlers/{id}/by-season` | 3 rates: wickets/inn, maidens/inn, four_wicket_hauls/inn |
| B3 | `/fielders/{id}/by-season` | 4 rates: dismissals/match, catches/match, stumpings/match, run_outs/match (all `volume / matches` from columns already in the row) |

**Group C — Cohort `/by-season` mirrors:**

| # | Endpoint | New per-season fields |
|---|---|---|
| C1 | `/players/batting/by-season` | 5 rates: runs/inn, hundreds/inn, fifties/inn, thirties/inn, ducks/inn |
| C2 | `/players/bowling/by-season` | 1 rate: four_wicket_hauls/inn |
| C3 | `/players/fielding/by-season` | none |

**Group D — Player `/by-phase` rate fields:**

| # | Endpoint | New per-phase fields | Denominator |
|---|---|---|---|
| D1 | `/batters/{id}/by-phase` | runs_per_innings_in_phase, fours/inn, sixes/inn, boundaries/inn | innings the player batted ≥1 ball in the phase |
| D2 | `/bowlers/{id}/by-phase` | wickets_per_innings_in_phase, runs_conceded/inn (optional) | innings the player bowled ≥1 ball in the phase |
| D3 | `/fielders/{id}/by-phase` | total/match, catches/match, stumpings/match, run_outs/match | player's matches in scope (already a known scalar) |

**Group E — Metrics metadata:**

| Field | Direction | Notes |
|---|---|---|
| `bat_runs_per_innings` | `higher_better` | |
| `bowl_four_wicket_hauls_per_innings` | `higher_better` | |

Most other per-innings rates already have metric_metadata entries from session 1 (`bat_hundreds_per_innings` etc. are in there). Audit before adding.

### 2.3 Schema audit

The `playerscopestats` table needs verification:

- Does it have a `four_wicket_hauls` column? If not, add via `populate_player_scope_stats.py` and full-rebuild.
- Confirms milestone counts (`thirties`, `fifties`, `hundreds`, `ducks`) already added in session 1's commit `0e7e7eb` — OK.
- Confirms `playerscopestatsover.maidens` column added in same commit — OK.

If `four_wicket_hauls` is missing: schema migration + populate rebuild. Otherwise zero schema work for this spec.

### 2.4 Sanity tests + regression captures

For each new envelope field (Group A) and each new per-rate field (Groups B/C/D):

1. **Sanity test** — assert `value` matches `numerator / denominator` derived independently from `cricket.db` at known scopes (Kohli IPL hundreds_per_innings = 9 / 272; Bumrah IPL four_wicket_hauls_per_innings = 5 / 157, etc.).
2. **Sanity test** — assert envelope's `scope_avg` matches the corresponding field on the cohort endpoint at the same scope (cross-endpoint consistency, same as `test_q6_extension_envelopes.py`).
3. **Regression capture** — for each new endpoint shape, REG→NEW flip in a preceding commit, then capture NEW payloads. ~6 endpoints × 3 scopes = 18 new captures.

Apply CLAUDE.md "REG→NEW flip BEFORE shape change" discipline — the flip commit lands BEFORE the shape change.

### 2.5 Backend sequencing

1. Schema verify (zero or one commit).
2. Group A (4 fields, 1 commit).
3. Group C (cohort by-season mirrors, 1 commit) — must precede Group B so the cohort scope_avg is available when the player endpoint computes deltas.
4. Group B (player by-season, 1 commit).
5. Group D (by-phase, 1 commit per discipline = 3 commits OR 1 combined).
6. Sanity tests + regression flips + captures — lands alongside or immediately after each shape change per cadence rule.

Estimated **5–8 backend commits**.

---

## 3. Frontend display rule (unchanged from §1)

After backend ships, frontend uses the new per-innings envelopes / fields to render the new tiles + charts per §4 and §5 tables.

---

## 4. Per-page audit tables — frontend tiles

Columns:
- **Stat** — label
- **Kind** — Absolute / Per-innings / Per-match / Identity
- **Currently** — what ships today
- **Action** — Keep / Drop chip / Add sibling rate tile / etc.

`+chip` = currently carries baseline chip. `+no chip` = currently no chip. `(NEW)` = doesn't exist as a tile today.

### 4.1 `/players` profile

#### 4.1.1 Batting band

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Runs | Absolute | bold 9183 + chip "vs base 441" | **Drop chip** |
| Avg | Per-dismissal rate | bold + chip | Keep |
| SR | Per-100-balls rate | bold + chip | Keep |
| 100s | Absolute | bold 9 + chip "vs base 0.006 +450%" | **Drop chip** |
| 50s | Absolute | bold 66 + chip "vs base 0.103 +136%" | **Drop chip** |
| HS | Identity | bold | Keep |
| 4s/Inn | Per-innings | bold + chip (Phase F) | Keep |
| 6s/Inn | Per-innings | bold + chip (Phase F) | Keep |
| Bndr/Inn | Per-innings | bold + chip (Phase F) | Keep |
| 30s/Inn | Per-innings | bold + chip (Phase F) | Keep |
| Dot% | Per-balls rate | bold + chip (Phase F) | Keep |
| B/Bndry | Per-innings | bold + chip (Phase F) | Keep |
| **100s/Inn** | Per-innings | (NEW tile, envelope shipped) | **Add tile** — sibling to 100s |
| **50s/Inn** | Per-innings | (NEW tile, envelope shipped) | **Add tile** — sibling to 50s |
| **Ducks/Inn** | Per-innings | (NEW tile, envelope shipped) | **Add tile** + add sibling **Ducks** volume tile |
| **Runs/Inn** | Per-innings | (NEW tile, NEW envelope — backend Group A) | **Add tile** — sibling to Runs |

Result: 12 → ~16 tiles. Three-row cols-6 layout.

#### 4.1.2 Bowling band

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Wickets | Absolute | bold (no chip) | Keep |
| Avg | Per-wicket rate | bold + chip | Keep |
| Econ | Per-over rate | bold + chip | Keep |
| SR | Per-wicket-in-balls rate | bold + chip | Keep |
| Wkts/Inn | Per-innings | bold + chip (Phase F) | Keep |
| Maidens/Inn | Per-innings | bold + chip (Phase F) | Keep |
| **Maiden Overs** | Absolute | (NEW tile, volume already on /summary) | **Add tile** — sibling to Maidens/Inn |
| **4-fers** | Absolute | (NEW tile, volume already on /summary as `four_wicket_hauls`) | **Add tile** |
| **4-fers/Inn** | Per-innings | (NEW tile, NEW envelope — backend Group A) | **Add tile** — sibling to 4-fers |

Result: 6 → 9 tiles. Second row needed.

#### 4.1.3 Fielding band

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Catches | Absolute | bold 125 + chip "vs base 0.316 +41.8%" | **Drop chip** |
| Stumpings | Absolute | bold (chip gated when 0) | Keep, drop chip when reactivated |
| Run-outs | Absolute | bold 20 + chip "vs base 0.043 +67%" | **Drop chip** |
| Total | Absolute | bold | Keep |
| Dis/Match | Per-match | bold + chip | Keep |
| **Catches/Match** | Per-match | (NEW tile, envelope shipped Phase E) | **Add tile** — sibling to Catches |
| **Run-outs/Match** | Per-match | (NEW tile, envelope shipped Phase E) | **Add tile** — sibling to Run-outs |
| **Stumpings/Match** | Per-match | (NEW tile, gate on value>0) | **Add tile** — sibling to Stumpings (keepers only) |

Result: 5 → 8 tiles. Cols-6 row pairing volume + rate side-by-side.

#### 4.1.4 Keeping band (conditional, when innings_kept > 0)

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Innings kept | Absolute | bold | Keep |
| Stumpings | Absolute | bold | Keep |
| Catches | Absolute | bold | Keep |
| Byes | Absolute | bold | Keep |
| Byes/Inn | Per-keeping-inning | bold (static "(keeping cohort)" hint, no chip) | Convert to full chip when cohort scope_avg available (keeping cohort spec) |
| **Stumpings/KeptInn** | Per-keeping-inning | (NEW) | **Add tile** (depends on keeping cohort spec) |
| **Catches/KeptInn** | Per-keeping-inning | (NEW) | **Add tile** (depends on keeping cohort spec) |
| **Dis/KeptInn** | Per-keeping-inning | (NEW) | **Add tile** (depends on keeping cohort spec) |

Keeping cohort baseline is currently null — keeping per-innings-kept chips depend on the keeping cohort being built (separate spec).

### 4.2 `/batting?player=X`

#### 4.2.1 Header — Stat row 1

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Matches | Absolute | bold (no chip) | Keep |
| Innings | Absolute | bold (no chip) | Keep |
| Runs | Absolute | bold (no chip — correctly suppressed) | Keep |
| Average | Per-dismissal | bold + chip | Keep |
| Strike Rate | Per-100-balls | bold + chip | Keep |
| **Runs/Inn** | Per-innings | (NEW, backend Group A) | **Add tile** — sibling to Runs |

#### 4.2.2 Header — Stat row 2

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Boundaries | Absolute | bold (subtitle: 4s/6s breakdown) | Keep |
| B/Four | Per-fours-in-balls | bold + chip | Keep |
| B/Boundary | Per-boundary-in-balls | bold + chip | Keep |
| Dot % | Per-balls rate | bold + chip | Keep |
| 30s / 50s / 100s | Absolute (combined) | bold "58 / 66 / 9" (no chip) | Keep |
| **Bndr/Inn** | Per-innings | (NEW tile, envelope shipped) | **Add tile** — sibling to Boundaries |
| **30s/Inn · 50s/Inn · 100s/Inn** | Per-innings (combined) | (NEW tile, envelopes shipped) | **Add tile** — sibling to combined milestone tile |

#### 4.2.3 By Season tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Runs by Season chart | Absolute per season | bars/line + cohort `total_runs` overlay (Phase C) | **Drop overlay** — chart is volume-per-season |
| Strike Rate by Season chart | Per-100-balls rate | line + cohort SR overlay (Phase C) | Keep overlay |
| **Runs/Inn by Season** | Per-innings | (NEW chart, backend Group B+C) | **Add chart** + cohort `runs_per_innings` overlay |
| **100s/Inn by Season** | Per-innings | (NEW chart, backend Group B+C) | Optional add |
| **50s/Inn by Season** | Per-innings | (NEW chart, backend Group B+C) | Optional add |

#### 4.2.4 By Over tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Strike Rate by Over | Per-balls rate | bars, no overlay | **Add cohort SR-per-over overlay** (originally deferred in spec-player-baseline-parity.md §4.2) |

#### 4.2.5 By Phase tab

Per-phase block tiles:

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Runs (in phase) | Absolute | bold (no chip) | Keep |
| Balls (in phase) | Absolute | bold (no chip) | Keep |
| SR | Per-balls rate | bold + chip (Phase C) | Keep |
| Dots | Per-balls rate | bold + chip (Phase C) | Keep |
| 4s (in phase) | Absolute | bold | Keep |
| 6s (in phase) | Absolute | bold | Keep |
| B/4 | Per-balls rate | bold + chip (Phase C) | Keep |
| **Runs/Inn (in phase)** | Per-innings | (NEW tile, backend Group D1) | **Add tile** — sibling to Runs-in-phase |
| **4s/Inn (in phase)** | Per-innings | (NEW tile, backend Group D1) | Optional add |
| **6s/Inn (in phase)** | Per-innings | (NEW tile, backend Group D1) | Optional add |

#### 4.2.6 vs Bowlers / Dismissals / Inter-Wicket / Innings List / Records

All matchup / proportional / identity surfaces — no chips by design. No action.

### 4.3 `/bowling?player=X`

#### 4.3.1 Header — Stat row 1

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Matches | Absolute | bold | Keep |
| Innings | Absolute | bold | Keep |
| Wickets | Absolute | bold | Keep |
| Average | Per-wicket rate | bold + chip | Keep |
| Economy | Per-over rate | bold + chip | Keep |
| **Wkts/Inn** | Per-innings | (NEW on this page, envelope shipped Phase F) | **Add tile** — sibling to Wickets |

#### 4.3.2 Header — Stat row 2

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Overs | Absolute (formatted) | bold | Keep |
| Strike Rate | Per-balls rate | bold + chip | Keep |
| Best Figures | Identity | bold | Keep |
| Dot % | Per-balls rate | bold + chip | Keep |
| B/Boundary | Per-balls rate | bold + chip | Keep |
| **Maiden Overs** | Absolute | (NEW on this page) | **Add tile** |
| **Maidens/Inn** | Per-innings | (NEW on this page, envelope shipped) | **Add tile** — sibling to Maiden Overs |
| **4-fers** | Absolute | (NEW on this page) | **Add tile** |
| **4-fers/Inn** | Per-innings | (NEW, backend Group A) | **Add tile** — sibling to 4-fers |

#### 4.3.3 By Season tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Wickets by Season chart | Absolute per season | line + cohort overlay rescaled to volume (Phase D) | **Drop overlay** — chart is volume |
| Strike Rate by Season chart | Per-balls rate | line + cohort overlay (Phase D) | Keep overlay |
| **Wkts/Inn by Season** | Per-innings | (NEW chart, backend Group B+C) | **Add chart** with cohort `wickets_per_innings` overlay |
| **Economy by Season** | Per-over rate | (NEW chart, cohort already has `economy` per season) | **Add chart** with cohort `economy` overlay |
| **Maidens/Inn by Season** | Per-innings | (NEW chart) | Optional add |

#### 4.3.4 By Over tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Economy by Over | Per-over rate | bars, no overlay | **Add cohort econ-per-over overlay** (originally deferred in spec-player-baseline-parity.md §4.3) |

#### 4.3.5 By Phase tab

Per-phase block tiles:

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Balls / Runs / Wickets | Absolute | bold (no chip) | Keep |
| Economy | Per-over rate | bold + chip (Phase D) | Keep |
| SR | Per-balls rate | bold + chip (Phase D) | Keep |
| Dots | Per-balls rate | bold + chip (Phase D) | Keep |
| **Wkts/Inn (in phase)** | Per-innings | (NEW tile, backend Group D2) | **Add tile** — sibling to Wickets-in-phase |
| **Runs conceded/Inn (in phase)** | Per-innings | (NEW tile, backend Group D2) | Optional add |

#### 4.3.6 vs Batters / Wickets / Innings List / Records

No chips by design. No action.

### 4.4 `/fielding?player=X`

#### 4.4.1 Header — Stat row

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Catches | Absolute | bold 125 + chip "vs base 0.316" (Phase E) | **Drop chip** |
| Stumpings | Absolute | bold (chip gated when 0) | Keep, drop chip when reactivated |
| Run Outs | Absolute | bold 20 + chip "vs base 0.043" (Phase E) | **Drop chip** |
| Total | Absolute | bold | Keep |
| Matches | Absolute | bold | Keep |
| Dis/Match | Per-match | bold + chip | Keep |
| **Catches/Match** | Per-match | (NEW, envelope shipped Phase E) | **Add tile** — sibling to Catches |
| **Run-outs/Match** | Per-match | (NEW, envelope shipped Phase E) | **Add tile** — sibling to Run-outs |
| **Stumpings/Match** | Per-match | (NEW, gate on value>0) | **Add tile** — sibling to Stumpings (keepers only) |

#### 4.4.2 By Season tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Dismissals by Season chart | Absolute per season | line + cohort overlay rescaled to volume (Phase E) | **Drop overlay** — chart is volume |
| **Dis/Match by Season** | Per-match | (NEW chart, backend Group B+C) | **Add chart** with cohort `dismissals_per_match` overlay |
| **Catches/Match by Season** | Per-match | (NEW chart) | Optional add |

#### 4.4.3 By Over tab

| Element | Kind | Currently | Action |
|---|---|---|---|
| Dismissals by Over | Absolute per over | bars | Keep (no overlay; volume) |

#### 4.4.4 By Phase tab

Per-phase block tiles:

| Stat | Kind | Currently | Action |
|---|---|---|---|
| Catches / Stumpings / Run Outs / C&B | Absolute | bold (no chip) | Keep |
| Total | Absolute | bold + chip "vs base 0.081" (Phase E) | **Drop chip** |
| **Total/Match (in phase)** | Per-match | (NEW tile, backend Group D3) | **Add tile** — sibling to Total-in-phase |
| **Catches/Match (in phase)** | Per-match | (NEW tile, backend Group D3) | Optional add |
| **Run-outs/Match (in phase)** | Per-match | (NEW tile, backend Group D3) | Optional add |

#### 4.4.5 Dismissal Types / Victims / Innings List / Records / Keeping

Proportional / identity / volume — no chips by design. No action.

---

## 5. Plot summary

| Chart | Kind | Today | Action |
|---|---|---|---|
| /batting Runs by Season | Absolute | bars + cohort overlay | **Drop overlay** |
| /batting SR by Season | Rate | line + overlay | Keep |
| /batting **Runs/Inn by Season** | Rate | (NEW) | Add chart with overlay |
| /batting SR by Over | Rate | bars, no overlay | Add overlay |
| /bowling Wickets by Season | Absolute | line + rescaled overlay | **Drop overlay** |
| /bowling SR by Season | Rate | line + overlay | Keep |
| /bowling **Wkts/Inn by Season** | Rate | (NEW) | Add chart with overlay |
| /bowling **Econ by Season** | Rate | (NEW) | Add chart with overlay |
| /bowling Econ by Over | Rate | bars, no overlay | Add overlay |
| /fielding Dismissals by Season | Absolute | line + rescaled overlay | **Drop overlay** |
| /fielding **Dis/Match by Season** | Rate | (NEW) | Add chart with overlay |
| /fielding Dismissals by Over | Absolute | bars, no overlay | Keep |

---

## 6. Full implementation sequencing

### Backend (5–8 commits)

1. **B0 Schema verify** — confirm `playerscopestats.four_wicket_hauls` exists. If not, add via populate (one commit).
2. **B1 Group A** — `runs_per_innings` + `four_wicket_hauls_per_innings` envelopes on /summary endpoints (player + cohort sides). One commit.
3. **B2 Group C** — cohort `/by-season` mirrors (5 batting + 1 bowling fields). One commit. **Lands before B3** so player-side has cohort scope_avg to compare against.
4. **B3 Group B** — player `/by-season` rate fields (8 batting + 3 bowling + 4 fielding). One commit per discipline or one combined.
5. **B4 Group D** — player `/by-phase` rate fields (3 disciplines). One commit per discipline or one combined.
6. **B5 Sanity tests + REG→NEW flips + regression captures** — per CLAUDE.md discipline. Flip lands as preceding commit before each shape change; NEW capture lands in the shape-change commit.

### Frontend (4–7 commits, after backend or in parallel with display-rule fixes)

7. **F1 /players Batting band** — drop chips on Runs/100s/50s; add Runs/Inn, 100s/Inn, 50s/Inn, Ducks/Inn tiles (three-row cols-6 layout).
8. **F2 /players Fielding band** — drop chips on Catches/Run-outs; add Catches/Match, Run-outs/Match, Stumpings/Match tiles (cols-6 pairing layout).
9. **F3 /players Bowling band** — add Maiden Overs, 4-fers, 4-fers/Inn tiles (second row).
10. **F4 /fielding stat row** — same as F2.
11. **F5 /fielding By Phase Total tile** — drop chip; add Total/Match per phase.
12. **F6 /bowling deep-dive** — add Wkts/Inn, Maiden Overs, Maidens/Inn, 4-fers, 4-fers/Inn tiles.
13. **F7 /batting deep-dive** — add Runs/Inn, Bndr/Inn, 30s/Inn|50s/Inn|100s/Inn tiles.

### Chart additions (after F1–F7, 4–6 commits)

14. **C1 Drop overlays** on Runs-by-Season, Wickets-by-Season, Dismissals-by-Season charts (one commit per page).
15. **C2 Add new rate-by-season charts**: Runs/Inn (batting), Wkts/Inn + Econ (bowling), Dis/Match (fielding).
16. **C3 Add by-over overlays**: SR/Over (batting), Econ/Over (bowling) — closes the spec-player-baseline-parity.md §4.2/§4.3 deferred items.

### Tests evolve in lockstep

Each tile move and chart change shifts the expecteds in:
- `tests/integration/player_band_q6_chips.sh`
- `tests/integration/player_baseline_chart_overlays.sh`
- `tests/integration/player_baseline_by_phase_chips.sh`
- `tests/integration/player_baseline_filter_matrix.sh`
- `tests/sanity/test_q6_extension_envelopes.py` (for new envelopes)

Same red-then-green discipline as `spec-player-baseline-parity.md` Phases C–H.

### Estimated total: 13–21 commits across one or two sessions.

---

## 7. Out of scope (this audit)

- `/head-to-head`, `/matches`, `/teams`, `/series` — separate audits if needed.
- Distribution panels (sparklines + form deltas) — already correctly uses scope-mean + gender-global dual-reference framework.
- Compare grid (`/players?player=A&compare=B`) — compact-mode chips already only on rate metrics.
- Keeping band per-innings-kept rates — keeping cohort doesn't exist yet (separate spec).
