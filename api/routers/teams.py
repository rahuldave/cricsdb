"""Teams router — team records, results, head-to-head, by-season."""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams
from ..metrics_metadata import wrap_metric
from ..tournament_canonical import series_type as series_type_for

router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])


# ICC full-member nations (men's & women's — same team strings in cricsheet).
# Used by the Teams landing page to split international teams into the
# top-line "regular" group vs "associate" (everyone else who's played an
# international T20). Afghanistan + Ireland were elevated in 2017; we
# treat them as regular for display simplicity since they play the full
# tournament calendar today. Zimbabwe remains a full member despite
# historical ICC pressure.
ICC_FULL_MEMBERS = frozenset({
    "Afghanistan", "Australia", "Bangladesh", "England", "India",
    "Ireland", "New Zealand", "Pakistan", "South Africa", "Sri Lanka",
    "West Indies", "Zimbabwe",
})


def _team_filter_clause(filters: FilterParams, team_param: str = ":team", aux: AuxParams | None = None) -> tuple[str, dict]:
    """Build match-level filter clause for team queries (no innings join)."""
    where, params = filters.build(has_innings_join=False, aux=aux)
    parts = [f"(m.team1 = {team_param} OR m.team2 = {team_param})"]
    if where:
        parts.append(where)
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


