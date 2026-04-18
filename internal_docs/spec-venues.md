# Spec: Venues (enhancement S)

Status: **Phases 1 + 2 shipped 2026-04-17.** Phase 3 (per-venue
dossier) remains opt-in after Phases 1+2 prove thin or sufficient.

**Phase 1 result**: 12,940 existing matches canonicalized. 676 raw
(venue, city) pairs collapsed to 456 canonical venues across 88
countries. Zero unknowns. `api/venue_aliases.py`, `scripts/fix_venue_names.py`,
`scripts/generate_venue_worklist.py` are the live modules;
`match.venue_country` TEXT NULL added to the schema. `import_data.py`
and `update_recent.py` canonicalize on insert via `resolve_or_raw()`;
unknown venues are logged to `docs/venue-worklist/unknowns-<date>.csv`
at end of run. Soft-fail contract: unknown venues never block import.

**Phase 2 result**: `filter_venue` is an ambient filter across every
tab. `FilterParams.build()` + `reference.py::list_teams` +
`tournaments.py::_build_filter_clauses` all honour it (3-line
additions per helper; 68 other endpoints cover via `filters.build()`
automatically). New `/api/v1/venues` (typeahead; `q` substring match
on venue or city; top-50 cap when `q` absent) and
`/api/v1/venues/landing` (country-grouped tiles). Both self-strip
`filter_venue` from their own filter chain. Frontend adds
`components/VenueSearch.tsx` (typeahead, chip mode when active),
`components/venues/VenuesLanding.tsx` (country accordion, top-3 open),
`pages/Venues.tsx`, the `/venues` route, and a Venues nav slot
between Players ▾ and Head to Head (7 → 8 top-level tabs). Every
page's `filterDeps` array + 5 carry functions patched to include
`filters.filter_venue` (SPA navigation refetches, back button works).
Regression harness: 18/18 REG byte-identical, 9/9 NEW queries differ
as intended.

## Motivation

Cricsheet carries `match.venue` (the ground name) and `match.city`
(the host city) on every match. Neither field is canonicalized.
Users today cannot ask two kinds of questions:

1. **"X at venue Y"** — Kohli at Wankhede, India at MCG, IPL
   matches at Chepauk. Every tab in the app (Teams, Players,
   Head-to-Head, Matches, Series) benefits from a venue scope;
   today there's no way to apply one.
2. **"What's this ground like?"** — avg first-innings total, bat-
   first win %, toss-decision split, boundary %. These are *venue-
   as-entity* stats — pitch and dew character, ground dimensions —
   and don't belong on any other tab.

## Shape of the three phases

**Phase 1 — DB cleanup** (½ day + human review). Canonicalize venue
names so queries aren't fragmented across spelling variants
(Chittagong/Chattogram) or ambiguous (six "County Ground"s).
Nothing user-visible changes yet.

**Phase 2 — `filter_venue` + landing** (~1 day). Add `filter_venue`
to `FilterParams.build()` + `build_side_neutral()` and surface it
as a FilterBar selector. Add a flat `/venues` landing page for
discovery. Every existing tab instantly gains venue scoping; no
per-venue dossier yet.

**Phase 3 — Venue dossier** (~1 day, optional after Phase 2 ships).
Per-venue page `/venues?venue=X` with the venue-character overview
panel plus Batters / Bowlers / Fielders leaders (all `filter_venue`-
derived) and a matches list. Decide after Phase 2 whether this
feels thin enough to skip.

---

## Phase 1 — Database cleanup

### The data problem (from 2026-04-16 research)

- `match.venue` — 631 distinct strings.
- `match.city`  — 281 distinct, 81 matches have `city = NULL`.
- Known failure modes:
  - **Same name, different grounds.** `"County Ground"` appears as
    the literal name of six English grounds (Taunton, Bristol,
    Chelmsford, Northampton, Derby, Hove). `(venue, city)` is the
    compound key that disambiguates.
  - **Spelling variants.** Chittagong ↔ Chattogram, Bangalore ↔
    Bengaluru, Mumbai ↔ Bombay in older match records.
  - **City NULL on known grounds.** Wankhede exists in scope with
    `city = NULL` for some matches — trivially fillable.
  - **Suffix drift.** "Wankhede Stadium" vs "Wankhede Stadium,
    Mumbai" vs "Wankhede" — same ground.
  - **Stray punctuation / whitespace.**

