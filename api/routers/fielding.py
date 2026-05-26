"""Fielding analytics router."""

from __future__ import annotations

import asyncio
import statistics
from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams, player_result_clause, player_inning_match_clause
from ..aux_clauses import splice_aux_join_clauses
from ..metrics_metadata import wrap_metric
from ..player_nationality import player_nationalities
from ..scope_links import suggested_splits, scope_dict_from_filters
from ..tournament_canonical import (
    is_canonical_with_variants,
    variants as canonical_variants,
    event_name_in_clause,
)
from ..wilson import prob_record, enrich_prob_record
from ..form_windows import scope_anchor

router = APIRouter(prefix="/api/v1/fielders", tags=["Fielding"])


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


async def _dismissal_position_distribution(
    db, person_id: str, filters: FilterParams, is_keeper: int = 0,
) -> list[dict]:
    """Return the fielder's per-(dismissed batter position) aggregates.

    Length-10 array keyed by `bucket` (1=opener, 2=#3, …, 10=#11).
    Substitute catches are EXCLUDED — the populate applied
    `is_substitute = 0`, matching the distribution-side semantics
    (CLAUDE.md "Substitute fielders — INCLUDED in /leaders, EXCLUDED
    in /distribution"). Convention 3: `catches` is inclusive of
    caught_and_bowled; not broken out separately.

    Joined from playerscopestats_fielding_position → playerscopestats;
    honours scope_key axes only (tournament/season/gender/team_type)
    per the precomputed-table-only contract this rollout uses.

    Each entry also carries per-bucket cohort fields
    (`cohort_dismissals_share` / `cohort_catches_per_match`)
    computed from the same `playerscopestatsfieldingposition` rows
    aggregated over every player at the same scope, partitioned by
    `is_keeper` (matches_as_keeper > 0 → keeper partition; = 0 →
    outfielder). Spec:
    spec-mix-and-performance-charts.md §3.3 — the By Dismissed
    Position tab's Mix histogram + Performance-vs-cohort chart
    reads these without a second roundtrip. cohort denominator for
    catches/match is SUM(playerscopestats.matches) across the
    partition (same for every bucket — bucket grain is the
    NUMERATOR; the cohort's total matches played is the
    DENOMINATOR).
    """
    scope_clauses: list[str] = []
    scope_params: dict = {}
    if filters.gender:
        scope_clauses.append("pss.gender = :gender")
        scope_params["gender"] = filters.gender
    if filters.team_type:
        scope_clauses.append("pss.team_type = :team_type")
        scope_params["team_type"] = filters.team_type
    if filters.tournament:
        if is_canonical_with_variants(filters.tournament):
            scope_clauses.append(event_name_in_clause(
                canonical_variants(filters.tournament),
                col="pss.tournament",
            ))
        else:
            scope_clauses.append("pss.tournament = :tournament")
            scope_params["tournament"] = filters.tournament
    if filters.season_from:
        scope_clauses.append("pss.season >= :season_from")
        scope_params["season_from"] = filters.season_from
    if filters.season_to:
        scope_clauses.append("pss.season <= :season_to")
        scope_params["season_to"] = filters.season_to

    player_clauses = ["pss.person_id = :pid"] + scope_clauses
    player_params: dict = {"pid": person_id, **scope_params}
    player_where = " AND ".join(player_clauses)
    cohort_where = " AND ".join(scope_clauses) if scope_clauses else "1=1"
    # Keeper-binary partition for the cohort — same predicate as
    # compute_players_fielding_cohort. is_keeper=1 → keepers (>0);
    # is_keeper=0 → outfielders (=0).
    keeper_pred = ">" if is_keeper else "="

    player_sql = f"""
        SELECT pssfp.position_bucket,
               SUM(pssfp.catches)    AS catches,
               SUM(pssfp.stumpings)  AS stumpings,
               SUM(pssfp.run_outs)   AS run_outs,
               SUM(pssfp.dismissals) AS dismissals
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.scope_key = pssfp.scope_key
         AND pss.person_id = pssfp.person_id
        WHERE {player_where}
        GROUP BY pssfp.position_bucket
        ORDER BY pssfp.position_bucket
    """
    cohort_sql = f"""
        SELECT pssfp.position_bucket,
               SUM(pssfp.catches)    AS catches,
               SUM(pssfp.dismissals) AS dismissals
        FROM playerscopestatsfieldingposition pssfp
        JOIN playerscopestats pss
          ON pss.scope_key = pssfp.scope_key
         AND pss.person_id = pssfp.person_id
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {cohort_where}
        GROUP BY pssfp.position_bucket
    """
    # The catches/match denominator is the SAME across all buckets:
    # SUM(playerscopestats.matches) for the cohort partition. Run it
    # in parallel with the bucket aggregates so the helper stays a
    # single roundtrip in user time.
    cohort_pool_sql = f"""
        SELECT SUM(pss.matches) AS n_matches_total
        FROM playerscopestats pss
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {cohort_where}
    """
    player_rows, cohort_rows, cohort_pool = await asyncio.gather(
        db.q(player_sql, player_params),
        db.q(cohort_sql, scope_params),
        db.q(cohort_pool_sql, scope_params),
    )

    by_bucket = {r["position_bucket"]: r for r in player_rows}
    cohort_by_bucket = {r["position_bucket"]: r for r in cohort_rows}
    cohort_total_dismissals = sum((r["dismissals"] or 0) for r in cohort_rows)
    cohort_n_matches = (cohort_pool[0].get("n_matches_total") if cohort_pool else 0) or 0

    out: list[dict] = []
    for b in range(1, 11):
        r = by_bucket.get(b)
        if r is None:
            entry = {
                "bucket": b, "catches": 0, "stumpings": 0,
                "run_outs": 0, "dismissals": 0,
            }
        else:
            entry = {
                "bucket":     b,
                "catches":    r["catches"] or 0,
                "stumpings":  r["stumpings"] or 0,
                "run_outs":   r["run_outs"] or 0,
                "dismissals": r["dismissals"] or 0,
            }
        c = cohort_by_bucket.get(b)
        if c is None or cohort_total_dismissals == 0:
            entry["cohort_dismissals_share"] = None
        else:
            entry["cohort_dismissals_share"] = (c["dismissals"] or 0) / cohort_total_dismissals
        if c is None or cohort_n_matches == 0:
            entry["cohort_catches_per_match"] = None
        else:
            entry["cohort_catches_per_match"] = round((c["catches"] or 0) / cohort_n_matches, 4)
        out.append(entry)
    return out


