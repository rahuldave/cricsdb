# Proto-spec: Wicketkeeper Identification (Fielding Tier 2)

Status: research complete, not yet ready for implementation.
Depends on: Tier 1 (`fielding_credit` table) being built first.

## Problem

Cricsheet has **no keeper designation** anywhere — not in match JSON,
not in `people.csv`, not in delivery data. We want to show
keeper-specific stats (stumpings, catches-as-keeper, byes conceded)
but first must identify **who was keeping in each innings**.

## What we know

### Three identification layers

| Layer | Method | Innings covered | Cumulative |
|---|---|---:|---:|
| 1 | **Stumping in this innings** — definitive | 4,713 | 4,713 (18.1%) |
| 2 | **Exactly 1 keeper-capable in fielding XI** — inferred | 10,621 | 15,334 (58.9%) |
| 3 | **Ambiguous** — 0 or 2+ keeper-capable | 10,704 | 26,038 (100%) |

### The threshold tension

"Keeper-capable" = a player with ≥ N career stumpings. The choice
of N creates a three-way tension:

| Threshold (N) | Keeper-capable players | 0 in XI (unresolvable) | 1 in XI (inferred) | 2+ in XI (ambiguous) | Total covered |
|---:|---:|---:|---:|---:|---:|
| ≥ 1 | 825 | 1,443 (6.8%) | 10,025 (47.0%) | 9,857 (46.2%) | 14,738 (56.6%) |
| ≥ 2 | 584 | 2,556 (12.0%) | 13,205 (61.9%) | 7,721 (36.2%) | 15,761 (60.5%) |
| **≥ 3** | **443** | **3,688 (17.3%)** | **12,271 (57.5%)** | **6,391 (30.0%)** | **15,959 (61.3%)** |
| ≥ 5 | 295 | 5,481 (25.7%) | 10,621 (49.8%) | 5,223 (24.5%) | 15,334 (58.9%) |
| ≥ 10 | 154 | 8,568 (40.2%) | 11,596 (54.4%) | 2,937 (13.8%) | 14,533 (55.8%) |

**Sweet spot: N = 3** maximizes total coverage at 61.3%. Explanation:

- **Lowering N** (e.g., ≥1): adds marginal keepers like DA Miller
  (1 anomalous stumping in 485 matches) who are NOT keepers. This
  floods the 2+ bucket (46.2% ambiguous!) because every team has
  several players with 1-2 stumpings. The coverage paradoxically
  drops because the false keeper-capables create more ambiguity
  than the true keeper-capables resolve.

- **Raising N** (e.g., ≥10): eliminates legitimate keepers from
  smaller teams (associate nations, domestic sides) whose keepers
  have 5-9 career stumpings in T20 data. The 0-keeper bucket
  balloons (40.2%) because their keepers fall below the threshold.

- **N = 3**: filters out 1-stumping noise (DA Miller, accidental
  keepers) while keeping genuine keepers from smaller programs.
  The 0-keeper bucket (17.3%) is mostly associate teams with
  genuinely sparse data; the 2+ bucket (30%) is the real problem
  cases (India with Rahul/Pant/Kishan, RCB with multiple keeper-
  batters, etc.).

### The 0-keeper cases (17.3% at N=3)

Mostly minor/associate teams: Goa, Nigeria, Romania, Oman, etc.
Their keepers have <3 career stumpings in T20 data. Could be
partially resolved by:
- Lowering threshold to ≥2 for teams with no ≥3 keeper (adaptive)
- External data (ESPNcricinfo keeper designation via their API)
- Manual curation for major teams only

### The 2+ keeper cases (30% at N=3)

These are genuinely hard. Sampled examples:

- **MS Dhoni (81) + WP Saha (30)** — India/IPL. Dhoni usually kept
  in T20s but Saha kept in some matches.
- **KL Rahul (10) + KD Karthik (56)** — India/IPL. Karthik probably
  kept but Rahul kept in several IPL seasons for Lucknow.
- **Ishan Kishan (15) + RR Pant (36)** — India. Either could keep.
- **Q de Kock (55) + N Pooran (41)** — West Indies/franchise cricket.

A "pick the one with more career stumpings" heuristic would be right
~70% of the time but wrong in meaningful cases (e.g., Rahul kept for
LSG despite Karthik having more career stumpings).

Possible approaches for Tier 2:
1. **Heuristic**: most stumpings = likely keeper. Fast, ~70% accurate.
2. **Per-team-season analysis**: within a tournament-season, if one
   player has ALL the stumpings for their team, they're the keeper
   for that season. Handles the IPL case well (Rahul kept for LSG
   2022-2024, identifiable from his stumpings in those seasons).
3. **External data**: scrape ESPNcricinfo's match pages for keeper
   designation. High accuracy, high effort, fragile.
4. **Manual curation**: for the ~50 most-watched teams, maintain a
   `keeper_assignments.py` dict mapping (team, season) → person_id.
   Labor-intensive but deterministic.

### Mid-innings keeper changes

Only **5 matches** in the entire DB had stumpings credited to 2
different fielders in the same innings. Negligible for stats.
7 additional cases had substitute fielders taking stumpings.
Both can be handled as edge cases rather than first-class features.

## Proposed data model (when we build Tier 2)

### `keeper_assignment` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `innings_id` | INTEGER FK → innings | one assignment per innings |
| `person_id` | VARCHAR FK → person | who kept |
| `method` | VARCHAR | `stumping`, `single_candidate`, `heuristic`, `manual` |
| `confidence` | VARCHAR | `definitive`, `high`, `medium`, `low` |

Coverage target: ~61% of innings at `definitive` or `high`
confidence (layers 1+2). The remaining ~39% would be `medium`
(heuristic) or left unassigned.

### Impact on the fielding page

Once `keeper_assignment` exists:

- **"Keeping" sub-tab** on the fielding page for keeper-capable
  players. Shows: stumpings, catches-as-keeper (catches in innings
  where this player was the assigned keeper), byes conceded (from
  `delivery.extras_byes` in keeper-assigned innings), keeping
  dismissals per match keeping.

- **"Catches as keeper vs in field"** breakdown. For innings where
  we know who kept, a catch by the keeper is a "keeping catch"
  (different skill than an outfield catch). For innings where we
  don't know, catches are unattributed.

- **Caveat text** on the page: "Keeper stats shown for innings
  where the keeper was identified (X% of this player's career
  innings). Remaining catches are included in general fielding."

## Open questions for Tier 2

1. Should we show keeper stats with the caveat, or wait until we
   have external data for higher coverage?
2. Is per-team-season analysis (approach 2) worth the implementation
   cost? It would significantly improve IPL/BBL/Hundred coverage.
3. Should the `keeper_assignment` table be populated at import time
   (like `fielding_credit`) or computed lazily per API request?
4. Is "byes conceded" a useful stat? It requires summing
   `delivery.extras_byes` for all deliveries in innings where this
   player was the keeper — possible but adds another join.
