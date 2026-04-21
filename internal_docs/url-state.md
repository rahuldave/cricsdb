# URL state discipline

## Why this document exists

The URL is the source of truth for per-page state in CricsDB — player,
tab, filters, scope, highlight. Almost every interactive feature either
reads from or writes to the search-params via two hooks in
`frontend/src/hooks/useUrlState.ts`:

- `useUrlParam(key, default?)` — one key, `[value, setValue]` like
  `useState`.
- `useSetUrlParams()` — atomic multi-key writes.

The discipline is narrow but repeatedly violated without a written
rule: **user-initiated changes should push history; programmatic
auto-corrections should replace.** If we get this wrong in either
direction the back button breaks.

## The hook contract

```ts
const [value, setValue] = useUrlParam('gender')
setValue('male')                       // push — user picked it
setValue('male', { replace: true })    // replace — we corrected it for them

const setUrlParams = useSetUrlParams()
setUrlParams({ team_type: 'club' })                    // push
setUrlParams({ team_type: 'club' }, { replace: true }) // replace
```

Both setters take an optional second argument `{ replace?: boolean }`.
The default is `false` (push). Before 2026-04-16 the default was
`true`, which meant every click — filter, tab, button — stomped the
URL in place. Back button jumped over everything the user had done on
the page and landed on whatever page they came from. That was wrong.

## The rule

> Push when the user did something. Replace when we did something on
> their behalf.

The practical test: if the reader thinks "undoing that is something
I'd want the back button to do," it's push. If the reader thinks
"that's a detail that happened while the page was loading," it's
replace.

### Push (default)

- FilterBar dropdown changes (gender / team type / tournament / season).
- FilterBar button clicks (`all-time`, `latest`, `reset all`).
- Tab switches on any page (`setActiveTab(…)` via `useUrlParam('tab')`).
- Entity picks in search dropdowns (player, team).
- Suggestion-tile clicks (popular matchups, rivalry tiles).
- `ScopeIndicator`'s `CLEAR` button.
- Season pick in the Editions tab of the Series dossier.
- `PlayerLink` navigations — these are `<Link>` elements, so React
  Router handles the push for us.

### Replace

Any of these patterns qualifies:

1. **Deep-link auto-fill.** A user arrived with `?tournament=IPL`
   but no gender/team_type. FilterBar fills those in from the
   tournament's metadata.
2. **One-shot defaults.** `useDefaultSeasonWindow` seeds `season_from`/
   `season_to` with the last 3 seasons in scope the first time the
   landing loads.
3. **Self-correcting deep links.** Batting/Bowling/Fielding pages
   infer `gender` from the player's nationalities when the URL omits
   it.
4. **Invalid-state repair.** `series_type=bilateral` is no longer
   offered once the user picks `team_type=club`. The component resets
   it to `all`.
5. **URL-shape migration.** Legacy `?rivalry=A,B` → modern
   `?filter_team=A&filter_opponent=B`.

The common thread: the URL changes, but the user didn't *ask* for the
change. A history entry for it would read as a back-button hop to
nothing the user remembers doing.

## Anti-pattern: setState during render

React anti-pattern with a URL-state twist. This is broken:

```tsx
// INSIDE RENDER — will fire every render and (with push default) push
// a fresh history entry every time.
{enabled && (() => {
  const opts = ['all', 'bilateral', 'icc', 'club'].filter(…)
  if (seriesType && !opts.includes(seriesType)) {
    setSeriesType('')   // ← setState during render
  }
  return <div>…</div>
})()}
```

React's old default-to-replace masked this: setting the same URL twice
with `replace: true` collapses to one URL update, so the anti-pattern
was invisible. After the push flip, the same code would push a
history entry on every render it ran — potentially hundreds during
fast interactions.

The fix: move the correction into a `useEffect` with `replace: true`
so it fires once per state change, not once per render.

```tsx
// OUTSIDE RENDER — fires when the inputs change, once.
useEffect(() => {
  const isClub = filters.team_type === 'club'
  const valid = /* …check seriesType against opts… */
  if (!valid) setSeriesType('', { replace: true })
}, [seriesType, filters.team_type])
```

**If you're tempted to call a setter during render, stop.** The only
legitimate exception is the `useState(computeInitialState)` / the
early-return pattern in React's own docs; you're almost certainly not
in that case. Use `useEffect`.

## Audit: current `{ replace: true }` call-sites

These were the spots identified when the push default flipped. Any new
auto-correcting effect should extend this list.

