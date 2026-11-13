# Tier-3 narrowing — audit + integration-test URL checklist

**Purpose.** Durable list of diverse share-links that exercise the
"narrow under the six" behaviour shipped by 3b–3e + Tier-3 Phase B
(`spec-player-baseline-aux-fallback.md`, `spec-tier3-cohort-narrowing.md`).
Two uses:

1. **Exhaustive re-audit** (next session, mirrors the post-3d audit): walk
   every one, toggle the filter control on-page, confirm narrowing. Treat
   any surface that does NOT move as a remaining Tier-3 work item. Enumerate
   the FULL tab list per page (Route paths × each page's `tabs[]`), not a
   sample — `feedback_exhaustive_audit_lists`.
2. **Integration-test targets** — each row's assertion should become a
   checked-in `tests/integration/*.sh` DOM/SQL-anchored assertion (the
   existing `player_baseline_aux_fallback.sh` §1–§17 already covers many;
   extend to cover the rest, especially the sparkline row below).

**The six** = venue / opponent / team / innings / toss / result.
Host: `http://localhost:5173`. The check for every row: toggle the named
filter (or delete its param) and watch **both** the player's own value AND
the grey/green cohort move together — EXCEPT the mix histograms, which stay
coarse by design (the weighting; `spec-tier3-cohort-narrowing.md` D-B1).

Anchor players: Kohli `ba607b88`, Bumrah `462411b3`, Dhoni `4a8a2e3b`,
Pant `919a3be2`.

## Phase-B per-bucket "By X" tabs (own bars + cohort bars narrow; mix coarse)

| # | URL (after host) | Exercises | Assert |
|---|---|---|---|
| 1 | `/batting?player=ba607b88&gender=male&team_type=international&tab=By+Position&inning=0` | batting By Position, innings | SR/Avg bars + green cohort ticks move; "Position mix" histogram unchanged |
| 2 | `/bowling?player=462411b3&gender=male&team_type=club&tournament=Indian+Premier+League&tab=By+Over&result=lost` | bowling By Over, result | economy/wkts/boundary bars + cohort ticks move; "Over mix" histogram unchanged |
| 3 | `/fielding?player=4a8a2e3b&gender=male&team_type=club&tournament=Indian+Premier+League&tab=By+Dismissed+Position&filter_opponent=Mumbai+Indians` | fielding By Dismissed Position, opponent | whole tab moves incl. dismissals histogram (fielding has no weight) |
| 4 | `/batting?player=ba607b88&tab=By+Over&filter_venue=Wankhede+Stadium` | batting By Over chart, venue | green SR/dot%/boundaries reference line + own bars move |
| 5 | `/fielding?player=4a8a2e3b&gender=male&team_type=international&tab=By+Over&inning=1` | fielding By Over, innings | green dismissals-per-match line + own bars move |

## Headline / summary / distribution chips (3b/3d/3e) + filter-combo matrix

| # | URL (after host) | Exercises | Assert |
|---|---|---|---|
| 6 | `/bowling?player=462411b3&gender=male&team_type=club&tournament=Indian+Premier+League&toss_outcome=won` | bowling headline, toss | grey "vs cohort" economy chip moves |
| 7 | `/fielding?player=4a8a2e3b&gender=male&team_type=international&inning=0` | fielding distribution chips, innings | "vs cohort" P(0)/P(1)/P(≥2) catch chips move (player % AND cohort %) |
| 8 | `/batting?player=ba607b88&gender=male&team_type=club&tournament=Indian+Premier+League&season_from=2018&season_to=2018&filter_opponent=Chennai+Super+Kings&tab=By+Season` | chained season + opponent | narrows on both axes together |
| 9 | `/fielding?player=ba607b88&gender=male&team_type=international&team_class=full_member` | team-class consistency fix | cohort respects full-member (used to ignore team-class on fielding) |

## AUDIT WATCH-ITEM — likely still frozen (Tier-3 remaining)

| # | URL (after host) | Exercises | Assert |
|---|---|---|---|
| 10 | `/batting?player=ba607b88&gender=male&team_type=international&inning=0` | Distribution-panel **sparkline cohort line** | toggle innings — does the GREEN cohort line on the sparkline move? If NOT, it's the remaining Tier-3 sparkline surface for the re-audit. (NOT touched by 3b–3e/Phase B.) |

Repeat #10 for /bowling and /fielding distribution sparklines. The
gender-global GREY static reference line is intentionally scope-independent
(leave it).

## Coverage notes for the re-audit

- Every row above is one (page, tab, filter) cell. The exhaustive audit must
  also cover the filter axes NOT shown per page (e.g. By Position under
  venue/opponent/team/toss/result, not just innings) and the OTHER players'
  pages — enumerate, don't sample.
- Already Tier-1 (leave): batting Inter-Wicket, batting Dismissals, all
  by-season/by-phase, all Teams surfaces.
- Bin every surface Tier 1/2/3 again; anything still Tier-3 → new work item.
