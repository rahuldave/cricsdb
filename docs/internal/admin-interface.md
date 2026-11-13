# Admin Interface

CricsDB ships with a deebase-provided admin interface at `/admin/`.
It's an auto-generated Django-style CRUD UI over every table in the
database. Useful for inspecting rows, debugging, and one-off edits.

## Status

| Environment | Works? | Notes |
|---|---|---|
| Local (Python 3.14, `uv run uvicorn …`) | Yes | Needs `jinja2` and `starlette<1.0.0` (both pinned in `pyproject.toml`). |
| Plash production | Yes after the fix committed with this doc | `deploy.sh` requirements now pin `starlette>=0.46.0,<1.0.0` for the same reason. Previously returned 500. |
| **Auth** | **HTTP Basic, fail-closed** | `/admin/*` requires `ADMIN_USERNAME` / `ADMIN_PASSWORD` from env — see "Authentication" below. Returns 503 if either is unset. |

## Tables exposed

All 10 tables in the schema get CRUD views automatically. The admin
dashboard at `/admin/` lists them with row counts:

| Path | Table | Typical use |
|---|---|---|
| `/admin/person/` | Person roster (17,851 rows) | Look up a player ID; rename aliases |
| `/admin/personname/` | Name aliases (7,351 rows) | Add a variant to improve search |
| `/admin/match/` | Matches (12,940 rows) | Edit tournament name, season, toss info |
| `/admin/matchdate/` | Match dates (12,959 rows) | One row per calendar day of a match |
| `/admin/matchplayer/` | XI rosters (285,525 rows) | Find who played in a specific match |
| `/admin/innings/` | Innings (25,886 rows) | Find a specific innings by match_id; inspect super_over |
| `/admin/delivery/` | Deliveries (2.95M rows) | Individual balls — rarely edited; used for debugging |
| `/admin/wicket/` | Wickets (160K rows) | Dismissal records |
| `/admin/fieldingcredit/` | Fielding credits (~118K rows) | Tier-1 fielding denormalization |
| `/admin/keeper_assignment/` (when Tier 2 ships) | Keeper per innings | Override misattributions |

Each table supports:

- **List** (`GET /admin/{table}/`) — paginated browse with filter params
- **View** (`GET /admin/{table}/{pk}`) — read-only detail
- **Create** (`GET/POST /admin/{table}/new`) — add a row
- **Edit** (`GET/POST /admin/{table}/{pk}/edit`) — modify any field, with FK dropdowns populated from parent tables
- **Delete** (`GET/POST /admin/{table}/{pk}/delete`) — with a confirmation page

## Finding a specific innings (worked example)

For the Tier 2 keeper-correction workflow we need `innings_id` for a
specific innings of a specific match. Two paths:

**Path A — from a scorecard URL.** The path `/matches/5975` maps to
`match.id = 5975`. Go to `/admin/innings/?match_id=5975` — you'll see
the two (or three, if super-over) innings rows for that match.
`innings_id` is the PK.

**Path B — search by team and date.** Use the match list admin with
filters: `/admin/match/?team1=Chennai+Super+Kings&season=2024` to
narrow to a handful of matches; click through to the innings list.

Once you have `innings_id`, you can either:
- Edit `keeper_assignment` directly in the admin (temporary — will be
  overwritten on next full rebuild), OR
- Add an override row to a partition CSV under
  `docs/keeper-ambiguous/` for a persistent fix.

## Known compatibility issues (fixed)

### Python 3.14 + jinja2 LRUCache

Symptom: `/admin/` returns HTTP 500 with traceback in logs pointing to
`jinja2/utils.py:515`: `cannot use 'tuple' as a dict key (unhashable
type: 'dict')`.

Root cause: **Starlette 1.0.0 flipped the positional-argument order of
`Jinja2Templates.TemplateResponse`**. In 0.x the signature was
`(name, context, ...)`; in 1.0+ it's `(request, name, context, ...)`.
The vendored deebase admin router (`router.py`) calls it using the
pre-1.0 order, so under starlette 1.0+ the template *name* ends up in
the `context` slot and vice versa. Jinja2 then tries to cache a lookup
where the "template name" is a dict — the Python 3.14 error message
just happens to surface this at the hashability check.

Fix: `pyproject.toml` and `deploy.sh` both pin `starlette>=0.46.0,<1.0.0`.
Both must be pinned — locally via uv, on plash via the generated
`requirements.txt` — or the admin breaks on that side.

**Upgrade path:** when deebase ships a version updated for starlette 1.0,
bump the starlette constraint and re-vendor.

### Missing jinja2 locally

Symptom: `uvicorn api.app:app` logs `Warning: deebase.admin not
available. Install with: pip install deebase[api]`. `/admin/` gets
caught by the SPA catch-all and returns `index.html`.

