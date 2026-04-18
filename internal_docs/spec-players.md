# Spec: Players tab (enhancement R)

Status: **shipped 2026-04-16.** This doc captures the design as
frozen at implementation; any deviations from v2 (role-classifier
thresholds + compact compare layout) are called out inline. For the
shipped files + entry points see `internal_docs/codebase-tour.md`
under `components/players/`. Integration tests at
`tests/integration/players.sh` + `players_hygiene.sh`.

## Motivation

Five role-specific entry points today (Series, Teams, Batting,
Bowling, Fielding, H2H, Matches) and no **person-focused** home. A
user looking up "V Kohli" wants the full picture of the player at a
glance, with the current FilterBar scope applied, and a jumping-off
point into the discipline pages for the deep dive.

Second motivation: **comparison**. "Kohli vs Markram all-time,"
"Smith vs Root in the 2024 T20 WC," "Bumrah vs Rabada in IPL" — none
has a home. `/head-to-head?mode=player` is a specific batter-vs-bowler
matchup, not a career comparison.

This spec adds a `/players` tab that houses both (single-player
overview, N-way comparison), and restructures the nav so the
discipline pages sit *under* Players as sub-routes.

## Nav restructure

**Today (7 top-level items):**

```
Series | Teams | Batting | Bowling | Fielding | Head to Head | Matches
```

**After (5 top-level items):**

```
Series | Teams | Players ▾ | Head to Head | Matches
                    │
                    ├── Batting
                    ├── Bowling
                    └── Fielding
```

The three discipline entries collapse into a Players group. Players
remains clickable as its own destination (`/players`); hovering (or
tapping on mobile) reveals Batting / Bowling / Fielding as the deep-
dive sub-routes.

### Desktop behaviour

- `Players` renders as a top-level `<Link>` with a small caret (▾)
  appended.
- Hover opens a dropdown below it listing Batting / Bowling / Fielding.
  Each item is a `<Link>` to the existing route (`/batting` etc.).
- Clicking Players itself goes to `/players` — hover is separate from
  activation.
- Active-state indicator (the existing underline/oxblood line) marks
  the top-level item when ANY of the four routes (`/players`,
  `/batting`, `/bowling`, `/fielding`) is the current route. The
  dropdown sub-items highlight the specific one.

### Mobile behaviour

- Top nav: Series, Teams, `Players ▾`, Head to Head, Matches as
  horizontal chips (existing `.wisden-nav-link` styling).
- Tapping Players navigates to `/players` (same as desktop click).
- A sub-row appears beneath Players in smaller typography, indented:
  `Batting · Bowling · Fielding`. Visible on all sub-routes and on
  `/players` itself; hidden on unrelated routes. This keeps the three
  sub-sections discoverable without an extra tap.

### Existing discipline routes unchanged

`/batting`, `/bowling`, `/fielding` keep their current behaviour —
only the nav presentation changes. External bookmarks survive. The
subnav just frames them as siblings under Players.

### Implementation notes

- `frontend/src/components/Layout.tsx` — split `navItems` into top-
  level and nested. Add a `children?: NavItem[]` field.
- New `<NavDropdown>` or augment existing NavLink with a
  `renderChildren` prop.
- `.wisden-nav-dropdown` CSS: absolute-positioned menu below the
  parent link, appearing on `:hover` + `:focus-within`. Use `ul`
  semantics for accessibility.
- Mobile sub-row: render the children list as an inline-wrapped
  secondary nav when the current route is in the group.

## Page layout

### Single-player mode

```
┌─────────────────────────────────────────────────────────────────┐
│ V Kohli  🇮🇳 men's                                              │  ← h2 + FlagBadge + gender label
│ Specialist batter · 375 matches                                 │  ← role + identity line
│ [Scoped to India vs Australia]  CLEAR                           │  ← ScopeIndicator (existing)
│                                                                 │
│ BATTING                                 → Open Batting page     │
│ ┌───────┬───────┬───────┬───────┬───────┬───────┐               │
│ │ Runs  │ Avg   │ SR    │ 100s  │ 50s   │ HS    │               │
│ │12,755 │ 42.38 │137.24 │   8   │  38   │  122* │               │
│ └───────┴───────┴───────┴───────┴───────┴───────┘               │
│                                                                 │
│ BOWLING                                 → Open Bowling page     │
│ ┌───────┬───────┬───────┬───────┐                               │
│ │ Wkts  │ Avg   │ Econ  │ SR    │                               │
│ │   4   │ 112.5 │  9.47 │ 71.2  │                               │
│ └───────┴───────┴───────┴───────┘                               │
│                                                                 │
│ FIELDING                                → Open Fielding page    │
│ ┌───────┬───────┬───────┬───────┐                               │
│ │Catches│ Stumps│  ROs  │ Total │                               │
│ │  124  │   0   │  17   │  141  │                               │
│ └───────┴───────┴───────┴───────┘                               │
│                                                                 │
│ KEEPING                       → Open Fielding > Keeping tab     │  ← hidden unless innings_kept >= 3
└─────────────────────────────────────────────────────────────────┘
```

