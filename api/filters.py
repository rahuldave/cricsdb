"""Filter system for CricsDB API queries.

Two-class model:

- `FilterBarParams` — the 10 fields driven by the frontend's FilterBar
  UI (gender, team_type, tournament, season_from/to, filter_team,
  filter_opponent, filter_venue, team_class, series_type). Maps 1:1 with
  `FILTER_KEYS` on the frontend (`components/scopeLinks.ts`). Rides
  through scope-link URLs.

- `AuxParams` — internal-plumbing narrowings that don't originate from
  the FilterBar. Includes `scope_to_team` (Compare-tab avg-slot
  auto-narrow), `chip_team_class` (chip-baseline alignment hint),
  `inning` (1st/2nd innings page-local toggle), `result` (game-outcome
  match filter from the path team's POV), and `toss_outcome` (toss-
  outcome match filter from the path team's POV). Future page-local
  filters (close_match, super_over, toss_decision) land here without
  bleeding into the UI contract.

Endpoints that care only about FilterBar use `FilterBarParams = Depends()`.
Endpoints that also want aux take both dependencies and pass aux to
`filters.build(aux=aux)`, which threads aux clauses centrally. This
keeps each router from re-wiring the same clause by hand (the original
`/matches` endpoint bug was precisely a missing hand-wire).

`FilterParams` is kept as an alias for `FilterBarParams` for incremental
migration — existing call sites keep working.
"""

from __future__ import annotations

from fastapi import Query
from typing import Optional

from .full_members import full_member_clause
from .club_tiers import primary_club_clause, secondary_club_clause
from .tournament_canonical import (
    is_canonical_with_variants,
    variants as canonical_variants,
    event_name_in_clause,
    series_type_clause,
)


# Sentinel used by Compare-tab per-slot URL overrides to express
# "explicit empty / do not inherit primary" — distinct from the param
# being absent (default-inherit) or empty-string (URL machinery's
# delete-on-falsy makes that indistinguishable from absent).
# Decoded as no-narrowing on the backend.
# Spec: internal_docs/spec-slot-override-chip-alignment.md §4.1.
ANY_SENTINEL = "__any__"


def _is_set(v) -> bool:
    """True iff v is a real narrowing value (not None, not '', not the
    `__any__` sentinel). Use at every clause guard that consumes a URL-
    derived filter field so the sentinel is consistently treated as
    no-narrowing."""
    return v not in (None, "", ANY_SENTINEL)


# Axis names recognised by FilterBarParams.build(drop=...). The single
# `season` name masks both season_from and season_to. Per-endpoint
# structural plumbing for tautology-prone baseline surfaces (player-
# compare position baselines, H2H baselines, venue character strips);
# not a user-facing toggle. Spec: internal_docs/spec-player-compare-
# average.md §4.6.
_DROP_AXES: frozenset[str] = frozenset({
    "gender", "team_type", "tournament", "season",
    "filter_venue", "filter_team", "filter_opponent",
    "team_class", "series_type",
})


