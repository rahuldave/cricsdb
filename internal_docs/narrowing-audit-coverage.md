# Narrowing audit — coverage matrix (feature × API × test)

**What this is.** Every cohort/comparison surface in the app, organised by
page → tab/subtab → feature (headline **tile**, **graph**, or **sparkline**),
with: the API field that feeds it, whether it **narrows** under the six
filters, and which integration test locks that behaviour. Built 2026-05-29
from a DOM-level audit (`agent-browser`, surface by surface) — job 2 of the
post-3e plan.

**The six** = venue / opponent / team / inning / toss / result.

**The rule.** Every headline number, graph, and **sparkline** must narrow
under the six — EXCEPT:
- the per-position / per-over **mix histogram** (the weighting) — stays
  COARSE by design (Tier 2, `spec-tier3-cohort-narrowing.md` §1/D-B1);
- the **gender-global grey** static sparkline line — scope-independent by
  design.

**Audit verdict (2026-05-29): PASS.** Every tile, graph and sparkline that
should narrow was confirmed moving at the rendered-DOM level; the mix
histograms correctly stay coarse. **No frozen surface found** — the prime
watch-item (the green sparkline cohort line) narrows on all of batting /
bowling / fielding / teams. See `narrowing-audit-findings.md` (empty of bugs).

Anchor players: Kohli `ba607b88`, Bumrah `462411b3`, Dhoni `4a8a2e3b`,
Pant `919a3be2`. Stable scope used: `gender=male&team_type=club&tournament=IPL`.

Legend — **Narrows?**: ✅ narrows (Tier 1) · 🟰 coarse-by-design (exception) ·
❄️ frozen (→ findings). **Test asserts narrowing?**: ✓ yes · ~ presence/structure
only · ✗ none (gap).

---

## Pages with NO cohort surface (nothing to narrow)

`/series` (Tournaments — dossier, leaderboards, by-tier cards),
`/venues`, `/head-to-head` (StatCards + bar/donut, no cohort overlay),
`/matches` + `/matches/:id`. These carry charts/tables but **no comparison
baseline** that responds to the six. Confirmed by grep: none of their
component subtrees use `MetricDelta` / `ProbChip` / `DistributionSparkline` /
`PerformanceVsCohort` / `referenceData`. (Their own non-cohort behaviour is
tested by `series*.sh`, `venues.sh`, `head_to_head.sh`, `matches.sh`.)

---

## /batting  (anchor: Kohli)

Tabs: By Season · By Position · By Over · By Phase · vs Bowlers · Dismissals ·
Inter-Wicket · Innings List · Records.

### Summary row + Distribution panel (above the tabs)
| Feature | Kind | API field | Narrows? | DOM-verified this session | Test | Asserts narrowing? |
|---|---|---|---|---|---|---|
| Runs/Inn, Average, Strike Rate, Bndr/Inn, B/Four, B/Boundary, Dot%, milestones/Inn — "VS COHORT" chips | tile | `/batters/{id}/summary` `*.scope_avg` | ✅ | 26.70→27.62 etc. under inning; moves under all 5 axes | `player_baseline_aux_fallback.sh` §1–4 | ✓ |
| Distribution milestone ProbChips P(≤10)/P(≥30)/P(≥50)/P(≥100)/conditionals | tile | `/batters/{id}/distribution` cohort | ✅ | chip deltas move | `prob_chip_baselines.sh` | ✓ |
| **Distribution sparkline — green "cohort at scope" line** | sparkline | `/batters/{id}/summary` `runs_per_innings.scope_avg` (or SR tab) | ✅ | **y1 24.44→24.18, legend 26.7→27.6 runs/inn under inning; moves on all 5 axes** | `sparkline_league_reference.sh` (presence) + **`sparkline_narrowing.sh` (NEW)** | ~ → ✓ |
| Distribution sparkline — grey gender-global line | sparkline | `globalBaselines` (static) | 🟰 | (intentionally static) | `batter_distribution.sh` | ~ |

### By Season
| Runs/Inn + Strike Rate cohort overlay (green ref line) | graph (LineChart) | `/scope/averages/players/batting/by-season` | ✅ | — | `player_baseline_chart_overlays.sh`, `player_baseline_filter_matrix.sh` | ✓ |

### By Position
| Per-position SR/Avg **cohort bars** (own + green cohort tick) | graph (PerformanceVsCohort) | `/batters/{id}/summary` `position_distribution[].cohort_*` → re-pointed to live `by_position[]` | ✅ | Open: own 141.63→138.84, cohort 136.05→136.20 under inning | `position_distribution_chart.sh` | ✓ |
| Position **mix histogram** (innings-share weighting) | graph (MixHistogram) | `position_distribution[].cohort_innings_share` | 🟰 | "Open 52.0%" identical under inning ✓ | `position_distribution_chart.sh` | ✓ (asserts unchanged) |

### By Over
| Per-over SR / Dot% / Boundaries cohort overlay | graph (BarChart) | `/scope/averages/players/batting/by-over` | ✅ | — | `batting_by_over_charts.sh` | ✓ |