### Section order (fixed)

**Batting → Bowling → Fielding → Keeping.**

Rationale (from your observation): in practice a player has either
{batting + fielding}, {bowling + fielding}, or all three. Fielding is
the near-universal row. Keeping is a rare addendum — keep it last so
specialist-keeper pages still read naturally.

### Stat rows (per discipline)

Use `.wisden-statrow` — same component as existing player pages. One
row per discipline with these columns:

| Discipline | Columns |
|---|---|
| Batting | Runs · Avg · SR · 100s · 50s · HS |
| Bowling | Wkts · Avg · Econ · SR (bowling SR = balls/wicket) |
| Fielding | Catches · Stumpings · Run-outs · Total dismissals |
| Keeping | Innings kept · Stumpings · Catches · Byes · Byes/inn |

Each section header is a one-liner with the section label on the
left and a `→ Open <role> page` link on the right. The link carries
`player` + every active FilterBar param through to the deep-dive
page.

### Identity line

One italic serif line under the player name:

```
Specialist batter · 375 matches
```

"Specialist batter" is the **primary-role label** — answered below.
"375 matches" is total matches in the current scope. These two facts
orient the user before the stat rows render.

### Primary-role label — definition

Heuristic computed from the four summary responses, scoped by the
active FilterBar:

```
batted  = BattingSummary.balls_faced  >= 100
bowled  = BowlingSummary.balls        >=  60
kept    = KeepingSummary.innings_kept >=   3

if kept AND batted:      "keeper-batter"
elif kept:               "wicketkeeper"
elif batted AND bowled:  "all-rounder"
elif batted:             "specialist batter"
elif bowled:             "specialist bowler"
elif fielded:            "fielder"             # rare fallback
else:                    "no matches in scope" # zero data
```

Threshold choices mirror the existing leaderboard thresholds. The
label is NOT cached — recomputed per fetch, so narrowing the scope to
"IPL 2024" can truthfully flip Kohli from "specialist batter" to
"all-rounder" if he bowled an over there.

The label is descriptive, not definitive — "for this scope, here's
what this player looked like." Small enough to be ignored if
uninteresting; valuable for orientation at a glance.

### Hidden-when-empty (single-player mode)