| File | What it does |
|---|---|
| `hooks/useDefaultSeasonWindow.ts` | Seeds last-3-seasons default. |
| `components/FilterBar.tsx` (3 useEffects) | Auto-fill gender/team_type from tournament; auto-fill from team-scoped tournament list; auto-set tournament when the team pair collapses to one shared competition. |
| `pages/Batting.tsx`, `Bowling.tsx`, `Fielding.tsx` | `gender`-from-nationalities self-correcting deep link. |
| `pages/Tournaments.tsx` | Legacy `?rivalry=A,B` → modern params migration. |
| `pages/HeadToHead.tsx` | Invalid `series_type` auto-reset (now in a useEffect, was setState-during-render). |
| `components/tournaments/TournamentDossier.tsx` | Same invalid `series_type` auto-reset. Also the tab-switch URL↔session migration effect (strips non-current-tab picker params, restores current tab's pick from session) — see "Active-URL / dormant-session state" below. |

## Testing the back button

After any change to a setter call-site, or any change that adds a new
`useEffect` that writes URL state, manually verify:

1. Open `/fielding`, pick a player. URL: `/fielding?player=X`.
2. Change gender to Men. URL: `/fielding?player=X&gender=male`.
3. Change team_type to Club. URL: `/fielding?player=X&gender=male&team_type=club`.
4. Click Back. URL should become `/fielding?player=X&gender=male`
   (one step back, NOT all the way to `/fielding` or the home page).
5. Click Back again. URL: `/fielding?player=X`.
6. Click Back. URL: wherever you came from.

If any back click skips a step, something is replacing when it should
be pushing. If you see history entries you don't recognise (landing
you in a half-filled state you never created), something is pushing
when it should be replacing.

The `agent-browser` skill makes this easy to script; see the commit
that added this doc for the concrete command sequence used.

## FAQ

**Q: Why not push everything?**

Push-everything fills the back stack with near-duplicates. A user
typing a text filter that debounces would push a history entry per
keystroke. Auto-corrections that fire on mount would push a history
entry for the auto-correction. Every back click then feels random.

**Q: Why not replace everything?**

That's what we had. Back button was useless for anything
within-page. Users had to manually reverse every filter they set to
get back to the previous state.

**Q: What about `navigate()` vs `setUrlParams`?**

`navigate('/some/path')` is always push by default (React Router's
default). If you want a programmatic redirect that shouldn't live in
history, use `navigate(…, { replace: true })` — the same discipline.
Most of our navigation is `<Link>`-based, which is fine as push.

**Q: Where does highlight_batter / highlight_bowler fit?**

Those are set by clicking a date link on a player's innings list —
that's a `<Link>` navigation, so it pushes. Correct behaviour: user
clicked, we navigated, back should return them. No special handling
needed.

## Search inputs: typing buffer, not mirrored state

Search inputs (PlayerSearch, TeamSearch, and the inline search on
`/teams` and `/matches`) used to hold their input text in local
`useState(urlParam || '')`. That initializer runs exactly once on
mount. React SPA navigation — including the back button — doesn't
unmount the page, so the URL can change while the local copy stays
stuck, leaving the input full of stale text and the autocomplete
dropdown re-opening off-URL state. The old web model, where an `<a>`
is a real link that unmounts the document on click, does not apply
here: React Router's `<Link>` and any `setUrlParams` call go through
`history.pushState` without a browser navigation.

The working pattern is "derive from URL, buffer typing locally":

```tsx
const [typing, setTyping] = useState<string | null>(null)
const displayValue = typing ?? urlValue ?? ''

<input
  value={displayValue}
  onChange={e => setTyping(e.target.value)}
/>

// On pick:
onSelect(x)
setTyping(null)   // release input back to URL truth
```

- `typing === null` means "not editing" — input falls through to the
  URL-derived value. Back-nav changing the URL updates the input
  naturally, no sync-effect needed.
- `typing !== null` means the user is mid-keystroke — show what they
  typed, feed it to the dropdown fetch effect (effect deps on
  `typing`, early-returns when null).
- On pick, `setTyping(null)` drops the buffer; the input now reads
  from the URL, or empty if the site convention is "clear after pick"
  (PlayerSearch used on `/batting`, `/players`, etc., which echo the
  picked player in a page header instead).
- Shared search components accept a `value` prop (the URL-derived
  canonical string). `TeamSearch` in `/head-to-head` uses it so the
  picked team stays in the input across re-renders; `PlayerSearch`
  call sites that don't pass `value` reset after each pick.