### Design: alias table + in-place rewrite

Mirror the existing patterns for teams (`team_aliases.py`) and
tournaments (`tournament_canonical.py`). **No schema change.** The
cleanup is a Python module + a post-import rewrite step.

```
api/venue_aliases.py           — canonical mapping (the source of truth)
scripts/fix_venue_names.py     — idempotent rewrite applied to match.venue / match.city
scripts/generate_venue_worklist.py — emits the CSV the user reviews
docs/venue-worklist/YYYY-MM-DD-worklist.csv — the round-tripped artefact
```

### Canonical key and display name

- **Key**: the canonical venue name *plus* the canonical city. The
  six "County Ground"s resolve to `"County Ground (Taunton)"`,
  `"County Ground (Bristol)"`, … — display names disambiguated by
  city in parens where ambiguity exists, bare elsewhere.
- **City**: always filled, always canonical (Chittagong → Chattogram;
  Bombay → Mumbai for post-1995 rename).
- **Country**: added as a derived field. Grouping the landing by
  country is the UX goal — currently we'd infer from city, but
  venue_aliases should carry it explicitly so the dossier can show
  a country flag without a lookup.

### `venue_aliases.py` shape

```python
# Each entry: (raw_venue, raw_city_or_None) → (canonical_venue, canonical_city, country)
VENUE_ALIASES: dict[tuple[str, str | None], tuple[str, str, str]] = {
    ("Wankhede Stadium", "Mumbai"):        ("Wankhede Stadium", "Mumbai", "India"),
    ("Wankhede Stadium", None):            ("Wankhede Stadium", "Mumbai", "India"),
    ("Wankhede",          None):           ("Wankhede Stadium", "Mumbai", "India"),
    ("Zahur Ahmed Chowdhury Stadium", "Chittagong"):
        ("Zahur Ahmed Chowdhury Stadium", "Chattogram", "Bangladesh"),
    ("County Ground", "Taunton"):
        ("County Ground (Taunton)", "Taunton", "England"),
    # … etc.
}

def resolve(raw_venue: str, raw_city: str | None) -> tuple[str, str, str] | None:
    """Returns (canonical_venue, canonical_city, country) or None if unknown."""
    return VENUE_ALIASES.get((raw_venue, raw_city)) \
        or VENUE_ALIASES.get((raw_venue, None))
```

Unknown `(raw_venue, raw_city)` pairs: `fix_venue_names.py` emits a
warning, leaves the row unchanged, and writes the unknowns to a
`docs/venue-worklist/unknowns.csv`. Next user-review cycle folds
them into the alias file.

### `fix_venue_names.py`

- Runs after `populate_full` in `import_data.py` (full rebuild) and
  after `populate_incremental` in `update_recent.py` (incremental).
- Idempotent: running twice is a no-op.
- For every match, calls `venue_aliases.resolve(raw_venue, raw_city)`
  and `UPDATE match SET venue=?, city=? WHERE id=?` if the pair
  changes. Country goes into `match.venue_country` (new column).
- **One schema addition**: `match.venue_country` TEXT NULL. Cheap
  and it saves a lookup per row.

### The human-in-the-loop process (how we work together)

The "County Ground × 6" rows require a human who knows English
county cricket. Here's the round-trip.

1. **I generate the worklist** (`scripts/generate_venue_worklist.py`).
   Queries every distinct `(venue, city)` pair from `match`, joins
   against `venue_aliases.py` to mark rows already covered. Emits
   `docs/venue-worklist/2026-MM-DD-worklist.csv`:
   ```
   raw_venue, raw_city, match_count, sample_match_id, sample_date,
   proposed_canonical_venue, proposed_canonical_city, proposed_country,
   needs_review
   ```
   Pre-fills `proposed_*` for the obvious cases (trivial suffix,
   known spelling variants, city-fillable-from-sibling-rows).
   `needs_review = TRUE` for anything where I'm not confident.