class AuxParams:
    """Internal-plumbing narrowings, distinct from the FilterBar UI.

    Distinct from FilterBarParams so:
      - scope-link URLs and status-strip summaries can iterate FilterBar
        fields without accidentally including aux;
      - future page-local filters (result_filter, close_match,
        toss_decision, …) have a natural home without polluting the
        FilterBar contract.

    `series_type` was promoted from here to FilterBarParams 2026-04-28
    (10th FilterBar key) — see spec-filterbar-series-type.md.
    """

    def __init__(
        self,
        scope_to_team: Optional[str] = Query(
            None,
            description=(
                "Auto-narrow the scope (m.event_name) to tournaments this team"
                " has appeared in. Only applied by /scope/averages/* endpoints"
                " (team=None code path) AND only when no explicit tournament"
                " filter is active. Used by the Compare-tab avg slot so 'RCB"
                " vs avg' means 'RCB vs IPL avg', not 'RCB vs all-club-cricket"
                " avg' — semantically correct AND ~38x faster for single-"
                " tournament club teams."
            ),
        ),
        chip_team_class: Optional[str] = Query(
            None,
            description=(
                "DEPRECATED 2026-04-29 — superseded by"
                " `chip_baseline_scope_json` which carries the avg slot's"
                " full effective scope (handles narrowing AND broadening"
                " on every overridable axis, not just team_class). Kept"
                " as a back-compat shortcut for clients still on the v3"
                " hint contract; the frontend chipAlignmentFor in"
                " TeamCompareGrid emits BOTH fields through the rollout"
                " soak window. Remove after the soak: drop this Query +"
                " the Path 2 fallback in api/routers/teams::_league_aux"
                " + the back-compat REG URL"
                " `team_batting_summary_aus_chip_team_class_fm` in"
                " tests/regression/teams/urls.txt."
                " Spec: spec-slot-override-chip-alignment.md §5.2 + §8."
                " ───"
                " Original semantics: chip-baseline alignment hint sent"
                " by the Compare-tab team slot when a peer avg slot has"
                " team_class set. The team request's data is computed"
                " against the team's own scope (no team_class), but the"
                " league-side baseline used for chip envelope `scope_avg`"
                " is narrowed by the peer avg slot's team_class so chip"
                " ↔ displayed-avg-col agreement holds. Applied only"
                " inside `_league_aux`; team-side aggregates are"
                " unaffected."
            ),
        ),
        chip_baseline_scope_json: Optional[str] = Query(
            None,
            description=(
                "Generalised chip-baseline alignment — base64-encoded"
                " JSON of the peer avg slot's full effective scope"
                " (FilterBar fields + synthesized scope_to_team). When"
                " set, `_league_aux` parses it into a fresh"
                " (filters, aux) pair used as the league-side baseline,"
                " bypassing the narrower `chip_team_class` shortcut."
                " Lets chip math align under broaden-direction overrides"
                " (e.g. primary tournament=IPL, avg slot"
                " tournament=__any__ → chip baseline = all-club pool)."
                " Spec: spec-slot-override-chip-alignment.md §4.2."
            ),
        ),
        inning: Optional[int] = Query(
            None,
            ge=0,
            le=1,
            description=(
                "Page-local filter on i.innings_number (0 = batting"
                " first, 1 = batting second). User-visible on team and"
                " player Batting/Bowling/Fielding/Partnerships pages as"
                " a toggle pill; per-slot override on the Compare tab"
                " via `compareN_inning`. NOT on the FilterBar — its"
                " 10-key ceiling stands. Threaded through filters.build"
                " via aux=aux on every consumer; gated on"
                " has_innings_join because the clause references the"
                " innings alias. Match-level endpoints"
                " (has_innings_join=False) honour inning via the"
                " separate `_inning_match_filter` helper in"
                " api/routers/teams.py — see"
                " internal_docs/spec-inning-split.md §3.1a."
            ),
        ),
        result: Optional[str] = Query(
            None,
            description=(
                "Match-outcome filter from the path team's POV: 'won'"
                " | 'lost' | 'tied'. 'won' selects matches where the"
                " path team is outcome_winner; 'lost' selects matches"
                " where another team won; 'tied' collapses tied and"
                " no-result (outcome_winner IS NULL — T20 ties go to"
                " super-over and that winner becomes outcome_winner, so"
                " NULL is almost exclusively rain-shortened). Only"
                " meaningful when a path :team is bound — non-team"
                " endpoints silently ignore. Honoured in teams router"
                " via `_result_match_filter` (match level) and folded"
                " into both `_team_filter_clause` and"
                " `_team_innings_clause`. Spec:"
                " internal_docs/spec-splits-mosaic.md §1.1."
            ),
        ),
        toss_outcome: Optional[str] = Query(
            None,
            description=(
                "Toss-outcome filter from the path team's POV: 'won'"
                " | 'lost'. Restricts to matches where the team did"
                " (or did not) win the toss. Only meaningful when a"
                " path :team is bound. Spec:"
                " internal_docs/spec-splits-mosaic.md §1.1."
            ),
        ),
    ):
        # When AuxParams is instantiated outside FastAPI's dependency
        # injection (e.g. by sanity tests), the Query() defaults aren't
        # unwrapped and the field holds the Query object itself. Convert
        # those to None so downstream `is not None` checks behave the
        # same in tests as in production.
        from fastapi.params import Query as _QueryClass
        def _norm(v):
            return None if isinstance(v, _QueryClass) else v
        self.scope_to_team = _norm(scope_to_team)
        self.chip_team_class = _norm(chip_team_class)
        self.chip_baseline_scope_json = _norm(chip_baseline_scope_json)
        self.inning = _norm(inning)
        self.result = _norm(result)
        self.toss_outcome = _norm(toss_outcome)


