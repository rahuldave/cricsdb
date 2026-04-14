"""CricsDB entry point for pla.sh deployment."""

import os
import uvicorn

# api.app loads .env at import time (see _load_dotenv there), so whether
# we enter via `python main.py` or `uvicorn api.app:app`, credentials are
# available to the require_admin guard.
from api.app import app

# Mount static assets (this is fine at import time — it's a mount, not a route)
if os.path.exists("frontend/dist"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="static-assets")

if __name__ == "__main__":
    port = 5001 if os.getenv("PLASH_PRODUCTION") == "1" else 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
