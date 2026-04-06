# CricsDB Documentation

Reference docs for working on CricsDB. Start here, then jump to whichever
file matches your task.

## I want to...

- **Run the app on my laptop** → [`local-development.md`](local-development.md)
- **Update the database with new matches from cricsheet** → [`data-pipeline.md`](data-pipeline.md)
- **Push code or a refreshed DB to production** → [`deploying.md`](deploying.md)
- **Understand a non-obvious design choice** → [`design-decisions.md`](design-decisions.md)
- **Tweak the Vite/Tailwind/TypeScript build** → [`frontend-build-pipeline.md`](frontend-build-pipeline.md)
- **Look up an API endpoint or page layout** → [`../SPEC.md`](../SPEC.md)
- **Find a known issue, gotcha, or future enhancement idea** → [`../CLAUDE.md`](../CLAUDE.md)

## At a glance

| Doc | What's in it |
|---|---|
| `local-development.md` | Two-terminal dev setup, type-check, hitting the API directly, project layout cheat sheet |
| `data-pipeline.md` | Cricsheet URLs, the 22 archives we use, full rebuild vs incremental update, dry-run output |
| `deploying.md` | `bash deploy.sh` vs `--first`, what does/doesn't ship, deebase vendoring, the `.plash` identity file, troubleshooting |
| `design-decisions.md` | Over numbering, phase boundaries, legal balls vs all deliveries, bowler-wicket exclusions, URL state |
| `frontend-build-pipeline.md` | Vite + Tailwind v4 + TypeScript build details |
| `../SPEC.md` | Schema, all API endpoints with SQL, all page layouts |
| `../CLAUDE.md` | Quick orientation, design decisions summary, known issues, future enhancements |