class FilterBarParams:
    """The 8 FilterBar fields. Each maps to a frontend FILTER_KEYS entry."""

    def __init__(
        self,
        gender: Optional[str] = Query(None),
        team_type: Optional[str] = Query(None),
        tournament: Optional[str] = Query(None),
        season_from: Optional[str] = Query(None),
        season_to: Optional[str] = Query(None),
        filter_team: Optional[str] = Query(None),
        filter_opponent: Optional[str] = Query(None),
        filter_venue: Optional[str] = Query(None),
        team_class: Optional[str] = Query(
            None,
            description=(
                "Restrict to matches between two teams in a named class."
                " Polymorphic over team_type:"
                " `full_member` requires team_type='international' (= matches"
                " between ICC full-member nations);"
                " `primary_club` requires team_type='club' (= matches in a"
                " marquee international franchise league — IPL, BBL, PSL,"
                " BPL, CPL, SA20, ILT20, LPL, MLC, The Hundred (M+W), WBBL,"
                " WPL, …);"
                " `secondary_club` requires team_type='club' (= matches in"
                " a domestic state/county/provincial competition — Vitality"
                " Blast, SMA Trophy, CSA T20 Challenge, Super Smash, NPL,"
                " Women's Super Smash, …)."
                " Cross-type values are silent no-ops (defensive backend"
                " gate). Spec: internal_docs/spec-filterbar-team-class-club.md."
            ),
        ),
        series_type: Optional[str] = Query(
            None,
            description=(
                "Restrict to a category of series. Canonical values:"
                " all (default — no clause) / bilateral / icc / club."
                " Legacy aliases: bilateral_only → bilateral,"
                " tournament_only → icc. Promoted from AuxParams to"
                " FilterBarParams 2026-04-28 (the 10th FilterBar key)."
            ),
        ),
    ):
        self.gender = gender
        self.team_type = team_type
        self.tournament = tournament
        self.season_from = season_from
        self.season_to = season_to
        self.team = filter_team
        self.opponent = filter_opponent
        self.venue = filter_venue
        self.team_class = team_class
        self.series_type = series_type

    def build(
        self,
        has_innings_join: bool = True,
        table_alias: str = "m",
        innings_alias: str = "i",
        aux: Optional[AuxParams] = None,
        drop: Optional[set[str]] = None,
        apply_inning: bool = True,
    ) -> tuple[str, dict]:
        """Build WHERE clause fragments and params dict.

        Args:
            has_innings_join: If True, includes super_over filter and uses
                innings-level opponent logic. If False, uses match-level opponent logic.
            table_alias: Alias for the match table.
            innings_alias: Alias for the innings table.
            aux: Optional AuxParams to fold in page-local clauses (e.g.
                series_type) without each router having to hand-wire them.
            drop: Optional set of axis names to mask from clause construction.
                When an axis name is in `drop`, its clause and params are
                skipped entirely — useful for tautology-prone surfaces that
                need a "baseline with this narrowing removed" computation
                (e.g. compute the league baseline at the same scope as the
                player query but with the venue narrowing dropped). Per-
                endpoint structural plumbing, not a user-facing toggle. See
                internal_docs/spec-player-compare-average.md §4.6.
                Recognised names: gender, team_type, tournament, season,
                filter_venue, filter_team, filter_opponent, team_class,
                series_type. The single `season` name masks both
                season_from and season_to. Unknown names raise ValueError.

        Returns:
            (where_clause_str, params_dict) — the clause string includes leading
            AND for each condition so it can be appended after a WHERE 1=1 or
            existing conditions.
        """
        if drop:
            unknown = drop - _DROP_AXES
            if unknown:
                raise ValueError(
                    f"FilterParams.build(drop=...) got unknown axis name(s): "
                    f"{sorted(unknown)}. Recognised: {sorted(_DROP_AXES)}."
                )
        else:
            drop = set()

        clauses: list[str] = []
        params: dict = {}

        if has_innings_join:
            clauses.append(f"{innings_alias}.super_over = 0")

        if "gender" not in drop and _is_set(self.gender):
            clauses.append(f"{table_alias}.gender = :gender")
            params["gender"] = self.gender

        if "team_type" not in drop and _is_set(self.team_type):
            clauses.append(f"{table_alias}.team_type = :team_type")
            params["team_type"] = self.team_type

        if "tournament" not in drop and _is_set(self.tournament):
            # Canonical tournaments (e.g. "T20 World Cup (Men)") expand
            # to `event_name IN (variants)` — see api/tournament_canonical.py.
            # Single-variant / non-canonical names stay as equality.
            if is_canonical_with_variants(self.tournament):
                clauses.append(
                    event_name_in_clause(
                        canonical_variants(self.tournament),
                        col=f"{table_alias}.event_name",
                    )
                )
                # No bind param — IN list interpolated via f-string.
            else:
                clauses.append(f"{table_alias}.event_name = :tournament")
                params["tournament"] = self.tournament

        if "season" not in drop and _is_set(self.season_from):
            clauses.append(f"{table_alias}.season >= :season_from")
            params["season_from"] = self.season_from

        if "season" not in drop and _is_set(self.season_to):
            clauses.append(f"{table_alias}.season <= :season_to")
            params["season_to"] = self.season_to

        if "filter_venue" not in drop and _is_set(self.venue):
            clauses.append(f"{table_alias}.venue = :filter_venue")
            params["filter_venue"] = self.venue

        if "filter_team" not in drop and _is_set(self.team):
            if has_innings_join:
                clauses.append(f"{innings_alias}.team = :team")
            else:
                clauses.append(
                    f"({table_alias}.team1 = :team OR {table_alias}.team2 = :team)"
                )
            params["team"] = self.team

        if "filter_opponent" not in drop and _is_set(self.opponent):
            if has_innings_join:
                clauses.append(
                    f"(({table_alias}.team1 = :opponent AND {innings_alias}.team = {table_alias}.team2)"
                    f" OR ({table_alias}.team2 = :opponent AND {innings_alias}.team = {table_alias}.team1))"
                )
            else:
                clauses.append(
                    f"({table_alias}.team1 = :opponent OR {table_alias}.team2 = :opponent)"
                )
            params["opponent"] = self.opponent

        # team_class is polymorphic over team_type. Each value pairs
        # with one team_type; cross-type combinations are silent
        # no-ops (preserves URL robustness when the frontend gate
        # fails or a curl request mixes them). Spec §3.
        #
        # When `team_type` is in `drop`, the polymorphism guard sees
        # team_type as effectively None — so team_class clauses
        # (which embed their own `m.team_type = …` predicate) do not
        # fire either. This keeps `drop={'team_type'}` semantically
        # equivalent to "as if team_type was never set" rather than
        # leaving team_class's embedded team_type predicate behind.
        eff_team_type = None if "team_type" in drop else self.team_type
        if "team_class" not in drop and _is_set(self.team_class):
            if self.team_class == "full_member" and eff_team_type == "international":
                clauses.append(full_member_clause(table_alias=table_alias))
            elif self.team_class == "primary_club" and eff_team_type == "club":
                clauses.append(primary_club_clause(table_alias=table_alias))
            elif self.team_class == "secondary_club" and eff_team_type == "club":
                clauses.append(secondary_club_clause(table_alias=table_alias))

        # series_type — promoted to FilterBar 2026-04-28. Reads from
        # self; the historical `aux.series_type` path is removed.
        if "series_type" not in drop and _is_set(self.series_type):
            st = series_type_clause(self.series_type, alias=table_alias)
            if st:
                clauses.append(st)

        # inning (AuxParams) — page-local 1st/2nd-innings filter. Gated
        # on has_innings_join because the clause references the innings
        # alias; match-level endpoints honour inning via
        # _inning_match_filter in api/routers/teams.py instead. Spec:
        # internal_docs/spec-inning-split.md.
        # Per-event innings_number narrowing. `apply_inning=False` lets
        # player/team discipline callers suppress this in favour of the
        # match-subset clause (player_inning_match_clause /
        # _inning_match_filter) — the Option-B "batted-first" unification
        # (internal_docs/spec-inning-unify-option-b.md). Match-level
        # endpoints already route inning through the match filter, so
        # they pass apply_inning=False too.
        if apply_inning and has_innings_join and aux is not None and aux.inning is not None:
            clauses.append(f"{innings_alias}.innings_number = :inning")
            params["inning"] = aux.inning

        where = " AND ".join(clauses) if clauses else ""
        return where, params

    def build_side_neutral(
        self,
        has_innings_join: bool = True,
        table_alias: str = "m",
        innings_alias: str = "i",
        aux: Optional[AuxParams] = None,
        apply_inning: bool = True,
    ) -> tuple[str, dict]:
        """Like build(), but filter_team / filter_opponent are applied
        at MATCH level instead of innings level.

        build() uses `i.team = :team` — correct for batting (a batter's
        innings IS his team's innings). For fielding / bowling / keeping
        queries, the player's records live in the OPPONENT's batting
        innings (you're in the field while they bat). So `i.team = :team`
        forces the wrong side and returns zero.

        This variant:
          - drops the i.team = :team / i.team-vs-opponent clauses
          - applies `(m.team1 = :team OR m.team2 = :team)` at match level
          - applies `(m.team1 = :opp OR m.team2 = :opp)` for opponent
          - when both set, requires the match pair exactly
        """
        saved_team = self.team
        saved_opp = self.opponent
        self.team = None
        self.opponent = None
        try:
            where, params = self.build(
                has_innings_join, table_alias, innings_alias, aux=aux,
                apply_inning=apply_inning,
            )
        finally:
            self.team = saved_team
            self.opponent = saved_opp

        pair_clauses: list[str] = []
        if saved_team and saved_opp:
            pair_clauses.append(
                f"(({table_alias}.team1 = :sn_team AND {table_alias}.team2 = :sn_opp)"
                f" OR ({table_alias}.team1 = :sn_opp AND {table_alias}.team2 = :sn_team))"
            )
            params["sn_team"] = saved_team
            params["sn_opp"] = saved_opp
        elif saved_team:
            pair_clauses.append(f"({table_alias}.team1 = :sn_team OR {table_alias}.team2 = :sn_team)")
            params["sn_team"] = saved_team
        elif saved_opp:
            pair_clauses.append(f"({table_alias}.team1 = :sn_opp OR {table_alias}.team2 = :sn_opp)")
            params["sn_opp"] = saved_opp

        if pair_clauses:
            where = " AND ".join([where] + pair_clauses) if where else " AND ".join(pair_clauses)
        return where, params


