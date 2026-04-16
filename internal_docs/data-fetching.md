# Data Fetching, Loading and Error UI

How the frontend talks to the API, surfaces in-flight state, and reports
failures. This is the canonical pattern across all pages — when adding a
new page or fetch, follow this.

## The three primitives

### `hooks/useFetch.ts`

```ts
const { data, loading, error, refetch } = useFetch<T>(fn, deps)
```

- `fn` is an async function returning `T` (usually one of the
  `frontend/src/api.ts` helpers).
- `deps` is the dependency array: the fetch re-runs when any value
  changes, like `useEffect`.
- Returns:
  - **`data: T | null`** — the latest successfully resolved value, or
    `null` before the first success.
  - **`loading: boolean`** — `true` while a request is in flight.
    Starts `true` on mount.
  - **`error: string | null`** — error message from the last failed
    attempt, or `null` on success/in-progress.
  - **`refetch: () => void`** — re-runs the fetch immediately. Used
    by `<ErrorBanner />`'s retry button.

**Stale-fetch protection.** `useFetch` keeps a call-id ref. When you
fire a new request, only that request's resolution is allowed to update
state — older calls that resolve later are silently dropped. This
prevents the Matches list from flickering between filters when you
type fast, and prevents the scorecard from flashing the wrong match
when you click through quickly.

### `components/Spinner.tsx`

```tsx
<Spinner />                                     // medium, no label
<Spinner label="Loading scorecard…" size="lg" />
```

Sizes are `sm`, `md` (default), `lg`. The label is optional and
accessibility-friendly (`role="status"`).

### `components/ErrorBanner.tsx`

```tsx
<ErrorBanner
  message={`Could not load matches: ${error}`}
  onRetry={refetch}
/>
```

Red alert card with bold "Something went wrong" header, the message
underneath, and an optional Retry button on the right.

## Page-level pattern

Most pages have a primary fetch that drives the page header (e.g.
batter summary, team summary, scorecard). Pattern:

```tsx
const { data, loading, error, refetch } = useFetch(
  () => playerId ? getBatterSummary(playerId, filters) : Promise.resolve(null),
  [playerId, filters.gender, filters.team_type, /* ...rest of filters */],
)

return (
  <div>
    <PlayerSearch role="batter" onSelect={...} />

    {!playerId && <div className="text-center text-gray-400 py-16">Search for a batter to view stats</div>}

    {playerId && loading && <Spinner label="Loading batter…" size="lg" />}

    {playerId && error && (
      <ErrorBanner
        message={`Could not load batter: ${error}`}
        onRetry={refetch}
      />
    )}

    {playerId && data && !loading && (
      <>
        {/* page header + tabs */}
      </>
    )}
  </div>
)
```

The four states are mutually exclusive: **no input** → empty state,
**loading** → spinner, **error** → banner with retry, **success** →
content.

## Gated fetches (the most important idiom)

Pages with tabs (Batting, Bowling, Teams) shouldn't make all tab
fetches at mount — only the visible tab needs network work. But
`useFetch` always calls its `fn` on every dep change. The solution:
gate inside `fn` and return `Promise.resolve(null)` when not needed:

```ts
const seasonFetch = useFetch<{ by_season: SeasonStats[] } | null>(
  () => playerId && activeTab === 'By Season'
    ? getBatterBySeason(playerId, filters)
    : Promise.resolve(null),
  [...filterDeps, activeTab],
)
const seasonData = seasonFetch.data?.by_season ?? []
```

When you switch tabs, the gated fetch re-runs because `activeTab`
changed. The newly-active tab fires its real network call; the
previously-active tab's fetch resolves to `null` and clears.

`activeTab` **must** be in the deps array. Without it, switching tabs
won't re-trigger.

The explicit `<T | null>` annotation is required because TypeScript
can't infer it from the conditional return.

## Per-tab `<TabState>` helper

On big pages (Batting, Bowling) with many tabs, the loading/error
boilerplate inside each tab body is repetitive. Extract a tiny local
helper at the top of the file:

```tsx
import { useFetch, type FetchState } from '../hooks/useFetch'

function TabState({ fetch }: { fetch: FetchState<unknown> }) {
  if (fetch.loading) return <Spinner label="Loading…" />
  if (fetch.error) return <ErrorBanner message={fetch.error} onRetry={fetch.refetch} />
  return null
}
```

Then in each tab body:

