# React, Vite, and this codebase — for ES6-fluent readers

This doc assumes you're comfortable with modern JavaScript (ES6+
classes, arrow functions, destructuring, modules, Promises/async) and
haven't worked extensively with React. It's not a generic React
tutorial — plenty of those exist. It's specifically about **how this
codebase uses React** and the machinery underneath it, so that reading
any file under `frontend/src/` makes sense by the end.

We use React 19, TypeScript, Tailwind CSS v4, and Vite 8 as the build
tool. React Router 7 handles client-side routing. Semiotic v3 is the
charting library. Chart wrappers live under
`frontend/src/components/charts/`; data fetching wrappers live under
`frontend/src/hooks/` and `frontend/src/api.ts`.

## 1. What React is, from an ES6 perspective

React is a library for **generating HTML from data**. You write
functions that take some data (props + state) and return a
description of what the DOM should look like for that data. React
reconciles that description against the current DOM and applies the
minimum set of changes.

Mental model shift from plain DOM:

```js
// Plain DOM: you mutate.
const el = document.querySelector('#count')
el.textContent = newValue

// React: you re-render.
// The "count" function is called with new data; React figures out
// that the <span> has a different text node and patches it.
```

You never write `document.querySelector` or `el.textContent` in
application code. You change the data, React re-runs your function,
and the library computes the DOM diff.

### The 90-second mental model

1. Your app is a tree of **components**. Each component is a plain
   JavaScript function.
2. A component returns **JSX** — an XML-like expression that compiles
   into a tree of JS objects React calls "elements." JSX is sugar; it
   is not a template language, it's a function call syntax.
3. When a component's **state** or **props** change, React calls the
   component function again. Functions are cheap to call; the diffing
   makes sure the DOM only gets the minimal update.
4. Side-effects (data fetches, subscriptions, timers) live in
   `useEffect` hooks, which run AFTER the DOM update.
5. State that survives across re-renders lives in `useState` (value)
   or `useRef` (mutable box). Local variables in the function body
   are fresh every render.
6. React Router reads the URL and picks which top-level component to
   render. We treat the URL as the source of per-page state — filters,
   tabs, selected player — so refresh / share / back-button all
   "just work."

Everything below is a filled-in version of those six points.

## 2. How Vite makes it run

Vite is the build tool. Two modes matter:

### Dev mode (`npm run dev`)

`frontend/index.html` has one script tag:

```html
<script type="module" src="/src/main.tsx"></script>
```

That's the entry. When Vite's dev server serves this page, it
intercepts imports and compiles each `.tsx` / `.ts` file **on demand**
as your browser asks for it. No bundle — just native ES modules
streamed one at a time. Compiling means:

- Strip TypeScript types.
- Transform JSX into `React.createElement(…)` calls (via the
  `@vitejs/plugin-react` plugin configured in
  `frontend/vite.config.ts`).
- Rewrite imports to absolute paths the browser can fetch.

This is fast because the browser does the module graph walk itself;
Vite just needs to transform each file once. That's why pages
appear within a second of edit.

**Hot Module Replacement (HMR).** When you save a file, Vite re-
compiles it, pushes the new module over a websocket, and the React
plugin swaps the component in-place without reloading the page.
Component state is preserved across the swap where possible. If you
edit a file and your filter state vanishes, something (usually
non-component state, or a `key=` changing) forced a remount.

Vite also proxies `/api/*` to the FastAPI backend running on port
8000 (see `vite.config.ts`), so the frontend's `fetch('/api/v1/…')`
calls go to your local backend without CORS gymnastics.

### Prod build (`npm run build`)

`tsc -b` first — TypeScript compiles the whole project and checks
types. If this fails, the build fails. No types hit runtime; they're
purely a compile-time check.

Then `vite build` actually bundles:

- Every `import` in the graph is walked from `src/main.tsx`.
- Code is minified.
- The output is a few `.js`, `.css`, and asset files under
  `frontend/dist/`, with content-hashed filenames
  (`index-Dp5T9zrn.js`) so browsers can cache aggressively.