2. **You review the CSV.** Filter to `needs_review = TRUE` rows.
   Fill in `proposed_canonical_venue` / `proposed_canonical_city` /
   `proposed_country`. For the six "County Ground"s you tell me
   which county each one is — that's the one thing I can't guess
   without English-cricket knowledge. For any row you want
   to drop from canonicalization (keep raw), set all proposed
   cells blank.
3. **You commit the filled CSV** back to `docs/venue-worklist/`.
   This is the artefact of record — auditable, diff-able.
4. **I ingest** — a script reads the CSV and emits the
   `VENUE_ALIASES` dict into `api/venue_aliases.py`. Hand-editable
   afterwards; the CSV round-trip is the source of truth for bulk
   changes, hand edits for quick fixes.
5. **I run `fix_venue_names.py`** against a copy of the prod DB in
   `/tmp` (per `internal_docs/testing-update-recent.md`). Sanity
   queries: distinct-venue count before/after (should drop), spot
   checks on a handful of canonicalized names.
6. **I deploy** — the canonicalization ships with the DB on the
   next `deploy.sh --first`. Between DB rebuilds, the `fix_venue_names.py`
   hook in `update_recent.py` keeps incremental imports clean.

Estimated human time: ~30-60 minutes for a few hundred rows of
review, most of it on the tail of ambiguous grounds.

### Phase 1 verification

