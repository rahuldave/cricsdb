#!/bin/bash
# Weekly cricsheet ingest — PREPARE step only.
#
# Does the mechanical half of a data-update cycle and then STOPS:
#   backup -> staleness check -> import -> venue retrofit -> sanity tests -> report
#
# It deliberately does NOT commit and does NOT deploy. Those need a human
# (or a Claude session) to attribute countries for any new grounds, triage
# test failures, and write the commit message. See the review step in
# internal_docs/data-pipeline.md "Weekly update cycle".
#
# Safe to re-run: matches dedupe on cricsheet's stable match id, the venue
# retrofit is idempotent, and the index/ANALYZE step is a no-op when current.
#
# Usage:
#   bash weekly_update.sh                # normal run
#   bash weekly_update.sh --allow-dirty  # proceed even with uncommitted changes
#
# Exit codes: 0 = ready to review (or nothing to do), 1 = needs attention.

# No `set -e` on purpose — a failing step must still reach the report.
set -uo pipefail

cd "$(dirname "$0")" || exit 1
REPO="$PWD"

# launchd gives us a bare PATH, so pin the tools we need.
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

ALLOW_DIRTY=0
[ "${1:-}" = "--allow-dirty" ] && ALLOW_DIRTY=1

TODAY=$(date +%F)
STAMP="tmp/.weekly-update-last-run"
LOG="tmp/weekly-update-$TODAY.log"
REPORT="tmp/weekly-update-$TODAY.md"
LATEST="tmp/weekly-update-latest.md"
BUNDLE_DAYS=30          # cricsheet's largest "recently added" bundle
STALE_WARN_DAYS=25      # start warning before we reach the bundle's reach

# Sanity checks that are expected to fail on current data. Each entry needs a
# reason — an unexplained entry here is how a real regression gets hidden.
#   test_playerscopestats_position: one row (R Choden, ACC Women's Premier Cup
#   2026) has 3 dismissals against 2 innings batted, so the per-position
#   breakdown is one short of the headline. Pre-dates 2026-08-20; unrelated to
#   any ingest. Remove from this list once that row is understood.
KNOWN_FAILING="test_playerscopestats_position"

SANITY_TESTS="
test_player_scope_stats
test_playerscopestats_position
test_playerscopestatsposition_rollup
test_playerscopestats_over
test_playerscopestats_fielding_position
test_playerscopestats_batting_phase
test_playerscopestats_fielding_phase
test_bucket_baseline
test_catches_convention3
test_predicate_invariants
test_inningsbatterperf_incremental
"

mkdir -p tmp backups
: > "$LOG"
: > "$REPORT"     # start fresh — a re-run on the same day must not append

say()  { printf '%s\n' "$*"; }
rep()  { printf '%s\n' "$*" >> "$REPORT"; }
run()  { say "  \$ $*"; "$@" >> "$LOG" 2>&1; }

finish() {   # finish <exit-code>
    cp "$REPORT" "$LATEST"
    say ""
    say "── report ──────────────────────────────────────────────"
    cat "$REPORT"
    say "────────────────────────────────────────────────────────"
    say "Full log:   $REPO/$LOG"
    say "Report:     $REPO/$REPORT"
    # Best-effort desktop nudge; harmless if osascript is unavailable.
    if [ "$1" -eq 0 ]; then
        MSG="Cricsheet weekly update ready to review"
    else
        MSG="Cricsheet weekly update needs attention"
    fi
    osascript -e "display notification \"$MSG\" with title \"CricsDB\"" >/dev/null 2>&1
    exit "$1"
}

sq() { sqlite3 cricket.db "$1" 2>/dev/null; }

# ── preflight ───────────────────────────────────────────────────────────
say "=== CricsDB weekly update — $TODAY ==="
rep "# Weekly cricsheet update — $TODAY"
rep ""

if [ ! -f cricket.db ] || [ ! -f update_recent.py ]; then
    rep "**ABORTED — not the project root.** No cricket.db / update_recent.py here."
    finish 1
fi

