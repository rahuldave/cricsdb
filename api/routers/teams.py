"""Teams router — team records, results, head-to-head, by-season."""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams, _is_set
from ..form_windows import scope_anchor
from ..full_members import ICC_FULL_MEMBERS
from ..metrics_metadata import wrap_metric
from ..scope_links import scope_dict_from_filters, suggested_splits
from ..tournament_canonical import series_type as series_type_for, canonicalize
from ..wilson import prob_record

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])


def _decode_chip_baseline(b64: str) -> tuple[FilterParams, AuxParams] | None:
    """Decode the `chip_baseline_scope_json` aux field — base64-JSON of
    the peer avg slot's effective scope — into a fresh
    (FilterBarParams, AuxParams) pair the league-side aggregation can
    use directly. Returns None on parse error (caller falls back to the
    legacy `chip_team_class` + `scope_to_team` synthesis path).

    Payload shape (any subset of the keys, all strings):
      gender, team_type, tournament, season_from, season_to,
      filter_venue, series_type, team_class, scope_to_team

    Spec: spec-slot-override-chip-alignment.md §4.2, §5.2.
    """
    import base64, json
    try:
        raw = base64.b64decode(b64, validate=True)
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    f = FilterParams(
        gender=payload.get("gender"),
        team_type=payload.get("team_type"),
        tournament=payload.get("tournament"),
        season_from=payload.get("season_from"),
        season_to=payload.get("season_to"),
        filter_team=None,
        filter_opponent=None,
        filter_venue=payload.get("filter_venue"),
        team_class=payload.get("team_class"),
        series_type=payload.get("series_type"),
    )
    # `inning` rides in payload as a string ('0' / '1') — the
    # OVERRIDABLE_SLOT_KEYS iterate in chipAlignmentFor reads it from
    # ResolvedSlotScope where it's typed as string. Backend AuxParams
    # expects int. Convert here so the league-side aggregation honours
    # the avg slot's inning narrowing for chip math alignment. Spec:
    # spec-inning-split.md §6.5 + §8.
    raw_inning = payload.get("inning")
    inning_val: int | None = None
    if raw_inning is not None:
        try:
            iv = int(raw_inning)
            if iv in (0, 1):
                inning_val = iv
        except (TypeError, ValueError):
            inning_val = None
    a = AuxParams(
        scope_to_team=payload.get("scope_to_team"),
        chip_team_class=None,
        chip_baseline_scope_json=None,
        inning=inning_val,
    )
    return f, a


def _inning_match_filter(
    team_value: str | None,
    aux: AuxParams | None,
) -> tuple[str, dict]:
    """Match-level WHERE fragment restricting to matches where :team had
    a role in the chosen inning. Empty when aux.inning is None or team
    is unknown.

    Semantics: aux.inning=0 → matches where :team batted in
    innings_number=0 (= matches where :team batted first).
    aux.inning=1 → matches where :team batted second.

    NOT the same as the Compare-slot dual-meaning of §3.4 — this helper
    is for match-level endpoints (/summary, /by-season, /vs-opponent,
    /match-list) where there's a single match subset. Bat-side framing
    is the natural reading for results-style metrics ("RCB's record
    batting first"). For Compare-slot dual-meaning on bowling/fielding
    rows, the central innings clause in FilterBarParams.build() handles
    it via the i.team discriminator already present in those queries.

    Spec: internal_docs/spec-inning-split.md §3.1a.
    """
    if aux is None or aux.inning is None or not team_value:
        return "", {}
    return (
        "m.id IN ("
        " SELECT i2.match_id FROM innings i2"
        " WHERE i2.team = :im_team"
        "   AND i2.innings_number = :im_inn"
        "   AND i2.super_over = 0"
        ")",
        {"im_team": team_value, "im_inn": aux.inning},
    )


def _result_match_filter(
    team_value: str | None,
    aux: AuxParams | None,
) -> tuple[str, dict]:
    """Match-level WHERE fragment for aux.result. Empty when aux.result
    is unset or no team is bound (the filter is path-team-relative and
    has no meaning without a subject).

    Semantics:
      'won'  → m.outcome_winner = :team
      'lost' → m.outcome_winner IS NOT NULL AND m.outcome_winner != :team
      'tied' → m.outcome_winner IS NULL (collapses tied + no-result; T20
               ties are decided by super-over so a NULL outcome_winner
               is almost exclusively rain-abandoned)

    Spec: internal_docs/spec-splits-mosaic.md §1.1.
    """
    if aux is None or aux.result is None or not team_value:
        return "", {}
    params = {"rmf_team": team_value}
    if aux.result == "won":
        return "m.outcome_winner = :rmf_team", params
    if aux.result == "lost":
        return (
            "(m.outcome_winner IS NOT NULL AND m.outcome_winner != :rmf_team)",
            params,
        )
    if aux.result == "tied":
        return "m.outcome_winner IS NULL", {}
    return "", {}


def _toss_outcome_match_filter(
    team_value: str | None,
    aux: AuxParams | None,
) -> tuple[str, dict]:
    """Match-level WHERE fragment for aux.toss_outcome. Empty when unset
    or no team is bound. Requires m.toss_winner IS NOT NULL so matches
    with un-recorded toss (rare) are excluded from both 'won' and 'lost'
    slices.

    Spec: internal_docs/spec-splits-mosaic.md §1.1.
    """
    if aux is None or aux.toss_outcome is None or not team_value:
        return "", {}
    params = {"tmf_team": team_value}
    if aux.toss_outcome == "won":
        return (
            "(m.toss_winner IS NOT NULL AND m.toss_winner = :tmf_team)",
            params,
        )
    if aux.toss_outcome == "lost":
        return (
            "(m.toss_winner IS NOT NULL AND m.toss_winner != :tmf_team)",
            params,
        )
    return "", {}


def _team_filter_clause(
    filters: FilterParams,
    team_param: str = ":team",
    aux: AuxParams | None = None,
    team_value: str | None = None,
) -> tuple[str, dict]:
    """Build match-level filter clause for team queries (no innings join).

    `team_value` is the path-team string (e.g. "Royal Challengers
    Bengaluru"). Required only when aux.inning is set so
    _inning_match_filter can derive the match-id subquery — otherwise
    it's optional and falls back to filters.team (the FilterBar
    `filter_team`). Path-team endpoints should always pass team_value
    explicitly.
    """
    where, params = filters.build(has_innings_join=False, aux=aux)
    parts = [f"(m.team1 = {team_param} OR m.team2 = {team_param})"]
    if where:
        parts.append(where)
    tv = team_value or filters.team
    inn_clause, inn_params = _inning_match_filter(tv, aux)
    if inn_clause:
        parts.append(inn_clause)
        params.update(inn_params)
    res_clause, res_params = _result_match_filter(tv, aux)
    if res_clause:
        parts.append(res_clause)
        params.update(res_params)
    toss_clause, toss_params = _toss_outcome_match_filter(tv, aux)
    if toss_clause:
        parts.append(toss_clause)
        params.update(toss_params)
    return " AND ".join(parts), params


@router.get("/landing")
async def teams_landing(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Filter-sensitive directory of teams for the Teams search landing.

    Returns:
      - international: { men: { regular, associate }, women: { regular, associate } }
        — split by gender so women's full members aren't buried in a
        mixed list, and split by ICC full-member status within each.
        When a gender filter is set, only that gender's bucket is populated.
      - club: { franchise_leagues, domestic_leagues, women_franchise, other }
        — tournaments classified using the tournaments-router series_type
        map so franchise leagues (IPL, BBL, …) are visually separate
        from domestic leagues (Vitality Blast, Syed Mushtaq Ali, CSA T20)
        and women's franchise leagues (WBBL, WPL, …).

    All match counts reflect the current filter scope, so teams with
    zero matches in window (e.g. Rising Pune Supergiant outside
    2016–2017) vanish naturally.
    """
    db = get_db()
    where, params = filters.build(has_innings_join=False, aux=aux)

    # International — aggregate by team AND gender, then bucket into
    # men's / women's so each gender has its own collapsible section.
    men_regular: list[dict] = []
    men_associate: list[dict] = []
    women_regular: list[dict] = []
    women_associate: list[dict] = []
    if filters.team_type != "club":
        intl_parts = ["m.team_type = 'international'"]
        if where:
            intl_parts.append(where)
        intl_rows = await db.q(
            f"""
            SELECT mp.team AS name, m.gender AS gender,
                   COUNT(DISTINCT m.id) AS matches
            FROM matchplayer mp
            JOIN match m ON m.id = mp.match_id
            WHERE {" AND ".join(intl_parts)}
            GROUP BY mp.team, m.gender
            ORDER BY matches DESC, mp.team
            """,
            params,
        )
        for r in intl_rows:
            entry = {"name": r["name"], "gender": r["gender"], "matches": r["matches"]}
            is_full_member = r["name"] in ICC_FULL_MEMBERS
            if r["gender"] == "female":
                (women_regular if is_full_member else women_associate).append(entry)
            else:
                (men_regular if is_full_member else men_associate).append(entry)

    # Club — (team, tournament, gender) tuples. Group tournaments by
    # total match count in window; within a tournament, teams alphabetical.
    # Each tournament is then bucketed by series_type so franchise
    # leagues, domestic championships (SMAT, Vitality Blast, CSA T20)
    # and women's franchise leagues get their own collapsible sections.
    franchise_leagues: list[dict] = []
    domestic_leagues: list[dict] = []
    women_franchise: list[dict] = []
    other_club: list[dict] = []
    if filters.team_type != "international":
        club_parts = ["m.team_type = 'club'", "m.event_name IS NOT NULL"]
        if where:
            club_parts.append(where)
        club_rows = await db.q(
            f"""
            SELECT mp.team AS name, m.event_name AS tournament,
                   m.gender AS gender,
                   COUNT(DISTINCT m.id) AS matches
            FROM matchplayer mp
            JOIN match m ON m.id = mp.match_id
            WHERE {" AND ".join(club_parts)}
            GROUP BY mp.team, m.event_name, m.gender
            """,
            params,
        )
        by_tournament: dict[str, list[dict]] = {}
        tourney_totals: dict[str, int] = {}
        for r in club_rows:
            t = r["tournament"]
            by_tournament.setdefault(t, []).append({
                "name": r["name"],
                "gender": r["gender"],
                "matches": r["matches"],
            })
            tourney_totals[t] = tourney_totals.get(t, 0) + (r["matches"] or 0)
        for t in sorted(by_tournament.keys(), key=lambda x: (-tourney_totals[x], x)):
            teams = sorted(by_tournament[t], key=lambda x: x["name"].lower())
            entry = {
                "tournament": t,
                "matches": tourney_totals[t],
                "teams": teams,
            }
            stype = series_type_for(t)
            if stype == "franchise_league":
                franchise_leagues.append(entry)
            elif stype == "domestic_league":
                domestic_leagues.append(entry)
            elif stype == "women_franchise":
                women_franchise.append(entry)
            else:
                other_club.append(entry)

    return {
        "international": {
            "men":   {"regular": men_regular,   "associate": men_associate},
            "women": {"regular": women_regular, "associate": women_associate},
        },
        "club": {
            "franchise_leagues": franchise_leagues,
            "domestic_leagues": domestic_leagues,
            "women_franchise": women_franchise,
            "other": other_club,
        },
    }


# ============================================================
# /splits — Splits Mosaic backing endpoint (Spec: spec-splits-mosaic.md §1.3-1.5)
#
# Joint distribution of (toss_outcome × team_inning × result) over
# the active filter scope. Two modes:
#   - Landing (?team= absent): league-side only. Cells reflect the
#     unpivoted "team-views" of every match in scope (each match
#     contributes 2 team-views, one per side). Aux filters
#     result / toss_outcome are 400-rejected here — both are
#     subject-POV filters that need a team to evaluate against.
#   - Team-detail (?team=X set): dual-query envelope. Team-side
#     cells + league-side cells at the same filter scope + per-cell
#     deltas (share - league_share) / league_share × 100. Same
#     envelope pattern as /summary's scope_avg.
#
# Aux filters honoured at endpoint level (cell-level post-filter):
#   inning, result, toss_outcome — restricted cells flow through
#   to the response. Marginals are always over the FULL 12-cell
#   grid pre-cell-filter so the frontend can still render
#   marginals when the user has filtered.
# ============================================================

def _cell_label_for_aux(
    toss_outcome: str, team_inning: int, result: str,
    aux: AuxParams,
) -> bool:
    """Cell-level post-filter: True iff this (toss_outcome, team_inning,
    result) cell should appear in the response given the aux narrowings.
    """
    if aux.toss_outcome is not None and aux.toss_outcome != toss_outcome:
        return False
    if aux.inning is not None and aux.inning != team_inning:
        return False
    if aux.result is not None and aux.result != result:
        return False
    return True


async def _splits_cells(
    where: str, params: dict, team_filter: str | None,
) -> tuple[list[dict], int]:
    """Run the team_views-unpivot GROUP BY and return raw cell rows
    plus the total team-view count (sum of all cell n).

    `team_filter`, if set, is added as `AND tv.team_view = :_sp_team` —
    used for the team-side query. Caller binds :_sp_team into params.
    """
    db = get_db()
    extra = f" AND tv.team_view = :_sp_team" if team_filter else ""
    sql = f"""
    WITH team_views AS (
      SELECT m.id AS match_id, m.team1 AS team_view FROM match m WHERE {where}
      UNION ALL
      SELECT m.id AS match_id, m.team2 AS team_view FROM match m WHERE {where}
    )
    SELECT
      CASE WHEN tv.team_view = m.toss_winner THEN 'won' ELSE 'lost' END AS toss_outcome,
      CASE WHEN (m.toss_decision = 'bat' AND m.toss_winner = tv.team_view)
             OR (m.toss_decision = 'field' AND m.toss_winner <> tv.team_view)
           THEN 0 ELSE 1 END AS team_inning,
      CASE WHEN m.outcome_winner = tv.team_view THEN 'won'
           WHEN m.outcome_winner IS NULL THEN 'tied'
           ELSE 'lost' END AS result,
      COUNT(*) AS n
    FROM team_views tv
    JOIN match m ON m.id = tv.match_id
    WHERE m.toss_winner IS NOT NULL{extra}
    GROUP BY toss_outcome, team_inning, result
    """
    rows = await db.q(sql, params)
    out = [
        {"toss_outcome": r["toss_outcome"], "inning": r["team_inning"],
         "result": r["result"], "n": r["n"]}
        for r in rows
    ]
    total = sum(c["n"] for c in out)
    return out, total


def _marginals(cells: list[dict], total: int) -> dict:
    """Aggregate marginal counts + Wilson CIs over the 3 axes.

    `total` is the denominator for share (sum of all cell n).
    """
    from ..wilson import wilson_ci
    out: dict[str, dict] = {
        "toss_outcome": {}, "inning": {}, "result": {},
    }
    for axis in out:
        sums: dict = {}
        for c in cells:
            sums[c[axis]] = sums.get(c[axis], 0) + c["n"]
        for v, n in sums.items():
            lo, hi = wilson_ci(n, total)
            key = str(v) if axis == "inning" else v
            out[axis][key] = {
                "n": n,
                "share": round(n / total, 4) if total else None,
                "wilson_lo": round(lo, 4) if lo is not None else None,
                "wilson_hi": round(hi, 4) if hi is not None else None,
            }
    return out


@router.get("/splits")
async def team_splits(
    team: Optional[str] = Query(
        None,
        description=(
            "Optional team name. When set, response carries team-side"
            " cells + league-side baseline + per-cell deltas. When"
            " absent (landing case), response carries league-side only."
        ),
    ),
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Joint (toss × inning × result) distribution.

    Spec: internal_docs/spec-splits-mosaic.md §1.3.
    """
    # Previously this endpoint 400'd ?result= / ?toss_outcome= without
    # ?team= on the "tautological 50% by construction" argument. That
    # missed the useful angle: while the MARGINAL of the filtered axis
    # is forced (one team-view per match on the toss-winner side, =
    # half the unpivot), the INNER joint distribution
    # (inning × outcome | toss=won) is the league-level conditional
    # baseline — exactly what users read off as the comparison anchor
    # for team-detail conditional win rates. Gate lifted 2026-05-11.
    # Spec §1.4 amended.

    # ── Build base WHERE (filter scope, no team binding) ─────────────
    # We null out filters.team / filters.opponent so the same WHERE
    # works for both the league-side (unpivot all team-views) and
    # team-side (restrict to one team-view) queries.
    saved_team = filters.team
    saved_opp = filters.opponent
    filters.team = None
    filters.opponent = None
    try:
        base_where, base_params = filters.build(has_innings_join=False, aux=aux)
    finally:
        filters.team = saved_team
        filters.opponent = saved_opp
    base_where = base_where or "1=1"

    # ── League side ──────────────────────────────────────────────────
    league_cells_all, _league_unfiltered = await _splits_cells(
        base_where, dict(base_params), team_filter=None,
    )

    # ── Team side (only when team is set) ───────────────────────────
    team_cells_all: list[dict] = []
    if team:
        team_params = dict(base_params)
        team_params["_sp_team"] = team
        team_cells_all, _ = await _splits_cells(
            base_where, team_params, team_filter=":_sp_team",
        )

    # ── Cell-level aux filter (post-GROUP BY) ────────────────────────
    league_cells = [
        c for c in league_cells_all
        if _cell_label_for_aux(c["toss_outcome"], c["inning"], c["result"], aux)
    ]
    team_cells = [
        c for c in team_cells_all
        if _cell_label_for_aux(c["toss_outcome"], c["inning"], c["result"], aux)
    ]

    # Denominators for shares + scope_total_n use the FILTERED slice so
    # the response is self-consistent with what the user asked to see:
    # "of the matches I've filtered to, here's the breakdown".
    league_filtered_total = sum(c["n"] for c in league_cells)
    team_filtered_total = sum(c["n"] for c in team_cells)

    # Marginals computed over the FILTERED cell set, using the
    # filtered total as denominator so all shares sum to 1.0.
    league_marginals = _marginals(league_cells, league_filtered_total)
    team_marginals = _marginals(team_cells, team_filtered_total) if team else {}

    # ── Compute per-cell shares + Wilson CIs ─────────────────────────
    from ..wilson import wilson_ci
    out_cells: list[dict] = []
    if team:
        # Team-detail: each cell carries team-side share + league baseline + delta.
        league_n_by_key = {
            (c["toss_outcome"], c["inning"], c["result"]): c["n"]
            for c in league_cells_all
        }
        for c in team_cells:
            key = (c["toss_outcome"], c["inning"], c["result"])
            league_n_for_cell = league_n_by_key.get(key, 0)
            share = round(c["n"] / team_filtered_total, 4) if team_filtered_total else None
            league_share = round(league_n_for_cell / league_filtered_total, 4) if league_filtered_total else None
            delta = (share - league_share) if (share is not None and league_share is not None) else None
            delta_pct = (
                round((share - league_share) / league_share * 100, 1)
                if (share is not None and league_share not in (None, 0))
                else None
            )
            lo, hi = wilson_ci(c["n"], team_filtered_total)
            out_cells.append({
                "toss_outcome": c["toss_outcome"],
                "inning": c["inning"],
                "result": c["result"],
                "n": c["n"],
                "share": share,
                "wilson_lo": round(lo, 4) if lo is not None else None,
                "wilson_hi": round(hi, 4) if hi is not None else None,
                "league_share": league_share,
                "delta": round(delta, 4) if delta is not None else None,
                "delta_pct": delta_pct,
            })
    else:
        for c in league_cells:
            lo, hi = wilson_ci(c["n"], league_filtered_total)
            out_cells.append({
                "toss_outcome": c["toss_outcome"],
                "inning": c["inning"],
                "result": c["result"],
                "n": c["n"],
                "share": round(c["n"] / league_filtered_total, 4) if league_filtered_total else None,
                "wilson_lo": round(lo, 4) if lo is not None else None,
                "wilson_hi": round(hi, 4) if hi is not None else None,
            })

    # ── Marginals with deltas (team-detail mode) ─────────────────────
    if team:
        marginals_out: dict = {}
        for axis in ("toss_outcome", "inning", "result"):
            marginals_out[axis] = {}
            for key, t_entry in team_marginals[axis].items():
                l_entry = league_marginals[axis].get(key, {})
                t_share = t_entry.get("share")
                l_share = l_entry.get("share")
                d = (t_share - l_share) if (t_share is not None and l_share is not None) else None
                dp = (
                    round((t_share - l_share) / l_share * 100, 1)
                    if (t_share is not None and l_share not in (None, 0))
                    else None
                )
                marginals_out[axis][key] = {
                    **t_entry,
                    "league_share": l_share,
                    "delta": round(d, 4) if d is not None else None,
                    "delta_pct": dp,
                }
    else:
        marginals_out = league_marginals

    return {
        "subject": {"team": team} if team else None,
        "scope_total_n": team_filtered_total if team else league_filtered_total,
        "league_total_n": league_filtered_total if team else None,
        "cells": out_cells,
        "marginals": marginals_out,
    }


@router.get("/{team}/summary")
async def team_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
            SUM(CASE WHEN m.toss_winner = :team THEN 1 ELSE 0 END) as toss_wins,
            SUM(CASE WHEN m.outcome_winner = :team AND m.toss_decision = 'bat'
                     AND m.toss_winner = :team THEN 1
                     WHEN m.outcome_winner = :team AND m.toss_decision = 'field'
                     AND m.toss_winner != :team THEN 1
                     ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN m.outcome_winner = :team AND m.toss_decision = 'field'
                     AND m.toss_winner = :team THEN 1
                     WHEN m.outcome_winner = :team AND m.toss_decision = 'bat'
                     AND m.toss_winner != :team THEN 1
                     ELSE 0 END) as field_first_wins
        FROM match m
        WHERE {filt}
        """,
        params,
    )
    row = rows[0] if rows else {}
    matches = row.get("matches", 0) or 0
    wins = row.get("wins", 0) or 0
    win_pct = round(wins * 100 / matches, 1) if matches > 0 else 0

    # Scope-avg counterpart: same query without the team filter. Used
    # to populate the per-metric envelope's `scope_avg` field. Wins
    # become "matches-with-a-winner" at scope level (every team's win
    # is some other team's loss; total wins == total losses == decided
    # matches). bat_first_wins / field_first_wins at scope level count
    # bat-first / field-first results across the field.
    scope_filt, scope_params = filters.build(has_innings_join=False, aux=aux)
    scope_filt = scope_filt or "1=1"
    scope_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END) as decided,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results,
            SUM(CASE WHEN m.toss_winner IS NOT NULL THEN 1 ELSE 0 END) as toss_decided,
            SUM(CASE WHEN m.toss_decision = 'bat'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'field'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as bat_first_wins,
            SUM(CASE WHEN m.toss_decision = 'field'
                     AND m.toss_winner = m.outcome_winner THEN 1
                     WHEN m.toss_decision = 'bat'
                     AND m.outcome_winner IS NOT NULL
                     AND m.toss_winner != m.outcome_winner THEN 1
                     ELSE 0 END) as field_first_wins
        FROM match m
        WHERE {scope_filt}
        """,
        scope_params,
    )
    sr = scope_rows[0] if scope_rows else {}
    # Pool totals from the scope query — keep as raw for downstream
    # per-team transform. Each scope_avg in the envelope must be a
    # PER-TEAM average so the displayed avg col + chip baseline align
    # with what a typical team actually has (not the pool total).
    # See internal_docs/spec-avg-col-per-team-transform.md.
    pool_matches    = sr.get("matches", 0) or 0
    pool_decided    = sr.get("decided", 0) or 0
    pool_ties       = sr.get("ties", 0) or 0
    pool_no_results = sr.get("no_results", 0) or 0
    pool_toss_dec   = sr.get("toss_decided", 0) or 0
    pool_bf         = sr.get("bat_first_wins", 0) or 0
    pool_ff         = sr.get("field_first_wins", 0) or 0

    unique_teams = await _unique_teams_in_scope(filters, aux)

    def _per_team_one(v):
        return round(v / unique_teams, 2) if unique_teams else None

    def _per_team_two(v):
        return round(v * 2 / unique_teams, 2) if unique_teams else None

    s_matches    = _per_team_two(pool_matches)
    s_decided    = _per_team_one(pool_decided)
    s_ties       = _per_team_two(pool_ties)
    s_no_results = _per_team_two(pool_no_results)
    s_toss_dec   = _per_team_one(pool_toss_dec)
    s_bf         = _per_team_one(pool_bf)
    s_ff         = _per_team_one(pool_ff)
    # True per-team avg win_pct = total decided wins / total team-
    # matches × 100. Replaces the prior bat_first_win_pct substitution
    # so chip values land in comparable per-team space.
    s_win_pct = (
        round(pool_decided * 100 / (pool_matches * 2), 2)
        if pool_matches > 0 else None
    )

    # Gender breakdown — only when no gender filter is active. Lets the
    # frontend warn the user when a team has matches in both men's and
    # women's cricket and they're seeing combined stats. Identical
    # filter scope to the main query, just grouped by gender.
    gender_breakdown = None
    if filters.gender is None:
        gb_rows = await db.q(
            f"""
            SELECT m.gender as gender, COUNT(*) as n
            FROM match m
            WHERE {filt}
            GROUP BY m.gender
            """,
            params,
        )
        gb = {r["gender"]: r["n"] for r in gb_rows if r["gender"]}
        male = gb.get("male", 0)
        female = gb.get("female", 0)
        # Only surface when BOTH sides have matches in the current
        # filter scope — otherwise there's nothing to disambiguate.
        if male > 0 and female > 0:
            gender_breakdown = {"male": male, "female": female}

    # Tier 2 — keepers used by this team (fielding innings where
    # keeper_assignment picked someone, grouped by that someone).
    # Match-level filters apply via params (already include :team).
    k_filt, k_params = filters.build(has_innings_join=True, aux=aux)
    k_params["team"] = team
    # The FIELDING team = NOT the batting team; team_filt ensures the
    # match involves this side, and i.team != :team means we're looking
    # at innings where the OTHER side was batting (i.e. our team fielding).
    k_parts = [
        "(m.team1 = :team OR m.team2 = :team)",
        "i.team != :team",
    ]
    if k_filt:
        k_parts.append(k_filt)
    # filters.build emits the inning clause but not result/toss_outcome
    # (those need :team binding). Add them explicitly per the same
    # pattern as _team_filter_clause. Spec: spec-splits-mosaic.md §1.2.
    res_clause, res_params = _result_match_filter(team, aux)
    if res_clause:
        k_parts.append(res_clause)
        k_params.update(res_params)
    toss_clause, toss_params = _toss_outcome_match_filter(team, aux)
    if toss_clause:
        k_parts.append(toss_clause)
        k_params.update(toss_params)
    k_clause = " AND ".join(k_parts)

    keepers_rows = await db.q(
        f"""
        SELECT ka.keeper_id, p.name, COUNT(*) as innings_kept
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN person p ON p.id = ka.keeper_id
        WHERE ka.keeper_id IS NOT NULL AND {k_clause}
        GROUP BY ka.keeper_id, p.name
        ORDER BY innings_kept DESC
        """,
        k_params,
    )
    keepers = [
        {"person_id": r["keeper_id"], "name": r["name"], "innings_kept": r["innings_kept"]}
        for r in keepers_rows
    ]

    ambig_rows = await db.q(
        f"""
        SELECT COUNT(*) as c
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE ka.keeper_id IS NULL AND {k_clause}
        """,
        k_params,
    )
    keeper_ambiguous = ambig_rows[0]["c"] if ambig_rows else 0

    # Distinct tournaments (canonical) the team has matches in within
    # the current scope. Drives the avg-col label promotion on the
    # Compare tab — when a club team's tournament universe collapses
    # to a singleton (RCB → IPL), the avg col can label as "IPL average"
    # instead of the generic "Men's club average".
    tour_rows = await db.q(
        f"""
        SELECT DISTINCT m.event_name
        FROM match m
        WHERE {filt} AND m.event_name IS NOT NULL
        """,
        params,
    )
    tournaments_in_scope = sorted({
        canon for canon in (canonicalize(r["event_name"]) for r in tour_rows)
        if canon
    })

    # Last match date — drives the dormancy badge on the Teams page
    # header (CLAUDE.md "Dormancy badge — page-header only"). Sourced
    # from the team's last appearance in scope, NOT one of the three
    # discipline distribution endpoints — the team's dormancy is a
    # team-level fact, independent of which discipline panel is
    # active. Wired via DormancyContext.setLastMatchDate from the
    # Teams.tsx page level (above tab-routing).
    date_rows = await db.q(
        f"""
        SELECT MAX(md.date) AS last_match_date
        FROM match m
        JOIN matchdate md ON md.match_id = m.id
        WHERE {filt}
        """,
        params,
    )
    last_match_date = date_rows[0]["last_match_date"] if date_rows else None

    # Per-team-averaged scope_avg values land in each envelope. Pool
    # totals (sr.*) are pre-divided into s_* above; team-side values
    # (matches, wins, …) stay as raw counts for THIS team.
    s_losses = s_decided  # every decided match has 1 loser, same per-team avg as wins
    return {
        "team": team,
        "matches":          wrap_metric(matches, s_matches, "matches", sample_size=s_matches),
        "wins":             wrap_metric(wins, s_decided, "wins", sample_size=matches),
        "losses":           wrap_metric(row.get("losses", 0) or 0, s_losses, "losses", sample_size=matches),
        "ties":             wrap_metric(row.get("ties", 0) or 0, s_ties, "ties", sample_size=matches),
        "no_results":       wrap_metric(row.get("no_results", 0) or 0, s_no_results, "no_results", sample_size=matches),
        "win_pct":          wrap_metric(win_pct, s_win_pct, "win_pct", sample_size=matches),
        "toss_wins":        wrap_metric(row.get("toss_wins", 0) or 0, s_toss_dec, "toss_wins", sample_size=matches),
        "bat_first_wins":   wrap_metric(row.get("bat_first_wins", 0) or 0, s_bf, "bat_first_wins", sample_size=matches),
        "field_first_wins": wrap_metric(row.get("field_first_wins", 0) or 0, s_ff, "field_first_wins", sample_size=matches),
        "unique_teams_in_scope": unique_teams,
        "gender_breakdown": gender_breakdown,
        "keepers": keepers,
        "keeper_ambiguous_innings": keeper_ambiguous,
        "tournaments_in_scope": tournaments_in_scope,
        "last_match_date": last_match_date,
    }


