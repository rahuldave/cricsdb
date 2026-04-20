"""Venues router — typeahead + country-grouped landing.

Two endpoints:

- GET /api/v1/venues — FilterBar typeahead. Optional `q` for substring
  match on venue or city. When `q` is absent, caps at top-50 by match
  count (so initial-focus dropdowns stay small). Respects all
  FilterParams ambient filters except `filter_venue` itself (self-
  referential: searching for venues while one is selected should still
  show all candidates).

- GET /api/v1/venues/landing — tile grid grouped by country. Countries
  ordered by total match count DESC; venues within a country by match
  count DESC. Filter-sensitive.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams, AuxParams

router = APIRouter(prefix="/api/v1/venues", tags=["Venues"])


def _strip_venue(
    filters: FilterParams,
    has_innings_join: bool = False,
    aux: AuxParams | None = None,
    **kwargs,
) -> tuple[str, dict]:
    """Run filters.build() with filter_venue temporarily cleared.

    Self-referential /venues endpoints shouldn't narrow to the currently-
    selected venue (typeahead/landing) or the dossier's own path-bound
    venue (summary pins m.venue explicitly, so compounding an ambient
    filter_venue from the URL would be a no-op at best and a mismatch
    at worst when the user arrived via a stale tile-click URL).
    """
    saved = filters.venue
    filters.venue = None
    try:
        return filters.build(has_innings_join=has_innings_join, aux=aux, **kwargs)
    finally:
        filters.venue = saved


@router.get("")
async def list_venues(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
    q: Optional[str] = Query(None, description="Substring match on venue name OR city, case-insensitive"),
    limit: int = Query(50, ge=1, le=500),
):
    """Scope-narrowed venue list for the FilterBar typeahead.

    Returns `{venues: [{venue, city, country, matches}, …]}` sorted by
    match count DESC. When `q` provided, matches substring against
    `venue` OR `city` (case-insensitive). When absent, caps at `limit`
    (default 50) so initial dropdown on focus is small.
    """
    db = get_db()
    where, params = _strip_venue(filters, aux=aux)

    clauses = ["m.venue IS NOT NULL"]
    if where:
        clauses.append(where)
    if q:
        clauses.append("(m.venue LIKE :q OR m.city LIKE :q)")
        params["q"] = f"%{q}%"

    params["limit"] = limit

    rows = await db.q(
        f"""
        SELECT m.venue          AS venue,
               m.city           AS city,
               m.venue_country  AS country,
               COUNT(DISTINCT m.id) AS matches
        FROM   match m
        WHERE  {" AND ".join(clauses)}
        GROUP  BY m.venue, m.city, m.venue_country
        ORDER  BY matches DESC, m.venue
        LIMIT  :limit
        """,
        params,
    )
    return {"venues": rows}


@router.get("/landing")
async def venues_landing(
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Country-grouped venue directory for the /venues landing page.

    Returns:
      {by_country: [{country, matches, venues: [{venue, city, matches}, …]}, …]}

    Countries ordered by total match count DESC; venues within a
    country ordered by match count DESC. `venue_country IS NULL` rows
    (shouldn't exist in a fully canonicalized DB but defensive) are
    bucketed under the `"Unknown"` country key.
    """
    db = get_db()
    where, params = _strip_venue(filters, aux=aux)

    clauses = ["m.venue IS NOT NULL"]
    if where:
        clauses.append(where)

    rows = await db.q(
        f"""
        SELECT COALESCE(m.venue_country, 'Unknown')  AS country,
               m.venue                                AS venue,
               m.city                                 AS city,
               COUNT(DISTINCT m.id)                   AS matches
        FROM   match m
        WHERE  {" AND ".join(clauses)}
        GROUP  BY m.venue_country, m.venue, m.city
        """,
        params,
    )

    # Bucket by country, accumulate totals
    by_country: dict[str, dict] = {}
    for r in rows:
        c = r["country"]
        bucket = by_country.setdefault(c, {"country": c, "matches": 0, "venues": []})
        bucket["matches"] += r["matches"]
        bucket["venues"].append({
            "venue":   r["venue"],
            "city":    r["city"],
            "matches": r["matches"],
        })

    # Sort venues within each country, then sort countries
    for bucket in by_country.values():
        bucket["venues"].sort(key=lambda v: (-v["matches"], v["venue"]))

    ordered = sorted(
        by_country.values(),
        key=lambda b: (-b["matches"], b["country"]),
    )
    return {"by_country": ordered}


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


