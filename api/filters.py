"""Filter system for CricsDB API queries.

Two-class model:

- `FilterBarParams` — the 8 fields driven by the frontend's FilterBar UI
  (gender, team_type, tournament, season_from/to, filter_team,
  filter_opponent, filter_venue). Maps 1:1 with `FILTER_KEYS` on the
  frontend (`components/scopeLinks.ts`). Rides through scope-link URLs.

- `AuxParams` — page-local narrowings that don't originate from the
  FilterBar. Currently `series_type` (Series-tab local pill). Future
  page-local filters (result_filter, close_match, super_over,
  toss_decision) land here without bleeding into the UI contract.

Endpoints that care only about FilterBar use `FilterBarParams = Depends()`.
Endpoints that also want aux take both dependencies and pass aux to
`filters.build(aux=aux)`, which threads `series_type_clause` and future
aux clauses centrally. This keeps each router from re-wiring the same
clause by hand (the original `/matches` endpoint bug was precisely a
missing hand-wire).

`FilterParams` is kept as an alias for `FilterBarParams` for incremental
migration — existing call sites keep working.
"""

from __future__ import annotations

from fastapi import Query
from typing import Optional

from .tournament_canonical import (
    is_canonical_with_variants,
    variants as canonical_variants,
    event_name_in_clause,
    series_type_clause,
)


class AuxParams:
    """Page-local, non-FilterBar narrowings.

    Distinct from FilterBarParams so:
      - scope-link URLs and status-strip summaries can iterate FilterBar
        fields without accidentally including aux;
      - future page-local filters (result_filter, close_match,
        toss_decision, …) have a natural home without polluting the
        FilterBar contract.
    """

    def __init__(
        self,
        series_type: Optional[str] = Query(
            None,
            description=(
                "Page-local narrowing: all (default) / bilateral / icc / club."
                " Legacy: bilateral_only / tournament_only."
            ),
        ),
    ):
        self.series_type = series_type


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
    ):
        self.gender = gender
        self.team_type = team_type
        self.tournament = tournament
        self.season_from = season_from
        self.season_to = season_to
        self.team = filter_team
        self.opponent = filter_opponent
        self.venue = filter_venue

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

        if self.gender:
            clauses.append(f"{table_alias}.gender = :gender")
            params["gender"] = self.gender

        if self.team_type:
            clauses.append(f"{table_alias}.team_type = :team_type")
            params["team_type"] = self.team_type

        if self.tournament:
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

        if self.season_from:
            clauses.append(f"{table_alias}.season >= :season_from")
            params["season_from"] = self.season_from

        if self.season_to:
            clauses.append(f"{table_alias}.season <= :season_to")
            params["season_to"] = self.season_to

        if self.venue:
            clauses.append(f"{table_alias}.venue = :filter_venue")
            params["filter_venue"] = self.venue

        if self.team:
            if has_innings_join:
                clauses.append(f"{innings_alias}.team = :team")
            else:
                clauses.append(
                    f"({table_alias}.team1 = :team OR {table_alias}.team2 = :team)"
                )
            params["team"] = self.team

        if self.opponent:
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

        # Aux clauses fold in here centrally — no router hand-wiring.
        if aux is not None and aux.series_type:
            st = series_type_clause(aux.series_type, alias=table_alias)
            if st:
                clauses.append(st)

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