def _fielding_filter(filters: FilterParams, person_id: str, aux: AuxParams | None = None):
    """Build WHERE clause for fielding queries via fielding_credit.

    Uses build_side_neutral so filter_team / filter_opponent apply at
    match level — fielders' credits live in opponent-batting innings,
    so the default `i.team = :team` would return zero.
    """
    where, params = filters.build_side_neutral(has_innings_join=True, aux=aux, apply_inning=False)
    params["person_id"] = person_id
    parts = ["fc.fielder_id = :person_id"]
    if where:
        parts.append(where)
    rc = player_result_clause(aux, person_id, params)
    if rc:
        parts.append(rc)
    ri = player_inning_match_clause(aux, person_id, params, side="fielding")
    if ri:
        parts.append(ri)
    return " AND ".join(parts), params


@router.get("/leaders")
async def fielding_leaders(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
):
    """Top fielders + top keepers in the current filter scope.

    Fielding leaderboards are volume-based, not rate-based: catches
    per match is mostly a position/opportunity stat, not a skill stat.
    So no thresholds — the top-N ranking is self-filtering.

    Returns two lists:
      - by_dismissals: sum of catches + run-outs + caught-and-bowled +
        stumpings per fielder. Inclusive — keepers will appear here
        too since they take many catches.
      - by_keeper_dismissals: catches + stumpings from innings where
        the fielder was the designated keeper per
        `keeper_assignment`. This separates specialist keeping from
        sub-fielders who caught behind the stumps. Uses the Tier 2
        keeper-identification pipeline; see docs/spec-fielding-tier2.md.

    Tiebreak: stumpings DESC (evidence of sharp hands) then catches
    DESC then run-outs DESC.
    """
    db = get_db()
    # See batting_leaders + aux_clauses module for the rationale.
    # `aux_extra` is " AND <clause>..." with leading AND; we strip
    # for the AND-joined fc_parts list below.
    match_where, params = filters.build(has_innings_join=False, aux=aux)
    aux_extra = splice_aux_join_clauses(aux, params)
    has_filters = bool(match_where) or bool(aux_extra)

    # --- List 1: top fielders by total dismissals ------------------
    # All four kinds aggregated per fielder, with per-kind breakdown
    # so the UI can show how the total composes.
    fc_parts = ["fc.fielder_id IS NOT NULL"]
    if has_filters:
        fc_join = ("JOIN delivery d ON d.id = fc.delivery_id "
                   "JOIN innings i ON i.id = d.innings_id "
                   "JOIN match m ON m.id = i.match_id")
        if match_where:
            fc_parts.append(match_where)
        if aux_extra:
            # aux_extra carries leading " AND "; the fc_parts list
            # gets joined by " AND ", so strip the prefix.
            fc_parts.append(aux_extra.removeprefix(" AND "))
    else:
        fc_join = ""
    fc_where = " AND ".join(fc_parts)
    fielder_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               -- catches is the inclusive total per Convention 3 —
               -- caught_and_bowled is a sub-count broken out as `c_and_b`
               -- so consumers know how the total composes.
               SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                        THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
               SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
               SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS c_and_b
        FROM fieldingcredit fc {fc_join}
        WHERE {fc_where}
        GROUP BY fc.fielder_id
        ORDER BY total DESC, stumpings DESC, catches DESC, run_outs DESC
        LIMIT :lim
        """,
        {**params, "lim": limit},
    )

    # --- List 2: top keepers by keeper dismissals ------------------
    # Only fielding credits from innings where this fielder was the
    # designated keeper count. Restricts to caught + stumped (run
    # outs by the keeper are rare and muddy — they're fielding, not
    # keeping).
    ka_join = ("JOIN delivery d ON d.id = fc.delivery_id "
               "JOIN innings i ON i.id = d.innings_id "
               "JOIN keeperassignment ka ON ka.innings_id = i.id")
    ka_parts = [
        "fc.fielder_id IS NOT NULL",
        "ka.keeper_id = fc.fielder_id",
        "fc.kind IN ('caught', 'stumped')",
    ]
    if has_filters:
        ka_join += " JOIN match m ON m.id = i.match_id"
        if match_where:
            ka_parts.append(match_where)
        if aux_extra:
            ka_parts.append(aux_extra.removeprefix(" AND "))
    ka_where = " AND ".join(ka_parts)
    keeper_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               -- Convention 3: catches inclusive of caught_and_bowled.
               -- (Keepers don't bowl by default position so this is a
               -- structural-zero in practice, but the predicate keeps
               -- consistency with /leaders + /summary.)
               SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                        THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings
        FROM fieldingcredit fc {ka_join}
        WHERE {ka_where}
        GROUP BY fc.fielder_id
        ORDER BY total DESC, stumpings DESC, catches DESC
        LIMIT :lim
        """,
        {**params, "lim": limit},
    )

    # Batch name lookup for the ~20 survivors.
    top_ids = {r["person_id"] for r in fielder_rows} | {r["person_id"] for r in keeper_rows}
    name_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}

    def enrich(r, keeper: bool) -> dict:
        d = {
            "person_id": r["person_id"],
            "name": name_map.get(r["person_id"], r["person_id"]),
            "total": r["total"] or 0,
            "catches": r["catches"] or 0,
            "stumpings": r["stumpings"] or 0,
        }
        if not keeper:
            d["run_outs"] = r["run_outs"] or 0
            d["c_and_b"] = r["c_and_b"] or 0
        return d

    return {
        "by_dismissals": [enrich(r, keeper=False) for r in fielder_rows],
        "by_keeper_dismissals": [enrich(r, keeper=True) for r in keeper_rows],
    }