@router.get("/{venue}/summary")
async def venue_summary(
    venue: str,
    filters: FilterParams = Depends(),
    aux: AuxParams = Depends(),
):
    """Venue-character overview bundle for the Phase-3 dossier.

    Pins `m.venue = :venue` from the path and strips any ambient
    `filter_venue` from the FilterBar (see _strip_venue's docstring on
    why). Every other FilterParams field (gender, team_type, tournament,
    season window, filter_team / filter_opponent) is honoured so the
    Overview tab narrows to e.g. "men's IPL 2023 at Wankhede".

    Returns a single payload covering the six Overview sections: meta,
    matches-by-tournament × gender × season, first-innings average,
    bat-first vs chase win %, toss decision split + win correlations,
    boundary + dot % per phase, highest team total, lowest all-out.

    404 if no matches exist in scope.
    """
    db = get_db()

    # Match-level clause (no delivery join) — used for every match-scan
    # query below.
    match_where, match_params = _strip_venue(filters, has_innings_join=False, aux=aux)
    match_params["venue"] = venue
    clauses_m = ["m.venue = :venue"]
    if match_where:
        clauses_m.append(match_where)
    where_m = " AND ".join(clauses_m)

    # Delivery-level clause — same filters with the innings join (for
    # super_over exclusion).
    d_where, d_params = _strip_venue(filters, has_innings_join=True, aux=aux)
    d_params["venue"] = venue
    clauses_d = ["m.venue = :venue"]
    if d_where:
        clauses_d.append(d_where)
    where_d = " AND ".join(clauses_d)

    # 1. Meta + total match count (also drives 404).
    meta_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id)         AS matches,
               MAX(m.city)                  AS city,
               MAX(m.venue_country)         AS country
        FROM   match m
        WHERE  {where_m}
        """,
        match_params,
    )
    meta = meta_rows[0] if meta_rows else {}
    matches = meta.get("matches", 0) or 0
    if matches == 0:
        raise HTTPException(status_code=404, detail=f"Venue not found: {venue}")

    # 2. by_tournament × gender × season. event_name IS NULL rows
    # bucket under "—" so the row still appears (a bilateral friendly
    # at the venue still counts).
    bg_rows = await db.q(
        f"""
        SELECT COALESCE(m.event_name, '—')  AS tournament,
               m.gender                      AS gender,
               m.season                      AS season,
               COUNT(*)                      AS matches
        FROM   match m
        WHERE  {where_m}
        GROUP  BY m.event_name, m.gender, m.season
        ORDER  BY m.season DESC, tournament, m.gender
        """,
        match_params,
    )
    by_tournament_gender_season = [
        {
            "tournament": r["tournament"],
            "gender": r["gender"],
            "season": r["season"],
            "matches": r["matches"],
        }
        for r in bg_rows
    ]

    # 3. Avg first-innings total + bat-first / chase / tie+NR split.
    #   Innings 0 is the first innings (0-indexed in our schema); super
    #   overs excluded. `first` subquery sums runs per first-innings.
    #   Join back to match to attach outcome + team-batting-first.
    bf_rows = await db.q(
        f"""
        SELECT AVG(first.total)  AS avg_first_innings_total,
               SUM(CASE WHEN m.outcome_winner = first.team  THEN 1 ELSE 0 END) AS bat_first_wins,
               SUM(CASE WHEN m.outcome_winner IS NOT NULL
                         AND m.outcome_winner != first.team  THEN 1 ELSE 0 END) AS chase_wins,
               SUM(CASE WHEN m.outcome_result IN ('tie', 'no result')
                         OR m.outcome_winner IS NULL        THEN 1 ELSE 0 END) AS indecisive,
               COUNT(*) AS n
        FROM   (
                   SELECT i.match_id          AS match_id,
                          i.team              AS team,
                          SUM(d.runs_total)   AS total
                   FROM   innings i
                   JOIN   delivery d ON d.innings_id = i.id
                   JOIN   match m   ON m.id = i.match_id
                   WHERE  i.innings_number = 0
                     AND  i.super_over = 0
                     AND  {where_m}
                   GROUP  BY i.match_id, i.team
               ) first
        JOIN   match m ON m.id = first.match_id
        """,
        match_params,
    )
    bf = bf_rows[0] if bf_rows else {}
    n = bf.get("n", 0) or 0
    avg_first = bf.get("avg_first_innings_total")
    bat_first_wins = bf.get("bat_first_wins", 0) or 0
    chase_wins = bf.get("chase_wins", 0) or 0
    indecisive = bf.get("indecisive", 0) or 0

    # 4. Toss-decision split.
    td_rows = await db.q(
        f"""
        SELECT m.toss_decision AS decision, COUNT(*) AS n
        FROM   match m
        WHERE  {where_m} AND m.toss_decision IS NOT NULL
        GROUP  BY m.toss_decision
        """,
        match_params,
    )
    toss_decision_split = {r["decision"]: r["n"] for r in td_rows}

    # 5. Toss-and-win correlation: of matches where toss winner chose to
    # bat, what % did the toss winner go on to win? And same for field.
    tw_rows = await db.q(
        f"""
        SELECT m.toss_decision AS decision,
               SUM(CASE WHEN m.outcome_winner = m.toss_winner THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN m.outcome_winner IS NOT NULL THEN 1 ELSE 0 END)     AS decided
        FROM   match m
        WHERE  {where_m}
          AND  m.toss_winner IS NOT NULL
          AND  m.toss_decision IS NOT NULL
        GROUP  BY m.toss_decision
        """,
        match_params,
    )
    toss_and_win: dict[str, dict] = {}
    for r in tw_rows:
        toss_and_win[r["decision"]] = {
            "wins": r["wins"] or 0,
            "decided": r["decided"] or 0,
            "win_pct": _safe_div((r["wins"] or 0) * 100, r["decided"] or 0, 1, 1),
        }

    # 6. Boundary % + dot % per phase. Same SQL-overs bucketing the app
    # uses everywhere (powerplay = 0-5, middle = 6-14, death = 15-19).
    phase_rows = await db.q(
        f"""
        SELECT CASE
                 WHEN d.over_number BETWEEN 0 AND 5 THEN 'powerplay'
                 WHEN d.over_number BETWEEN 6 AND 14 THEN 'middle'
                 WHEN d.over_number BETWEEN 15 AND 19 THEN 'death'
               END AS phase,
               COUNT(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 END) AS legal_balls,
               SUM(CASE WHEN d.runs_batter = 4
                         AND COALESCE(d.runs_non_boundary, 0) = 0 THEN 1 ELSE 0 END)    AS fours,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END)                        AS sixes,
               SUM(CASE WHEN d.runs_total = 0
                         AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots
        FROM   delivery d
        JOIN   innings i ON i.id = d.innings_id
        JOIN   match m   ON m.id = i.match_id
        WHERE  {where_d}
        GROUP  BY phase
        """,
        d_params,
    )
    boundary_pct_by_phase: dict[str, float | None] = {"powerplay": None, "middle": None, "death": None}
    dot_pct_by_phase: dict[str, float | None] = {"powerplay": None, "middle": None, "death": None}
    for r in phase_rows:
        phase = r["phase"]
        if phase not in boundary_pct_by_phase:
            continue
        legal = r["legal_balls"] or 0
        boundary_pct_by_phase[phase] = _safe_div(
            (r["fours"] or 0) + (r["sixes"] or 0), legal, 100, 1
        )
        dot_pct_by_phase[phase] = _safe_div(r["dots"] or 0, legal, 100, 1)

    # 7. Highest team total (any innings) + lowest all-out.
    #   `innings_totals` aggregates runs per innings in scope, joined to
    #   match so we can pick team / opponent / date / season back out.
    #   Lowest all-out additionally requires the innings to have ended
    #   on a wicket count = 10 (all out).
    highest_rows = await db.q(
        f"""
        SELECT it.total    AS runs,
               it.team     AS team,
               CASE WHEN m.team1 = it.team THEN m.team2 ELSE m.team1 END AS opponent,
               m.id        AS match_id,
               m.season    AS season,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) AS date
        FROM   (
                   SELECT i.match_id, i.team, SUM(d.runs_total) AS total
                   FROM   innings i
                   JOIN   delivery d ON d.innings_id = i.id
                   JOIN   match m ON m.id = i.match_id
                   WHERE  i.super_over = 0 AND {where_m}
                   GROUP  BY i.id
               ) it
        JOIN   match m ON m.id = it.match_id
        ORDER  BY it.total DESC, m.id
        LIMIT  1
        """,
        match_params,
    )
    highest_total = highest_rows[0] if highest_rows else None

    lowest_rows = await db.q(
        f"""
        SELECT it.total    AS runs,
               it.team     AS team,
               CASE WHEN m.team1 = it.team THEN m.team2 ELSE m.team1 END AS opponent,
               m.id        AS match_id,
               m.season    AS season,
               (SELECT MIN(date) FROM matchdate md WHERE md.match_id = m.id) AS date
        FROM   (
                   SELECT i.id          AS innings_id,
                          i.match_id    AS match_id,
                          i.team        AS team,
                          SUM(d.runs_total) AS total,
                          (SELECT COUNT(*)
                             FROM wicket w
                             JOIN delivery d2 ON d2.id = w.delivery_id
                             WHERE d2.innings_id = i.id
                               AND w.kind NOT IN ('retired hurt', 'retired not out')
                          ) AS wkts
                   FROM   innings i
                   JOIN   delivery d ON d.innings_id = i.id
                   JOIN   match m ON m.id = i.match_id
                   WHERE  i.super_over = 0 AND {where_m}
                   GROUP  BY i.id
               ) it
        JOIN   match m ON m.id = it.match_id
        WHERE  it.wkts >= 10
        ORDER  BY it.total ASC, m.id
        LIMIT  1
        """,
        match_params,
    )
    lowest_all_out = lowest_rows[0] if lowest_rows else None

    return {
        "venue": venue,
        "city": meta.get("city"),
        "country": meta.get("country"),
        "matches": matches,
        "by_tournament_gender_season": by_tournament_gender_season,
        "avg_first_innings_total": round(avg_first, 1) if avg_first is not None else None,
        "first_innings_sample": n,
        "bat_first_wins": bat_first_wins,
        "chase_wins": chase_wins,
        "indecisive": indecisive,
        "bat_first_win_pct": _safe_div(bat_first_wins * 100, n, 1, 1),
        "chase_win_pct": _safe_div(chase_wins * 100, n, 1, 1),
        "toss_decision_split": toss_decision_split,
        "toss_and_win_pct": toss_and_win,
        "boundary_pct_by_phase": boundary_pct_by_phase,
        "dot_pct_by_phase": dot_pct_by_phase,
        "highest_total": highest_total,
        "lowest_all_out": lowest_all_out,
    }
