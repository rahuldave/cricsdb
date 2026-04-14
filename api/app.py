"""FastAPI application entry point."""

import os
import secrets


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader — no external dep, no interpolation.
    Runs at import time so env vars are available by the time the
    require_admin dependency reads them. Looks for .env in CWD.
    Works whether the app is launched via `main.py` or directly via
    `uvicorn api.app:app`.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if val and len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            os.environ.setdefault(key, val)


_load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from .dependencies import get_db, init_db  # noqa: E402
from .routers import register_routers  # noqa: E402


# HTTP Basic Auth guard for /admin/*. Credentials come from env vars
# ADMIN_USERNAME and ADMIN_PASSWORD. Fail-closed: if either env var
# is missing, every admin request returns 503. See docs/admin-interface.md.
_admin_security = HTTPBasic()


def require_admin(
    creds: HTTPBasicCredentials = Depends(_admin_security),
) -> None:
    """Guard dependency applied to the deebase admin router."""
    user = os.environ.get("ADMIN_USERNAME")
    pw = os.environ.get("ADMIN_PASSWORD")
    if not user or not pw:
        raise HTTPException(
            status_code=503,
            detail="Admin is not configured (ADMIN_USERNAME/ADMIN_PASSWORD unset).",
        )
    ok = (
        secrets.compare_digest(creds.username, user)
        and secrets.compare_digest(creds.password, pw)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    db = get_db()

    # Register CRUD routers (must be after init_db so db is available)
    register_routers(app)

    # Register admin interface — gated behind HTTP Basic Auth.
    # See require_admin above and docs/admin-interface.md.
    if db:
        try:
            from deebase.admin import create_admin_router
            await db.reflect()
            app.include_router(
                create_admin_router(db),
                dependencies=[Depends(require_admin)],
            )
        except ImportError:
            print("Warning: deebase.admin not available. Install with: pip install deebase[api]")

    # SPA fallback — must be registered AFTER API routers so /api/v1/* matches first
    if os.path.exists("frontend/dist"):
        from fastapi.responses import FileResponse

        @app.get("/{path:path}", include_in_schema=False)
        async def serve_spa(path: str):
            file_path = os.path.join("frontend/dist", path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse("frontend/dist/index.html")

    yield

    # Shutdown
    if db:
        await db.close()


app = FastAPI(
    title="CricsDB API",
    description="T20 Cricket Analytics Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
