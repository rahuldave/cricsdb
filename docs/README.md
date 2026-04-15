# CricsDB Documentation

Reference docs for working on CricsDB. Start here, then jump to whichever
file matches your task.

## I want to...

- **Run the app on my laptop** → [`local-development.md`](local-development.md)
- **Update the database with new matches from cricsheet** → [`data-pipeline.md`](data-pipeline.md)
- **Smoke-test `update_recent.py` against a copy of prod** → [`testing-update-recent.md`](testing-update-recent.md)
- **Push code or a refreshed DB to production** → [`deploying.md`](deploying.md)
- **Use the deebase admin UI to inspect or edit tables** → [`admin-interface.md`](admin-interface.md)
- **Understand a non-obvious design choice** → [`design-decisions.md`](design-decisions.md)
- **Add a new fetch / page that loads data** → [`data-fetching.md`](data-fetching.md)
- **Tweak the Vite/Tailwind/TypeScript build** → [`frontend-build-pipeline.md`](frontend-build-pipeline.md)
- **Hit an API endpoint with a curl example in front of me** → [`api.md`](api.md)
- **Make a full-table aggregate endpoint fast** → [`perf-leaderboards.md`](perf-leaderboards.md)
- **Look up an endpoint's full schema + SQL or a page layout** → [`../SPEC.md`](../SPEC.md)
- **See what's next and what's stuck behind what** → [`next-session-ideas.md`](next-session-ideas.md) + [`enhancements-roadmap.md`](enhancements-roadmap.md)
- **Find a known issue, gotcha, or future enhancement idea** → [`../CLAUDE.md`](../CLAUDE.md)

## At a glance

| Doc | What's in it |
|---|---|
| `local-development.md` | Two-terminal dev setup, type-check, hitting the API directly, project layout cheat sheet |
| `data-pipeline.md` | Cricsheet URLs, the 22 archives we use, full rebuild vs incremental update, dry-run output |
| `deploying.md` | `bash deploy.sh` vs `--first`, what does/doesn't ship, deebase vendoring, the `.plash` identity file, troubleshooting |
| `admin-interface.md` | `/admin/` deebase UI, table map, jinja2 + starlette version pins, authentication (TODO), per-innings edit workflow |
| `design-decisions.md` | Over numbering, phase boundaries, legal balls vs all deliveries, bowler-wicket exclusions, URL state, scatter↔table linking pattern |
| `data-fetching.md` | `useFetch` hook, `Spinner` + `ErrorBanner`, gated fetches, the per-tab `<TabState>` helper, when NOT to use `useFetch`, where loading/error sit relative to data |
| `frontend-build-pipeline.md` | Vite + Tailwind v4 + TypeScript build details |
| `api.md` | Practical API reference — one section per endpoint with a curl example and abbreviated JSON response |
| `perf-leaderboards.md` | How the Batting/Bowling/Fielding landing queries went from 3s+ to sub-second — conditional JOIN elimination, composite covering indexes, ANALYZE |
| `testing-update-recent.md` | Copy-to-tmp workflow for smoke-testing incremental imports against a prod snapshot via `--db` |
| `next-session-ideas.md` | Open design questions to pick up next: `/tournaments`, team-to-team H2H placement, landing-page perf options |
| `../SPEC.md` | Schema, all API endpoints with SQL, all page layouts |
| `../CLAUDE.md` | Quick orientation, design decisions summary, known issues, future enhancements |
