# Regression-testing an API refactor

Goal: before shipping a change that touches a shared helper (e.g.
`FilterParams`, a router filter helper, a populate script's query) you
want proof that **queries you didn't intend to change still return
byte-identical responses**, and queries you DID intend to change now
return the right answer.

Eyeball tests give you a handful of sanity points. A proper regression
run gives you coverage across the full endpoint matrix at every filter
combination, with a binary pass/fail per URL.

## When to use this pattern

Reach for this when the change has:

- **High blast radius** — a shared helper called from many routes
  (`FilterParams.build`, `_fielding_filter`, etc.).
- **Silent-failure potential** — SQL changes don't raise errors; they
  return the wrong rows, and the test most likely to expose that is
  pushing two queries through the two versions and diffing the output.
- **A before/after hypothesis** — you're claiming "this code path
  returned wrong data, my fix returns right data, and nothing
  unrelated changes." That hypothesis is directly testable.

Don't use it for one-line fixes or for pure frontend changes (use the
`agent-browser` skill for those — see CLAUDE.md "UI verification
rule").

## Methodology at a glance

1. Enumerate every (endpoint, filter-combo) URL your change could
   affect, plus a control sample of unrelated endpoints.
2. Tag each URL `REG` (regression — must match HEAD) or `NEW`
   (new-behavior — HEAD and patched should differ, patched side must
   be sensible).
3. `git stash` the changes, let `uvicorn --reload` pick up HEAD.
4. Hit every URL, save the pretty JSON, md5 the compact form. This is
   the baseline.
5. `git stash pop`, wait for reload, hit the same URLs again. This is
   the patched run.
6. Diff the manifests:
   - **REG drifted** → regression failure, investigate.
   - **NEW unchanged** → either the URL was a dud (typo, missing data)
     or the fix is inert on that code path — worth checking.
7. Spot-check a handful of `NEW` responses numerically — HEAD vs
   patched side-by-side — so you know the fix moves numbers in the
   right direction, not just *some* direction.

## Prerequisites

- `uvicorn api.app:app --reload --port 8000` running. The `--reload`
  flag is what lets you stash/unstash without restarting the server.
  (See memory: `feedback_uvicorn_reload.md` — bare `uvicorn` serves
  stale code.)
- `curl`, `python3`, `md5` (macOS) or `md5sum` (Linux).
- A working-directory state where the only uncommitted changes are
  the code you're testing. Anything else (half-edited docs, scratch
  files) should be either committed or intentionally out-of-scope so
  the `git stash` step is clean.

## Step-by-step, with reusable code

The convention below writes all artefacts under `/tmp/regression-test/`
so they don't leak into the repo. Nothing here is committed — these
are per-change, disposable runs.

### 1. Write the URL inventory

Create `/tmp/regression-test/urls.txt` with one test per line:

```text
# <kind> <label> <url-path-and-query>
REG bumrah_bow_sum_none          /api/v1/bowlers/462411b3/summary
REG bumrah_bow_sum_tournament    /api/v1/bowlers/462411b3/summary?tournament=Indian%20Premier%20League
NEW bumrah_bow_sum_team_india    /api/v1/bowlers/462411b3/summary?filter_team=India
```

Conventions:

- `label` must be filesystem-safe (`[a-z0-9_]+`) — it becomes a
  filename.
- `REG` = this query should not be affected by your change.
- `NEW` = this query SHOULD be affected.
- Aim for coverage across **every endpoint** in the touched routers,
  **every filter dimension** (gender, tournament, season, team, etc.),
  and **a control sample** from unrelated routers that MUST NOT budge.
- Include at least one subject per router (a batter for batting
  routes, a bowler for bowling, etc.).
- Verify team names match the DB's canonical form (check
  `team_aliases.py` — e.g. "Royal Challengers Bengaluru", not
  "Bangalore"). A typo'd team name silently returns zero rows, which
  looks like a bug in your code if you're not paying attention.

### 2. Capture script (`/tmp/regression-test/capture.sh`)

