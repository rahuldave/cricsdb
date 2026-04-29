"""Filter system for CricsDB API queries.

Two-class model:

- `FilterBarParams` — the 10 fields driven by the frontend's FilterBar
  UI (gender, team_type, tournament, season_from/to, filter_team,
  filter_opponent, filter_venue, team_class, series_type). Maps 1:1 with
  `FILTER_KEYS` on the frontend (`components/scopeLinks.ts`). Rides
  through scope-link URLs.

- `AuxParams` — internal-plumbing narrowings that don't originate from
  the FilterBar. Currently `scope_to_team` (Compare-tab avg-slot
  auto-narrow) and `chip_team_class` (chip-baseline alignment hint).
  Future page-local filters (result_filter, close_match, super_over,
  toss_decision) land here without bleeding into the UI contract.

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
                " Currently supports `full_member` (= matches between ICC"
                " full-member nations only). No-op when team_type !="
                " 'international' (defensive backend gate — full-member"
                " status is an intl classification)."
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
    ) -> tuple[str, dict]:
        """Build WHERE clause fragments and params dict.

        Args:
            has_innings_join: If True, includes super_over filter and uses
                innings-level opponent logic. If False, uses match-level opponent logic.
            table_alias: Alias for the match table.
            innings_alias: Alias for the innings table.
            aux: Optional AuxParams to fold in page-local clauses (e.g.
                series_type) without each router having to hand-wire them.

        Returns:
            (where_clause_str, params_dict) — the clause string includes leading
            AND for each condition so it can be appended after a WHERE 1=1 or
            existing conditions.
        """
        clauses: list[str] = []
        params: dict = {}

        if has_innings_join:
            clauses.append(f"{innings_alias}.super_over = 0")

        if _is_set(self.gender):
            clauses.append(f"{table_alias}.gender = :gender")
            params["gender"] = self.gender

        if _is_set(self.team_type):
            clauses.append(f"{table_alias}.team_type = :team_type")
            params["team_type"] = self.team_type

        if _is_set(self.tournament):
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

        if _is_set(self.season_from):
            clauses.append(f"{table_alias}.season >= :season_from")
            params["season_from"] = self.season_from

        if _is_set(self.season_to):
            clauses.append(f"{table_alias}.season <= :season_to")
            params["season_to"] = self.season_to

        if _is_set(self.venue):
            clauses.append(f"{table_alias}.venue = :filter_venue")
            params["filter_venue"] = self.venue

        if _is_set(self.team):
            if has_innings_join:
                clauses.append(f"{innings_alias}.team = :team")
            else:
                clauses.append(
                    f"({table_alias}.team1 = :team OR {table_alias}.team2 = :team)"
                )
            params["team"] = self.team

        if _is_set(self.opponent):
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

        # team_class is a FilterBar narrowing, defensive-gated to
        # team_type='international'. For clubs the FM list (country
        # names) doesn't match franchise team strings so it would zero
        # out every match — silent no-op preserves club URL robustness.
        if (
            _is_set(self.team_class)
            and self.team_class == "full_member"
            and self.team_type == "international"
        ):
            clauses.append(full_member_clause(table_alias=table_alias))

        # series_type — promoted to FilterBar 2026-04-28. Reads from
        # self; the historical `aux.series_type` path is removed.
        if _is_set(self.series_type):
            st = series_type_clause(self.series_type, alias=table_alias)
            if st:
                clauses.append(st)

        # inning (AuxParams) — page-local 1st/2nd-innings filter. Gated
        # on has_innings_join because the clause references the innings
        # alias; match-level endpoints honour inning via
        # _inning_match_filter in api/routers/teams.py instead. Spec:
        # internal_docs/spec-inning-split.md.
        if has_innings_join and aux is not None and aux.inning is not None:
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