@router.get("/{team}/results")
async def team_results(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["team"] = team
    params["limit"] = limit
    params["offset"] = offset

    # total count
    count_rows = await db.q(
        f"SELECT COUNT(*) as total FROM match m WHERE {filt}", params
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = await db.q(
        f"""
        SELECT
            m.id as match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = m.id ORDER BY md.date LIMIT 1) as date,
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
            m.venue,
            m.city,
            m.event_name as tournament,
            m.toss_winner,
            m.toss_decision,
            CASE
                WHEN m.outcome_winner = :team THEN 'won'
                WHEN m.outcome_winner IS NOT NULL AND m.outcome_winner != :team THEN 'lost'
                WHEN m.outcome_result = 'tie' THEN 'tied'
                WHEN m.outcome_result = 'no result' THEN 'no result'
                ELSE 'no result'
            END as result,
            CASE
                WHEN m.outcome_by_runs IS NOT NULL THEN CAST(m.outcome_by_runs AS TEXT) || ' runs'
                WHEN m.outcome_by_wickets IS NOT NULL THEN CAST(m.outcome_by_wickets AS TEXT) || ' wickets'
                ELSE NULL
            END as margin,
            m.player_of_match
        FROM match m
        WHERE {filt}
        ORDER BY date DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    return {"results": rows, "total": total}


@router.get("/{team}/vs/{opponent}")
async def team_vs_opponent(
    team: str,
    opponent: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    # Use _team_filter_clause so aux narrowings (inning / result /
    # toss_outcome) flow through — previous direct `filters.build`
    # call skipped the result + toss_outcome match-level filters and
    # the vs-opponent counts ignored those aux params. Spec:
    # internal_docs/spec-splits-mosaic.md §1.2.
    team_filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["opponent"] = opponent
    params["team"] = team

    match_clause = (
        f"{team_filt} AND (m.team1 = :opponent OR m.team2 = :opponent)"
    )

    # Overall record
    overall_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner = :opponent THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {match_clause}
        """,
        params,
    )
    overall = overall_rows[0] if overall_rows else {}

    # By season
    by_season = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner = :opponent THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {match_clause}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    # Match list
    matches = await db.q(
        f"""
        SELECT
            m.id as match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = m.id ORDER BY md.date LIMIT 1) as date,
            m.venue,
            m.event_name as tournament,
            CASE
                WHEN m.outcome_winner = :team THEN 'won'
                WHEN m.outcome_winner = :opponent THEN 'lost'
                WHEN m.outcome_result = 'tie' THEN 'tied'
                ELSE 'no result'
            END as result,
            CASE
                WHEN m.outcome_by_runs IS NOT NULL THEN CAST(m.outcome_by_runs AS TEXT) || ' runs'
                WHEN m.outcome_by_wickets IS NOT NULL THEN CAST(m.outcome_by_wickets AS TEXT) || ' wickets'
                ELSE NULL
            END as margin
        FROM match m
        WHERE {match_clause}
        ORDER BY date DESC
        """,
        params,
    )

    return {
        "team": team,
        "opponent": opponent,
        "overall": overall,
        "by_season": by_season,
        "matches": matches,
    }


@router.get("/{team}/opponents-matrix")
async def team_opponents_matrix(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    top_n: int = Query(20, ge=1, le=200),
):
    """Opponents × seasons win-matrix for the Teams > vs Opponent tab.

    Returns:
      - `opponents`: top-N opponents by total matches with W/L/T totals
        (the "who we play most" rollup for the stacked bar).
      - `seasons`: sorted list of seasons present in scope.
      - `cells`: one entry per (opponent, season) with matches/wins/
        losses/ties/win_pct — feeds the heatmap. Only cells for the
        top-N opponents are returned (noise suppression).
    """
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["team"] = team

    # Rollup — per opponent totals
    rollup = await db.q(
        f"""
        SELECT
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {filt}
        GROUP BY opponent
        ORDER BY matches DESC
        """,
        params,
    )
    top_opponents = [r["opponent"] for r in rollup[:top_n]]

    opponents = []
    for r in rollup[:top_n]:
        matches = r["matches"] or 0
        wins = r["wins"] or 0
        opponents.append({
            "name": r["opponent"],
            "matches": matches,
            "wins": wins,
            "losses": r["losses"] or 0,
            "ties": r["ties"] or 0,
            "no_results": r["no_results"] or 0,
            "win_pct": round(wins * 100 / matches, 1) if matches > 0 else None,
        })

    # Cells — one per (opponent, season) for top-N opponents
    cells = []
    seasons_set: set[str] = set()
    if top_opponents:
        opp_list = ",".join(f"'{o.replace(chr(39), chr(39)+chr(39))}'" for o in top_opponents)
        cell_rows = await db.q(
            f"""
            SELECT
                m.season,
                CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as opponent,
                COUNT(*) as matches,
                SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN m.outcome_winner IS NOT NULL
                         AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties
            FROM match m
            WHERE {filt}
              AND (CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END) IN ({opp_list})
            GROUP BY m.season, opponent
            ORDER BY m.season, opponent
            """,
            params,
        )
        for r in cell_rows:
            season = r["season"]
            seasons_set.add(season)
            matches = r["matches"] or 0
            wins = r["wins"] or 0
            cells.append({
                "season": season,
                "opponent": r["opponent"],
                "matches": matches,
                "wins": wins,
                "losses": r["losses"] or 0,
                "ties": r["ties"] or 0,
                "win_pct": round(wins * 100 / matches, 1) if matches > 0 else None,
            })

    return {
        "team": team,
        "seasons": sorted(seasons_set),
        "opponents": opponents,
        "cells": cells,
    }


@router.get("/{team}/opponents")
async def team_opponents(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Return opponents the team has actually played (non-zero matches), respecting filters."""
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            CASE WHEN m.team1 = :team THEN m.team2 ELSE m.team1 END as name,
            COUNT(*) as matches
        FROM match m
        WHERE {filt}
        GROUP BY name
        ORDER BY matches DESC, name
        """,
        params,
    )
    return {"opponents": rows}


@router.get("/{team}/by-season")
async def team_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux, team_value=team)
    params["team"] = team

    rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(*) as matches,
            SUM(CASE WHEN m.outcome_winner = :team THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.outcome_winner IS NOT NULL
                     AND m.outcome_winner != :team THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) as ties,
            SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) as no_results
        FROM match m
        WHERE {filt}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    seasons = []
    for r in rows:
        matches = r["matches"] or 0
        wins = r["wins"] or 0
        win_pct = round(wins * 100 / matches, 1) if matches > 0 else 0
        seasons.append({**r, "win_pct": win_pct})

    return {"seasons": seasons}


@router.get("/{team}/players-by-season")
async def team_players_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Distinct players per season who appeared in the team's XI,
    with that season's batting average and bowling strike rate, and
    roster turnover (new / departed) vs the previous listed season.

    Batting stats are scoped to innings where :team was batting;
    bowling stats to innings where :team was in the field. Filters
    (gender, team_type, tournament, season range) apply to all four
    ball-level queries so numbers line up with the /batting and
    /bowling pages when clicked through.

    Full name resolution: cricsheet's person.name is abbreviated
    ("V Kohli"). personname holds variants (e.g. "Virat Kohli"). We
    pick the longest personname entry strictly longer than
    person.name, else fall back to person.name.
    """
    db = get_db()

    # Roster: who was in the XI each season. Match-level filter.
    roster_filt, roster_params = _team_filter_clause(filters, aux=aux, team_value=team)
    roster_params["team"] = team

    roster_rows = await db.q(
        f"""
        SELECT DISTINCT
            m.season AS season,
            p.id AS person_id,
            p.name AS short_name,
            (
                SELECT pn.name FROM personname pn
                WHERE pn.person_id = p.id
                  AND LENGTH(pn.name) > LENGTH(p.name)
                ORDER BY LENGTH(pn.name) DESC
                LIMIT 1
            ) AS full_name
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        JOIN person p ON p.id = mp.person_id
        WHERE mp.team = :team
          AND mp.person_id IS NOT NULL
          AND {roster_filt}
        """,
        roster_params,
    )

    # Batting / bowling stats reuse _team_innings_clause so the same
    # filter scope as the team batting/bowling tabs applies.
    bat_where, bat_params = _team_innings_clause(filters, team, side="batting", aux=aux)
    bowl_where, bowl_params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    bat_runs_rows = await db.q(
        f"""
        SELECT m.season AS season, d.batter_id AS person_id,
               SUM(d.runs_batter) AS runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {bat_where} AND d.batter_id IS NOT NULL
        GROUP BY m.season, d.batter_id
        """,
        bat_params,
    )
    bat_dism_rows = await db.q(
        f"""
        SELECT m.season AS season, w.player_out_id AS person_id,
               COUNT(*) AS dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {bat_where}
          AND w.player_out_id IS NOT NULL
          AND w.kind NOT IN ('retired hurt', 'retired out')
        GROUP BY m.season, w.player_out_id
        """,
        bat_params,
    )
    bowl_balls_rows = await db.q(
        f"""
        SELECT m.season AS season, d.bowler_id AS person_id,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                        THEN 1 ELSE 0 END) AS legal_balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {bowl_where} AND d.bowler_id IS NOT NULL
        GROUP BY m.season, d.bowler_id
        """,
        bowl_params,
    )
    bowl_wkts_rows = await db.q(
        f"""
        SELECT m.season AS season, d.bowler_id AS person_id,
               COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {bowl_where}
          AND d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        GROUP BY m.season, d.bowler_id
        """,
        bowl_params,
    )

    bat_runs = {(r["season"], r["person_id"]): r["runs"] or 0 for r in bat_runs_rows}
    bat_dism = {(r["season"], r["person_id"]): r["dismissals"] or 0 for r in bat_dism_rows}
    bowl_balls = {(r["season"], r["person_id"]): r["legal_balls"] or 0 for r in bowl_balls_rows}
    bowl_wkts = {(r["season"], r["person_id"]): r["wickets"] or 0 for r in bowl_wkts_rows}

    by_season: dict[str, list[dict]] = {}
    for r in roster_rows:
        season = r["season"]
        if not season:
            continue
        pid = r["person_id"]
        key = (season, pid)
        runs = bat_runs.get(key, 0)
        dism = bat_dism.get(key, 0)
        balls = bowl_balls.get(key, 0)
        wkts = bowl_wkts.get(key, 0)
        display = r["full_name"] or r["short_name"]
        by_season.setdefault(season, []).append({
            "person_id": pid,
            "name": display,
            "bat_avg": round(runs / dism, 2) if dism > 0 else None,
            "bowl_sr": round(balls / wkts, 2) if wkts > 0 else None,
        })

    # Descending by season (latest first). Turnover is vs the season
    # immediately after in the returned list (i.e. the previous season
    # chronologically) so the response is self-contained.
    ordered_seasons = sorted(by_season.keys(), reverse=True)
    season_sets = {s: {p["person_id"] for p in by_season[s]} for s in ordered_seasons}

    seasons = []
    for idx, season in enumerate(ordered_seasons):
        players = sorted(by_season[season], key=lambda p: p["name"].lower())
        prev_season = ordered_seasons[idx + 1] if idx + 1 < len(ordered_seasons) else None
        turnover = None
        if prev_season is not None:
            cur = season_sets[season]
            prev = season_sets[prev_season]
            turnover = {
                "prev_season": prev_season,
                "new_count": len(cur - prev),
                "left_count": len(prev - cur),
            }
        seasons.append({
            "season": season,
            "players": players,
            "turnover": turnover,
        })

    return {"seasons": seasons}


# ============================================================
# Team ball-level stats — batting, bowling, fielding, partnerships.
# See internal_docs/spec-team-stats.md.
# ============================================================


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


def _half(v: float | int | None) -> float | None:
    """Halve a per-match league rate to per-team-equivalent. Each
    match has 2 fielding/bowling sides, so league total catches /
    matches counts both sides; the team-side comparable is half.

    DEPRECATED for use in `_compute_xxx_summary` chip wrappers — as of
    spec-avg-column-per-innings.md Commit 2, the team-side
    `_xxx_aggregates(team=None, …)` helper halves per-match rates at
    source so the chip's `scope_avg` matches the avg endpoint's
    displayed value. Wrapping `_half(s["..._per_match"])` would
    double-halve. Still exported for the standalone helper."""
    if v is None:
        return None
    return round(v / 2, 2)


# ── Per-innings transform helpers ─────────────────────────────────
# spec-avg-column-per-innings.md (2026-04-26): the avg column on the
# Compare tab + every chip's `scope_avg` must express a per-INNINGS
# average, not a pool aggregate. Pool sums across both fielding/bowling
# sides per match are misleading next to a per-team value.
# These helpers divide absolute counts by an innings_count, halve
# per-match rates that aggregate both sides per match, and (for
# bowling) recompute `overs` from the new per-innings `legal_balls`.

# Keys touched by the per-innings transform per discipline.
BATTING_COUNT_KEYS = (
    "total_runs", "legal_balls", "fours", "sixes", "fifties", "hundreds",
)
BOWLING_COUNT_KEYS = (
    "runs_conceded", "legal_balls", "wickets",
    "fours_conceded", "sixes_conceded", "boundaries_conceded", "wides", "noballs",
)
BOWLING_HALF_KEYS = ("wides_per_match", "noballs_per_match")
FIELDING_COUNT_KEYS = (
    "catches", "caught_and_bowled", "stumpings", "run_outs",
    "total_dismissals_contributed",
)
FIELDING_HALF_KEYS = ("catches_per_match", "stumpings_per_match", "run_outs_per_match")
PARTNERSHIPS_COUNT_KEYS = ("total", "count_50_plus", "count_100_plus")


def _apply_batting_per_innings(d: dict, innings_batted: int, *, drop_divisor: bool = False) -> dict:
    """Divide batting absolute counts by innings_batted. Rates
    (run_rate, boundary_pct, dot_pct, avg_*_innings_total) and
    identity (highest_total, lowest_all_out_total) untouched.

    `drop_divisor`: pop innings_batted from the result. Set True for
    the avg endpoint (spec recommendation); False for the team-side
    league call where `_compute_batting_summary` reads s["innings_batted"]
    when constructing the envelope."""
    if not innings_batted:
        return d
    for k in BATTING_COUNT_KEYS:
        v = d.get(k)
        if v is not None:
            d[k] = round(v / innings_batted, 2)
    if drop_divisor:
        d.pop("innings_batted", None)
    return d


def _apply_bowling_per_innings(d: dict, innings_bowled: int, *, drop_divisor: bool = False) -> dict:
    """Divide bowling absolute counts by innings_bowled, halve
    per-match rates (wides_per_match, noballs_per_match), recompute
    `overs` from the new per-innings legal_balls."""
    if innings_bowled:
        for k in BOWLING_COUNT_KEYS:
            v = d.get(k)
            if v is not None:
                d[k] = round(v / innings_bowled, 2)
        if d.get("legal_balls") is not None:
            d["overs"] = round(d["legal_balls"] / 6, 2)
    for k in BOWLING_HALF_KEYS:
        v = d.get(k)
        if v is not None:
            d[k] = round(v / 2, 2)
    if drop_divisor:
        d.pop("innings_bowled", None)
    return d


def _apply_fielding_per_innings(
    d: dict,
    fielding_innings: int,
    *,
    halve_per_match: bool = True,
) -> dict:
    """Divide fielding counts by fielding_innings, halve per-match rates.

    `fielding_innings` is the divisor for pool counts; pass
    `matches × 2` for the all-innings case (every match has 2 fielding
    innings) and `matches × 1` under inning narrowing (the inning
    clause restricts each match to 1 fielding innings in scope).
    `halve_per_match` controls whether the existing *_per_match rates
    are further divided by 2 — pass False under inning narrowing for
    the same reason. Spec: spec-inning-split.md §5.5.
    """
    if fielding_innings:
        for k in FIELDING_COUNT_KEYS:
            v = d.get(k)
            if v is not None:
                d[k] = round(v / fielding_innings, 2)
    if halve_per_match:
        for k in FIELDING_HALF_KEYS:
            v = d.get(k)
            if v is not None:
                d[k] = round(v / 2, 2)
    return d


def _apply_partnerships_per_innings(d: dict, innings_batted: int) -> dict:
    """Divide partnership counts by innings_batted. avg_runs is a
    per-partnership rate (untouched); highest is identity."""
    if not innings_batted:
        return d
    for k in PARTNERSHIPS_COUNT_KEYS:
        v = d.get(k)
        if v is not None:
            d[k] = round(v / innings_batted, 2)
    return d


# ── Per-team transform for RESULTS metrics ──────────────────────────
#
# Sibling of the per-INNINGS transform above. The team summary +
# /scope/averages/summary endpoints return team-level results stats
# (matches, wins, toss_wins, …). The displayed "average" column on
# Compare must show what the typical team's value is — not the pool
# total. Each match contributes 2 team-instances (each side plays it),
# so per-team averages are `pool * mult / unique_teams_in_scope`.
# Multiplier is 2 for metrics where each match generates 2 instances
# (matches, ties, no_results — both sides share the outcome) and 1
# for metrics where each match generates 1 instance (wins / losses /
# toss_wins / bat_first_wins / field_first_wins — one team gets
# attribution per match).
#
# `win_pct` for the league averaged across teams = total wins / total
# team-matches × 100 = decided / (matches × 2) × 100. Algebraically:
# every decided match contributes 1 win + 1 loss → 1 to the wins
# numerator, 2 to the denominator across both sides. Coincidentally
# close to bat_first_win_pct on small scopes but a distinct metric.

RESULTS_COUNT_KEYS_TWO_INSTANCES = ("matches", "ties", "no_results")
RESULTS_COUNT_KEYS_ONE_INSTANCE = (
    "decided", "toss_decided", "bat_first_wins", "field_first_wins",
)


def _apply_results_per_team(d: dict, unique_teams: int) -> dict:
    """Convert pool-level RESULTS counts to per-team averages.

    Adds `win_pct` (true per-team avg, not bat-first share) and
    `unique_teams_in_scope` (diagnostic). Leaves `bat_first_win_pct`
    untouched (it's already a percentage, no per-team transform
    applies — every match has one bat-first or field-first outcome,
    not per-team).
    """
    matches_pool = d.get("matches") or 0
    decided_pool = d.get("decided") or 0
    if not unique_teams:
        d["win_pct"] = None
        d["unique_teams_in_scope"] = 0
        return d
    out = dict(d)
    for k in RESULTS_COUNT_KEYS_TWO_INSTANCES:
        v = out.get(k)
        if v is not None:
            out[k] = round(v * 2 / unique_teams, 2)
    for k in RESULTS_COUNT_KEYS_ONE_INSTANCE:
        v = out.get(k)
        if v is not None:
            out[k] = round(v / unique_teams, 2)
    # True per-team avg win_pct uses POOL totals (decided_pool /
    # (matches_pool × 2)), not the divided values above.
    out["win_pct"] = (
        round(decided_pool * 100 / (matches_pool * 2), 2)
        if matches_pool > 0 else None
    )
    out["unique_teams_in_scope"] = unique_teams
    return out


async def _unique_teams_in_scope(filters: FilterParams, aux: AuxParams) -> int:
    """Distinct number of teams (m.team1 ∪ m.team2) within the current
    scope. Drops any filter_team narrowing the caller may have set so
    the count reflects the full pool of teams the avg col baselines
    against.
    """
    db = get_db()
    saved_team = filters.team
    filters.team = None
    try:
        where, params = filters.build(has_innings_join=False, aux=aux)
    finally:
        filters.team = saved_team
    st_clause, st_params = _scope_to_team_clause(aux, filters)
    if st_clause:
        where = f"{where} AND {st_clause}" if where else st_clause
        params.update(st_params)
    where = where or "1=1"
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT t) AS n FROM (
            SELECT m.team1 AS t FROM match m WHERE {where}
            UNION
            SELECT m.team2 FROM match m WHERE {where}
        )
        """,
        params,
    )
    return (rows[0].get("n") if rows else 0) or 0