@router.get("/{person_id}/summary")
async def fielding_summary(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()

    name_rows = await db.q(
        "SELECT name FROM person WHERE id = :pid", {"pid": person_id}
    )
    name = name_rows[0]["name"] if name_rows else person_id

    where, params = _fielding_filter(filters, person_id, aux=aux)

    # Counts by kind
    kind_rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt,
               SUM(CASE WHEN fc.is_substitute THEN 1 ELSE 0 END) as sub_cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        """,
        params,
    )

    caught_only = 0
    stumpings = 0
    run_outs = 0
    caught_and_bowled = 0
    substitute_catches = 0

    for r in kind_rows:
        if r["kind"] == "caught":
            caught_only = r["cnt"]
            substitute_catches = r["sub_cnt"] or 0
        elif r["kind"] == "stumped":
            stumpings = r["cnt"]
        elif r["kind"] == "run_out":
            run_outs = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            caught_and_bowled = r["cnt"]

    # Convention 3: catches headline is INCLUSIVE of caught_and_bowled.
    # caught_and_bowled is exposed as a sub-count sibling so consumers
    # can see the breakdown but summing both would double-count.
    catches = caught_only + caught_and_bowled
    total = catches + stumpings + run_outs

    # Match count from matchplayer
    match_where, match_params = filters.build(has_innings_join=False, aux=aux)
    match_params["person_id"] = person_id
    match_parts = ["mp.person_id = :person_id"]
    if match_where:
        match_parts.append(match_where)
    # Player-POV result narrowing (matches the player's own side
    # won/lost/tied). mp + m are already joined here, but route through
    # the shared helper for one definition of the result semantics.
    rc = player_result_clause(aux, person_id, match_params, match_id_expr="mp.match_id")
    if rc:
        match_parts.append(rc)
    # Option-B inning: matches where the player's team batted in
    # innings N (match subset). This count is match-level (no innings
    # join) so it never saw the per-event clause — add the subset here
    # so fielding `matches` narrows consistently with the catches.
    ri = player_inning_match_clause(aux, person_id, match_params, match_id_expr="mp.match_id", side="fielding")
    if ri:
        match_parts.append(ri)
    match_clause = " AND ".join(match_parts)

    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT mp.match_id) as matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE {match_clause}
        """,
        match_params,
    )
    matches = match_rows[0]["matches"] if match_rows else 0

    # Tier 2: innings where this person was identified as the keeper.
    # Used by the frontend to decide whether to render the "Keeping" tab.
    # side-neutral: keeper's innings live in opponent-batting innings.
    keeping_where, keeping_params = filters.build_side_neutral(has_innings_join=True, apply_inning=False, aux=aux)
    keeping_params["person_id"] = person_id
    keeping_parts = ["ka.keeper_id = :person_id"]
    if keeping_where:
        keeping_parts.append(keeping_where)
    ri = player_inning_match_clause(aux, person_id, keeping_params, side="keeping")
    if ri:
        keeping_parts.append(ri)
    keeping_clause = " AND ".join(keeping_parts)
    keeping_rows = await db.q(
        f"""
        SELECT COUNT(*) as c FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {keeping_clause}
        """,
        keeping_params,
    )
    innings_kept = keeping_rows[0]["c"] if keeping_rows else 0

    nationalities = await player_nationalities(db, person_id)

    # Cohort baseline: partition by is_keeper (innings_kept > 0).
    # Phase 4 spec — fold the cohort response into the envelope. The
    # per-bucket cohort fields on dismissal_position_distribution
    # (spec-mix-and-performance-charts.md §3.3) also need the
    # partition flag, so compute it BEFORE the helper call.
    is_keeper_val = 1 if innings_kept > 0 else 0
    dismissal_position_distribution = await _dismissal_position_distribution(
        db, person_id, filters, is_keeper_val,
    )

    cohort: Optional[dict] = None
    if matches > 0:
        from .scope_averages import compute_players_fielding_cohort
        cohort = await compute_players_fielding_cohort(
            db, filters, aux, is_keeper_val, drop_set=None,
        )

    def _cohort_scope_avg(key: str) -> Optional[float]:
        if cohort is None:
            return None
        m = cohort.get(key)
        return m.get("scope_avg") if m else None

    cohort_sample = cohort["cohort"]["n_matches_total"] if cohort else None
    dismissals_pm_val = _safe_div(total, matches, 1, 3)
    catches_pm_val = _safe_div(catches, matches, 1, 3)
    stumpings_pm_val = _safe_div(stumpings, matches, 1, 3)
    run_outs_pm_val = _safe_div(run_outs, matches, 1, 3)

    return {
        "person_id": person_id,
        "name": name,
        "nationalities": nationalities,
        # Numeric fields envelope-wrapped per Phase 4.
        "matches":             wrap_metric(matches,            None, "matches",                    sample_size=cohort_sample),
        "catches":             wrap_metric(catches,            None, "field_catches",              sample_size=cohort_sample),
        "stumpings":           wrap_metric(stumpings,          None, "field_stumpings",            sample_size=cohort_sample),
        "run_outs":            wrap_metric(run_outs,           None, "field_run_outs",             sample_size=cohort_sample),
        "caught_and_bowled":   wrap_metric(caught_and_bowled,  None, "field_caught_and_bowled",    sample_size=cohort_sample),
        "total_dismissals":    wrap_metric(total,              None, "field_total_dismissals",     sample_size=cohort_sample),
        "substitute_catches":  wrap_metric(substitute_catches, None, "field_substitute_catches",   sample_size=cohort_sample),
        "innings_kept":        wrap_metric(innings_kept,       None, "field_innings_kept",         sample_size=cohort_sample),
        # Rate metrics — per-match rates against the keeper-binary
        # cohort. dismissals_per_match shipped Phase 4; the three
        # sub-component envelopes (catches/stumpings/run_outs)
        # close a spec gap (spec-player-baseline-parity.md §4.4
        # assumed they already existed; cohort returns them but the
        # player-side endpoint didn't thread them through).
        "dismissals_per_match": wrap_metric(
            dismissals_pm_val, _cohort_scope_avg("dismissals_per_match"),
            "field_dismissals_per_match", sample_size=cohort_sample,
        ),
        "catches_per_match": wrap_metric(
            catches_pm_val, _cohort_scope_avg("catches_per_match"),
            "field_catches_per_match", sample_size=cohort_sample,
        ),
        "stumpings_per_match": wrap_metric(
            stumpings_pm_val, _cohort_scope_avg("stumpings_per_match"),
            "field_stumpings_per_match", sample_size=cohort_sample,
        ),
        "run_outs_per_match": wrap_metric(
            run_outs_pm_val, _cohort_scope_avg("run_outs_per_match"),
            "field_run_outs_per_match", sample_size=cohort_sample,
        ),
        "dismissal_position_distribution": dismissal_position_distribution,
        "cohort": cohort["cohort"] if cohort else None,
        "is_keeper": is_keeper_val,
    }


