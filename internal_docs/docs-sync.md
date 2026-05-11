# Keeping docs in sync

**This file is the source of truth for "what doc do I update when I change X?". Read it before claiming any feature done, and update affected sections IN this file (and the ones it points to) at the end of every feature.**

Undocumented features decay fastest. The codebase has dedicated docs for each concern; CLAUDE.md is the inviolable-rules file and deliberately does not duplicate them.

---

## Update map — what to touch when

- **Added / changed / removed an API route?** Update `docs/api.md` — add or amend the endpoint section (path, one-liner, curl, abbreviated JSON response). Hit the endpoint via `curl` to capture a real response rather than inventing one.
- **Changed a URL scheme, filter param, or response shape on an existing endpoint?** Same — update the affected `docs/api.md` section. Re-curl the example if the shape changed.
- **Added a new router file, a new page, or a new hook?** Update `internal_docs/codebase-tour.md` (both the router summary line and the frontend hooks block).
- **Shipped a feature that belongs in the A-O narrative?** Add or amend the entry in `internal_docs/enhancements-roadmap.md`; done items stay there as historical markers.
- **Made a non-obvious design decision** (a convention future contributors would otherwise try to change)? Add a bullet to `internal_docs/design-decisions.md`.
- **Added or changed a metric formula** (run rate, economy, win %, a transform, an exclusion rule)? Update the matching section in `internal_docs/how-stats-calculated.md` with the new formula + WHY. The doc grows with the codebase; never let a formula go undocumented.
- **Changed pipeline behaviour, introduced a new invariant the DB must carry, or added a testing workflow?** Touch `internal_docs/data-pipeline.md` (and/or `internal_docs/testing-update-recent.md`).
- **Refactored a shared query helper (`FilterParams`, router filter fns, SQL generators) with many callers?** Run `./tests/regression/run.sh <feature>` against a URL inventory at `tests/regression/<feature>/urls.txt`. Workflow + inventory conventions in `internal_docs/regression-testing-api.md` + `tests/regression/README.md`. Report the pass count before claiming done.
- **Added a user-visible feature the browser-agent can exercise?** Write or extend the matching `tests/integration/<feature>.sh` script. See `tests/integration/README.md` for the helper set and when-to-run rules.
- **Introduced a new perf pattern worth reusing?** Add it to `internal_docs/perf-leaderboards.md` (or create a sibling `perf-*.md` if scope is different).
- **Changed the page structure, tabs, or search-bar landing?** Update `internal_docs/landing-pages.md`.
- **Changed palette / swatch / reference-line behaviour?** Update `internal_docs/colors.md`.
- **Changed Splits Mosaic behaviour (aux semantics, dimensionality, share denominator)?** Update `internal_docs/splits-mosaic-discipline.md` and/or `internal_docs/spec-splits-mosaic.md`.
- **Changed anything user-visible about the home page, filter bar, or global conventions?** Update the relevant narrative doc.

If the change is genuinely trivial (typo, whitespace, one-line comment), skip. Otherwise default to updating.

---

## Regression-shape changes — REG→NEW flip discipline

**Intentionally changed the response shape of an endpoint that has REG entries in `urls.txt`?** Flip those lines from `REG` to `NEW` in a **separate, earlier commit** before the shape change itself. The runner keys on the HEAD-side `kind` column (`kind, hh = head[k]` in `run.sh`), so an uncommitted flip has no effect — it has to be in HEAD when the runner stashes.

Workflow:
1. Commit the `REG → NEW` flip on affected URLs.
2. Commit the backend change.
3. Run `./tests/regression/run.sh <feature>` — expected output is `0 REG drifted, N NEW changed, 0 NEW unchanged`.

This sequencing was flagged by the user — retroactive flips don't test anything because the runner reads the kind column from HEAD.
