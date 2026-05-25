# Captaincy data in our cricsheet corpus — investigation (2026-05-25)

**Question (for a later session):** what captaincy information do we
have, so we could build a "performance as captain / under captain X"
filter or a captaincy record?

## Finding: cricsheet carries NO captain field

The raw cricsheet T20 match JSONs in `data/ctc_json/` do **not** encode
captaincy.

- `grep -rl captain data/ctc_json/` → **0 of 314** match JSONs contain
  the string "captain" anywhere.
- A match JSON's `info` keys are exactly:
  `balls_per_over, city, dates, event, gender, match_type, officials,
  outcome, overs, player_of_match, players, registry, season,
  team_type, teams, toss, venue`.
  - `info.players` = squad list per team (names only, no role/captain
    marker).
  - `info.officials` = umpires / match referees / reserve umpire / TV
    umpire — **not** captains.
  - `info.registry.people` = name → cricsheet person-id map.
  - `info.toss` = `{winner, decision}` — the toss winner is a *team*,
    not a person, so it doesn't even imply who the captain was.

This matches the published cricsheet schema: the standard `info` block
has never included a captain field. So neither our local sample nor the
full upstream feed will have it — it's a format gap, not an ingestion
gap.

## Our DB confirms the gap

`matchplayer` columns: `id, match_id, team, player_name, person_id`.
No captain / role / is_captain. No captain column on `match` either.
Nothing downstream to surface.

## To build captaincy later we'd need an external source

Options, roughly increasing effort:

1. **ESPNcricinfo / other scorecards** — captains are marked (the "(c)"
   and "†" annotations). Would need a scraper or a licensed feed keyed
   to our matches (by date + teams + venue, or by Cricinfo match id).
   Toss winner is per-team in cricsheet, so a join key exists but is
   coarse.
2. **A curated captaincy table** — `matchcaptain(match_id, team,
   person_id)` populated from an external dataset, then an aux filter
   (`captain=self` for "as captain", or `under_captain=<id>`). This is
   the cleanest target shape; the populate is the hard part (sourcing).
3. **Heuristic inference** — NOT reliable (e.g. "player who batted most
   / is most senior" is wrong often enough to be useless). Don't.

## Recommendation

Park captaincy until we decide on an external source. The
`player_result_clause` work in this session (player-POV win/loss aux)
is the reusable groundwork for *match-context* player filters; a
captaincy filter would slot in as a sibling aux once a
`matchcaptain`-style table exists.
