# Roughdraft — spec-review workflow

Roughdraft is a local single-file Markdown viewer that round-trips CriticMarkup comments through a browser pane. This codebase uses it for reviewing build-ready specs in `internal_docs/spec-*.md`.

The user may refer to Roughdraft as `rd` in natural language. Treat `rd` as shorthand. Do NOT create any shell alias / executable / symlink / command named `rd`.

When the user asks for a plan, write the plan as a Markdown file on disk BEFORE asking them to review it (this codebase's convention — drop it under `internal_docs/spec-*.md`).

## Opening a spec

```bash
roughdraft open "/absolute/path/to/internal_docs/spec-*.md"
```

Roughdraft is single-file — open one `.md` at a time. If Roughdraft isn't running, `roughdraft open` starts it automatically.

After `roughdraft open` runs, **leave the command running**. Do not interrupt, kill, background, detach, or treat the waiting process as cleanup — the wait IS the signal. Roughdraft exits the command when the user clicks Done Reviewing, and that exit is your signal to resume.

**Known issue on this machine:** `roughdraft watch` (the long-poll for Done Reviewing) hits a Node 25 / undici 60-second headers timeout. The browser window still opens fine and edits still save to disk. If the CLI errors out with `HeadersTimeoutError` / `UND_ERR_HEADERS_TIMEOUT`, the window IS open at `http://localhost:7373/?path=...`; tell the user, then re-read the file from disk after they say they're done.

After the user finishes reviewing, **read the Markdown file from disk** and respond to any CriticMarkup comments / suggested changes. Don't assume — `grep -nE '\{>>|\{\+\+|\{--|\{~~|\{=='` the file to surface all markers.

## CriticMarkup syntax (Roughdraft-flavored)

Base markers:

- Comment: `{>>comment<<}`
- Insertion: `{++new text++}`
- Deletion: `{--old text--}`
- Substitution: `{~~old~>new~~}`
- Highlight: `{==text==}`

Anchored comment: `{==selected text==}{>>Comment text<<}{id="c1" by="AI" at="2026-04-28T12:00:00.000Z"}`.
Suggested change: `{++new text++}{id="s1" by="AI" at="..."}` or `{~~old text~>new text~~}{id="s2" by="AI" at="..."}`.
Reply (refers to parent via `re`): `{>>Reply text<<}{id="c2" by="AI" at="..." re="c1"}`.

When you ADD a new comment or suggested change, use the extended attribute block: `{id="cN" by="AI" at="<ISO timestamp>"}`. Generate stable doc-local ids (`c1`, `c2`, … for comments; `s1`, `s2`, … for suggestions). When replying, set `re` to the parent id.

Roughdraft may already have attribute blocks on existing comments — **preserve them** unless you're intentionally removing the comment. Common attributes: `id`, `by`, `at`, `re`.

## Spec-review flow for this codebase

For build-ready specs (`spec-apples-to-apples-baselines.md`, `spec-prob-baselines.md`, etc.):

1. Draft the spec as a single Markdown file under `internal_docs/`.
2. Commit the draft (one clean commit so the review pass diff is readable).
3. `roughdraft open "/Users/rahul/Projects/cricsdb/internal_docs/<spec>.md"` — the user reviews in the browser.
4. After Done Reviewing, grep the file for CriticMarkup markers; respond to each as inline reply comments (preserve original ids; assign new ids to your replies with `re=` set).
5. Apply any structural changes the user asked for (e.g., promote "open questions" to "decisions", drop deferred sections, tighten ambiguous principles).
6. Commit the review pass as a separate commit with `spec: review pass — decisions locked` style message that summarises which comments were addressed.
7. Push so a future session sees the locked spec on `origin/main`.

If `roughdraft help` or `roughdraft help criticmarkup` is needed for local CLI / syntax details, run them directly.
