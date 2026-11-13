---
title: CricsDB
---

CricsDB is a T20 cricket statistics site, live at <https://t20.rahuldave.com>. It reads ball-by-ball data
from [cricsheet](https://cricsheet.org) into SQLite, serves it from a FastAPI backend, and shows it in a React
front end. This site is its documentation, and has three parts:

- **[Guide](tab-structure.md).** The pages of the site, their tabs, the URL parameters that drive them, and
  the endpoints behind them.
- **[HTTP API](api.md).** Each endpoint of `/api/v1`, with an example `curl` command and its response. The
  in-app Help page links to it.
- **[Front-end reference](api/index.qmd).** A page for each file of `frontend/src`. smalldocs writes these
  pages from the doc comments in the code.

The contributor documents are in the Contributors section of the sidebar. They come from `docs/internal/` in
the repository. [The specification](https://github.com/rahuldave/cricsdb/blob/main/SPEC.md) gives the
database schema, the SQL of each endpoint and the page layouts.

## Where to start

| To | Read |
|---|---|
| Run the app on your computer | [Local development](internal/local-development.md) |
| Learn React and Vite in this codebase | [React primer](internal/react-primer.md) |
| Add new matches from cricsheet to the database | [Data pipeline](internal/data-pipeline.md) |
| Test `update_recent.py` on a copy of the production database | [Testing update_recent](internal/testing-update-recent.md) |
| Deploy code or a new database | [Deploying](internal/deploying.md) |
| Look at or edit tables in the deebase admin page | [Admin interface](internal/admin-interface.md) |
| Understand a design choice that is not obvious | [Design decisions](internal/design-decisions.md) |
| Keep the page state in the URL | [URL state](internal/url-state.md) |
| Add a page or a request that loads data | [Data fetching](internal/data-fetching.md) |
| Change the Vite, Tailwind or TypeScript build | [Front-end build pipeline](internal/frontend-build-pipeline.md) |
| Make an endpoint that reads a whole table fast | [Leaderboard performance](internal/perf-leaderboards.md) |
| Check that a refactor changes no API response | [Regression testing](internal/regression-testing-api.md) |
| See what comes next | [Next session](internal/next-session-ideas.md) and [the roadmap](internal/enhancements-roadmap.md) |
| Find the browser tests | [tests/integration](https://github.com/rahuldave/cricsdb/tree/main/tests/integration) |
| Find the backend regression checks | [tests/regression](https://github.com/rahuldave/cricsdb/tree/main/tests/regression) |
| Find the rules that every change keeps | [CLAUDE.md](https://github.com/rahuldave/cricsdb/blob/main/CLAUDE.md) |

## Where a new document goes

A document for people who work on the code goes in `docs/internal/`. A document for users, or one that the in-app Help
page links to, goes in `docs/`. To put it on this site, add it to `render` in `docs/_smalldocs.yml`. Every page in `docs/internal/` is on the site.
