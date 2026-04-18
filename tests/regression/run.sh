#!/bin/bash
# Regression-test runner: HEAD-vs-patched md5-diff for a feature's URL
# inventory. See tests/regression/README.md for the full workflow.
#
# Usage:
#   ./tests/regression/run.sh <feature>
#
# Reads tests/regression/<feature>/urls.txt, stashes the current
# uncommitted code changes, captures HEAD responses, pops, captures
# patched responses, diffs. Exit 0 iff REG:0 drifted AND NEW:0
# unchanged.

set -u

FEATURE="${1:-}"
if [ -z "$FEATURE" ]; then
  echo "Usage: $0 <feature>" >&2
  echo "Available:" >&2
  ls tests/regression 2>/dev/null | grep -v -E '^(README|run)' >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
URLS_FILE="$REPO_ROOT/tests/regression/$FEATURE/urls.txt"
if [ ! -f "$URLS_FILE" ]; then
  echo "No urls.txt at $URLS_FILE" >&2
  exit 2
fi

BASE="${BASE:-http://localhost:8000}"
WORK="/tmp/regression-test-$FEATURE"
rm -rf "$WORK"
mkdir -p "$WORK/head" "$WORK/patched"

# ──────────────── capture ────────────────
capture() {
  local out="$1"
  : > "$out/manifest.txt"
  : > "$out/errors.txt"
  while IFS= read -r line; do
    case "$line" in \#*|"") continue ;; esac
    local kind label url
    kind=$(echo "$line" | awk '{print $1}')
    label=$(echo "$line" | awk '{print $2}')
    url=$(echo "$line" | awk '{print $3}')
    [ -z "$url" ] && continue

    local response
    response=$(curl -sS --max-time 15 "$BASE$url")
    if [ $? -ne 0 ]; then
      echo "$label CURL_ERROR $url" >> "$out/errors.txt"
      continue
    fi

    echo "$response" | python3 -m json.tool > "$out/$label.json" 2>/dev/null \
      || echo "$response" > "$out/$label.json"
    local compact h
    compact=$(echo "$response" | python3 -c 'import sys,json; print(json.dumps(json.loads(sys.stdin.read()), sort_keys=True, separators=(",",":")))' 2>/dev/null || echo "$response")
    if command -v md5 >/dev/null 2>&1; then
      h=$(echo -n "$compact" | md5 | awk '{print $NF}')
    else
      h=$(echo -n "$compact" | md5sum | awk '{print $1}')
    fi
    printf "%s\t%s\t%s\n" "$kind" "$label" "$h" >> "$out/manifest.txt"
  done < "$URLS_FILE"
}

echo "=== [$FEATURE] Smoke-check: does every URL resolve on the patched server? ==="
capture "$WORK/smoke"
err_count=$(wc -l < "$WORK/smoke/errors.txt" | tr -d ' ')
if [ "$err_count" -ne 0 ]; then
  echo "FAIL: $err_count URL(s) errored against the patched server:" >&2
  cat "$WORK/smoke/errors.txt" >&2
  exit 1
fi
url_count=$(wc -l < "$WORK/smoke/manifest.txt" | tr -d ' ')
echo "OK — $url_count URLs resolve cleanly."
rm -rf "$WORK/smoke"

# ──────────────── HEAD vs patched ────────────────
echo
echo "=== Stashing code to capture HEAD ==="
STASH_MSG="regression-test-$FEATURE-$(date +%s)"
# Stash all tracked modifications. Unstaged code changes go with the
# stash; the resulting tree is the last committed state.
if ! git stash push -m "$STASH_MSG" --keep-index 2>/dev/null; then
  # --keep-index tries to preserve staged changes. If it fails we just
  # stash everything.
  git stash push -m "$STASH_MSG" || { echo "git stash failed"; exit 1; }
fi

# Actually we want to stash EVERYTHING (including staged), so index is
# HEAD state. Redo if --keep-index left anything modified.
if ! git diff --quiet; then
  git stash push -m "$STASH_MSG-full" || { echo "git stash (full) failed"; exit 1; }
fi

sleep 3  # uvicorn --reload settle
echo "Capturing HEAD..."
capture "$WORK/head"

echo "=== Popping stash back ==="
# Pop all stashes we pushed (there may be one or two)
while git stash list | grep -q "$STASH_MSG"; do
  git stash pop || { echo "git stash pop failed"; break; }
done

sleep 3
echo "Capturing patched..."
capture "$WORK/patched"

# ──────────────── diff ────────────────
echo
echo "=== Diff HEAD vs patched ==="
python3 - <<PY
from pathlib import Path
head = {}
for l in Path("$WORK/head/manifest.txt").read_text().splitlines():
    kind, label, h = l.split("\t")
    head[label] = (kind, h)
patched = {}
for l in Path("$WORK/patched/manifest.txt").read_text().splitlines():
    kind, label, h = l.split("\t")
    patched[label] = (kind, h)

reg_ok, reg_drift, new_ch, new_same = [], [], [], []
for k in sorted(set(head) | set(patched)):
    if k not in head or k not in patched:
        print(f"MISSING: {k}"); continue
    kind, hh = head[k]
    _, hp = patched[k]
    if kind == "REG":
        (reg_ok if hh == hp else reg_drift).append(k)
    else:
        (new_ch if hh != hp else new_same).append(k)

print(f"REG matched:    {len(reg_ok)}")
print(f"REG DRIFTED:    {len(reg_drift)}  ← must be zero")
for k in reg_drift: print(f"  ✗ {k}")
print(f"NEW changed:    {len(new_ch)}")
for k in new_ch: print(f"  ✓ {k}")
print(f"NEW unchanged:  {len(new_same)}  ← suspicious if non-zero")
for k in new_same: print(f"  ? {k}")

import sys
sys.exit(1 if reg_drift or new_same else 0)
PY
status=$?

echo
echo "Artefacts in $WORK/{head,patched}/*.json for inspection."
exit $status