DIRTY=$(git status --porcelain 2>/dev/null)
if [ -n "$DIRTY" ] && [ "$ALLOW_DIRTY" -eq 0 ]; then
    rep "**ABORTED — uncommitted changes in the working tree.**"
    rep ""
    rep 'An ingest cycle ends in its own commit, so it must start from a clean'
    rep 'tree. Commit or stash the below, then re-run (or pass `--allow-dirty`).'
    rep ""
    rep '```'
    rep "$DIRTY"
    rep '```'
    finish 1
fi

FREE_GB=$(df -g . | awk 'NR==2 {print $4}')
if [ "${FREE_GB:-99}" -lt 5 ]; then
    rep "**ABORTED — only ${FREE_GB}GB free.** Need headroom for the backup."
    finish 1
fi

# ── staleness: can the 30-day bundle still reach our last import? ────────
DAYS_SINCE=""
if [ -f "$STAMP" ]; then
    LAST_RUN=$(cat "$STAMP")
    LAST_EPOCH=$(date -j -f %F "$LAST_RUN" +%s 2>/dev/null)
    if [ -n "${LAST_EPOCH:-}" ]; then
        DAYS_SINCE=$(( ( $(date +%s) - LAST_EPOCH ) / 86400 ))
    fi
fi

MATCHES_BEFORE=$(sq "select count(*) from match;")
LATEST_BEFORE=$(sq "select max(substr(dates,3,10)) from match;")
PERSON_BEFORE=$(sq "select count(*) from person;")
NAMES_BEFORE=$(sq "select count(*) from personname;")

rep "## Before"
rep ""
rep "| | |"
rep "|---|---|"
rep "| Matches in database | $MATCHES_BEFORE |"
rep "| Latest match | $LATEST_BEFORE |"
if [ -n "$DAYS_SINCE" ]; then
    rep "| Last update run | $LAST_RUN ($DAYS_SINCE days ago) |"
else
    rep "| Last update run | no record — first run of this script |"
fi
rep ""

if [ -n "$DAYS_SINCE" ] && [ "$DAYS_SINCE" -gt "$BUNDLE_DAYS" ]; then
    rep "> **Gap risk.** $DAYS_SINCE days since the last run, and cricsheet's"
    rep "> largest bundle only reaches back $BUNDLE_DAYS days. Matches added to"
    rep "> cricsheet before that window may be unreachable. The date-continuity"
    rep "> check below tells you whether anything actually fell through; if it"
    rep "> did, a full rebuild is the fix (download_data.py + import_data.py)."
    rep ""
elif [ -n "$DAYS_SINCE" ] && [ "$DAYS_SINCE" -gt "$STALE_WARN_DAYS" ]; then
    rep "> **Heads up.** $DAYS_SINCE days since the last run — close to the"
    rep "> $BUNDLE_DAYS-day limit of cricsheet's largest bundle. Don't let the"
    rep "> next cycle slip."
    rep ""
fi

# ── backup (rotate, keep the two most recent) ───────────────────────────
say "--- backing up cricket.db ---"
BACKUP="backups/cricket.db.pre-incremental-$TODAY"
if cp cricket.db "$BACKUP"; then
    say "  backup: $BACKUP"
else
    rep "**ABORTED — could not back up cricket.db.** Nothing was imported."
    finish 1
fi
ls -1t backups/cricket.db.pre-incremental-* 2>/dev/null | tail -n +3 | while read -r old; do
    say "  pruning old backup: $old"
    rm -f "$old"
done

# ── import ──────────────────────────────────────────────────────────────
say "--- importing (30-day window) ---"
uv run python update_recent.py --days "$BUNDLE_DAYS" >> "$LOG" 2>&1
IMPORT_RC=$?

MATCHES_AFTER=$(sq "select count(*) from match;")
LATEST_AFTER=$(sq "select max(substr(dates,3,10)) from match;")
NEW_COUNT=$(( MATCHES_AFTER - MATCHES_BEFORE ))

if [ "$IMPORT_RC" -ne 0 ]; then
    rep "## Import FAILED (exit $IMPORT_RC)"
    rep ""
    rep "Database went from $MATCHES_BEFORE to $MATCHES_AFTER matches before"
    rep "the failure. Backup to restore from if needed:"
    rep ""
    rep '```'
    rep "cp $BACKUP cricket.db"
    rep '```'
    rep ""
    rep "Last 30 lines of the log:"
    rep ""
    rep '```'
    tail -30 "$LOG" >> "$REPORT"
    rep '```'
    finish 1
