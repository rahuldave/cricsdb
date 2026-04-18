# CricsDB Documentation

Two audiences, two folders:

- **`docs/`** (this folder) — user-facing / externally-linked
  documentation. Right now that's the API reference and this index.
  The in-app `/help` page links directly into `api.md`.
- **`internal_docs/`** — contributor-facing docs: local setup, build
  pipeline, design decisions, specs, testing workflows, roadmap,
  React primer, URL-state discipline. See
  [`../internal_docs/`](../internal_docs/).

## External docs (in this folder)

| Doc | What's in it |
|---|---|
| [`api.md`](api.md) | Practical API reference — one section per endpoint with a curl example and abbreviated JSON response. Linked from the in-app `/help` page. |
| [`../SPEC.md`](../SPEC.md) | Full schema + every endpoint's SQL + page layouts. |

## Internal docs (in `internal_docs/`)

A quick map — follow the links for the full index in the sibling folder.

### I want to...

- **Run the app on my laptop** → [`../internal_docs/local-development.md`](../internal_docs/local-development.md)
- **Read React / Vite for the first time in this codebase** → [`../internal_docs/react-primer.md`](../internal_docs/react-primer.md)
- **Update the database with new matches from cricsheet** → [`../internal_docs/data-pipeline.md`](../internal_docs/data-pipeline.md)
- **Smoke-test `update_recent.py` against a copy of prod** → [`../internal_docs/testing-update-recent.md`](../internal_docs/testing-update-recent.md)
- **Push code or a refreshed DB to production** → [`../internal_docs/deploying.md`](../internal_docs/deploying.md)
- **Use the deebase admin UI to inspect or edit tables** → [`../internal_docs/admin-interface.md`](../internal_docs/admin-interface.md)
- **Understand a non-obvious design choice** → [`../internal_docs/design-decisions.md`](../internal_docs/design-decisions.md)
- **Understand push-vs-replace for URL state** → [`../internal_docs/url-state.md`](../internal_docs/url-state.md)
- **Add a new fetch / page that loads data** → [`../internal_docs/data-fetching.md`](../internal_docs/data-fetching.md)
- **Tweak the Vite/Tailwind/TypeScript build** → [`../internal_docs/frontend-build-pipeline.md`](../internal_docs/frontend-build-pipeline.md)
- **Make a full-table aggregate endpoint fast** → [`../internal_docs/perf-leaderboards.md`](../internal_docs/perf-leaderboards.md)
- **Run a regression harness before shipping a helper refactor** → [`../internal_docs/regression-testing-api.md`](../internal_docs/regression-testing-api.md)
- **See what's next and what's stuck behind what** → [`../internal_docs/next-session-ideas.md`](../internal_docs/next-session-ideas.md) + [`../internal_docs/enhancements-roadmap.md`](../internal_docs/enhancements-roadmap.md)
- **Run end-to-end browser checks** → [`../tests/integration/`](../tests/integration/)
- **Run backend regression (md5-diff) checks** → [`../tests/regression/`](../tests/regression/)
- **Find a known issue, gotcha, or future enhancement idea** → [`../CLAUDE.md`](../CLAUDE.md)

If a new doc would only ever be read by someone working on the code,
it goes in `internal_docs/`. If it's linked from the in-app Help pages
or meant to be shareable with end-users, it goes in `docs/`.
