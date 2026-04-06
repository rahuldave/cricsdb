# Local Development

How to run CricsDB on your laptop, edit code, and verify changes before
committing.

## Prerequisites

- **Python ≥ 3.13** managed via `uv`. If `uv` isn't installed:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`. `uv` will install
  the right Python automatically — you do not need to manage venvs.
- **Node ≥ 20** for the frontend dev server.
- **`cricket.db`** present at the repo root. If you don't have it,
  build it with `download_data.py` + `import_data.py` (see
  `data-pipeline.md`) — takes ~15 minutes.

## Two-terminal workflow

Local dev runs the backend and the frontend as separate processes.

### Terminal 1 — backend (FastAPI on port 8000)

```bash
uv run uvicorn api.app:app --reload --port 8000
```

- Run from the **repo root**, not from `api/`.
- `--reload` restarts uvicorn whenever a Python file changes.
- The API is at `http://localhost:8000/api/v1/...`. The deebase admin
  is at `http://localhost:8000/admin/`.
- If you get **"address already in use"**, an old uvicorn is still
  running:
  ```bash
  pkill -f "uvicorn api.app"
  ```
  then retry.

### Terminal 2 — frontend (Vite dev server on port 5173)

```bash
cd frontend && npm install      # first time only
cd frontend && npm run dev
```

- Vite proxies `/api/*` → `http://localhost:8000` (configured in
  `frontend/vite.config.ts`), so the React app calls the API as if it
  were same-origin. You do **not** need to enable CORS for local dev.
- Hot module reload is on by default — saved files refresh in the
  browser without losing component state.
- The app is at **http://localhost:5173**.

## Editing code

The repo is a single FastAPI service plus a Vite React app. The most
common edits:

| Want to... | Files to touch |
|---|---|
| Add an API endpoint | New router file in `api/routers/`, register in `api/routers/__init__.py` |
| Add a filter to existing endpoint | `api/filters.py` (FilterParams) |
| Add a new page | `frontend/src/pages/Foo.tsx`, route in `frontend/src/App.tsx`, nav link in `frontend/src/components/Layout.tsx` |
| Add an API client function | `frontend/src/api.ts` and corresponding types in `frontend/src/types.ts` |
| Change URL state on a page | Use `useUrlParam` / `useSetUrlParams` from `frontend/src/hooks/useUrlState.ts` (see `design-decisions.md` for the race-condition reason) |

## Verifying changes before committing

The dev server tolerates type errors that the production build does not.
Run a one-off type-check + production build before committing UI changes:

```bash
cd frontend && npm run build
```

This runs `tsc -b && vite build` and writes to `frontend/dist/`. If it
fails, the issue will likely also break the deploy.

For backend code, a quick sanity check:

```bash
uv run python -c "import api.app; print('ok')"
```

This catches import-time errors (missing imports, syntax errors,
router registration mistakes).

## Hitting the API directly

Useful while iterating on a router:

```bash
# In a third terminal, with the backend running:
curl -sS "http://localhost:8000/api/v1/matches?limit=2" | python3 -m json.tool
curl -sS "http://localhost:8000/api/v1/matches/6025/scorecard" | python3 -m json.tool
```

`api.app` also serves the OpenAPI docs at `http://localhost:8000/docs`
which is handy for browsing endpoints and trying them in the browser.

## Database access

`cricket.db` is a SQLite file. You can poke at it with any SQLite
client, or with deebase from a Python REPL:

```python
import asyncio
from deebase import Database

async def main():
    db = Database('sqlite+aiosqlite:///cricket.db')
    rows = await db.q("SELECT COUNT(*) as c FROM match WHERE event_name = :ev",
                      {"ev": "Indian Premier League"})
    print(rows[0]["c"])

asyncio.run(main())
```

Always use `:param` bind syntax with `db.q()` — never f-string into the
SQL. See `CLAUDE.md` for the deebase patch context.

## See also

- `data-pipeline.md` — building and updating `cricket.db` from cricsheet
- `frontend-build-pipeline.md` — Vite/Tailwind/TypeScript build details
- `design-decisions.md` — why certain things are the way they are
- `deploying.md` — pushing to plash
- `../SPEC.md` — full API + page specification
- `../CLAUDE.md` — quick reference for design decisions and known issues