If you find yourself writing a sync-`useEffect` to copy URL state
into a `useState`, you're re-creating the bug. The fix is to derive.

## Aux filters: `series_type` and how it flows

Most URL params are FilterBar fields — driven by the FilterBar UI,
listed in `FILTER_KEYS` (`components/scopeLinks.ts`), iterated by
`useFilters()` to populate the canonical filters object every page
consumes.

`series_type` is the lone exception (so far): it's a **page-local aux
filter**, set by the Series-tab pill but applied by every endpoint
that uses `FilterBarParams.build(aux=aux)`. It rides on URLs the way
any other filter does, but:

- It's NOT in `FILTER_KEYS`. Adding it would mean it rides through
  scope-link letter URLs for PlayerLink (which would change the
  `(e, t, s, b)` semantics) and through `useFilterDeps`. Neither is
  what we want — series_type is its own axis.
- It IS surfaced by `useFilters()` as a special case — the hook reads
  `params.get('series_type')` outside the `FILTER_KEYS` loop and adds
  it to the returned `FilterParams` object (typed with an optional
  `series_type?: string` field in `types.ts`). This is so consumers
  like `Teams.tsx`, `Batting.tsx`, etc. don't have to remember to
  read it themselves before calling `getTeamSummary(team, filters)`.
- `TeamLink` reads it directly via `useSearchParams` (alongside
  `useFilters`) because its container resolution logic is keyed on
  `series_type` (icc/club → keep tournament in URL; bilateral →
  drop). See `internal_docs/design-decisions.md` "TeamLink phrase
  model + container resolution from Series tab".
- The backend mirrors the split: `FilterBarParams` (8 fields) +
  `AuxParams` (currently `series_type`). Routers take both as
  `Depends()` and pass `aux` to `filters.build()` so the SQL gets the
  `series_type_clause` automatically. See same doc: "FilterBarParams +
  AuxParams: filter classification".

Future page-local filters (result_filter, close_match, toss_decision
from the roadmap) follow the same pattern: add to `AuxParams`,
add to `useFilters` as a special-case read (or generalise into an
`AUX_KEYS` registry once we have ≥2). Don't add to `FILTER_KEYS`.

## Active-URL / dormant-session state (the Series picker model)

The Series dossier's Batters/Bowlers/Fielders subtabs each own a
picker whose pick lives in `series_batter` / `series_bowler` /
`series_fielder`. Leaving all three in the URL at once would clutter
the share link with inactive-tab state. Dropping picks entirely on
tab-switch would lose them.

The "active-URL / dormant-session" model:

- **URL** carries only the current tab's pick. Shareable, deep-linkable,
  back-button walks each pick/clear/tab action.
- **`sessionStorage`** (keys `cricsdb:series_batter`, `…_bowler`,
  `…_fielder`) holds the dormant tabs' picks. Survives reload in the
  same tab (you refresh, tab-round-trip still has your picks).
  Dies when the tab closes — picks are session-scoped, not
  cross-session, so you don't get stale stuff from yesterday.

**Two mechanisms keep URL ↔ session in sync**, and the split maps
cleanly onto the push/replace rule:

1. **Session-aware setters** (`pickBatter`, `pickBowler`, `pickFielder`
   in `TournamentDossier.tsx`) — on a user pick or × clear, push the
   URL change AND mirror it to session in one shot. User action →
   push (like every other facet).
2. **Tab-switch migration effect** (`useEffect` keyed on `currentTab`)
   — on tab change, strip non-current-tab picks from URL (stashing
   to session first) and restore the current tab's pick from session
   if the URL lost it on a prior switch. Auto-correcting → replace,
   so back-walk doesn't get stuck in "URL cleanup" dead entries.

Back-button behaviour round-trips:

- User picks Kohli on Batters → `push` state A (`series_batter=X`).
- Clicks Bowlers tab → `push` state B (`tab=Bowlers&series_batter=X`)
  → effect `replace` to B' (`tab=Bowlers`, session has X).
- Picks Jadeja on Bowlers → `push` state C (`tab=Bowlers&series_bowler=Y`).
- Back → lands on B' (Bowlers empty). Back → A (Batters+Kohli). Back →
  initial. Every entry is a real user step; no dupes, no ghosts.

Deep-link self-correction: if someone opens a share URL like
`?tab=Fielders&series_batter=X`, the effect strips `series_batter`
(stashing to session) on first mount, so the Batters pick is still
there if the recipient clicks Batters — but the URL bar stays clean.

× clear removes both URL param AND session key (not "park for later"),
because × means "I'm done with this pick." Undo is via back button.
