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
  Bowlers, Fielders, Partnerships, Records subtabs.
- **Teams page** (`/teams?team=X`) — By Season, vs Opponent,
  Batting, Bowling, Fielding, Partnerships, Players subtabs (page-
  level toggle); Compare tab (per-slot SlotScopeEditor override).
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
- `/{team}/summary` — per-team results metrics: matches/wins/losses
  partitioned by inning (1st-innings record vs 2nd-innings record)

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

Note: `tournaments.py::_build_filter_clauses` is a hand-rolled
clause builder that bypasses `filters.build()` — it MUST be
extended to accept an `aux: AuxParams | None` arg and apply the
inning clause itself when set + when the underlying SQL has an
innings JOIN. Same hand-rolled pattern applied to
`reference.py::_reference_clauses` (already takes a series_type
arg via the same shape; inning rides through the same way). Both
helpers are listed in the "trace every consumer" check in §12.2.

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

`tournaments.py::_build_filter_clauses` and
`reference.py::_reference_clauses` don't have an innings join.
Inning narrowing is meaningless on /tournaments and /seasons
dropdowns. These bypass `filters.build()` entirely; no change
needed. Ditto `reference.py::list_teams` and `search_players`.

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
`_apply_*_per_innings` (the divisor is innings_count_in_inning_X
which the league-side aggregator computes from the same scope).

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

### 7.1 Bowler-perspective labelling

A bowler "in the 1st innings" was bowling against the team batting
first. Conventional cricket parlance "X bowled first" typically
means "X's team was on the field FIRST" — i.e. opposition batted
first — i.e. innings_number=0.

But that's exactly the opposite of what some readers might assume.
And for fielders the same confusion compounds — "Pakistan fielded
first" means Pakistan's fielders were active during innings 1 (when
Pakistan's opposition batted first).

**Convention to write into `internal_docs/design-decisions.md`
before shipping:**

> Inning labels are framed by the MATCH'S innings_number even on
> bowling and fielding pages: "1st innings" = innings_number=0
> regardless of which side of the ball the page focuses on. So
> "Bumrah, 1st innings" = Bumrah's deliveries when the opposition
> was batting first. "Pakistan fielding, 2nd innings" = Pakistan's
> fielding credits during innings_number=1. NEVER use "bowling
> first" / "fielded first" as labels — those phrases mean the
> OPPOSITE of what a casual reader assumes.

The frontend toggle pill says "1st innings" / "2nd innings" on
every page. No "bowling first" anywhere in the UI.

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

### 7.3 Single-discipline pages (single-column reading)

Player Batting page with inning=0: "Babar in 1st innings" =
his batting in matches where his team batted first. Direct.

Player Bowling page with inning=0: "Bumrah in 1st innings" = his
bowling when opposition batted first. The bowler-perspective gloss
in §7.1 takes care of the conceptual flip; the label "1st innings"
stays.

Player Fielding page with inning=0: "Jadeja's catches in 1st
innings" = catches taken when opposition was batting first. Same
logic.

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

Time-pinned to closed-window anchors — copy-paste of
`test_chip_direction_invariant.py`'s scope list works as the seed.

Expected runtime: under 5s (N scopes × ~K teams × M metrics — each
aggregate is one SQL).

### 10.2 Regression — NEW URLs

Add to `tests/regression/teams/urls.txt`,
`tests/regression/batting/urls.txt`,
`tests/regression/bowling/urls.txt`,
`tests/regression/fielding/urls.txt`,
`tests/regression/scope-averages/urls.txt`:

```
NEW team_batting_summary_rcb_inn0  /api/v1/teams/Royal%20Challengers%20Bengaluru/batting/summary?gender=male&team_type=club&season_from=2025&season_to=2025&inning=0
NEW team_batting_summary_rcb_inn1  /api/v1/teams/.../batting/summary?...&inning=1
NEW team_batting_by_inning_rcb     /api/v1/teams/.../batting/by-inning?gender=male&team_type=club&season_from=2025&season_to=2025
... (mirror for bowling, fielding, partnerships, player batting/bowling/fielding, scope averages)
```

Plus 1-2 REG entries with `&inning=0|1` to lock in the partition
behaviour against future shape changes.

The existing `&inning`-absent REG URLs MUST stay byte-identical
post-Commit-1 (the clause is gated on `aux.inning is not None`, so
no inning param ⇒ no clause ⇒ same SQL).

### 10.3 DOM tests

`tests/integration/dom/cross_cutting_inning_split.sh` (NEW):

- Anchor: `/teams?team=RCB&tab=Batting&season_from=2025&season_to=2025`.
- Toggle through "All / 1st / 2nd". Assert the headline run rate
  changes; assert match-count: 1st + 2nd = overall.
- Repeat on `/teams?...&tab=Compare` with two slots overriding
  `compare1_inning=0` and `compare2_inning=1`. Assert chip
  alignment math `chip.scope_avg == avg.displayed` for the
  inning-overriden slots — same invariant as
  `cross_cutting_slot_override_chip_align.sh`.