def _league_aux(
    team: str | None, aux: AuxParams, filters: FilterParams | None = None,
) -> tuple[FilterParams | None, AuxParams]:
    """Return `(league_filters, league_aux)` for the league-side call
    inside `_compute_xxx_summary` / by-phase / by-wicket handlers so
    the chip envelope's `scope_avg` baselines against the same scope
    the Compare-tab avg column displays.

    Three synthesis paths, in priority order:

    0. **`chip_baseline_scope_json`** (preferred, post-2026-04-29) —
       full base64-JSON serialization of the peer avg slot's scope
       sent by the frontend `chipAlignmentFor`. When set, fully
       overrides the team-side filters for the league baseline call.
       Generalises Steps 1 + 2 below: handles narrowing AND broadening
       overrides on every overridable axis (tournament / season /
       venue / series_type / team_class). Spec:
       spec-slot-override-chip-alignment.md §4.2.

    1. **`scope_to_team`** (legacy fallback, lands on aux) — auto-
       narrow the league pool to the team's tournament universe.
       GATED on `filters.team_type == 'club'` (closed-league
       semantic). For internationals a single team's universe
       contains that team in every match, so narrowing collapses into
       a self-mirror; the frontend defaults to the full pool there,
       so the chip baseline must agree (no synthesis). Skipped when
       aux already carries `scope_to_team` explicitly.

    2. **`chip_team_class` → `team_class` on filters** (legacy
       fallback) — the v3 narrow-direction shortcut. Copy onto the
       LEAGUE-SIDE filters' `team_class`. Kept for back-compat with
       clients that haven't switched to `chip_baseline_scope_json`.

    No-op when `team is None`.

    Spec: spec-slot-override-chip-alignment.md §5.2 +
    spec-avg-column-per-innings.md Commit 3 + the 2026-04-27
    international avg-baseline correction.
    """
    from copy import copy
    if team is None:
        return filters, aux

    # Path 0 — full-scope override. Bypass the legacy synthesis paths
    # entirely so the league-side aggregation uses the avg slot's exact
    # effective scope. Falls through on parse error.
    if aux.chip_baseline_scope_json:
        decoded = _decode_chip_baseline(aux.chip_baseline_scope_json)
        if decoded is not None:
            return decoded

    new_aux = aux
    new_filters = filters
    # Path 1: scope_to_team narrow (clubs only, only when not already set,
    # and only when the request hasn't explicitly declared a club-tier
    # pool via team_class). The tier override is the user's explicit
    # pool dimension — auto-narrowing to the team's tournament
    # universe on top would intersect both clauses (IPL ∩ primary
    # = IPL again for a CSK avg slot), silently swallowing the tier
    # broadening the user asked for.
    explicit_club_tier = filters is not None and filters.team_class in (
        "primary_club", "secondary_club",
    )
    if (
        not aux.scope_to_team
        and (filters is None or filters.team_type == "club")
        and not explicit_club_tier
    ):
        new_aux = copy(aux)
        new_aux.scope_to_team = team
    # Path 2: chip_team_class → team_class on filters (any team_type).
    if aux.chip_team_class and filters is not None:
        new_filters = copy(filters)
        new_filters.team_class = aux.chip_team_class
    return new_filters, new_aux


def _phase_dict_per_innings(by_phase: dict, innings_count: int) -> dict:
    """Apply per-innings to a {phase: row} dict. Used by team-side
    `_batting_by_phase_aggregates(team=None, …)` /
    `_bowling_by_phase_aggregates(team=None, …)`. Mutates and returns."""
    if not innings_count:
        return by_phase
    keys = ("runs", "runs_conceded", "balls", "wickets_lost", "wickets",
            "fours", "sixes", "fours_conceded", "sixes_conceded")
    for r in by_phase.values():
        for k in keys:
            v = r.get(k)
            if v is not None:
                r[k] = round(v / innings_count, 2)
    return by_phase


async def _innings_count_for_phase(filters, aux, *, side: str) -> int:
    """Quick count of distinct innings in scope (no team), batting or
    bowling side. Used by the team-side phase aggregator's team=None
    branch to compute the per-innings divisor."""
    db = get_db()
    where, params = _team_innings_clause(filters, None, side=side, aux=aux)
    rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS n
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    return (rows[0].get("n") if rows else 0) or 0


async def _innings_count_per_inning(filters, aux, *, side: str) -> dict[int, int]:
    """Innings-count GROUPED BY i.innings_number, for one side.

    Used by the league-side branch of `_*_by_inning_aggregates` to
    compute the per-innings divisor when transforming pool counts to
    per-innings rates. Each row of the /by-inning response divides by
    the count of innings of THAT innings_number in scope (typically
    matches × 1, since each match contributes one innings_0 and one
    innings_1 to the league pool).
    """
    db = get_db()
    where, params = _team_innings_clause(filters, None, side=side, aux=aux)
    rows = await db.q(
        f"""
        SELECT i.innings_number AS inning, COUNT(DISTINCT i.id) AS n
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.innings_number
        """,
        params,
    )
    return {r["inning"]: (r["n"] or 0) for r in rows if r["inning"] in (0, 1)}


def _inning_dict_per_innings(by_inning: dict, counts_per_inning: dict) -> dict:
    """Apply per-innings transform to a {inning: row} dict — divides
    pool counts by the per-inning innings_count. Mirrors
    `_phase_dict_per_innings` shape but per-row divisor instead of a
    single shared divisor (counts vary across innings for abandoned
    matches and slot inning narrowing)."""
    keys = ("runs", "runs_conceded", "balls", "wickets_lost", "wickets",
            "fours", "sixes", "fours_conceded", "sixes_conceded")
    for inn_no, r in by_inning.items():
        div = counts_per_inning.get(inn_no, 0)
        if not div:
            continue
        for k in keys:
            v = r.get(k)
            if v is not None:
                r[k] = round(v / div, 2)
    return by_inning


def _scope_to_team_clause(
    aux: AuxParams | None, filters: FilterParams,
) -> tuple[str, dict]:
    """Subquery clause narrowing m.event_name to the primary team's
    tournament universe. Applied only when:
      - aux.scope_to_team is set (avg-slot fetch), AND
      - the request hasn't explicitly narrowed by tournament.

    Returns ("", {}) if the gate doesn't apply. Caller decides where
    to splice the clause + extend its params dict.

    `COALESCE(event_name, '')` on both sides matches the bucket_baseline
    convention (Convention 4 in perf-bucket-baselines.md): NULL
    event_name (bilaterals) is stored as '' in the precomputed tables.
    Without COALESCE, `IN (NULL)` evaluates to UNKNOWN and excludes
    bilaterals from the scope — diverging from the baseline path's
    narrowing.
    """
    if aux is None or not aux.scope_to_team or _is_set(filters.tournament):
        return "", {}
    return (
        "COALESCE(m.event_name, '') IN ("
        "SELECT DISTINCT COALESCE(m_st.event_name, '') FROM matchplayer mp_st "
        "JOIN match m_st ON mp_st.match_id = m_st.id "
        "WHERE mp_st.team = :scope_to_team)",
        {"scope_to_team": aux.scope_to_team},
    )


def _team_innings_clause(
    filters: FilterParams, team: str | None, side: str = "batting",
    aux: AuxParams | None = None,
) -> tuple[str, dict]:
    """Build WHERE clause for team-scoped innings queries.

    side='batting' → innings where :team batted (i.team = :team)
    side='fielding' → innings where :team was in the field (i.team != :team
                      AND :team is one of the match teams)

    When `team` is None, the team-specific clauses are dropped entirely
    and the result is a pure scope filter — used by `/scope/averages/*`
    endpoints. The same SQL surface stays in one place; both code paths
    agree on filter injection.

    The path :team takes precedence over any filter_team query param.
    """
    # Null out filter_team so our :team bind isn't clobbered. Each request
    # gets a fresh FilterParams via Depends() so this mutation is safe.
    filters.team = None
    where, params = filters.build(has_innings_join=True, aux=aux)
    parts: list[str] = []
    if team is not None:
        params["team"] = team
        if side == "batting":
            parts.append("i.team = :team")
        else:
            parts.extend(["i.team != :team", "(m.team1 = :team OR m.team2 = :team)"])
    if where:
        parts.append(where)
    # Match-level aux filters (result / toss_outcome) need a path team
    # to evaluate. They only apply on team-detail (team is not None);
    # on the scope-averages path (team is None) they're silently
    # ignored — the league baseline can't meaningfully filter on
    # outcome-vs-self when there's no self.
    if team is not None:
        res_clause, res_params = _result_match_filter(team, aux)
        if res_clause:
            parts.append(res_clause)
            params.update(res_params)
        toss_clause, toss_params = _toss_outcome_match_filter(team, aux)
        if toss_clause:
            parts.append(toss_clause)
            params.update(toss_params)
    # Auto-scope: only meaningful for the scope-averages path (team is None).
    if team is None:
        st_clause, st_params = _scope_to_team_clause(aux, filters)
        if st_clause:
            parts.append(st_clause)
            params.update(st_params)
    if not parts:
        # filters.build() returns "" when no filters are active; the
        # scope-avg "no filter, no team" code path needs a tautology
        # so the WHERE clause builds.
        parts.append("1=1")
    return " AND ".join(parts), params