fi

if [ "$NEW_COUNT" -eq 0 ]; then
    rep "## Nothing to import"
    rep ""
    rep "Cricsheet has published nothing new since $LATEST_BEFORE. Database"
    rep "unchanged at $MATCHES_BEFORE matches. No commit, no deploy needed."
    rep ""
    rep "A one-to-three day lag behind today is normal for cricsheet."
    rm -f "$BACKUP"
    echo "$TODAY" > "$STAMP"
    finish 0
fi

# ── date continuity: did anything fall through the bundle's window? ─────
FIRST_NEW=$(sq "select min(substr(dates,3,10)) from match where substr(dates,3,10) > '$LATEST_BEFORE';")
GAP_DAYS=$(python3 - "$LATEST_BEFORE" "$FIRST_NEW" <<'PY' 2>/dev/null
import sys, datetime
a = datetime.date.fromisoformat(sys.argv[1])
b = datetime.date.fromisoformat(sys.argv[2])
print((b - a).days)
PY
)
MISSING_DAYS=$(python3 - "$LATEST_BEFORE" "$LATEST_AFTER" <<'PY' 2>/dev/null
import sys, datetime, sqlite3, subprocess
start = datetime.date.fromisoformat(sys.argv[1])
end   = datetime.date.fromisoformat(sys.argv[2])
con = sqlite3.connect('cricket.db')
have = {r[0] for r in con.execute(
    "select distinct substr(dates,3,10) from match where substr(dates,3,10) > ?",
    (sys.argv[1],))}
d, missing = start + datetime.timedelta(days=1), []
while d <= end:
    if d.isoformat() not in have: missing.append(d.isoformat())
    d += datetime.timedelta(days=1)
print(len(missing), ' '.join(missing[:10]))
PY
)

# ── venue retrofit + collision sweep ────────────────────────────────────
say "--- venue retrofit ---"
uv run python scripts/fix_venue_names.py >> "$LOG" 2>&1
uv run python scripts/sweep_venue_punctuation_collisions.py >> "$LOG" 2>&1
NULL_COUNTRY=$(sq "select count(*) from match where venue_country is null;")
UNKNOWNS_CSV="docs/venue-worklist/unknowns-$TODAY.csv"

# ── sanity tests ────────────────────────────────────────────────────────
say "--- sanity tests ---"
SANITY_LINES=""
NEW_FAILURES=0
KNOWN_NOW_PASSING=""
for t in $SANITY_TESTS; do
    uv run python "tests/sanity/$t.py" >> "$LOG" 2>&1
    rc=$?
    known=0
    case " $KNOWN_FAILING " in *" $t "*) known=1 ;; esac
    if [ "$rc" -eq 0 ] && [ "$known" -eq 1 ]; then
        SANITY_LINES="$SANITY_LINES
| $t | passing — was a known failure |"
        KNOWN_NOW_PASSING="$KNOWN_NOW_PASSING $t"
    elif [ "$rc" -eq 0 ]; then
        SANITY_LINES="$SANITY_LINES
| $t | pass |"
    elif [ "$known" -eq 1 ]; then
        SANITY_LINES="$SANITY_LINES
| $t | fail — known, unchanged |"
    else
        SANITY_LINES="$SANITY_LINES
| $t | **FAIL — new** |"
        NEW_FAILURES=$(( NEW_FAILURES + 1 ))
    fi
    say "  $t: rc=$rc"
done

# ── report ──────────────────────────────────────────────────────────────
PERSON_AFTER=$(sq "select count(*) from person;")
NAMES_AFTER=$(sq "select count(*) from personname;")
DELIVERIES=$(sq "select count(*) from delivery;")

rep "## Imported $NEW_COUNT matches"
rep ""
rep "| | |"
rep "|---|---|"
rep "| Window | $FIRST_NEW → $LATEST_AFTER |"
rep "| Matches in database | $MATCHES_BEFORE → $MATCHES_AFTER |"
rep "| Deliveries | $DELIVERIES |"
rep "| Players on roster | $PERSON_BEFORE → $PERSON_AFTER |"
rep "| Name variants | $NAMES_BEFORE → $NAMES_AFTER |"
rep "| Matches with no country tag | $NULL_COUNTRY |"
rep ""