Per-page DOM tests (`teams_batting_*.sh`, `players_single_*.sh`,
etc.) gain new anchors with `&inning=0|1`.

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

7 commits, in order:

1. **Backend `inning` filter primitive.** `AuxParams.inning`,
   `FilterBarParams.build()` clause, `is_precomputed_scope`
   rejection. Sanity test
   `tests/sanity/test_inning_split_partition.py` ships in this
   commit. No frontend change yet — every endpoint accepts
   `?inning=0|1` and returns the partitioned aggregate.
2. **Backend `/by-inning` band endpoints.** New aggregators
   mirroring `/by-phase` for batting, bowling, fielding,
   partnerships team-side and the corresponding scope/averages
   mirrors. Player-side by-inning is the existing `/by-innings`
   endpoint pattern? No — `/by-innings` (with the trailing s)
   already exists on player batting/bowling and lists individual
   innings rows; per-innings-NUMBER aggregate is a different beast.
   New endpoints: `/api/v1/batters/{p}/by-inning-no` (etc.) — name
   is awkward; settle on `/by-inning-half` or just only add team-
   side bands. **Decision before commit 2:** team-side band
   endpoints only; player pages rely on the toggle (commit 4).
3. **Frontend slot-grammar + Compare tab override.**
   `OVERRIDABLE_SLOT_KEYS` adds `inning`; `SlotScopeEditor`
   "Innings" row; `ColumnScopeStrip` "Inning:" segment;
   `chipAlignmentFor` (no-op if §6.5 holds). DOM canary
   `cross_cutting_slot_override_chip_align.sh` extended with one
   inning anchor.
4. **Frontend toggle on player pages.** `InningToggle.tsx`
   mounted on `Batting.tsx`, `Bowling.tsx`, `Fielding.tsx`. URL
   param `inning` flips the headline.
5. **Frontend toggle on team tabs (no bands yet).** `InningToggle`
   mounted on Team Batting/Bowling/Fielding/Partnerships tabs.
   Uses the same primitive.
6. **Frontend band rows on team tabs.** `InningBandsRow.tsx`
   reading `/by-inning` band endpoints. Three rows (Overall / 1st
   / 2nd) below the existing Phase bands.
7. **Tests + docs.** Regression URL adds, full DOM cross-cutting
   test, `internal_docs/design-decisions.md` bowler-labelling
   convention, `internal_docs/how-stats-calculated.md` partition
   semantic.

Estimated total effort: ~12-15h (mechanical filter + band code +
toggle UI + spec-mandated tests + design-decision doc).

Risk: **low**. Single new clause, one new aux field, four new
band endpoints. No architectural refactor. The slot-grammar piece
rides entirely on the override mechanism shipped 2026-04-29.

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

### 12.2 Trace every consumer of `aux=`

```bash
grep -rn "filters\.build\(" api/ | grep -v test
```

Every call site must pass `aux=aux` (or `aux=None`). Per the
shared-helper contract in CLAUDE.md, omitting it leaves `aux` as
a free variable — import-time silent, request-time 500. The
`inning` clause is gated on `aux.inning`, so any call site that
drops aux silently fails to narrow.

### 12.3 Decisions to make before commit 1

- **Player page band endpoint?** §11 commit 2 punts to "team-side
  only." Confirm that's right — alternative is to ship player-side
  bands too. Decision rationale: player pages already toggle the
  whole page via §6.1; band rows would duplicate the data the user
  is already looking at. Skip unless user asks.
- **Toggle pill default?** "All innings" (no narrowing) — matches
  the convention of every other narrowing field.
- **Chip baseline alignment for inning** — verify §6.5 (no new
  code needed) by running the broaden-direction DOM test with an
  inning override before claiming done.

### 12.4 Per-commit gate criteria

- **Commit 1 (backend filter primitive).** All existing REG URLs
  byte-identical. Sanity tests pass (chip invariant, slot
  alignment, NEW partition test). Per-endpoint smoke: curl with
  `&inning=0` and `&inning=1` returns expected partitioned counts.
- **Commit 2 (band endpoints).** /by-inning endpoints return the
  same partitioned aggregates as 2× /summary?inning=0|1. New
  regression URLs flagged as NEW.
- **Commit 3 (slot grammar).** chip invariant + slot-override
  alignment tests stay PASS. New DOM canary anchor passes.
- **Commit 4-5 (toggles).** Frontend tsc -b clean. UI verification
  via agent-browser per CLAUDE.md UI-verification rule — load each
  page with the toggle, exercise all three states, confirm the
  partition invariant holds at the rendered level (toggle to "1st"
  + "2nd" sums to "All"'s headline number).
- **Commit 6 (band rows).** Same UI verification on team tabs,
  bands aligned with the existing PhaseBandsRow visually.
- **Commit 7 (tests + docs).** All NEW regression URLs added; DOM
  cross-cutting test PASS; design-decisions.md + how-stats-
  calculated.md updated.

---

*Spec written 2026-04-29 after the slot-override-chip-alignment
rollout shipped. Builds directly on the slot-override grammar +
chip-baseline mechanism shipped that same day. Pick up at §11
commit 1.*