async def _batting_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Flat-shape batting aggregates (no envelope). Called twice by
    `_compute_batting_summary`: once with team, once with team=None
    (to compute scope_avg). Identity-bearing fields (`highest_total`,
    `lowest_all_out_total`) are only consumed by the team side."""
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        return await _batting_aggregates_baseline(team, filters, aux)
    return await _batting_aggregates_live(team, filters, aux)


async def _batting_aggregates_baseline(team, filters, aux):
    from .bucket_baseline_dispatch import baseline_where, LEAGUE_TEAM_KEY
    db = get_db()
    table_team = team if team else LEAGUE_TEAM_KEY
    where, params = baseline_where(filters, aux, team=table_team)
    rows = await db.q(
        f"""
        SELECT
          SUM(innings_batted) AS innings_batted,
          SUM(total_runs) AS total_runs,
          SUM(legal_balls) AS legal_balls,
          SUM(fours) AS fours, SUM(sixes) AS sixes, SUM(dots) AS dots,
          SUM(fifties) AS fifties, SUM(hundreds) AS hundreds,
          SUM(first_inn_runs_sum) AS first_inn_runs_sum,
          SUM(first_inn_count) AS first_inn_count,
          SUM(second_inn_runs_sum) AS second_inn_runs_sum,
          SUM(second_inn_count) AS second_inn_count
        FROM bucketbaselinebatting {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    total_runs = r.get("total_runs") or 0
    legal_balls = r.get("legal_balls") or 0
    fours = r.get("fours") or 0
    sixes = r.get("sixes") or 0
    dots = r.get("dots") or 0
    boundaries = fours + sixes
    fic = r.get("first_inn_count") or 0
    sic = r.get("second_inn_count") or 0
    avg_1st = round((r.get("first_inn_runs_sum") or 0) / fic, 1) if fic else None
    avg_2nd = round((r.get("second_inn_runs_sum") or 0) / sic, 1) if sic else None

    # Highest single innings — pick row with max highest_inn_runs.
    hi_rows = await db.q(
        f"""
        SELECT highest_inn_runs, highest_inn_match_id, highest_inn_innings_number
        FROM bucketbaselinebatting {where} AND highest_inn_runs > 0
        ORDER BY highest_inn_runs DESC, highest_inn_match_id LIMIT 1
        """,
        params,
    )
    highest_total = None
    if hi_rows:
        h = hi_rows[0]
        highest_total = {
            "runs": h["highest_inn_runs"] or 0,
            "match_id": h["highest_inn_match_id"],
            "innings_number": (h["highest_inn_innings_number"] or 0) + 1,
        }
    # Lowest all-out total.
    lo_rows = await db.q(
        f"""
        SELECT lowest_all_out_runs, lowest_all_out_match_id, lowest_all_out_innings_number
        FROM bucketbaselinebatting {where} AND lowest_all_out_runs IS NOT NULL
        ORDER BY lowest_all_out_runs ASC, lowest_all_out_match_id LIMIT 1
        """,
        params,
    )
    lowest_all_out = None
    if lo_rows:
        lo = lo_rows[0]
        lowest_all_out = {
            "runs": lo["lowest_all_out_runs"] or 0,
            "match_id": lo["lowest_all_out_match_id"],
            "innings_number": (lo["lowest_all_out_innings_number"] or 0) + 1,
        }
    innings_batted = r.get("innings_batted") or 0
    # avg_innings_total = pool_runs / innings_count. Computed server-side
    # so the team-page StatCard's value AND scope_avg flow through the
    # same code path (audit §4.2). NOT touched by _apply_batting_per_innings
    # (rate, not a count) — already per-innings by construction.
    avg_innings_total = round(total_runs / innings_batted, 1) if innings_batted else None
    out = {
        "innings_batted": innings_batted,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "bat_dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "fifties": r.get("fifties") or 0,
        "hundreds": r.get("hundreds") or 0,
        "avg_innings_total": avg_innings_total,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
        "lowest_all_out_total": lowest_all_out,
    }
    # Spec-avg-column-per-innings.md Commit 2 part B: when called with
    # team=None for the chip's scope_avg, return per-innings averages so
    # chip_scope_avg numerically matches `/scope/averages/*`'s displayed
    # value. Team-given path stays pool (the team-side response is a
    # fact about THIS team's pool counts).
    if team is None:
        return _apply_batting_per_innings(out, out["innings_batted"])
    return out


async def _batting_aggregates_live(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict:
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    innings_batted = c.get("innings_batted") or 0
    total_runs = c.get("total_runs") or 0
    legal_balls = c.get("legal_balls") or 0
    fours = c.get("fours") or 0
    sixes = c.get("sixes") or 0
    dots = c.get("dots") or 0
    boundaries = fours + sixes

    # Per-innings totals (runs + balls + innings_number + whether all-out)
    innings_rows = await db.q(
        f"""
        SELECT
            i.id as innings_id, i.match_id, i.innings_number,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as balls,
            (SELECT COUNT(*) FROM wicket w2
             JOIN delivery d2 ON d2.id = w2.delivery_id
             WHERE d2.innings_id = i.id
               AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_lost
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number
        """,
        params,
    )

    avg_1st = None
    avg_2nd = None
    first_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 0 and r["runs"] is not None]
    second_totals = [r["runs"] for r in innings_rows if r["innings_number"] == 1 and r["runs"] is not None]
    if first_totals:
        avg_1st = round(sum(first_totals) / len(first_totals), 1)
    if second_totals:
        avg_2nd = round(sum(second_totals) / len(second_totals), 1)

    highest_total = None
    lowest_all_out = None
    if innings_rows:
        top = max(innings_rows, key=lambda r: r["runs"] or 0)
        highest_total = {
            "runs": top["runs"] or 0,
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }
        all_out = [r for r in innings_rows if (r["wickets_lost"] or 0) >= 10]
        if all_out:
            lo = min(all_out, key=lambda r: r["runs"] or 0)
            lowest_all_out = {
                "runs": lo["runs"] or 0,
                "match_id": lo["match_id"],
                "innings_number": lo["innings_number"] + 1,
            }

    # 50s / 100s count — aggregate from batter-level innings stats for
    # this team. Use delivery-level grouping so filter scope is respected.
    player_inn_rows = await db.q(
        f"""
        SELECT d.batter_id, i.id as innings_id,
               SUM(d.runs_batter) as r
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id, i.id
        """,
        params,
    )
    fifties = sum(1 for r in player_inn_rows if 50 <= (r["r"] or 0) < 100)
    hundreds = sum(1 for r in player_inn_rows if (r["r"] or 0) >= 100)

    # avg_innings_total = pool_runs / innings_count. Same shape as the
    # baseline path. Audit §4.2.
    avg_innings_total = round(total_runs / innings_batted, 1) if innings_batted else None
    out = {
        "innings_batted": innings_batted,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "bat_dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "fifties": fifties,
        "hundreds": hundreds,
        "avg_innings_total": avg_innings_total,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
        "lowest_all_out_total": lowest_all_out,
    }
    if team is None:
        return _apply_batting_per_innings(out, innings_batted)
    return out


async def _compute_batting_summary(
    team: str,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Per-metric envelope team-batting summary. Runs the flat-shape
    aggregator twice (team, then team=None for scope_avg) and wraps
    each numeric metric in the {value, scope_avg, delta_pct,
    direction, sample_size} envelope. Identity-bearing nested objects
    (highest_total, lowest_all_out_total) stay flat — they're not
    metrics."""
    t = await _batting_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _batting_aggregates(None, lf, la)
    legal = t.get("legal_balls") or 0
    return {
        "team": team,
        "innings_batted": wrap_metric(t["innings_batted"], s["innings_batted"], "innings_batted", sample_size=t["innings_batted"]),
        "total_runs": wrap_metric(t["total_runs"], s["total_runs"], "total_runs", sample_size=legal),
        "legal_balls": wrap_metric(t["legal_balls"], s["legal_balls"], "legal_balls", sample_size=legal),
        "run_rate": wrap_metric(t["run_rate"], s["run_rate"], "run_rate", sample_size=legal),
        "boundary_pct": wrap_metric(t["boundary_pct"], s["boundary_pct"], "boundary_pct", sample_size=legal),
        # Server-side field is "dot_pct"; metadata key is "bat_dot_pct"
        # to disambiguate from bowling dot_pct (opposite direction).
        "dot_pct": wrap_metric(t["bat_dot_pct"], s["bat_dot_pct"], "bat_dot_pct", sample_size=legal),
        "fours": wrap_metric(t["fours"], s["fours"], "fours", sample_size=legal),
        "sixes": wrap_metric(t["sixes"], s["sixes"], "sixes", sample_size=legal),
        "fifties": wrap_metric(t["fifties"], s["fifties"], "fifties", sample_size=t["innings_batted"]),
        "hundreds": wrap_metric(t["hundreds"], s["hundreds"], "hundreds", sample_size=t["innings_batted"]),
        # avg_innings_total — server-side per-innings runs avg (audit §4.2).
        # Replaces the synthetic envelope at Teams.tsx:651-674 that mixed
        # client-computed value with server scope_avg. Both sides now flow
        # through _batting_aggregates → _apply_batting_per_innings, so any
        # future change to per-innings normalisation applies symmetrically.
        "avg_innings_total": wrap_metric(t["avg_innings_total"], s["avg_innings_total"], "avg_innings_total", sample_size=t["innings_batted"]),
        "avg_1st_innings_total": wrap_metric(t["avg_1st_innings_total"], s["avg_1st_innings_total"], "avg_1st_innings_total", sample_size=t["innings_batted"]),
        "avg_2nd_innings_total": wrap_metric(t["avg_2nd_innings_total"], s["avg_2nd_innings_total"], "avg_2nd_innings_total", sample_size=t["innings_batted"]),
        "highest_total": t["highest_total"],
        "lowest_all_out_total": t["lowest_all_out_total"],
    }


@router.get("/{team}/batting/summary")
async def team_batting_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    return await _compute_batting_summary(team, filters, aux)


# ============================================================
# Team batting — distribution dossier (spec §16.2).
# Per-innings observation row + two sibling blocks (runs +
# run_rate) + phase rollup + four form windows. Reuses
# `_team_innings_clause` (side='batting') for filter scope.
# `FilterParams.filter_team` is IGNORED — the path-param
# dominates per spec §16.1.
# ============================================================


async def _innings_master_sample_team_batting(
    team: str, filters: FilterParams, aux: AuxParams,
) -> list[dict]:
    """Per-innings observation rows for the team's batting innings
    (`i.team = :team`), under the active filter scope. Spec §16.2.1.

    Wickets exclude `'retired hurt'` and `'retired not out'` —
    matches the existing team-batting/by-phase convention so
    wickets-fallen here is consistent with `wickets_lost` elsewhere
    in the team-batting endpoints.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)
    rows = await db.q(
        f"""
        SELECT
            i.id AS innings_id,
            i.match_id,
            i.innings_number,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) AS date,
            SUM(d.runs_total) AS runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls,
            SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wickets,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                     THEN d.runs_total ELSE 0 END) AS runs_at_10,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_at_10,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS legal_balls_first_10,
            -- Phase: powerplay (overs 1-6, over_number 0-5)
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     THEN d.runs_total ELSE 0 END) AS runs_pp,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_pp,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_pp,
            -- Phase: middle (overs 7-15, over_number 6-14)
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     THEN d.runs_total ELSE 0 END) AS runs_mid,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_mid,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_mid,
            -- Phase: death (overs 16-20, over_number 15-19)
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     THEN d.runs_total ELSE 0 END) AS runs_death,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_death,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_death
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.kind NOT IN ('retired hurt', 'retired not out')
        WHERE {where}
        GROUP BY i.id
        ORDER BY date ASC, i.innings_number ASC
        """,
        params,
    )
    out = []
    for r in rows:
        legal_first_10 = r["legal_balls_first_10"] or 0
        out.append({
            "innings_id": r["innings_id"],
            "match_id": r["match_id"],
            "innings_number": r["innings_number"],
            "date": r["date"],
            "runs": r["runs"] or 0,
            "balls": r["balls"] or 0,
            "wickets": r["wickets"] or 0,
            "runs_at_10": r["runs_at_10"] or 0,
            "wickets_at_10": r["wickets_at_10"] or 0,
            "reached_10_overs": 1 if legal_first_10 >= 60 else 0,
            "runs_pp": r["runs_pp"] or 0,
            "balls_pp": r["balls_pp"] or 0,
            "wickets_pp": r["wickets_pp"] or 0,
            "runs_mid": r["runs_mid"] or 0,
            "balls_mid": r["balls_mid"] or 0,
            "wickets_mid": r["wickets_mid"] or 0,
            "runs_death": r["runs_death"] or 0,
            "balls_death": r["balls_death"] or 0,
            "wickets_death": r["wickets_death"] or 0,
        })
    return out


def _runs_block_team_batting(observations: list[dict]) -> dict:
    """`runs` block — skewed continuous + simples + chain-ladder
    conditionals + over-aware doubling. Spec §16.2.2."""
    n = len(observations)
    runs = [o["runs"] for o in observations]

    if n == 0:
        keys = [
            "p_lt_100", "p_geq_100", "p_geq_150", "p_geq_200", "p_geq_230",
            "p_150_given_100", "p_200_given_150", "p_230_given_200",
            "p_double_at_10",
        ]
        return {
            "total": 0,
            "mean_per_innings": None,
            "median": None,
            "variance": None,
            "std": None,
            "escalation_ratio_median": None,
            "observations": [],
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(runs)
    mean = total / n
    median = statistics.median(runs)
    variance = statistics.variance(runs) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_lt(v: int) -> int:
        return sum(1 for r in runs if r < v)

    def _count_geq(v: int) -> int:
        return sum(1 for r in runs if r >= v)

    geq_100 = _count_geq(100)
    geq_150 = _count_geq(150)
    geq_200 = _count_geq(200)
    geq_230 = _count_geq(230)

    # Over-aware doubling — denom is innings with `reached_10_overs=1
    # AND runs_at_10 > 0` (avoids 0/0 when team is 0 at halfway).
    doubling_pool = [
        o for o in observations
        if o["reached_10_overs"] == 1 and o["runs_at_10"] > 0
    ]
    doubling_denom = len(doubling_pool)
    doubling_num = sum(
        1 for o in doubling_pool
        if o["runs"] >= 2 * o["runs_at_10"]
    )
    ratios = [o["runs"] / o["runs_at_10"] for o in doubling_pool]
    escalation_median = round(statistics.median(ratios), 4) if ratios else None

    return {
        "total": total,
        "mean_per_innings": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "escalation_ratio_median": escalation_median,
        "observations": observations,
        "milestones": {
            "p_lt_100":  prob_record(_count_lt(100), n),
            "p_geq_100": prob_record(geq_100, n),
            "p_geq_150": prob_record(geq_150, n),
            "p_geq_200": prob_record(geq_200, n),
            "p_geq_230": prob_record(geq_230, n),
            # Chain ladder — each rung's denom is the rung below.
            "p_150_given_100": prob_record(geq_150, geq_100),
            "p_200_given_150": prob_record(geq_200, geq_150),
            "p_230_given_200": prob_record(geq_230, geq_200),
            # Over-aware doubling.
            "p_double_at_10": prob_record(doubling_num, doubling_denom),
        },
    }


def _run_rate_block_team_batting(observations: list[dict]) -> dict:
    """`run_rate` block — continuous per-over rate distribution. Both
    `pool` (balls-weighted, the conventional career RR) and
    `mean_per_innings` (unweighted mean of per-innings RR) ship.
    Spec §16.2.2."""
    n = len(observations)

    if n == 0:
        keys = ["p_rr_leq_7", "p_rr_leq_8", "p_rr_geq_9", "p_rr_geq_10"]
        return {
            "pool": None,
            "mean_per_innings": None,
            "median_per_innings": None,
            "variance": None,
            "std": None,
            "per_innings": [],
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total_runs = sum(o["runs"] for o in observations)
    total_balls = sum(o["balls"] for o in observations)
    pool = (total_runs * 6.0 / total_balls) if total_balls > 0 else None

    per_innings = [round(o["runs"] * 6.0 / o["balls"], 4)
                   for o in observations if o["balls"] > 0]
    mean_pi = sum(per_innings) / len(per_innings) if per_innings else None
    median_pi = statistics.median(per_innings) if per_innings else None
    variance = statistics.variance(per_innings) if len(per_innings) >= 2 else 0.0
    std = variance ** 0.5

    def _count_leq(v: float) -> int:
        return sum(1 for e in per_innings if e <= v)

    def _count_geq(v: float) -> int:
        return sum(1 for e in per_innings if e >= v)

    return {
        "pool": round(pool, 4) if pool is not None else None,
        "mean_per_innings": round(mean_pi, 4) if mean_pi is not None else None,
        "median_per_innings": round(median_pi, 4) if median_pi is not None else None,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "per_innings": per_innings,
        "milestones": {
            "p_rr_leq_7":  prob_record(_count_leq(7.0), n),
            "p_rr_leq_8":  prob_record(_count_leq(8.0), n),
            "p_rr_geq_9":  prob_record(_count_geq(9.0), n),
            "p_rr_geq_10": prob_record(_count_geq(10.0), n),
        },
    }


def _phase_rollup_team_batting(observations: list[dict]) -> dict:
    """Per-phase rollup: runs + balls + wickets + innings_active.
    Spec §16.2.3."""
    out = {}
    keys = {
        "powerplay": ("runs_pp", "balls_pp", "wickets_pp"),
        "middle":    ("runs_mid", "balls_mid", "wickets_mid"),
        "death":     ("runs_death", "balls_death", "wickets_death"),
    }
    for name, (rk, bk, wk) in keys.items():
        out[name] = {
            "runs_total": sum(o[rk] for o in observations),
            "balls_total": sum(o[bk] for o in observations),
            "wickets_total": sum(o[wk] for o in observations),
            "innings_active": sum(1 for o in observations if o[bk] > 0),
        }
    return out


def _distribution_dossier_team_batting(observations: list[dict]) -> dict:
    """Pure aggregate. Two sibling blocks (`runs` + `run_rate`) +
    phase rollup. Same shape used for lifetime + form windows.
    Spec §16.2."""
    return {
        "n_innings": len(observations),
        "runs": _runs_block_team_batting(observations),
        "run_rate": _run_rate_block_team_batting(observations),
        "phase": _phase_rollup_team_batting(observations),
    }


def _form_windows_team_batting(
    observations: list[dict], today: date,
) -> dict:
    """Slice the date-asc observation list into four form windows,
    run the dossier on each, emit the team-batting delta block (8
    entries: 4 windows × 2 metrics — runs_mean + run_rate_pool).
    Calendar cutoffs scope-anchored per `form_windows.scope_anchor`.
    Spec §16.2.4."""
    anchor = scope_anchor(observations, today)
    last_10 = observations[-10:]
    cutoff_60d = (anchor - timedelta(days=60)).isoformat()
    cutoff_6mo = (anchor - timedelta(days=180)).isoformat()
    cutoff_1yr = (anchor - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    lifetime_doss = _distribution_dossier_team_batting(observations)
    last_10_doss = _distribution_dossier_team_batting(last_10)
    last_60d_doss = _distribution_dossier_team_batting(last_60d)
    last_6mo_doss = _distribution_dossier_team_batting(last_6mo)
    last_1yr_doss = _distribution_dossier_team_batting(last_1yr)

    def _delta_runs(w: dict) -> Optional[float]:
        wv = w["runs"]["mean_per_innings"]
        lv = lifetime_doss["runs"]["mean_per_innings"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    def _delta_rr(w: dict) -> Optional[float]:
        wv = w["run_rate"]["pool"]
        lv = lifetime_doss["run_rate"]["pool"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": {
            "last_10_runs_mean_minus_lifetime":      _delta_runs(last_10_doss),
            "last_10_run_rate_pool_minus_lifetime":  _delta_rr(last_10_doss),
            "last_60d_runs_mean_minus_lifetime":     _delta_runs(last_60d_doss),
            "last_60d_run_rate_pool_minus_lifetime": _delta_rr(last_60d_doss),
            "last_6mo_runs_mean_minus_lifetime":     _delta_runs(last_6mo_doss),
            "last_6mo_run_rate_pool_minus_lifetime": _delta_rr(last_6mo_doss),
            "last_1yr_runs_mean_minus_lifetime":     _delta_runs(last_1yr_doss),
            "last_1yr_run_rate_pool_minus_lifetime": _delta_rr(last_1yr_doss),
        },
    }


@router.get("/{team}/batting/distribution")
async def team_batting_distribution(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "ISO date (YYYY-MM-DD) to anchor the calendar form windows"
            " (last_60d / last_6mo / last_1yr). Defaults to today;"
            " pin for deterministic regression tests."
        ),
    ),
):
    """Per-innings team-batting distribution dossier.

    Two sibling distribution blocks under one master sample —
    `runs` (skewed continuous; chain-ladder conditionals at
    100/150/200/230 + over-aware doubling at the 10-over checkpoint)
    and `run_rate` (continuous per-over) — plus phase decomposition,
    four form windows (last_10 / last_60d / last_6mo / last_1yr),
    and scope-derived suggested-splits navigation hints.

    Every probability field ships as `{value, num, denom, ci_low,
    ci_high}` with a Wilson 95% CI. Calendar form windows use a
    scope-anchored cutoff (`min(today, max_obs_date)`) so retired
    teams get non-empty windows.

    `FilterParams.filter_team` is IGNORED — the team path-param
    dominates. `FilterParams.filter_opponent` works as expected.

    Spec: internal_docs/spec-distribution-stats.md §16.2.
    """
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations = await _innings_master_sample_team_batting(team, filters, aux)
    lifetime = _distribution_dossier_team_batting(observations)
    form = _form_windows_team_batting(observations, today)

    obs_dates = [o["date"] for o in observations if o.get("date")]
    lifetime["last_match_date"] = max(obs_dates) if obs_dates else None

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "team": team,
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }


async def _team_batting_by_season_baseline(team, filters, aux):
    """One row per season — SUM-over-tournaments since cells split per
    (tournament, season, team)."""
    from .bucket_baseline_dispatch import baseline_where
    db = get_db()
    where, params = baseline_where(filters, aux, team=team)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_batted) AS innings_batted,
               SUM(total_runs) AS total_runs,
               SUM(legal_balls) AS legal_balls,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots,
               COALESCE(MAX(highest_inn_runs), 0) AS highest_total,
               MIN(lowest_all_out_runs) AS lowest_all_out_total
        FROM bucketbaselinebatting {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    out = []
    for r in rows:
        runs = r["total_runs"] or 0
        balls = r["legal_balls"] or 0
        innings = r["innings_batted"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        dots = r["dots"] or 0
        boundaries = fours + sixes
        out.append({
            "season": r["season"],
            "innings_batted": innings,
            "total_runs": runs,
            "legal_balls": balls,
            "avg_innings_total": _safe_div(runs, innings, 1, 1),
            "run_rate": _safe_div(runs, balls, 6),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "dot_pct": _safe_div(dots, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
            "highest_total": r["highest_total"],
            "lowest_all_out_total": r["lowest_all_out_total"],
        })
    return {"seasons": out}


@router.get("/{team}/batting/by-season")
async def team_batting_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    from .bucket_baseline_dispatch import is_precomputed_scope, baseline_where
    if is_precomputed_scope(filters, aux):
        return await _team_batting_by_season_baseline(team, filters, aux)

    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)

    # Per-season aggregate deliveries
    season_rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_batted,
            SUM(d.runs_total) as total_runs,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    # Per-innings totals for highest / lowest all-out
    innings_rows = await db.q(
        f"""
        SELECT
            m.season, i.id as innings_id,
            SUM(d.runs_total) as runs,
            (SELECT COUNT(*) FROM wicket w2
             JOIN delivery d2 ON d2.id = w2.delivery_id
             WHERE d2.innings_id = i.id
               AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_lost
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, i.id
        """,
        params,
    )
    by_season_innings: dict[str, list] = {}
    for r in innings_rows:
        by_season_innings.setdefault(r["season"], []).append(r)

    seasons = []
    for s in season_rows:
        season = s["season"]
        total_runs = s["total_runs"] or 0
        innings_batted = s["innings_batted"] or 0
        legal_balls = s["legal_balls"] or 0
        fours = s["fours"] or 0
        sixes = s["sixes"] or 0
        dots = s["dots"] or 0
        boundaries = fours + sixes

        inn_list = by_season_innings.get(season, [])
        highest = max((r["runs"] or 0 for r in inn_list), default=0)
        all_out = [r for r in inn_list if (r["wickets_lost"] or 0) >= 10]
        lowest_all_out = min((r["runs"] or 0 for r in all_out), default=None)

        seasons.append({
            "season": season,
            "innings_batted": innings_batted,
            "total_runs": total_runs,
            "legal_balls": legal_balls,
            "avg_innings_total": _safe_div(total_runs, innings_batted, 1, 1),
            "run_rate": _safe_div(total_runs, legal_balls, 6),
            "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
            "dot_pct": _safe_div(dots, legal_balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
            "highest_total": highest,
            "lowest_all_out_total": lowest_all_out,
        })

    return {"seasons": seasons}


async def _batting_by_phase_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict[str, dict]:
    """Flat per-phase batting aggregates keyed by phase name. Called
    twice by team_batting_by_phase (team + None for scope_avg).
    Dispatches to bucket_baseline_phase + a small live wkt query for
    precomputed scopes; full live aggregation otherwise."""
    from .bucket_baseline_dispatch import is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY
    if is_precomputed_scope(filters, aux):
        return await _batting_by_phase_aggregates_baseline(team, filters, aux)
    return await _batting_by_phase_aggregates_live(team, filters, aux)


async def _batting_by_phase_aggregates_baseline(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict[str, dict]:
    from .bucket_baseline_dispatch import baseline_where, LEAGUE_TEAM_KEY
    db = get_db()
    table_team = team if team else LEAGUE_TEAM_KEY
    bw, bp = baseline_where(filters, aux, team=table_team)
    rows = await db.q(
        f"""
        SELECT phase,
               SUM(legal_balls) AS balls,
               SUM(runs) AS runs,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots
        FROM bucketbaselinephase {bw} AND side='batting'
        GROUP BY phase
        """,
        bp,
    )
    # wickets_lost uses retired-only exclusion; baseline.wickets is
    # bowler-credited (excludes more). Small live query for the diff.
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)
    wicket_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wicket_map = {r["phase"]: r["wickets_lost"] for r in wicket_rows}
    out: dict[str, dict] = {}
    for r in rows:
        phase = r["phase"]
        if not phase:
            continue
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        boundaries = fours + sixes
        out[phase] = {
            "phase": phase,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wicket_map.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "bat_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        }
    if team is None:
        out = _phase_dict_per_innings(out, await _innings_count_for_phase(filters, aux, side="batting"))
    return out


async def _batting_by_phase_aggregates_live(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict[str, dict]:
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )
    wicket_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY phase
        """,
        params,
    )
    wicket_map = {r["phase"]: r["wickets_lost"] for r in wicket_rows}

    out: dict[str, dict] = {}
    for r in rows:
        phase = r["phase"]
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        boundaries = fours + sixes
        out[phase] = {
            "phase": phase,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wicket_map.get(phase, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "bat_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        }
    if team is None:
        out = _phase_dict_per_innings(out, await _innings_count_for_phase(filters, aux, side="batting"))
    return out


async def _batting_by_inning_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict[int, dict]:
    """Flat per-inning batting aggregates keyed by innings_number (0/1).

    Mirrors `_batting_by_phase_aggregates_live` but `GROUP BY
    i.innings_number` instead of by phase CASE. Live only — bucket
    tables don't carry an innings dimension. Spec:
    spec-inning-split.md §3.2 + §5.5.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            i.innings_number AS inning,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.innings_number
        """,
        params,
    )
    wicket_rows = await db.q(
        f"""
        SELECT i.innings_number AS inning, COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY i.innings_number
        """,
        params,
    )
    wicket_map = {r["inning"]: r["wickets_lost"] for r in wicket_rows}

    out: dict[int, dict] = {}
    for r in rows:
        inning = r["inning"]
        if inning not in (0, 1):
            continue
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        boundaries = fours + sixes
        out[inning] = {
            "inning": inning,
            "runs": runs,
            "balls": balls,
            "run_rate": _safe_div(runs, balls, 6),
            "wickets_lost": wicket_map.get(inning, 0),
            "boundary_pct": _safe_div(boundaries, balls, 100, 1),
            "bat_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours": fours,
            "sixes": sixes,
        }
    if team is None:
        out = _inning_dict_per_innings(
            out, await _innings_count_per_inning(filters, aux, side="batting"),
        )
    return out


@router.get("/{team}/batting/by-inning")
async def team_batting_by_inning(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-innings_number batting band — sibling of /by-phase. Returns
    an `innings` array with up to two entries (1st innings / 2nd
    innings) carrying the same metrics + chip envelopes as /by-phase.
    Spec: spec-inning-split.md §3.2.
    """
    t = await _batting_by_inning_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _batting_by_inning_aggregates(None, lf, la)

    innings = []
    for inn_no in (0, 1):
        tr = t.get(inn_no)
        if tr is None:
            continue
        sr = s.get(inn_no, {})
        balls = tr["balls"]
        innings.append({
            "inning_no": inn_no,
            "label": "1st innings" if inn_no == 0 else "2nd innings",
            "runs": tr["runs"],
            "balls": balls,
            "run_rate":     wrap_metric(tr["run_rate"], sr.get("run_rate"), "run_rate", sample_size=balls),
            "wickets_lost": tr["wickets_lost"],
            "boundary_pct": wrap_metric(tr["boundary_pct"], sr.get("boundary_pct"), "boundary_pct", sample_size=balls),
            "dot_pct":      wrap_metric(tr["bat_dot_pct"], sr.get("bat_dot_pct"), "bat_dot_pct", sample_size=balls),
            "fours": tr["fours"],
            "sixes": tr["sixes"],
        })
    return {"innings": innings}


@router.get("/{team}/batting/by-phase")
async def team_batting_by_phase(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _batting_by_phase_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _batting_by_phase_aggregates(None, lf, la)

    phase_ranges = {
        "powerplay": [1, 6],
        "middle": [7, 15],
        "death": [16, 20],
    }
    phases = []
    # Stable order, regardless of SQL ordering.
    for phase in ("powerplay", "middle", "death"):
        tr = t.get(phase)
        if tr is None:
            continue
        sr = s.get(phase, {})
        balls = tr["balls"]
        phases.append({
            "phase": phase,
            "overs_range": phase_ranges.get(phase, []),
            "runs": tr["runs"],
            "balls": balls,
            "run_rate":     wrap_metric(tr["run_rate"], sr.get("run_rate"), "run_rate", sample_size=balls),
            "wickets_lost": tr["wickets_lost"],
            "boundary_pct": wrap_metric(tr["boundary_pct"], sr.get("boundary_pct"), "boundary_pct", sample_size=balls),
            "dot_pct":      wrap_metric(tr["bat_dot_pct"], sr.get("bat_dot_pct"), "bat_dot_pct", sample_size=balls),
            "fours": tr["fours"],
            "sixes": tr["sixes"],
        })
    return {"phases": phases}


@router.get("/{team}/batting/top-batters")
async def team_top_batters(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT d.batter_id as person_id, p.name,
               SUM(d.runs_batter) as runs,
               COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
               SUM(CASE WHEN d.runs_batter = 4
                        AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
               COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE {where} AND d.batter_id IS NOT NULL
        GROUP BY d.batter_id, p.name
        ORDER BY runs DESC
        LIMIT :lim
        """,
        params,
    )
    top = []
    for r in rows:
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        top.append({
            "person_id": r["person_id"],
            "name": r["name"] or r["person_id"],
            "runs": runs,
            "balls": balls,
            "strike_rate": _safe_div(runs, balls, 100),
            "fours": r["fours"] or 0,
            "sixes": r["sixes"] or 0,
            "innings": r["innings"] or 0,
        })
    return {"top_batters": top}


@router.get("/{team}/batting/phase-season-heatmap")
async def team_batting_phase_season_heatmap(
    team: str, filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Season × phase matrix for batting — both run_rate and
    wickets_lost per cell, so the frontend can render two heatmaps
    from one round-trip.

    Cells: {season, phase, run_rate, wickets_lost, balls}.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="batting", aux=aux)

    rate_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, phase
        ORDER BY m.season
        """,
        params,
    )

    wicket_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets_lost
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND w.kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season, phase
        """,
        params,
    )
    wmap = {(r["season"], r["phase"]): r["wickets_lost"] for r in wicket_rows}

    seasons, seen_s = [], set()
    cells = []
    for r in rate_rows:
        s = r["season"]
        if s not in seen_s:
            seen_s.add(s)
            seasons.append(s)
        balls = r["balls"] or 0
        innings = r["innings"] or 0
        wkts = wmap.get((s, r["phase"]), 0)
        cells.append({
            "season": s,
            "phase": r["phase"],
            "run_rate": round((r["runs"] or 0) * 6 / balls, 2) if balls else None,
            "wickets_lost": wkts,
            "wickets_per_innings": round(wkts / innings, 2) if innings else None,
            "innings": innings,
            "balls": balls,
        })
    seasons.sort()
    return {
        "team": team,
        "seasons": seasons,
        "phases": ["powerplay", "middle", "death"],
        "cells": cells,
    }


# Bowling wickets exclude these kinds — a run-out isn't credited to the
# bowler, nor are retirement/obstructing-the-field.
BOWLER_WICKET_EXCLUDE = "('run out', 'retired hurt', 'retired out', 'obstructing the field', 'retired not out')"


async def _bowling_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Flat-shape bowling aggregates. Called twice by
    `_compute_bowling_summary` (team + None for scope_avg). When team is
    None, identity-bearing fields (worst_conceded, best_defence) are
    null."""
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        return await _bowling_aggregates_baseline(team, filters, aux)
    return await _bowling_aggregates_live(team, filters, aux)


async def _bowling_aggregates_baseline(team, filters, aux):
    from .bucket_baseline_dispatch import baseline_where, LEAGUE_TEAM_KEY
    db = get_db()
    table_team = team if team else LEAGUE_TEAM_KEY
    where, params = baseline_where(filters, aux, team=table_team)
    rows = await db.q(
        f"""
        SELECT
          SUM(innings_bowled) AS innings_bowled,
          SUM(matches) AS matches,
          SUM(runs_conceded) AS runs_conceded,
          SUM(legal_balls) AS legal_balls,
          -- Convention 2 (unified 2026-04-26): both endpoints return
          -- delivery COUNT, not run-total. wide_runs/noball_runs columns
          -- still populated for callers that genuinely want runs total.
          SUM(wides) AS wides,
          SUM(noballs) AS noballs,
          SUM(fours_conceded) AS fours_conceded,
          SUM(sixes_conceded) AS sixes_conceded,
          SUM(dots) AS dots,
          SUM(wickets) AS wickets
        FROM bucketbaselinebowling {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    runs_conceded = r.get("runs_conceded") or 0
    legal_balls = r.get("legal_balls") or 0
    matches = r.get("matches") or 0
    wickets = r.get("wickets") or 0

    # avg_opposition_total = runs_conceded / innings_bowled (per-innings).
    innings_bowled = r.get("innings_bowled") or 0
    avg_opp_total = round(runs_conceded / innings_bowled, 1) if innings_bowled else None

    # worst_conceded identity — find the cell with largest worst_inn_runs.
    worst = None
    if team is not None:  # only meaningful per-team
        worst_rows = await db.q(
            f"""
            SELECT worst_inn_runs FROM bucketbaselinebowling {where}
              AND worst_inn_runs > 0
            ORDER BY worst_inn_runs DESC LIMIT 1
            """,
            params,
        )
        if worst_rows:
            # Identity columns (match_id, innings_number) NOT in schema —
            # one tiny live SELECT to find the matching innings row.
            wp_where, wp_params = _team_innings_clause(filters, team, side="fielding", aux=aux)
            wid_rows = await db.q(
                f"""
                SELECT i.id AS innings_id, i.match_id, i.innings_number,
                       SUM(d.runs_total) AS runs
                FROM delivery d
                JOIN innings i ON i.id = d.innings_id
                JOIN match m ON m.id = i.match_id
                WHERE {wp_where}
                GROUP BY i.id ORDER BY runs DESC LIMIT 1
                """,
                wp_params,
            )
            if wid_rows:
                w = wid_rows[0]
                worst = {
                    "runs": w["runs"] or 0,
                    "match_id": w["match_id"],
                    "innings_number": (w["innings_number"] or 0) + 1,
                }

    # best_defence — only meaningful per-team. Stays live (rare query,
    # not in baseline schema).
    best_defence = None
    if team is not None:
        wp_where, wp_params = _team_innings_clause(filters, team, side="fielding", aux=aux)
        defended_rows = await db.q(
            f"""
            SELECT i.match_id, SUM(d.runs_total) AS runs
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {wp_where} AND m.outcome_winner = :team AND i.innings_number = 1
            GROUP BY i.id, i.match_id ORDER BY runs ASC LIMIT 1
            """,
            {**wp_params, "team": team},
        )
        if defended_rows:
            d = defended_rows[0]
            best_defence = {
                "runs": d["runs"] or 0,
                "match_id": d["match_id"],
            }

    out = {
        "innings_bowled": innings_bowled,
        "matches": matches,
        "runs_conceded": runs_conceded,
        "legal_balls": legal_balls,
        "overs": round(legal_balls / 6, 1) if legal_balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs_conceded, legal_balls, 6),
        "strike_rate": _safe_div(legal_balls, wickets),
        "average": _safe_div(runs_conceded, wickets),
        "bowl_dot_pct": _safe_div(r.get("dots") or 0, legal_balls, 100, 1),
        "fours_conceded": r.get("fours_conceded") or 0,
        "sixes_conceded": r.get("sixes_conceded") or 0,
        "boundaries_conceded": (r.get("fours_conceded") or 0) + (r.get("sixes_conceded") or 0),
        "wides": r.get("wides") or 0,
        "noballs": r.get("noballs") or 0,
        "wides_per_match": _safe_div(r.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(r.get("noballs") or 0, matches, 1, 2),
        "avg_opposition_total": avg_opp_total,
        "worst_conceded": worst,
        "best_defence": best_defence,
    }
    if team is None:
        return _apply_bowling_per_innings(out, innings_bowled)
    return out


async def _bowling_aggregates_live(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict:
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    core = await db.q(
        f"""
        SELECT
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            COUNT(*) as all_balls,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            -- Convention 2 (unified 2026-04-26): COUNT of wide/noball
            -- deliveries, not run-total.
            SUM(CASE WHEN d.extras_wides > 0 THEN 1 ELSE 0 END) as wides,
            SUM(CASE WHEN d.extras_noballs > 0 THEN 1 ELSE 0 END) as noballs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    c = core[0] if core else {}
    runs_conceded = c.get("runs_conceded") or 0
    legal_balls = c.get("legal_balls") or 0
    innings_bowled = c.get("innings_bowled") or 0
    fours = c.get("fours_conceded") or 0
    sixes = c.get("sixes_conceded") or 0
    dots = c.get("dots") or 0

    # Wickets taken by bowlers on this team
    w_where = where  # same scope
    w_params = params.copy()
    wicket_rows = await db.q(
        f"""
        SELECT COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {w_where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        """,
        w_params,
    )
    wickets = wicket_rows[0]["wickets"] if wicket_rows else 0

    # Matches count for per-match averages
    match_count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    matches = match_count_rows[0]["matches"] if match_count_rows else 0

    # Opposition innings totals (for avg / worst conceded / best defence)
    opp_innings = await db.q(
        f"""
        SELECT i.id as innings_id, i.match_id, i.innings_number,
               SUM(d.runs_total) as runs,
               (SELECT COUNT(*) FROM wicket w2
                JOIN delivery d2 ON d2.id = w2.delivery_id
                WHERE d2.innings_id = i.id
                  AND w2.kind NOT IN ('retired hurt', 'retired not out')) as wickets_taken,
               m.outcome_winner
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.id, i.match_id, i.innings_number, m.outcome_winner
        """,
        params,
    )
    avg_opp_total = None
    if opp_innings:
        avg_opp_total = round(
            sum(r["runs"] or 0 for r in opp_innings) / len(opp_innings), 1
        )
    # Worst conceded: highest opposition total
    worst = None
    if opp_innings:
        top = max(opp_innings, key=lambda r: r["runs"] or 0)
        worst = {
            "runs": top["runs"] or 0,
            "match_id": top["match_id"],
            "innings_number": top["innings_number"] + 1,
        }
    # Best defence: lowest total successfully defended (team bowled 2nd,
    # bowled out opposition OR ran out overs with lower score than the
    # opposition's target). Simpler heuristic: innings where our team
    # WON (outcome_winner = :team), innings_number = 1 (chase failed),
    # lowest opposition runs.
    best_defence = None
    if team is not None:
        defended = [
            r for r in opp_innings
            if r["outcome_winner"] == team and r["innings_number"] == 1
        ]
        if defended:
            lo = min(defended, key=lambda r: r["runs"] or 0)
            best_defence = {
                "runs": lo["runs"] or 0,
                "match_id": lo["match_id"],
            }

    out = {
        "innings_bowled": innings_bowled,
        "matches": matches,
        "runs_conceded": runs_conceded,
        "legal_balls": legal_balls,
        "overs": round(legal_balls / 6, 1) if legal_balls else 0,
        "wickets": wickets,
        "economy": _safe_div(runs_conceded, legal_balls, 6),
        "strike_rate": _safe_div(legal_balls, wickets),
        "average": _safe_div(runs_conceded, wickets),
        "bowl_dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours_conceded": fours,
        "sixes_conceded": sixes,
        "boundaries_conceded": fours + sixes,
        "wides": c.get("wides") or 0,
        "noballs": c.get("noballs") or 0,
        "wides_per_match": _safe_div(c.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(c.get("noballs") or 0, matches, 1, 2),
        "avg_opposition_total": avg_opp_total,
        "worst_conceded": worst,
        "best_defence": best_defence,
    }
    if team is None:
        return _apply_bowling_per_innings(out, innings_bowled)
    return out


async def _compute_bowling_summary(
    team: str,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Per-metric envelope team-bowling summary."""
    t = await _bowling_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _bowling_aggregates(None, lf, la)
    legal = t.get("legal_balls") or 0
    matches = t.get("matches") or 0
    return {
        "team": team,
        "innings_bowled": wrap_metric(t["innings_bowled"], s["innings_bowled"], "innings_bowled", sample_size=t["innings_bowled"]),
        "matches": wrap_metric(t["matches"], s["matches"], "matches", sample_size=matches),
        "runs_conceded": wrap_metric(t["runs_conceded"], s["runs_conceded"], "runs_conceded", sample_size=legal),
        "legal_balls": wrap_metric(t["legal_balls"], s["legal_balls"], "legal_balls", sample_size=legal),
        "overs": wrap_metric(t["overs"], s["overs"], "overs", sample_size=legal),
        "wickets": wrap_metric(t["wickets"], s["wickets"], "wickets", sample_size=legal),
        "economy": wrap_metric(t["economy"], s["economy"], "economy", sample_size=legal),
        "strike_rate": wrap_metric(t["strike_rate"], s["strike_rate"], "strike_rate", sample_size=legal),
        "average": wrap_metric(t["average"], s["average"], "average", sample_size=t["wickets"]),
        # Server-side field "dot_pct" — bowling direction (higher is better) via key "bowl_dot_pct".
        "dot_pct": wrap_metric(t["bowl_dot_pct"], s["bowl_dot_pct"], "bowl_dot_pct", sample_size=legal),
        "fours_conceded": wrap_metric(t["fours_conceded"], s["fours_conceded"], "fours_conceded", sample_size=legal),
        "sixes_conceded": wrap_metric(t["sixes_conceded"], s["sixes_conceded"], "sixes_conceded", sample_size=legal),
        "boundaries_conceded": wrap_metric(t["boundaries_conceded"], s["boundaries_conceded"], "boundaries_conceded", sample_size=legal),
        "wides": wrap_metric(t["wides"], s["wides"], "wides", sample_size=matches),
        "noballs": wrap_metric(t["noballs"], s["noballs"], "noballs", sample_size=matches),
        # Per-match league rates: `s` is already halved at source by
        # `_apply_bowling_per_innings(out, innings_bowled)` when called
        # with team=None (spec-avg-column-per-innings.md Commit 2).
        # Don't wrap with _half() — that would double-halve.
        "wides_per_match": wrap_metric(t["wides_per_match"], s["wides_per_match"], "wides_per_match", sample_size=matches),
        "noballs_per_match": wrap_metric(t["noballs_per_match"], s["noballs_per_match"], "noballs_per_match", sample_size=matches),
        "avg_opposition_total": wrap_metric(t["avg_opposition_total"], s["avg_opposition_total"], "avg_opposition_total", sample_size=t["innings_bowled"]),
        "worst_conceded": t["worst_conceded"],
        "best_defence": t["best_defence"],
    }


@router.get("/{team}/bowling/summary")
async def team_bowling_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    return await _compute_bowling_summary(team, filters, aux)


# ============================================================
# Team bowling — distribution dossier (spec §16.3).
# Per-innings observation row (the OPPONENT's batting innings) +
# three sibling blocks (wickets + runs_conceded + economy) +
# phase rollup + four form windows. Reuses _team_innings_clause
# (side='fielding') for the side-neutral filter scope.
#
# Wickets INCLUDE run-outs per spec §16.3.1 — "wickets the team
# took" naturally credits the team for sharp run-outs. This
# DIVERGES from team-bowling/summary's bowler-credited count
# (which uses BOWLER_WICKET_EXCLUDE). Exclusion list here:
# 'retired hurt', 'retired out', 'retired not out', 'obstructing
# the field'. The spec's claim that this "mirrors team-bowling/
# summary" was inaccurate; the distribution slice intentionally
# uses the broader "team-credited" count.
# ============================================================


# Team-bowling-side wicket exclusion: drops the four kinds that
# aren't team-credited (retirements + obstruction). INCLUDES
# 'run out' since the team caused it. Spec §16.3.1.
_TEAM_BOWLING_WICKET_EXCLUDE = (
    "('retired hurt', 'retired out', 'retired not out', 'obstructing the field')"
)


async def _innings_master_sample_team_bowling(
    team: str, filters: FilterParams, aux: AuxParams,
) -> list[dict]:
    """Per-innings observation rows of the OPPONENT's batting
    innings under the active filter scope, where the path-team is
    the bowling/fielding side (`i.team != :team` AND match has
    :team as one of the pair). Spec §16.3.1.

    Wickets is the TEAM-CREDITED count (includes run-outs); see
    the comment block above for rationale and divergence from
    team-bowling/summary.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)
    rows = await db.q(
        f"""
        SELECT
            i.id AS innings_id,
            i.match_id,
            i.innings_number,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) AS date,
            SUM(d.runs_total) AS runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls,
            SUM(CASE WHEN w.id IS NOT NULL THEN 1 ELSE 0 END) AS wickets,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                     THEN d.runs_total ELSE 0 END) AS runs_at_10,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_at_10,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 9
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS legal_balls_first_10,
            -- Phase: powerplay (overs 1-6, over_number 0-5)
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     THEN d.runs_total ELSE 0 END) AS runs_pp,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_pp,
            SUM(CASE WHEN d.over_number BETWEEN 0 AND 5 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_pp,
            -- Phase: middle (overs 7-15, over_number 6-14)
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     THEN d.runs_total ELSE 0 END) AS runs_mid,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_mid,
            SUM(CASE WHEN d.over_number BETWEEN 6 AND 14 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_mid,
            -- Phase: death (overs 16-20, over_number 15-19)
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     THEN d.runs_total ELSE 0 END) AS runs_death,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19
                     AND d.extras_wides = 0 AND d.extras_noballs = 0
                     THEN 1 ELSE 0 END) AS balls_death,
            SUM(CASE WHEN d.over_number BETWEEN 15 AND 19 AND w.id IS NOT NULL
                     THEN 1 ELSE 0 END) AS wickets_death
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN wicket w ON w.delivery_id = d.id
            AND w.kind NOT IN {_TEAM_BOWLING_WICKET_EXCLUDE}
        WHERE {where}
        GROUP BY i.id
        ORDER BY date ASC, i.innings_number ASC
        """,
        params,
    )
    out = []
    for r in rows:
        legal_first_10 = r["legal_balls_first_10"] or 0
        out.append({
            "innings_id": r["innings_id"],
            "match_id": r["match_id"],
            "innings_number": r["innings_number"],
            "date": r["date"],
            "runs_conceded": r["runs_conceded"] or 0,
            "balls": r["balls"] or 0,
            "wickets": r["wickets"] or 0,
            "runs_at_10": r["runs_at_10"] or 0,
            "wickets_at_10": r["wickets_at_10"] or 0,
            "reached_10_overs": 1 if legal_first_10 >= 60 else 0,
            "runs_pp": r["runs_pp"] or 0,
            "balls_pp": r["balls_pp"] or 0,
            "wickets_pp": r["wickets_pp"] or 0,
            "runs_mid": r["runs_mid"] or 0,
            "balls_mid": r["balls_mid"] or 0,
            "wickets_mid": r["wickets_mid"] or 0,
            "runs_death": r["runs_death"] or 0,
            "balls_death": r["balls_death"] or 0,
            "wickets_death": r["wickets_death"] or 0,
        })
    return out


def _wickets_block_team_bowling(observations: list[dict]) -> dict:
    """`wickets` block — discrete count distribution + simples +
    ≥5-anchored conditional ladder + over-aware early-breakthrough
    + finishing rate. Spec §16.3.2."""
    n = len(observations)
    wkts = [o["wickets"] for o in observations]

    if n == 0:
        keys = [
            "p_leq_3", "p_geq_5", "p_geq_7", "p_eq_10",
            "p_7_given_5", "p_10_given_5",
            "p_geq_3_at_10", "p_eq_10_given_3_at_10",
        ]
        return {
            "total": 0,
            "mean_per_innings": None,
            "median": None,
            "variance": None,
            "std": None,
            "observations": [],
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(wkts)
    mean = total / n
    median = statistics.median(wkts)
    variance = statistics.variance(wkts) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_eq(v: int) -> int:
        return sum(1 for w in wkts if w == v)

    def _count_geq(v: int) -> int:
        return sum(1 for w in wkts if w >= v)

    def _count_leq(v: int) -> int:
        return sum(1 for w in wkts if w <= v)

    geq_5 = _count_geq(5)
    geq_7 = _count_geq(7)
    eq_10 = _count_eq(10)

    # Over-aware (denom = innings with reached_10_overs=1).
    reached_10 = [o for o in observations if o["reached_10_overs"] == 1]
    reached_10_n = len(reached_10)
    early_break_pool = [o for o in reached_10 if o["wickets_at_10"] >= 3]
    early_break_n = len(early_break_pool)
    finished_after_break = sum(1 for o in early_break_pool if o["wickets"] == 10)

    return {
        "total": total,
        "mean_per_innings": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "observations": observations,
        "milestones": {
            "p_leq_3":  prob_record(_count_leq(3), n),
            "p_geq_5":  prob_record(geq_5, n),
            "p_geq_7":  prob_record(geq_7, n),
            "p_eq_10":  prob_record(eq_10, n),
            # Anchored conditionals (denom = count(≥5)).
            "p_7_given_5":  prob_record(geq_7, geq_5),
            "p_10_given_5": prob_record(eq_10, geq_5),
            # Over-aware.
            "p_geq_3_at_10": prob_record(early_break_n, reached_10_n),
            "p_eq_10_given_3_at_10": prob_record(finished_after_break, early_break_n),
        },
    }


def _runs_conceded_block_team_bowling(observations: list[dict]) -> dict:
    """`runs_conceded` block — mirror of team-batting `runs` with
    polarity flipped color-wise. Spec §16.3.2."""
    n = len(observations)
    runs = [o["runs_conceded"] for o in observations]

    if n == 0:
        keys = [
            "p_lt_100", "p_lt_150", "p_geq_150", "p_geq_200", "p_geq_230",
            "p_150_given_100", "p_200_given_150", "p_230_given_200",
            "p_double_at_10",
        ]
        return {
            "total": 0,
            "mean_per_innings": None,
            "median": None,
            "variance": None,
            "std": None,
            "escalation_ratio_median": None,
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(runs)
    mean = total / n
    median = statistics.median(runs)
    variance = statistics.variance(runs) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_lt(v: int) -> int:
        return sum(1 for r in runs if r < v)

    def _count_geq(v: int) -> int:
        return sum(1 for r in runs if r >= v)

    geq_100 = _count_geq(100)
    geq_150 = _count_geq(150)
    geq_200 = _count_geq(200)
    geq_230 = _count_geq(230)

    doubling_pool = [
        o for o in observations
        if o["reached_10_overs"] == 1 and o["runs_at_10"] > 0
    ]
    doubling_denom = len(doubling_pool)
    doubling_num = sum(
        1 for o in doubling_pool
        if o["runs_conceded"] >= 2 * o["runs_at_10"]
    )
    ratios = [o["runs_conceded"] / o["runs_at_10"] for o in doubling_pool]
    escalation_median = round(statistics.median(ratios), 4) if ratios else None

    return {
        "total": total,
        "mean_per_innings": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "escalation_ratio_median": escalation_median,
        "milestones": {
            "p_lt_100":  prob_record(_count_lt(100), n),
            "p_lt_150":  prob_record(_count_lt(150), n),
            "p_geq_150": prob_record(geq_150, n),
            "p_geq_200": prob_record(geq_200, n),
            "p_geq_230": prob_record(geq_230, n),
            "p_150_given_100": prob_record(geq_150, geq_100),
            "p_200_given_150": prob_record(geq_200, geq_150),
            "p_230_given_200": prob_record(geq_230, geq_200),
            "p_double_at_10": prob_record(doubling_num, doubling_denom),
        },
    }


def _economy_block_team_bowling(observations: list[dict]) -> dict:
    """`economy` block — continuous per-over rate. Same shape as
    bowler v1 §11.4.3. Both `pool` (balls-weighted) and
    `mean_per_innings` (unweighted mean of per-innings RPO) ship.
    Spec §16.3.2."""
    n = len(observations)

    if n == 0:
        keys = ["p_econ_leq_6", "p_econ_leq_7", "p_econ_geq_9", "p_econ_geq_10"]
        return {
            "pool": None,
            "mean_per_innings": None,
            "median_per_innings": None,
            "variance": None,
            "std": None,
            "per_innings": [],
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total_runs = sum(o["runs_conceded"] for o in observations)
    total_balls = sum(o["balls"] for o in observations)
    pool = (total_runs * 6.0 / total_balls) if total_balls > 0 else None

    per_innings = [round(o["runs_conceded"] * 6.0 / o["balls"], 4)
                   for o in observations if o["balls"] > 0]
    mean_pi = sum(per_innings) / len(per_innings) if per_innings else None
    median_pi = statistics.median(per_innings) if per_innings else None
    variance = statistics.variance(per_innings) if len(per_innings) >= 2 else 0.0
    std = variance ** 0.5

    def _count_leq(v: float) -> int:
        return sum(1 for e in per_innings if e <= v)

    def _count_geq(v: float) -> int:
        return sum(1 for e in per_innings if e >= v)

    return {
        "pool": round(pool, 4) if pool is not None else None,
        "mean_per_innings": round(mean_pi, 4) if mean_pi is not None else None,
        "median_per_innings": round(median_pi, 4) if median_pi is not None else None,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "per_innings": per_innings,
        "milestones": {
            "p_econ_leq_6":  prob_record(_count_leq(6.0), n),
            "p_econ_leq_7":  prob_record(_count_leq(7.0), n),
            "p_econ_geq_9":  prob_record(_count_geq(9.0), n),
            "p_econ_geq_10": prob_record(_count_geq(10.0), n),
        },
    }


def _phase_rollup_team_bowling(observations: list[dict]) -> dict:
    """Per-phase rollup mirroring team-batting (§16.2.3). Spec §16.3.3."""
    out = {}
    keys = {
        "powerplay": ("runs_pp", "balls_pp", "wickets_pp"),
        "middle":    ("runs_mid", "balls_mid", "wickets_mid"),
        "death":     ("runs_death", "balls_death", "wickets_death"),
    }
    for name, (rk, bk, wk) in keys.items():
        out[name] = {
            "runs_total": sum(o[rk] for o in observations),
            "balls_total": sum(o[bk] for o in observations),
            "wickets_total": sum(o[wk] for o in observations),
            "innings_active": sum(1 for o in observations if o[bk] > 0),
        }
    return out


def _distribution_dossier_team_bowling(observations: list[dict]) -> dict:
    """Pure aggregate. Three sibling blocks (wickets + runs_conceded
    + economy) + phase rollup. Spec §16.3."""
    wickets_block = _wickets_block_team_bowling(observations)
    runs_block = _runs_conceded_block_team_bowling(observations)
    # pool_strike_rate (balls/wkt) + pool_average (runs/wkt) — server-
    # computed (audit §4.3) so TeamBowlingStatStrips.tsx can read these
    # directly instead of cascade-deriving balls via runs*6/economy.
    # Mirrors the bowler /distribution endpoint's pool_strike_rate +
    # pool_average fields.
    total_balls = sum(o.get("balls") or 0 for o in observations)
    total_runs = runs_block.get("total") or 0
    total_wickets = wickets_block.get("total") or 0
    pool_strike_rate = round(total_balls / total_wickets, 4) if total_wickets > 0 else None
    pool_average = round(total_runs / total_wickets, 4) if total_wickets > 0 else None
    return {
        "n_innings": len(observations),
        "pool_strike_rate": pool_strike_rate,
        "pool_average": pool_average,
        "wickets": wickets_block,
        "runs_conceded": runs_block,
        "economy": _economy_block_team_bowling(observations),
        "phase": _phase_rollup_team_bowling(observations),
    }


def _form_windows_team_bowling(
    observations: list[dict], today: date,
) -> dict:
    """Slice the date-asc observation list into four form windows,
    run the dossier on each, emit a 12-entry delta block (4 windows
    × 3 metrics: wickets_mean, runs_conceded_mean, economy_pool
    minus lifetime). Spec §16.3.4."""
    anchor = scope_anchor(observations, today)
    last_10 = observations[-10:]
    cutoff_60d = (anchor - timedelta(days=60)).isoformat()
    cutoff_6mo = (anchor - timedelta(days=180)).isoformat()
    cutoff_1yr = (anchor - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    lifetime_doss = _distribution_dossier_team_bowling(observations)
    last_10_doss = _distribution_dossier_team_bowling(last_10)
    last_60d_doss = _distribution_dossier_team_bowling(last_60d)
    last_6mo_doss = _distribution_dossier_team_bowling(last_6mo)
    last_1yr_doss = _distribution_dossier_team_bowling(last_1yr)

    def _delta_wkts(w: dict) -> Optional[float]:
        wv = w["wickets"]["mean_per_innings"]
        lv = lifetime_doss["wickets"]["mean_per_innings"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    def _delta_runs(w: dict) -> Optional[float]:
        wv = w["runs_conceded"]["mean_per_innings"]
        lv = lifetime_doss["runs_conceded"]["mean_per_innings"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    def _delta_econ(w: dict) -> Optional[float]:
        wv = w["economy"]["pool"]
        lv = lifetime_doss["economy"]["pool"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    delta = {}
    for window_name, window_doss in (
        ("last_10", last_10_doss),
        ("last_60d", last_60d_doss),
        ("last_6mo", last_6mo_doss),
        ("last_1yr", last_1yr_doss),
    ):
        delta[f"{window_name}_wickets_mean_minus_lifetime"] = _delta_wkts(window_doss)
        delta[f"{window_name}_runs_conceded_mean_minus_lifetime"] = _delta_runs(window_doss)
        delta[f"{window_name}_economy_pool_minus_lifetime"] = _delta_econ(window_doss)

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": delta,
    }


@router.get("/{team}/bowling/distribution")
async def team_bowling_distribution(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "ISO date (YYYY-MM-DD) to anchor the calendar form windows"
            " (last_60d / last_6mo / last_1yr). Defaults to today;"
            " pin for deterministic regression tests."
        ),
    ),
):
    """Per-innings team-bowling distribution dossier.

    Three sibling distribution blocks under one master sample —
    `wickets` (discrete count; ≥5-anchored conditional ladder +
    over-aware `p_geq_3_at_10` early-breakthrough rate +
    `p_eq_10_given_3_at_10` finishing rate), `runs_conceded`
    (skewed continuous; chain-ladder leakage + over-aware doubling
    against the team), and `economy` (continuous per-over) —
    plus phase decomposition, four scope-anchored form windows,
    and scope-derived suggested-splits navigation hints.

    Wickets here is TEAM-CREDITED (includes run-outs); diverges
    from team-bowling/summary which uses bowler-credited wickets.
    See spec §16.3.1.

    Every probability field ships as `{value, num, denom, ci_low,
    ci_high}` with a Wilson 95% CI.

    `FilterParams.filter_team` is IGNORED — the team path-param
    dominates. `FilterParams.filter_opponent` works as expected.

    Spec: internal_docs/spec-distribution-stats.md §16.3.
    """
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations = await _innings_master_sample_team_bowling(team, filters, aux)
    lifetime = _distribution_dossier_team_bowling(observations)
    form = _form_windows_team_bowling(observations, today)

    obs_dates = [o["date"] for o in observations if o.get("date")]
    lifetime["last_match_date"] = max(obs_dates) if obs_dates else None

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "team": team,
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }


@router.get("/{team}/bowling/by-season")
async def team_bowling_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        return await _team_bowling_by_season_baseline(team, filters, aux)
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    season_rows = await db.q(
        f"""
        SELECT
            m.season,
            COUNT(DISTINCT i.id) as innings_bowled,
            SUM(d.runs_total) as runs_conceded,
            SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as legal_balls,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours_conceded,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes_conceded,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )

    # Wickets per season
    w_rows = await db.q(
        f"""
        SELECT m.season, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY m.season
        """,
        params,
    )
    wicket_map = {r["season"]: r["wickets"] for r in w_rows}

    # Opposition innings totals per season (for avg + worst)
    opp_inn_rows = await db.q(
        f"""
        SELECT m.season, i.id as innings_id,
               SUM(d.runs_total) as runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, i.id
        """,
        params,
    )
    by_season_opp: dict[str, list] = {}
    for r in opp_inn_rows:
        by_season_opp.setdefault(r["season"], []).append(r)

    seasons = []
    for s in season_rows:
        season = s["season"]
        runs_conc = s["runs_conceded"] or 0
        legal_balls = s["legal_balls"] or 0
        innings_bowled = s["innings_bowled"] or 0
        fours = s["fours_conceded"] or 0
        sixes = s["sixes_conceded"] or 0
        dots = s["dots"] or 0
        wickets = wicket_map.get(season, 0)
        opp_list = by_season_opp.get(season, [])
        avg_opp = round(sum(r["runs"] or 0 for r in opp_list) / len(opp_list), 1) if opp_list else None
        worst = max((r["runs"] or 0 for r in opp_list), default=0)

        seasons.append({
            "season": season,
            "innings_bowled": innings_bowled,
            "runs_conceded": runs_conc,
            "legal_balls": legal_balls,
            "overs": round(legal_balls / 6, 1) if legal_balls else 0,
            "wickets": wickets,
            "economy": _safe_div(runs_conc, legal_balls, 6),
            "avg_opposition_total": avg_opp,
            "dot_pct": _safe_div(dots, legal_balls, 100, 1),
            "boundaries_conceded": fours + sixes,
            "worst_conceded": worst,
        })

    return {"seasons": seasons}


async def _team_bowling_by_season_baseline(team, filters, aux):
    """Per-season bowling — SUM-over-tournament cells. worst_conceded
    identity (match_id) gets one tiny live SELECT per season since the
    schema only stores the runs value."""
    from .bucket_baseline_dispatch import baseline_where
    db = get_db()
    where, params = baseline_where(filters, aux, team=team)
    rows = await db.q(
        f"""
        SELECT season,
               SUM(innings_bowled) AS innings_bowled,
               SUM(runs_conceded) AS runs_conceded,
               SUM(legal_balls) AS legal_balls,
               SUM(fours_conceded + sixes_conceded) AS boundaries_conceded,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets,
               COALESCE(MAX(worst_inn_runs), 0) AS worst_inn_runs
        FROM bucketbaselinebowling {where}
        GROUP BY season ORDER BY season
        """,
        params,
    )
    out = []
    for r in rows:
        runs = r["runs_conceded"] or 0
        balls = r["legal_balls"] or 0
        innings = r["innings_bowled"] or 0
        avg_opp = round(runs / innings, 1) if innings else None
        out.append({
            "season": r["season"],
            "innings_bowled": innings,
            "runs_conceded": runs,
            "legal_balls": balls,
            "overs": round(balls / 6, 1) if balls else 0,
            "wickets": r["wickets"] or 0,
            "economy": _safe_div(runs, balls, 6),
            "avg_opposition_total": avg_opp,
            "dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "boundaries_conceded": r["boundaries_conceded"] or 0,
            "worst_conceded": r["worst_inn_runs"],
        })
    return {"seasons": out}


async def _bowling_by_phase_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict[str, dict]:
    """Flat per-phase bowling aggregates keyed by phase name. Dispatches
    to bucket_baseline_phase for precomputed scopes; live otherwise."""
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        return await _bowling_by_phase_aggregates_baseline(team, filters, aux)
    return await _bowling_by_phase_aggregates_live(team, filters, aux)


async def _bowling_by_phase_aggregates_baseline(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict[str, dict]:
    from .bucket_baseline_dispatch import baseline_where, LEAGUE_TEAM_KEY
    db = get_db()
    table_team = team if team else LEAGUE_TEAM_KEY
    bw, bp = baseline_where(filters, aux, team=table_team)
    rows = await db.q(
        f"""
        SELECT phase,
               SUM(legal_balls) AS balls,
               SUM(runs) AS runs,
               SUM(fours) AS fours,
               SUM(sixes) AS sixes,
               SUM(dots) AS dots,
               SUM(wickets) AS wickets
        FROM bucketbaselinephase {bw} AND side='bowling'
        GROUP BY phase
        """,
        bp,
    )
    out: dict[str, dict] = {}
    for r in rows:
        phase = r["phase"]
        if not phase:
            continue
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        out[phase] = {
            "phase": phase,
            "runs_conceded": runs,
            "balls": balls,
            "economy": _safe_div(runs, balls, 6),
            "wickets": r["wickets"] or 0,
            "boundary_pct": _safe_div(fours + sixes, balls, 100, 1),
            "bowl_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours_conceded": fours,
            "sixes_conceded": sixes,
        }
    if team is None:
        out = _phase_dict_per_innings(out, await _innings_count_for_phase(filters, aux, side="fielding"))
    return out


async def _bowling_by_phase_aggregates_live(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict[str, dict]:
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase
        ORDER BY MIN(d.over_number)
        """,
        params,
    )
    w_rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY phase
        """,
        params,
    )
    wicket_map = {r["phase"]: r["wickets"] for r in w_rows}

    out: dict[str, dict] = {}
    for r in rows:
        phase = r["phase"]
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        out[phase] = {
            "phase": phase,
            "runs_conceded": runs,
            "balls": balls,
            "economy": _safe_div(runs, balls, 6),
            "wickets": wicket_map.get(phase, 0),
            "boundary_pct": _safe_div(fours + sixes, balls, 100, 1),
            "bowl_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours_conceded": fours,
            "sixes_conceded": sixes,
        }
    if team is None:
        out = _phase_dict_per_innings(out, await _innings_count_for_phase(filters, aux, side="fielding"))
    return out


async def _bowling_by_inning_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict[int, dict]:
    """Flat per-inning bowling aggregates keyed by innings_number.

    Mirrors `_bowling_by_phase_aggregates_live` but `GROUP BY
    i.innings_number`. Live only. Spec: spec-inning-split.md §3.2.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT
            i.innings_number AS inning,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            SUM(d.runs_total) as runs,
            SUM(CASE WHEN d.runs_batter = 4
                     AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END) as fours,
            SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
            SUM(CASE WHEN d.runs_total = 0
                     AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) as dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.innings_number
        """,
        params,
    )
    w_rows = await db.q(
        f"""
        SELECT i.innings_number AS inning, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY i.innings_number
        """,
        params,
    )
    wicket_map = {r["inning"]: r["wickets"] for r in w_rows}

    out: dict[int, dict] = {}
    for r in rows:
        inning = r["inning"]
        if inning not in (0, 1):
            continue
        balls = r["balls"] or 0
        runs = r["runs"] or 0
        fours = r["fours"] or 0
        sixes = r["sixes"] or 0
        out[inning] = {
            "inning": inning,
            "runs_conceded": runs,
            "balls": balls,
            "economy": _safe_div(runs, balls, 6),
            "wickets": wicket_map.get(inning, 0),
            "boundary_pct": _safe_div(fours + sixes, balls, 100, 1),
            "bowl_dot_pct": _safe_div(r["dots"] or 0, balls, 100, 1),
            "fours_conceded": fours,
            "sixes_conceded": sixes,
        }
    if team is None:
        out = _inning_dict_per_innings(
            out, await _innings_count_per_inning(filters, aux, side="fielding"),
        )
    return out


@router.get("/{team}/bowling/by-inning")
async def team_bowling_by_inning(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-innings_number bowling band — sibling of /by-phase.
    Spec: spec-inning-split.md §3.2.
    """
    t = await _bowling_by_inning_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _bowling_by_inning_aggregates(None, lf, la)

    innings = []
    for inn_no in (0, 1):
        tr = t.get(inn_no)
        if tr is None:
            continue
        sr = s.get(inn_no, {})
        balls = tr["balls"]
        innings.append({
            "inning_no": inn_no,
            "label": "1st innings" if inn_no == 0 else "2nd innings",
            "runs_conceded": tr["runs_conceded"],
            "balls": balls,
            "economy":      wrap_metric(tr["economy"], sr.get("economy"), "economy", sample_size=balls),
            "wickets": tr["wickets"],
            "boundary_pct": wrap_metric(tr["boundary_pct"], sr.get("boundary_pct"), "boundary_pct", sample_size=balls),
            "dot_pct":      wrap_metric(tr["bowl_dot_pct"], sr.get("bowl_dot_pct"), "bowl_dot_pct", sample_size=balls),
            "fours_conceded": tr["fours_conceded"],
            "sixes_conceded": tr["sixes_conceded"],
        })
    return {"innings": innings}


@router.get("/{team}/bowling/by-phase")
async def team_bowling_by_phase(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _bowling_by_phase_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _bowling_by_phase_aggregates(None, lf, la)

    phase_ranges = {
        "powerplay": [1, 6],
        "middle": [7, 15],
        "death": [16, 20],
    }
    phases = []
    for phase in ("powerplay", "middle", "death"):
        tr = t.get(phase)
        if tr is None:
            continue
        sr = s.get(phase, {})
        balls = tr["balls"]
        phases.append({
            "phase": phase,
            "overs_range": phase_ranges.get(phase, []),
            "runs_conceded": tr["runs_conceded"],
            "balls": balls,
            "economy":      wrap_metric(tr["economy"], sr.get("economy"), "economy", sample_size=balls),
            "wickets": tr["wickets"],
            "boundary_pct": wrap_metric(tr["boundary_pct"], sr.get("boundary_pct"), "boundary_pct", sample_size=balls),
            "dot_pct":      wrap_metric(tr["bowl_dot_pct"], sr.get("bowl_dot_pct"), "bowl_dot_pct", sample_size=balls),
            "fours_conceded": tr["fours_conceded"],
            "sixes_conceded": tr["sixes_conceded"],
        })
    return {"phases": phases}


@router.get("/{team}/bowling/top-bowlers")
async def team_top_bowlers(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT d.bowler_id as person_id, p.name,
               SUM(d.runs_total) as runs_conceded,
               COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
               COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.bowler_id
        WHERE {where} AND d.bowler_id IS NOT NULL
        GROUP BY d.bowler_id, p.name
        ORDER BY balls DESC
        LIMIT :lim
        """,
        params,
    )

    # Wickets per bowler (separate query so we filter wicket-kind)
    w_rows = await db.q(
        f"""
        SELECT d.bowler_id as person_id, COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
          AND d.bowler_id IS NOT NULL
        GROUP BY d.bowler_id
        """,
        params,
    )
    w_map = {r["person_id"]: r["wickets"] for r in w_rows}

    # Re-sort by wickets
    top = []
    for r in rows:
        pid = r["person_id"]
        balls = r["balls"] or 0
        runs = r["runs_conceded"] or 0
        wickets = w_map.get(pid, 0)
        top.append({
            "person_id": pid,
            "name": r["name"] or pid,
            "wickets": wickets,
            "runs_conceded": runs,
            "balls": balls,
            "overs": round(balls / 6, 1) if balls else 0,
            "economy": _safe_div(runs, balls, 6),
            "average": _safe_div(runs, wickets),
            "strike_rate": _safe_div(balls, wickets),
            "innings": r["innings"] or 0,
        })
    top.sort(key=lambda r: r["wickets"] or 0, reverse=True)
    return {"top_bowlers": top[:limit]}


@router.get("/{team}/bowling/phase-season-heatmap")
async def team_bowling_phase_season_heatmap(
    team: str, filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Season × phase matrix for bowling — both economy and wickets
    per cell. Cells: {season, phase, economy, wickets, balls}."""
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    rate_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            SUM(d.runs_total) as runs,
            COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) as balls,
            COUNT(DISTINCT i.id) as innings
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, phase
        ORDER BY m.season
        """,
        params,
    )

    wicket_rows = await db.q(
        f"""
        SELECT
            m.season,
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            COUNT(*) as wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where} AND w.kind NOT IN {BOWLER_WICKET_EXCLUDE}
        GROUP BY m.season, phase
        """,
        params,
    )
    wmap = {(r["season"], r["phase"]): r["wickets"] for r in wicket_rows}

    seasons, seen_s = [], set()
    cells = []
    for r in rate_rows:
        s = r["season"]
        if s not in seen_s:
            seen_s.add(s)
            seasons.append(s)
        balls = r["balls"] or 0
        innings = r["innings"] or 0
        wkts = wmap.get((s, r["phase"]), 0)
        cells.append({
            "season": s,
            "phase": r["phase"],
            "economy": round((r["runs"] or 0) * 6 / balls, 2) if balls else None,
            "wickets": wkts,
            "wickets_per_innings": round(wkts / innings, 2) if innings else None,
            "innings": innings,
            "balls": balls,
        })
    seasons.sort()
    return {
        "team": team,
        "seasons": seasons,
        "phases": ["powerplay", "middle", "death"],
        "cells": cells,
    }


async def _fielding_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Flat-shape fielding aggregates."""
    from .bucket_baseline_dispatch import is_precomputed_scope
    if is_precomputed_scope(filters, aux):
        return await _fielding_aggregates_baseline(team, filters, aux)
    return await _fielding_aggregates_live(team, filters, aux)


async def _fielding_aggregates_baseline(team, filters, aux):
    from .bucket_baseline_dispatch import baseline_where, LEAGUE_TEAM_KEY
    db = get_db()
    table_team = team if team else LEAGUE_TEAM_KEY
    where, params = baseline_where(filters, aux, team=table_team)
    rows = await db.q(
        f"""
        SELECT SUM(matches) AS matches,
               SUM(catches) AS catches_only,
               SUM(caught_and_bowled) AS caught_and_bowled,
               SUM(stumpings) AS stumpings,
               SUM(run_outs) AS run_outs
        FROM bucketbaselinefielding {where}
        """,
        params,
    )
    r = rows[0] if rows else {}
    catches_only = r.get("catches_only") or 0
    cnb = r.get("caught_and_bowled") or 0
    stumpings = r.get("stumpings") or 0
    run_outs = r.get("run_outs") or 0
    # Per-team live semantic: response.catches excludes c_a_b (NOT the
    # same as scope/averages/fielding/summary which includes it).
    # matches denominator: live uses COUNT(DISTINCT m.id) over innings
    # the team fielded; baseline.matches stores COUNT(DISTINCT i.id)
    # which can drift when fielding had no credits in a match. Fall
    # back to a tiny live SELECT for matches denominator.
    where_live, params_live = _team_innings_clause(filters, team, side="fielding", aux=aux)
    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM innings i JOIN match m ON m.id = i.match_id
        WHERE {where_live}
        """,
        params_live,
    )
    matches = match_rows[0]["matches"] if match_rows else 0
    out = {
        "matches": matches,
        # Convention 3 (unified 2026-04-26): `catches` includes
        # caught-and-bowled on both endpoints. `caught_and_bowled`
        # is broken out as a sub-count (consumers summing catches +
        # caught_and_bowled would double-count — the contract is
        # "catches" is the inclusive total).
        "catches": catches_only + cnb,
        "caught_and_bowled": cnb,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches_only + cnb + stumpings + run_outs,
        "catches_per_match": _safe_div(catches_only + cnb, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    if team is None:
        # Under inning narrowing each match contributes 1 fielding
        # innings (not 2) — flip both the divisor multiplier and the
        # per_match halving.  Spec: spec-inning-split.md §5.5.
        inning_active = aux is not None and aux.inning is not None
        mult = 1 if inning_active else 2
        return _apply_fielding_per_innings(
            out, matches * mult, halve_per_match=not inning_active,
        )
    return out


async def _fielding_aggregates_live(
    team: str | None, filters: FilterParams, aux: AuxParams,
) -> dict:
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    kind_rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        """,
        params,
    )
    by_kind = {r["kind"]: r["cnt"] for r in kind_rows}
    catches = by_kind.get("caught", 0)
    caught_and_bowled = by_kind.get("caught_and_bowled", 0)
    stumpings = by_kind.get("stumped", 0)
    run_outs = by_kind.get("run_out", 0)

    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) as matches
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    matches = match_rows[0]["matches"] if match_rows else 0

    out = {
        "matches": matches,
        # Convention 3 (unified 2026-04-26): `catches` includes c_a_b.
        "catches": catches + caught_and_bowled,
        "caught_and_bowled": caught_and_bowled,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + caught_and_bowled + stumpings + run_outs,
        "catches_per_match": _safe_div(catches + caught_and_bowled, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }
    if team is None:
        inning_active = aux is not None and aux.inning is not None
        mult = 1 if inning_active else 2
        return _apply_fielding_per_innings(
            out, matches * mult, halve_per_match=not inning_active,
        )
    return out


async def _fielding_by_inning_aggregates(
    team: str | None,
    filters: FilterParams,
    aux: AuxParams,
) -> dict[int, dict]:
    """Flat per-inning fielding aggregates keyed by innings_number.

    Mirrors `_fielding_aggregates_live` but `GROUP BY i.innings_number`.
    No /by-phase sibling for fielding (phase doesn't apply to fielding
    credits) — the per-inning split is the first banded fielding view.
    Spec: spec-inning-split.md §3.2.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    kind_rows = await db.q(
        f"""
        SELECT i.innings_number AS inning, fc.kind AS kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.innings_number, fc.kind
        """,
        params,
    )
    by_inning_kind: dict[int, dict[str, int]] = {0: {}, 1: {}}
    for r in kind_rows:
        if r["inning"] in (0, 1):
            by_inning_kind[r["inning"]][r["kind"]] = r["cnt"]

    match_rows = await db.q(
        f"""
        SELECT i.innings_number AS inning, COUNT(DISTINCT m.id) as matches
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.innings_number
        """,
        params,
    )
    matches_per_inning = {r["inning"]: r["matches"] for r in match_rows if r["inning"] in (0, 1)}

    out: dict[int, dict] = {}
    for inning, by_kind in by_inning_kind.items():
        if inning not in matches_per_inning and not by_kind:
            continue
        catches = by_kind.get("caught", 0)
        cnb = by_kind.get("caught_and_bowled", 0)
        stumpings = by_kind.get("stumped", 0)
        run_outs = by_kind.get("run_out", 0)
        matches = matches_per_inning.get(inning, 0)
        out[inning] = {
            "inning": inning,
            "matches": matches,
            "catches": catches + cnb,
            "caught_and_bowled": cnb,
            "stumpings": stumpings,
            "run_outs": run_outs,
            "total_dismissals_contributed": catches + cnb + stumpings + run_outs,
            "catches_per_match": _safe_div(catches + cnb, matches, 1, 2),
            "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
            "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
        }
    if team is None:
        # Each match contributes 1 fielding innings to the inning-X
        # scope (not 2). _apply_fielding_per_innings with halve=False
        # honours that. Spec §5.5.
        for inning, row in out.items():
            matches = matches_per_inning.get(inning, 0)
            _apply_fielding_per_innings(row, matches * 1, halve_per_match=False)
    return out


@router.get("/{team}/fielding/by-inning")
async def team_fielding_by_inning(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-innings_number fielding band — no /by-phase sibling (phase
    doesn't apply to fielding). Spec: spec-inning-split.md §3.2.
    """
    t = await _fielding_by_inning_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _fielding_by_inning_aggregates(None, lf, la)

    innings = []
    for inn_no in (0, 1):
        tr = t.get(inn_no)
        if tr is None:
            continue
        sr = s.get(inn_no, {})
        matches = tr["matches"]
        innings.append({
            "inning_no": inn_no,
            "label": "1st innings" if inn_no == 0 else "2nd innings",
            "matches": matches,
            "catches": tr["catches"],
            "caught_and_bowled": tr["caught_and_bowled"],
            "stumpings": tr["stumpings"],
            "run_outs": tr["run_outs"],
            "total_dismissals_contributed": tr["total_dismissals_contributed"],
            "catches_per_match":  wrap_metric(tr["catches_per_match"], sr.get("catches_per_match"), "catches_per_match", sample_size=matches),
            "stumpings_per_match": wrap_metric(tr["stumpings_per_match"], sr.get("stumpings_per_match"), "stumpings_per_match", sample_size=matches),
            "run_outs_per_match": wrap_metric(tr["run_outs_per_match"], sr.get("run_outs_per_match"), "run_outs_per_match", sample_size=matches),
        })
    return {"innings": innings}


@router.get("/{team}/fielding/summary")
async def team_fielding_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _fielding_aggregates(team, filters, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _fielding_aggregates(None, lf, la)
    matches = t.get("matches") or 0
    return {
        "team": team,
        "matches":             wrap_metric(t["matches"], s["matches"], "matches", sample_size=matches),
        "catches":             wrap_metric(t["catches"], s["catches"], "catches", sample_size=matches),
        "caught_and_bowled":   wrap_metric(t["caught_and_bowled"], s["caught_and_bowled"], "caught_and_bowled", sample_size=matches),
        "stumpings":           wrap_metric(t["stumpings"], s["stumpings"], "stumpings", sample_size=matches),
        "run_outs":            wrap_metric(t["run_outs"], s["run_outs"], "run_outs", sample_size=matches),
        "total_dismissals_contributed": wrap_metric(t["total_dismissals_contributed"], s["total_dismissals_contributed"], "total_dismissals_contributed", sample_size=matches),
        # Per-match rates: `s` is already halved at source by
        # `_apply_fielding_per_innings(out, matches*2)` when called with
        # team=None (spec-avg-column-per-innings.md Commit 2).
        "catches_per_match":   wrap_metric(t["catches_per_match"], s["catches_per_match"], "catches_per_match", sample_size=matches),
        "stumpings_per_match": wrap_metric(t["stumpings_per_match"], s["stumpings_per_match"], "stumpings_per_match", sample_size=matches),
        "run_outs_per_match":  wrap_metric(t["run_outs_per_match"], s["run_outs_per_match"], "run_outs_per_match", sample_size=matches),
    }


# ============================================================
# Team fielding — distribution dossier (spec §16.4).
# Per-innings observation row of the OPP's batting innings; counts
# fielding events credited to ANY of the team's matchplayers in
# that match. Three sibling count blocks (catches / run_outs /
# stumpings) + four scope-anchored form windows. Reuses
# _team_innings_clause(side='fielding') for the side-neutral
# filter scope.
#
# Catches block: 4 milestones (p_eq_0, p_geq_3/5/7), no ladder.
# Run-outs / Stumpings: 3-simple partition (p_eq_0, p_eq_1,
# p_geq_2). Stumpings is ALWAYS shipped (unlike player-fielder
# §13 where the block is null for non-keepers).
# ============================================================


async def _innings_master_sample_team_fielding(
    team: str, filters: FilterParams, aux: AuxParams,
) -> list[dict]:
    """Per-innings observation rows of the OPPONENT's batting
    innings; counts fielding events credited to any of the team's
    matchplayers (subs handled separately as `substitute_catches`).
    Spec §16.4.1.

    Scalar-subquery pattern per innings — keeps the SQL parallel
    structure between catches / run_outs / stumpings / sub_catches
    / wickets_total without a multi-CTE assembly.
    """
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)
    rows = await db.q(
        f"""
        SELECT
            i.id AS innings_id,
            i.match_id,
            i.innings_number,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) AS date,
            (SELECT COUNT(*) FROM fieldingcredit fc
             JOIN delivery d ON d.id = fc.delivery_id
             WHERE d.innings_id = i.id
               -- Convention 3 (codified 2026-04-26 in /summary): catches
               -- is the inclusive total. caught_and_bowled is a sub-count
               -- of catches, broken out separately on /summary but rolled
               -- into the totals on every endpoint that surfaces catches.
               AND fc.kind IN ('caught', 'caught_and_bowled')
               AND COALESCE(fc.is_substitute, 0) = 0
               AND fc.fielder_id IN
                 (SELECT mp.person_id FROM matchplayer mp
                  WHERE mp.match_id = i.match_id AND mp.team = :team)
            ) AS catches,
            (SELECT COUNT(*) FROM fieldingcredit fc
             JOIN delivery d ON d.id = fc.delivery_id
             WHERE d.innings_id = i.id
               AND fc.kind = 'run_out'
               AND COALESCE(fc.is_substitute, 0) = 0
               AND fc.fielder_id IN
                 (SELECT mp.person_id FROM matchplayer mp
                  WHERE mp.match_id = i.match_id AND mp.team = :team)
            ) AS run_outs,
            (SELECT COUNT(*) FROM fieldingcredit fc
             JOIN delivery d ON d.id = fc.delivery_id
             WHERE d.innings_id = i.id
               AND fc.kind = 'stumped'
               AND fc.fielder_id IN
                 (SELECT mp.person_id FROM matchplayer mp
                  WHERE mp.match_id = i.match_id AND mp.team = :team)
            ) AS stumpings,
            (SELECT COUNT(*) FROM fieldingcredit fc
             JOIN delivery d ON d.id = fc.delivery_id
             WHERE d.innings_id = i.id
               AND fc.kind = 'caught'
               AND fc.is_substitute = 1
            ) AS substitute_catches,
            (SELECT COUNT(*) FROM wicket w
             JOIN delivery d ON d.id = w.delivery_id
             WHERE d.innings_id = i.id
            ) AS wickets_total
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        ORDER BY date ASC, i.innings_number ASC
        """,
        params,
    )
    return [
        {
            "innings_id": r["innings_id"],
            "match_id": r["match_id"],
            "innings_number": r["innings_number"],
            "date": r["date"],
            "catches": r["catches"] or 0,
            "run_outs": r["run_outs"] or 0,
            "stumpings": r["stumpings"] or 0,
            "substitute_catches": r["substitute_catches"] or 0,
            "wickets_total": r["wickets_total"] or 0,
        }
        for r in rows
    ]


def _catches_block_team_fielding(observations: list[dict]) -> dict:
    """`catches` block — 4 simples (p_eq_0, p_geq_3/5/7), no ladder
    (the simples already span the meaningful range; conditioning
    on ≥3 would shrink denoms without adding signal). Spec §16.4.2."""
    n = len(observations)
    vals = [o["catches"] for o in observations]

    if n == 0:
        keys = ["p_eq_0", "p_geq_3", "p_geq_5", "p_geq_7"]
        return {
            "total": 0,
            "mean_per_innings": None,
            "median": None,
            "variance": None,
            "std": None,
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(vals)
    mean = total / n
    median = statistics.median(vals)
    variance = statistics.variance(vals) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_eq(v: int) -> int:
        return sum(1 for x in vals if x == v)

    def _count_geq(v: int) -> int:
        return sum(1 for x in vals if x >= v)

    return {
        "total": total,
        "mean_per_innings": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "milestones": {
            "p_eq_0":  prob_record(_count_eq(0), n),
            "p_geq_3": prob_record(_count_geq(3), n),
            "p_geq_5": prob_record(_count_geq(5), n),
            "p_geq_7": prob_record(_count_geq(7), n),
        },
    }


def _three_simple_block_team_fielding(
    observations: list[dict], key: str,
) -> dict:
    """Sibling 3-simple count block — `run_outs` / `stumpings`.
    Three simples (p_eq_0 / p_eq_1 / p_geq_2) that partition the
    sample exactly (sum to 1). Spec §16.4.2."""
    n = len(observations)
    vals = [o[key] for o in observations]

    if n == 0:
        keys = ["p_eq_0", "p_eq_1", "p_geq_2"]
        return {
            "total": 0,
            "mean_per_innings": None,
            "median": None,
            "variance": None,
            "std": None,
            "milestones": {k: prob_record(0, 0) for k in keys},
        }

    total = sum(vals)
    mean = total / n
    median = statistics.median(vals)
    variance = statistics.variance(vals) if n >= 2 else 0.0
    std = variance ** 0.5

    def _count_eq(v: int) -> int:
        return sum(1 for x in vals if x == v)

    def _count_geq(v: int) -> int:
        return sum(1 for x in vals if x >= v)

    return {
        "total": total,
        "mean_per_innings": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "milestones": {
            "p_eq_0":  prob_record(_count_eq(0), n),
            "p_eq_1":  prob_record(_count_eq(1), n),
            "p_geq_2": prob_record(_count_geq(2), n),
        },
    }


def _distribution_dossier_team_fielding(observations: list[dict]) -> dict:
    """Pure aggregate. Three count blocks + top-level scalars.
    Stumpings block is ALWAYS shipped (every senior team has had a
    keeper at some point); zero-event scopes ship with all-zero
    chips and small-n CIs rather than null. Spec §16.4."""
    n = len(observations)
    return {
        "n_innings_fielded": n,
        "wickets_total": sum(o["wickets_total"] for o in observations),
        "substitute_catches": sum(o["substitute_catches"] for o in observations),
        "observations": observations,
        "catches": _catches_block_team_fielding(observations),
        "run_outs": _three_simple_block_team_fielding(observations, "run_outs"),
        "stumpings": _three_simple_block_team_fielding(observations, "stumpings"),
    }


def _form_windows_team_fielding(
    observations: list[dict], today: date,
) -> dict:
    """Slice the date-asc observation list into four form windows,
    run the dossier on each, emit a 12-entry delta block (4 windows
    × 3 metrics: catches_mean, run_outs_mean, stumpings_mean minus
    lifetime). Spec §16.4.4."""
    anchor = scope_anchor(observations, today)
    last_10 = observations[-10:]
    cutoff_60d = (anchor - timedelta(days=60)).isoformat()
    cutoff_6mo = (anchor - timedelta(days=180)).isoformat()
    cutoff_1yr = (anchor - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    lifetime_doss = _distribution_dossier_team_fielding(observations)
    last_10_doss = _distribution_dossier_team_fielding(last_10)
    last_60d_doss = _distribution_dossier_team_fielding(last_60d)
    last_6mo_doss = _distribution_dossier_team_fielding(last_6mo)
    last_1yr_doss = _distribution_dossier_team_fielding(last_1yr)

    def _delta(window_doss: dict, key: str) -> Optional[float]:
        wv = window_doss[key]["mean_per_innings"]
        lv = lifetime_doss[key]["mean_per_innings"]
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    delta = {}
    for window_name, window_doss in (
        ("last_10", last_10_doss),
        ("last_60d", last_60d_doss),
        ("last_6mo", last_6mo_doss),
        ("last_1yr", last_1yr_doss),
    ):
        delta[f"{window_name}_catches_mean_minus_lifetime"] = _delta(window_doss, "catches")
        delta[f"{window_name}_run_outs_mean_minus_lifetime"] = _delta(window_doss, "run_outs")
        delta[f"{window_name}_stumpings_mean_minus_lifetime"] = _delta(window_doss, "stumpings")

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": delta,
    }


@router.get("/{team}/fielding/distribution")
async def team_fielding_distribution(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    as_of_date: Optional[str] = Query(
        None,
        description=(
            "ISO date (YYYY-MM-DD) to anchor the calendar form windows"
            " (last_60d / last_6mo / last_1yr). Defaults to today;"
            " pin for deterministic regression tests."
        ),
    ),
):
    """Per-innings team-fielding distribution dossier.

    Three sibling count blocks under one master sample —
    `catches` (4 simples: p_eq_0 + p_geq_3/5/7), `run_outs` (3-
    simple partition), `stumpings` (3-simple partition; ALWAYS
    shipped at team grain) — plus form windows, top-level
    scalars (`wickets_total`, `substitute_catches`), and scope-
    derived suggested-splits navigation hints.

    Master sample is the OPPONENT's batting innings under the
    active filter scope. Catches/run_outs/stumpings count fielding
    events credited to any of the team's matchplayers for that
    match (substitute fielders are tracked separately via the
    `substitute_catches` scalar — they're not on the team sheet).
    `wickets_total` is the all-kinds wicket-fallen count for the
    fielder-ratio tooltip ("X catches of Y wickets").

    Every probability field ships as `{value, num, denom, ci_low,
    ci_high}` with a Wilson 95% CI.

    `FilterParams.filter_team` is IGNORED — the team path-param
    dominates. `FilterParams.filter_opponent` works as expected.

    Spec: internal_docs/spec-distribution-stats.md §16.4.
    """
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations = await _innings_master_sample_team_fielding(team, filters, aux)
    lifetime = _distribution_dossier_team_fielding(observations)
    form = _form_windows_team_fielding(observations, today)

    obs_dates = [o["date"] for o in observations if o.get("date")]
    lifetime["last_match_date"] = max(obs_dates) if obs_dates else None

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "team": team,
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }


@router.get("/{team}/fielding/by-season")
async def team_fielding_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    from .bucket_baseline_dispatch import is_precomputed_scope, baseline_where
    if is_precomputed_scope(filters, aux):
        db = get_db()
        bw, bp = baseline_where(filters, aux, team=team)
        rows = await db.q(
            f"""
            SELECT season,
                   SUM(catches) AS catches,
                   SUM(caught_and_bowled) AS caught_and_bowled,
                   SUM(stumpings) AS stumpings,
                   SUM(run_outs) AS run_outs
            FROM bucketbaselinefielding {bw}
            GROUP BY season
            HAVING SUM(catches + caught_and_bowled + stumpings + run_outs) > 0
            ORDER BY season
            """,
            bp,
        )
        # Matches per season — fielding-side requires the live count.
        match_rows = await db.q(
            """
            SELECT m.season, COUNT(DISTINCT m.id) as matches
            FROM innings i JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0
              AND i.team != :team
              AND (m.team1 = :team OR m.team2 = :team)
            GROUP BY m.season
            """,
            {"team": team},
        )
        match_map = {r["season"]: r["matches"] for r in match_rows}
        seasons = []
        for r in rows:
            s = r["season"]
            catches = r["catches"] or 0
            cnb = r["caught_and_bowled"] or 0
            stumpings = r["stumpings"] or 0
            run_outs = r["run_outs"] or 0
            matches = match_map.get(s, 0)
            seasons.append({
                "season": s,
                # Convention 3: catches includes c_a_b on both endpoints.
                "catches": catches + cnb,
                "caught_and_bowled": cnb,
                "stumpings": stumpings,
                "run_outs": run_outs,
                "matches": matches,
                "catches_per_match": _safe_div(catches + cnb, matches, 1, 2),
                "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
                "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
                "total_dismissals_contributed": catches + cnb + stumpings + run_outs,
            })
        return {"seasons": seasons}

    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)

    rows = await db.q(
        f"""
        SELECT m.season, fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY m.season, fc.kind
        ORDER BY m.season
        """,
        params,
    )

    # Matches per season (for per-match rates)
    match_rows = await db.q(
        """
        SELECT m.season, COUNT(DISTINCT m.id) as matches
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0
          AND i.team != :team
          AND (m.team1 = :team OR m.team2 = :team)
        GROUP BY m.season
        """,
        {"team": team},
    )
    match_map = {r["season"]: r["matches"] for r in match_rows}

    by_season: dict[str, dict] = {}
    for r in rows:
        s = r["season"]
        by_season.setdefault(s, {
            "season": s, "catches": 0, "caught_and_bowled": 0,
            "stumpings": 0, "run_outs": 0,
        })
        kind = r["kind"]
        cnt = r["cnt"]
        if kind == "caught":
            by_season[s]["catches"] = cnt
        elif kind == "caught_and_bowled":
            by_season[s]["caught_and_bowled"] = cnt
        elif kind == "stumped":
            by_season[s]["stumpings"] = cnt
        elif kind == "run_out":
            by_season[s]["run_outs"] = cnt

    seasons = []
    for s in sorted(by_season.keys()):
        row = by_season[s]
        matches = match_map.get(s, 0)
        total_catches = row["catches"] + row["caught_and_bowled"]
        seasons.append({
            "season": row["season"],
            # Convention 3: catches includes c_a_b on both endpoints.
            "catches": total_catches,
            "caught_and_bowled": row["caught_and_bowled"],
            "stumpings": row["stumpings"],
            "run_outs": row["run_outs"],
            "matches": matches,
            "catches_per_match": _safe_div(total_catches, matches, 1, 2),
            "stumpings_per_match": _safe_div(row["stumpings"], matches, 1, 2),
            "run_outs_per_match": _safe_div(row["run_outs"], matches, 1, 2),
            "total_dismissals_contributed": (
                row["catches"] + row["caught_and_bowled"]
                + row["stumpings"] + row["run_outs"]
            ),
        })
    return {"seasons": seasons}


@router.get("/{team}/fielding/top-fielders")
async def team_top_fielders(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(5, ge=1, le=50),
):
    db = get_db()
    where, params = _team_innings_clause(filters, team, side="fielding", aux=aux)
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT fc.fielder_id as person_id, p.name, fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = fc.fielder_id
        WHERE {where} AND fc.fielder_id IS NOT NULL
        GROUP BY fc.fielder_id, p.name, fc.kind
        """,
        params,
    )

    by_player: dict[str, dict] = {}
    for r in rows:
        pid = r["person_id"]
        if pid not in by_player:
            by_player[pid] = {
                "person_id": pid,
                "name": r["name"] or pid,
                "catches": 0, "caught_and_bowled": 0,
                "stumpings": 0, "run_outs": 0,
            }
        kind = r["kind"]
        if kind == "caught":
            by_player[pid]["catches"] = r["cnt"]
        elif kind == "caught_and_bowled":
            by_player[pid]["caught_and_bowled"] = r["cnt"]
        elif kind == "stumped":
            by_player[pid]["stumpings"] = r["cnt"]
        elif kind == "run_out":
            by_player[pid]["run_outs"] = r["cnt"]

    players = list(by_player.values())
    for p in players:
        p["total"] = (
            p["catches"] + p["caught_and_bowled"]
            + p["stumpings"] + p["run_outs"]
        )
    players.sort(key=lambda p: p["total"], reverse=True)
    return {"top_fielders": players[:limit]}


def _partnership_filter(
    filters: FilterParams, team: str | None, side: str,
    aux: AuxParams | None = None,
):
    """Build WHERE clause for partnership table queries.

    side='batting' → partnerships when :team batted (i.team = :team)
    side='bowling' → partnerships against :team's bowling
                     (i.team != :team AND :team in match)

    When `team` is None, the team-specific clauses are dropped entirely
    and the result is a pure scope filter — used by `/scope/averages/*`
    endpoints. `side` is irrelevant in that case (every partnership
    counts toward the league average regardless of which side faced it).
    """
    filters.team = None
    where, params = filters.build(has_innings_join=True, aux=aux)
    parts: list[str] = []
    if team is not None:
        params["team"] = team
        if side == "batting":
            parts.append("i.team = :team")
        else:
            parts.extend(["i.team != :team", "(m.team1 = :team OR m.team2 = :team)"])
    if where:
        parts.append(where)
    # Match-level aux filters (result / toss_outcome) need a path team
    # to evaluate; only apply on team-detail (mirror of
    # _team_innings_clause). Spec: spec-splits-mosaic.md §1.2.
    if team is not None:
        res_clause, res_params = _result_match_filter(team, aux)
        if res_clause:
            parts.append(res_clause)
            params.update(res_params)
        toss_clause, toss_params = _toss_outcome_match_filter(team, aux)
        if toss_clause:
            parts.append(toss_clause)
            params.update(toss_params)
    if team is None:
        st_clause, st_params = _scope_to_team_clause(aux, filters)
        if st_clause:
            parts.append(st_clause)
            params.update(st_params)
    if not parts:
        parts.append("1=1")
    return " AND ".join(parts), params


def _validate_side(side: str) -> str:
    return side if side in ("batting", "bowling") else "batting"


async def _partnerships_by_wicket_aggregates(
    team: str | None,
    filters: FilterParams,
    side: str,
    aux: AuxParams,
) -> dict[int, dict]:
    """Flat per-wicket partnership aggregates keyed by wicket_number."""
    from .bucket_baseline_dispatch import is_precomputed_scope, baseline_where, LEAGUE_TEAM_KEY
    if is_precomputed_scope(filters, aux) and side == "batting":
        # Baseline path — only valid for side='batting' (the team batting
        # in the partnership). side='bowling' uses an opposition-side
        # aggregate not in the schema.
        db = get_db()
        table_team = team if team else LEAGUE_TEAM_KEY
        bw, bp = baseline_where(filters, aux, team=table_team)
        bl_rows = await db.q(
            f"""
            SELECT wicket_number,
                   SUM(n) AS n,
                   ROUND(SUM(total_runs) * 1.0 / NULLIF(SUM(n), 0), 1) AS avg_runs,
                   ROUND(SUM(total_balls) * 1.0 / NULLIF(SUM(n), 0), 1) AS avg_balls,
                   COALESCE(MAX(best_runs), 0) AS best_runs
            FROM bucketbaselinepartnership {bw}
            GROUP BY wicket_number ORDER BY wicket_number
            """,
            bp,
        )
        out = {
            r["wicket_number"]: {
                "wicket_number": r["wicket_number"],
                "n": r["n"] or 0,
                "avg_runs": r["avg_runs"],
                "avg_balls": r["avg_balls"],
                "best_runs": r["best_runs"],
            }
            for r in bl_rows
        }
        if team is None:
            innings_batted = await _innings_count_for_phase(filters, aux, side="batting")
            for row in out.values():
                if innings_batted:
                    row["n"] = round((row["n"] or 0) / innings_batted, 2)
        return out

    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)
    rows = await db.q(
        f"""
        SELECT p.wicket_number,
               COUNT(*) as n,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               ROUND(AVG(p.partnership_balls), 1) as avg_balls,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY p.wicket_number
        ORDER BY p.wicket_number
        """,
        params,
    )
    out = {r["wicket_number"]: dict(r) for r in rows}
    if team is None:
        # `dict(r)` to make rows mutable; sqlite Row is read-only.
        innings_batted = await _innings_count_for_phase(filters, aux, side="batting")
        for row in out.values():
            if innings_batted:
                row["n"] = round((row["n"] or 0) / innings_batted, 2)
    return out


async def _partnerships_by_inning_aggregates(
    team: str | None,
    filters: FilterParams,
    side: str,
    aux: AuxParams,
) -> dict[int, dict]:
    """Flat per-inning partnership aggregates keyed by innings_number.

    Mirrors `_partnerships_by_wicket_aggregates` but groups by
    i.innings_number instead of p.wicket_number. Live only — bucket
    table has wicket_number but no innings_number dimension.
    Spec: spec-inning-split.md §3.2.
    """
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)

    rows = await db.q(
        f"""
        SELECT i.innings_number AS inning,
               COUNT(*) AS n,
               ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
               ROUND(AVG(p.partnership_balls), 1) AS avg_balls,
               MAX(p.partnership_runs) AS best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY i.innings_number
        """,
        params,
    )
    out: dict[int, dict] = {}
    for r in rows:
        inning = r["inning"]
        if inning not in (0, 1):
            continue
        out[inning] = {
            "inning": inning,
            "n": r["n"] or 0,
            "avg_runs": r["avg_runs"],
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"] or 0,
        }
    if team is None:
        # League-side per-innings transform: divide n by innings count
        # for that inning_number. avg_runs / avg_balls / best_runs are
        # identity-bearing — leave alone.
        counts = await _innings_count_per_inning(filters, aux, side="batting")
        for inning, row in out.items():
            div = counts.get(inning, 0)
            if div:
                row["n"] = round((row["n"] or 0) / div, 2)
    return out


@router.get("/{team}/partnerships/by-inning")
async def team_partnerships_by_inning(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
):
    """Per-innings_number partnership band — sibling of /by-wicket.
    Spec: spec-inning-split.md §3.2.
    """
    side = _validate_side(side)
    t = await _partnerships_by_inning_aggregates(team, filters, side, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _partnerships_by_inning_aggregates(None, lf, side, la)

    innings = []
    for inn_no in (0, 1):
        tr = t.get(inn_no)
        if tr is None:
            continue
        sr = s.get(inn_no, {})
        innings.append({
            "inning_no": inn_no,
            "label": "1st innings" if inn_no == 0 else "2nd innings",
            "n":         wrap_metric(tr["n"], sr.get("n"), "total", sample_size=tr["n"]),
            "avg_runs":  wrap_metric(tr["avg_runs"], sr.get("avg_runs"), "avg_runs", sample_size=tr["n"]),
            "avg_balls": tr["avg_balls"],
            "best_runs": tr["best_runs"],
        })
    return {"team": team, "side": side, "innings": innings}


@router.get("/{team}/partnerships/by-wicket")
async def team_partnerships_by_wicket(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)

    t = await _partnerships_by_wicket_aggregates(team, filters, side, aux)
    lf, la = _league_aux(team, aux, filters)
    s = await _partnerships_by_wicket_aggregates(None, lf, side, la)

    # Best partnership detail per wicket (identity-bearing — only
    # fetched for the team side; the league's record at each wicket
    # is in /scope/averages/partnerships/by-wicket).
    by_wicket = []
    for wn in sorted(t.keys()):
        r = t[wn]
        sr = s.get(wn, {})
        best_rows = await db.q(
            f"""
            SELECT p.id as partnership_id, p.partnership_runs as runs,
                   p.partnership_balls as balls,
                   p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                   p.batter1_runs, p.batter1_balls, p.batter2_runs, p.batter2_balls,
                   m.id as match_id, m.season, m.event_name as tournament,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
                   CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as opponent
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.wicket_number = :wn
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.partnership_runs = :best
            ORDER BY p.id
            LIMIT 1
            """,
            {**params, "wn": wn, "best": r["best_runs"]},
        )
        best = best_rows[0] if best_rows else None
        by_wicket.append({
            "wicket_number": wn,
            "n":         wrap_metric(r["n"], sr.get("n"), "total", sample_size=r["n"]),
            "avg_runs":  wrap_metric(r["avg_runs"], sr.get("avg_runs"), "avg_runs", sample_size=r["n"]),
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"],
            "best_partnership": (
                {
                    "partnership_id": best["partnership_id"],
                    "match_id": best["match_id"],
                    "date": best["date"],
                    "season": best["season"],
                    "tournament": best["tournament"],
                    "opponent": best["opponent"],
                    "runs": best["runs"],
                    "balls": best["balls"],
                    "batter1": {
                        "person_id": best["batter1_id"],
                        "name": best["batter1_name"],
                        "runs": best["batter1_runs"],
                        "balls": best["batter1_balls"],
                    },
                    "batter2": {
                        "person_id": best["batter2_id"],
                        "name": best["batter2_name"],
                        "runs": best["batter2_runs"],
                        "balls": best["batter2_balls"],
                    },
                }
                if best else None
            ),
        })

    return {"team": team, "side": side, "by_wicket": by_wicket}


@router.get("/{team}/partnerships/best-pairs")
async def team_partnerships_best_pairs(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
    min_n: int = Query(2, ge=1, le=20),
    top_n: int = Query(3, ge=1, le=10),
):
    """Per-wicket "most prolific pairs" — top-N pairs ranked by **total
    runs together** at that wicket. Captures both volume (how many
    partnerships) and quality (avg per partnership) — pure-average
    ranking gave a 5-game purple patch the same weight as a multi-year
    workhorse pair, missing the actual bread-and-butter combinations.

    For each (batterA, batterB) pair (canonicalized so order doesn't
    matter) at each wicket number, we compute:
      n           — number of partnerships together
      avg_runs    — average runs per partnership
      total_runs  — n × avg, the ranking metric
      best_runs   — single biggest partnership

    Returns top `top_n` pairs per wicket, requiring at least `min_n`
    partnerships together to qualify.

    Different from the by-wicket "best_partnership" which shows a
    single one-off blockbuster. For side='bowling', "pair" = the
    opposition pair that did best against us at that wicket.
    """
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)
    params["min_n"] = min_n

    # Canonicalize pair (smaller id first) so AB+CD and CD+AB count as
    # one pair regardless of who arrived first.
    rows = await db.q(
        f"""
        SELECT
            wicket_number,
            CASE WHEN batter1_id < batter2_id THEN batter1_id ELSE batter2_id END as p1_id,
            CASE WHEN batter1_id < batter2_id THEN batter2_id ELSE batter1_id END as p2_id,
            COUNT(*) as n,
            ROUND(AVG(partnership_runs), 1) as avg_runs,
            ROUND(AVG(partnership_balls), 1) as avg_balls,
            MAX(partnership_runs) as best_runs,
            SUM(partnership_runs) as total_runs
        FROM (
            SELECT p.* FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.wicket_number IS NOT NULL
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.batter1_id IS NOT NULL
              AND p.batter2_id IS NOT NULL
        )
        GROUP BY wicket_number, p1_id, p2_id
        HAVING COUNT(*) >= :min_n
        ORDER BY wicket_number, total_runs DESC, avg_runs DESC
        """,
        params,
    )

    # Bucket top-N rows per wicket
    pairs_per_wicket: dict[int, list[dict]] = {}
    for r in rows:
        wn = r["wicket_number"]
        bucket = pairs_per_wicket.setdefault(wn, [])
        if len(bucket) < top_n:
            bucket.append(r)

    # Resolve names in one shot
    person_ids: set[str] = set()
    for bucket in pairs_per_wicket.values():
        for r in bucket:
            person_ids.add(r["p1_id"])
            person_ids.add(r["p2_id"])
    name_map: dict[str, str] = {}
    if person_ids:
        id_list = ",".join(f"'{pid}'" for pid in person_ids)
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({id_list})"
        )
        name_map = {r["id"]: r["name"] for r in name_rows}

    by_wicket = []
    for wn in sorted(pairs_per_wicket.keys()):
        pairs = []
        for rank, r in enumerate(pairs_per_wicket[wn], start=1):
            pairs.append({
                "rank": rank,
                "batter1": {"person_id": r["p1_id"], "name": name_map.get(r["p1_id"], r["p1_id"])},
                "batter2": {"person_id": r["p2_id"], "name": name_map.get(r["p2_id"], r["p2_id"])},
                "n": r["n"],
                "avg_runs": r["avg_runs"],
                "avg_balls": r["avg_balls"],
                "best_runs": r["best_runs"],
                "total_runs": r["total_runs"],
            })
        by_wicket.append({
            "wicket_number": wn,
            "pairs": pairs,
        })

    return {
        "team": team,
        "side": side,
        "min_n": min_n,
        "top_n": top_n,
        "by_wicket": by_wicket,
    }


@router.get("/{team}/partnerships/heatmap")
async def team_partnerships_heatmap(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)

    rows = await db.q(
        f"""
        SELECT m.season, p.wicket_number,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               COUNT(*) as n
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season, p.wicket_number
        ORDER BY m.season, p.wicket_number
        """,
        params,
    )

    seasons: list[str] = []
    seen_seasons = set()
    wickets: list[int] = []
    seen_wickets = set()
    cells = []
    for r in rows:
        s = r["season"]
        wn = r["wicket_number"]
        if s not in seen_seasons:
            seen_seasons.add(s)
            seasons.append(s)
        if wn not in seen_wickets:
            seen_wickets.add(wn)
            wickets.append(wn)
        cells.append({
            "season": s,
            "wicket_number": wn,
            "avg_runs": r["avg_runs"],
            "n": r["n"],
        })
    seasons.sort()
    wickets.sort()

    return {
        "team": team,
        "side": side,
        "seasons": seasons,
        "wickets": wickets,
        "cells": cells,
    }


@router.get("/{team}/partnerships/top")
async def team_partnerships_top(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
    limit: int = Query(10, ge=1, le=50),
):
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT p.id as partnership_id,
               p.partnership_runs as runs, p.partnership_balls as balls,
               p.wicket_number, p.unbroken, p.ended_by_kind,
               p.batter1_id, p.batter1_name,
               p.batter2_id, p.batter2_name,
               p.batter1_runs, p.batter1_balls,
               p.batter2_runs, p.batter2_balls,
               m.id as match_id, m.season, m.event_name as tournament,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date,
               CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END as opponent
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        ORDER BY p.partnership_runs DESC, p.id
        LIMIT :lim
        """,
        params,
    )

    partnerships = []
    for r in rows:
        partnerships.append({
            "partnership_id": r["partnership_id"],
            "match_id": r["match_id"],
            "date": r["date"],
            "season": r["season"],
            "tournament": r["tournament"],
            "opponent": r["opponent"],
            "wicket_number": r["wicket_number"],
            "runs": r["runs"],
            "balls": r["balls"],
            "unbroken": bool(r["unbroken"]),
            "ended_by_kind": r["ended_by_kind"],
            "batter1": {
                "person_id": r["batter1_id"],
                "name": r["batter1_name"],
                "runs": r["batter1_runs"],
                "balls": r["batter1_balls"],
            },
            "batter2": {
                "person_id": r["batter2_id"],
                "name": r["batter2_name"],
                "runs": r["batter2_runs"],
                "balls": r["batter2_balls"],
            },
        })
    return {"team": team, "side": side, "partnerships": partnerships}


@router.get("/{team}/partnerships/summary")
async def team_partnerships_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
):
    """Scope-aware partnership aggregates: total count, 50+ / 100+
    counts, highest single partnership, and the top pair by total
    runs together. Powers the Compare tab on the Teams page — the
    granular partnership endpoints return too much data for a 1-row
    summary comparison.

    Filters out retired-hurt / retired-not-out terminations to match
    the other partnership endpoints' convention.
    """
    side = _validate_side(side)
    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)

    # Aggregates in a single scan.
    agg_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN p.partnership_runs >= 50  THEN 1 ELSE 0 END) as count_50_plus,
            SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
            MAX(p.partnership_runs) as highest_runs,
            ROUND(AVG(p.partnership_runs * 1.0), 1) as avg_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        """,
        params,
    )
    agg = agg_rows[0] if agg_rows else {}
    total = agg.get("total", 0) or 0

    # Best single partnership — fetch the match+batters for the MAX row
    # so the UI can render "210 · Kohli/Rohit".
    highest = None
    if total > 0:
        hi_rows = await db.q(
            f"""
            SELECT p.partnership_runs as runs, p.partnership_balls as balls,
                   p.batter1_id, p.batter1_name,
                   p.batter2_id, p.batter2_name,
                   m.id as match_id,
                   (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) as date
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
            ORDER BY p.partnership_runs DESC, p.id
            LIMIT 1
            """,
            params,
        )
        if hi_rows:
            r = hi_rows[0]
            highest = {
                "runs": r["runs"],
                "balls": r["balls"],
                "match_id": r["match_id"],
                "date": r["date"],
                "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
                "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
            }

    # Top pair by total runs together (any wicket). Canonicalize the
    # pair id-wise so AB+CD = CD+AB, as in /best-pairs.
    best_pair = None
    if total > 0:
        pair_rows = await db.q(
            f"""
            SELECT
                CASE WHEN p.batter1_id < p.batter2_id THEN p.batter1_id ELSE p.batter2_id END as p1_id,
                CASE WHEN p.batter1_id < p.batter2_id THEN p.batter2_id ELSE p.batter1_id END as p2_id,
                COUNT(*) as n,
                SUM(p.partnership_runs) as total_runs,
                MAX(p.partnership_runs) as best_runs
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
              AND p.batter1_id IS NOT NULL
              AND p.batter2_id IS NOT NULL
            GROUP BY p1_id, p2_id
            ORDER BY total_runs DESC, n DESC
            LIMIT 1
            """,
            params,
        )
        if pair_rows:
            r = pair_rows[0]
            name_rows = await db.q(
                "SELECT id, name FROM person WHERE id IN (:p1, :p2)",
                {"p1": r["p1_id"], "p2": r["p2_id"]},
            )
            names = {row["id"]: row["name"] for row in name_rows}
            best_pair = {
                "batter1": {"person_id": r["p1_id"], "name": names.get(r["p1_id"], r["p1_id"])},
                "batter2": {"person_id": r["p2_id"], "name": names.get(r["p2_id"], r["p2_id"])},
                "n": r["n"],
                "total_runs": r["total_runs"],
                "best_runs": r["best_runs"],
            }

    # Scope-avg counterpart — same query, team=None, but with
    # scope_to_team synthesized so the league-side baselines against
    # the team's tournament universe (matching the avg endpoint's
    # auto-narrow). Spec-avg-column-per-innings.md Commit 3.
    league_filters, league_aux = _league_aux(team, aux, filters)
    s_where, s_params = _partnership_filter(league_filters, None, side, aux=league_aux)
    s_rows = await db.q(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN p.partnership_runs >= 50  THEN 1 ELSE 0 END) as count_50_plus,
            SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
            ROUND(AVG(p.partnership_runs * 1.0), 1) as avg_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {s_where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        """,
        s_params,
    )
    sa_raw = s_rows[0] if s_rows else {}
    # Per-innings transform on the league-side dict — chip's scope_avg
    # must match `/scope/averages/partnerships/summary`'s response.
    sa = {
        "total": sa_raw.get("total") or 0,
        "count_50_plus": sa_raw.get("count_50_plus") or 0,
        "count_100_plus": sa_raw.get("count_100_plus") or 0,
        "avg_runs": sa_raw.get("avg_runs"),
    }
    # Divisor must come from `league_filters` so the chip's per-innings
    # rate matches the avg endpoint (which computes its own divisor
    # against the same scope as the aggregate). Pre-2026-04-29 this
    # passed `filters` — silent when filters and league_filters only
    # differed via `scope_to_team` (which lives on aux) or
    # `chip_team_class` (which only ran the chip alignment, not the
    # divisor), but a real bug under chip_baseline_scope_json which
    # fully overrides league_filters. Spec:
    # spec-slot-override-chip-alignment.md §5.2 (per-innings divisor
    # alignment).
    sa = _apply_partnerships_per_innings(
        sa, await _innings_count_for_phase(league_filters, league_aux, side="batting"),
    )

    return {
        "team": team,
        "side": side,
        "total":          wrap_metric(total, sa.get("total") or 0, "total", sample_size=total),
        "count_50_plus":  wrap_metric(agg.get("count_50_plus", 0) or 0, sa.get("count_50_plus") or 0, "count_50_plus", sample_size=total),
        "count_100_plus": wrap_metric(agg.get("count_100_plus", 0) or 0, sa.get("count_100_plus") or 0, "count_100_plus", sample_size=total),
        "avg_runs":       wrap_metric(agg.get("avg_runs"), sa.get("avg_runs"), "avg_runs", sample_size=total),
        "highest": highest,
        "best_pair": best_pair,
    }


@router.get("/{team}/partnerships/by-season")
async def team_partnerships_by_season(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    side: str = Query("batting"),
):
    """Per-season partnership aggregates for a team."""
    side = _validate_side(side)
    from .bucket_baseline_dispatch import is_precomputed_scope, baseline_where
    if is_precomputed_scope(filters, aux) and side == "batting":
        db = get_db()
        bw, bp = baseline_where(filters, aux, team=team)
        rows = await db.q(
            f"""
            SELECT season,
                   SUM(n) AS total,
                   SUM(count_50_plus) AS count_50_plus,
                   SUM(count_100_plus) AS count_100_plus,
                   ROUND(SUM(total_runs) * 1.0 / NULLIF(SUM(n), 0), 1) AS avg_runs,
                   COALESCE(MAX(best_runs), 0) AS best_runs
            FROM bucketbaselinepartnership {bw}
            GROUP BY season ORDER BY season
            """,
            bp,
        )
        return {
            "team": team,
            "side": side,
            "by_season": [
                {
                    "season": r["season"],
                    "total": r["total"] or 0,
                    "count_50_plus": r["count_50_plus"] or 0,
                    "count_100_plus": r["count_100_plus"] or 0,
                    "avg_runs": r["avg_runs"],
                    "best_runs": r["best_runs"],
                }
                for r in rows
            ],
        }

    db = get_db()
    where, params = _partnership_filter(filters, team, side, aux=aux)

    rows = await db.q(
        f"""
        SELECT m.season,
               COUNT(*) as total,
               SUM(CASE WHEN p.partnership_runs >= 50 THEN 1 ELSE 0 END) as count_50_plus,
               SUM(CASE WHEN p.partnership_runs >= 100 THEN 1 ELSE 0 END) as count_100_plus,
               ROUND(AVG(p.partnership_runs), 1) as avg_runs,
               MAX(p.partnership_runs) as best_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season
        ORDER BY m.season
        """,
        params,
    )
    return {
        "team": team,
        "side": side,
        "by_season": [
            {
                "season": r["season"],
                "total": r["total"] or 0,
                "count_50_plus": r["count_50_plus"] or 0,
                "count_100_plus": r["count_100_plus"] or 0,
                "avg_runs": r["avg_runs"],
                "best_runs": r["best_runs"],
            }
            for r in rows
        ],
    }
