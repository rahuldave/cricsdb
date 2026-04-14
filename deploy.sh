#!/bin/bash
# Deploy CricsDB to pla.sh
# Stages a clean build directory with only what plash needs.
set -e

BUILD_DIR="build_plash"

echo "=== Building frontend ==="
cd frontend
npm run build
cd ..

echo "=== Staging deploy directory ==="
# Preserve .plash app identity across deploys
PLASH_BAK=""
if [ -f "$BUILD_DIR/.plash" ]; then
    PLASH_BAK=$(cat "$BUILD_DIR/.plash")
fi
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/data"
mkdir -p "$BUILD_DIR/frontend/dist"
mkdir -p "$BUILD_DIR/api/routers"
mkdir -p "$BUILD_DIR/models"

# Main entry point
cp main.py "$BUILD_DIR/"

# Stage the local .env (admin credentials etc) into the build.
# The file is gitignored so credentials never land in source control,
# but we need them on the plash runtime. Fail loudly if missing so a
# deploy doesn't silently ship an unauthenticated admin.
if [ -f .env ]; then
    cp .env "$BUILD_DIR/.env"
    echo "Staged .env into $BUILD_DIR/ (admin credentials etc)"
else
    echo "WARNING: no .env file found — admin will return 503 on plash" >&2
fi

# Requirements (deebase deps only — deebase itself is vendored)
cat > "$BUILD_DIR/requirements.txt" <<'EOF'
aiosqlite>=0.22.0
sqlalchemy>=2.0.45
greenlet>=3.3.0
click>=8.3.1
toml>=0.10.2
fastapi>=0.115.0
# Pin starlette below 1.0 — vendored deebase admin uses the pre-1.0
# TemplateResponse signature (name first, not request first). Upgrade
# this constraint once deebase is patched upstream.
starlette>=0.46.0,<1.0.0
pydantic>=2.10.0
fastcore>=1.7.0
uvicorn>=0.34.0
jinja2>=3.1.0
python-multipart>=0.0.9
EOF

# Vendor deebase (requires Python 3.13+, plash has 3.12)
cp -r .venv/lib/python3.14/site-packages/deebase "$BUILD_DIR/deebase"
rm -rf "$BUILD_DIR/deebase/__pycache__" "$BUILD_DIR/deebase"/*/__pycache__

# API code
cp api/__init__.py api/app.py api/dependencies.py api/filters.py "$BUILD_DIR/api/"
cp api/routers/*.py "$BUILD_DIR/api/routers/"

# Models
cp models/__init__.py models/tables.py "$BUILD_DIR/models/"

# Built frontend
cp -r frontend/dist/* "$BUILD_DIR/frontend/dist/"

# Restore .plash identity
if [ -n "$PLASH_BAK" ]; then
    echo "$PLASH_BAK" > "$BUILD_DIR/.plash"
fi

# Database (435MB — only needed on first deploy with --force_data)
if [ "$1" = "--first" ]; then
    echo "First deploy: copying cricket.db to build (435MB)..."
    cp cricket.db "$BUILD_DIR/data/cricket.db"
fi

echo "=== Deploy directory contents ==="
du -sh "$BUILD_DIR"/*

echo "=== Deploying from $BUILD_DIR ==="
if [ "$1" = "--first" ]; then
    plash_deploy --path "$BUILD_DIR" --force_data
else
    plash_deploy --path "$BUILD_DIR"
fi

echo "=== Done ==="
plash_view --path "$BUILD_DIR"