- The compiled `index.html` replaces the single dev script tag with
  links to the hashed bundles.

The deploy step (`bash deploy.sh`) ships `dist/` to plash. The
FastAPI server mounts it as a static directory with an SPA fallback
so any unknown path (e.g. `/series?tournament=IPL`) serves
`index.html`, letting the React Router pick up from there.

### Strict mode

`src/main.tsx` wraps the app in `<StrictMode>`:

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

In dev, Strict Mode **intentionally double-invokes** your components
and effects to flush out bugs: non-idempotent setup, accidental
shared state, missing cleanup. If you see an effect's console.log
fire twice in dev but once in prod, that's not a bug — that's Strict
Mode doing its job. If your effect misbehaves under double-invocation
(e.g. posts data twice), THAT is a bug, and you should fix it.

## 3. JSX — what the compiler does

```tsx
<h2 className="wisden-page-title">{summary.name}</h2>
```

compiles roughly to:

```js
React.createElement('h2', { className: 'wisden-page-title' }, summary.name)
```

Two gotchas for ES6 readers:

- **`className`, not `class`** (class is an ES6 reserved word).
- **`{expression}`** embeds JS inside JSX. `{` starts a JS escape;
  `}` closes it. Inside, you can have any expression — function
  calls, arithmetic, conditional expressions — but not statements.
  That's why you see ternaries everywhere instead of if-statements in
  JSX: `{loading ? <Spinner /> : <Data />}`.

Components are just functions whose names start with a capital
letter (JSX tagnames that start lowercase are treated as HTML
elements, uppercase as component references):

```tsx
function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="wisden-statcard">
      <div className="wisden-statlabel">{label}</div>
      <div className="wisden-statvalue">{value}</div>
    </div>
  )
}

// Used elsewhere:
<StatCard label="Matches" value={189} />
```

The `{ label, value }` pattern is destructuring the props object.
The props shape is just the function's first-argument type.

### Lists and keys

When you map an array to JSX children, each element needs a stable
`key` prop so React can match list items across renders:

```tsx
{summary.nationalities.map(n => (
  <FlagBadge key={`${n.team}-${n.gender}`} team={n.team} gender={n.gender} />
))}
```

Don't use array indices as keys if the list can reorder or items can
be inserted / removed. Use a natural stable identifier. Missing keys
cause subtle bugs: input boxes lose focus, animation state leaks,
`useEffect` cleanup fires at the wrong time. Writing a decent key is
the difference between "it seems fine" and "it's correct."

## 4. Components are pure functions of (props, state)

A component is a function. It must be pure in the sense that two
calls with the same props + state must produce the same JSX. That's
why you can't do this:

```tsx
function Bad({ id }) {
  const data = await fetch(`/api/thing/${id}`).then(r => r.json())  // NO
  return <div>{data.name}</div>
}
```

No `await`, no side-effects, no DOM manipulation, no `Math.random()`
for visible state. All of those go in hooks.

The return value is what React calls a **render output**. React
re-calls the function whenever its inputs change; the function
should return the same output each time for the same inputs.

## 5. Hooks

A **hook** is a function whose name starts with `use`. Hooks are the
official mechanism for attaching behaviour to a component across
re-renders. The two foundational ones:

### `useState`

```tsx
import { useState } from 'react'

function Counter() {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(count + 1)}>{count}</button>
}
```

Each call to `useState(initial)` gives you a `[value, setValue]`
tuple. `setValue(n)` schedules a re-render with the new value. The
next invocation of `Counter` sees `count === n`.

**Rule 1: Hooks must be called at the top level of a component, in
the same order, every render.** No loops, no conditions. React
identifies hooks by call order, not by name. The ESLint plugin
`react-hooks/rules-of-hooks` enforces this — listen to it.