rep "### Continuity"
rep ""
if [ "${GAP_DAYS:-1}" -le 1 ]; then
    rep "First new match is $FIRST_NEW, one day after the previous latest"
    rep "($LATEST_BEFORE) — the bundle picked up exactly where we left off."
else
    rep "⚠️ First new match is $FIRST_NEW, but the database already went to"
    rep "$LATEST_BEFORE — a ${GAP_DAYS}-day jump. Check whether matches were"
    rep "played in between and missed; if so a full rebuild is the fix."
fi
MISSING_N=$(printf '%s' "${MISSING_DAYS:-0}" | awk '{print $1}')
MISSING_LIST=$(printf '%s' "${MISSING_DAYS:-}" | cut -d' ' -f2-)
if [ "${MISSING_N:-0}" -gt 0 ]; then
    rep ""
    rep "Days with no match at all inside the imported window: $MISSING_N ($MISSING_LIST)."
    rep "A handful is normal off-season; a long unbroken run is not."
fi
rep ""

rep "### Competitions added"
rep ""
rep "| Competition | Matches |"
rep "|---|---|"
# COALESCE: cricsheet leaves event_name null for some bilateral fixtures, and
# a null would collapse the whole concatenation into a blank row.
sq "select '| ' || coalesce(event_name, '(no competition name)') || ' | ' || count(*) || ' |'
    from match
    where substr(dates,3,10) > '$LATEST_BEFORE'
    group by event_name order by count(*) desc limit 15;" >> "$REPORT"
rep ""

rep "### Sanity tests"
rep ""
rep "| Check | Result |"
rep "|---|---|"
printf '%s\n' "$SANITY_LINES" | sed '/^$/d' >> "$REPORT"
rep ""
if [ -n "$KNOWN_NOW_PASSING" ]; then
    rep "A known failure now passes:$KNOWN_NOW_PASSING. Drop it from"
    rep "\`KNOWN_FAILING\` in weekly_update.sh so a future break is caught."
    rep ""
fi

rep "## Needs a human"
rep ""
NEEDS_HUMAN=0
if [ -f "$UNKNOWNS_CSV" ]; then
    NEEDS_HUMAN=1
    rep "**New grounds to attribute.** Each needs a country worked out from"
    rep "the hosting competition and who played there, then folded into"
    rep "\`api/venue_aliases.py\` under BOTH the raw \`\"Ground, City\"\` key and"
    rep "the stripped \`\"Ground\"\` key (the dual-key rule), then"
    rep "\`scripts/fix_venue_names.py\` re-run:"
    rep ""
    rep '```'
    cat "$UNKNOWNS_CSV" >> "$REPORT"
    rep '```'
    rep ""
fi
if [ "$NEW_FAILURES" -gt 0 ]; then
    NEEDS_HUMAN=1
    rep "**$NEW_FAILURES new sanity failure(s)** — triage before committing."
    rep "Details in \`$LOG\`."
    rep ""
fi
KEEPER_CSV="docs/keeper-ambiguous/$TODAY.csv"
if [ -f "$KEEPER_CSV" ]; then
    KEEPER_N=$(( $(wc -l < "$KEEPER_CSV") - 1 ))
    rep "**$KEEPER_N ambiguous wicketkeeper innings** queued in \`$KEEPER_CSV\`."
    rep "Optional — resolving them improves keeper stats but nothing blocks on it."
    rep ""
fi
if [ "$NEEDS_HUMAN" -eq 0 ]; then
    rep "Nothing. Clean run — review the numbers above and ship it."
    rep ""
fi

rep "## Then ship it"
rep ""
rep '```bash'
rep "git add frontend/src/generated/site-stats.json docs/keeper-ambiguous/$TODAY.csv"
rep "git commit      # window, counts, competitions, test status"
rep "bash deploy.sh --first   # re-uploads cricket.db; code-only deploy will NOT carry the data"
rep "git push origin main"
rep '```'
rep ""
rep "Nothing above has been committed or deployed. The database on disk is"
rep "current; the live site is not until that deploy runs."

echo "$TODAY" > "$STAMP"
[ "$NEW_FAILURES" -gt 0 ] && finish 1
finish 0