# Backward-compat alias — existing code imports FilterParams everywhere.
# Gradual rename over time.
FilterParams = FilterBarParams


def player_result_clause(
    aux: Optional[AuxParams],
    person_id: str,
    params: dict,
    match_id_expr: str = "m.id",
    key: str = "prc_pid",
) -> str:
    """Player-POV `result` aux narrowing — the player-page sibling of
    the team-POV `_result_match_filter` in api/routers/teams.py.

    The subject team is the player's OWN side per match
    (`matchplayer.team`), so this works across every team a player has
    turned out for (India, RCB, …) using each match's actual team —
    unlike the team-POV clause which compares a single fixed `:team`.

      'won'  → the player's team is the match's outcome_winner
      'lost' → there is a winner and it is NOT the player's team
      'tied' → outcome_winner IS NULL (collapses true ties + no-results,
               mirroring the team-POV + Mosaic convention)

    Returns a BARE clause (no leading AND) for splicing into a parts
    list, binding :<key>; "" when aux.result is unset. `match_id_expr`
    is the outer query's match-id column (the consuming query must have
    the relevant table in scope, e.g. `m.id` or `i.match_id`).
    """
    if aux is None or not getattr(aux, "result", None):
        return ""
    r = aux.result
    if r == "won":
        cond = "mm.outcome_winner = mp.team"
    elif r == "lost":
        cond = "mm.outcome_winner IS NOT NULL AND mm.outcome_winner != mp.team"
    elif r == "tied":
        cond = "mm.outcome_winner IS NULL"
    else:
        return ""
    params[key] = person_id
    return (
        f"{match_id_expr} IN ("
        f"SELECT mp.match_id FROM matchplayer mp "
        f"JOIN match mm ON mm.id = mp.match_id "
        f"WHERE mp.person_id = :{key} AND {cond})"
    )


