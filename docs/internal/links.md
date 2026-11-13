# TeamLink / PlayerLink / SeriesLink — contract and usage

Any navigation to `/teams?…`, `/batting|/bowling|/fielding|/players?…`, or
`/series?…` **must** go through the matching link component. If you find
yourself typing a raw `<Link to="/teams…">` or building a URL with a
local helper (`teamUrl`, `teamLinkHref`, `renderBatter`, `renderVsTeams`,
etc.), stop — the existing component handles it with one or two props.

This doc is the reference. The underlying mechanics live in
`frontend/src/components/scopeLinks.ts`, but 90% of call sites only need
the patterns below.

## The three components at a glance

| | Destination | Default name href | Phrase subscripts | Main props |
|---|---|---|---|---|
| **TeamLink** | `/teams?team=X` | **All-time** (identity only: gender + team_type) | 0–2 tiers, off-axis filters dropped | `teamName`, `subscriptSource`, `phraseLabel`, `maxTiers`, `compact`, `layout` |
| **PlayerLink** | `/batting|bowling|fielding|players?player=ID` | **All-time** (identity: gender) | 0–3 tiers, `keepRivalry=true` by default (player's "vs Opp" axis matters) | `personId`, `name`, `role`, `subscriptSource`, `phraseLabel`, `maxTiers`, `compact`, `trailingContent` |
| **SeriesLink** | `/series?…` | Scope is passed in directly — no subscriptSource, no phrases | — | free-text `children`, explicit scope props (`tournament`, `season`, `team1/team2`, `seriesType`, etc.) |

The split matters: **TeamLink and PlayerLink are "entity + scope phrase"
composites** (name = identity, phrase = scope). **SeriesLink is a single
destination-scoped link** with caller-provided children — closer to a raw
`<Link>`, just with predictable URL building.

## The core invariant

For TeamLink and PlayerLink:

> **Name link = all-time identity.** The phrase subscript after the name
> carries scope. Never invert this.

This is the contract every reader has learned. "CSK" on any page goes to
CSK's all-time dossier. The small "at IPL, 2024" or "(ed)" phrase after
the name is the edition-scoped link. Don't build a cell where clicking
the team/player name takes the reader somewhere scoped — use a phrase
subscript (optionally with a compact `phraseLabel` like "ed") instead.

## subscriptSource — per-row scope overrides

When a row has a scope that differs from the ambient FilterBar (innings
list row, partnership row, champions table, knockouts table…), pass
`subscriptSource`:

```tsx
<TeamLink
  teamName={r.team}
  subscriptSource={{ tournament: r.tournament, season: r.season }}
  phraseLabel="ed"
  phraseClassName="scope-phrase-ed"
  maxTiers={1}
/>
```

`SubscriptSource` has four fields that map onto FILTER_KEYS via
SOURCE_MAP in scopeLinks.ts:

```ts
{ tournament?, season?, team1?, team2? }
```

`season` fans out to both `season_from` and `season_to`. `team1/team2`
map to `filter_team/filter_opponent`. `null` on a field **explicitly
clears** that axis from the phrase bucket — important when the ambient
FilterBar has a rivalry set but the (ed) destination is single-team (see
`TeamWithEd` in TournamentDossier.tsx).

## phraseLabel — rendering-only text override

The computed URL and tooltip flow through the normal pipeline; only the
**visible phrase text** is overridden. Use for compact tokens in dense
tables and for "scope-as-count" patterns:

- `phraseLabel="ed"` — standard per-row edition tag. Always paired with
  `phraseClassName="scope-phrase-ed"` for the small-caps styling.
- `phraseLabel={`(${count})`}` — bracketed scoped-count ("Most titles:
  CSK **(6)**", where "6" links to CSK-at-this-tournament).
- `phraseLabel={(tier, i) => …}` — per-tier function form (rare).

The computed tier's full label stays in the tooltip, so readers get the
expressive scope on hover.

## Decision tree — which component do I reach for?

```
Is the destination /series?… (a tournament/series view)?
├─ YES → SeriesLink. Pass scope props + children. Done.
└─ NO
   └─ Is it /teams?… ?
      ├─ YES → TeamLink.
      └─ NO (it's a player path: /batting|bowling|fielding|players?…)
         └─ PlayerLink.
```

For TeamLink / PlayerLink: **always pass `subscriptSource` if the row has
its own scope** (tournament, season, rivalry pair). If the row's scope
happens to equal the ambient FilterBar, `subscriptSource` is optional —
but passing it explicitly costs nothing and documents intent.

## Common patterns

### "Name is all-time, count is scoped" (the bracketed-count convention)

Use `phraseLabel` on the scoped count, wrap everything in one component:

```tsx
{/* "Most titles: CSK (6)" — CSK all-time, (6) linked to CSK-at-IPL */}
Most titles:{' '}
<TeamLink
  teamName={team}
  subscriptSource={{ tournament: canonical }}
  phraseLabel={`(${titles})`}
  maxTiers={1}
/>
```

Do NOT build a raw `<Link>` for the "(6)" — it loses the shared phrase
pipeline (tooltip, bucket resolution, future filter keys).

### Per-row edition tag "(ed)"

```tsx
<TeamLink
  teamName={r.team}
  subscriptSource={{ tournament: r.tournament, season: r.season,
                     team1: null, team2: null }}  {/* kill ambient rivalry */}
  phraseLabel="ed"
  phraseClassName="scope-phrase-ed"
  maxTiers={1}
/>
```

The Matches / Records / Champions / Knockouts tables all use this shape
via the `TeamWithEd` local helper in TournamentDossier.tsx. If you need
it in a new tab, either reuse `TeamWithEd` or inline the same props.

### Leaderboard row with rivalry orientation

```tsx
<PlayerLink
  personId={r.person_id}
  name={r.name}
  role="batter"
  subscriptSource={rowSubscriptSource({ filterTeam, filterOpponent, rowTeam: r.team })}
/>
```

`rowSubscriptSource` (TournamentDossier.tsx:1705–1721) flips the rivalry
pair per row so a Kohli row in an India-vs-Aus dossier reads "vs
Australia" and a Smith row reads "vs India".

### Curated tile with scope not derivable from FilterBar

Pass `gender`, `team_type`, and `seriesType` explicitly:

```tsx
<TeamLink
  teamName={champion}
  gender={gender}
  team_type="international"
  seriesType="bilateral"        {/* don't let ambient URL leak in */}
  subscriptSource={{ season, team1: winner, team2: opp }}
  keepRivalry={true}            {/* rivalry tile → keep "vs Opp" */}
  maxTiers={1}
/>
```

## Anti-patterns — do not do these

- **Raw `<Link to="/teams…">`**. Every case the codebase has today either
  needed `TeamLink` or was a documented exception that `TeamLink` +
  `phraseLabel` could have handled. If you think you need a raw link,
  re-read this file first.
- **Local `teamUrl()` / `teamLinkHref()` helpers**. Historical — all
  removed. Build the URL through TeamLink.
- **`renderBatter` / `renderBatterPair` / `renderVsTeams`**. Historical
  — all removed. Use `PlayerLink` × 2 and `TeamLink` × 2 with (ed).
- **"Winner: `<Team>`" with scope on the name**. The name is always
  all-time. If the natural-language reading wants "this team at this
  edition", render `Winner:{' '}<TeamLink … subscriptSource={…}
  phraseLabel="ed" />` — you get "Winner: India (ed)" with India going
  all-time (the escape falls out for free) and (ed) going to the
  edition.
- **Inverting the name/phrase direction** so that the phrase is the
  "all-time escape". This is backwards. TeamLink's name link IS the
  all-time escape; the phrase is always the scoped link.
- **Putting scope on `TeamLink compact`**. `compact` drops phrases
  entirely — it's for dense cells where only the name makes sense
  (scorecard rows, matchup grids). If you need scope too, don't use
  `compact`; pass `maxTiers={1}` and `phraseLabel` instead.

## When to reach for SeriesLink

Three canonical use cases:

1. **Tournament tile primary** (TournamentsLanding.tsx) — stretched-link
   click target on the tile.
2. **Rivalry tile primary** — same, scoped to a team pair.
3. **Edition cell in a multi-tournament row** (Knockouts table when
   dossier isn't scoped to one tournament) — "T20 WC 2024" as a link
   to that edition's dossier.

SeriesLink has no phrase-subscript machinery. Callers pass the scope
shape they want and the children they want. If your call site has a
phrase-subscript requirement, the destination probably isn't `/series`.

## When adding a new FilterBar filter

If the filter should flow through into every link URL, append it to
`FILTER_KEYS` in scopeLinks.ts — nothing else changes. All three
components pick it up automatically through `nameParams` /
`resolveBucket`. See the comment block at scopeLinks.ts:27–40.

## When you're not sure

Re-read the "Common patterns" section above and match your cell to the
nearest one. Failing that, grep the codebase for the closest existing
surface — ten live call sites of the same pattern is usually the
fastest answer.