```tsx
{activeTab === 'By Season' && (
  <>
    <TabState fetch={seasonFetch as FetchState<unknown>} />
    {!seasonFetch.loading && !seasonFetch.error && seasonData.length > 0 && (
      <BarChart .../>
    )}
  </>
)}
```

The `as FetchState<unknown>` cast is needed because each fetch has its
own concrete data type. Keep the helper local to the page rather than
exporting a shared one — it's three lines and the cast hides the
specific type, which is fine for a presentation-only component.

## When NOT to use `useFetch`

**Debounced inputs.** `PlayerSearch` and the team-search dropdown on
the Teams page run a debounced query while the user types. They have
their own `setTimeout` + cleanup logic that doesn't fit `useFetch`'s
"deps change → fetch" model. For these, keep the raw `useEffect` +
`try/catch` and surface errors inline:

```tsx
const [error, setError] = useState<string | null>(null)

// inside the debounce:
try {
  const data = await searchPlayers(query, role)
  setResults(data.players)
} catch (err) {
  setError(err instanceof Error ? err.message : 'Search failed')
}
```

Then render an inline error row in the dropdown.

**Mount-time fetches with non-blocking failure.** `FilterBar`'s
`getTournaments` and `getSeasons` populate dropdowns at mount. A
failure there is rare and shouldn't paint a big red banner across the
top of every page. Pattern:

```tsx
const [error, setError] = useState(false)
useEffect(() => {
  getTournaments()
    .then(d => { setTournaments(d.tournaments); setError(false) })
    .catch(err => {
      console.warn('Failed to load tournaments:', err)
      setError(true)
    })
}, [])
```

Then disable the dropdown and put a `⚠ Tournaments failed to load`
placeholder in the empty option. Quiet enough not to be annoying,
loud enough that the user sees the filter is broken.

## Where loading/error sit relative to the data

A consistent rule across pages: the loading/error state is rendered
**in place of** the content it replaces, never above unrelated content.

- **Page-level fetch** (drives the whole page) → spinner/banner sits
  where the content would have appeared, so the search input and nav
  remain reachable.
- **Tab-level fetch** → spinner/banner sits inside the tab card, so
  the tab strip and page header stay visible. The user can switch
  tabs without losing context even if one tab is broken.
- **List-table fetch** (Matches list) → spinner sits **inside** the
  table body as a single full-width row, so the column headers stay
  in place while loading. The error banner sits **above** the table
  because making it a `<tr>` is fiddly.

## Reference: which pages use which pattern

| Page | Primary fetch | Tab fetches | Notes |
|---|---|---|---|
| Home | `getMatches({ limit: 5 })` | — | Spinner + banner inside the recent-matches block |
| Matches (list) | `getMatches(filters)` | — | Loading row inside table; error banner above |
| MatchScorecard | `getMatchScorecard(id)` | — | Page-level large spinner; charts and innings only render once data arrives |
| Teams | `getTeamSummary` | by-season, opponents, vs-opponent, results | Per-tab spinners; opponent dropdown shows ⚠ inline if its fetch fails |
| Batting | `getBatterSummary` | 7 tabs | `<TabState>` helper |
| Bowling | `getBowlerSummary` | 6 tabs | `<TabState>` helper |
| Head to Head | `getHeadToHead(b, bw, filters)` | — | Empty state until both players selected; spinner once both chosen |
| PlayerSearch | _(debounced)_ | — | Inline red error row in dropdown |
| FilterBar | `getTournaments`, `getSeasons` | — | Quiet: console.warn + disabled dropdown with ⚠ placeholder |

## Adding a new fetch

Checklist when wiring up a new endpoint to a page:

1. Add the API helper to `frontend/src/api.ts` and the response type to
   `frontend/src/types.ts`.
2. In the page, call `useFetch` with an explicit `<T | null>` type
   parameter and a gate that returns `Promise.resolve(null)` when the
   fetch shouldn't run yet (missing player_id, wrong active tab,
   missing required input).
3. Put **every** value the gate or `fn` reads into the deps array.
   Forgetting `activeTab` is the most common bug.
4. Render `<Spinner />` when `loading`, `<ErrorBanner onRetry={refetch} />`
   when `error`, and the actual content only when `data && !loading &&
   !error`.
5. Pick the right physical location for the spinner/banner per the
   rules in "Where loading/error sit" above.

## See also

- `local-development.md` — running the frontend dev server
- `frontend-build-pipeline.md` — Vite + Tailwind + TypeScript build
- `design-decisions.md` — other non-obvious choices
- `../CLAUDE.md` — full Future Enhancements list
