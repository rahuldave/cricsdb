# CricsDB — T20 Cricket Analytics Platform

Live: https://t20.rahuldave.com · Repo: https://github.com/rahuldave/cricsdb · deebase PR: https://github.com/rahulcredcore/deebase/pull/8

CLAUDE.md is the **inviolable-rules file**. Everything describing what the codebase IS (files, endpoints, payloads, formulas, design history) lives in dedicated docs — go there before assuming.

## Contents

1. [Pointers (doc index)](#pointers)
2. [Running locally + deploying](#running-locally--deploying)
3. [Documentation discipline](#documentation-discipline)
4. [Methodology rules](#methodology-rules)
5. [Code patterns](#code-patterns) — pointer
6. [Testing discipline](#testing-discipline) — pointer
7. [Cricket invariants](#cricket-invariants) — pointer
8. [Page conventions](#page-conventions) — pointer
9. [Palette](#palette)
10. [Splits Mosaic](#splits-mosaic)

---

## Pointers

**Orientation**
- Codebase tour: `internal_docs/codebase-tour.md`
- React + Vite primer (this codebase): `internal_docs/react-primer.md`
- Frontend build pipeline: `internal_docs/frontend-build-pipeline.md`
- Visual identity / Wisden styles: `internal_docs/visual-identity.md`
- Color discipline (palettes, reference lines, swatch alignment): `internal_docs/colors.md`
- Local dev prerequisites + REPL: `internal_docs/local-development.md`
- **Semiotic v3 gotchas (canvas vs SVG, opacity props, `pieceStyle` replace-not-merge trap, lookup workflow): `internal_docs/semiotic-notes.md`** — read BEFORE writing any Semiotic chart code

**Rules detail (subordinate to this file)**
- Code patterns (router imports, ChartContainer, extend-don't-fork, ScopedPageHeader, URL-clean, chip↔chart, rate-vs-volume, cascade-clear, no-hacks): `internal_docs/code-patterns.md`
- Testing discipline (SQL-anchored expecteds, every-call-site, sparkline bar count, /summary anchor): `internal_docs/testing-discipline.md`
- Roughdraft spec-review workflow + CriticMarkup syntax: `internal_docs/roughdraft-workflow.md`

**Domain + UX**
- Landing pages on every search-bar tab + Compare slots + Series/H2H/Venues structure: `internal_docs/landing-pages.md`
- API reference (every endpoint, curl, response): `docs/api.md` — also `/api/docs` (Swagger) and `/api/redoc`
- Stat formulas: `internal_docs/how-stats-calculated.md`
- Server-vs-client calc inventory + cross-endpoint divergence audit: `internal_docs/server-vs-client-calcs.md` — read before changing any predicate or shipping a new derived metric
- Design decisions: `internal_docs/design-decisions.md`
- URL state discipline: `internal_docs/url-state.md`
- Link components (TeamLink / PlayerLink / SeriesLink contract — read before writing ANY navigation): `internal_docs/links.md`
- Inning-controls mount-site inventory (InningToggle / Splits Mosaic per route × subtab — read before adding/moving either widget): `internal_docs/inning-controls-mount-sites.md`

**Data + ops**
- Data pipeline: `internal_docs/data-pipeline.md`
- Smoke-test update_recent against /tmp DB: `internal_docs/testing-update-recent.md`
- Deploying: `internal_docs/deploying.md`

**Performance**
- Leaderboard landings: `internal_docs/perf-leaderboards.md`
- deebase pool / async SQLite: `internal_docs/perf-async-deebase.md`
- Compare-tab page-load: `internal_docs/perf-bucket-baselines.md`
- Systems / perf catch-all: `internal_docs/systems-followups.md`

**Testing**
- Test catalogue: `internal_docs/tests.md`
- Regression harness: `internal_docs/regression-testing-api.md` + `tests/regression/`

**Active work**
- Next-session agenda + NO-DEPLOYS gate: `internal_docs/next-session-ideas.md`
- A–Q lettered roadmap, dated session logs, deferred queue: `internal_docs/enhancements-roadmap.md`
- Build-ready specs: `internal_docs/spec-inning-split.md`, `internal_docs/spec-filterbar-team-class-v3.md`, `internal_docs/spec-filterbar-team-class-club.md`, `internal_docs/spec-distribution-stats.md`, `internal_docs/spec-splits-mosaic.md`, `internal_docs/splits-mosaic-cross-page.md`, `internal_docs/spec-rate-vs-volume-audit.md` (next-up Phase I — absolute-vs-per-innings tile/chart hygiene; backend extensions front of doc)
- Club-tier classification: `internal_docs/club-tier-classification.md` + anchor numbers `internal_docs/club-tier-anchor-numbers.md`

---

## Running locally + deploying

```bash
# Terminal 1 — backend (ALWAYS --reload; bare uvicorn serves stale code)
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` → port 8000.

```bash
bash deploy.sh           # code-only (DB persists on plash)
bash deploy.sh --first   # uploads cricket.db (~435 MB)
```

Type-check with `tsc -b` or `npm run build` — `tsc --noEmit` is a no-op here (root tsconfig has `files: []`).

Prereqs, REPL, troubleshooting: `internal_docs/local-development.md`. Deploy details: `internal_docs/deploying.md`.

---

## Documentation discipline

**READ `internal_docs/docs-sync.md` before claiming any feature done.** It is the update-map (API route → `docs/api.md`, design decision → `design-decisions.md`, palette → `colors.md`, etc.) and the regression REG→NEW flip-order workflow.

**Update the affected sections IN that doc** at the end of every feature. CLAUDE.md is rules, not history; new history goes in the right named doc.

---

## Methodology rules

### Plain language — explain to the user without jargon

When **talking to the user** (summaries, explanations, status updates, bug
diagnoses, question prompts), use plain English. The user is sharp but is
NOT here to decode internal shorthand. This is a hard rule — flagged
repeatedly (2026-05-26: "Your language is so complicated that I can't
understand at all"; "I have zero clue what you mean").

- **No code/DB identifiers as nouns.** Don't say "playerscopestats", "the
  cohort baseline", "primarySlotOf", "`_inning_extras`", "scope_avg",
  "per-event clause" in prose meant for the user. Name the thing by what
  the user SEES ("the grey 'typical player' comparison number", "the left
  column of the comparison", "the innings filter").
- **No unexplained stat/cricket shorthand or project coinages** —
  "per-event", "cohort", "POV-flip", "match-subset", "envelope",
  "marginal". If a precise term is genuinely needed, define it in the same
  sentence in everyday words.
- **Lead with the plain-English point**, then the detail. If you catch
  yourself writing a noun pile-up ("distribution cohort baselines stay
  full-scope under inning"), stop and rewrite it as a sentence a cricket
  fan who doesn't code would understand.
- Applies to prose only — code, code comments, commit messages, and the
  internal `spec-*.md` / memory files keep their precise vocabulary.
- Tell: you're about to send a sentence with 2+ snake_case/camelCase
  tokens or a chain of 3+ abstract nouns. Rewrite before sending.

### Commit cadence — one feature, one commit, immediately

**Commit as soon as a feature looks complete — don't batch.** One logical change per commit, committed at the moment it reaches a runnable state (type-check passing, feature working in the browser, tests still green). If you just finished X and X works, commit X before starting Y. Even if Y is the obvious next step — the atomicity is the point.

Why: sessions that accumulate 30 files of uncommitted work across five unrelated features make `git bisect` useless. Lost-bisect debugging is expensive; small commits are free.

User has flagged this repeatedly. Tells you're about to violate it:
- You've made 3+ working changes and haven't committed.
- You're tempted to "finish the whole arc" before committing.
- You're using `git add -A` because the diff sprawls. → Use `git add -p` to split.

### Filter-combination testing — the matrix is mandatory

The app's premise is **consistent comparisons across all filter combinations**. A delta that works at `team=X` but disappears at `team=X&filter_venue=Y` is a bug. User feedback 2026-05-11: "things need to be consistent on filtration" — flagged after Wankhede + toss filter lost its league-baseline chips.

When a change touches anything that depends on FilterBar / AuxParam state (deltas, league-avg chips, marginals, baselines), exercise this matrix:

- No team selected (landing view) + a narrowing filter (`filter_venue=...`, opponent, single season).
- Team selected + same narrowing filters (venue, opponent, season).
- Team selected + aux filter (`toss_outcome`, `inning`, `result`) AND a narrowing together (e.g. `team=MI&filter_venue=Wankhede&toss_outcome=won`).
- Bowling tab + inning filter (the inning POV flip).
- Multiple filters chained (`&season_from=2018&season_to=2020&filter_venue=...`).

Regression + tsc + curl are NOT substitutes. **Load the actual page in agent-browser, click the actual controls, verify the rendered DOM at each combination.**

### UI verification — browser-agent + mobile, every time

After any change to `frontend/src/`:
1. Use the `agent-browser` skill to load affected pages in a real browser, exercise every new tab/component, hover interactive elements, click every link to confirm navigation.
2. **Mobile viewport check is not optional.** `agent-browser set viewport 390 844` then `reload` BEFORE committing. Reproduce the user's exact URL at both 1280 and 390 widths.

Common mobile failure modes:
- Inline `style={{gridTemplateColumns: 'minmax(0, 1fr) minmax(220px, …)'}}` silently zeros the first column on a 342-wide panel — histogram/chart becomes invisible. Inline styles can't do media queries; extract to a `wisden-*` class in `index.css` with `@media (max-width: 720px) { grid-template-columns: 1fr }`.
- Inline rows (toggles, milestone chips, form-delta lines) overflow without `flex-wrap: wrap`.
- `grid-template-columns: repeat(N, 1fr)` with N > 3 needs to drop on mobile.

A frontend change is not "done" until both desktop AND mobile look right. `tsc -b` and `npm run build` verify code correctness, not feature correctness.

### Bug reports — reproduce, propose, WAIT

When the user reports a bug or asks why something looks/behaves a certain way:

1. **Reproduce.** Load the URL with agent-browser, query the DB, run the test. Confirm what's actually wrong before forming a hypothesis. Phrases like "this might be because…", "probably the X is Y…", "I bet the issue is…" are tells that you're about to ship a speculative fix — STOP and verify first.
2. **Identify the root cause.** Name the actual mechanism — code path, data state, design choice — not a plausible-sounding guess.
3. **Explain what you found AND propose 1–3 fixes with trade-offs.** Two-three sentences each, not a wall of code.
4. **WAIT.** Do NOT ship the fix in the same turn unless explicitly told to ("just fix it"). The user knows their codebase; they may pick a different fix, OR decide the behavior is correct.

Bug reports often LOOK like routine fixes but turn out to be design questions in disguise. Auto mode is NOT a license to skip this — auto mode is for routine work, not bug-fix decisions.

Tells you're about to skip the rule:
- You jump to an Edit before reading the surrounding code.
- You announce "Going to ship this now" / "Implementing the fix" before the user has confirmed the diagnosis.

### Do NOT defer parts of an assigned task

When the user gives you a task — "add per-page Twitter cards", "wire up X for the whole app" — finish it. Don't ship the easy half and pitch the rest as a follow-up. If a part is genuinely out-of-scope or needs a different design call, ASK before cutting it. The "shipped + deferred" pattern reads as scope-shaving and forces the user to re-prompt.

### Audit prompt discipline — raw output, not verdicts

When asking agent-browser to verify, ask for RAW OUTPUT, not summaries. "List every section header with the first row label per column" is checkable. "Verify all sections render" is a verdict that drops information — when the agent reports PASS but walked the wrong cells, the bug ships.

For each assertion you'd put in an integration test, **write the test AT THE SAME TIME**, not after a bug surfaces. One-shot browser audits are exploratory; checked-in `tests/integration/<feature>.sh` assertions are durable.

### Red-then-green test discipline

Every fix gets a test that demonstrates the bug (red against HEAD), THEN the fix (green). Report both phases in the commit message. A green-only test ships a fix that may or may not address the actual bug.

### Perf changes — measure after every single change

When optimizing, make ONE change at a time and measure it in isolation. Do not stack 2–3 changes and measure at the end.

Why: batched measurements can't tell you which change moved the number. If the final result is faster, slower, or flat, you can't decide which change to keep, drop, or extend. You also can't notice when one change cancelled out the gain from another — the way `lite=true` skipping the 3 GROUP BY queries hid the actual cost of restoring them when `lite` was deleted in the next iteration (2026-05-14 /series perf work).

A perf pass should look like:
1. Baseline timing recorded.
2. Change A. Measure. Record delta.
3. Change B. Measure. Record delta.
4. Change C. Measure. Record delta.

If a commit message claims a perf win, the win should be measurable in isolation — gather one query, time it; gather another, time it; etc.

Tells you're about to violate this:
- Several refactors stacked without a baseline timing between them.
- Vague claims like "this should be faster" without a number-vs-number comparison.
- Switching to a precomputed table AND parallelizing the query AND deleting an endpoint in one commit.

### Spec review via Roughdraft

This codebase keeps build-ready specs in `internal_docs/spec-*.md`. When the user wants to review a new or edited spec, use **Roughdraft** — a local single-file Markdown viewer that round-trips CriticMarkup comments through a browser pane. User may call it `rd` in conversation; do NOT create any shell alias / symlink / command named `rd`.

When the user asks for a plan, write the plan as a Markdown file on disk BEFORE asking for review — drop it under `internal_docs/spec-*.md`.

`roughdraft open "<abs/path/to/spec.md>"` opens one file at a time and starts Roughdraft if not running. **Leave the command running** — the wait IS the signal; it exits when the user clicks Done Reviewing. (Known issue: `roughdraft watch` hits a Node 25 / undici 60s headers timeout — the browser window IS open at `http://localhost:7373/?path=...` even if the CLI errors with `HeadersTimeoutError`.)

Full CriticMarkup syntax + spec-review flow steps: `internal_docs/roughdraft-workflow.md`.

---

## Code patterns

Detailed rules and their tells live in `internal_docs/code-patterns.md`. Headline list:

- **Router imports must come from shipped paths** — `api/routers/*.py` cannot import from `scripts/` / `tests/` (resolves locally, 500s in prod).
- **Chart wrappers — header lives OUTSIDE the positioning context** — use `<ChartContainer>` whenever overlays are absolute-positioned.
- **Extend existing abstractions — do NOT fork parallel helpers** — `TeamLink` / `PlayerLink` / `SeriesLink` / `DataTable` / `Score` / `MetricDelta` / `scopeLinks.ts` each get a narrow prop, not a parallel re-implementation.
- **`ScopedPageHeader` for every scoped page** — no inline H2 + flag JSX.
- **`abbreviateScope` is the source of truth for scope** — new FilterBar / AuxParam fields go there AND in `ScopeStatusStrip`.
- **URL state — share-link reproducibility** — `useUrlParam`; URL-clean rule (compute for display, never auto-mutate in `useEffect`).
- **Single-payload + window-toggle** — one round-trip for related views ≤ 6, frontend toggles on in-memory payload.
- **API ↔ frontend type contract** — drop dead fields from `frontend/src/types.ts` in the same commit as the backend drop.
- **Chip ↔ chart baseline symmetry** — if a tile shows a `MetricDelta` chip vs `scope_avg`, the by-season chart MUST render the same `scope_avg` overlay at the same scope.
- **Absolute-vs-per-innings dimensional discipline** — absolute tiles (Runs/100s/Catches/Wickets) bold-only no chip; per-innings tiles (Avg/SR/Econ/100s-per-inn) bold + chip OK. Same rule for charts.
- **No CSS-pixel shortcuts when a structural fix exists** — subgrid over `min-height`/`padding-top`/`position: absolute` hacks.
- **No hacks where a structural fix exists** — match the codebase's idiom (useRef once-per-mount gates over `window.location` reads in effects, derived state over `setTimeout`).
- **FilterBar cascade-clear rule** — `if (t && (!v || t.team_type !== v))`, NOT `if (t && v && ...)` (auto-correct spring-back bug).

---

## Testing discipline

Detail in `internal_docs/testing-discipline.md`. Headline rules:

- **Three layers** — Sanity (`tests/sanity/*.py`: SQL↔API) · Integration (`tests/integration/*.sh`: DOM↔SQL via running app) · Regression (`tests/regression/*/urls.txt`: no-drift at API).
- **Integration tests must self-anchor against SQL** — every numeric expected derived from `sqlite3 cricket.db` at runtime, never hardcoded.
- **Tests must cover EVERY call site of a shared abstraction** — `grep -rn 'helperName' src/` enumerates the sites; write one assertion per site.
- **Sparkline / per-item bar count must match SQL** — assert rendered bars == SQL-anchored item count; assert zero height=0 bars.
- **Integration tests anchor against `/summary`'s scope_avg, not re-derived SQL** — pull dual-query envelope values via `curl`, don't re-derive in-shell.

---

## Cricket invariants

These are codified in `internal_docs/how-stats-calculated.md` and `internal_docs/design-decisions.md`. **Do not change any of these predicates without re-reading the linked section.**

- **Catches counts include caught-and-bowled (Convention 3)** — `fc.kind IN ('caught','caught_and_bowled')` AND `COALESCE(fc.is_substitute,0)=0` for any catches headline. Exception: `substitute_catches` reconciliation scalar stays `kind='caught'` only. → `design-decisions.md` "Convention 3 applies to distribution endpoints, not just /summary".
- **Substitute fielders — INCLUDED in /leaders, EXCLUDED in /distribution** — intentional asymmetry. `/fielders/leaders.catches` + `/fielders/{id}/summary.catches` + `/fielders/{id}/records.most_catches_match` apply NO `is_substitute` filter (volume framing). `/fielders/{id}/distribution` per-match catches applies `is_substitute=0` (matchplayer-sample denominator consistency). Algebraic identity locked by `tests/sanity/test_catches_convention3.py::assert_leaders_substitute_leak`. → `how-stats-calculated.md` §Fielding.
- **DLS-truncated innings — INCLUDED everywhere** — NO `target_overs` filter or branch anywhere in `api/routers/`. Overs/balls denominators (RR, econ, SR, phase rates) divide by actual legal-ball counts and are DLS-safe by construction. Innings denominators (Avg innings total, mean_per_innings, dismissals_per_match) count DLS innings as 1 — symmetric with fast-chase / all-out-early innings. Tested by `tests/sanity/test_predicate_invariants.py`. → `how-stats-calculated.md` "DLS-truncated innings" + `server-vs-client-calcs.md` §3.5.
- **Scope-anchored form-window cutoffs** — `last_60d` / `last_6mo` / `last_1yr` compute against `anchor = min(today, max_obs_date)`. Single helper `api/form_windows.py::scope_anchor`; new endpoints MUST use it. → `design-decisions.md` "Form-window cutoffs are scope-anchored, not today-anchored".
- **Player/team-aware seasons + scope-anchored quick-select buttons** — `/api/v1/seasons` accepts `?person_id=` and `?team=`; FilterBar quick-select buttons (`first-3` / `all-time` / `prev-3` / `last-3` / `latest`) all slice the returned array. New season buttons slice; do NOT re-fetch with different args. → `design-decisions.md` "FilterBar season-window quick-select buttons".
- **Player baseline buckets — opener merged + per-over + keeper-binary** — Batting: 10 position buckets, bucket 1 = positions 1+2 merged. Bowling: 20 buckets (1-indexed overs 1..20). Fielding: binary `is_keeper=0|1` (NOT position-weighted). Sliding-scale per-bucket thresholds; strict cliff (any bucket below threshold → entire `scope_avg` null). By-season/by-phase endpoints take `person_id` and derive mix server-side; only lifetime `/summary` endpoints take external mix vectors. Phase tables: `playerscopestats_batting_phase` + `playerscopestats_fielding_phase` (powerplay/middle/death). → `internal_docs/spec-player-compare-average.md` §4 + §6; `spec-player-baseline-parity.md` §3.1 + §3.2.

---

## Page conventions

Codified in `internal_docs/design-decisions.md`. Headlines:

- **Status bar derives "all-time" range; URL stays clean** — `ScopeStatusStrip` shows `Season: 2005/06–2021 (all-time)` in italic faint when no range is picked; URL is NOT auto-mutated. → `design-decisions.md` "Status bar computes the all-time season range".
- **Dormancy badge — page-header only** — `≤ 60 days` hidden / `61–364` → `5 months since last match` / `≥ 365` → `last match: Oct 2021`. Wired via `last_match_date` on distribution-endpoint lifetime blocks → `DormancyContext`. Page header only — NOT in the status strip. → `design-decisions.md` "Dormancy badge".
- **Inning filter — Option B "batted-first" semantics (unified)** — `?inning=0` ≡ the subject's team **batted first**; `?inning=1` ≡ batted second — on EVERY page/tab/discipline. The filter is **per-event + discipline-aware**, NOT the match's raw innings_number: batting → `innings_number=N`; bowling/fielding/keeping → `innings_number=(1-N)` (the team fields in the innings it didn't bat). So a number never changes meaning between Batting and Bowling tabs. Backend helpers: players `filters.player_inning_match_clause(side=…)`, teams `teams.py::_option_b_team_inning(side=…)`, leaderboards `aux_clauses.splice_aux_join_clauses(side=…)` / `tournaments._inning_extras(side=…)` (bowling/fielding bind `:inning_flip`). Match-level/header counts use the **union** "batted-in-N OR fielded-in-(1-N)". Cohort/scope-averages narrow per-event by the same side rule. Caveat: distribution-panel cohort baselines read `playerscopestats` (no innings dim) → stay full-scope under inning (shared across batting/bowling/fielding panels). Spec: `spec-inning-unify-option-b.md` (supersedes `spec-inning-split.md` §1/§3.4/§7).
  - **POV-aware pill labels via `useDiscipline()`** — Batting/Partnerships → "Batting first/second" (value = ordinal); Bowling/Fielding → "Bowling first/second" with **value FLIPPED** ("Bowling first" writes `inning=1`, since bowled-first = batted-second); ambiguous (Players profile, Records, Compare slots) → neutral "1st/2nd innings" = batted-first. Team `/by-inning` band rows are POV-labelled too ("Bowled first/second" / "Batted first/second"). Tested by `inning_toggle_pov_labels.sh`, `inning_unify_{players,teams,compare,series,venues}.sh`, `team_by_inning.sh`.

Mount-site inventory for InningToggle / Splits Mosaic / ResultFilter: `internal_docs/inning-controls-mount-sites.md`.

---

## Palette

Three palette systems, never blurred:

- **Magnitude tiers** (indigo / sage / ochre) — histograms, sparklines, ProbChips on Distribution panels. Polarity tied to OUTCOME for the player (high SR = ochre; high econ = indigo).
- **Outcome traffic light** (`WISDEN_WL` green/amber/red) — **Splits Mosaic only**.
- **Accent strokes** — oxblood `#7A1F1F` for rolling-mean overlay, forest `#3F7A4D` for league-avg reference line.

Reds are reserved across the whole codebase: oxblood (strokes) and `WISDEN_WL.lost` (Mosaic cells). Nowhere else.

Full rules — polarity convention, `WISDEN_TIER_TINTS` chip helper, sparkline visual contract, reference-line table, legend-swatch alignment pattern — in **`internal_docs/colors.md`**.

---

## Splits Mosaic

The Mosaic is a filter widget that LOOKS like a stat chart. URL params drive the visual density (no internal state for expanded/collapsed):

| Aux URL params set | Layout |
|---|---|
| 0 | 2×2 (toss × inning) cells with W/T/L sub-rects per cell |
| 1 | 2×2 of the two free axes |
| 2 | 1D horizontal stacked bar of the one free axis |
| 3 | verbose colloquial status strip — "Won toss · Batted first · Won the game — 3 matches" |

`result` and `toss_outcome` aux filters **require `?team=`** (without a subject team, the unpivoted league-side view makes "won" tautologically 50%). `/teams/splits` returns HTTP 400 when either aux is set without `?team=`.

Full rules — aux semantics, palette reservation, share-denominator-follows-filter, tells — in **`internal_docs/splits-mosaic-discipline.md`**. Design specs: `spec-splits-mosaic.md` (Teams-only — implemented 2026-05-11), `splits-mosaic-cross-page.md` (cross-page reuse DESIGN).