def player_inning_match_clause(
    aux: Optional[AuxParams],
    person_id: str,
    params: dict,
    match_id_expr: str = "m.id",
    key: str = "pim_pid",
    side: str = "batting",
) -> str:
    """Player-POV `inning` narrowing — Option-B, DISCIPLINE-AWARE
    (internal_docs/spec-inning-unify-option-b.md). The toggle label
    `inning=N` means "the player's team batted in innings N", but the
    underlying filter follows the innings the discipline actually
    happened in:

      side='batting'                  → matches the player's team BATTED
                                        in innings_number = N
                                        (mp2.team = i2.team, inn = N)
      side bowling/fielding/keeping   → matches the player's team FIELDED
                                        in innings_number = (1 - N)
                                        (mp2.team != i2.team, inn = 1-N)

    The fielding-side form is deliberately keyed on the FIELDING innings,
    not "matches the team batted in N": a match the player BOWLED in but
    his team never BATTED (e.g. a rain-abandoned game they fielded first
    and the chase never started) carries real wickets/balls that MUST
    count toward the bowling average and its denominator. A batting-keyed
    subset would silently drop it. So batting and bowling can legitimately
    span different match counts at the same inning value.

    Works at any grain (match_id_expr defaults to m.id) — innings-grain
    summaries AND per-match precomp records alike. Callers must suppress
    the central clause (`build(..., apply_inning=False)`). Returns a BARE
    clause (no leading AND); "" when aux.inning is unset.
    """
    if aux is None or aux.inning is None:
        return ""
    bat = side == "batting"
    params[key] = person_id
    params["pim_inn"] = aux.inning if bat else (1 - aux.inning)
    team_rel = "=" if bat else "!="
    return (
        f"{match_id_expr} IN ("
        f"SELECT i2.match_id FROM innings i2 "
        f"JOIN matchplayer mp2 ON mp2.match_id = i2.match_id "
        f"AND mp2.person_id = :{key} AND mp2.team {team_rel} i2.team "
        f"WHERE i2.innings_number = :pim_inn AND i2.super_over = 0)"
    )