@router.get("/{person_id}/by-season")
async def fielding_by_season(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

    rows = await db.q(
        f"""
        SELECT
            m.season,
            fc.kind,
            COUNT(*) as cnt
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

    # Per-season matches the player appeared in — needed for the
    # by-season chart's cohort overlay to rescale a per-match rate
    # baseline back to per-season volume (spec-player-baseline-
    # parity.md §4.4). Match-level filter clause (build with
    # has_innings_join=False) joined on matchplayer.
    match_where, match_params = filters.build(has_innings_join=False, aux=aux)
    match_params["person_id"] = person_id
    match_parts = ["mp.person_id = :person_id"]
    if match_where:
        match_parts.append(match_where)
    match_clause = " AND ".join(match_parts)
    matches_rows = await db.q(
        f"""
        SELECT m.season, COUNT(DISTINCT m.id) AS n_matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE {match_clause}
        GROUP BY m.season
        """,
        match_params,
    )
    matches_by_season = {r["season"]: r["n_matches"] for r in matches_rows}

    from collections import defaultdict
    seasons = defaultdict(lambda: {"caught_only": 0, "stumpings": 0, "run_outs": 0, "caught_and_bowled": 0})
    for r in rows:
        s = seasons[r["season"]]
        if r["kind"] == "caught":
            s["caught_only"] = r["cnt"]
        elif r["kind"] == "stumped":
            s["stumpings"] = r["cnt"]
        elif r["kind"] == "run_out":
            s["run_outs"] = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            s["caught_and_bowled"] = r["cnt"]

    by_season = []
    for season in sorted(seasons.keys()):
        s = seasons[season]
        # Convention 3: catches inclusive of caught_and_bowled.
        catches = s["caught_only"] + s["caught_and_bowled"]
        total = catches + s["stumpings"] + s["run_outs"]
        n_matches = matches_by_season.get(season, 0)
        # Group B (spec-rate-vs-volume-audit §2.1): per-match rates so
        # the new Dis/Match by-Season chart and its cohort overlay can
        # render off this payload directly. Denominator is matches the
        # player appeared in that season (not innings — fielding is
        # match-grain by convention).
        if n_matches:
            dpm = round(total / n_matches, 3)
            cpm = round(catches / n_matches, 3)
            spm = round(s["stumpings"] / n_matches, 3)
            rpm = round(s["run_outs"] / n_matches, 3)
        else:
            dpm = cpm = spm = rpm = None
        by_season.append({
            "season": season,
            "catches": catches,
            "stumpings": s["stumpings"],
            "run_outs": s["run_outs"],
            "caught_and_bowled": s["caught_and_bowled"],
            "total": total,
            "matches": n_matches,
            "dismissals_per_match": dpm,
            "catches_per_match": cpm,
            "stumpings_per_match": spm,
            "run_outs_per_match": rpm,
        })

    return {"by_season": by_season}


@router.get("/{person_id}/by-phase")
async def fielding_by_phase(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

    rows = await db.q(
        f"""
        SELECT
            CASE
                WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
            END as phase,
            fc.kind,
            COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY phase, fc.kind
        ORDER BY MIN(d.over_number)
        """,
        params,
    )

    from collections import defaultdict
    phases = defaultdict(lambda: {"caught_only": 0, "stumpings": 0, "run_outs": 0, "caught_and_bowled": 0})
    for r in rows:
        p = phases[r["phase"]]
        if r["kind"] == "caught":
            p["caught_only"] = r["cnt"]
        elif r["kind"] == "stumped":
            p["stumpings"] = r["cnt"]
        elif r["kind"] == "run_out":
            p["run_outs"] = r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            p["caught_and_bowled"] = r["cnt"]

    # Group D3 (spec-rate-vs-volume-audit §2.1): denominator is
    # player's matches in scope — a single scalar across phases
    # (fielding is match-grain by convention; per-phase isn't the
    # right denominator). Mirrors the /summary matchplayer-based
    # match count.
    match_where, match_params = filters.build(has_innings_join=False, aux=aux)
    match_params["person_id"] = person_id
    match_parts = ["mp.person_id = :person_id"]
    if match_where:
        match_parts.append(match_where)
    match_clause = " AND ".join(match_parts)
    match_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT mp.match_id) as matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE {match_clause}
        """,
        match_params,
    )
    matches = match_rows[0]["matches"] if match_rows else 0

    phase_labels = {"powerplay": "1-6", "middle": "7-15", "death": "16-20"}
    phase_order = ["powerplay", "middle", "death"]

    by_phase = []
    for phase in phase_order:
        if phase not in phases:
            continue
        p = phases[phase]
        # Convention 3: catches inclusive of caught_and_bowled.
        catches = p["caught_only"] + p["caught_and_bowled"]
        total = catches + p["stumpings"] + p["run_outs"]
        # Group D3 per-match rates per phase.
        if matches:
            tpm = round(total / matches, 3)
            cpm = round(catches / matches, 3)
            spm = round(p["stumpings"] / matches, 3)
            rpm = round(p["run_outs"] / matches, 3)
        else:
            tpm = cpm = spm = rpm = None
        by_phase.append({
            "phase": phase,
            "overs": phase_labels[phase],
            "catches": catches,
            "stumpings": p["stumpings"],
            "run_outs": p["run_outs"],
            "caught_and_bowled": p["caught_and_bowled"],
            "total": total,
            "matches": matches,
            "total_per_match": tpm,
            "catches_per_match": cpm,
            "stumpings_per_match": spm,
            "run_outs_per_match": rpm,
        })

    return {"by_phase": by_phase}


@router.get("/{person_id}/by-over")
async def fielding_by_over(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Per-over fielding rollup for the bowler-side overs the player
    appears in. Returns dismissals + per-kind breakdown (catches /
    run_outs / stumpings) + a cohort dismissals-per-match field
    aggregated across the keeper / outfielder partition the player
    belongs to. User-asked 2026-05-23 — drives the three new
    comparative charts on /fielding?tab=By+Over.
    """
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

    # Player per-over rollup with per-kind breakdown.
    player_rows = await db.q(
        f"""
        SELECT
            d.over_number,
            COUNT(*) AS dismissals,
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                     THEN 1 ELSE 0 END) AS catches,
            SUM(CASE WHEN fc.kind = 'run_out'  THEN 1 ELSE 0 END) AS run_outs,
            SUM(CASE WHEN fc.kind = 'stumped'  THEN 1 ELSE 0 END) AS stumpings
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY d.over_number
        ORDER BY d.over_number
        """,
        params,
    )

    # Derive is_keeper_val for the cohort partition. Cheaper than the
    # full /summary path: matches_as_keeper > 0 on playerscopestats.
    keep_rows = await db.q(
        """
        SELECT COALESCE(SUM(matches_as_keeper), 0) AS mk
        FROM playerscopestats
        WHERE person_id = :person_id
        """,
        {"person_id": person_id},
    )
    is_keeper_val = 1 if (keep_rows and (keep_rows[0]["mk"] or 0) > 0) else 0
    keeper_pred = ">" if is_keeper_val else "="

    # Cohort dismissals per match by over — keeper-binary partition,
    # same scope as the player. Two parallel queries:
    #  - per-over dismissal counts across the cohort
    #  - total matches across the cohort (constant per over)
    # Filter at the playerscopestats level on the scope_key axes only
    # (mirrors _dismissal_position_distribution).
    scope_clauses: list[str] = []
    scope_params: dict = {}
    if filters.gender:
        scope_clauses.append("pss.gender = :gender")
        scope_params["gender"] = filters.gender
    if filters.team_type:
        scope_clauses.append("pss.team_type = :team_type")
        scope_params["team_type"] = filters.team_type
    if filters.tournament:
        if is_canonical_with_variants(filters.tournament):
            scope_clauses.append(event_name_in_clause(
                canonical_variants(filters.tournament), col="pss.tournament",
            ))
        else:
            scope_clauses.append("pss.tournament = :tournament")
            scope_params["tournament"] = filters.tournament
    if filters.season_from:
        scope_clauses.append("pss.season >= :season_from")
        scope_params["season_from"] = filters.season_from
    if filters.season_to:
        scope_clauses.append("pss.season <= :season_to")
        scope_params["season_to"] = filters.season_to
    cohort_where = " AND ".join(scope_clauses) if scope_clauses else "1=1"

    cohort_total_matches_sql = f"""
        SELECT SUM(pss.matches) AS n
        FROM playerscopestats pss
        WHERE pss.matches_as_keeper {keeper_pred} 0
          AND {cohort_where}
    """
    cohort_over_sql = f"""
        SELECT d.over_number,
               COUNT(*) AS dismissals
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE COALESCE(fc.is_substitute, 0) = 0
          AND fc.fielder_id IN (
            SELECT DISTINCT pss.person_id
            FROM playerscopestats pss
            WHERE pss.matches_as_keeper {keeper_pred} 0
              AND {cohort_where}
          )
        GROUP BY d.over_number
    """
    cohort_match_rows, cohort_over_rows = await asyncio.gather(
        db.q(cohort_total_matches_sql, scope_params),
        db.q(cohort_over_sql, scope_params),
    )
    cohort_total_matches = (cohort_match_rows[0]["n"] if cohort_match_rows else 0) or 0
    cohort_by_over = {r["over_number"]: r["dismissals"] for r in cohort_over_rows}

    by_over = []
    for r in player_rows:
        over_display = r["over_number"] + 1  # display 1-20
        cd = cohort_by_over.get(r["over_number"], 0)
        by_over.append({
            "over_number": over_display,
            "dismissals": r["dismissals"],
            "catches":   r["catches"] or 0,
            "run_outs":  r["run_outs"] or 0,
            "stumpings": r["stumpings"] or 0,
            "cohort_dismissals_per_match": (
                round(cd / cohort_total_matches, 4)
                if cohort_total_matches else None
            ),
        })

    return {"by_over": by_over}


@router.get("/{person_id}/dismissal-types")
async def fielding_dismissal_types(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)

    rows = await db.q(
        f"""
        SELECT fc.kind, COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY fc.kind
        ORDER BY cnt DESC
        """,
        params,
    )

    by_kind = {r["kind"]: r["cnt"] for r in rows}
    total = sum(by_kind.values())

    return {"total": total, "by_kind": by_kind}


@router.get("/{person_id}/victims")
async def fielding_victims(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)
    params["limit"] = limit

    rows = await db.q(
        f"""
        SELECT
            w.player_out_id as batter_id,
            w.player_out as batter_name,
            fc.kind,
            COUNT(*) as cnt
        FROM fieldingcredit fc
        JOIN wicket w ON w.id = fc.wicket_id
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY w.player_out_id, fc.kind
        ORDER BY cnt DESC
        """,
        params,
    )

    from collections import defaultdict
    victim_agg = defaultdict(lambda: {
        "batter_name": "", "catches": 0, "stumpings": 0, "run_outs": 0, "total": 0,
    })
    for r in rows:
        v = victim_agg[r["batter_id"]]
        v["batter_name"] = r["batter_name"]
        if r["kind"] == "caught":
            v["catches"] += r["cnt"]
        elif r["kind"] == "caught_and_bowled":
            v["catches"] += r["cnt"]
        elif r["kind"] == "stumped":
            v["stumpings"] += r["cnt"]
        elif r["kind"] == "run_out":
            v["run_outs"] += r["cnt"]
        v["total"] += r["cnt"]

    victims = sorted(
        [{"batter_id": k, **v} for k, v in victim_agg.items()],
        key=lambda x: x["total"],
        reverse=True,
    )[:limit]

    return {"victims": victims}


@router.get("/{person_id}/by-innings")
async def fielding_by_innings(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    where, params = _fielding_filter(filters, person_id, aux=aux)
    params["limit"] = limit
    params["offset"] = offset

    # Count total distinct match appearances with fielding credits
    count_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.match_id) as total
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        """,
        params,
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = await db.q(
        f"""
        SELECT
            i.match_id,
            (SELECT md.date FROM matchdate md WHERE md.match_id = i.match_id
             ORDER BY md.date LIMIT 1) as date,
            m.event_name as tournament,
            -- Convention 3: catches inclusive of caught_and_bowled at SQL.
            -- (Previous shape was caught-only here + python addition at
            -- line 614; collapsed into a single inclusive predicate so
            -- there's only one source of truth.)
            SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                     THEN 1 ELSE 0 END) as catches,
            SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) as stumpings,
            SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) as run_outs,
            COUNT(*) as total
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        GROUP BY i.match_id
        ORDER BY date DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    # For each match, figure out the opponent from the fielder's team perspective
    innings_list = []
    for r in rows:
        # Look up which team this fielder was on in this match
        team_rows = await db.q(
            "SELECT team FROM matchplayer WHERE match_id = :mid AND person_id = :pid LIMIT 1",
            {"mid": r["match_id"], "pid": person_id},
        )
        team = team_rows[0]["team"] if team_rows else None

        match_rows = await db.q(
            "SELECT team1, team2 FROM match WHERE id = :mid",
            {"mid": r["match_id"]},
        )
        if match_rows and team:
            mr = match_rows[0]
            opponent = mr["team2"] if mr["team1"] == team else mr["team1"]
        else:
            opponent = None

        innings_list.append({
            "match_id": r["match_id"],
            "date": r["date"],
            "opponent": opponent,
            "tournament": r["tournament"],
            "catches": r["catches"],  # already inclusive (Convention 3)
            "stumpings": r["stumpings"],
            "run_outs": r["run_outs"],
            "total": r["total"],
        })

    return {"innings": innings_list, "total": total}


# ─────────────────────────────────────────────────────────────────────
# Per-match fielder distribution dossier — three sibling count blocks
# (catches / run_outs / stumpings) with three-simple milestone
# probabilities (P=0 / P=1 / P≥2), Wilson 95% CIs, and four form
# windows. Stumpings block emitted only for players with
# innings_kept > 0 in scope. Spec: internal_docs/spec-distribution-stats.md §13.


async def _match_master_sample_fielder(
    db, person_id: str, filters: FilterParams, aux: AuxParams,
) -> tuple[list[dict], int]:
    """Materialise per-match observation rows for a fielder under the
    active filter scope. One row per match the player appears on the
    team sheet (matchplayer.person_id = id). Returns (observations,
    substitute_catches). Spec §13.2.

    Match-grain filtering — drop has_innings_join. Side-neutral team
    filter — fielding credits live on the OPPOSITE-side innings.
    Inning aux is no-op for fielder (events span both innings; per
    spec §13.1).
    """
    # Match-level scope clause (no innings join). Side-neutral so
    # filter_team and filter_opponent apply at match level.
    where, params = filters.build_side_neutral(has_innings_join=False, aux=aux)
    params["person_id"] = person_id
    match_where = where if where else "1=1"

    # Single CTE-based query. player_matches is the scope-filtered
    # match list; fielding_per_match and keeping_per_match are
    # constrained only by player id (LEFT JOIN to player_matches
    # carries the scope filter).
    rows = await db.q(
        f"""
        WITH player_matches AS (
            SELECT mp.match_id,
                   MIN(md.date) AS date
            FROM matchplayer mp
            JOIN match m ON m.id = mp.match_id
            LEFT JOIN matchdate md ON md.match_id = mp.match_id
            WHERE mp.person_id = :person_id AND {match_where}
            GROUP BY mp.match_id
        ),
        fielding_per_match AS (
            SELECT i.match_id,
                   -- Convention 3 (codified 2026-04-26 in /fielding/summary):
                   -- catches is the inclusive total — caught_and_bowled
                   -- is a sub-count rolled into catches everywhere a
                   -- single "catches" headline is surfaced.
                   SUM(CASE WHEN fc.kind IN ('caught', 'caught_and_bowled')
                            AND COALESCE(fc.is_substitute, 0) = 0
                            THEN 1 ELSE 0 END) AS catches,
                   SUM(CASE WHEN fc.kind = 'run_out'
                            AND COALESCE(fc.is_substitute, 0) = 0
                            THEN 1 ELSE 0 END) AS run_outs,
                   SUM(CASE WHEN fc.kind = 'stumped'
                            THEN 1 ELSE 0 END) AS stumpings
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            WHERE fc.fielder_id = :person_id
            GROUP BY i.match_id
        ),
        keeping_per_match AS (
            SELECT i.match_id,
                   COUNT(*) AS kept_innings
            FROM keeperassignment ka
            JOIN innings i ON i.id = ka.innings_id
            WHERE ka.keeper_id = :person_id
            GROUP BY i.match_id
        )
        SELECT pm.match_id,
               COALESCE(pm.date, '') AS date,
               COALESCE(fpm.catches, 0) AS catches,
               COALESCE(fpm.run_outs, 0) AS run_outs,
               COALESCE(fpm.stumpings, 0) AS stumpings,
               COALESCE(kpm.kept_innings, 0) AS kept_innings
        FROM player_matches pm
        LEFT JOIN fielding_per_match fpm ON fpm.match_id = pm.match_id
        LEFT JOIN keeping_per_match kpm ON kpm.match_id = pm.match_id
        ORDER BY pm.date ASC, pm.match_id ASC
        """,
        params,
    )
    observations = [
        {
            "match_id": r["match_id"],
            "date": r["date"],
            "catches": r["catches"] or 0,
            "run_outs": r["run_outs"] or 0,
            "stumpings": r["stumpings"] or 0,
            "kept_innings": r["kept_innings"] or 0,
            "is_keeper": 1 if (r["kept_innings"] or 0) > 0 else 0,
        }
        for r in rows
    ]

    # Substitute catches — same scope, separate scalar for
    # reconciliation against /fielders/{id}/summary.
    sub_rows = await db.q(
        f"""
        SELECT COUNT(*) AS sub_catches
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id = :person_id
          AND fc.kind = 'caught'
          AND fc.is_substitute = 1
          AND {match_where}
        """,
        params,
    )
    substitute_catches = (sub_rows[0]["sub_catches"] if sub_rows else 0) or 0
    return observations, substitute_catches


def _count_block(observations: list[dict], key: str) -> dict:
    """Sibling count block — `catches` / `run_outs` / `stumpings`.
    Three simples (P=0 / P=1 / P≥2), denom = n_matches. Spec §13.3.1."""
    n = len(observations)
    vals = [o[key] for o in observations]

    if n == 0:
        keys = ["p_zero", "p_one", "p_geq_2"]
        return {
            "total": 0,
            "mean_per_match": None,
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
        "mean_per_match": round(mean, 4),
        "median": median,
        "variance": round(variance, 4),
        "std": round(std, 4),
        "milestones": {
            "p_zero":  prob_record(_count_eq(0), n),
            "p_one":   prob_record(_count_eq(1), n),
            "p_geq_2": prob_record(_count_geq(2), n),
        },
    }


def _distribution_dossier_fielder(
    observations: list[dict], substitute_catches: int,
) -> dict:
    """Pure aggregate. Three count blocks + top-level scalars. The
    stumpings block is null when innings_kept == 0 (non-keepers).
    Spec §13.3."""
    n = len(observations)
    innings_kept = sum(o["kept_innings"] for o in observations)

    return {
        "n_matches": n,
        "innings_kept": innings_kept,
        "substitute_catches": substitute_catches,
        "observations": [
            {
                "match_id": o["match_id"],
                "date": o["date"],
                "catches": o["catches"],
                "run_outs": o["run_outs"],
                "stumpings": o["stumpings"],
                "is_keeper": o["is_keeper"],
            }
            for o in observations
        ],
        "catches": _count_block(observations, "catches"),
        "run_outs": _count_block(observations, "run_outs"),
        "stumpings": _count_block(observations, "stumpings") if innings_kept > 0 else None,
    }


def _form_windows_fielder(
    observations: list[dict], substitute_catches_total: int, today: date,
) -> dict:
    """Slice the date-asc observation list into four match-grain form
    windows, run the dossier on each, emit the fielder-specific delta
    block (three means per window, stumpings nullable). Spec §13.4.

    Substitute-catches scalar inside form windows is derived as the
    fraction of the lifetime total proportional to the window's
    n_matches share — substitutes are rare (≤ a handful per career)
    and per-match attribution would require a second filtered query
    per window. The dossier-level scalar is the authoritative number;
    form-window values are informational only.
    """
    anchor = scope_anchor(observations, today)
    last_10 = observations[-10:]
    cutoff_60d = (anchor - timedelta(days=60)).isoformat()
    cutoff_6mo = (anchor - timedelta(days=180)).isoformat()
    cutoff_1yr = (anchor - timedelta(days=365)).isoformat()
    last_60d = [o for o in observations if (o["date"] or "") >= cutoff_60d]
    last_6mo = [o for o in observations if (o["date"] or "") >= cutoff_6mo]
    last_1yr = [o for o in observations if (o["date"] or "") >= cutoff_1yr]

    # Form-window subs scalar: proportional share. Lifetime carries the
    # authoritative count.
    n_total = len(observations)
    def _sub_share(window_obs: list[dict]) -> int:
        if n_total == 0 or substitute_catches_total == 0:
            return 0
        return round(substitute_catches_total * len(window_obs) / n_total)

    lifetime_doss = _distribution_dossier_fielder(observations, substitute_catches_total)
    last_10_doss = _distribution_dossier_fielder(last_10, _sub_share(last_10))
    last_60d_doss = _distribution_dossier_fielder(last_60d, _sub_share(last_60d))
    last_6mo_doss = _distribution_dossier_fielder(last_6mo, _sub_share(last_6mo))
    last_1yr_doss = _distribution_dossier_fielder(last_1yr, _sub_share(last_1yr))

    def _delta(window_doss: dict, key: str) -> Optional[float]:
        wb = window_doss.get(key)
        lb = lifetime_doss.get(key)
        if wb is None or lb is None:
            return None
        wv = wb.get("mean_per_match")
        lv = lb.get("mean_per_match")
        if wv is None or lv is None:
            return None
        return round(wv - lv, 4)

    delta = {}
    for win_name, win_doss in [
        ("last_10", last_10_doss),
        ("last_60d", last_60d_doss),
        ("last_6mo", last_6mo_doss),
        ("last_1yr", last_1yr_doss),
    ]:
        for metric in ("catches", "run_outs", "stumpings"):
            delta[f"{win_name}_{metric}_mean_minus_lifetime"] = _delta(win_doss, metric)

    return {
        "last_10": last_10_doss,
        "last_60d": last_60d_doss,
        "last_6mo": last_6mo_doss,
        "last_1yr": last_1yr_doss,
        "delta": delta,
    }


@router.get("/{person_id}/distribution")
async def fielding_distribution(
    person_id: str,
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
    """Per-match fielding distribution dossier.

    Returns three sibling count blocks under one master sample —
    `catches`, `run_outs`, and `stumpings` (null for non-keepers) —
    plus four form windows (last_10 / last_60d / last_6mo / last_1yr),
    a `substitute_catches` reconciliation scalar, and scope-derived
    suggested-splits navigation hints.

    Master sample is per-match (one row per match the player appears
    in `matchplayer`). Substitute catches are excluded from the
    distribution and surfaced separately. Caught-and-bowled is bowler-
    credited and lives on the bowling dossier.

    Every probability ships as `{value, num, denom, ci_low, ci_high}`
    with a Wilson 95% CI. Three simples per block: `p_zero`, `p_one`,
    `p_geq_2`.

    Spec: internal_docs/spec-distribution-stats.md §13.
    """
    db = get_db()
    today = date.fromisoformat(as_of_date) if as_of_date else date.today()

    observations, substitute_catches = await _match_master_sample_fielder(
        db, person_id, filters, aux,
    )
    lifetime = _distribution_dossier_fielder(observations, substitute_catches)
    form = _form_windows_fielder(observations, substitute_catches, today)

    # PT4 of spec-prob-baselines.md — keeper-binary cohort baseline.
    # Player's is_keeper for this scope is derived the same way the
    # /summary endpoint does it (innings_kept > 0). Cohort fetched
    # once, applied to lifetime + every form window's catches block
    # (P(=0) / P(=1) / P(≥2)).
    if observations:
        innings_kept = sum(o["kept_innings"] for o in observations)
        is_keeper_val = 1 if innings_kept > 0 else 0
        from .scope_averages import compute_players_fielding_cohort
        cohort = await compute_players_fielding_cohort(
            db, filters, aux, is_keeper_val, drop_set=None,
        )
        _enrich_fielding_catches_milestones_with_cohort(
            lifetime["catches"]["milestones"], cohort,
        )
        for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
            window_doss = form.get(window_key)
            if window_doss and "catches" in window_doss:
                _enrich_fielding_catches_milestones_with_cohort(
                    window_doss["catches"]["milestones"], cohort,
                )

    # last_match_date — drives the frontend dormancy badge.
    # Spec §13 + design-decisions.md "Dormancy badge".
    obs_dates = [o["date"] for o in observations if o.get("date")]
    lifetime["last_match_date"] = max(obs_dates) if obs_dates else None

    scope = scope_dict_from_filters(filters)
    splits = suggested_splits(scope)

    return {
        "scope": {k: v for k, v in scope.items() if v},
        "lifetime": lifetime,
        "form": form,
        "suggested_splits": splits,
    }


# PT4 of spec-prob-baselines.md — fielding catches chip direction +
# cohort field map. P(=0) lower_better (more 0-catch matches is bad);
# P(=1) higher_better (revised 2026-05-22 per user feedback — more
# single-catch matches IS a positive signal: it lifts mass off the
# 0-catch tail, even when it doesn't convert to a 2+ haul); P(≥2)
# higher_better.
_FIELDING_CATCHES_PROB_DIRECTIONS: dict[str, str | None] = {
    "p_zero":  "lower_better",
    "p_one":   "higher_better",
    "p_geq_2": "higher_better",
}

_FIELDING_CATCHES_COHORT_FIELD: dict[str, str] = {
    "p_zero":  "prob_zero",
    "p_one":   "prob_one",
    "p_geq_2": "prob_geq_2",
}


def _enrich_fielding_catches_milestones_with_cohort(
    milestones: dict, cohort: dict,
) -> None:
    """Mutate each ProbRecord in the fielding catches block to attach
    cohort baselines. Mirrors the batting + bowling enrichment helpers.
    spec-prob-baselines.md §4.2.

    P(=1) has direction=None per spec §6 — descriptive, not directional;
    enrich_prob_record's None-direction path leaves delta_pct null.
    """
    cohort_info = cohort.get("cohort") or {}
    sample_size = cohort_info.get("n_matches_total")
    for chip_key, direction in _FIELDING_CATCHES_PROB_DIRECTIONS.items():
        pr = milestones.get(chip_key)
        if not pr:
            continue
        cohort_field = _FIELDING_CATCHES_COHORT_FIELD[chip_key]
        cohort_envelope = cohort.get(cohort_field) or {}
        scope_avg = cohort_envelope.get("scope_avg")
        enrich_prob_record(pr, scope_avg, direction, sample_size)


def _row_to_fielding_record(r: dict) -> dict:
    return {
        "catches": r["catches"], "stumpings": r["stumpings"],
        "run_outs": r["run_outs"], "dismissals": r["dismissals"],
        "match_id": r["match_id"],
        "opponent": r["opponent"],
        "team": r["team"],
        "date": r["date"],
        "tournament": r["tournament"],
        "season": r["season"],
    }


@router.get("/{person_id}/records")
async def fielding_records(
    person_id: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    limit: int = Query(10, ge=1, le=20),
):
    """Per-player fielding record lists — three lists by dismissal type.

    Lists:
      - most_catches_match (catches DESC, then dismissals DESC tiebreak)
      - most_stumpings_match (stumpings DESC; populated only for
        keepers — typically empty / single-row for outfielders)
      - most_dismissals_match (catches + stumpings + run_outs DESC)

    Catches INCLUDE caught_and_bowled (Convention 3 invariant). Volume
    framing — substitute appearances counted (matches the /leaders
    semantic for catches, NOT the /distribution master-sample
    semantic).

    Reads from matchfielderperf (precomputed). Option-B inning IS
    applied as a MATCH subset (matches where the fielder's team batted
    in innings N — internal_docs/spec-inning-unify-option-b.md), which
    composes cleanly with the per-match precomp grain via a match-id
    filter. This is NOT per-event inning ("which innings he fielded
    in") — Option B's inning is a match filter, so the clause keys on
    m.id only.
    """
    db = get_db()
    where, params = filters.build(has_innings_join=False, aux=aux)
    params["person_id"] = person_id
    params["lim"] = limit
    ri = player_inning_match_clause(aux, person_id, params, side="fielding")
    if ri:
        where = f"{where} AND {ri}" if where else ri

    base_filt = "mf.fielder_id = :person_id"
    if where:
        base_filt = f"{base_filt} AND {where}"

    select_clause = """
        SELECT mf.catches, mf.stumpings, mf.run_outs, mf.dismissals,
               m.id AS match_id,
               mp.team AS team,
               CASE WHEN m.team1 = mp.team THEN m.team2 ELSE m.team1 END AS opponent,
               m.event_name AS tournament, m.season AS season,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM matchfielderperf mf
        JOIN match m ON m.id = mf.match_id
        JOIN matchplayer mp ON mp.match_id = m.id AND mp.person_id = mf.fielder_id
    """

    mc_q = db.q(f"""{select_clause}
        WHERE {base_filt} AND mf.catches > 0
        ORDER BY mf.catches DESC, mf.dismissals DESC LIMIT :lim""", params)
    ms_q = db.q(f"""{select_clause}
        WHERE {base_filt} AND mf.stumpings > 0
        ORDER BY mf.stumpings DESC, mf.dismissals DESC LIMIT :lim""", params)
    md_q = db.q(f"""{select_clause}
        WHERE {base_filt} AND mf.dismissals > 0
        ORDER BY mf.dismissals DESC LIMIT :lim""", params)

    name_q = db.q("SELECT name FROM person WHERE id = :person_id", {"person_id": person_id})

    mc, ms, md, name_rows = await asyncio.gather(mc_q, ms_q, md_q, name_q)

    return {
        "person_id": person_id,
        "name": name_rows[0]["name"] if name_rows else person_id,
        "most_catches_match": [_row_to_fielding_record(r) for r in mc],
        "most_stumpings_match": [_row_to_fielding_record(r) for r in ms],
        "most_dismissals_match": [_row_to_fielding_record(r) for r in md],
    }
