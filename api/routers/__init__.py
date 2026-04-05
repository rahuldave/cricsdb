"""Router registration for FastAPI app."""

from fastapi import FastAPI

from .reference import router as reference_router
from .teams import router as teams_router
from .batting import router as batting_router
from .bowling import router as bowling_router
from .head_to_head import router as head_to_head_router


def register_routers(app: FastAPI):
    """Register all API routers."""
    app.include_router(reference_router)
    app.include_router(teams_router)
    app.include_router(batting_router)
    app.include_router(bowling_router)
    app.include_router(head_to_head_router)
