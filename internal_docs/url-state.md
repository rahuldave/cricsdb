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
| `components/tournaments/TournamentDossier.tsx` | Same invalid `series_type` auto-reset. |

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