```bash
#!/bin/bash
set -u
OUT="${1:?Usage: capture.sh <output_dir>}"
mkdir -p "$OUT"
: > "$OUT/manifest.txt"
: > "$OUT/errors.txt"
URLS=/tmp/regression-test/urls.txt
BASE=http://localhost:8000

while IFS= read -r line; do
  case "$line" in \#*|"") continue ;; esac
  kind=$(echo "$line" | awk '{print $1}')
  label=$(echo "$line" | awk '{print $2}')
  url=$(echo "$line" | awk '{print $3}')
  [ -z "$url" ] && continue

  response=$(curl -sS --max-time 15 "$BASE$url")
  if [ $? -ne 0 ]; then
    echo "$label CURL_ERROR $url" >> "$OUT/errors.txt"
    continue
  fi

  # Pretty-print for human inspection; hash the compact sorted form so
  # whitespace and key-order noise don't cause false diffs.
  echo "$response" | python3 -m json.tool > "$OUT/$label.json" 2>/dev/null \
    || echo "$response" > "$OUT/$label.json"
  compact=$(echo "$response" | python3 -c 'import sys,json; print(json.dumps(json.loads(sys.stdin.read()), sort_keys=True, separators=(",",":")))' 2>/dev/null || echo "$response")
  h=$(echo -n "$compact" | md5 | awk '{print $NF}')
  printf "%s\t%s\t%s\n" "$kind" "$label" "$h" >> "$OUT/manifest.txt"
done < "$URLS"
```

Make it executable: `chmod +x /tmp/regression-test/capture.sh`.

### 3. Run once to smoke the inventory

Before stashing, run the capture against your current (patched) state:

```bash
/tmp/regression-test/capture.sh /tmp/regression-test/smoke-check
wc -l /tmp/regression-test/smoke-check/errors.txt   # should be 0
wc -l /tmp/regression-test/smoke-check/manifest.txt # = URL count
```

Zero `errors.txt` confirms every URL resolves on your current server.
Non-zero means a typo or a missing endpoint — fix `urls.txt` before
proceeding.

`rm -rf /tmp/regression-test/smoke-check` once it's clean.

### 4. Capture HEAD baseline

Stash only the code files, not docs or unrelated scratch:

```bash
git stash push -u -m "regression-test-head-capture" -- \
  api/filters.py api/routers/<the-files-you-changed>.py \
  frontend/src/<frontend-files>
```

Wait ~3 seconds for uvicorn's reloader, then sanity-check that you're
really on HEAD:

```bash
sleep 3
curl -s 'http://localhost:8000/api/v1/<a-known-NEW-url>' \
  | python3 -m json.tool | head
# expect: values that demonstrate the HEAD bug
```

Then capture:

```bash
/tmp/regression-test/capture.sh /tmp/regression-test/head
```

### 5. Capture patched

```bash
git stash pop
sleep 3
curl -s 'http://localhost:8000/api/v1/<a-known-NEW-url>' \
  | python3 -m json.tool | head
# expect: values that demonstrate the patched fix
/tmp/regression-test/capture.sh /tmp/regression-test/patched
```

### 6. Diff script (`/tmp/regression-test/diff.py`)

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

HEAD = Path("/tmp/regression-test/head/manifest.txt")
PATCHED = Path("/tmp/regression-test/patched/manifest.txt")

def load(p):
    out = {}
    for line in p.read_text().splitlines():
        kind, label, h = line.split("\t")
        out[label] = (kind, h)
    return out

head = load(HEAD)
patched = load(PATCHED)
reg_drifted, reg_matched, new_changed, new_unchanged = [], [], [], []
for label in sorted(set(head) | set(patched)):
    if label not in head or label not in patched:
        print(f"MISSING: {label}"); continue
    kind_h, hh = head[label]
    kind_p, hp = patched[label]
    if kind_h == "REG":
        (reg_matched if hh == hp else reg_drifted).append(label)
    else:
        (new_changed if hh != hp else new_unchanged).append(label)

print(f"REG: {len(reg_matched)} matched, {len(reg_drifted)} DRIFTED")
print(f"NEW: {len(new_changed)} changed, {len(new_unchanged)} unchanged")
if reg_drifted:
    print("\n!! Regression failures:")
    for lbl in reg_drifted: print(f"  - {lbl}")