Root cause: `jinja2` is pulled in transitively by starlette on plash
(because `deploy.sh` lists it), but local `pyproject.toml` didn't have
it. Fix: `jinja2>=3.1` pinned in `pyproject.toml`.

## Authentication

`/admin/*` is gated behind HTTP Basic Auth via a `require_admin`
dependency applied to the admin router in `api/app.py`. Credentials
come from env vars `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

### Setup

**1. Local development.** Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
$EDITOR .env     # set ADMIN_USERNAME and ADMIN_PASSWORD
```

`.env` is gitignored. `api/app.py` loads it at import time (a tiny
parser, no external dep), so it works with either entry point:

```bash
uv run uvicorn api.app:app --reload --port 8000   # same as before
# or
uv run python main.py
```

**2. Plash production.** Plash's container Dockerfile ENTRYPOINT
does `bash -c ". ./plash.env && python main.py"`, i.e. it
*dot-sources* a file named `plash.env` before launching Python.
That's the hook we use to ship credentials.

**Gotcha: `.env` files are normally `KEY=VALUE`, but bash `.` sourcing
sets shell vars only — NOT environment vars — so the Python subprocess
would not inherit them.** `deploy.sh` transforms on the way in,
prefixing every `KEY=VALUE` line with `export`:

```bash
# In deploy.sh (simplified):
awk '
    /^[[:space:]]*(#|$)/ { print; next }
    /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=/ { print "export " $0; next }
    { print }
' .env > "$BUILD_DIR/plash.env"
```

Locally the same `.env` file is read directly by `api/app.py`'s
`_load_dotenv` (which doesn't care whether lines start with `export`).

If `.env` is missing at deploy time, `deploy.sh` prints a warning and
plash's `/admin/*` returns 503 fail-closed — the site itself keeps
working.

**Verification after a deploy:**

```bash
# Should be 401, not 503 — means plash has the env vars
curl -s -o /dev/null -w '%{http_code}\n' -u "x:y" https://t20.rahuldave.com/admin/
```

If you see 503: check `plash_logs --mode build` for the Dockerfile
ENTRYPOINT line (to confirm it still sources `plash.env`), then
`plash_download --save_path /tmp/dl` to inspect what's actually on
plash — the file should be there and its contents should have
`export` prefixes on the `KEY=VALUE` lines.

### Behavior

| Request | Response |
|---|---|
| No `Authorization` header | 401 with `WWW-Authenticate: Basic` → browser prompts |
| Wrong username or password | 401 |
| Env vars unset | 503 "Admin is not configured" |
| Correct credentials | 200 (or whatever the admin endpoint returns) |

Implementation in `api/app.py`:

```python
_admin_security = HTTPBasic()

def require_admin(creds: HTTPBasicCredentials = Depends(_admin_security)):
    user = os.environ.get("ADMIN_USERNAME")
    pw = os.environ.get("ADMIN_PASSWORD")
    if not user or not pw:
        raise HTTPException(503, "Admin is not configured …")
    ok = (secrets.compare_digest(creds.username, user)
          and secrets.compare_digest(creds.password, pw))
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})

app.include_router(
    create_admin_router(db),
    dependencies=[Depends(require_admin)],
)
```

Uses `secrets.compare_digest` to avoid timing attacks on the comparison.

**What Basic Auth does and doesn't give us:**

- Enforces a username/password prompt before any `/admin/*` request.
- Credentials are sent base64-encoded in the `Authorization` header on
  every request. Safe over HTTPS (plash terminates TLS); NOT safe over
  plain HTTP.
- No session cookie, no expiry. Browsers cache credentials for the
  session. Closing the browser logs you out.
- No per-user differentiation. All admin users share the same secret.
  If we later need multi-user, upgrade to session-based auth or OAuth.

### Alternatives considered

- **IP allowlist** (middleware that checks `X-Forwarded-For` against a
  set): simpler but brittle — needs updating when you move networks.
- **Admin-only subpath with nginx/Caddy auth**: plash runs Caddy and
  could apply `basicauth` there. Cleaner separation but configuration
  lives outside the repo.
- **Session-based login with a cookie**: needs a login page, CSRF
  tokens, session storage. Overkill for single-admin use.

HTTP Basic is the minimum viable lock on the door.

## Future enhancements

- **Multi-user auth** — if more than one person needs admin access,
  move to session auth with per-user credentials stored in `person`
  or a new `admin_user` table.
- **Read-only role** — useful for read-only debugging access without
  handing out full CRUD.
- **Audit log** — deebase admin doesn't track who made what edit.
  For any mutation-heavy use, add a small audit table logging
  `(timestamp, username, table, pk, field, old_value, new_value)`.
- **Upstream deebase patch** — when deebase is updated for starlette
  1.0+, drop the version pin.
