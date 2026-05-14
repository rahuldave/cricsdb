"""Router registration for FastAPI app."""

from fastapi import FastAPI

from .reference import router as reference_router
from .teams import router as teams_router
from .scope_averages import router as scope_averages_router
from .batting import router as batting_router
from .bowling import router as bowling_router
from .fielding import router as fielding_router
from .keeping import router as keeping_router
from .head_to_head import router as head_to_head_router
from .matches import router as matches_router
from .tournaments import router as tournaments_router
from .venues import router as venues_router


def register_routers(app: FastAPI):
    """Register all API routers."""
    app.include_router(reference_router)
    app.include_router(teams_router)
    app.include_router(scope_averages_router)
    app.include_router(batting_router)
    app.include_router(bowling_router)
    app.include_router(fielding_router)
    app.include_router(keeping_router)
    app.include_router(head_to_head_router)
    app.include_router(matches_router)
    app.include_router(tournaments_router)
    app.include_router(venues_router)
