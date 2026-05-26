"""Aux-narrowing clauses spliced into JOIN-context SQL.

Defines the protocol every page-local AuxParams field follows when its
narrowing has to be added to a SQL where-clause where the relevant
alias is in scope but `FilterBarParams.build()` suppressed the clause
via has_innings_join=False (typically because the same where is
reused on a bare-table fast path lacking the alias, or because the
build() gate is conservative).

Two consumer patterns:

  • Leaders endpoints (`api/routers/{batting,bowling,fielding}.py`)
    use `splice_aux_join_clauses(aux, params)` — gets the
    concatenated AND-prefixed fragment, mutates `params` to bind.
  • Tournaments dossier (`api/routers/tournaments.py`) uses the
    same helper via `_inning_extras` (kept as a thin wrapper so its
    callers don't have to know about the registry).

To add a new aux narrowing:

  1. Add the field to `AuxParams` in `api/filters.py`.
  2. Add a `JoinClause` subclass below.
  3. Append it to `JOIN_CLAUSES`.

Order matters for SQL legibility but NOT correctness (AND is
commutative). If a future query planner hint requires a specific
order, lift `JOIN_CLAUSES` to a config file.

Convention rationale: a previous design used three copy-pasted
inline blocks (one per leaders endpoint) that built the inning
clause + mutated params + concatenated. User feedback 2026-04-30:
"better that you iterate through a set of functions via an
interface". This module is that interface.
Spec: internal_docs/design-decisions.md "Aux-clause registry".
"""
from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .filters import AuxParams


class JoinClause(Protocol):
    """An aux-narrowing clause splicer.

    Returns the AND-prefixed fragment to append to a JOIN-context
    where (e.g. ' AND i.innings_number = :inning'), mutating the
    params dict to bind the values. Empty string when this aux
    field isn't set on the request.

    Implementations should be stateless — the registry holds one
    instance per class.
    """
    def splice(self, aux: "AuxParams | None", params: dict, side: str = "batting") -> str: ...


class InningClause:
    """`aux.inning` → ' AND i.innings_number = :inning' (or the flipped
    bind for bowling/fielding).

    Option B (spec-inning-unify-option-b.md §2): the `inning=N` toggle
    means "the subject's team batted in innings N", but the FILTER is
    per-event and discipline-aware:

      batting / match  → innings_number = N        (bind :inning)
      bowling / fielding → innings_number = (1 - N) (bind :inning_flip)

    A team that bats in innings N bowls in the OTHER innings, so a
    bowling/fielding leaderboard at the toggle's "bowled first" (= the
    team batted second = inning=1) must read innings_number 0. The
    flipped side uses a DISTINCT bind (`:inning_flip`) so a mixed
    endpoint can splice a batting (`:inning`) and a bowling
    (`:inning_flip`) clause into different sub-queries without the two
    binds colliding. batting/match path is byte-identical to pre-Option-B.

    Splices into innings-joined SQL only — match-level callers (no
    innings alias) honour inning via `_inning_match_filter` in
    api/routers/teams.py / the per-event team helper.
    """
    def splice(self, aux, params: dict, side: str = "batting") -> str:
        if aux is None or aux.inning is None:
            return ""
        if side in ("batting", "match"):
            params["inning"] = aux.inning
            return " AND i.innings_number = :inning"
        params["inning_flip"] = 1 - aux.inning
        return " AND i.innings_number = :inning_flip"


# Order-stable registry. Append here when a new aux narrowing lands.
# Order is for SQL legibility only — if it starts mattering for query
# planner hints, move to a config file.
JOIN_CLAUSES: list[JoinClause] = [
    InningClause(),
]


def splice_aux_join_clauses(aux: "AuxParams | None", params: dict, side: str = "batting") -> str:
    """Concatenate every registered `JoinClause` splice into a single
    AND-prefixed string. Mutates `params` to bind. Empty string when
    no aux narrowing is set on this request — caller can use that as
    a sniff signal alongside `bool(match_where)` to gate fast paths.

    `side` is the discipline POV for Option-B inning narrowing
    (batting / match → innings_number=N; bowling / fielding → the
    flipped (1-N) innings; see `InningClause`). Defaults to 'batting'
    so existing batting/match callers are byte-identical.
    """
    return "".join(c.splice(aux, params, side) for c in JOIN_CLAUSES)
