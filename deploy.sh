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
# but we need them on the plash runtime. Plash's Docker ENTRYPOINT
# does `. ./plash.env` (bash source) before running main.py, which sets
# shell vars but does NOT auto-export them to child processes. So we
# transform `KEY=VALUE` -> `export KEY=VALUE` on the way in. Locally,
# api/app.py reads .env directly via its own _load_dotenv parser.
if [ -f .env ]; then
    awk '
        /^[[:space:]]*(#|$)/ { print; next }                      # comment or blank
        /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=/ { print "export " $0; next }
        { print }                                                  # anything else, pass through
    ' .env > "$BUILD_DIR/plash.env"
    echo "Staged .env -> $BUILD_DIR/plash.env (with export prefix for Dockerfile ENTRYPOINT)"
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
# api/*.py is globbed so new top-level modules (e.g. tournament_canonical.py)
# don't silently fail to ship. Routers already use a glob.
cp api/*.py "$BUILD_DIR/api/"
cp api/routers/*.py "$BUILD_DIR/api/routers/"

# Models
cp models/__init__.py models/tables.py "$BUILD_DIR/models/"

# Built frontend
cp -r frontend/dist/* "$BUILD_DIR/frontend/dist/"

# Restore .plash identity
if [ -n "$PLASH_BAK" ]; then
    echo "$PLASH_BAK" > "$BUILD_DIR/.plash"
fi

# Database (~653 MB as of 2026-04 — only needed on first deploy with --force_data).
#
# Pre-flight: verify the SOURCE cricket.db isn't malformed AND checkpoint
# the WAL into the main file so the cp captures a consistent on-disk
# state. The 2026-04-27 prod outage was caused by uploading a cricket.db
# while populate_bucket_baseline.py still had pending WAL pages — the
# uploaded file was page-corrupt, queries that touched the bad pages
# 500'd in production. The two extra checks below cost ~10s and prevent
# silently shipping a torn DB.
if [ "$1" = "--first" ]; then
    echo "First deploy — verifying source cricket.db integrity..."
    sqlite3 cricket.db "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null
    integrity=$(sqlite3 cricket.db "PRAGMA integrity_check;")
    if [ "$integrity" != "ok" ]; then
        echo "FATAL: cricket.db is malformed:" >&2
        echo "$integrity" | head -10 >&2
        echo "Aborting deploy. Fix the local DB first (rebuild via import_data.py or restore from backup)." >&2
        exit 1
    fi
    db_bytes=$(stat -f%z cricket.db 2>/dev/null || stat -c%s cricket.db)
    db_mb=$(( db_bytes / 1024 / 1024 ))
    echo "Source DB is clean (${db_mb}MB). Copying to build..."
    cp cricket.db "$BUILD_DIR/data/cricket.db"
    # Verify the COPY also passes integrity — catches a torn cp on a
    # full disk or filesystem hiccup before we hand it to plash.
    copy_integrity=$(sqlite3 "$BUILD_DIR/data/cricket.db" "PRAGMA integrity_check;")
    if [ "$copy_integrity" != "ok" ]; then
        echo "FATAL: copy in $BUILD_DIR/data/cricket.db is malformed after cp" >&2
        exit 1
    fi
    echo "Copy verified OK."
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
