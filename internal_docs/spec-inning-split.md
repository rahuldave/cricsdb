# Spec — Inning split (1st innings / 2nd innings) on team + player stats

> **Status:** build-ready. New page-local filter dimension touching
> team + player Batting / Bowling / Fielding / Partnerships and the
> Compare-tab slot grammar. No DB migration. Architectural cost
> mostly mechanical — one new clause, one new aux field, one new
> set of by-inning band endpoints, one new frontend toggle component.

---

## 1. What this is

A new filter dimension that splits team and player stats by which
half of the match the data was generated in:

- `inning=0` → batting first (innings_number = 0 in the DB; for
  bowlers, this is "deliveries during the opposition's 1st innings",
  i.e. the team batted second).
- `inning=1` → batting second (innings_number = 1; for bowlers, the
  opposition batted first).
- `inning` unset → no narrowing; the existing aggregate behaviour.

User-visible labels are **"1st innings"** / **"2nd innings"** —
NEVER "bowled first / bowled second." The latter is a category error
for bowling/fielding stats: a team that "bowled first" was on the
field during innings 1, which is the team that batted second. The
innings-number framing avoids the confusion entirely; see §7.

In scope (full coverage):

- **Series dossier** (`/series?tournament=X`) — Overview, Batters,
  Bowlers, Fielders, Partnerships, Records subtabs (innings-joined,
  rides through the central clause via the §5.3 helper extension).
- **Teams page** (`/teams?team=X`) — By Season, vs Opponent,
  Batting, Bowling, Fielding, Partnerships, Players subtabs (page-
  level toggle); Compare tab (per-slot SlotScopeEditor override).
  Match-level endpoints (`/summary`, `/by-season`, `/vs-opponent`,
  `/match-list`) get inning narrowing via the new
  `_inning_match_filter` helper (§3.1a).
- **Players profile** (`/players?player=X`) — multi-band view.
- **Standalone discipline pages** — `/batting?player=X`,
  `/bowling?player=X`, `/fielding?player=X`.
- **Venues dossier** (`/venues?venue=X`) — Batters, Bowlers,
  Fielders, Records subtabs (Overview already splits natively, see
  §3.4).
- New `/by-inning` band endpoints on Team {Batting/Bowling/
  Fielding/Partnerships} (parallel to `/by-phase`).
- Chip-baseline alignment via `chip_baseline_scope_json`.
- Status-strip rendering on every tab where it's set.

Out of scope (intentionally — calling out before cutting under the
"DO NOT defer" rule):

- **Global FilterBar promotion.** User explicitly: "its not a main
  filterbar thing." The 10-key ceiling stands.
- **`/matches` list filter.** Matches are inherently both innings;
  filtering the list to "matches where this team batted first"
  isn't a product question.
- **`/head-to-head`** — explicitly deferred per user wording: "we
  will apply our comparison filters on the head to head pages as
  well in due course." Architecturally aligned (same `inning` URL
  param + slot override grammar), but waits for the H2H comparison-
  filters work.
- **`bucket_baseline` precomputation of by-inning aggregates.** Live
  aggregation handles it; precompute later if measured hot.
