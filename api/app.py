"""FastAPI application entry point."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .dependencies import get_db, init_db
from .routers import register_routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    db = get_db()

    # Register CRUD routers (must be after init_db so db is available)
    register_routers(app)

    # Register admin interface
    if db:
        try:
            from deebase.admin import create_admin_router
            await db.reflect()
            app.include_router(create_admin_router(db))
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
