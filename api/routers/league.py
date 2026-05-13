"""League router — above-tournament scope dossier endpoints.

The League page (`/league` in the SPA) is the destination for scope
configurations that are broader than a single tournament — "men's club
cricket", "men's primary-tier clubs across all leagues", "women's
international ICC events", etc. It mirrors `TournamentDossier`
structurally (Overview / Batting / Bowling / Fielding tabs) but every
endpoint here drops the per-tournament restriction in favour of pure
FilterParams scoping.

The discipline subtabs reuse the existing `/api/v1/scope/averages/*`
endpoints (already pool-weighted at every FilterBar scope). This
router adds the three remaining payload shapes the spec calls out:

  - `/api/v1/league/overview`    — Overview composite (counts +
    top-teams + best-moments singletons).
  - `/api/v1/league/champions`   — cross-tournament unionized
    Champions table (Series-by-season's finals shape, unioned).
  - `/api/v1/league/leaders/{batting,bowling,fielding}` — top-N
    players in scope across the whole pool, paginated.

Spec: `internal_docs/spec-league-pages.md`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams
from .tournaments import (
    _tournament_scope_where, _inning_extras, _safe_div,
)

router = APIRouter(prefix="/api/v1/league", tags=["League"])


# ─── /league/overview ──────────────────────────────────────────────────

@router.get("/overview")
async def league_overview(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Composite Overview payload — counts strip, top teams, best moments.

    The Tournaments-in-scope tile grid uses the existing
    `/api/v1/series/landing` payload; the Champions table uses
    `/league/champions`. This endpoint covers the remaining four
    Overview blocks in a single roundtrip.

    Honours every FilterParams field (no tournament restriction —
    tournament-narrowed callers should be redirected to /series).
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament=None)
    inn_clause, inn_params = _inning_extras(aux)
    params.update(inn_params)

    # ── Headline counts ──
    meta_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) AS matches,
               COUNT(DISTINCT m.event_name) AS tournaments
        FROM match m
        WHERE {where}
        """,
        params,
    )
    meta = meta_rows[0] if meta_rows else {"matches": 0, "tournaments": 0}

    inn_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT i.id) AS innings
        FROM innings i
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        """,
        params,
    )
    innings = (inn_rows[0]["innings"] if inn_rows else 0) or 0

    teams_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.team1 AS team FROM match m WHERE {where}
          UNION
          SELECT m.team2 FROM match m WHERE {where}
        )
        SELECT COUNT(*) AS n FROM sides
        """,
        params,
    )
    teams_count = (teams_rows[0]["n"] if teams_rows else 0) or 0

    # ── Top teams by win % (decided matches only) ──
    # `decided` = matches with an outcome_winner (excludes ties/NR).
    # win_pct ranks teams; secondary sort by `played` so a 100%-win 2-
    # game team doesn't outrank a 60%-win 500-game team.
    top_teams_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.team1 AS team, m.id AS match_id,
                 m.outcome_winner, m.outcome_result
          FROM match m WHERE {where}
          UNION ALL
          SELECT m.team2, m.id, m.outcome_winner, m.outcome_result
          FROM match m WHERE {where}
        )
        SELECT team,
               COUNT(*) AS played,
               SUM(CASE WHEN outcome_winner = team THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN outcome_winner IS NOT NULL
                          AND outcome_winner != team THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN outcome_winner IS NOT NULL THEN 1 ELSE 0 END) AS decided
        FROM sides
        GROUP BY team
        HAVING played >= 5
        ORDER BY (CAST(SUM(CASE WHEN outcome_winner = team THEN 1 ELSE 0 END) AS REAL)
                  / NULLIF(SUM(CASE WHEN outcome_winner IS NOT NULL THEN 1 ELSE 0 END), 0)) DESC,
                 played DESC
        LIMIT 10
        """,
        params,
    )
    top_teams = [
        {
            "team": r["team"],
            "played": r["played"] or 0,
            "wins": r["wins"] or 0,
            "losses": r["losses"] or 0,
            "win_pct": _safe_div(r["wins"] or 0, r["decided"] or 0, 100, 1),
        }
        for r in top_teams_rows
    ]

    # ── Best moments — singleton from each record axis ──
    # Highest team total (innings-level)
    ht_rows = await db.q(
        f"""
        SELECT i.team, tot.total AS runs,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM (
          SELECT d.innings_id, SUM(d.runs_total) AS total
          FROM delivery d
          GROUP BY d.innings_id
        ) tot
        JOIN innings i ON i.id = tot.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        ORDER BY tot.total DESC
        LIMIT 1
        """,
        params,
    )
    highest_total = None
    if ht_rows:
        r = ht_rows[0]
        highest_total = {
            "team": r["team"], "runs": r["runs"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "opponent": r["opponent"],
            "date": r["date"],
        }

    # Lowest all-out total (10 wickets fell)
    lo_rows = await db.q(
        f"""
        WITH innings_totals AS (
          SELECT d.innings_id, SUM(d.runs_total) AS total,
                 (SELECT COUNT(*) FROM wicket w
                  JOIN delivery d2 ON d2.id = w.delivery_id
                  WHERE d2.innings_id = d.innings_id
                    AND w.kind NOT IN ('retired hurt', 'retired not out')) AS wkts
          FROM delivery d
          GROUP BY d.innings_id
        )
        SELECT i.team, it.total AS runs,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM innings_totals it
        JOIN innings i ON i.id = it.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND it.wkts >= 10 AND {where}{inn_clause}
        ORDER BY it.total ASC
        LIMIT 1
        """,
        params,
    )
    lowest_all_out = None
    if lo_rows:
        r = lo_rows[0]
        lowest_all_out = {
            "team": r["team"], "runs": r["runs"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "opponent": r["opponent"],
            "date": r["date"],
        }

    # Biggest win by runs
    bwr_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_runs AS margin,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_runs IS NOT NULL
        ORDER BY m.outcome_by_runs DESC
        LIMIT 1
        """,
        params,
    )
    biggest_win_runs = None
    if bwr_rows:
        r = bwr_rows[0]
        biggest_win_runs = {
            "winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "date": r["date"],
        }

    # Biggest win by wickets
    bww_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_wickets AS margin,
               m.id AS match_id, m.season AS season, m.event_name AS tournament,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_wickets IS NOT NULL
        ORDER BY m.outcome_by_wickets DESC, m.outcome_by_runs ASC
        LIMIT 1
        """,
        params,
    )
    biggest_win_wickets = None
    if bww_rows:
        r = bww_rows[0]
        biggest_win_wickets = {
            "winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"], "date": r["date"],
        }

    # Most sixes in a match
    ms_rows = await db.q(
        f"""
        SELECT m.id AS match_id, m.season AS season, m.event_name AS tournament,
               m.team1, m.team2,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}{inn_clause}
        GROUP BY m.id
        ORDER BY sixes DESC
        LIMIT 1
        """,
        params,
    )
    most_sixes_match = None
    if ms_rows:
        r = ms_rows[0]
        most_sixes_match = {
            "match_id": r["match_id"], "season": r["season"],
            "tournament": r["tournament"],
            "team1": r["team1"], "team2": r["team2"],
            "sixes": r["sixes"] or 0,
            "date": r["date"],
        }

    return {
        "matches": meta["matches"] or 0,
        "innings": innings,
        "teams_count": teams_count,
        "tournaments_count": meta["tournaments"] or 0,
        "top_teams": top_teams,
        "best_moments": {
            "highest_total": highest_total,
            "lowest_all_out": lowest_all_out,
            "biggest_win_runs": biggest_win_runs,
            "biggest_win_wickets": biggest_win_wickets,
            "most_sixes_match": most_sixes_match,
        },
    }
