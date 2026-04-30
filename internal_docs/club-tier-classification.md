# Club-tier classification — primary vs secondary

Companion doc to `api/club_tiers.py` and
`internal_docs/spec-filterbar-team-class-club.md`. Captures the
**why** behind each league's tier so future contributors don't
re-litigate.

The `team_class` FilterBar key partitions club competitions into two
tiers, mirroring the international "full member / associate" split:

- **Primary** = marquee international franchise leagues. Top-flight
  T20 destinations recognized globally; auction-driven; full-member
  overseas pros are a regular feature of squads.
- **Secondary** = traditional domestic competitions. Country's
  state / county / provincial structure run as a T20 tournament;
  mostly local players; or small-market franchise leagues that don't
  reach the marquee bar above.

The cut is structural — verified DB-wide that every cricsheet club
T20 `event_name` lands in exactly one tier (untagged = 0 across 7,573
matches as of 2026-04-30, asserted by the
`test_completeness_invariant` sanity test).

## Men's leagues

### Primary (10)

| League | Country | DB matches | Notes |
|---|---|---|---|
| Indian Premier League | India | 1,207 | Marquee; auction; foundational |
| Big Bash League | Australia | 662 | Established 2011/12; international draft |
| Bangladesh Premier League | Bangladesh | 469 | Heavy roster turnover but durable franchise format |
| Caribbean Premier League | Caribbean | 407 | West Indies' marquee; multi-island |
| Pakistan Super League | Pakistan | 351 | Auction-driven; Foreign-pro factory |
| The Hundred Men's Competition | England | 167 | ECB franchise (technically 100-ball but stored as T20) |
| International League T20 | UAE | 134 | Major international destination |
| SA20 | South Africa | 130 | Replaced/displaced CSA T20 Challenge as SA's marquee |
| Lanka Premier League | Sri Lanka | 119 | Smaller but still draft-driven international |
| Major League Cricket | USA | 75 | New (2023+); USA's Test for major-international scale |

### Secondary (5)

| League | Country | DB matches | Notes |
|---|---|---|---|
| Vitality Blast | England | 1,455 | County-based (18 first-class counties); England's senior domestic. Has overseas pros but not a draft-format auction; eclipsed by The Hundred for marquee status |
| Syed Mushtaq Ali Trophy | India | 695 | India's state T20 (Ranji-style; 39 state teams) |
| CSA T20 Challenge | South Africa | 314 | SA provincial; mostly displaced post-SA20 |
| Super Smash | New Zealand | 270 | NZ's only T20 league. Six provincial associations (Auckland, Canterbury, Central Districts, Northern Districts, Otago, Wellington). NZ has no franchise tier — Super Smash IS the top NZ T20 cricket. Still secondary by structure (provincial, not franchise auction) |
| Nepal Premier League | Nepal | 64 | Two seasons (2024/25–2025/26). Franchise-format, but small-market: rosters are mostly Nepali domestic plus a handful of fellow Associates (UAE, Hong Kong, Oman, Namibia, Netherlands, Scotland, Canada, USA). No marquee Full-Member overseas, no auction-scale comparable to IPL/PSL/SA20. Belongs with secondary even though structurally franchise — the principle is "marquee international destination", not "franchise format" |

## Women's leagues

### Primary (4)

| League | Country | DB matches | Notes |
|---|---|---|---|
| Women's Big Bash League | Australia | 519 | Longest-running women's franchise league |
| The Hundred Women's Competition | England | 155 | ECB franchise |
| Women's Cricket Super League | England | 95 | Defunct (2016–2019); franchise predecessor to The Hundred Women's. Team strings persist in the DB |
| Women's Premier League | India | 88 | BCCI-run auction; IPL-economic-tier for women's |

### Secondary (2 — same 6 NZ teams)

| League | Country | DB matches | Notes |
|---|---|---|---|
| Women's Super Smash | New Zealand | 148 | NZ provincial (same 6 teams: Auckland, Canterbury, Central Districts, Northern Districts, Otago, Wellington) |
| New Zealand Cricket Women's Twenty20 | New Zealand | 49 | Older cricsheet event_name for the **same** provincial competition. Treated as a continuation; appears separately in cricsheet because the naming changed |

## Edge cases worth flagging

1. **Vitality Blast** is the only genuinely debatable men's case.
   Structurally secondary (county-based, no auction draft) but has
   elite overseas pros and shares England's senior-T20 status with
   The Hundred. Kept secondary so the rule stays mechanical;
   bumping it makes the cut subjective and "what about CSA T20
   Challenge in the franchise era?" follows immediately. The rule
   to remember: **"county-based" → secondary**, regardless of how
   star-studded the rosters look.

2. **Nepal Premier League** is the only debatable secondary-side
   case in the opposite direction. Franchise-format (8 city-named
   teams, 2 seasons in) → looks like it could go primary. But the
   classification principle is **marquee international destination**
   measured by:
   - regular Full-Member overseas pros (NPL fails — imports are
     fellow Associates),
   - established multi-season auction history (NPL fails — too new),
   - globally recognised top-tier league (NPL fails — small market).
   So secondary. If NPL grows into a marquee venue over time, this
   classification becomes the right thing to revisit.

3. **CSA T20 Challenge** had a pseudo-franchise era (Cape Cobras,
   Lions, Titans, Dolphins) but those were provincial amalgamations
   under SA's old "franchise system", not city-franchise auctions.
   Always secondary.

4. **Super Smash + Women's Super Smash** are NZ's only T20 leagues —
   the provincial sides ARE the top NZ T20 cricket. Still secondary
   by structure; NZ just doesn't have a franchise tier.

5. **The Hundred** is technically 100-ball, not 120-ball. Stored as
   `match_type='T20'` in cricsheet, so it's part of this universe.
   No special-casing needed.

## What's NOT in this classification

- ICC T20 World Cup, Asia Cup, qualifiers, etc. — those are
  international, not club. Filtered by `team_type='international'`.
  `team_class=full_member` applies there.

- U19 / Under-25 / age-group club leagues. None are in the DB
  currently; if introduced via `update_recent`, they'd hit the
  completeness invariant test and need a tier assignment before
  merging.

- Test-format county championships, List A 50-over tournaments, etc.
  Out of scope — DB is T20-only (`match_type IN ('T20', 'IT20')`).

## Phase-2 reconciliation work (tracked separately)

The existing `tournament_canonical.py::TOURNAMENT_SERIES_TYPE` has
two classifications that don't match the tier classification:

- Super Smash is tagged `franchise_league` (should be
  `domestic_league` per the structural principle).
- Women's Super Smash is tagged `women_franchise` (should be
  `women_domestic` — but that bucket doesn't exist yet).

These power the **Teams landing-page bucketing** (franchise_leagues
/ domestic_leagues / women_franchise / other section headers). The
phase-1 tier work deliberately leaves them alone — fixing them
changes user-visible UX section labels and wants a separate product
call. Phase 2 candidates:

- Move Super Smash + WSS to a `domestic_league` / `women_domestic`
  bucket.
- Optionally rename landing-page section labels to "Primary
  leagues" / "Secondary leagues" / "Women's primary" / "Women's
  secondary" so the section vocabulary matches the FilterBar pill.

Until then: the dual map (tier in `club_tiers.py`, landing bucket in
`tournament_canonical.py`) is a deliberate accommodation, not an
oversight. The two maps serve different audiences (filter narrowing
vs section UX) and can evolve independently.