- `SELECT COUNT(DISTINCT venue) FROM match` — lower than before.
- `SELECT venue, COUNT(DISTINCT city) FROM match GROUP BY venue HAVING COUNT(DISTINCT city) > 1`
  — zero rows, or only ones we explicitly accepted as multi-city (shouldn't exist after cleanup).
- `SELECT COUNT(*) FROM match WHERE venue_country IS NULL` — zero.
- Spot-check 10 random matches in `/admin/match` to confirm the
  canonicalized values look right.

### Phase 1 docs

- `internal_docs/data-pipeline.md` — new paragraph on the venue
  cleanup hook (runs after `populate_full` / `populate_incremental`).
- `internal_docs/design-decisions.md` — entry on canonical venue
  keying (why `(venue, city)` + why in-place rewrite over FK).
- `CLAUDE.md` — known-issues section notes the DB is now
  venue-canonicalized; `venue_aliases.py` is the source of truth.

---

## Phase 2 — `filter_venue` + Venues landing

### Backend

**`FilterParams` changes** (`api/filters.py`):

```python
def __init__(
    self,
    …,
    filter_venue: Optional[str] = Query(None),
):
    …
    self.venue = filter_venue

def build(self, …):
    …
    if self.venue:
        clauses.append(f"{table_alias}.venue = :filter_venue")
        params["filter_venue"] = self.venue

def build_side_neutral(self, …):
    # same clause — venue is a match-level property, side-symmetric
```

Every endpoint that uses `filters.build()` or `build_side_neutral()`
gains venue scoping for free. That's ~all of them.

**New endpoint `GET /api/v1/venues`** (for the FilterBar dropdown):

Returns venues in the current scope with match counts, like
`/api/v1/tournaments` and `/api/v1/seasons`. Response:

```json
{
  "venues": [
    { "venue": "Wankhede Stadium", "city": "Mumbai", "country": "India", "matches": 842 },
    …
  ]
}
```

Accepts the same scope inputs as `/api/v1/tournaments`: `team`,
`opponent`, `gender`, `team_type`, `tournament`. Narrows the dropdown
so picking India + Men's + IPL shows only venues in that scope.

**New endpoint `GET /api/v1/venues/landing`** (for the `/venues`
page):

```json
{
  "by_country": [
    { "country": "India",     "venues": [ { "venue": …, "city": …, "matches": … }, … ] },
    { "country": "Australia", "venues": [ … ] },
    …
  ]
}
```

Countries ordered by total match count desc; venues within a country
ordered by match count desc. Filter-sensitive (gender / team_type /
tournament / season), so narrowing the FilterBar narrows the tile
grid.

### Frontend: FilterBar

Add a **Venue** selector after Tournament, before Seasons. Same
pattern as Tournament: typeahead dropdown over the `/api/v1/venues`
response, scoped to the current FilterBar state (team, gender,
team_type, tournament). Pick → sets `filter_venue=` URL param; clear
button removes it.

No auto-narrow logic for venue — unlike Tournament (which feeds
auto-fill of gender/team_type), venue is ambient. A single venue
can host men's + women's + international + club matches, so no
constraint to propagate.

### Frontend: `/venues` landing page

- Route `/venues`. Search-bar at the top (like Teams / Players).
- Landing renders a tile grid grouped by country. Each country has
  a heading (flag + name + total matches) and a two-column tile
  list: "Wankhede Stadium · Mumbai · 842".
- Tile click sets `filter_venue` in the URL and navigates to
  `/matches?filter_venue=<venue>` — the default drilldown (shows
  the match list scoped to that venue).
- No per-venue dossier yet — that's Phase 3.

### Nav slot

Add **Venues** as a top-level nav item between Players and
Head-to-Head:

```
Series | Teams | Players ▾ | Venues | Head to Head | Matches
```

Alphabetical-ish and sensible-flow — person → place → matchup.

### Phase 2 verification

- **Browser flows (via `agent-browser`):**
  - Pick India on Teams tab, then set Venue to Wankhede via the
    FilterBar. Every tab's stats scope to India-at-Wankhede.
  - Pick Kohli on Players tab, then set Venue to MCG. Role line
    + all bands narrow to MCG matches.
  - Head-to-Head Kohli vs Starc + Venue = MCG.
  - Series dossier + Venue filter: "IPL matches at Chepauk".
  - `/matches?filter_venue=Wankhede` — bare match list scoped.
  - `/venues` landing — tiles group by country, click one goes
    to `/matches` with `filter_venue` set.
  - FilterBar venue dropdown: narrow team + tournament, confirm
    dropdown only shows venues in that scope.
- **Regression** (per `internal_docs/regression-testing-api.md`):
  Because `FilterParams.build()` changes, run the HEAD-vs-patched
  md5-diff harness on every endpoint that uses filters. Without a
  `filter_venue` query param, every endpoint must return
  byte-identical results (REG). With `filter_venue=X`, responses
  should differ (NEW). Required pass count reported in the ship
  commit.

### Phase 2 docs

- `docs/api.md` — `/venues`, `/venues/landing` endpoints with curl
  examples; `filter_venue` listed in the common-filters table.
- `internal_docs/codebase-tour.md` — new `components/venues/` folder
  (at least the landing component this phase).
- `CLAUDE.md` — tabs list updated (7 → 8 top-level); new
  Landing-pages entry for Venues.
- `frontend/src/content/user-help.md` — paragraph on the Venue
  filter + Venues tab.

---

## Phase 3 — Venue dossier

Only start after Phase 2 ships *and* feels thin enough to justify
the extra work. The Phase 2 FilterBar + landing may already cover
90% of what users want; the dossier earns its keep only by
surfacing venue-character stats.

### Route + nav

- `/venues?venue=<canonical_name>` — dossier for a single venue.
- Landing tiles (from Phase 2) now link to `/venues?venue=<X>`
  instead of `/matches?filter_venue=<X>`. The dossier has a
  "View all matches →" link back to `/matches?filter_venue=<X>`
  for users who want the bare list.

### Dossier tabs

```
Overview | Batters | Bowlers | Fielders | Matches | Records
```

- **Overview**: the venue-character panel — the ONLY truly
  venue-unique content.
  - Matches hosted, broken down by tournament × gender × season
    (table + sparkline).
  - Avg 1st-innings total (overall, and split by bat-first/chase
    side).
  - Bat-first win % vs chasing win %.
  - Toss-decision pie (bat vs field) + per-decision win rate
    (the "at this venue, captains who win the toss choose to
    bowl 80% of the time and those teams win 60%" story).
  - Boundary % (per phase — PP / middle / death).
  - Dot-ball %.
  - Highest / lowest team totals.
- **Batters**: `/batters/leaders?filter_venue=<X>&…` — top-10
  by runs, by strike rate, by average.
- **Bowlers**: `/bowlers/leaders?filter_venue=<X>&…` — top-10
  by wickets, by economy, by strike rate.
- **Fielders**: `/fielders/leaders?filter_venue=<X>&…` — user-
  requested in-session; included.
- **Matches**: `/matches?filter_venue=<X>&…` — embedded list.
- **Records**: highest team total, lowest all-out, biggest win
  (runs + wickets), best bowling figures, best batting score,
  biggest partnership. If the series records endpoint
  (`/api/v1/series/records`) composes with `filter_venue`, reuse
  it; otherwise a thin `/venues/{venue}/records` wrapper.

### New endpoints (Phase 3 only)

**`GET /api/v1/venues/{venue}/summary`** — the Overview panel
bundle. Returns:

```json
{
  "venue": "Wankhede Stadium",
  "city": "Mumbai",
  "country": "India",
  "matches": 842,
  "by_tournament_gender_season": [ … ],
  "avg_first_innings_total": 172.4,
  "bat_first_win_pct": 47.2,
  "chase_win_pct":     52.8,
  "toss_decision_split": { "bat": 310, "field": 532 },
  "toss_and_win_pct":  … ,
  "boundary_pct_by_phase": { "pp": 17.1, "middle": 13.4, "death": 21.2 },
  "dot_pct": 38.7,
  "highest_total": { "runs": 263, "match_id": 1234, … },
  "lowest_all_out": { "runs": 67, "match_id": 5678, … }
}
```

Other tabs reuse existing endpoints with `filter_venue`. Zero
additional backend work for Batters / Bowlers / Fielders / Matches
tabs.

### Frontend: `components/venues/`

```
components/venues/
  VenueDossier.tsx         — tab strip + panel host
  VenueOverviewPanel.tsx   — the Overview content
  VenuesLanding.tsx        — (already present from Phase 2)
  venueUtils.ts            — carryVenueFilters etc.
```

Mirrors `components/tournaments/TournamentDossier.tsx` — single-
entity deep view (not N-way compare, so don't mirror
`components/teams/`). Reuse `DataTable`, `BarChart`,
`PartnershipLeaderboard` where applicable.

### Phase 3 verification

- Each dossier tab loads, respects the full FilterBar scope, and
  cross-links sensibly (Batter name in leaders → player page with
  `filter_venue` carried).
- Overview numbers sanity: avg 1st-inn at Wankhede should be
  ~160-180 range (IPL-heavy high-scoring ground); at Chepauk
  should be lower (spin-friendly, lower first-inn totals).
- Bat-first win % at dew-heavy grounds (Wankhede, Chinnaswamy) <
  50%; at Chepauk ≥ 50%.
- If those gut-checks fail, the pipe is wrong somewhere.

### Phase 3 docs

- `docs/api.md` — `/venues/{venue}/summary` endpoint.
- `internal_docs/codebase-tour.md` — `components/venues/` folder
  expanded.
- `CLAUDE.md` — Landing-pages entry updated to reflect dossier
  content.
- `user-help.md` — dossier screenshot + paragraph.
- `internal_docs/enhancements-roadmap.md` — mark S shipped.

---

## URL scheme summary

- `?filter_venue=<canonical_venue>` — the filter param, works on
  every existing tab.
- `/venues` — landing.
- `/venues?venue=<canonical_venue>` — Phase 3 dossier.
- `/venues?venue=X&tab=Batters` — dossier sub-tab.

`filter_venue` is URL-safe (canonical names don't contain `&` or
`#`; parens around county names survive URL-encoding fine).

## Resolved design decisions (2026-04-17)

1. **Worklist CSV mechanics — committed file in `docs/venue-worklist/`.**
   Round-trip through git: I generate, you edit (in any tool —
   Numbers, VSCode, or a Google Sheet export/re-import), you commit
   the edited CSV. Auditable and diff-able, fits the existing
   `docs/keeper-ambiguous/` pattern.
2. **Naming style — `"{raw name} ({city})"` as the disambiguator of
   last resort.** Applied only when the raw name alone would match
   ≥2 grounds in our data (the six "County Ground"s, plus any
   similar collisions the worklist surfaces). Where a ground has a
   universally-known canonical name (`M. A. Chidambaram Stadium`,
   `Wankhede Stadium`), use that without parens. The rule is
   "minimal intervention": canonicalize spelling, fill NULL cities,
   disambiguate only where genuinely ambiguous.
3. **Multi-city venues — handled by alias density, not architecture.**
   The resolver supports N raw keys → 1 canonical triple, so
   Sharjah-labelled-UAE + Sharjah-labelled-Sharjah + Sharjah-NULL
   all map to the same `("Sharjah Cricket Stadium", "Sharjah",
   "United Arab Emirates")` entry. Non-issue once the alias table
   exists.
4. **Phase 3 trigger — qualitative.** After Phase 2 ships, use the
   tool for a session or two. If venue-character questions keep
   coming up that the FilterBar alone can't answer (avg 1st-inn,
   bat-first win %, toss-decision pie, boundary % by phase), build
   Phase 3. Otherwise defer indefinitely. No analytics-based
   threshold — there's no analytics layer to lean on.
5. **Indexing — defer until measured.** Post-Phase-2, run
   `EXPLAIN QUERY PLAN` on a representative query (e.g.
   `/api/v1/teams/India/by-season?filter_venue=X`). If a `SCAN match`
   shows up costing >50ms, add `CREATE INDEX ix_match_venue ON
   match(venue)` via the idempotent pattern in
   `internal_docs/perf-leaderboards.md`. Diagnose-then-index.

## Risks

- **Canonicalization volume unknown.** Could be 50 rows needing
  user review, could be 200. Mitigation: worklist script runs
  first, surfaces the scale, we re-estimate before committing.
- **Re-import overwrite.** `import_data.py` pulls fresh cricsheet
  YAML which has the raw (uncanonicalized) venue. Mitigation:
  `fix_venue_names.py` is a post-populate hook on BOTH
  `import_data.py` and `update_recent.py`; belts-and-braces test
  after every incremental update.
- **Series dossier + `filter_venue`.** Need to verify the existing
  series handlers honour the new filter. Covered by the regression
  harness in Phase 2 verification.

---

## Sequencing (condensed)

**Phase 1 session:**
1. I write `scripts/generate_venue_worklist.py`.
2. Run it, commit the draft CSV to `docs/venue-worklist/`.
3. You review + fill in the `needs_review` rows. Commit the filled CSV.
4. I ingest → `api/venue_aliases.py`, add `match.venue_country` column,
   write `scripts/fix_venue_names.py`, hook into import_data +
   update_recent. Run against `/tmp` DB copy; sanity-check.
5. Commit + deploy (DB rebuild or incremental apply).

**Phase 2 session:**
1. `FilterParams` + `/api/v1/venues` + `/api/v1/venues/landing`.
2. Regression-test all filter-consuming endpoints.
3. FilterBar Venue selector component.
4. `/venues` landing page + `components/venues/VenuesLanding.tsx`.
5. Browser verification per flow list above.
6. Docs pass + commit + deploy.

**Phase 3 session (only if Phase 2 feels thin):**
1. `/api/v1/venues/{venue}/summary` endpoint.
2. `components/venues/VenueDossier.tsx` + `VenueOverviewPanel.tsx`.
3. Tile-click navigation switches from `/matches?filter_venue=X` to
   `/venues?venue=X`.
4. Browser verification.
5. Docs pass + commit + deploy.
