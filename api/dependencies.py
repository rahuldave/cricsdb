"""Database dependencies for FastAPI."""

import os
from deebase import Database

# Global database instance
_db: Database | None = None


def get_db() -> Database | None:
    """Get the database instance."""
    return _db


async def init_db():
    """Initialize the database connection."""
    global _db

    if os.environ.get("PLASH_PRODUCTION") == "1":
        db_path = "data/cricket.db"
    else:
        db_path = "./cricket.db"

    db_url = f"sqlite+aiosqlite:///{db_path}"
    _db = Database(db_url)
    await _db.enable_foreign_keys()
    await _db.q("PRAGMA journal_mode = WAL")