Our pages have ten or fifteen hook calls in a row at the top. That's
fine; it's the flat, non-conditional calling pattern that matters.
See `frontend/src/pages/Fielding.tsx` for a typical layout.

### `useEffect`

The only safe place to run code with side-effects (fetches,
subscriptions, DOM APIs, timers). It runs AFTER React has committed
the render to the DOM.

```tsx
useEffect(() => {
  document.title = `${name} — Fielding`
}, [name])
```

The second argument is a **dependency array**. The effect re-runs
only when one of those values changes between renders (using
`Object.is` for comparison).

- `[]` — run once on mount, never again.
- No array — run after every render (almost never what you want).
- `[a, b]` — run on mount and whenever `a` or `b` changes.

A common bug: omitting a dependency the effect closes over. Stale
closures then see stale values from a previous render. ESLint's
`react-hooks/exhaustive-deps` rule catches most of these. We
sometimes suppress it deliberately (e.g. in `hooks/useFetch.ts` —
see comment there) when the dep we want isn't quite what the lint
computes, but each suppression needs a written reason.

#### Cleanup

An effect can return a cleanup function. It runs either:

- Before the effect re-runs (because a dep changed), or
- When the component unmounts.

```tsx
useEffect(() => {
  const handler = (e: MouseEvent) => { /* … */ }
  document.addEventListener('mousedown', handler)
  return () => document.removeEventListener('mousedown', handler)
}, [])
```

**Forgetting cleanup is the most common source of leaks** in React.
Listeners stay on `document` after a page-change remount. Intervals
keep firing. Subscriptions keep pushing updates into components that
no longer exist. The `PlayerSearch` and `TeamSearch` components
illustrate the pattern; the chart wrappers cleanup their
`ResizeObserver` in `useContainerWidth`.

#### Effects are NOT a general "run this when X changes" tool

Beginners reach for `useEffect` to derive state. Don't.

```tsx
// BAD — pure computation doesn't need an effect.
const [doubled, setDoubled] = useState(0)
useEffect(() => { setDoubled(count * 2) }, [count])

// GOOD — just compute it inline.
const doubled = count * 2
```

Effects are for **reaching outside React** (DOM, network, timers,
other libraries) or for synchronising React state with something
React doesn't own.

### `useRef`

A mutable box whose `.current` persists across renders but doesn't
trigger re-renders when changed.

```tsx
const timerRef = useRef<number | undefined>(undefined)
// …
clearTimeout(timerRef.current)
timerRef.current = setTimeout(fn, 300)
```

Two use cases:

1. Holding a mutable value (a debounce timer, a "was this already
   applied?" flag) that you don't want to re-render the component
   for.
2. Attaching to a DOM node: `const ref = useRef<HTMLDivElement>(null)`
   then `<div ref={ref}>` — after render, `ref.current` is the DOM
   node. `hooks/useContainerWidth.ts` uses this to set up a
   `ResizeObserver` on the actual `<div>`.

`useRef` is the escape hatch when `useState` would cause wasted
re-renders.

## 6. Custom hooks

A function whose name starts with `use` that calls other hooks is a
custom hook. It's just an abstraction technique — lets you reuse
stateful logic across components. We have several.

### `useFetch` (`hooks/useFetch.ts`)

Wraps the common "fetch data based on deps, expose loading / error /
data, cancel stale requests" pattern.

```tsx
const summaryFetch = useFetch<FieldingSummary | null>(
  () => playerId ? getFielderSummary(playerId, filters) : Promise.resolve(null),
  [playerId, filters.gender, filters.team_type, /* … */],
)
const summary = summaryFetch.data  // null while loading or on error
```

Two things to notice:

1. The **callback is not a dependency**. The dep array is what
   decides when to re-fetch; the callback is allowed to close over
   whatever it needs.
2. Stale responses are dropped. If the user changes the filter
   mid-fetch, the old promise's `.then` still resolves, but
   `useFetch` checks a ref'd call-id and ignores it. Without this,
   rapid filter changes would race-condition and show the wrong
   data.

**This is why the dep array matters.** If you forget to include
`filter_team` in deps (we made this mistake — see
`internal_docs/regression-testing-api.md`), a change to `filter_team` won't
retrigger the fetch — the component re-renders with the new filter
in its closure, but the old data is still displayed because no
fetch was scheduled.

### `useUrlParam` and `useSetUrlParams` (`hooks/useUrlState.ts`)

Our URL-as-state layer. `useUrlParam('tab')` returns `[value, setValue]`
just like `useState`, but the state is a URL search parameter. Changes
are reflected in the address bar, survive refresh, and are shareable.

See `internal_docs/url-state.md` for the push-vs-replace discipline (most
setter calls push a history entry so the back button walks filter
state; programmatic auto-corrections pass `{ replace: true }`).

### `useDocumentTitle`, `useDefaultSeasonWindow`, `useContainerWidth`

Each follows the same "wrap a common side-effect pattern" shape. Look
at them when you want a template for extracting your own.

## 7. React Router — URL as the state

`App.tsx` defines the top-level routes:

```tsx
<BrowserRouter>
  <Routes>
    <Route element={<Layout />}>
      <Route path="/series" element={<Tournaments />} />
      <Route path="/teams" element={<Teams />} />
      {/* … */}
    </Route>
  </Routes>
</BrowserRouter>
```

- `<BrowserRouter>` subscribes to `window.history` and tells React
  which route matches.
- `<Layout>` wraps every route with the nav + FilterBar; `<Outlet/>`
  inside `Layout` is where the matched route's content renders.
- Navigating is done by rendering `<Link to="/foo?bar=1">` (which is
  a real anchor tag that React Router intercepts) or calling
  `navigate('/foo')` from the `useNavigate()` hook.

### URL search params as state

React Router exposes `useSearchParams()` which returns
`[URLSearchParams, setSearchParams]`. Our two wrappers live in
`hooks/useUrlState.ts`:

```tsx
// Read ?tab= from the URL, update it atomically.
const [activeTab, setActiveTab] = useUrlParam('tab', 'By Season')
setActiveTab('By Phase')                       // push history entry
setActiveTab('By Phase', { replace: true })    // replace in place
```

Why URL state instead of `useState`?

- Deep links work (copy URL → share → lands in the exact view).
- Back button works (the browser already has a history stack; use it).
- Refresh preserves state (no LocalStorage hacks).
- Cross-tab state isolation (two tabs = two URLs = two states).

The cost is that you need to be disciplined about what goes in the
URL (primary filters, tabs, entity IDs) vs transient component state
(hover, animation progress, search-box open/closed). The rule of
thumb: **if a user would ever want to share, bookmark, or refresh
back to this state, put it in the URL.**

### SPA fallback

When a user opens `https://t20.rahuldave.com/series?tournament=IPL`
directly, the server receives a request for `/series?tournament=IPL`
— which matches no static file. The backend's SPA fallback (registered
in `api/app.py` in the lifespan handler, AFTER routers) returns
`index.html` for any non-API path, letting React Router take over in
the browser. If you add a new route and it 404s on refresh, the
fallback registration order is probably wrong.

## 8. Our codebase conventions

```
frontend/src/
  main.tsx            — entry; mounts <App/> into #root
  App.tsx             — <BrowserRouter> + route table
  api.ts              — fetchApi<T>() helper + every API client fn
  types.ts            — TS interfaces for every API response
  index.css           — Wisden editorial styles (cream, oxblood, …)
  pages/              — one file per top-level route
  components/         — shared UI: Layout, FilterBar, PlayerSearch, …
  components/charts/  — Semiotic wrappers (BarChart, LineChart, …)
  hooks/              — useFetch, useUrlState, useContainerWidth, …
  content/            — markdown rendered by the /help pages
```

Everything is a pure function. No classes. All state lives in hooks.
All side-effects live in `useEffect` or custom hooks built on it.