if new_unchanged:
    print("\n?? New-behavior URLs that did not change:")
    for lbl in new_unchanged: print(f"  - {lbl}")
sys.exit(1 if reg_drifted else 0)
```

`python3 /tmp/regression-test/diff.py`.

### 7. Interpret results

**REG drifted → stop and investigate.** The change affected something
it was not supposed to. Diff the JSON:

```bash
diff /tmp/regression-test/{head,patched}/<label>.json
```

**NEW unchanged → investigate but don't panic.** Common causes:

- Typo in the test URL (e.g. old team name that's been canonicalized).
  Re-verify with `curl` directly.
- The query genuinely returns 0 on both sides (e.g. "MS Wade
  stumpings vs India" is legitimately 0 — he never stumped an Indian).
  Confirm with a broader version of the query.
- The fix is inert for this specific endpoint — sometimes OK, but
  means your `NEW` coverage is weaker than you thought.

**NEW changed but values look wrong →** the fix is wrong or
incomplete. Go back to the code.

### 8. Spot-check numerics

`md5` diffs prove "different"; they don't prove "correct". Pick 5-10
`NEW` responses and print key fields side-by-side. Something like:

```python
import json
from pathlib import Path
H, P = Path("/tmp/regression-test/head"), Path("/tmp/regression-test/patched")
for lbl, fields in [
    ("bumrah_bow_sum_team_india", ["matches", "wickets", "runs_conceded"]),
    # ...
]:
    h = json.load(open(H/f"{lbl}.json"))
    p = json.load(open(P/f"{lbl}.json"))
    print(lbl)
    for f in fields:
        arrow = " --> " if h[f] != p[f] else "  == "
        print(f"  {f}: HEAD={h[f]!r}{arrow}PATCHED={p[f]!r}")
```

Cross-reference two or three against public career totals (cricinfo,
stats.espncricinfo.com) so you have external evidence the patched
numbers are right.

## Cleanup

After the run: `rm -rf /tmp/regression-test/{head,patched}`. Keep
`urls.txt`, `capture.sh`, and `diff.py` if you anticipate another
iteration on the same refactor; otherwise clear `/tmp/regression-test/`
entirely.

## Caveats

- **md5 on the compact+sorted form.** Pretty-printed JSON can vary in
  whitespace across Python versions; compact+sort-keys is stable.
- **Order-sensitive endpoints.** If an endpoint returns a list whose
  order is not stable (e.g. `ORDER BY` ties), an md5 diff will
  false-positive. Add a stable secondary sort in the endpoint or
  post-process the JSON before hashing.
- **Time-dependent endpoints.** Anything that embeds "now" (rare in
  this codebase) will md5-differ across runs. Skip or stub.
- **Connection pooling / warm caches.** Between the two runs, the same
  sqlite connection is reused. If your change touches cached state
  (pragma, attached DBs), restart uvicorn between captures.
- **Canonical names.** Before writing `filter_team=<Team>`, check
  `team_aliases.py` so you don't send a pre-rename literal. Same for
  `event_aliases.py` and tournament names.

## Worked example: `build_side_neutral` refactor

The original motivation for this doc. The change added
`FilterParams.build_side_neutral()` and switched fielding/bowling/
keeping routers to use it instead of `build()` when applying
`filter_team` / `filter_opponent`. 100 URLs were tested:

- **63 REG** (no team filter, or batting/team/tournament/matches
  routers) → 63/63 byte-identical, proving the fix is inert when no
  `filter_team`/`filter_opponent` is set.
- **37 NEW** → 36 changed, 1 was a test-URL typo (`Bangalore` instead
  of the canonicalized `Bengaluru`) which re-verified correctly.
  Numerics cross-checked: Bumrah T20I career (90 matches, 117 wkts),
  Pollard MI-IPL (97 catches), de Villiers SA T20Is (60 catches) — all
  match public career numbers.

That gave concrete evidence the refactor was safe to ship.