If a discipline has zero in-scope data (e.g. Kohli's keeping row,
Bumrah's batting row when scoped to pre-debut seasons), **hide the
whole section** including its header. The stack compresses.

Thresholds for "has data":

- Batting: `innings > 0`
- Bowling: `balls > 0`
- Fielding: any of `catches + stumpings + run_outs > 0`
- Keeping: `innings_kept > 0`

If ALL four are empty, show a "No matches in scope" placeholder
under the header (the ScopeIndicator CLEAR button is the escape
hatch).

### Comparison mode — greyed placeholders for alignment

In N-way comparison, aligned sections matter more than tight vertical
space. Rule: **for each discipline, if ANY column has data, show the
discipline band on ALL columns**. Columns without data render a dim
placeholder at the same height:

```
BOWLING                          BOWLING                       BOWLING
┌───────┬───────┬───────┬───────┐  ─ no bowling in scope ─       ┌───────┬───...
│ Wkts  │ Avg   │ Econ  │ SR    │                               │ Wkts  │ Avg
│  315  │ 19.73 │  7.89 │ 14.9  │                               │   4   │ 112.5
└───────┴───────┴───────┴───────┘                               └───────┴───...
  Bumrah                           Kohli                          de Villiers
```

Styling: `.wisden-empty-compare { color: var(--ink-faint); font-style:
italic; padding: … matching statrow height }`. Keeps the eye locked.

If NO column in a discipline has data (e.g. comparing two specialist
batters, neither bowls), hide the whole band — don't render four rows
of placeholders.

## URL shape

```
/players                                             landing
/players?player=X                                    single player
/players?player=X&compare=Y                          2-way
/players?player=X&compare=Y,Z                        3-way  (cap here)
/players?player=X&gender=male&tournament=IPL&…       filtered
/players?player=X&compare=Y&filter_team=India&filter_opponent=Australia
                                                     shared rivalry scope
```

All FilterBar params apply globally to every player in the group —
no per-player scopes. `compare` is a comma-separated list, max 2
additional IDs (3 total).

`player` is primary; removing it returns to the landing. Removing a
`compare` ID drops that column.

### Why `compare=Y,Z` over `player2=Y&player3=Z`

Clean for arbitrary arity. Extending 2-way to 3-way doesn't change
the URL shape. Matches how enhancement M handled rivalry-tile URLs.

## Auto-gender on pick

When a user selects a player (via PlayerSearch dropdown OR a landing
tile OR a curated comparison tile), and the URL doesn't yet have
`gender=`, set it atomically to that player's gender.

- Single-player pick: `setUrlParams({ player: id, gender: p.gender })`.
- Tile click: same.
- Comparison-mode "add" pick with mixed genders: omit the `gender`
  param so both render. Edge case — very rare (Kohli vs Mandhana)
  and the user is implicitly saying "show both."

On cold-load with `?player=X` and no gender, the self-correcting
effect from `pages/Batting.tsx:73` already handles this (replace,
not push, since it's auto-correction). Port that pattern.

## Default-to-all-time

No `useDefaultSeasonWindow` on this page. The user opened a specific
player; they want the full career view first. If they want to scope
down, the FilterBar's `season_from` / `season_to` are right there.
Same policy as `/teams` scoped pages — deep-dive, not leaderboard.

## Landing

Two sections on the landing page. Both are FilterBar-sensitive (so
`gender=female` shows women's tiles only).

### Popular profiles

Curated tiles. Start list (swap any time):

**Men**: V Kohli · JJ Bumrah · SPD Smith · RG Sharma · JC Buttler ·
HM Amla · Babar Azam · KS Williamson · JO Holder

**Women**: SG Mandhana · EA Perry · HC Knight · BL Mooney ·
Meg Lanning · Deepti Sharma · AJ Healy · Sophie Devine ·
H Matthews

Each tile: name + flag(s) + a one-line stat strip (e.g. "375 m ·
12,755 runs · 42.38 avg"). Click → `/players?player=X&gender=g`
(gender auto-applied).

### Popular comparisons

Curated pairs. Start list:

**Men**: V Kohli × AK Markram · SPD Smith × JE Root · JJ Bumrah ×
Rabada · Stokes × Jadeja · Buttler × Gilchrist (retired-era curio)

**Women**: Mandhana × Mooney · Perry × Knight · Healy × Mandhana

Each tile: both names + both flags + "compare". Click →
`/players?player=A&compare=B&gender=g`.

If the FilterBar has a gender set, show only matching-gender tiles.
If not, show both.

## Comparison-mode UX

### Picker shape

Above the columns, one or two additional picker inputs. Layout:

```
[Primary player: V Kohli           ]
[Compare with:  AK Markram          ]   ← appears after primary picked
[+ Add another comparison…        ]   ← button below second, opens third
[  Another player:                  ]   ← third only when requested
```

- First box (Primary player) is always visible. Mirrors existing
  `PlayerSearch`.
- Second box (Compare with) appears as soon as primary is set. Also a
  `PlayerSearch`.
- Third box: hidden by default. A `+ Add another comparison` button
  underneath the second box reveals it — prevents visual clutter for
  the common 2-way case.

Each box gets a small ✕ on its column header that removes that
player's ID from the URL. Clearing the primary returns to landing.

### Highlighted differences (nice-to-have)

Where a stat differs between columns, the winning value is rendered
bolder. E.g. "Avg 42.38" vs "Avg 38.14" → the 42.38 gets `font-
weight: 600`. Applies only to stats with an obvious "higher is
better" (runs, wickets, average, SR for batting, fielding totals)
or "lower is better" (bowling economy, bowling SR). Skip for
neutral stats.

Cap at single-best highlighting: 3-way with three different values
would make "everyone loses" visually. Bold only the max (or min).

Not blocking for ship; do it after the alignment and row logic are
stable.

## Homepage integration

The home page currently has player name links like "V Kohli" that go
to `/batting?player=…`. After this ships, primary player links go to
`/players?player=…` (the overview), and a tiny role-letter suffix
carries the deep-dive links:

```
V Kohli  b · bw · f
```

- `V Kohli` — links to `/players?player=X`. Primary name.
- `b` — small subscript italic, links to `/batting?player=X`.
- `bw` — links to `/bowling?player=X`.
- `f` — links to `/fielding?player=X`.

Only render letters for disciplines where the player has data (same
thresholds as the player-page section visibility). Separator is
interpunct (`·`).

Mirror the `PlayerLink` two-link idiom — the name is the "who,"
letters are the "which discipline view."

Styling: reuse `.comp-link`, override with smaller font size and
italic colour for the letters (match the existing "· at X ›"
context-link style).

### Where this applies

- `frontend/src/pages/Home.tsx` — every PlayerLink-style entry.
- Not a universal replacement of `PlayerLink` yet — the existing
  two-link pattern (name + "· at X ›") on team/series dossier tables
  stays, because the context link is meaningful ("this player AT
  that team"). On the home page the letters serve the same purpose
  with less prose.

Future: an augmented PlayerLink that takes an optional `deepDiveLetters`
prop and renders them inline. Not needed for MVP — Home is the only
current home-page-player-links surface.

## Backend

No new endpoints. The four existing summary endpoints already
return everything needed:

- `GET /api/v1/batters/{id}/summary`
- `GET /api/v1/bowlers/{id}/summary`
- `GET /api/v1/fielders/{id}/summary`
- `GET /api/v1/fielders/{id}/keeping/summary`

The page fetches all four in parallel. `useFetch` handles stale
responses. For N-way comparison it's `N × 4` concurrent fetches —
negligible (each sub-100ms).

Rejected: composing on the backend. Reasons:

- Duplicates SQL with no perf win (browser does N × 4 in parallel
  already).
- Less composable for the N-way compare case.
- Adds a layer that can drift from its inputs.

### New API helper

In `frontend/src/api.ts`:

```ts
export const getPlayerProfile = async (id: string, filters?: F) => {
  const [bat, bowl, field, keep] = await Promise.all([
    getBatterSummary(id, filters).catch(() => null),
    getBowlerSummary(id, filters).catch(() => null),
    getFielderSummary(id, filters).catch(() => null),
    getFielderKeepingSummary(id, filters).catch(() => null),
  ])
  return { batting: bat, bowling: bowl, fielding: field, keeping: keep }
}
```

`.catch(() => null)` — a 404 on `/bowlers/{id}/summary` for a
specialist batter must not blow up the whole profile fetch.

### New type

In `frontend/src/types.ts`:

```ts
export interface PlayerProfile {
  batting:  BattingSummary | null
  bowling:  BowlingSummary | null
  fielding: FieldingSummary | null
  keeping:  KeepingSummary | null
}
```

All four sub-types already exist.

## Frontend — files to create / modify

### Create

```
frontend/src/pages/Players.tsx                — mode switch (landing | single | compare)
frontend/src/components/players/
  PlayerProfile.tsx                            — single-player layout
  PlayerCompareColumn.tsx                      — one column of the compare view
  PlayerCompareGrid.tsx                        — the N-column CSS grid
  PlayerSummaryRow.tsx                         — one discipline band
  PlayersLanding.tsx                           — landing (tiles + curated compares)
  CuratedLists.ts                              — exported PROFILE_MEN, PROFILE_WOMEN,
                                                 COMPARE_MEN, COMPARE_WOMEN arrays
```

### Modify

```
frontend/src/App.tsx                          — add <Route path="/players">
frontend/src/components/Layout.tsx            — nav restructure (Players + sub-nav)
frontend/src/api.ts                           — add getPlayerProfile
frontend/src/types.ts                         — add PlayerProfile
frontend/src/pages/Home.tsx                   — switch PlayerLinks to /players + b/bw/f suffix
frontend/src/index.css                        — sub-nav styles, compare-column grid,
                                                .wisden-empty-compare placeholder,
                                                subscript role-letter link style
```

## FilterBar integration

### Subsequent fetches when filters change

Standard `filterDeps` array:

```tsx
const filterDeps = [
  playerId, compareIds.join(','),
  filters.gender, filters.team_type, filters.tournament,
  filters.season_from, filters.season_to,
  filters.filter_team, filters.filter_opponent,
]
```

One `useFetch<PlayerProfile>` call per player in the group, each
gated on their own ID being present, all sharing the common
`filterDeps`.

### Scope pill

`ScopeIndicator` renders when `filter_team` || `filter_opponent` is
set, same as existing pages. CLEAR strips all narrowing — existing
contract.

### Auto-narrow

The three FilterBar auto-narrow effects (tournament → gender/type,
team → gender/type, team pair → tournament) all keep working. They
don't depend on page identity.

## Empty states

| Situation | Behaviour |
|---|---|
| No player selected | Landing (popular profiles + popular compares) |
| `?player=X` but player doesn't exist | "Player not found" banner, back link to `/players` |
| Valid player, no data in scope | Identity line reads "no matches in scope"; all four discipline sections hide; ScopeIndicator shows so CLEAR is reachable |
| Comparison mode, one column has zero-in-scope | That column shows identity line with "no matches"; other columns show normally |

## Accessibility

- Each section header is an `<h3>` so screen readers can jump between
  disciplines.
- The nav dropdown is keyboard-navigable (focus + arrow-down).
- Mobile sub-nav is a flat `<ul>` with clear visual hierarchy.
- Compare mode: each column announces player name as a `<h2>` at the
  top; screen readers can navigate column-by-column.

## Testing

Before the final commit:

### Unit-level (type check + manual)

- Primary-role classification function — exercise all six branches
  with fabricated summary objects.
- `getPlayerProfile` handles 404 on any individual endpoint (mock
  with a failed promise).

### Integration (agent-browser)

Extend `tests/integration/cross_cutting_url_state.sh` (or `players.sh`
if the test is Players-specific):

- Test: `/players` → pick Kohli → add compare Markram → back walks
  compare then primary.
- Test: click a landing compare-tile → URL sets `player` + `compare`
  + `gender` atomically (one history entry, not three).

Extend `tests/integration/cross_cutting_mount_unmount.sh`:

- Test: rapid filter change while 8 fetches in flight (two players ×
  four disciplines). No React warnings, no page errors.
- Test: remove a compare column via ✕ while its fetch was in flight.
  No errors.

### Manual browser checks

- `/players?player=<kohli_id>` — batting / bowling / fielding all
  visible. Keeping hidden.
- Add `filter_team=India&filter_opponent=Pakistan` — scope pill
  renders, stats narrow, bowling hides (no Kohli Ind-vs-Pak
  bowling).
- Add `compare=<markram_id>` — 2-column grid. Bowling greyed on one
  side, live on other.
- `gender=female` — empties both men. Both columns show "no matches."
- Mobile width — sub-nav visible under Players header; nav readable.
- Desktop hover on Players — dropdown reveals Batting / Bowling /
  Fielding.
- From home page, click "V Kohli" → `/players?player=…`. Click the
  small `b` suffix → `/batting?player=…`.

## Docs pass (when shipped)

- `docs/api.md` — no new endpoints. Add a section noting that
  `/players` composes client-side via the four existing summary
  endpoints.
- `frontend/src/content/user-help.md` — new "Players" section
  describing the tab, comparison mode, the nav sub-grouping of
  Batting/Bowling/Fielding under Players, and when to use this vs
  the discipline pages (overview vs deep dive).
- `internal_docs/codebase-tour.md` — new `pages/Players.tsx`,
  `components/players/`, API helper, CuratedLists constants.
- `CLAUDE.md` "Landing pages" section — add Players bullet.
- `internal_docs/enhancements-roadmap.md` — mark R as done, promote
  Venues S from drafting.
- This spec file moves from draft to shipped.

## Effort estimate

| Chunk | Effort |
|---|---|
| `getPlayerProfile` + type + curated lists | 30 min |
| Single-player layout + role classification + hidden-when-empty | 3–4 h |
| Comparison grid + greyed placeholder + 3-way | 3–4 h |
| Landing (tiles + curated compares) + FilterBar-sensitivity | 2 h |
| Nav restructure (dropdown + mobile sub-nav) + CSS | 3 h |
| Home page PlayerLink migration + role-letter suffix | 1 h |
| Docs pass + integration-test extensions | 1–2 h |

Total: **~2 working days**. Near-zero backend, heavy reuse of
component vocabulary. Main risk is the nav restructure — it changes a
user-visible layout touched by every page. Keep the diff reviewable;
break nav + sub-nav into its own commit if needed.

## Open questions

These remained after v1 and need to stay explicit for the final-
spec discussion:

1. **Identity-line quality** — is "Specialist batter · 375 matches"
   useful or noise? Drop-option: just show "375 matches" and let the
   user infer role from which sections render. I lean keep — it's
   the one-line summary of "who is this?"

2. **Comparison mode — highlight winner (bold)?** Nice-to-have,
   defer. Needs care for neutral-direction stats (fours, sixes —
   higher-is-better? matches played — neither).

3. **Sub-nav hover timing on desktop** — open on hover instantly, or
   with a 200ms delay to avoid jitter? Convention varies; keep
   instant unless it feels flickery in practice.

4. **Mobile sub-nav persistence** — always visible on player-adjacent
   routes, or collapsed behind a disclosure widget? Proposal:
   always visible on `/players`, `/batting`, `/bowling`, `/fielding`
   (ensures Batting/Bowling/Fielding are one-tap reachable from
   each other). Elsewhere, hidden.

5. **Role-letter suffix on PlayerLink (team/series dossier
   tables)** — extend the existing two-link pattern to also include
   the letters? E.g. `V Kohli · at Mumbai Indians ›` becomes
   `V Kohli · at Mumbai Indians ›  b · bw · f`. More info-dense but
   cluttered; I'd skip for dossier tables and keep only on Home.

6. **Primary-role for specialist fielders** — "fielder" is the
   fallback label when someone has no meaningful batting/bowling/
   keeping but has catches. This should be near-zero people
   (substitute fielders who never played a full match). Accept the
   fallback; if it ever reads badly, switch to "No primary role."

7. **Gender-mixed compare** — when both players differ in gender and
   the URL has no `gender`, we omit the gender param so both render.
   BUT: the FilterBar's existing auto-correct effect will try to
   narrow gender if one of the scoped tournaments has a single
   gender. Verify that auto-correct doesn't kick in and clobber the
   cross-gender comparison. Fallback: track a flag that the mode is
   intentionally cross-gender and disable the auto-correct in that
   specific case.

## Deviations from v2 in the shipped implementation

Two real departures from the draft, both captured in
`components/players/roleUtils.ts` and `components/players/PlayerSummaryRow.tsx`:

1. **Role classifier thresholds raised above raw ball counts.** v2
   said `batted := balls_faced >= 100`, `bowled := balls >= 60`.
   Those gates misclassify two obvious cases:
   - Bumrah: 101 balls faced across 36 innings (≈2.8 balls/inn,
     avg < 3). Classic #10 tail-ender, not a batter.
   - Kohli: 403 balls bowled across 388 career matches. A part-
     timer called in to break a partnership, not a bowler.

   Shipped rule:
   ```
   batted = innings >= 5
          AND balls_faced / innings >= 5
          AND average >= 10
   bowled = balls >= 60
          AND balls / fielding.matches >= 3
   ```
   `fielding.matches` is the TRUE career-match count (everyone fields
   every match, so `fielding.matches` is the denominator we want).
   `bowling.matches` only counts matches where the bowler actually
   sent down a delivery — using that as the denominator flatters the
   occasional dabbler.

2. **Compare columns switch to a compact label/value layout, not
   StatCards.** v2 described stat rows matching the single-player
   layout. In practice, a 6-cell batting StatCard row in a 1/3-width
   compare column overflows — 12,755 / 42.38 / 134.18 etc. collide.
   Shipped: compare columns render the same stats as a
   `.wisden-player-compact` definition list (label left, value
   right, bordered between rows). Single-player keeps the StatCard
   row. The `compact` prop on `PlayerSummaryRow` is the switch.

Also — the "hidden-when-empty" thresholds for the row-visibility
gates use the weaker `balls_faced > 0` / `balls > 0` rather than the
role-classifier numbers above. This is deliberate: if the player
ever faced a ball or bowled one, we render the band with their
actual (possibly tiny) numbers; the role LABEL uses the stronger
gates to describe who they _are_ in scope.