### By Phase
| Per-phase SR/Dots/Balls-per-4 chips (BaselineChip) + comparative panels | tile+graph | `/scope/averages/players/batting/by-phase` | ✅ | — | `player_baseline_by_phase_chips.sh`, `batting_by_phase_comparative.sh` | ✓ |

### Inter-Wicket
| SR-by-wickets-down cohort line | graph (LineChart) | `/batters/{id}/inter-wicket` `cohort_strike_rate` | ✅ | — | `batting_inter_wicket_cohort.sh` | ✓ |

### Dismissals
| Dismissal cohort comparative charts | graph (PerformanceVsCohort) | `/scope/averages/batting/dismissals` | ✅ | — | `dismissal_cohort.sh` | ✓ |

### vs Bowlers · Innings List · Records
No cohort baseline (scatter / data tables / record lists). Tests:
`batting_vs_bowlers_search.sh`, `players.sh`, `player_records.sh`.

---

## /bowling  (anchor: Bumrah)

Tabs: By Season · By Over · By Phase · vs Batters · Wickets · Victims ·
Innings List · Records.

### Summary row + Distribution panel
| Wkts/Inn, Average, Economy, Strike Rate, Dot%, B/Boundary, Maidens/Inn, 4-fers/Inn chips | tile | `/bowlers/{id}/summary` `*.scope_avg` | ✅ | 1.03→1.00, econ 8.97→8.89 etc. under inning | `player_baseline_aux_fallback.sh` | ✓ |
| Distribution wicket-ladder ProbChips | tile | `/bowlers/{id}/distribution` cohort | ✅ | — | `prob_chip_baselines.sh` | ✓ |
| **Distribution sparkline — green cohort line** | sparkline | `/bowlers/{id}/summary` `wickets_per_innings.scope_avg` (or econ tab) | ✅ | **y1 25.42→23.98, legend 1.03→1.00 wkts/inn under inning** | `sparkline_league_reference.sh` + **`sparkline_narrowing.sh` (NEW)** | ~ → ✓ |

### By Season / By Phase
| Wkts/Inn · SR · Economy cohort overlays + phase chips | graph | `/scope/averages/players/bowling/by-season` + `/by-phase` | ✅ | — | `player_baseline_chart_overlays.sh`, `player_baseline_by_phase_chips.sh`, `bowling_by_phase_comparative.sh` | ✓ |

### By Over
| Per-over Economy / Wkts / Boundaries **cohort bars** | graph (PerformanceVsCohort) | `/bowlers/{id}/summary` `over_distribution[].cohort_*` → live `by_over[]` | ✅ | — | `over_distribution_chart.sh`, `bowling_by_over_boundaries.sh` | ✓ |
| Over **mix histogram** (balls-based weighting) | graph (MixHistogram) | `over_distribution[].mix_legal_balls` | 🟰 | coarse by design (D-B2) | `over_distribution_chart.sh` | ✓ (asserts unchanged) |

### vs Batters · Wickets · Victims · Innings List · Records
No cohort baseline. Tests: `bowling_vs_batters_search.sh`, `bowling_victims.sh`, `bowling.sh`.

---

## /fielding  (anchor: Dhoni)

Tabs: By Season · By Dismissed Position · By Over · By Phase · Dismissal
Types · Victims · Innings List · Records (+ Keeping when `innings_kept>0`).

### Summary row + Distribution panel
| Catches/Match, Run-outs/Match, Stumpings/Match, Dis/Match chips | tile | `/fielders/{id}/summary` `*.scope_avg` (denominator = `matches_fielded`) | ✅ | 0.584→0.494 etc. under inning | `player_baseline_aux_fallback.sh` §10–12 | ✓ |
| Distribution catch ProbChips P(0)/P(1)/P(≥2) | tile | `/fielders/{id}/distribution` cohort | ✅ | — | `fielder_probchip_alignment.sh`, `fielder_p_one_direction.sh` | ✓ |
| **Distribution sparkline — green cohort line** | sparkline | `/fielders/{id}/summary` `catches_per_match.scope_avg` | ✅ | **y1 27.33→26.73, legend 0.58→0.49 catches/match under inning** | `sparkline_league_reference.sh` + **`sparkline_narrowing.sh` (NEW)** | ~ → ✓ |

### By Season / By Phase
| Dismissals/match cohort overlay + phase chips | graph | `/scope/averages/players/fielding/by-season` + `/by-phase` | ✅ | — | `fielding_by_phase_charts.sh` | ✓ |

### By Dismissed Position
| Per-dismissed-position **cohort bars** (keeper-binary, no mix → whole tab narrows) | graph (PerformanceVsCohort + MixHistogram) | `/fielders/{id}/summary` `dismissal_position_distribution[].cohort_*` → live `by_dismissed_position[]` | ✅ | — | `dismissed_position_chart.sh` | ✓ |

### By Over
| Per-over dismissals-per-match cohort line | graph | `/fielders/{id}/by-over` `cohort_dismissals_per_match` | ✅ | — | `fielding_by_over_charts.sh` | ✓ |

