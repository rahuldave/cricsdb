# Deploying to plash

CricsDB is hosted on [pla.sh](https://pla.sh/) at
**https://t20-cricket-db.pla.sh**. Deploys go through `deploy.sh`,
which stages a clean `build_plash/` directory and runs `plash_deploy`.

## TL;DR

```bash
bash deploy.sh           # code-only deploy (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db too (~435 MB, slow)
```

`plash_view` opens the live URL at the end either way.

## When to use `--first`

| You changed... | Command |
|---|---|
| Frontend (React/Tailwind) only | `bash deploy.sh` |
| Backend (FastAPI router/filter) only | `bash deploy.sh` |
| Both | `bash deploy.sh` |
| `cricket.db` (e.g. ran `update_recent.py`) | `bash deploy.sh --first` |
| First-ever deploy of a new plash app | `bash deploy.sh --first` |

The plain deploy leaves the `data/` directory on plash untouched, so
the previously-uploaded `cricket.db` keeps serving. The `--first` flag
ships a fresh copy of the local DB and passes `--force_data` to
`plash_deploy` so plash overwrites its persisted copy.

If in doubt: a code-only deploy is safe and takes ~10 seconds. A
`--first` deploy uploads 435 MB and takes a few minutes.

## What ships and what doesn't

`deploy.sh` builds `build_plash/` with **only** what plash needs to run
the app:

```
build_plash/
├── main.py              # plash entry point
├── requirements.txt     # python deps (deebase deps only — deebase is vendored)
├── deebase/             # vendored: plash runs Python 3.12, deebase needs 3.13+
├── api/                 # __init__, app, dependencies, filters, routers/*
├── models/              # __init__, tables
├── frontend/dist/       # vite build output
├── data/                # cricket.db (only present with --first)
└── .plash               # plash app identity (preserved across deploys)
```

**Things in the repo that do NOT ship to plash:**
- `import_data.py`, `download_data.py`, `update_recent.py` — data
  pipeline scripts run only on your laptop. plash isn't where you
  ingest cricket data; you do that locally and re-deploy with `--first`.
- `data/*.zip`, `data/*_json/` — the cricsheet source archives.
- `SPEC.md`, `CLAUDE.md`, `docs/` — documentation.
- `frontend/src/`, `frontend/node_modules/` — only the built `dist/`
  ships.
- Tests (none yet) and `.git/`.

If you find yourself wanting plash to run a script, the answer is
almost always "run it locally and redeploy" — see the GitHub Actions
discussion in the project history for why.

## The `.plash` identity file

`build_plash/.plash` records which plash app this directory belongs to.
`deploy.sh` saves it before `rm -rf "$BUILD_DIR"` and restores it after
staging, so a fresh deploy keeps publishing to the same URL. Don't
delete it manually unless you want a brand-new plash app.

## deebase is vendored

plash runs Python 3.12; deebase requires 3.13+. The deploy script
copies deebase out of your local `.venv` into `build_plash/deebase/`.
The hardcoded path is currently:

```bash
cp -r .venv/lib/python3.14/site-packages/deebase "$BUILD_DIR/deebase"
```

If you're using a different local Python (3.13, 3.15, etc.), update
that path in `deploy.sh`. `uv` puts the venv at `.venv/lib/pythonX.Y/`.

A consequence of vendoring: the deebase admin UI at `/admin/` does
**not** load on plash, because deebase's `admin` extras (Jinja
templates, etc.) aren't included in the vendored copy. The admin works
fine in local dev. This is in the Known Issues list.

## Troubleshooting

**Deploy succeeds but the live site shows an old version.**
plash caches aggressively at the CDN. Hard-refresh
(Cmd-Shift-R) the browser. If still stale, wait 1-2 minutes.

**`plash_deploy` errors with auth.**
plash credentials live outside this repo. Re-run whatever plash login
flow you used initially (`plash_login` or similar). Don't put tokens
in `deploy.sh` or commit them.

**`/admin/` 500s on plash.**
Expected (see deebase note above). The admin only works locally.

**Built frontend missing or stale.**
`deploy.sh` always runs `npm run build` first, so this shouldn't
happen — but if you copy `build_plash/` around manually, make sure
`frontend/dist/` was rebuilt.

## See also

- `local-development.md` — running the same code on your laptop
- `data-pipeline.md` — how to populate `cricket.db` before a `--first` deploy
- `../deploy.sh` — the actual script
