# Frontend Build Pipeline: Vite + React + TypeScript + Tailwind

## How the pieces fit together

```
                 Development                              Production
                 ===========                              ==========

index.html ──→ Vite Dev Server ──→ Browser            index.html ──→ vite build ──→ dist/
    │              (port 5173)         ↑                   │                          ├── index.html
    │                  │               │                   │                          ├── assets/
    │           Hot Module Replace     │                   │                          │   ├── index-xxxxx.js
    │                  │               │                   │                          │   └── index-xxxxx.css
    ↓                  ↓               │                   ↓                          │
src/main.tsx    Transforms TSX → JS    │            src/main.tsx                      │
    │           Processes CSS          │                                              │
    ↓           Proxies /api → :8000   │                                              ↓
src/App.tsx ──→ React Router ──────────┘                                    FastAPI serves these
```

## The entry point chain

### 1. `frontend/index.html` — the real entry point

Unlike Create React App (which hides `index.html`), Vite treats `index.html` as the entry point. This file is what the browser loads first:

```html
<div id="root"></div>
<script type="module" src="/src/main.tsx"></script>
```

The key line is the `<script>` tag pointing to `src/main.tsx`. In development, Vite serves this file directly (transforming TSX on the fly). In production, `vite build` bundles everything referenced from this entry point into `dist/assets/`.

### 2. `src/main.tsx` — React bootstrap

```tsx
import { createRoot } from 'react-dom/client'
import './index.css'    // ← this is where Tailwind enters
import App from './App'

createRoot(document.getElementById('root')!).render(<App />)
```

This mounts the React component tree onto the `<div id="root">` from `index.html`. The `import './index.css'` is crucial — it's how CSS (including Tailwind) gets into the build.

### 3. `src/App.tsx` — React Router

Sets up client-side routing. When you navigate to `/batting`, no server request happens — React Router swaps the component in the browser.

## Vite: what it does

Vite is a build tool that replaces Webpack. It does two things:

### Development: `npm run dev`

Starts a dev server on port 5173. When you edit a `.tsx` file:
1. Vite detects the change
2. Transforms the TSX → JS using esbuild (very fast, ~1ms)
3. Sends the updated module to the browser via WebSocket
4. React re-renders only the changed component (Hot Module Replacement)

You never wait for a full rebuild. Each file is transformed independently.

**API proxy:** The Vite config includes:
```ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
  },
}
```
This means `fetch('/api/v1/seasons')` from the browser goes to Vite (port 5173), which forwards it to FastAPI (port 8000). This avoids CORS issues in development.

### Production: `npm run build`

The build command is `tsc -b && vite build`:

1. **`tsc -b`** — TypeScript compiler checks all types. Does NOT emit JS (the config has `noEmit: true`). This is purely a type-checking step. If there are type errors, the build fails here.

2. **`vite build`** — Bundles everything into `dist/`:
   - Traces the dependency graph starting from `index.html` → `main.tsx` → all imports
   - Transforms TSX → JS using Rolldown (Vite 8's bundler)
   - Processes CSS (including Tailwind's `@import "tailwindcss"`)
   - Tree-shakes unused code
   - Minifies JS and CSS
   - Adds content hashes to filenames (e.g., `index-Dqj1CgqG.js`) for cache busting
   - Outputs to `dist/`

The `dist/` directory is a static site — just HTML, JS, and CSS files. No Node.js needed to serve it.

## Tailwind CSS v4

Tailwind v4 is fundamentally different from v3:

- **No `tailwind.config.js`** — configuration is done in CSS via `@theme`
- **No PostCSS** — uses the `@tailwindcss/vite` plugin instead
- **No `@tailwind` directives** — just `@import "tailwindcss"` in CSS

### How it works

In `src/index.css`:
```css
@import "tailwindcss";
```

The `@tailwindcss/vite` plugin in `vite.config.ts` intercepts this import:
1. Scans all `.tsx` files for class names (e.g., `className="text-gray-500 px-4"`)
2. Generates only the CSS for classes actually used
3. Injects the CSS into the bundle

In development, this happens on every file change (incrementally). In production, it happens once during build.

### How Tailwind classes become CSS

When you write:
```tsx
<div className="rounded-lg border border-gray-200 bg-white p-4 text-center shadow-sm">
```

Tailwind generates:
```css
.rounded-lg { border-radius: 0.5rem; }
.border { border-width: 1px; }
.border-gray-200 { border-color: rgb(229 231 235); }
.bg-white { background-color: rgb(255 255 255); }
.p-4 { padding: 1rem; }
.text-center { text-align: center; }
.shadow-sm { box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05); }
```

Only classes used in your source files are included. Unused classes are never generated.

## TypeScript configuration

The project uses TypeScript for type safety. The config is split across three files:

- **`tsconfig.json`** — root config, references the other two
- **`tsconfig.app.json`** — config for app source code (`src/`)
  - `target: "ES2023"` — output modern JS
  - `jsx: "react-jsx"` — transforms JSX using React 17+ automatic runtime (no need to `import React`)
  - `noEmit: true` — TypeScript only checks types, Vite handles the actual compilation
  - `strict: true` — enables all strict type checks
  - `moduleResolution: "bundler"` — lets TypeScript understand Vite's import resolution
- **`tsconfig.node.json`** — config for build tooling (vite.config.ts itself)

### Why TypeScript doesn't emit

This is a common confusion. In a Vite project, TypeScript serves two roles:
1. **Type checker** — `tsc -b` validates types at build time
2. **IDE support** — provides autocomplete, error highlighting in your editor

The actual TSX → JS transformation is done by Vite/esbuild/Rolldown, which is much faster than `tsc` but doesn't check types. So the build runs both: `tsc -b` (slow, checks types) then `vite build` (fast, produces output).

## File flow in production

```
Browser request: GET /batting

  → FastAPI (port 5001)
    → No matching API route (/api/v1/...)
    → No matching static file
    → SPA fallback: serves dist/index.html
      → Browser loads index.html
        → Fetches dist/assets/index-xxxxx.js (the bundled React app)
        → Fetches dist/assets/index-xxxxx.css (the bundled Tailwind CSS)
        → React Router sees path "/batting", renders <Batting> component
        → Component calls fetch("/api/v1/players?q=...") 
          → Same FastAPI server, matches API route
          → Returns JSON
        → React renders the stats
```

## Key files

| File | Purpose |
|------|---------|
| `frontend/index.html` | Entry point — loaded by browser, references main.tsx |
| `frontend/src/main.tsx` | React bootstrap — mounts App, imports CSS |
| `frontend/src/index.css` | `@import "tailwindcss"` — entry for all CSS |
| `frontend/src/App.tsx` | React Router — maps URLs to page components |
| `frontend/vite.config.ts` | Vite config — plugins (React, Tailwind), dev proxy |
| `frontend/tsconfig.app.json` | TypeScript settings for app code |
| `frontend/package.json` | Dependencies and build scripts |
| `frontend/dist/` | Build output (gitignored) — static files served in production |

## Commands

```bash
cd frontend

npm run dev      # Start dev server (port 5173, proxies /api → :8000)
npm run build    # Type-check + bundle → dist/
npm run preview  # Serve dist/ locally to test production build
npm run lint     # Run ESLint
```