### Dismissal Types · Victims · Innings List · Records · Keeping
No cohort baseline. Tests: `fielding.sh`.

---

## /teams  (anchor: Mumbai Indians / India)

Tabs: By Season · vs Opponent · Compare · Batting · Bowling · Fielding ·
Partnerships · Players · Records · Match List. (All Teams cohorts are Tier 1 —
no mix weighting.)

### Summary row + Splits Mosaic
| Win % "VS AVG" chip | tile | `/teams/{team}/summary` | ✅ | 49.0→44.4 under inning | `teams.sh`, `team_by_inning.sh` | ✓ |
| Splits Mosaic (toss×inning W/T/L) | filter-widget | `/teams/splits` | ✅ | — | `team_splits_mosaic.sh`, `team_aux_order_invariance.sh` | ✓ |

### Batting / Bowling / Fielding tabs
| Summary tiles + ProbChips | tile | `/teams/{team}/{disc}/summary` + `/distribution` | ✅ | batting Win-panel verified | `team_batting_distribution.sh`, `team_bowling_distribution.sh`, `team_fielding_distribution.sh`, `prob_chip_baselines_teams.sh`, `teams_*_tile_std.sh` | ✓/~ |
| **Distribution sparkline — green cohort line** | sparkline | `/teams/{team}/{disc}/distribution` league ref | ✅ | **team batting y1 11.05→9.82 under inning** | (team distribution suites) + **`sparkline_narrowing.sh` (NEW, team rows)** | ~ → ✓ |
| Per-over / per-phase cohort bars + overlays | graph | `/teams/{team}/{disc}/by-{season,phase}` | ✅ | — | `team_phase_barcharts.sh`, `team_class_per_tab_narrowing.sh`, `series_type_per_tab_narrowing.sh` | ✓ |

### vs Opponent · Compare · Partnerships · Players · Records · Match List
Compare = `team-compare-average.sh`, `compare_*.sh`. Partnerships cohort:
`series_partnerships_top_by_wicket.sh`. Others = data tables / records.

---

## /players  (profile — no tabs; anchor: Kohli)

| Per-discipline summary tiles (batting + bowling + fielding "VS COHORT" chips, via `PlayerSummaryRow`) | tile | `/players/{id}/profile` (per-discipline `scope_avg`) | ✅ | all three disciplines' tiles move under inning (batting Runs/Inn 26.70→27.62, fielding Catches/Match 0.316→0.298) | `players.sh`, `player_result_filter.sh`, `player_toss_value.sh`, `player_vs_team.sh`, `inning_unify_players.sh` | ✓ |
| Compare slots (`PlayerCompareGrid`) | tile | same, per slot | ✅ | — | `player_compare_baseline.sh` | ✓ |

---

## Gaps found → action (closed 2026-05-29)

1. **Sparkline cohort-line narrowing** — no test asserted the green line
   MOVES under the six (`sparkline_league_reference.sh` only checks
   presence + value at a fixed scope). **Closed:** added
   `tests/integration/sparkline_narrowing.sh` — asserts the green line's y1
   moves + legend tracks the API scope_avg under inning, for batting /
   bowling / fielding (legend-anchored) and the three team panels
   (y1-move). 15/15 pass.

2. **Stale denominator-B assertion** — `dismissed_position_chart.sh` A7
   computed the opener player catches/match as `catches / matches.value`
   (squad), but the UI divides by `matches_fielded` (denominator-B, 3e).
   They diverged once the 2026-05-29 re-ingest left Kohli fielding 279 of 280
   IPL matches (37/280=0.132 vs 37/279=0.133 on screen). Red→green: fixed A7
   to divide by `matches_fielded`. The surface itself narrows fine (the
   narrowing assertions C12 etc. were green throughout); only the test's
   denominator was stale.

## Suite confirmation (2026-05-29, all green)

Ran the per-tab narrowing suites as authoritative DOM confirmation — all
PASS: `player_baseline_chart_overlays` (34), `player_baseline_by_phase_chips`
(38), `position_distribution_chart` (14), `over_distribution_chart` (11),
`dismissed_position_chart` (16, after fix), `batting_by_over_charts` (5),
`fielding_by_over_charts`, `fielding_by_phase_charts` (6),
`batting_inter_wicket_cohort` (3), `dismissal_cohort` (11),
`prob_chip_baselines` (13), `prob_chip_baselines_teams` (17),
`team_class_per_tab_narrowing`, `sparkline_league_reference` (9),
`sparkline_narrowing` (15, NEW). Plus the Players-profile + team-distribution
suites cited above, run-and-green: `player_result_filter` (17),
`player_toss_value` (6, asserts narrowing under toss), `inning_unify_players`
(19), `team_batting_distribution` (55), `team_bowling_distribution` (52),
`team_fielding_distribution` (42). Every surface in the matrix now has a
run-and-green test, not just a cited one (none drifted under the re-ingest —
all self-anchor against the live DB).

No other gaps: every narrowing surface now has a dedicated test that asserts
movement under the six (or under team_class/series_type for teams).