@router.get("/{team}/summary")
async def team_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    db = get_db()
    filt, params = _team_filter_clause(filters, aux=aux)
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
    s_matches = sr.get("matches", 0) or 0
    s_decided = sr.get("decided", 0) or 0
    s_bf = sr.get("bat_first_wins", 0) or 0
    s_ff = sr.get("field_first_wins", 0) or 0
    # Scope-avg win_pct collapses to ~50% by construction (every win
    # is some team's loss). Render as the bat-first share — the
    # informative league signal.
    s_win_pct = round(s_bf * 100 / s_decided, 1) if s_decided > 0 else None

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

    return {
        "team": team,
        "matches":          wrap_metric(matches, s_matches, "matches", sample_size=s_matches),
        "wins":             wrap_metric(wins, None, "wins", sample_size=matches),
        "losses":           wrap_metric(row.get("losses", 0) or 0, None, "losses", sample_size=matches),
        "ties":             wrap_metric(row.get("ties", 0) or 0, sr.get("ties", 0) or 0, "ties", sample_size=matches),
        "no_results":       wrap_metric(row.get("no_results", 0) or 0, sr.get("no_results", 0) or 0, "no_results", sample_size=matches),
        "win_pct":          wrap_metric(win_pct, s_win_pct, "win_pct", sample_size=matches),
        "toss_wins":        wrap_metric(row.get("toss_wins", 0) or 0, sr.get("toss_decided", 0) or 0, "toss_wins", sample_size=matches),
        "bat_first_wins":   wrap_metric(row.get("bat_first_wins", 0) or 0, s_bf, "bat_first_wins", sample_size=matches),
        "field_first_wins": wrap_metric(row.get("field_first_wins", 0) or 0, s_ff, "field_first_wins", sample_size=matches),
        "gender_breakdown": gender_breakdown,
        "keepers": keepers,
        "keeper_ambiguous_innings": keeper_ambiguous,
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
    filt, params = _team_filter_clause(filters, aux=aux)
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
    base_where, params = filters.build(has_innings_join=False, aux=aux)
    params["team"] = team
    params["opponent"] = opponent

    match_clause = (
        "(m.team1 = :team OR m.team2 = :team) AND "
        "(m.team1 = :opponent OR m.team2 = :opponent)"
    )
    if base_where:
        match_clause += f" AND {base_where}"

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
    filt, params = _team_filter_clause(filters, aux=aux)
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
    filt, params = _team_filter_clause(filters, aux=aux)
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
    filt, params = _team_filter_clause(filters, aux=aux)
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
    roster_filt, roster_params = _team_filter_clause(filters, aux=aux)
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
    Used for scope_avg's of catches_per_match, stumpings_per_match,
    run_outs_per_match, wides_per_match, noballs_per_match — every
    rate computed as (fielding-side count / matches) where the
    league-side denominator counts each match once but the league-
    side numerator counts both sides."""
    if v is None:
        return None
    return round(v / 2, 2)


def _scope_to_team_clause(
    aux: AuxParams | None, filters: FilterParams,
) -> tuple[str, dict]:
    """Subquery clause narrowing m.event_name to the primary team's
    tournament universe. Applied only when:
      - aux.scope_to_team is set (avg-slot fetch), AND
      - the request hasn't explicitly narrowed by tournament.

    Returns ("", {}) if the gate doesn't apply. Caller decides where
    to splice the clause + extend its params dict.
    """
    if aux is None or not aux.scope_to_team or filters.tournament:
        return "", {}
    return (
        "m.event_name IN ("
        "SELECT DISTINCT m_st.event_name FROM matchplayer mp_st "
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
    return {
        "innings_batted": r.get("innings_batted") or 0,
        "total_runs": total_runs,
        "legal_balls": legal_balls,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(boundaries, legal_balls, 100, 1),
        "bat_dot_pct": _safe_div(dots, legal_balls, 100, 1),
        "fours": fours,
        "sixes": sixes,
        "fifties": r.get("fifties") or 0,
        "hundreds": r.get("hundreds") or 0,
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
        "lowest_all_out_total": lowest_all_out,
    }


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

    return {
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
        "avg_1st_innings_total": avg_1st,
        "avg_2nd_innings_total": avg_2nd,
        "highest_total": highest_total,
        "lowest_all_out_total": lowest_all_out,
    }


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
    s = await _batting_aggregates(None, filters, aux)
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
    return out


@router.get("/{team}/batting/by-phase")
async def team_batting_by_phase(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _batting_by_phase_aggregates(team, filters, aux)
    s = await _batting_by_phase_aggregates(None, filters, aux)

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
          SUM(wide_runs) AS wides,
          SUM(noball_runs) AS noballs,
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

    return {
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
        "wides": r.get("wides") or 0,
        "noballs": r.get("noballs") or 0,
        "wides_per_match": _safe_div(r.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(r.get("noballs") or 0, matches, 1, 2),
        "avg_opposition_total": avg_opp_total,
        "worst_conceded": worst,
        "best_defence": best_defence,
    }


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
            SUM(d.extras_wides) as wides,
            SUM(d.extras_noballs) as noballs,
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

    return {
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
        "wides": c.get("wides") or 0,
        "noballs": c.get("noballs") or 0,
        "wides_per_match": _safe_div(c.get("wides") or 0, matches, 1, 2),
        "noballs_per_match": _safe_div(c.get("noballs") or 0, matches, 1, 2),
        "avg_opposition_total": avg_opp_total,
        "worst_conceded": worst,
        "best_defence": best_defence,
    }


async def _compute_bowling_summary(
    team: str,
    filters: FilterParams,
    aux: AuxParams,
) -> dict:
    """Per-metric envelope team-bowling summary."""
    t = await _bowling_aggregates(team, filters, aux)
    s = await _bowling_aggregates(None, filters, aux)
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
        "wides": wrap_metric(t["wides"], s["wides"], "wides", sample_size=matches),
        "noballs": wrap_metric(t["noballs"], s["noballs"], "noballs", sample_size=matches),
        # Per-match league rates halved to per-team-equivalent (each
        # match has 2 bowling sides; league total wides / matches
        # counts both teams' bowling).
        "wides_per_match": wrap_metric(t["wides_per_match"], _half(s["wides_per_match"]), "wides_per_match", sample_size=matches),
        "noballs_per_match": wrap_metric(t["noballs_per_match"], _half(s["noballs_per_match"]), "noballs_per_match", sample_size=matches),
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
    return out


@router.get("/{team}/bowling/by-phase")
async def team_bowling_by_phase(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _bowling_by_phase_aggregates(team, filters, aux)
    s = await _bowling_by_phase_aggregates(None, filters, aux)

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
    return {
        "matches": matches,
        "catches": catches_only,
        "caught_and_bowled": cnb,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches_only + cnb + stumpings + run_outs,
        "catches_per_match": _safe_div(catches_only + cnb, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }


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

    return {
        "matches": matches,
        "catches": catches,
        "caught_and_bowled": caught_and_bowled,
        "stumpings": stumpings,
        "run_outs": run_outs,
        "total_dismissals_contributed": catches + caught_and_bowled + stumpings + run_outs,
        "catches_per_match": _safe_div(catches + caught_and_bowled, matches, 1, 2),
        "stumpings_per_match": _safe_div(stumpings, matches, 1, 2),
        "run_outs_per_match": _safe_div(run_outs, matches, 1, 2),
    }


@router.get("/{team}/fielding/summary")
async def team_fielding_summary(
    team: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    t = await _fielding_aggregates(team, filters, aux)
    s = await _fielding_aggregates(None, filters, aux)
    matches = t.get("matches") or 0
    return {
        "team": team,
        "matches":             wrap_metric(t["matches"], s["matches"], "matches", sample_size=matches),
        "catches":             wrap_metric(t["catches"], s["catches"], "catches", sample_size=matches),
        "caught_and_bowled":   wrap_metric(t["caught_and_bowled"], s["caught_and_bowled"], "caught_and_bowled", sample_size=matches),
        "stumpings":           wrap_metric(t["stumpings"], s["stumpings"], "stumpings", sample_size=matches),
        "run_outs":            wrap_metric(t["run_outs"], s["run_outs"], "run_outs", sample_size=matches),
        "total_dismissals_contributed": wrap_metric(t["total_dismissals_contributed"], s["total_dismissals_contributed"], "total_dismissals_contributed", sample_size=matches),
        # per-match rates: scope_avg halved because the league pool
        # counts both fielding sides per match; the team-side
        # comparable is /2.
        "catches_per_match":   wrap_metric(t["catches_per_match"], _half(s["catches_per_match"]), "catches_per_match", sample_size=matches),
        "stumpings_per_match": wrap_metric(t["stumpings_per_match"], _half(s["stumpings_per_match"]), "stumpings_per_match", sample_size=matches),
        "run_outs_per_match":  wrap_metric(t["run_outs_per_match"], _half(s["run_outs_per_match"]), "run_outs_per_match", sample_size=matches),
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
            GROUP BY season ORDER BY season
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
                "catches": catches,
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
            **row,
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
        return {
            r["wicket_number"]: {
                "wicket_number": r["wicket_number"],
                "n": r["n"] or 0,
                "avg_runs": r["avg_runs"],
                "avg_balls": r["avg_balls"],
                "best_runs": r["best_runs"],
            }
            for r in bl_rows
        }

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
    return {r["wicket_number"]: r for r in rows}


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
    s = await _partnerships_by_wicket_aggregates(None, filters, side, aux)

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

    # Scope-avg counterpart — same query, team=None. Identity-bearing
    # nested objects (highest, best_pair) are dropped here; only the
    # numeric metrics are needed.
    s_where, s_params = _partnership_filter(filters, None, side, aux=aux)
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
    sa = s_rows[0] if s_rows else {}

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