- **Match-role axis** (`bat_first=true|false`, "matches where this
  team batted first"). DIFFERENT axis from per-innings — see §9.

Slot's bands on Players subtab of Teams: NOT included. The Players
subtab is a list of player-rows showing each player's stats in
scope. Page-level toggle filters the list (each row recomputes for
the chosen inning); separate band rows per row would balloon the
surface. Toggle only.

---

## 2. Data layer — no migration

Verified facts (per the `DO NOT speculate` rule, every claim below
was queried against the DB before writing):

- `innings.innings_number INTEGER` already exists. 0-indexed:
  `0`=batting first, `1`=batting second; `2..7` are super-over
  re-innings.
- Super-over innings are already excluded by the `i.super_over=0`
  clause every endpoint applies. The inning split therefore only
  has to consider `innings_number IN (0, 1)`.
- 188 matches in DB have only `innings_number=0` (rain-abandoned /
  D/L). They contribute to `inning=0` aggregates and contribute
  nothing to `inning=1`. The partition invariant
  `metric(inning=0) + metric(inning=1) ≡ metric(unfiltered)` holds
  even with abandoneds — overall counts only include innings that
  actually exist. **Abandoned matches stay in** (per user); the
  natural SQL behaviour is correct, no special handling required.

**Partition invariant ground-truth (verified 2026-04-29):**

```
IPL 2025 men:           74 + 72 = 146 innings · 13974+12529=26503 runs · 2 abandoned
T20 WC Men 2024:        44 + 43 =  87 innings ·  5877+ 5196=11073 runs · 1 abandoned
BBL 2024/25:            42 + 41 =  83 innings ·  6931+ 6565=13496 runs · 1 abandoned
All men intl 2024:     333 +330 = 663 innings · 47184+38785=85969 runs · 3 abandoned
```

Plus partnerships and fielding credits for IPL 2025:

```
Partnerships:    528 + 458 = 986 (clean partition)
Fielding credits: 385 + 314 = 699 (clean partition)
```

So: deliveries, partnerships, AND fielding credits all partition
cleanly. No new column, no migration, no populate change.

---

## 3. Where it lands — endpoint inventory

### 3.1 Backend endpoints affected (filter clause added)

Team-side (`api/routers/teams.py`):
- `/{team}/batting/summary`, `/by-phase`, `/by-season`, `/by-over`,
  `/top-batters`, `/leaders`, `/phase-season-heatmap`
- `/{team}/bowling/{summary,by-phase,by-season,by-over,top-bowlers,
  phase-season-heatmap}`
- `/{team}/fielding/{summary,by-season,top-fielders}`
- `/{team}/partnerships/{summary,by-wicket,best-pairs,heatmap,top}`
- `/{team}/summary` — per-team results metrics, partitioned by inning
  via the `_inning_match_filter` helper described in §3.1a (a derived
  match-id subquery — the central `aux.inning` clause CAN'T be applied
  to this endpoint because it's `has_innings_join=False`).

Player-side (`api/routers/{batting,bowling,fielding,keeping}.py`):
- `/leaders` (batters / bowlers / fielders) — leaderboards filtered
- `/{person_id}/{summary,by-innings,by-phase,by-season,by-over,
  vs-bowlers,vs-batters,wickets,dismissals,inter-wicket}`

Series-side (`api/routers/tournaments.py`):
- `/series/summary` (Overview)
- `/series/by-season`
- `/series/records`
- `/series/{batters,bowlers,fielders}-leaders`
- `/series/partnerships/{by-wicket,top,top-by-wicket,heatmap}`

**Hand-rolled clause builders — disambiguated.**
`tournaments.py::_build_filter_clauses` serves two different call-site
populations:

- **/series dossier endpoints** (`/series/summary`, `/series/records`,
  `/series/{batters,bowlers,fielders}-leaders`, partnerships variants)
  — these JOIN innings and must apply the inning clause.
- **/tournaments dropdown** (FilterBar reference) — no innings join,
  inning is meaningless there.

Resolution: extend `_build_filter_clauses` to accept BOTH `aux:
AuxParams | None` AND a `has_innings_join: bool = True` parameter
(parallel to `FilterBarParams.build`). Dossier callers pass
`has_innings_join=True` and `aux=aux`; the dropdown caller in
`tournaments_list` passes `has_innings_join=False` and `aux=None`.
The clause body adds `i.innings_number = :inning` only when both
gates are open. Same shape applied to
`reference.py::_reference_clauses` (which today takes a series_type
arg via the same hand-rolled pattern — inning rides through the
same way). Both helpers are listed in the "trace every consumer"
check in §12.2.

This supersedes the bullet in §5.3 — the helpers ARE changed; the
guard is the new `has_innings_join` arg, not "no change needed."

Venues-side: `/venues?venue=X` subtabs reuse the existing
batters/bowlers/fielders leaderboards with `filter_venue` set.
The inning filter rides through naturally — no per-venue endpoint
to change. The venue's Overview endpoint
(`/venues/{venue}/summary`) already returns 1st-innings-vs-chase
splits as part of its native shape (avg 1st-innings total, bat-
first vs chase win %, toss correlation). Adding the page toggle
on top would conflict — Overview stays untouched, see §3.4.

Scope averages (`api/routers/scope_averages.py`):
- All 12 mirror endpoints. Required for chip-baseline alignment on
  Compare-tab when an avg slot has `compareN_inning` set.

NOT touched:
- `/api/v1/seasons`, `/api/v1/tournaments`, `/api/v1/teams` (search),
  `/api/v1/players` (search) — reference endpoints don't have an
  innings JOIN; the inning filter is meaningless there.
- `/venues/{venue}/summary` — already structured by inning natively.
- `/matches`, `/head-to-head/*` — out of scope per §1.

### 3.1a Match-level endpoints (`has_innings_join=False`) — per-endpoint contract

The central clause `i.innings_number = :inning` (§5.2) is gated on
`has_innings_join=True` because it references the innings alias.
But several team endpoints call `filters.build(has_innings_join=
False)` and would silently no-op on `?inning=0|1`. §3.3 promises a
toggle on these surfaces — so we need a parallel mechanism.

**Audit of `has_innings_join=False` call sites in `api/routers/
teams.py`** (verified by grep before writing this spec):

| Site | Endpoint family | Toggle in §3.3? |
|---|---|---|
| L60 `_team_filter_clause` | `/teams/{team}/summary`, match-list assembly | yes (`/summary` partitioned; match-list filtered) |
| L90 `teams_landing` | `/teams/landing` (directory) | no — directory, not a stats surface |
| L234 `_team_filter_clause` | `/teams/{team}/by-season` | yes |
| L471 `_team_filter_clause` | `/teams/{team}/vs-opponent` | yes |
| L1070 `_team_filter_clause` | `/teams/{team}/match-list` | yes |

Plus parallel sites in `tournaments.py` (Series leaders, records)
and `reference.py` (dropdowns) — already handled by the §5.3
disambiguation.

**Mechanism — `_inning_match_filter` helper.**
Add to `api/routers/teams.py` (mirroring the existing
`_team_filter_clause` shape):

```python
def _inning_match_filter(
    team: str,
    aux: AuxParams | None,
) -> tuple[str, dict]:
    """Return a match-level WHERE fragment that restricts to matches
    where :team played a role in the chosen inning. Empty when
    aux.inning is None.

    Semantics: aux.inning=0 → matches where :team batted in
    innings_number=0 (= matches where :team batted first).
    aux.inning=1 → matches where :team batted second.

    NOTE the asymmetry vs §3.4 Compare-slot dual-meaning: this helper
    is for match-level endpoints (/summary, /by-season, /vs-opponent,
    /match-list) where there's a single match subset. Bat-side framing
    is the natural reading for results-style metrics ("RCB's record
    batting first"). For Compare-slot dual-meaning on bowling/fielding
    rows, see §3.4 — that runs through the central innings clause,
    not this helper.
    """
    if aux is None or aux.inning is None:
        return "", {}
    return (
        "m.match_id IN ("
        " SELECT i2.match_id FROM innings i2"
        " WHERE i2.team = :im_team"
        "   AND i2.innings_number = :im_inn"
        "   AND i2.super_over = 0"
        ")",
        {"im_team": team, "im_inn": aux.inning},
    )
```

Compose in `_team_filter_clause`:

```python
def _team_filter_clause(filters, team_param=":team", aux=None,
                        team_value: str | None = None):
    where, params = filters.build(has_innings_join=False, aux=aux)
    parts = [f"(m.team1 = {team_param} OR m.team2 = {team_param})"]
    if where:
        parts.append(where)
    inn_clause, inn_params = _inning_match_filter(
        team_value or filters.team or "", aux
    )
    if inn_clause:
        parts.append(inn_clause)
        params.update(inn_params)
    return " AND ".join(parts), params
```

Endpoint-by-endpoint commitment (this is the spec, lock in before
commit 1):

| Endpoint | Inning behaviour |
|---|---|
| `/teams/{team}/summary` | matches/wins/losses/toss/win_pct partition into "team batted first" (inning=0) vs "team batted second" (inning=1) subsets. Pool counts on the team side; per-team-avg comparators on the league side run through the same `_inning_match_filter` so chip alignment holds. |
| `/teams/{team}/by-season` | row-level partition — each season-row reflects only matches in the chosen inning subset. Seasons with zero such matches drop out naturally. |
| `/teams/{team}/vs-opponent` | per-opponent record reflects only matches in the chosen inning subset. |
| `/teams/{team}/match-list` | filters to matches where :team had the role in inning X. (Useful: "show RCB's chase log" via inning=1.) |
| `/teams/landing` | NO toggle (per §3.3) — no change needed; helper isn't wired here. |

Per-innings-rate metrics on `/summary` (e.g. `win_pct`) keep the
same divisor logic as the existing per-team transform — but the
divisor (matches/decided/etc.) is computed from the
inning-narrowed subset, since the same clause is in the team-side
SQL. League-side mirror (`/scope/averages/team-summary`) needs the
SAME helper threading or chip math drifts; covered in §5.5.

Series-side analogue: NOT added in this spec. The Series Overview
endpoint joins innings already (verified by §3.1 enumeration), so
the central clause via the §5.3 helper extension covers it. If a
future Series-Overview metric is at match-level (no innings join),
revisit then.

### 3.2 New endpoints — by-inning band mirrors

Parallel to the existing `/by-phase` family:

- `/api/v1/teams/{team}/batting/by-inning`
- `/api/v1/teams/{team}/bowling/by-inning`
- `/api/v1/teams/{team}/fielding/by-inning`
- `/api/v1/teams/{team}/partnerships/by-inning`

Response shape mirrors `/by-phase`:

```json
{
  "innings": [
    {"inning_no": 0, "label": "1st innings", "metrics": {...envelopes...}},
    {"inning_no": 1, "label": "2nd innings", "metrics": {...envelopes...}}
  ]
}
```

Each metric is wrapped in the standard chip envelope
(`{value, scope_avg, delta_pct, direction, sample_size}`) so the
band rows participate in the existing chip-baseline alignment
mechanism. Backend handlers mirror `_batting_by_phase_aggregates`
etc., but `GROUP BY i.innings_number` instead of by phase CASE.

### 3.3 Frontend pages — per-subtab matrix

Per-subtab inventory, left to right. **toggle** = page-local pill
(`?inning=`); **slot** = per-slot dropdown in SlotScopeEditor;
**bands** = three-row InningBandsRow rendered always. Empty cell =
not in scope for this subtab.

#### `/series?tournament=X` — TournamentDossier

| Subtab | Mechanism | Why |
|---|---|---|
| Overview | toggle | tournament-wide patterns ("1st vs chase avg total") |
| Editions | — | list of editions, identity surface |
| Points | — | standings, not innings stats |
| Batters | toggle | leaderboard split |
| Bowlers | toggle | leaderboard split |
| Fielders | toggle | leaderboard split |
| Partnerships | toggle | "biggest 1st vs chase stands" |
| Records | toggle | "highest 1st-innings total" / chase total |
| Matches | — | list of matches |

#### `/teams?team=X` — Team profile

| Subtab | Mechanism | Why |
|---|---|---|
| By Season | toggle | team's per-season record split by inning |
| vs Opponent | toggle | rivalry record split |
| Compare | slot | per-slot SlotScopeEditor; no top-toggle |
| Batting | toggle + bands | page-level + 3-row band below headline |
| Bowling | toggle + bands | same |
| Fielding | toggle + bands | same |
| Partnerships | toggle + bands | same |
| Players | toggle | each player-row recomputes for chosen inning |
| Match List | — | list of matches |

User explicitly: "on the teams pages this seems to call for one
more filter (on the page not in the filter bar so as to affect the
first column)." That one filter = the page-level toggle pill,
sitting between FilterBar and tab nav. Affects every tab in the
"toggle" rows above (i.e. all subtabs except Compare and Match
List). On Compare, slot dropdowns own scope per-column.

#### `/players` (single profile, multi-band view)

| Surface | Mechanism |
|---|---|
| Batting / Bowling / Fielding / Keeping bands | page toggle |

#### Standalone discipline pages

| Page | Mechanism |
|---|---|
| `/batting?player=X` | toggle |
| `/bowling?player=X` | toggle |
| `/fielding?player=X` | toggle |

#### `/venues?venue=X` — VenueDossier

| Subtab | Mechanism | Why |
|---|---|---|
| Overview | — | already split natively (1st-inn avg / chase win%) |
| Batters | toggle | leaderboard split (reuses /batters/leaders) |
| Bowlers | toggle | leaderboard split |
| Fielders | toggle | leaderboard split |
| Matches | — | list |
| Records | toggle | venue records split by inning |

#### Pages NOT touched

`/matches`, `/series` landing, `/players` landing, `/teams`
landing, `/help`, `/venues` landing. `/head-to-head` is
architecturally aligned with the same `inning` URL param + slot
override grammar but defers to the H2H comparison-filters work
(§9).

### 3.4 Compare-tab semantic — slot inning=0 is dual-meaning

A slot with `compareN_inning=0` shows **two different match
subsets** on two different sides of the ball:

- **Batting metrics**: the team's batting innings where
  `i.innings_number=0` AND `i.team=team` → matches where this
  team batted FIRST.
- **Bowling / Fielding metrics**: the team's bowling-side
  aggregation where `i.innings_number=0` AND `i.team!=team` AND
  team is on the match → matches where opposition batted in inning
  0 → matches where this team BOWLED FIRST (= batted second).

These are **complementary match subsets** within the team's match
log: every match in the team's log has either the team batting in
inning 0 OR bowling in inning 0 (the team can't be in two places).
Across many matches, both subsets are non-empty. The slot
represents "this team's first-up activity in whatever role they
were in" — batted-first matches contribute to the batting row,
bowled-first matches contribute to the bowling/fielding row.

Equivalent table:

| Slot inning | Batting row reads | Bowling row reads |
|---|---|---|
| `0` | matches where team batted first | matches where team bowled first |
| `1` | matches where team chased | matches where team defended (bowled second) |
| unset | all matches | all matches |
| `__any__` (slot override) | broaden past primary's narrowing — same as unset | same |

**The user's question** ("team A batting first vs team B bowling
first") maps directly:

- Slot 1: Team A, `compare1_inning=0` → read the **batting** row.
- Slot 2: Team B, `compare2_inning=0` → read the **bowling** row.

User reads ACROSS rows in the comparison grid. Same `inning=0`
token on both slots — different match subsets per side because the
SQL clause `i.team=team` (batting) vs `i.team!=team` (bowling)
splits the role.

**SlotScopeEditor tooltip** must surface this so users don't read
"inning=1st on slot" and assume the bowling row is also "team in
their 1st-innings batting role":

> Innings: 1st innings only — batting row shows matches where this
> team BATTED FIRST; bowling/fielding rows show matches where this
> team BOWLED FIRST (= opposition batted first).

`InningToggle` on single-column pages (Team Batting tab, Player
Batting page, etc.) doesn't have this dual-meaning concern since
the page focuses on one discipline. The framing "1st innings"
applies cleanly: "Babar in 1st innings" = his batting in matches
where his team batted first; "Bumrah in 1st innings" = his bowling
when opposition batted first.

---

## 4. URL grammar

`inning` is a Query param. Encoded values:

- absent / `inning=` (empty) → no narrowing; "all innings".
- `inning=0` → 1st innings only (batting first).
- `inning=1` → 2nd innings only (batting second).

For Compare-tab per-slot overrides, follow the slot-override grammar
already shipped:

- `compareN_inning=0` / `compareN_inning=1` — slot scope-overrides
  to that inning.
- `compareN_inning=__any__` — explicit broaden past primary's
  inning narrowing (the `__any__` sentinel works the same as for
  every other overridable axis).

Frontend user-facing labels:

- "All innings" (toggle pill default; slot dropdown "— inherit —"
  with `(any)` option when primary has inning set).
- "1st innings"
- "2nd innings"

The internal code uses `inning` (matching `i.innings_number` on the
backend); the user never sees this token in the UI.

---

## 5. Backend changes

### 5.1 `api/filters.py` — `AuxParams.inning`

Per CLAUDE.md guidance ("Future page-local filters … land in
`AuxParams`"), `inning` is an aux field, not a FilterBarParams field
and not a per-router Query.

```python
class AuxParams:
    def __init__(
        self,
        scope_to_team: Optional[str] = ...,
        chip_team_class: Optional[str] = ...,
        chip_baseline_scope_json: Optional[str] = ...,
        inning: Optional[int] = Query(
            None, ge=0, le=1,
            description=(
                "Page-local filter on innings_number (0=batting first,"
                " 1=batting second). User-visible on team and player"
                " batting/bowling/fielding/partnerships pages as a"
                " toggle pill; per-slot override on the Compare tab"
                " via compareN_inning. NOT on FilterBar — its 10-key"
                " ceiling stands. Threaded through filters.build via"
                " aux=aux on every consumer."
            ),
        ),
    ):
        ...
        self.inning = inning
```

`AuxParams` continues to bear two roles: chip alignment hints
(`chip_*`) AND page-local narrowings (`scope_to_team`, `inning`,
and any future ones). Keep distinct in the docstring; rule of thumb
for future fields — page-local filter ⇒ AuxParams.

### 5.2 `FilterBarParams.build()` honours `aux.inning`

```python
if aux is not None and aux.inning is not None and has_innings_join:
    clauses.append(f"{innings_alias}.innings_number = :inning")
    params["inning"] = aux.inning
```

Gated on `has_innings_join` because the clause references the
innings alias. Endpoints that DON'T join innings naturally don't
narrow by inning; the aux field is silently a no-op there
(consistent with how every other innings-level clause behaves).

### 5.3 Hand-rolled clause builders

Two flavours. The split is per call-site, not per helper:

- **Dossier callers** (Series Overview / Records / leaders /
  partnerships) JOIN innings and need the inning clause. Per §3.1,
  `_build_filter_clauses` is extended to accept `aux: AuxParams |
  None` and `has_innings_join: bool = True`; dossier callers pass
  both. The body emits `i.innings_number = :inning` when
  `aux.inning is not None and has_innings_join`.
- **Reference dropdown callers** (`/api/v1/tournaments`,
  `/api/v1/seasons`, `reference.py::list_teams`,
  `reference.py::search_players`) don't join innings. They pass
  `has_innings_join=False` and `aux=None`. Inning narrowing is a
  silent no-op there — narrowing the FilterBar season dropdown by
  "1st innings" is meaningless.

### 5.4 `api/routers/bucket_baseline_dispatch.py`

`is_precomputed_scope` rejects when `aux.inning is not None`:

```python
def is_precomputed_scope(filters, aux):
    ...
    if aux is not None and aux.inning is not None:
        return False
    ...
```

Falls back to live aggregation. Bucket tables don't carry an
innings dimension; precompute later iff measured hot.

### 5.5 New `/by-inning` band aggregators

Mirror `_batting_by_phase_aggregates`,
`_bowling_by_phase_aggregates`, the partnerships per-wicket variant,
and the fielding per-season variant — but `GROUP BY
i.innings_number` instead of by phase CASE. Same envelope wrapping
via `wrap_metric`. Same per-innings transform via
`_apply_*_per_innings`.

**Per-innings divisor — invariant.** When `aux.inning` is set, every
per-innings transform helper MUST receive a divisor (`innings_batted`
/ `innings_bowled` / `innings_fielded` / `partnerships_count`)
computed from the SAME inning-filtered query that produced the
numerator. Concretely:

- Numerator (e.g. `total_runs`): `SUM(...) WHERE i.team=:team AND
  i.innings_number=:inning AND ...`
- Divisor (`innings_batted`): `COUNT(DISTINCT i.id) WHERE i.team=
  :team AND i.innings_number=:inning AND ...`
- Per-innings rate: numerator / divisor

A divisor pulled from a separate (non-narrowed) query — e.g. by
reusing a cached "total innings_batted in scope" computed before the
inning clause was added — would produce a per-innings rate that
silently halves (the numerator narrows, the denominator doesn't).
Chip envelopes' `scope_avg` would then disagree with the avg-col
displayed value, breaking the chip alignment invariant.

The rule applies on BOTH sides:

- Team-side (`teams.py::_apply_{batting,bowling,fielding,
  partnerships}_per_innings` call sites): the divisor is read from
  the same row in the same query that has the inning clause applied.
  If the divisor comes from a sibling query (rare, but exists for
  fielding which JOINs `fieldingcredit`), that sibling query gets
  the same `aux.inning`-derived clause.
- League-side (`scope_averages.py` mirrors + `_league_aux` chip
  baseline): the divisor is computed from the league pool with the
  same `aux.inning` (or, for chip alignment under broaden direction,
  the `chip_baseline_scope_json` payload's `inning` field).

Sanity-test assertion (covered in §10.1): for each scope,
`per_innings_rate(inning=0)` and `per_innings_rate(inning=1)`
weight-reconstruct the unfiltered rate via
`(rate_0 * count_0 + rate_1 * count_1) / (count_0 + count_1)`.
A mismatched divisor breaks this invariant cleanly.

Implementation note: grep `_apply_.*_per_innings\(` in
`api/routers/teams.py` and `api/routers/scope_averages.py` before
shipping commit 1 — every call site must be inning-aware. List in
§12.2 trace.

---

## 6. Frontend changes

### 6.1 `InningToggle.tsx` (new)

Three-pill segmented control reading/writing the URL `inning`
param via `useUrlParam('inning')`:

```
[ All innings | 1st innings | 2nd innings ]
```

Mounted at the top of:
- `Teams.tsx` Batting tab content
- `Teams.tsx` Bowling tab content
- `Teams.tsx` Fielding tab content
- `Teams.tsx` Partnerships tab content
- `Batting.tsx` (player page) — above the stats
- `Bowling.tsx` (player page)
- `Fielding.tsx` (player page)

NOT mounted on the Compare tab — slot-level override is the
mechanism there.

### 6.2 `useCompareSlots.ts` — `inning` joins the slot grammar

```ts
export const OVERRIDABLE_SLOT_KEYS = [
  'tournament', 'season_from', 'season_to',
  'filter_venue', 'series_type', 'team_class', 'inning',  // new
] as const

export type ResolvedSlotScope = Pick<FilterParams, /* ... */> & {
  inning?: '0' | '1'
}
```

`readSlot` decodes `compareN_inning=0|1|__any__` per the
slot-override-chip-alignment.md grammar. `inheritedScope` carries
`inning` from primary (read from URL `inning` param). `__any__`
override → resolved scope's inning is `undefined`.

### 6.3 `SlotScopeEditor.tsx`

New row, parallel to `Series` and `Class`:

```tsx
<div style={fieldStyle}>
  <span style={labelStyle}>Innings</span>
  <select value={inning} onChange={e => setInning(e.target.value)}>
    <option value="">— inherit —</option>
    {showAny.inning && <option value={ANY_SENTINEL}>(any — all innings)</option>}
    <option value="0">1st innings only</option>
    <option value="1">2nd innings only</option>
  </select>
</div>
```

Always rendered (no team_type gate; inning applies to both intl and
club). `showAny.inning` true iff primary has inning set.

### 6.4 `ColumnScopeStrip.tsx`

`buildSlotSegments` adds an `Inning` segment when `scope.inning`
is set OR when `'inning' in overrides`:

```ts
if (scope.inning === '0') segs.push({label: 'Inning', value: '1st', overridden: ovr('inning')})
else if (scope.inning === '1') segs.push({label: 'Inning', value: '2nd', overridden: ovr('inning')})
else if (ovr('inning')) segs.push({label: 'Inning', value: 'any', overridden: true})
```

### 6.5 `TeamCompareGrid.tsx::chipAlignmentFor`

`chip_baseline_scope_json` payload includes `inning` so the
team-side chip's `scope_avg` baselines against the avg slot's
inning narrowing:

```ts
for (const k of OVERRIDABLE_SLOT_KEYS) {
  const v = avg.scope[k]
  if (v) payload[k] = v
}
```

OVERRIDABLE_SLOT_KEYS already iterates inning post-§6.2. So this
section is a no-op once §6.2 lands — just a verification step.

### 6.6 `ScopeStatusStrip.tsx`

`buildSegments` adds a segment for `inning` so the page-wide
status bar reflects the active inning narrowing:

```ts
const inning = params.get('inning')
if (inning === '0') segs.push({label: 'Inning', value: '1st innings'})
else if (inning === '1') segs.push({label: 'Inning', value: '2nd innings'})
```

Segment placement: between Season and Venue (logical flow: who →
when → which inning of the match → where).

### 6.7 `InningBandsRow.tsx` (new)

Parallel to `PhaseBandsRow.tsx`. Three rows (Overall / 1st innings
/ 2nd innings) reading from `/by-inning` endpoint response. Mounted
on:

- Team Batting tab — below the existing PhaseBandsRow
- Team Bowling tab — below the existing PhaseBandsRow
- Team Fielding tab — there is no existing phase band; add the
  inning band as the only band row
- Team Partnerships tab — same

NOT on player pages (keeps player page tight; user flips the toggle
to navigate the three views).

### 6.8 API client (`api.ts`)

Each endpoint client gains an `inning` field on the params type:

```ts
type FilterParams = {
  ...
  inning?: string
}
```

`fetchApi` already drops null/undefined params. `'0'` and `'1'` are
truthy strings so they ride through.

New endpoint clients:
```ts
export const getTeamBattingByInning = (team, filters) =>
  fetchApi('/api/v1/teams/' + ... + '/batting/by-inning', filters)
// + bowling, fielding, partnerships variants
```

Add to `getTeamProfile` parallel-fetch (4 new fetches per team
column on Compare tab — bumps from 12 to 16).

---

## 7. Reading conventions — labels + slot semantics

### 7.1 POV-aware inning labels (updated 2026-05-12)

**Original policy (deprecated 2026-05-12):** the toggle showed "1st
innings" / "2nd innings" everywhere, on the theory that "bowled
first" / "fielded first" risk confusing a casual reader.

**Revised policy:** `?inning=0/1` always means the match's
`innings.innings_number=0/1`; the URL semantics are constant. The
**rendered pill label** is POV-aware via `useDiscipline()`:

| Page POV | `useDiscipline()` returns | Pill label |
|---|---|---|
| Batting · Partnerships | `'batting'` | `Batting first` / `Batting second` |
| Bowling · Fielding | `'bowling'` / `'fielding'` | `Bowling first` / `Bowling second` |
| Ambiguous (Records, single-player profile) | `null` | `1st innings` / `2nd innings` |

Cricket idiom resolves the bowler/fielder confusion: "Bumrah bowled
first" = his team was the fielding side in innings_number=0 = he
was bowling while the OPPOSITION batted first. This matches the
conventional reading. Fielding pages adopt **bowling** terminology
("Bowling first") because the fielding side IS the bowling side
in any given innings — never "Fielded first".

**Ambiguous pages stay neutral** because a single `?inning=0`
simultaneously means three different POVs on one page: the batting
section reflects batted-first, the bowling section bowled-first,
the fielding section fielded-first. No single POV label can be
accurate for all three on the same page. Polysemy is locked by
`tests/integration/inning_toggle_pov_labels.sh` Part B.

13 mount sites: 4 batting-POV, 6 bowling/fielding-POV, 3 ambiguous.
Source-of-truth rule lives in `CLAUDE.md` "Inning-toggle labels"
under Page conventions; cross-codebase consistency comes from
the single hook (no per-component POV resolution).

### 7.2 Slot-level inning=0 is dual-meaning (Compare tab)

§3.4 covered the SQL semantic; the user-facing convention:

> When a Compare slot has Innings = 1st innings only, the slot's
> BATTING row shows matches where the team BATTED FIRST; the
> BOWLING and FIELDING rows show matches where the team BOWLED
> FIRST (= opposition batted first). These are complementary
> subsets of the team's match log; together they represent the
> team's "first-up activity" across roles.

The SlotScopeEditor's "Innings" dropdown gets a hover tooltip
with this text. The ColumnScopeStrip segment for `inning=0`
shows as "Inning: 1st" — the user clicks for the tooltip if
unsure.

`InningToggle` on single-column pages (Team Batting, Player
Batting, etc.) doesn't have this issue — page is one discipline.

### 7.3 Single-discipline pages (single-column reading) — updated 2026-05-12

Player Batting page with inning=0: pill reads "Batting first" —
his batting in matches where his team batted first. Direct.

Player Bowling page with inning=0: pill reads "Bowling first" —
his bowling when his team was the fielding side in the 1st innings
(i.e. opposition batted first). Cricket idiom resolves: "Bumrah
bowled first" reads naturally.

Player Fielding page with inning=0: pill reads "Bowling first" —
fielding inherits bowling terminology because the fielding side
IS the bowling side in any innings (Convention 3 of cricket
parlance, mirrored in `useDiscipline()` returning `'fielding'` →
same Bowling-first label as `'bowling'`).

---

## 8. Chip-baseline alignment

When an avg slot on the Compare tab carries `compareN_inning=X`,
the team-side chip envelopes' `scope_avg` must align with the
avg col's displayed value (the math invariant that
`spec-slot-override-chip-alignment.md` enforces).

Mechanism: `chip_baseline_scope_json` already serializes the avg
slot's full effective scope. Once `inning` is in
OVERRIDABLE_SLOT_KEYS (§6.2), the iterate in
`chipAlignmentFor` automatically includes it in the payload.
Backend `_decode_chip_baseline` already preserves whatever's in
the payload onto the league-side filters via `FilterBarParams`. So
inning rides through with zero new code — verify in §10.3.

The narrow back-compat path (`chip_team_class` aux hint, deprecated
2026-04-29) does NOT cover inning. Clients still on the deprecated
shortcut won't get correct inning chip alignment. Document this in
the deprecation note. Targeted removal of `chip_team_class`
post-soak takes care of the divergence.

---

## 9. Out of scope (explicit, with justification)

Per the `DO NOT defer parts of an assigned task` rule, listing
what's NOT in this spec — with the reason — so future work can
pick up where this leaves off:

- **`/matches` list filtering by inning** — matches are inherently
  both innings; "matches where this team batted first" isn't a
  product question users ask of a match list. The match-level
  filter belongs to the separate "match-role" axis below.
- **`/head-to-head` inning split** — explicitly deferred per user:
  "we will apply our comparison filters on the head to head pages
  as well in due course." Architecturally aligned: H2H reads the
  same `inning` URL param and slot-override grammar; landing it
  is a follow-up commit when the H2H comparison-filters work
  starts. Both `mode=team` and `mode=player` will get the toggle.
- **Bucket-baseline precomputation of by-inning aggregates** —
  bucket tables don't carry an innings dimension and adding one
  doubles the row count. Live aggregation handles it; only
  precompute if measured hot.
- **"Chasing" semantic** — D/L revisions and reduced-overs matches
  change the chase target but not innings_number. We use
  innings_number as the safe primitive; "chasing" is a derived
  concept not modeled here. Don't conflate.

### 9.1 Match-role axis (separate future filter)

A user request like "show me Team A's full stats restricted to
matches where Team A batted first" is **not** what `inning=0` does
on the Compare slot model. Per §3.4, slot `inning=0` produces:

- batting row from matches-where-batted-first (subset X)
- bowling row from matches-where-bowled-first (subset Y, disjoint
  from X)

Together: every match contributes SOMETHING somewhere. Together
they DON'T equal "matches where Team A batted first."

A match-role filter would be a SEPARATE axis:

- `bat_first=true` → restrict to matches in which this team batted
  first (regardless of which innings the data was generated in).
  Within those matches, batting stats reflect inning=0 by
  construction; bowling stats reflect inning=1 (the chase they
  defended).
- `bat_first=false` → restrict to matches the team chased.

Notes on this separate axis:

- It's match-level (boolean derived from the team's role), not
  innings-level. SQL clause is on `m.team1`/`m.team2` × the
  match-level "team batted first" determination — different from
  `i.innings_number = :inning`.
- Composes with `inning` orthogonally: `bat_first=true&inning=0`
  is "batting stats from matches the team batted first" (= the
  current `inning=0` batting subset; redundant), but
  `bat_first=true&inning=1` is "bowling stats from matches the
  team batted first" (= the chase-defence stats).
- Useful for the question "What does Team A do AFTER they bat
  first?" — i.e. how do they defend the score.

**Not in this spec.** Adding it now muddies the per-innings story
and the user didn't ask for it. Document here as a future axis so
the next person picking up this surface knows the difference.

If the H2H comparison-filters work later wants both axes, the
mechanism is two URL params: `inning` (per-innings) and
`bat_first` / `match_role` (match-role boolean). They're
orthogonal and each fits as an `AuxParams` field per the
established CLAUDE.md convention.

---

## 10. SQL + test plan

### 10.1 Sanity test — `tests/sanity/test_inning_split_partition.py`

For each of N closed-window scopes, assert the partition invariant
across multiple metric families:

```python
SCOPES = [
    ("ipl_2025_men", {gender:male, team_type:club, tournament:IPL, season:2025}),
    ("t20wc_men_2024", {gender:male, team_type:international, tournament:T20WC, season:2024}),
    ("bbl_2024_25", {gender:male, team_type:club, tournament:BBL, season:2024/25}),
    ("men_intl_2024", {gender:male, team_type:international, season:2024}),
]

ADDITIVE_METRICS = (
    # batting
    "matches", "innings_batted", "total_runs", "legal_balls",
    "fours", "sixes", "dots", "fifties", "hundreds",
    # bowling
    "innings_bowled", "runs_conceded", "wickets",
    "fours_conceded", "sixes_conceded", "wides", "noballs",
    # fielding
    "catches", "caught_and_bowled", "stumpings", "run_outs",
    "total_dismissals_contributed",
    # partnerships
    "total", "count_50_plus", "count_100_plus",
)

# For each scope:
for label, scope in SCOPES:
    for team in teams_in_scope:
        for metric in ADDITIVE_METRICS:
            v_all = aggregate(team, scope, inning=None, metric)
            v_0   = aggregate(team, scope, inning=0,    metric)
            v_1   = aggregate(team, scope, inning=1,    metric)
            assert v_0 + v_1 == v_all
```

Plus a per-innings-rate check (run rate, avg, economy etc.):
weighted-by-innings-count reconstruction:

```python
v_all = (v_0 * count_0 + v_1 * count_1) / (count_0 + count_1)
```

This is the invariant that catches a wrong divisor (§5.5) — if the
denominator on either side wasn't inning-narrowed, the
weight-reconstruction will diverge from `v_all`.

**Identity-bearing fields** (different invariant — max-of-pieces).
Partition doesn't apply to `highest_total`, `lowest_all_out`,
`best_pair`, `worst_inn_runs`. The relationship is:

```python
unfiltered_max == max(inning0_max, inning1_max)
unfiltered_min == min(inning0_min, inning1_min)  # when defined
```

…assuming the metric is monotone within a side. Test: for each
scope, query the field with no inning filter and with inning=0 +
inning=1; assert max/min reconstruction. Skip when the field is
null (scope produced no innings of that flavour — abandoneds).

**Match-level no-op assertion.** `/teams/landing` is the lone
`has_innings_join=False` site that intentionally ignores inning
(per §3.1a). Assert: `GET /teams/landing?...&inning=0` returns
byte-identical JSON to `GET /teams/landing?...` (no inning param).
Catches accidental wiring of `_inning_match_filter` to the landing.

Time-pinned to closed-window anchors — copy-paste of
`test_chip_direction_invariant.py`'s scope list works as the seed.

Expected runtime: under 5s (N scopes × ~K teams × M metrics — each
aggregate is one SQL).

### 10.2 Regression — NEW URLs

Per-suite enumeration (concrete URL counts, not "~"):

**`tests/regression/teams/urls.txt`** — 16 NEW + 4 REG:
- `/teams/{team}/{batting,bowling,fielding,partnerships}/summary` × 2 inning (8 NEW)
- `/teams/{team}/{batting,bowling,fielding,partnerships}/by-inning` × 1 (4 NEW)
- `/teams/{team}/summary?inning=0|1` (2 NEW — match-level via
  `_inning_match_filter`, §3.1a)
- `/teams/{team}/by-season?inning=0|1` (2 NEW)
- 4 REG entries with `&inning=0|1` to lock in the partition shape.

**`tests/regression/batting/urls.txt`** — 4 NEW:
- `/batters/{p}/summary?inning=0|1` (2)
- `/batters/leaders?...&inning=0|1` (2)

**`tests/regression/bowling/urls.txt`** — 4 NEW (mirror of batting).

**`tests/regression/fielding/urls.txt`** — 4 NEW.

**`tests/regression/series/urls.txt`** — 14 NEW (Series dossier
coverage, was missing in v1 of this spec):
- `/series/summary?...&inning=0|1` (2)
- `/series/by-season?...&inning=0|1` (2)
- `/series/records?...&inning=0|1` (2)
- `/series/{batters,bowlers,fielders}-leaders?...&inning=0|1` (6)
- `/series/partnerships/{by-wicket,top}?...&inning=0|1` (4 — pick 2
  variants × 2 inning)
- 2 REG entries.

**`tests/regression/scope-averages/urls.txt`** — 12 NEW (1 per
mirror endpoint × inning=0; the 0/1 partition is checked by sanity
test, regression just needs anchor numbers).

**`tests/regression/players/urls.txt`** — 0 NEW (Players page is a
frontend composer; backend coverage rides through batting/bowling/
fielding suites).

**`tests/regression/venues/urls.txt`** — 0 NEW (Venues subtabs
reuse `/batters/leaders` etc. with `filter_venue` — covered by
batting/bowling/fielding suite NEW URLs; add 2 REG entries with
`filter_venue` + `inning` to confirm composition).

Total: ~58 NEW + ~10 REG across 6 suites.

**Critical invariant**: every existing `inning`-absent REG URL
MUST stay byte-identical post-Commit-1. The central clause is
gated on `aux.inning is not None`, so no inning param ⇒ no
clause ⇒ same SQL. If a single REG drifts, the gate is wired
wrong — investigate before shipping.

### 10.3 DOM tests

`tests/integration/dom/cross_cutting_inning_split.sh` (NEW) —
this is the central new DOM test. Five sections, each with raw-
output assertions per the audit-prompt-discipline rule in CLAUDE.md
(literal cell text, not "PASS/FAIL summaries"):

**§A — single-team toggle, partition.**
- Anchor: `/teams?team=RCB&tab=Batting&season_from=2025&
  season_to=2025`.
- Capture headline `run_rate`, `total_runs`, `matches`, `innings`
  for All / 1st / 2nd.
- Assert `total_runs(all) == total_runs(1st) + total_runs(2nd)`,
  `innings(all) == innings(1st) + innings(2nd)`.
- Assert `run_rate` differs across the three states (would catch a
  silent no-op where the toggle changes the URL but nothing else).

**§B — Compare-slot dual-meaning** (was missing in v1 of this
spec; flagged in code review as the most under-tested semantic).
- Anchor: `/teams?team=RCB&tab=Compare&compare1=Royal%20...&
  compare1_inning=0` (slot 1 = same team, batted-first override).
- Capture the slot column's BATTING row metrics AND BOWLING row
  metrics.
- Assert: batting-row's `innings_count` is the count of "RCB
  batted first" matches in scope; bowling-row's `innings_count`
  is the count of "RCB bowled first" matches in scope.
- Assert the two counts are NOT equal (proves the dual-meaning is
  surfacing different match subsets, not the same subset rendered
  twice). Sum of the two counts ≈ total RCB matches in scope (off
  by however many abandoneds — assert ≥ 95% of total).

**§C — chip alignment under inning override.**
- Anchor: `/teams?team=RCB&tab=Compare&compare1=__avg__&
  compare1_inning=0`.
- For each chip-bearing metric, capture the team-side chip's
  `scope_avg` AND the avg col's displayed value.
- Assert `chip.scope_avg == avg.displayed` (math invariant —
  same shape as `cross_cutting_slot_override_chip_align.sh`).

**§D — status strip rendering.**
- Anchor: `/teams?team=RCB&inning=0`.
- Assert the status strip contains a segment with label "Inning"
  and value "1st innings" (literal text match).
- Repeat with `inning=1` → "2nd innings".
- Anchor without `inning` → status strip has NO "Inning" segment.

**§E — toggle pill ↔ URL roundtrip.**
- Anchor: `/teams?team=RCB&tab=Batting`.
- Click "1st innings" pill → URL gains `inning=0` (no full reload).
- Click "2nd innings" → URL gains `inning=1`.
- Click "All innings" → `inning` removed from URL.
- Browser back button walks `inning=1 → inning=0 → (none)`.

Per-page DOM tests gain new anchors with `&inning=0|1`:
- `teams_batting_{club,intl}.sh` — 1 anchor each
- `teams_bowling_{club,intl}.sh` — 1 each
- `teams_fielding_{club,intl}.sh` — 1 each
- `teams_partnerships_{club,intl}.sh` — 1 each
- `teams_overview_{club,intl}.sh` — 1 each (verify match-level
  partition via `_inning_match_filter`)
- `teams_compare_{club,intl}.sh` — 1 each with slot override
- `players_single_{club,intl,intl_women}.sh` — 1 each
- `series_overview_{club,intl}.sh` + `series_records_{club,intl}.sh`
  + `series_{batters,bowlers,fielders}_{club,intl}.sh` — 1 each
- `venues_{batters,bowlers,fielders}_club.sh` — 1 each

~26 per-page anchor additions. Each is a small append to an
existing `.sh` script.

### 10.4 Canaries (must stay green throughout)

- `test_chip_direction_invariant.py` — adding `inning` to the slot
  grammar must NOT change pre-existing chip behaviour.
- `test_slot_override_alignment.py` — same.
- `cross_cutting_slot_override_chip_align.sh` — chip alignment
  under broaden direction. Adding inning shouldn't affect
  non-inning-set anchors.
- All existing REG URLs without `&inning` must stay byte-identical.

---

## 11. Migration sequence

6 commits, in order. Each ships its own tests + docs (per
CLAUDE.md "Keeping docs in sync" + commit-cadence rules — no
catch-all "tests + docs" commit at the end).

1. **Backend `inning` filter primitive + match-level helper.**
   - `AuxParams.inning` + `FilterBarParams.build()` clause +
     `is_precomputed_scope` rejection.
   - `_inning_match_filter` helper (§3.1a) wired into
     `_team_filter_clause` so `/teams/{team}/{summary,by-season,
     vs-opponent,match-list}` partition correctly.
   - `_build_filter_clauses` extension (§5.3) — accepts `aux` +
     `has_innings_join`; dossier callers pass True.
   - Sanity test `tests/sanity/test_inning_split_partition.py` —
     additive partition + per-innings-rate weight reconstruction
     + identity-bearing max/min reconstruction + `/teams/landing`
     no-op assertion (§10.1).
   - **Docs**: `internal_docs/design-decisions.md` bowler-
     labelling convention (§7.1) + match-role-axis-vs-per-innings
     distinction (§9.1).
   - No frontend change yet — every backend endpoint accepts
     `?inning=0|1` and returns the partitioned aggregate.
   - Regression: every existing REG URL stays byte-identical.

2. **Backend `/by-inning` band endpoints.** Team-side only (per
   §12.3 decision: player pages use the toggle, no player-side
   band endpoints). New aggregators mirror `/by-phase` for
   batting/bowling/fielding/partnerships. Same envelope
   wrapping, `GROUP BY i.innings_number`. Per-innings divisor
   from inning-narrowed query per §5.5 invariant.
   - Tests: NEW regression URLs in `tests/regression/teams/
     urls.txt` for the four new endpoints.
   - Docs: `docs/api.md` entries for the four new endpoints +
     `internal_docs/codebase-tour.md` entry under teams.py.

3. **Frontend slot-grammar + Compare tab override.**
   `OVERRIDABLE_SLOT_KEYS` adds `inning`; `SlotScopeEditor`
   "Innings" row with the dual-meaning tooltip from §7.2;
   `ColumnScopeStrip` "Inning:" segment; `chipAlignmentFor`
   verify (§6.5).
   - Tests: extend
     `tests/integration/dom/cross_cutting_slot_override_chip_align
     .sh` with an inning anchor; ship the §B + §C blocks of
     `cross_cutting_inning_split.sh` (Compare-slot dual-meaning +
     chip alignment).
   - Docs: `internal_docs/design-decisions.md` slot-grammar
     extension entry; `internal_docs/spec-team-compare-scoped-
     slots.md` cross-link.

4. **Frontend toggle on player pages.** `InningToggle.tsx`
   mounted on `Batting.tsx`, `Bowling.tsx`, `Fielding.tsx`.
   URL param `inning` flips the headline.
   - Tests: per-page anchors in `players_single_*.sh` (§10.3
     per-page list).
   - Docs: `internal_docs/codebase-tour.md` frontend hooks
     block notes the new component.

5. **Frontend toggle on team tabs (no bands yet) + status
   strip.** `InningToggle` mounted on Team Batting / Bowling /
   Fielding / Partnerships / By Season / vs Opponent tabs.
   `ScopeStatusStrip` segment for inning (§6.6).
   - Tests: ship the §A + §D + §E blocks of
     `cross_cutting_inning_split.sh` (single-team toggle
     partition + status strip + URL roundtrip); per-page
     `teams_*.sh` anchors.
   - Docs: `internal_docs/how-stats-calculated.md` partition
     semantic entry.

6. **Frontend band rows on team tabs.** `InningBandsRow.tsx`
   reading `/by-inning` band endpoints. Three rows (Overall /
   1st / 2nd) below the existing Phase bands on Team
   Batting/Bowling/Fielding/Partnerships tabs.
   - Tests: extend `teams_{batting,bowling,fielding,
     partnerships}_*.sh` with a band-row presence + value
     check.
   - Docs: `CLAUDE.md` "Key Files" line for `InningBandsRow.tsx`
     parallel to `PhaseBandsRow.tsx`.

Estimated total effort: ~14-17h (was 12-15h in v1 — added time
for `_inning_match_filter` per-endpoint surgery + per-commit doc
discipline).

Risk: **low-to-moderate**. One new clause + one new helper
(_inning_match_filter), one new aux field, four new band
endpoints. The match-level helper is the only architectural
addition; the rest is mechanical. The slot-grammar piece rides
entirely on the override mechanism shipped 2026-04-29.

---

## 12. Pre-flight checklist

### 12.1 Capture baselines (before commit 1)

```bash
# 1. Chip invariant — must stay 15/15 PASS.
uv run python tests/sanity/test_chip_direction_invariant.py 2>&1 | tail -3

# 2. Slot-override alignment — must stay 6/6 PASS.
uv run python tests/sanity/test_slot_override_alignment.py 2>&1 | tail -3

# 3. Per-suite regression baseline.
for suite in teams series scope-averages batting bowling fielding \
             players head_to_head matches venues filterbar_refs; do
  awk -v s="$suite" '/^REG/{r++} /^NEW/{n++}
    END{printf "%-18s REG=%d NEW=%d\n", s, r, n}' \
    tests/regression/$suite/urls.txt
done

# 4. Verify the partition invariant on the SCOPES list before
#    committing the sanity test — manual SQL spot-check confirms
#    the test's ground truth.
uv run python -c "
import sqlite3
c = sqlite3.connect('cricket.db')
... # run the partition queries from §2 again
"
```

### 12.2 Trace every consumer of `aux=` AND every per-innings divisor

```bash
# Every filters.build() call site — must pass aux=aux (or aux=None).
grep -rn "filters\.build\(" api/ | grep -v test

# Every per-innings transform helper call site — must use a
# divisor from the inning-narrowed query (per §5.5 invariant).
grep -rn "_apply_.*_per_innings\(" api/ | grep -v test

# Every call site of the hand-rolled clause builders that the
# §5.3 disambiguation extends — must pass has_innings_join +
# aux per-call.
grep -rn "_build_filter_clauses\|_reference_clauses" api/ | grep -v test

# Every has_innings_join=False call site in teams.py — confirm
# §3.1a has decided which ones get _inning_match_filter wired and
# which stay no-op (landing).
grep -rn "has_innings_join=False" api/routers/teams.py
```

Per the shared-helper contract in CLAUDE.md, omitting `aux=aux`
leaves `aux` as a free variable — import-time silent, request-
time 500. The `inning` clause is gated on `aux.inning`, so any
call site that drops aux silently fails to narrow.

For the divisor grep: every match must be inning-aware before
shipping commit 1. A wrong divisor breaks the per-innings-rate
weight-reconstruction in `tests/sanity/test_inning_split_
partition.py`, which is the canary.

### 12.3 Decisions to make before commit 1

- **Player page band endpoint?** §11 commit 2 punts to "team-side
  only." Confirmed. Player pages already toggle the whole page
  via §6.1; band rows would duplicate the data the user is
  already looking at. Skip unless user asks.
- **Toggle pill default?** "All innings" (no narrowing) — matches
  the convention of every other narrowing field.
- **Chip baseline alignment for inning** — verify §6.5 (no new
  code needed) by running the broaden-direction DOM test with an
  inning override before claiming done.
- **Match-level endpoint semantic — already locked.** §3.1a
  commits `/teams/{team}/summary` and friends to the "team batted
  first" reading via `_inning_match_filter`. This is NOT the
  Compare-slot dual-meaning of §3.4 — different mechanism,
  different endpoints. Don't conflate.

### 12.4 Per-commit gate criteria

- **Commit 1 (backend filter primitive + match-level helper).**
  All existing `inning`-absent REG URLs byte-identical. Sanity
  tests pass: chip invariant, slot alignment, NEW partition test
  (additive + weight-reconstruction + identity-bearing max/min +
  `/teams/landing` no-op). Per-endpoint smoke: curl
  `/teams/{team}/summary?inning=0` and `?inning=1` against an IPL
  2025 anchor — partition reconciles. Bowler-labelling convention
  in design-decisions.md.
- **Commit 2 (band endpoints).** `/by-inning` endpoints return
  the same partitioned aggregates as 2× corresponding
  `/summary?inning=0|1`. NEW regression URLs added in
  `tests/regression/teams/urls.txt`. `docs/api.md` entries
  shipped.
- **Commit 3 (slot grammar).** chip invariant + slot-override
  alignment tests stay PASS. New DOM cross-cutting §B + §C
  blocks PASS. SlotScopeEditor "Innings" tooltip surfaces the
  dual-meaning text per §7.2.
- **Commit 4 (player-page toggle).** Frontend tsc -b clean. UI
  verification via agent-browser per CLAUDE.md UI-verification
  rule — load `/batting?player=...` etc., exercise three states,
  confirm partition invariant at rendered level. `players_single
  _*.sh` anchors PASS.
- **Commit 5 (team-tabs toggle + status strip).** Same UI
  verification on team tabs. Cross-cutting §A + §D + §E blocks
  PASS. Status-strip rendering test PASS. how-stats-calculated.md
  partition entry shipped.
- **Commit 6 (band rows).** UI verification on team tabs; bands
  aligned with existing PhaseBandsRow visually. `teams_*.sh`
  anchors include band-row presence checks. CLAUDE.md "Key
  Files" updated.

There is no commit 7. Each feature commit ships its own tests +
docs.

---

*Spec written 2026-04-29 after the slot-override-chip-alignment
rollout shipped. Builds directly on the slot-override grammar +
chip-baseline mechanism shipped that same day. Revised 2026-04-29
after critical review: added §3.1a match-level endpoint contract
+ `_inning_match_filter` helper (resolves `has_innings_join=False`
silent no-op), disambiguated §3.1↔§5.3 hand-rolled clause builder
contradiction, tightened §5.5 per-innings divisor invariant,
expanded §10 test plan (identity-bearing fields, dual-meaning
DOM test, status-strip + URL roundtrip, enumerated regression
URLs), redistributed commit 7's contents across commits 1-6.
Pick up at §11 commit 1.*
