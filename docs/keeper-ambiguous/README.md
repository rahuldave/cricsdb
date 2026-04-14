# Keeper Ambiguous Worklist

This directory holds **partitioned ambiguous worklists** for Tier 2
wicketkeeper identification. Full background in
[`../spec-fielding-tier2.md`](../spec-fielding-tier2.md).

## What's in here

Each file is a partition named by the date the run that first
discovered those ambiguous innings was executed:

```
YYYY-MM-DD.csv   — the innings_ids marked ambiguous on that date
```

A partition CSV is **immutable in content** — once an innings_id is
listed in a partition, later runs never move it to a newer file.
Resolutions get added **in-place** by editing the last three columns
of each row.

## File format

```
innings_id,match_id,date,tournament,season,fielding_team,innings_number,
ambiguous_reason,candidate_ids,candidate_names,
resolved_keeper_id,resolved_source,notes
```

| Column | Populated by | Editable? |
|---|---|---|
| `innings_id` through `innings_number` | System (do not edit) | No |
| `ambiguous_reason` | System | No |
| `candidate_ids`, `candidate_names` | System | No |
| `resolved_keeper_id` | You | **Yes** — put the person_id of the actual keeper |
| `resolved_source` | You | **Yes** — e.g. `cricinfo`, `manual`, `scraper:<date>` |
| `notes` | You | **Yes** — free text |

The first 10 columns are the system's output. The last 3 are the
resolution.

## How to resolve a row

1. Open the CSV in VS Code / Excel / Numbers.
2. Find the row by `innings_id`. Cross-reference via the
   deebase admin at `/admin/innings/{innings_id}` if you want context.
3. Fill in:
   - `resolved_keeper_id` — the `person.id` of the actual keeper.
     Usually one of the values in `candidate_ids`, but can be any
     valid person who was in the fielding XI.
   - `resolved_source` — how you know: `cricinfo`, `manual`,
     `scraper:2026-05-01`, `bcci`, etc.
   - `notes` — optional free text.
4. Save the CSV.
5. Run `uv run python scripts/apply_keeper_resolutions.py`.
6. Verify via the scorecard page or admin — `keeper_id`, `method`,
   and `confidence` on the row in `keeper_assignment` should now be
   set to your values with `method='manual'`, `confidence='definitive'`.

The same mechanism handles **overriding a wrong high-confidence
assignment**: append a new row to any partition CSV (easiest: the
latest one) with the `innings_id` and `resolved_keeper_id` filled in.
The system columns can stay blank — apply will overwrite whatever was
there, so the algorithmic guess gets replaced by the manual value.

## Finding person_ids

Person IDs are cricsheet hex strings, e.g. `4a8a2e3b` for MS Dhoni.
Look them up via:

- The player search box on any page (URL shows `?player=<id>`)
- The admin at `/admin/person/` (filter by name)
- A direct SQL query:
  ```bash
  sqlite3 cricket.db "SELECT id, name FROM person WHERE name LIKE '%Dhoni%'"
  ```

## When are partitions created?

- **Full rebuild** (`import_data.py` → `populate_keeper_assignments.populate_full`):
  writes the current day's partition with any ambiguous innings
  that aren't already listed in an earlier partition.
- **Incremental update** (`update_recent.py` → `populate_incremental`):
  appends any newly-ambiguous innings from the new matches to today's
  partition (creates the file if it doesn't exist).

## Persistence across rebuilds

Every run of `populate_full` and `populate_incremental` re-applies
all resolutions from every partition file before finishing. A full
`import_data.py` rebuild therefore preserves every manual correction
(as long as the row stays in the CSV).

## Priority order for disambiguation

The CSV is sorted `(ambiguous_reason, date DESC)` so the highest-value
targets float to the top:

1. `multi_season` — major-league matches with two star keeper-batters
   in the XI (e.g. Kishan+Pant for India). Cricinfo scorecards are
   very reliable for these — a fast scraping pass could fill them.
2. `multi_career` — usually associate-level ambiguities or mid-tier
   leagues. Cricinfo has some, manual research for the rest.
3. `multi_team_ever` — smaller teams with two historical keepers in
   one XI. Case-by-case.
4. `no_candidate` — associate / minor cricket with sparse data.
   Keeper may never have stumped anyone in cricsheet's record; needs
   external sources or may be genuinely unresolvable.
5. `multi_stumpers_same_innings` — extremely rare (5 matches total).
   Cricsheet data anomaly, usually a mid-innings keeper change or a
   data entry error. Investigate per case.
6. `stump_fielder_unresolved` — stumping happened but we couldn't
   resolve the fielder's name to a person_id. Add them to
   `fielder_aliases.py` (Tier 1) instead of resolving here.