### Data flow

1. Page loads → React Router picks the route → the page component
   mounts.
2. The page reads URL state via `useFilters()` / `useUrlParam`.
3. It fires `useFetch` calls with those filter values as deps.
4. The fetch resolves → state updates → the page re-renders with
   data.
5. User interaction changes URL state → React Router updates the URL
   → the page re-renders with new filters → `useFetch` deps change →
   new fetch → new data.

Every page in this codebase follows that loop.

## 9. TypeScript in our React

The code is TS, not JS, which means:

- Props shapes are compile-time-checked. If you pass
  `<FlagBadge gender="unknown">` and `gender` is typed `"male" |
  "female"`, the build fails.
- API response shapes live in `types.ts`. `api.ts` uses generics
  like `fetchApi<T>` so callers know what they're getting.
- Inside components, types usually flow from the props, the hooks,
  and the API responses — we rarely need to annotate local
  variables.

If a TS error looks nonsensical ("Type 'Element' is not assignable
to type 'string | number'"), it's usually about a function signature
mismatch — the DataTable's `format` callback is typed to return
`string | number`, and if you hand it back JSX you need to cast with
`as unknown as string`. You'll see this pattern repeated.

## 10. Common pitfalls we've hit

### `setSearchParams` race condition

Two `useUrlParam` setters called in the same event handler race —
the second call's `prev` doesn't see the first call's write. Fix:
use `useSetUrlParams()` to batch. See
`hooks/useUrlState.ts` and the memory note about this.

### Missing deps in `filterDeps`

We had `filter_team` and `filter_opponent` missing from the
`filterDeps` array on Batting/Bowling/Fielding for a while. URL
changes to those params didn't retrigger fetches, so stale data sat
on the page until you navigated away. The fix was one line per file.

### Race-condition in async state setters

`PlayerSearch` sets state from a setTimeout+fetch chain. On unmount
the timer is cleared, but an already-dispatched fetch still fires
its `.then(setResults)` on an unmounted component. React 18+ tolerates
this silently but it's wasted work. Belt-and-suspenders: carry a
local `cancelled` flag in the effect cleanup.

### setState during render

Seen in the series-type auto-reset logic (now fixed; see
`internal_docs/url-state.md`). Calling a setter in the body of a component —
outside a handler, outside a `useEffect` — runs on every render. With
a URL setter that pushes history by default, every render would fire
a history entry. Always move that logic into a `useEffect`.

### Over-reactive effects

A `useEffect` with `[filters]` as a dep, where `filters` is a fresh
object each render, will fire every render. Destructure the fields
you actually depend on: `[filters.gender, filters.team_type]`.

### Component remounts vs re-renders

A re-render calls the same component function with new state/props;
hooks keep their values across re-renders of the same mount. A
**remount** throws away all hook state and starts fresh. Common
causes:

- Route change (navigating to a different `path`).
- `key={…}` changing on an element.
- Conditional rendering (`{enabled ? <Foo/> : null}`) collapsing
  and re-expanding.

If your local component state keeps vanishing, check whether the
component's being remounted — React DevTools helps.

## 11. Where to look next

- React's own "Thinking in React" doc:
  https://react.dev/learn/thinking-in-react — short, and worth
  reading once.
- Our `hooks/useFetch.ts` has a complete, self-documented example of
  a race-safe data-fetching hook.
- `hooks/useUrlState.ts` + `internal_docs/url-state.md` together explain the
  URL-as-state pattern we rely on.
- `pages/Fielding.tsx` is a representative page — pull it up while
  reading this doc and every idiom in sections 4–7 shows up.
- `vite.config.ts` is the 12-line build configuration; no surprises.

The fastest way to learn this codebase is to start a dev server
(`uv run uvicorn … --reload` + `cd frontend && npm run dev`), load
`/series`, and **make small edits**. HMR's feedback loop is the
whole point — break things, fix them, watch what actually changes.
