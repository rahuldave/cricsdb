# Tweet thread — T20 & CricsDB launch

Each tweet is a block separated by `---`. Copy the text below the header, attach the image noted in the header (all images live alongside this file in `frontend/public/social/`).

Twitter / X counts any URL as 23 characters regardless of length, so the character counts below include that convention. Every tweet is under 250.

---

**Tweet 1 · 1/12 · attach: none (link autocard renders the OG image)**

1/ Shipped T20 & CricsDB — an almanack of Twenty20 cricket, pulled from @cricsheet.

13,019 matches · 2.95M deliveries · international + club. Every number searchable, filterable, linkable.

https://t20.rahuldave.com

---

**Tweet 2 · 2/12 · attach: 03-team-overview.png**

2/ Every T20 side gets a dossier.

Wins/losses, opponents, season-by-season, keepers used, 11-man XI per season with year-on-year turnover, phase splits for batting + bowling.

India (men's) — 266 matches, 67.7% wins ↓

---

**Tweet 3 · 3/12 · attach: 05-team-partnerships.png**

3/ Team pages go deep into partnerships.

Best pairs by wicket, heatmap of average stand per wicket per season, full top-N list.

All filter-sensitive — narrow to IPL, or one season, and every number rescopes.

Mumbai Indians ↓

---

**Tweet 4 · 4/12 · attach: 08-rivalry-dossier.png**

4/ Series tab houses competitions AND bilateral rivalries.

ICC events · men's/women's bilateral tiles · club leagues (IPL · BBL · PSL · WPL · WBBL + more).

India v Australia men's: 37 meetings, 22–12 to India ↓

---

**Tweet 5 · 5/12 · attach: 10-player-single.png**

5/ Players tab (new): a person-focused home.

Batting, bowling, fielding, keeping — all on one page.

Role classifier adapts to scope: narrow to one tournament and a "specialist batter" can legit flip to "all-rounder" if they bowled there ↓

---

**Tweet 6 · 6/12 · attach: 11-player-compare.png**

6/ Compare up to 3 players side-by-side, aligned by discipline.

No data for one column? "— no bowling in scope —" placeholder keeps rows level.

Kohli × Williamson × Smith, all-time ↓

---

**Tweet 7 · 7/12 · attach: 12-batting-vs-bowlers.png**

7/ Each discipline gets a dedicated deep-dive.

Batting: season, over, phase, inter-wicket, dismissals, and a vs-bowlers scatter — strike rate × average, size = balls faced. Click a row in the table, find the dot.

Kohli ↓

---

**Tweet 8 · 8/12 · attach: 14-h2h-player.png**

8/ Head-to-Head for any batter vs any bowler.

Summary, phase split, season trend, over-by-over, every match.

A "Show" pill slices Bilateral / ICC / Club so you can ask three questions from one URL.

Kohli v Bumrah ↓

---

**Tweet 9 · 9/12 · attach: 15-h2h-team.png**

9/ Flip mode=team and H2H becomes team vs team.

Every meeting between two sides — bilateral tours + tournament matches combined — reusing the rivalry dossier's tabs.

India v Australia, all meetings ↓

---

**Tweet 10 · 10/12 · attach: 17-scorecard-full.png**

10/ Every match has a full scorecard.

Batting order, bowling figures, fall of wickets, a ball-by-ball innings grid, worm chart, batter×bowler matchup grid.

Innings-list date links highlight that player's row on load.

2024 T20 WC Final ↓

---

**Tweet 11 · 11/12 · attach: 18-filter-rivalry.png**

11/ FilterBar composes across every page: gender · type · tournament · season.

Click a rivalry link and filter_team + filter_opponent join in. A scope pill names what you're looking at, one tap to CLEAR.

"Scoped to India v Australia" ↓

---

**Tweet 12 · 12/12 · attach: none**

12/ Built: SQLite + deebase + FastAPI + React + Semiotic + Tailwind.

Data from @cricsheet under ODC-BY, incrementally refreshed.

Source → https://github.com/rahuldave/cricsdb

Try it → https://t20.rahuldave.com

What would you want next?

---

## Image manifest — quick reference

| Tweet | Image | What it shows |
|---|---|---|
| 1 | — | autocard (OG image) |
| 2 | `03-team-overview.png` | India dossier: summary row + tabs + keepers |
| 3 | `05-team-partnerships.png` | Mumbai Indians: best pairs + heatmap |
| 4 | `08-rivalry-dossier.png` | India v Australia: 37 matches, by-team split, knockouts |
| 5 | `10-player-single.png` | Kohli: Batting / Bowling / Fielding bands |
| 6 | `11-player-compare.png` | 3-way compare: Kohli × Williamson × Smith |
| 7 | `12-batting-vs-bowlers.png` | Kohli's vs-Bowlers scatter + matchup table |
| 8 | `14-h2h-player.png` | Kohli v Bumrah h2h |
| 9 | `15-h2h-team.png` | India v Australia team-mode dossier |
| 10 | `17-scorecard-full.png` | 2024 T20 WC Final full scroll |
| 11 | `18-filter-rivalry.png` | Kohli /batting with rivalry scope pill |
| 12 | — | tech + outro, no image |

## Also in this folder (not used in the thread)

- `01-homepage.png` — full homepage scroll (masthead, In the Volume, fixtures, departments). Good for a future "how it fits together" post.
- `02-teams-landing.png` — Teams landing page (international + franchise columns).
- `04-team-batting.png` — India's Batting tab (phase-season heatmap).
- `06-series-landing.png` — Series landing (tournament + rivalry tiles).
- `07-ipl-dossier.png` — IPL dossier (champions timeline, records panel).
- `09-players-landing.png` — Players landing (curated profile tiles + compare pairs).
- `13-batting-by-phase.png` — Kohli's three-up phase blocks.
- `16-scorecard.png` — scorecard top-fold (shorter than 17).

## Posting tips

1. Write tweet 1, post it, then reply-to-self with tweet 2, then reply-to-tweet-2 with tweet 3, and so on. X links them as a thread automatically.
2. Attach the image BEFORE sending — X's char counter only goes yellow; an over-limit attachment won't auto-truncate.
3. The arrow glyphs (↓, ×, · , —) are pure Unicode so they render identically on mobile + web.
