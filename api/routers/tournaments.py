"""Series router — tournament & bilateral-rivalry rollups.

Cricket has two shapes of "series": a tournament-season (IPL 2024, a
T20 World Cup edition) and a bilateral series (India's tour of
Australia 2024). This router serves both under the common `/series/`
namespace so the UI can treat them interchangeably. The FilterBar's
Tournament dropdown still selects a cricsheet `event_name` — the
`/series/` prefix exists specifically to disambiguate the landing /
dossier catalog from that filter.

- `/series/landing`    — sectioned directory (ICC / franchise /
  domestic / women / rivalries) for the search landing.
- `/series/summary`    — headline numbers for one series.
- `/series/by-season`  — per-edition rollup (champion, top scorer…).
- `/series/points-table` — reconstructed league-stage standings + NRR.
  Visible only when a single season is in scope.
- `/series/records`    — highest totals, biggest wins, best bowling, …
- `/series/other-rivalries` — lazy-loaded rivalry list for pairs
  outside the default top-9 grid.
- `/rivalries/summary` — synthesized bilateral rivalry dossier
  (legacy path, kept at /rivalries/summary for external callers).

Canonicalization:
  Cricsheet's `event_name` has drift — the men's T20 World Cup lives
  under three names across its history. The TOURNAMENT_CANONICAL map
  merges variants into a single display name. Variants expand back to
  a SQL `event_name IN (...)` clause via `event_name_in_clause`.

  NOTE: Canonical names apply to this router only. FilterParams on
  other routes treats `tournament` as a literal cricsheet event_name.
  That's why the endpoints here skip `filters.tournament` and accept
  their own `tournament` Query param.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams
from ..tournament_canonical import (
    TOURNAMENT_CANONICAL, TOURNAMENT_SERIES_TYPE,
    ICC_EVENT_NAMES, BILATERAL_TOP_TEAMS,
    canonicalize, variants, event_name_in_clause, series_type,
    series_type_clause as _series_type_clause,
)

router = APIRouter(prefix="/api/v1", tags=["Series"])


def _build_filter_clauses(
    filters: FilterParams,
    alias: str = "m",
    include_tournament: bool = False,
    include_team_pair: bool = True,
) -> tuple[list[str], dict]:
    """Build per-field WHERE clauses from FilterParams.

    Tournament is skipped by default — the tournaments router handles
    it specially via canonical → variants expansion. team / opponent
    are included when both set (rivalry scope) or individually.
    """
    clauses: list[str] = []
    params: dict = {}
    if filters.gender:
        clauses.append(f"{alias}.gender = :gender")
        params["gender"] = filters.gender
    if filters.team_type:
        clauses.append(f"{alias}.team_type = :team_type")
        params["team_type"] = filters.team_type
    if include_tournament and filters.tournament:
        clauses.append(f"{alias}.event_name = :tournament")
        params["tournament"] = filters.tournament
    if filters.season_from:
        clauses.append(f"{alias}.season >= :season_from")
        params["season_from"] = filters.season_from
    if filters.season_to:
        clauses.append(f"{alias}.season <= :season_to")
        params["season_to"] = filters.season_to
    if filters.venue:
        clauses.append(f"{alias}.venue = :filter_venue")
        params["filter_venue"] = filters.venue
    if include_team_pair:
        if filters.team:
            clauses.append(f"({alias}.team1 = :filter_team OR {alias}.team2 = :filter_team)")
            params["filter_team"] = filters.team
        if filters.opponent:
            clauses.append(f"({alias}.team1 = :filter_opp OR {alias}.team2 = :filter_opp)")
            params["filter_opp"] = filters.opponent
    return clauses, params


def _t20_match_clause(alias: str = "m") -> str:
    """Restrict to T20/IT20 matches (the only format we cover)."""
    return f"{alias}.match_type IN ('T20', 'IT20')"


# ─── Landing endpoint ─────────────────────────────────────────────────


@router.get("/series/landing")
async def tournaments_landing(filters: FilterParams = Depends()):
    """Sectioned directory of tournaments + bilateral rivalries.

    Left (international):
      - ICC events (T20 World Cup, Asia Cup, etc.) — canonicalized.
      - Bilateral rivalries among the top-9 men's teams (36 tiles by
        default); plus a pointer to the expandable "other rivalries"
        list fetched separately.

    Right (club):
      - Franchise leagues (IPL, BBL, PSL, …).
      - Domestic leagues (Vitality Blast, Syed Mushtaq Ali, …).
      - Women's franchise (WBBL, WPL, The Hundred Women's, …).
      - Other (unclassified, long tail).

    All counts honour FilterBar (gender / team_type / season_from / to).
    """
    db = get_db()
    base_clauses, params = _build_filter_clauses(filters)
    base_clauses.append(_t20_match_clause())

    # ── Tournament aggregates (by raw event_name, then canonicalized) ──
    tournament_where = " AND ".join(
        ["m.event_name IS NOT NULL"] + base_clauses
    )

    rows = await db.q(
        f"""
        SELECT m.event_name AS ev,
               COUNT(*) AS matches,
               COUNT(DISTINCT m.season) AS editions
        FROM match m
        WHERE {tournament_where}
        GROUP BY m.event_name
        """,
        params,
    )

    # Merge variants into canonical display names.
    canon_agg: dict[str, dict] = {}
    for r in rows:
        canon = canonicalize(r["ev"])
        entry = canon_agg.setdefault(
            canon,
            {"canonical": canon, "matches": 0, "editions_seasons": set(),
             "team_type": None, "genders": set()},
        )
        entry["matches"] += r["matches"] or 0

    # Editions count = distinct seasons across variants. Re-query per
    # canonical in one pass to collect season sets.
    season_rows = await db.q(
        f"""
        SELECT m.event_name AS ev, m.season AS season
        FROM match m
        WHERE {tournament_where}
        GROUP BY m.event_name, m.season
        """,
        params,
    )
    for r in season_rows:
        canon = canonicalize(r["ev"])
        canon_agg[canon]["editions_seasons"].add(r["season"])

    # team_type + gender per canonical — used by landing tiles so clicks
    # into a dossier URL carry the implicit FilterBar state, avoiding
    # the "self-correcting deep link" flash when the FilterBar sees a
    # canonical name that doesn't match any cricsheet event_name.
    type_rows = await db.q(
        f"""
        SELECT m.event_name AS ev, m.team_type AS team_type, m.gender AS gender
        FROM match m
        WHERE {tournament_where}
        GROUP BY m.event_name, m.team_type, m.gender
        """,
        params,
    )
    for r in type_rows:
        canon = canonicalize(r["ev"])
        existing = canon_agg[canon]["team_type"]
        if existing is None or r["team_type"] == "international":
            canon_agg[canon]["team_type"] = r["team_type"]
        if r["gender"]:
            canon_agg[canon]["genders"].add(r["gender"])

    # ── Champions / most-titles / latest edition per canonical ──
    finals_where = " AND ".join(
        ["m.event_name IS NOT NULL", "m.event_stage = 'Final'", "m.outcome_winner IS NOT NULL"] + base_clauses
    )
    finals_rows = await db.q(
        f"""
        SELECT m.event_name AS ev, m.season AS season,
               m.outcome_winner AS winner
        FROM match m
        WHERE {finals_where}
        """,
        params,
    )
    # canonical → list of (season, winner)
    canon_finals: dict[str, list[tuple[str, str]]] = {}
    for r in finals_rows:
        canon = canonicalize(r["ev"])
        canon_finals.setdefault(canon, []).append((r["season"], r["winner"]))

    def _most_titles(items: list[tuple[str, str]]) -> Optional[dict]:
        if not items:
            return None
        counts: dict[str, int] = {}
        for _, w in items:
            counts[w] = counts.get(w, 0) + 1
        team, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        return {"team": team, "titles": n}

    def _latest_edition(items: list[tuple[str, str]]) -> Optional[dict]:
        if not items:
            return None
        season, winner = max(items, key=lambda sw: sw[0])  # season strings sort chronologically
        return {"season": season, "champion": winner}

    # ── Build landing entries ──
    def _entry(canon: str, agg: dict) -> dict:
        finals = canon_finals.get(canon, [])
        genders = agg.get("genders") or set()
        gender = next(iter(genders)) if len(genders) == 1 else None
        return {
            "canonical": canon,
            "editions": len(agg["editions_seasons"]),
            "matches": agg["matches"],
            "most_titles": _most_titles(finals),
            "latest_edition": _latest_edition(finals),
            "team_type": agg.get("team_type"),
            "gender": gender,
        }

    # Bucket into sections. Respect team_type filter if user forced one.
    # International split: classified ICC events (prominent) vs. the long
    # tail (regional qualifiers, tri-series, minor continental events)
    # which gets a collapsible "other international" bucket so rivalries
    # aren't buried.
    icc_events: list[dict] = []
    other_international: list[dict] = []
    franchise_leagues: list[dict] = []
    domestic_leagues: list[dict] = []
    women_franchise: list[dict] = []
    other_club: list[dict] = []

    for canon, agg in canon_agg.items():
        e = _entry(canon, agg)
        stype = series_type(canon)
        ttype = agg["team_type"]
        if ttype == "international":
            if stype == "icc_event":
                icc_events.append(e)
            else:
                other_international.append(e)
        else:
            if stype == "franchise_league":
                franchise_leagues.append(e)
            elif stype == "domestic_league":
                domestic_leagues.append(e)
            elif stype == "women_franchise":
                women_franchise.append(e)
            else:
                other_club.append(e)

    # Sort each section by match count desc (primary) then name
    for section in (icc_events, other_international, franchise_leagues,
                    domestic_leagues, women_franchise, other_club):
        section.sort(key=lambda x: (-x["matches"], x["canonical"]))

    # ── Bilateral rivalries (top-9 men's teams) — split by gender so
    # the user can see "India v Australia (men's)" and "India v
    # Australia (women's)" as separate tiles. Each tile counts only
    # bilateral series (no ICC event meetings).
    rivalries_men: list[dict] = []
    rivalries_women: list[dict] = []
    other_count_men = 0
    other_count_women = 0

    show_men = filters.gender != "female" and filters.team_type != "club"
    show_women = filters.gender != "male" and filters.team_type != "club"

    if show_men:
        rivalries_men, other_count_men = await _rivalries_top_and_other_count(
            db, filters, gender="male",
        )
    if show_women:
        rivalries_women, other_count_women = await _rivalries_top_and_other_count(
            db, filters, gender="female",
        )

    # Club rivalries — top team-pair matchups within franchise/domestic
    # leagues. Drives the H2H Team-vs-Team mode's club suggestions
    # alongside the international rivalries.
    club_rivalries_men: list[dict] = []
    club_rivalries_women: list[dict] = []
    show_club_men = filters.gender != "female" and filters.team_type != "international"
    show_club_women = filters.gender != "male" and filters.team_type != "international"
    if show_club_men:
        club_rivalries_men = await _top_club_rivalries(db, filters, gender="male", limit=12)
    if show_club_women:
        club_rivalries_women = await _top_club_rivalries(db, filters, gender="female", limit=12)

    return {
        "international": {
            "icc_events": icc_events,
            "bilateral_rivalries": {
                "men": {"top": rivalries_men, "other_count": other_count_men},
                "women": {"top": rivalries_women, "other_count": other_count_women},
                "other_threshold": 5,
            },
            "other_international": other_international,
        },
        "club": {
            "franchise_leagues": franchise_leagues,
            "domestic_leagues": domestic_leagues,
            "women_franchise": women_franchise,
            "other": other_club,
            "rivalries": {
                "men": club_rivalries_men,
                "women": club_rivalries_women,
            },
        },
    }


async def _top_club_rivalries(
    db, filters: FilterParams, gender: str, limit: int = 12,
) -> list[dict]:
    """Top-N most-played team pairs within club tournaments. Used by
    the H2H Team-vs-Team page's club suggestion tiles. Each entry
    includes the dominant tournament for context (a pair like
    "RCB v CSK" is unambiguously IPL — no ICC-event mixing here)."""
    clauses = [
        _t20_match_clause(),
        "m.team_type = 'club'",
        f"m.gender = '{gender}'",
    ]
    if filters.season_from:
        clauses.append("m.season >= :season_from")
    if filters.season_to:
        clauses.append("m.season <= :season_to")
    where = " AND ".join(clauses)
    params: dict = {}
    if filters.season_from:
        params["season_from"] = filters.season_from
    if filters.season_to:
        params["season_to"] = filters.season_to
    params["lim"] = limit

    rows = await db.q(
        f"""
        WITH p AS (
          SELECT CASE WHEN m.team1 < m.team2 THEN m.team1 ELSE m.team2 END AS a,
                 CASE WHEN m.team1 < m.team2 THEN m.team2 ELSE m.team1 END AS b,
                 m.event_name AS tournament,
                 m.outcome_winner AS winner,
                 m.outcome_result AS result
          FROM match m
          WHERE {where}
        )
        SELECT a, b, tournament,
               COUNT(*) AS matches,
               SUM(CASE WHEN winner = a THEN 1 ELSE 0 END) AS a_wins,
               SUM(CASE WHEN winner = b THEN 1 ELSE 0 END) AS b_wins,
               SUM(CASE WHEN result = 'tie' THEN 1 ELSE 0 END) AS ties,
               SUM(CASE WHEN result = 'no result' THEN 1 ELSE 0 END) AS no_result
        FROM p
        GROUP BY a, b, tournament
        ORDER BY matches DESC, a, b
        LIMIT :lim
        """,
        params,
    )
    return [
        {
            "team1": r["a"], "team2": r["b"],
            "tournament": r["tournament"],
            "matches": r["matches"],
            "team1_wins": r["a_wins"], "team2_wins": r["b_wins"],
            "ties": r["ties"], "no_result": r["no_result"],
        }
        for r in rows
    ]


async def _rivalries_top_and_other_count(
    db, filters: FilterParams, gender: str,
) -> tuple[list[dict], int]:
    """Compute the 36 default rivalries (top-9 men's-or-women's pairs)
    plus the count of "other" pairs (involving non-top-9 teams) with
    ≥ 5 matches. Counts are bilateral-only — pure bilateral series,
    excluding ICC-event meetings.

    `gender` must be 'male' or 'female'. National women's teams use the
    same team-string as men's in cricsheet, so the same top-9 list applies.
    """
    rivalry_clauses = [
        _t20_match_clause(),
        "m.team_type = 'international'",
        f"m.gender = '{gender}'",
    ]
    if filters.season_from:
        rivalry_clauses.append("m.season >= :season_from")
    if filters.season_to:
        rivalry_clauses.append("m.season <= :season_to")
    # Bilateral-only — exclude ICC events.
    bi_clause = _series_type_clause("bilateral_only")
    if bi_clause:
        rivalry_clauses.append(bi_clause)

    params: dict = {}
    if filters.season_from:
        params["season_from"] = filters.season_from
    if filters.season_to:
        params["season_to"] = filters.season_to

    top_teams_clause = event_name_in_clause(BILATERAL_TOP_TEAMS, col="m.team1")
    top_teams_clause2 = event_name_in_clause(BILATERAL_TOP_TEAMS, col="m.team2")

    # Aggregate per unordered pair.
    rivalry_where = " AND ".join(rivalry_clauses + [top_teams_clause, top_teams_clause2])
    rows = await db.q(
        f"""
        WITH p AS (
          SELECT CASE WHEN m.team1 < m.team2 THEN m.team1 ELSE m.team2 END AS a,
                 CASE WHEN m.team1 < m.team2 THEN m.team2 ELSE m.team1 END AS b,
                 m.outcome_winner AS winner,
                 m.outcome_result AS result,
                 m.id AS match_id
          FROM match m
          WHERE {rivalry_where}
        )
        SELECT a, b,
               COUNT(*) AS matches,
               SUM(CASE WHEN winner = a THEN 1 ELSE 0 END) AS a_wins,
               SUM(CASE WHEN winner = b THEN 1 ELSE 0 END) AS b_wins,
               SUM(CASE WHEN result = 'tie' THEN 1 ELSE 0 END) AS ties,
               SUM(CASE WHEN result = 'no result' THEN 1 ELSE 0 END) AS no_result
        FROM p
        GROUP BY a, b
        """,
        params,
    )

    # Latest match per pair — intentionally NOT bilateral-only. The home
    # tile's "Latest" line surfaces the most recent meeting between the
    # two teams regardless of series type ("be that a WC or a
    # bilateral"), so a WC 2024 final beats a 2023 bilateral. The pair
    # counts above stay bilateral-only (that's what the headline number
    # represents); the latest_match payload carries `tournament` +
    # `season` so the frontend can scope the click correctly.
    latest_clauses = [
        _t20_match_clause(),
        "m.team_type = 'international'",
        f"m.gender = '{gender}'",
    ]
    if filters.season_from:
        latest_clauses.append("m.season >= :season_from")
    if filters.season_to:
        latest_clauses.append("m.season <= :season_to")
    latest_where = " AND ".join(latest_clauses + [top_teams_clause, top_teams_clause2])
    latest_rows = await db.q(
        f"""
        WITH p AS (
          SELECT CASE WHEN m.team1 < m.team2 THEN m.team1 ELSE m.team2 END AS a,
                 CASE WHEN m.team1 < m.team2 THEN m.team2 ELSE m.team1 END AS b,
                 m.id AS match_id,
                 m.outcome_winner AS winner,
                 m.event_name AS event_name,
                 m.season AS season,
                 (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS d
          FROM match m
          WHERE {latest_where}
        )
        SELECT a, b, match_id, winner, event_name, season, d
        FROM p
        WHERE d = (SELECT MAX(d2.d) FROM (
            SELECT CASE WHEN m2.team1 < m2.team2 THEN m2.team1 ELSE m2.team2 END AS a2,
                   CASE WHEN m2.team1 < m2.team2 THEN m2.team2 ELSE m2.team1 END AS b2,
                   (SELECT MIN(date) FROM matchdate WHERE match_id = m2.id) AS d
            FROM match m2
            WHERE {latest_where.replace('m.', 'm2.')}
          ) d2 WHERE d2.a2 = p.a AND d2.b2 = p.b)
        """,
        params,
    )
    latest_by_pair: dict[tuple[str, str], dict] = {}
    for r in latest_rows:
        # Classify the meeting's series-type. `canonicalize()` returns the
        # raw event_name when no alias exists, so we can't use its output
        # alone — bilateral tours carry event_names like "Pakistan tour
        # of New Zealand" that aren't canonical tournaments. Treat a
        # match as a recognized tournament only when its canonical name
        # is in ICC_EVENT_NAMES; everything else (tours, unlisted one-
        # offs, NULL event_name) reports as tournament=None so the
        # frontend knows to render the "Latest" link as a bilateral-
        # scoped series view.
        canon = canonicalize(r["event_name"])
        tournament = canon if canon in ICC_EVENT_NAMES else None
        latest_by_pair.setdefault((r["a"], r["b"]), {
            "match_id": r["match_id"],
            "date": r["d"],
            "winner": r["winner"],
            "tournament": tournament,
            "season": r["season"],
        })

    rivalries: list[dict] = []
    for r in rows:
        key = (r["a"], r["b"])
        rivalries.append({
            "team1": r["a"],
            "team2": r["b"],
            "matches": r["matches"],
            "team1_wins": r["a_wins"],
            "team2_wins": r["b_wins"],
            "ties": r["ties"],
            "no_result": r["no_result"],
            "latest_match": latest_by_pair.get(key),
        })
    rivalries.sort(key=lambda x: (-x["matches"], x["team1"], x["team2"]))

    # ── "Other" pair count — pairs involving at least one non-top-9 team, with ≥ 5 matches ──
    other_where = " AND ".join(rivalry_clauses + [
        f"NOT ({top_teams_clause} AND {top_teams_clause2})"
    ])
    other_rows = await db.q(
        f"""
        WITH p AS (
          SELECT CASE WHEN m.team1 < m.team2 THEN m.team1 ELSE m.team2 END AS a,
                 CASE WHEN m.team1 < m.team2 THEN m.team2 ELSE m.team1 END AS b
          FROM match m
          WHERE {other_where}
        )
        SELECT COUNT(*) AS n FROM (
          SELECT a, b FROM p GROUP BY a, b HAVING COUNT(*) >= 5
        )
        """,
        params,
    )
    other_count = other_rows[0]["n"] if other_rows else 0

    return rivalries, other_count


# ─── Per-tournament endpoints ─────────────────────────────────────────


def _tournament_scope_where(
    filters: FilterParams,
    tournament: str | None,
    alias: str = "m",
    series_type: str | None = None,
) -> tuple[str, dict]:
    """Build WHERE clause for a match-set scope.

    The match-set is defined by:
      - tournament (optional canonical name → IN variants)
      - filter_team / filter_opponent (FilterParams; 0, 1, or 2 may be set)
      - series_type ('all' / 'bilateral_only' / 'tournament_only')
      - other FilterParams (gender, team_type, season range)

    When tournament is None and no other filters apply, the WHERE is
    just `match_type IN ('T20','IT20')` — i.e. the whole T20 universe.
    Useful for cross-cutting team-pair queries (rivalry across all
    tournaments) and for the H2H Team-vs-Team mode.
    """
    clauses, params = _build_filter_clauses(filters, alias=alias)
    if tournament:
        clauses.append(event_name_in_clause(variants(tournament), col=f"{alias}.event_name"))
    st_clause = _series_type_clause(series_type, alias=alias)
    if st_clause:
        clauses.append(st_clause)
    clauses.append(_t20_match_clause(alias))
    return " AND ".join(clauses), params


def _safe_div(a, b, mul=1, ndigits=2):
    if not b:
        return None
    return round(a * mul / b, ndigits)


@router.get("/series/summary")
async def tournament_summary(
    tournament: str | None = Query(None, description="Canonical tournament name (optional)"),
    series_type: str | None = Query(None, description="all / bilateral_only / tournament_only"),
    filters: FilterParams = Depends(),
):
    """Headline numbers for a match-set scope.

    The match-set is defined by tournament (optional canonical name),
    series_type (bilateral-only / tournament-only), and FilterParams
    including filter_team / filter_opponent for rivalry scope. All four
    optional — empty scope = all T20s.

    When filter_team + filter_opponent are both set, the response also
    includes `*_by_team` companion fields breaking down records per
    team in the matchup. Reusable for enhancement O baselines.
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)
    vs = variants(tournament) if tournament else []

    # ── Basic aggregates ──
    meta_rows = await db.q(
        f"""
        SELECT COUNT(DISTINCT m.id) AS matches,
               COUNT(DISTINCT m.season) AS editions
        FROM match m
        WHERE {where}
        """,
        params,
    )
    meta = meta_rows[0] if meta_rows else {"matches": 0, "editions": 0}

    # Delivery-level aggregates (runs, wickets, sixes, rates)
    bat_rows = await db.q(
        f"""
        SELECT SUM(d.runs_total) AS total_runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
               SUM(CASE WHEN d.runs_batter = 4 AND (d.runs_non_boundary IS NULL OR d.runs_non_boundary = 0) THEN 1 ELSE 0 END) AS fours,
               SUM(CASE WHEN d.runs_total = 0 AND d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS dots
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        """,
        params,
    )
    b = bat_rows[0] if bat_rows else {}
    total_runs = b.get("total_runs") or 0
    legal_balls = b.get("legal_balls") or 0
    sixes = b.get("sixes") or 0
    fours = b.get("fours") or 0
    dots = b.get("dots") or 0

    wkt_rows = await db.q(
        f"""
        SELECT COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        """,
        params,
    )
    total_wickets = wkt_rows[0]["wickets"] if wkt_rows else 0

    # ── Champions + most-titles ──
    finals_rows = await db.q(
        f"""
        SELECT m.season AS season, m.outcome_winner AS winner, m.id AS match_id
        FROM match m
        WHERE {where} AND m.event_stage = 'Final' AND m.outcome_winner IS NOT NULL
        ORDER BY m.season DESC
        """,
        params,
    )
    champions_by_season = [
        {"season": r["season"], "champion": r["winner"], "match_id": r["match_id"]}
        for r in finals_rows
    ]
    title_counts: dict[str, int] = {}
    for r in finals_rows:
        title_counts[r["winner"]] = title_counts.get(r["winner"], 0) + 1
    most_titles = None
    if title_counts:
        team, n = max(title_counts.items(), key=lambda kv: (kv[1], kv[0]))
        most_titles = {"team": team, "titles": n}

    # ── Top scorer all-time (in this tournament scope) ──
    #
    # `team` is needed so the frontend StatCard can orient the rivalry
    # phrase correctly on rivalry scope (a batter playing FOR India
    # should read "vs Australia", not "vs India"). SQLite's bare-column
    # GROUP BY returns an arbitrary team from the batter's innings in
    # scope — deterministic for rivalry (one team per batter) and
    # informational for non-rivalry multi-team scope.
    ts_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id, p.name, i.team AS team,
               SUM(d.runs_batter) AS runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE i.super_over = 0 AND {where}
          AND d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id
        ORDER BY runs DESC
        LIMIT 1
        """,
        params,
    )
    top_scorer = None
    if ts_rows:
        r = ts_rows[0]
        top_scorer = {
            "person_id": r["person_id"], "name": r["name"],
            "team": r["team"], "runs": r["runs"],
        }

    # ── Top wicket-taker all-time ──
    # Bowler's team = opposite of the innings batting team.
    tw_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id, p.name,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS team,
               COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.bowler_id
        WHERE i.super_over = 0 AND {where}
          AND d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        GROUP BY d.bowler_id
        ORDER BY wickets DESC
        LIMIT 1
        """,
        params,
    )
    top_wicket_taker = None
    if tw_rows:
        r = tw_rows[0]
        top_wicket_taker = {
            "person_id": r["person_id"], "name": r["name"],
            "team": r["team"], "wickets": r["wickets"],
        }

    # ── Highest team total (innings) ──
    ht_rows = await db.q(
        f"""
        SELECT i.team, tot.total,
               m.id AS match_id,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM (
          SELECT d.innings_id, SUM(d.runs_total) AS total
          FROM delivery d
          GROUP BY d.innings_id
        ) tot
        JOIN innings i ON i.id = tot.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        ORDER BY tot.total DESC
        LIMIT 1
        """,
        params,
    )
    highest_team_total = None
    if ht_rows:
        r = ht_rows[0]
        highest_team_total = {
            "team": r["team"], "total": r["total"],
            "match_id": r["match_id"], "opponent": r["opponent"],
            "date": r["date"],
        }

    # ── Highest individual innings (best batting single-match) ──
    hi_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id, p.name, i.team AS team,
               m.id AS match_id,
               SUM(d.runs_batter) AS runs,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE i.super_over = 0 AND {where}
          AND d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id, m.id
        ORDER BY runs DESC
        LIMIT 1
        """,
        params,
    )
    highest_individual = None
    if hi_rows:
        r = hi_rows[0]
        highest_individual = {
            "person_id": r["person_id"], "name": r["name"],
            "team": r["team"],
            "runs": r["runs"], "match_id": r["match_id"], "date": r["date"],
        }

    # ── Largest partnership (enriched — batter IDs, team, date) ──
    lp_rows = await db.q(
        f"""
        SELECT p.partnership_runs AS runs, m.id AS match_id,
               p.batter1_id, p.batter1_name,
               p.batter2_id, p.batter2_name,
               i.team AS team,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        ORDER BY p.partnership_runs DESC
        LIMIT 1
        """,
        params,
    )
    largest_partnership = None
    if lp_rows:
        r = lp_rows[0]
        largest_partnership = {
            "runs": r["runs"], "match_id": r["match_id"],
            "team": r["team"], "opponent": r["opponent"],
            "date": r["date"],
            "batter1": {"person_id": r["batter1_id"], "name": r["batter1_name"]},
            "batter2": {"person_id": r["batter2_id"], "name": r["batter2_name"]},
        }

    # ── Best bowling figures (single match) ──
    # Bowler's team = opposite of the innings they bowled in.
    bb_rows = await db.q(
        f"""
        WITH per_match_bowler AS (
          SELECT d.bowler_id, i.match_id,
                 CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS bowler_team,
                 SUM(CASE WHEN w.id IS NOT NULL
                              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
                          THEN 1 ELSE 0 END) AS wickets,
                 SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0
                          THEN d.runs_total ELSE d.runs_total END) AS runs_conceded
          FROM delivery d
          LEFT JOIN wicket w ON w.delivery_id = d.id
          JOIN innings i ON i.id = d.innings_id
          JOIN match m ON m.id = i.match_id
          WHERE i.super_over = 0 AND {where}
            AND d.bowler_id IS NOT NULL
          GROUP BY d.bowler_id, i.match_id
        )
        SELECT pm.bowler_id AS person_id, p.name,
               pm.bowler_team AS team,
               pm.wickets, pm.runs_conceded AS runs,
               pm.match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = pm.match_id) AS date
        FROM per_match_bowler pm
        LEFT JOIN person p ON p.id = pm.bowler_id
        ORDER BY pm.wickets DESC, pm.runs_conceded ASC
        LIMIT 1
        """,
        params,
    )
    best_bowling = None
    if bb_rows:
        r = bb_rows[0]
        best_bowling = {
            "person_id": r["person_id"], "name": r["name"],
            "team": r["team"],
            "figures": f"{r['wickets']}/{r['runs']}",
            "wickets": r["wickets"], "runs": r["runs"],
            "match_id": r["match_id"], "date": r["date"],
        }

    # ── Best fielding (most dismissals in a single match) ──
    # Counts catches + stumpings + run-outs + caught-and-bowled. Excludes
    # substitute fielders. Fielder's team = opposite of innings batting team.
    bf_rows = await db.q(
        f"""
        WITH per_match_fielder AS (
          SELECT fc.fielder_id, i.match_id,
                 CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS fielder_team,
                 SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
                 SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
                 SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
                 SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS caught_bowled,
                 COUNT(*) AS total
          FROM fieldingcredit fc
          JOIN delivery d ON d.id = fc.delivery_id
          JOIN innings i ON i.id = d.innings_id
          JOIN match m ON m.id = i.match_id
          WHERE i.super_over = 0 AND {where}
            AND fc.fielder_id IS NOT NULL
            AND fc.is_substitute = 0
          GROUP BY fc.fielder_id, i.match_id
        )
        SELECT pf.fielder_id AS person_id, p.name,
               pf.fielder_team AS team,
               pf.catches, pf.stumpings, pf.run_outs, pf.caught_bowled,
               pf.total, pf.match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = pf.match_id) AS date
        FROM per_match_fielder pf
        LEFT JOIN person p ON p.id = pf.fielder_id
        ORDER BY pf.total DESC, pf.stumpings DESC
        LIMIT 1
        """,
        params,
    )
    best_fielding = None
    if bf_rows:
        r = bf_rows[0]
        best_fielding = {
            "person_id": r["person_id"], "name": r["name"],
            "team": r["team"],
            "catches": r["catches"], "stumpings": r["stumpings"],
            "run_outs": r["run_outs"], "caught_bowled": r["caught_bowled"],
            "total": r["total"],
            "match_id": r["match_id"], "date": r["date"],
        }

    # ── Participating teams (in scope) ──
    team_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.team1 AS team, m.id AS match_id FROM match m WHERE {where}
          UNION ALL
          SELECT m.team2, m.id FROM match m WHERE {where}
        )
        SELECT team, COUNT(DISTINCT match_id) AS n
        FROM sides GROUP BY team ORDER BY n DESC, team
        """,
        params,
    )
    teams = [{"name": r["team"], "matches": r["n"]} for r in team_rows]

    # ── Groups (when event_group is populated — ICC events etc.) ──
    group_rows = await db.q(
        f"""
        WITH sides AS (
          SELECT m.event_group AS g, m.season AS season,
                 m.team1 AS team, m.id AS match_id
          FROM match m WHERE {where} AND m.event_group IS NOT NULL
          UNION ALL
          SELECT m.event_group, m.season, m.team2, m.id
          FROM match m WHERE {where} AND m.event_group IS NOT NULL
        )
        SELECT g, season, team, COUNT(DISTINCT match_id) AS n
        FROM sides GROUP BY g, season, team
        ORDER BY season DESC, g, n DESC
        """,
        params,
    )
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in group_rows:
        key = (r["season"], r["g"])
        groups.setdefault(key, []).append({"team": r["team"], "matches": r["n"]})
    # Sort within each season: lettered groups first (A, B, C, D…) then
    # numeric groups (1, 2 — typically Super 8 / later rounds). Season
    # DESC so the most recent edition comes first when multi-season.
    def _group_sort_key(g: str) -> tuple[int, str]:
        return (0, g) if g and g[0].isalpha() else (1, g)
    items = sorted(groups.items(), key=lambda kv: _group_sort_key(kv[0][1]))
    items = sorted(items, key=lambda kv: kv[0][0], reverse=True)
    groups_out = [
        {"season": season, "group": group, "teams": teams_list}
        for (season, group), teams_list in items
    ]

    # ── Knockouts (semi-finals + finals) ──
    ko_rows = await db.q(
        f"""
        SELECT m.id AS match_id, m.season, m.event_stage, m.event_name,
               m.team1, m.team2, m.outcome_winner,
               m.outcome_by_runs, m.outcome_by_wickets, m.outcome_result,
               m.venue,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.event_stage IN (
          'Final', 'Semi Final', 'Semi-Final', 'Semi-final',
          'Qualifier 1', 'Qualifier 2', 'Eliminator',
          '3rd Place Play-Off', 'Preliminary Final'
        )
        ORDER BY m.season DESC,
          CASE m.event_stage
            WHEN 'Final' THEN 1
            WHEN '3rd Place Play-Off' THEN 2
            WHEN 'Preliminary Final' THEN 3
            WHEN 'Qualifier 2' THEN 4
            WHEN 'Eliminator' THEN 5
            WHEN 'Qualifier 1' THEN 6
            ELSE 7
          END
        """,
        params,
    )
    knockouts = [
        {
            "match_id": r["match_id"],
            "season": r["season"],
            "stage": r["event_stage"],
            "tournament": r["event_name"],
            "team1": r["team1"],
            "team2": r["team2"],
            "winner": r["outcome_winner"],
            "margin": (f"{r['outcome_by_runs']} runs" if r["outcome_by_runs"] is not None
                       else f"{r['outcome_by_wickets']} wickets" if r["outcome_by_wickets"] is not None
                       else r["outcome_result"] or "—"),
            "venue": r["venue"],
            "date": r["date"],
        }
        for r in ko_rows
    ]

    # ── Per-team breakdowns when a team pair is in scope ──
    by_team = None
    head_to_head = None
    if filters.team and filters.opponent:
        by_team = await _summary_by_team(
            db, where, params, [filters.team, filters.opponent],
        )
        # Wins/losses/ties/NR — the basic "who won how much" stats that
        # were missing on the Team-vs-Team dossier.
        h2h_rows = await db.q(
            f"""
            SELECT
              SUM(CASE WHEN m.outcome_winner = :h2h_a THEN 1 ELSE 0 END) AS a_wins,
              SUM(CASE WHEN m.outcome_winner = :h2h_b THEN 1 ELSE 0 END) AS b_wins,
              SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
              SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS no_result
            FROM match m
            WHERE {where}
            """,
            {**params, "h2h_a": filters.team, "h2h_b": filters.opponent},
        )
        if h2h_rows:
            r = h2h_rows[0]
            head_to_head = {
                "team1": filters.team, "team2": filters.opponent,
                "team1_wins": r["a_wins"] or 0,
                "team2_wins": r["b_wins"] or 0,
                "ties": r["ties"] or 0,
                "no_result": r["no_result"] or 0,
            }

    return {
        "canonical": tournament,
        "variants": vs,
        "editions": meta["editions"],
        "matches": meta["matches"],
        "total_runs": total_runs,
        "total_wickets": total_wickets,
        "total_sixes": sixes,
        "total_fours": fours,
        "run_rate": _safe_div(total_runs, legal_balls, 6),
        "boundary_pct": _safe_div(fours + sixes, legal_balls, 100),
        "dot_pct": _safe_div(dots, legal_balls, 100),
        "most_titles": most_titles,
        "champions_by_season": champions_by_season,
        "top_scorer_alltime": top_scorer,
        "top_wicket_taker_alltime": top_wicket_taker,
        "highest_individual": highest_individual,
        "highest_team_total": highest_team_total,
        "largest_partnership": largest_partnership,
        "best_bowling": best_bowling,
        "best_fielding": best_fielding,
        "teams": teams,
        "groups": groups_out,
        "knockouts": knockouts,
        "by_team": by_team,
        "head_to_head": head_to_head,
    }


async def _summary_by_team(
    db, where: str, params: dict, teams_list: list[str],
) -> dict:
    """Per-team breakdowns for rivalry view: top scorer, top wicket-taker,
    highest individual, largest partnership — split by which team scored.

    Used when filter_team + filter_opponent are both set so the dossier
    can show "highest individual by India" alongside "highest individual
    by Australia" in addition to the unified value.
    """
    out: dict[str, dict] = {}
    for team in teams_list:
        team_params = {**params, "by_team": team}
        # Top scorer for this team
        ts_rows = await db.q(
            f"""
            SELECT d.batter_id AS person_id, p.name, SUM(d.runs_batter) AS runs
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            LEFT JOIN person p ON p.id = d.batter_id
            WHERE i.super_over = 0 AND {where}
              AND i.team = :by_team
              AND d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
            GROUP BY d.batter_id ORDER BY runs DESC LIMIT 1
            """,
            team_params,
        )
        # Top wicket-taker for this team (bowling for this team =
        # batting team is the opponent → i.team != :by_team)
        tw_rows = await db.q(
            f"""
            SELECT d.bowler_id AS person_id, p.name, COUNT(*) AS wickets
            FROM wicket w
            JOIN delivery d ON d.id = w.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            LEFT JOIN person p ON p.id = d.bowler_id
            WHERE i.super_over = 0 AND {where}
              AND i.team != :by_team
              AND d.bowler_id IS NOT NULL
              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
            GROUP BY d.bowler_id ORDER BY wickets DESC LIMIT 1
            """,
            team_params,
        )
        # Highest individual innings for this team
        hi_rows = await db.q(
            f"""
            SELECT d.batter_id AS person_id, p.name,
                   m.id AS match_id,
                   SUM(d.runs_batter) AS runs,
                   (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            LEFT JOIN person p ON p.id = d.batter_id
            WHERE i.super_over = 0 AND {where}
              AND i.team = :by_team
              AND d.batter_id IS NOT NULL
              AND d.extras_wides = 0 AND d.extras_noballs = 0
            GROUP BY d.batter_id, m.id ORDER BY runs DESC LIMIT 1
            """,
            team_params,
        )
        # Largest partnership for this team
        lp_rows = await db.q(
            f"""
            SELECT p.partnership_runs AS runs, m.id AS match_id,
                   p.batter1_name, p.batter2_name,
                   p.batter1_id, p.batter2_id,
                   (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 AND {where}
              AND i.team = :by_team
            ORDER BY p.partnership_runs DESC LIMIT 1
            """,
            team_params,
        )

        out[team] = {
            "top_scorer": (
                {"person_id": ts_rows[0]["person_id"], "name": ts_rows[0]["name"],
                 "runs": ts_rows[0]["runs"]}
                if ts_rows else None
            ),
            "top_wicket_taker": (
                {"person_id": tw_rows[0]["person_id"], "name": tw_rows[0]["name"],
                 "wickets": tw_rows[0]["wickets"]}
                if tw_rows else None
            ),
            "highest_individual": (
                {"person_id": hi_rows[0]["person_id"], "name": hi_rows[0]["name"],
                 "runs": hi_rows[0]["runs"], "match_id": hi_rows[0]["match_id"],
                 "date": hi_rows[0]["date"]}
                if hi_rows else None
            ),
            "largest_partnership": (
                {"runs": lp_rows[0]["runs"], "match_id": lp_rows[0]["match_id"],
                 "date": lp_rows[0]["date"],
                 "batter1": {"person_id": lp_rows[0]["batter1_id"], "name": lp_rows[0]["batter1_name"]},
                 "batter2": {"person_id": lp_rows[0]["batter2_id"], "name": lp_rows[0]["batter2_name"]}}
                if lp_rows else None
            ),
        }
    return out


@router.get("/series/by-season")
async def tournament_by_season(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
):
    """Per-edition rollup for one tournament.

    Returns one row per season in scope with champion, runner-up, top
    scorer, top wicket-taker, and aggregate batting metrics.
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)

    # Per-season match counts + final champion/runner-up
    season_rows = await db.q(
        f"""
        SELECT m.season,
               COUNT(DISTINCT m.id) AS matches
        FROM match m
        WHERE {where}
        GROUP BY m.season
        ORDER BY m.season DESC
        """,
        params,
    )

    finals_rows = await db.q(
        f"""
        SELECT m.season, m.id AS match_id,
               m.outcome_winner AS winner,
               m.team1, m.team2
        FROM match m
        WHERE {where} AND m.event_stage = 'Final' AND m.outcome_winner IS NOT NULL
        """,
        params,
    )
    finals_by_season: dict[str, dict] = {}
    for r in finals_rows:
        runner_up = r["team1"] if r["winner"] == r["team2"] else r["team2"]
        finals_by_season[r["season"]] = {
            "champion": r["winner"],
            "runner_up": runner_up,
            "final_match_id": r["match_id"],
        }

    # Per-season batting aggregates
    bat_rows = await db.q(
        f"""
        SELECT m.season,
               SUM(d.runs_total) AS total_runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
               SUM(CASE WHEN d.runs_batter = 4 AND (d.runs_non_boundary IS NULL OR d.runs_non_boundary = 0) THEN 1 ELSE 0 END) AS fours
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        GROUP BY m.season
        """,
        params,
    )
    bat_by_season = {r["season"]: r for r in bat_rows}

    # Per-season top scorer
    ts_rows = await db.q(
        f"""
        WITH b AS (
          SELECT m.season AS season, d.batter_id, SUM(d.runs_batter) AS runs
          FROM delivery d
          JOIN innings i ON i.id = d.innings_id
          JOIN match m ON m.id = i.match_id
          WHERE i.super_over = 0 AND {where}
            AND d.batter_id IS NOT NULL
            AND d.extras_wides = 0 AND d.extras_noballs = 0
          GROUP BY m.season, d.batter_id
        )
        SELECT b.season AS season, b.batter_id AS person_id, p.name, b.runs AS runs
        FROM b
        JOIN (SELECT season, MAX(runs) AS mx FROM b GROUP BY season) best
          ON b.season = best.season AND b.runs = best.mx
        LEFT JOIN person p ON p.id = b.batter_id
        """,
        params,
    )
    top_scorer_by_season: dict[str, dict] = {}
    for r in ts_rows:
        # first hit wins for ties
        top_scorer_by_season.setdefault(r["season"], {
            "person_id": r["person_id"], "name": r["name"], "runs": r["runs"]
        })

    # Per-season top wicket-taker
    tw_rows = await db.q(
        f"""
        WITH w AS (
          SELECT m.season AS season, d.bowler_id, COUNT(*) AS wickets
          FROM wicket wk
          JOIN delivery d ON d.id = wk.delivery_id
          JOIN innings i ON i.id = d.innings_id
          JOIN match m ON m.id = i.match_id
          WHERE i.super_over = 0 AND {where}
            AND d.bowler_id IS NOT NULL
            AND wk.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
          GROUP BY m.season, d.bowler_id
        )
        SELECT w.season AS season, w.bowler_id AS person_id, p.name, w.wickets AS wickets
        FROM w
        JOIN (SELECT season, MAX(wickets) AS mx FROM w GROUP BY season) best
          ON w.season = best.season AND w.wickets = best.mx
        LEFT JOIN person p ON p.id = w.bowler_id
        """,
        params,
    )
    top_wicket_by_season: dict[str, dict] = {}
    for r in tw_rows:
        top_wicket_by_season.setdefault(r["season"], {
            "person_id": r["person_id"], "name": r["name"], "wickets": r["wickets"]
        })

    seasons: list[dict] = []
    for sr in season_rows:
        season = sr["season"]
        f = finals_by_season.get(season, {})
        b = bat_by_season.get(season, {})
        total_runs = (b.get("total_runs") or 0) if b else 0
        legal_balls = (b.get("legal_balls") or 0) if b else 0
        sixes = (b.get("sixes") or 0) if b else 0
        fours = (b.get("fours") or 0) if b else 0
        seasons.append({
            "season": season,
            "matches": sr["matches"],
            "champion": f.get("champion"),
            "runner_up": f.get("runner_up"),
            "final_match_id": f.get("final_match_id"),
            "run_rate": _safe_div(total_runs, legal_balls, 6),
            "boundary_pct": _safe_div(fours + sixes, legal_balls, 100),
            "total_sixes": sixes,
            "top_scorer": top_scorer_by_season.get(season),
            "top_wicket_taker": top_wicket_by_season.get(season),
        })

    return {"tournament": tournament, "seasons": seasons}


@router.get("/series/points-table")
async def tournament_points_table(
    tournament: str = Query(...),
    filters: FilterParams = Depends(),
):
    """Reconstructed league-stage points table + NRR.

    Only meaningful when a single season is in scope. Returns one table
    per event_group (e.g. T20 WC groups 1/2/A/B) or one combined table
    for single-group leagues (IPL).

    Knockout stages (Final, Semi Final, Eliminator, Qualifier 1/2,
    Quarter Final, Play-Off, etc.) are excluded from league aggregates.
    NRR excludes no-result matches.
    """
    db = get_db()

    # Require single-season scope — otherwise return empty + reason.
    if not (filters.season_from and filters.season_to
            and filters.season_from == filters.season_to):
        return {
            "canonical": tournament,
            "season": None,
            "tables": [],
            "reason": "multi_season",
        }
    season = filters.season_from

    where, params = _tournament_scope_where(filters, tournament)
    # League match predicate — exclude knockout stages (most common enum values).
    knockout_stages = (
        "Final", "Semi Final", "Semi-Final", "Semi-final", "Eliminator",
        "Qualifier 1", "Qualifier 2", "Qualifier 3", "Qualifier",
        "Quarter Final", "Quarter-Final", "Quarter-final",
        "3rd Place Play-Off", "5th Place Play-Off", "7th Place Play-Off",
        "Play-Off", "Play-off", "Preliminary Final", "Preliminary Quarter Final",
        "Preliminary quarter-final", "Elimination Final", "Challenger",
        "Knockout",
    )
    ko_clause = event_name_in_clause(list(knockout_stages), col="m.event_stage")
    league_where = f"{where} AND (m.event_stage IS NULL OR NOT {ko_clause})"

    # Determine groups present
    group_rows = await db.q(
        f"""
        SELECT DISTINCT m.event_group AS g
        FROM match m
        WHERE {league_where}
        """,
        params,
    )
    groups = sorted({r["g"] for r in group_rows}, key=lambda g: (g is None, g or ""))
    if not groups:
        groups = [None]

    tables: list[dict] = []
    for g in groups:
        g_where = league_where + (" AND m.event_group = :group" if g is not None
                                    else " AND m.event_group IS NULL")
        g_params = {**params}
        if g is not None:
            g_params["group"] = g

        # Aggregate wins/losses/ties/nr per team
        m_rows = await db.q(
            f"""
            SELECT m.id, m.team1, m.team2,
                   m.outcome_winner, m.outcome_result
            FROM match m
            WHERE {g_where}
            """,
            g_params,
        )
        # Per-match ball-by-ball aggregates for NRR
        agg_rows = await db.q(
            f"""
            SELECT m.id AS match_id, i.team,
                   SUM(d.runs_total) AS runs,
                   SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS legal_balls
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE i.super_over = 0 AND {g_where}
            GROUP BY m.id, i.team
            """,
            g_params,
        )
        # (match_id, team) → (runs, legal_balls)
        innings_agg: dict[tuple[int, str], tuple[int, int]] = {}
        for r in agg_rows:
            innings_agg[(r["match_id"], r["team"])] = (
                r["runs"] or 0, r["legal_balls"] or 0
            )

        team_stats: dict[str, dict] = {}

        def _team(t: str) -> dict:
            return team_stats.setdefault(t, {
                "team": t, "played": 0, "wins": 0, "losses": 0,
                "ties": 0, "nr": 0, "points": 0,
                "runs_for": 0, "balls_for": 0,
                "runs_against": 0, "balls_against": 0,
            })

        for mr in m_rows:
            a = _team(mr["team1"])
            b = _team(mr["team2"])
            a["played"] += 1
            b["played"] += 1
            result = mr["outcome_result"]
            winner = mr["outcome_winner"]
            if result == "no result":
                a["nr"] += 1
                b["nr"] += 1
                a["points"] += 1
                b["points"] += 1
            elif result == "tie":
                a["ties"] += 1
                b["ties"] += 1
                a["points"] += 1
                b["points"] += 1
            else:
                if winner == mr["team1"]:
                    a["wins"] += 1
                    b["losses"] += 1
                    a["points"] += 2
                elif winner == mr["team2"]:
                    b["wins"] += 1
                    a["losses"] += 1
                    b["points"] += 2

            # NRR — exclude no-result
            if result != "no result":
                for team, opp in ((mr["team1"], mr["team2"]),
                                   (mr["team2"], mr["team1"])):
                    ts = team_stats[team]
                    rf, bf = innings_agg.get((mr["id"], team), (0, 0))
                    ra, ba = innings_agg.get((mr["id"], opp), (0, 0))
                    ts["runs_for"] += rf
                    ts["balls_for"] += bf
                    ts["runs_against"] += ra
                    ts["balls_against"] += ba

        # Compute NRR
        rows = []
        for ts in team_stats.values():
            rf = ts["runs_for"]
            bf = ts["balls_for"]
            ra = ts["runs_against"]
            ba = ts["balls_against"]
            if bf > 0 and ba > 0:
                nrr = round(rf / bf * 6 - ra / ba * 6, 3)
            else:
                nrr = None
            rows.append({**ts, "nrr": nrr})

        rows.sort(key=lambda r: (-r["points"], -(r["nrr"] or -999), -r["wins"], r["team"]))
        tables.append({"group": g, "rows": rows})

    return {
        "canonical": tournament,
        "season": season,
        "tables": tables,
    }


@router.get("/series/records")
async def tournament_records(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    limit: int = Query(5, ge=1, le=20),
):
    """Records lists for the match-set scope — each capped at top-N.

    Highest / lowest team totals, biggest wins (runs / wickets),
    largest partnerships, best bowling figures, most sixes in a match.
    Tournament optional (omit for cross-tournament rivalry records);
    series_type narrows international scope (bilateral_only / tournament_only).
    """
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)
    params["lim"] = limit

    # Highest team totals
    ht_rows = await db.q(
        f"""
        SELECT i.team, tot.total AS runs, m.id AS match_id,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM (
          SELECT d.innings_id, SUM(d.runs_total) AS total
          FROM delivery d
          GROUP BY d.innings_id
        ) tot
        JOIN innings i ON i.id = tot.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        ORDER BY tot.total DESC LIMIT :lim
        """,
        params,
    )

    # Lowest all-out totals (innings where 10 wickets fell)
    lo_rows = await db.q(
        f"""
        WITH innings_wkts AS (
          SELECT w.delivery_id, d.innings_id
          FROM wicket w JOIN delivery d ON d.id = w.delivery_id
        ),
        innings_totals AS (
          SELECT d.innings_id, SUM(d.runs_total) AS total,
                 (SELECT COUNT(*) FROM wicket w
                  JOIN delivery d2 ON d2.id = w.delivery_id
                  WHERE d2.innings_id = d.innings_id
                    AND w.kind NOT IN ('retired hurt', 'retired not out')) AS wkts
          FROM delivery d
          GROUP BY d.innings_id
        )
        SELECT i.team, it.total AS runs, m.id AS match_id,
               CASE WHEN m.team1 = i.team THEN m.team2 ELSE m.team1 END AS opponent,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM innings_totals it
        JOIN innings i ON i.id = it.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND it.wkts >= 10 AND {where}
        ORDER BY it.total ASC LIMIT :lim
        """,
        params,
    )

    # Biggest wins by runs
    bwr_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_runs AS margin,
               m.id AS match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_runs IS NOT NULL
        ORDER BY m.outcome_by_runs DESC LIMIT :lim
        """,
        params,
    )

    # Biggest wins by wickets
    bww_rows = await db.q(
        f"""
        SELECT m.outcome_winner AS winner,
               CASE WHEN m.team1 = m.outcome_winner THEN m.team2 ELSE m.team1 END AS loser,
               m.outcome_by_wickets AS margin,
               m.id AS match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_wickets IS NOT NULL
        ORDER BY m.outcome_by_wickets DESC, m.outcome_by_runs ASC LIMIT :lim
        """,
        params,
    )

    # Largest partnerships
    lp_rows = await db.q(
        f"""
        SELECT p.partnership_runs AS runs,
               p.batter1_id, p.batter2_id,
               p1.name AS b1_name, p2.name AS b2_name,
               m.id AS match_id,
               m.team1, m.team2,
               i.team AS batting_team,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p1 ON p1.id = p.batter1_id
        LEFT JOIN person p2 ON p2.id = p.batter2_id
        WHERE i.super_over = 0 AND {where}
        ORDER BY p.partnership_runs DESC LIMIT :lim
        """,
        params,
    )

    # Best bowling figures (single match)
    bb_rows = await db.q(
        f"""
        WITH per_match_bowler AS (
          SELECT d.bowler_id, m.id AS match_id,
                 SUM(CASE WHEN w.id IS NOT NULL
                              AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
                          THEN 1 ELSE 0 END) AS wickets,
                 SUM(d.runs_total) AS runs,
                 SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS balls
          FROM delivery d
          LEFT JOIN wicket w ON w.delivery_id = d.id
          JOIN innings i ON i.id = d.innings_id
          JOIN match m ON m.id = i.match_id
          WHERE i.super_over = 0 AND {where}
            AND d.bowler_id IS NOT NULL
          GROUP BY d.bowler_id, m.id
        )
        SELECT pm.bowler_id AS person_id, p.name,
               pm.wickets, pm.runs, pm.balls, pm.match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = pm.match_id) AS date
        FROM per_match_bowler pm
        LEFT JOIN person p ON p.id = pm.bowler_id
        WHERE pm.wickets >= 2
        ORDER BY pm.wickets DESC, pm.runs ASC LIMIT :lim
        """,
        params,
    )

    # Most sixes in a match
    ms_rows = await db.q(
        f"""
        SELECT m.id AS match_id,
               SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes,
               m.team1 || ' v ' || m.team2 AS teams,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        GROUP BY m.id
        ORDER BY sixes DESC LIMIT :lim
        """,
        params,
    )

    return {
        "canonical": tournament,
        "highest_team_totals": [
            {"team": r["team"], "runs": r["runs"], "opponent": r["opponent"],
             "match_id": r["match_id"], "date": r["date"]}
            for r in ht_rows
        ],
        "lowest_all_out_totals": [
            {"team": r["team"], "runs": r["runs"], "opponent": r["opponent"],
             "match_id": r["match_id"], "date": r["date"]}
            for r in lo_rows
        ],
        "biggest_wins_by_runs": [
            {"winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
             "match_id": r["match_id"], "date": r["date"]}
            for r in bwr_rows
        ],
        "biggest_wins_by_wickets": [
            {"winner": r["winner"], "loser": r["loser"], "margin": r["margin"],
             "match_id": r["match_id"], "date": r["date"]}
            for r in bww_rows
        ],
        "largest_partnerships": [
            {"runs": r["runs"],
             "batter1": {"person_id": r["batter1_id"], "name": r["b1_name"]},
             "batter2": {"person_id": r["batter2_id"], "name": r["b2_name"]},
             "teams": f"{r['team1']} v {r['team2']}",
             "batting_team": r["batting_team"],
             "match_id": r["match_id"], "date": r["date"]}
            for r in lp_rows
        ],
        "best_bowling_figures": [
            {"person_id": r["person_id"], "name": r["name"],
             "wickets": r["wickets"], "runs": r["runs"], "balls": r["balls"],
             "figures": f"{r['wickets']}/{r['runs']}",
             "match_id": r["match_id"], "date": r["date"]}
            for r in bb_rows
        ],
        "most_sixes_in_a_match": [
            {"match_id": r["match_id"], "sixes": r["sixes"],
             "teams": r["teams"], "date": r["date"]}
            for r in ms_rows
        ],
    }


# ─── Leader wrappers (variant-aware) ──────────────────────────────────
#
# These mirror /batters/leaders, /bowlers/leaders, /fielders/leaders but
# use IN-variants expansion so canonical tournaments with name drift
# (e.g. T20 World Cup across "ICC World Twenty20" / "World T20" / "ICC
# Men's T20 World Cup") aggregate across all variants. Single-variant
# tournaments work through the same code path — the IN-clause just has
# one element.


@router.get("/series/batters-leaders")
async def tournament_batters_leaders(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
    min_balls: int = Query(100, ge=1),
    min_dismissals: int = Query(3, ge=0),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)

    agg_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id,
               SUM(d.runs_batter) AS runs,
               COUNT(*) AS balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
          AND i.super_over = 0 AND {where}
        GROUP BY d.batter_id
        HAVING COUNT(*) >= :min_balls
        """,
        {**params, "min_balls": min_balls},
    )
    dism_rows = await db.q(
        f"""
        SELECT w.player_out_id AS person_id, COUNT(*) AS dismissals
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE w.player_out_id IS NOT NULL
          AND w.kind NOT IN ('retired hurt', 'retired out')
          AND i.super_over = 0 AND {where}
        GROUP BY w.player_out_id
        """,
        params,
    )
    dism_map = {r["person_id"]: r["dismissals"] or 0 for r in dism_rows}

    entries: list[dict] = []
    for r in agg_rows:
        pid = r["person_id"]
        runs = r["runs"] or 0
        balls = r["balls"] or 0
        dism = dism_map.get(pid, 0)
        entries.append({
            "person_id": pid,
            "runs": runs,
            "balls": balls,
            "dismissals": dism,
            "average": _safe_div(runs, dism) if dism > 0 else None,
            "strike_rate": _safe_div(runs, balls, 100),
        })

    avg_top = sorted(
        (e for e in entries if e["dismissals"] >= min_dismissals and e["average"] is not None),
        key=lambda e: (e["average"], e["runs"]), reverse=True,
    )[:limit]
    sr_top = sorted(
        (e for e in entries if e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], e["runs"]), reverse=True,
    )[:limit]

    top_ids = {e["person_id"] for e in avg_top} | {e["person_id"] for e in sr_top}
    name_map: dict[str, str] = {}
    team_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}
        # Dominant team (most balls faced within scope). Needed by the
        # rivalry-dossier UI so the "vs <opponent>" context link flips
        # per player — a batter who played for India vs Australia needs
        # "vs Australia", not the dossier's filter_opponent verbatim.
        team_rows = await db.q(
            f"""
            SELECT d.batter_id AS pid, i.team AS team, COUNT(*) AS n
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.batter_id IN ({placeholders})
              AND d.extras_wides = 0 AND d.extras_noballs = 0
              AND i.super_over = 0 AND {where}
            GROUP BY d.batter_id, i.team
            """,
            {**params, **name_params},
        )
        per_pid: dict[str, tuple[str, int]] = {}
        for r in team_rows:
            pid, team, n = r["pid"], r["team"], r["n"] or 0
            if pid not in per_pid or n > per_pid[pid][1]:
                per_pid[pid] = (team, n)
        team_map = {pid: v[0] for pid, v in per_pid.items()}
    for e in avg_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
        e["team"] = team_map.get(e["person_id"])
    for e in sr_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
        e["team"] = team_map.get(e["person_id"])

    return {
        "by_average": avg_top,
        "by_strike_rate": sr_top,
        "thresholds": {"min_balls": min_balls, "min_dismissals": min_dismissals},
    }


@router.get("/series/bowlers-leaders")
async def tournament_bowlers_leaders(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
    min_balls: int = Query(60, ge=1),
    min_wickets: int = Query(3, ge=0),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)

    agg_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id,
               SUM(d.runs_total) AS runs,
               SUM(CASE WHEN d.extras_wides = 0 AND d.extras_noballs = 0 THEN 1 ELSE 0 END) AS balls
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.bowler_id IS NOT NULL
          AND i.super_over = 0 AND {where}
        GROUP BY d.bowler_id
        HAVING balls >= :min_balls
        """,
        {**params, "min_balls": min_balls},
    )
    wkt_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id, COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
          AND i.super_over = 0 AND {where}
        GROUP BY d.bowler_id
        """,
        params,
    )
    wkt_map = {r["person_id"]: r["wickets"] or 0 for r in wkt_rows}

    entries: list[dict] = []
    for r in agg_rows:
        pid = r["person_id"]
        runs = r["runs"] or 0
        balls = r["balls"] or 0
        wickets = wkt_map.get(pid, 0)
        entries.append({
            "person_id": pid,
            "runs": runs,
            "balls": balls,
            "wickets": wickets,
            "economy": _safe_div(runs, balls, 6),
            "strike_rate": _safe_div(balls, wickets) if wickets > 0 else None,
        })

    # by_strike_rate: need min_wickets to exclude tiny-sample blazing SRs
    sr_top = sorted(
        (e for e in entries if e["wickets"] >= min_wickets and e["strike_rate"] is not None),
        key=lambda e: (e["strike_rate"], -e["wickets"]),
    )[:limit]
    econ_top = sorted(
        (e for e in entries if e["economy"] is not None),
        key=lambda e: (e["economy"], -e["balls"]),
    )[:limit]

    top_ids = {e["person_id"] for e in sr_top} | {e["person_id"] for e in econ_top}
    name_map: dict[str, str] = {}
    team_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}
        # Bowler's team = the side NOT batting in this innings.
        team_rows = await db.q(
            f"""
            SELECT d.bowler_id AS pid,
                   CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS team,
                   COUNT(*) AS n
            FROM delivery d
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE d.bowler_id IN ({placeholders})
              AND i.super_over = 0 AND {where}
            GROUP BY d.bowler_id, team
            """,
            {**params, **name_params},
        )
        per_pid: dict[str, tuple[str, int]] = {}
        for r in team_rows:
            pid, team, n = r["pid"], r["team"], r["n"] or 0
            if pid not in per_pid or n > per_pid[pid][1]:
                per_pid[pid] = (team, n)
        team_map = {pid: v[0] for pid, v in per_pid.items()}
    for e in sr_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
        e["team"] = team_map.get(e["person_id"])
    for e in econ_top:
        e["name"] = name_map.get(e["person_id"], e["person_id"])
        e["team"] = team_map.get(e["person_id"])

    return {
        "by_strike_rate": sr_top,
        "by_economy": econ_top,
        "thresholds": {"min_balls": min_balls, "min_wickets": min_wickets},
    }


@router.get("/series/fielders-leaders")
async def tournament_fielders_leaders(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    limit: int = Query(10, ge=1, le=50),
):
    db = get_db()
    where, params = _tournament_scope_where(filters, tournament, series_type=series_type)
    params["lim"] = limit

    # By total dismissals (catches + stumpings + run-outs + c&b)
    disp_rows = await db.q(
        f"""
        SELECT fc.fielder_id AS person_id,
               COUNT(*) AS total,
               SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings,
               SUM(CASE WHEN fc.kind = 'run_out' THEN 1 ELSE 0 END) AS run_outs,
               SUM(CASE WHEN fc.kind = 'caught_and_bowled' THEN 1 ELSE 0 END) AS c_and_b
        FROM fieldingcredit fc
        JOIN delivery d ON d.id = fc.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE fc.fielder_id IS NOT NULL
          AND i.super_over = 0 AND {where}
        GROUP BY fc.fielder_id
        ORDER BY total DESC
        LIMIT :lim
        """,
        params,
    )

    # By keeper dismissals — credit catches/stumpings to the designated
    # keeper (via keeper_assignment) for the fielding innings. Join
    # fielding_credit through delivery → innings to match ka.innings_id.
    keeper_rows = await db.q(
        f"""
        SELECT ka.keeper_id AS person_id,
               SUM(CASE WHEN fc.kind IN ('caught','stumped') THEN 1 ELSE 0 END) AS total,
               SUM(CASE WHEN fc.kind = 'caught' THEN 1 ELSE 0 END) AS catches,
               SUM(CASE WHEN fc.kind = 'stumped' THEN 1 ELSE 0 END) AS stumpings
        FROM keeperassignment ka
        JOIN innings i ON i.id = ka.innings_id
        JOIN match m ON m.id = i.match_id
        JOIN delivery d ON d.innings_id = i.id
        JOIN fieldingcredit fc ON fc.delivery_id = d.id
          AND fc.fielder_id = ka.keeper_id
        WHERE ka.keeper_id IS NOT NULL
          AND i.super_over = 0 AND {where}
        GROUP BY ka.keeper_id
        HAVING total > 0
        ORDER BY total DESC
        LIMIT :lim
        """,
        params,
    )

    top_ids = {r["person_id"] for r in disp_rows} | {r["person_id"] for r in keeper_rows}
    name_map: dict[str, str] = {}
    team_map: dict[str, str] = {}
    if top_ids:
        placeholders = ",".join(f":n{i}" for i in range(len(top_ids)))
        name_params = {f"n{i}": pid for i, pid in enumerate(top_ids)}
        name_rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({placeholders})",
            name_params,
        )
        name_map = {r["id"]: r["name"] for r in name_rows}
        # Fielder's team = the side NOT batting in this innings (they're
        # in the field). Same shape as bowlers.
        team_rows = await db.q(
            f"""
            SELECT fc.fielder_id AS pid,
                   CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS team,
                   COUNT(*) AS n
            FROM fieldingcredit fc
            JOIN delivery d ON d.id = fc.delivery_id
            JOIN innings i ON i.id = d.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE fc.fielder_id IN ({placeholders})
              AND i.super_over = 0 AND {where}
            GROUP BY fc.fielder_id, team
            """,
            {**params, **name_params},
        )
        per_pid: dict[str, tuple[str, int]] = {}
        for r in team_rows:
            pid, team, n = r["pid"], r["team"], r["n"] or 0
            if pid not in per_pid or n > per_pid[pid][1]:
                per_pid[pid] = (team, n)
        team_map = {pid: v[0] for pid, v in per_pid.items()}

    def _pack(rows):
        out = []
        for r in rows:
            d = dict(r)
            d["name"] = name_map.get(d["person_id"], d["person_id"])
            d["team"] = team_map.get(d["person_id"])
            out.append(d)
        return out

    return {
        "by_dismissals": _pack(disp_rows),
        "by_keeper_dismissals": _pack(keeper_rows),
    }


# ─── Partnership endpoints ────────────────────────────────────────────
#
# Tournament-scoped partnership aggregates. These serve two use cases:
# 1. The Partnerships tab on the tournament dossier.
# 2. Baseline for the Teams page — call without `filter_team` to get
#    "average 1st-wicket partnership in IPL 2024"; call with a specific
#    team to get their batting partnerships; overlay.
#
# When `filter_team` is set via FilterParams, the endpoint scopes to
# partnerships where that team was batting (side='batting') or against
# whom the partnerships were scored (side='bowling'). Without a team
# filter, returns all partnerships in the tournament scope.


def _partnership_tournament_where(
    filters: FilterParams, tournament: str | None,
    side: str = "batting",
    series_type: str | None = None,
) -> tuple[str, dict]:
    """Build WHERE for partnership queries scoped by tournament + filters.

    side='batting': partnerships of `filter_team` (if set) or any team.
    side='bowling': partnerships conceded by `filter_team`.
    """
    where, params = _tournament_scope_where(
        filters, tournament, series_type=series_type,
    )
    clauses = [where, "i.super_over = 0"]
    # Innings-level scoping: when filter_team is set, narrow to which
    # side was batting (already match-scoped to involve the team via
    # _build_filter_clauses). The match-level :filter_team bind is
    # reused so the dict update is a no-op (same value).
    if filters.team:
        if side == "batting":
            clauses.append("i.team = :filter_team")
        else:
            clauses.append("i.team != :filter_team")
        params["filter_team"] = filters.team
    return " AND ".join(clauses), params


@router.get("/series/partnerships/by-wicket")
async def tournament_partnerships_by_wicket(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
):
    """Per-wicket partnership rollup for the tournament.

    Without `filter_team`: tournament-wide average per wicket (a
    baseline). With `filter_team`: partnerships for/against that team.
    """
    if side not in ("batting", "bowling"):
        side = "batting"
    db = get_db()
    where, params = _partnership_tournament_where(
        filters, tournament, side, series_type=series_type,
    )

    rows = await db.q(
        f"""
        SELECT p.wicket_number,
               COUNT(*) AS n,
               ROUND(AVG(p.partnership_runs), 1) AS avg_runs,
               ROUND(AVG(p.partnership_balls), 1) AS avg_balls,
               MAX(p.partnership_runs) AS best_runs
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

    # Enrich each wicket row with the single best-partnership detail
    # (batter names/ids, match, date, season) so multi-edition scope is
    # disambiguated and the date column can deep-link to the scorecard
    # with both batters highlighted.
    by_wicket = []
    for r in rows:
        wn = r["wicket_number"]
        best_rows = await db.q(
            f"""
            SELECT p.partnership_runs AS runs,
                   p.partnership_balls AS balls,
                   p.batter1_id, p.batter1_name, p.batter2_id, p.batter2_name,
                   m.id AS match_id, m.season,
                   (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date,
                   i.team AS batting_team,
                   CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS opponent
            FROM partnership p
            JOIN innings i ON i.id = p.innings_id
            JOIN match m ON m.id = i.match_id
            WHERE {where}
              AND p.wicket_number = :wn
              AND p.partnership_runs = :best
              AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
            ORDER BY p.id LIMIT 1
            """,
            {**params, "wn": wn, "best": r["best_runs"]},
        )
        best_detail = None
        if best_rows:
            br = best_rows[0]
            best_detail = {
                "runs": br["runs"], "balls": br["balls"],
                "match_id": br["match_id"],
                "season": br["season"],
                "date": br["date"],
                "batting_team": br["batting_team"],
                "opponent": br["opponent"],
                "batter1": {"person_id": br["batter1_id"], "name": br["batter1_name"]},
                "batter2": {"person_id": br["batter2_id"], "name": br["batter2_name"]},
            }
        by_wicket.append({
            "wicket_number": wn,
            "n": r["n"],
            "avg_runs": r["avg_runs"],
            "avg_balls": r["avg_balls"],
            "best_runs": r["best_runs"],
            "best_partnership": best_detail,
        })

    return {
        "tournament": tournament,
        "side": side,
        "filter_team": filters.team,
        "by_wicket": by_wicket,
    }


@router.get("/series/partnerships/top")
async def tournament_partnerships_top(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
    limit: int = Query(10, ge=1, le=50),
):
    """Top-N partnerships in the tournament scope."""
    if side not in ("batting", "bowling"):
        side = "batting"
    db = get_db()
    where, params = _partnership_tournament_where(
        filters, tournament, side, series_type=series_type,
    )
    params["lim"] = limit

    rows = await db.q(
        f"""
        SELECT p.id AS partnership_id,
               p.partnership_runs AS runs,
               p.partnership_balls AS balls,
               p.wicket_number, p.unbroken, p.ended_by_kind,
               p.batter1_id, p.batter1_name, p.batter1_runs, p.batter1_balls,
               p.batter2_id, p.batter2_name, p.batter2_runs, p.batter2_balls,
               m.id AS match_id, m.season, m.event_name AS event_name_raw,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date,
               i.team AS batting_team,
               CASE WHEN i.team = m.team1 THEN m.team2 ELSE m.team1 END AS opponent
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
        ORDER BY p.partnership_runs DESC, p.partnership_balls ASC
        LIMIT :lim
        """,
        params,
    )
    out = []
    for r in rows:
        out.append({
            "partnership_id": r["partnership_id"],
            "runs": r["runs"],
            "balls": r["balls"],
            "wicket_number": r["wicket_number"],
            "unbroken": bool(r["unbroken"]),
            "ended_by_kind": r["ended_by_kind"],
            "match_id": r["match_id"],
            "season": r["season"],
            "tournament": canonicalize(r["event_name_raw"]),
            "date": r["date"],
            "batting_team": r["batting_team"],
            "opponent": r["opponent"],
            "batter1": {
                "person_id": r["batter1_id"], "name": r["batter1_name"],
                "runs": r["batter1_runs"], "balls": r["batter1_balls"],
            },
            "batter2": {
                "person_id": r["batter2_id"], "name": r["batter2_name"],
                "runs": r["batter2_runs"], "balls": r["batter2_balls"],
            },
        })
    return {
        "tournament": tournament,
        "side": side,
        "filter_team": filters.team,
        "partnerships": out,
    }


@router.get("/series/partnerships/heatmap")
async def tournament_partnerships_heatmap(
    tournament: str | None = Query(None),
    series_type: str | None = Query(None),
    filters: FilterParams = Depends(),
    side: str = Query("batting"),
):
    """Season × wicket avg-runs heatmap for the tournament."""
    if side not in ("batting", "bowling"):
        side = "batting"
    db = get_db()
    where, params = _partnership_tournament_where(
        filters, tournament, side, series_type=series_type,
    )

    rows = await db.q(
        f"""
        SELECT m.season, p.wicket_number,
               COUNT(*) AS n,
               ROUND(AVG(p.partnership_runs), 1) AS avg_runs
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE {where}
          AND p.wicket_number IS NOT NULL
          AND p.ended_by_kind NOT IN ('retired hurt', 'retired not out')
        GROUP BY m.season, p.wicket_number
        """,
        params,
    )
    seasons = sorted({r["season"] for r in rows})
    wickets = sorted({r["wicket_number"] for r in rows})
    cells = [
        {"season": r["season"], "wicket_number": r["wicket_number"],
         "avg_runs": r["avg_runs"], "n": r["n"]}
        for r in rows
    ]
    return {
        "tournament": tournament,
        "side": side,
        "filter_team": filters.team,
        "seasons": seasons,
        "wickets": wickets,
        "cells": cells,
    }


# ─── Rivalry endpoints ────────────────────────────────────────────────


@router.get("/series/other-rivalries")
async def tournaments_other_rivalries(filters: FilterParams = Depends()):
    """Pairs outside the default top-9 grid with ≥ 5 matches in scope.

    Lazy-loaded by the landing page's "Show other rivalries" expander.
    """
    db = get_db()
    if filters.team_type == "club":
        return {"rivalries": [], "threshold": 5}

    clauses, params = _build_filter_clauses(filters)
    clauses.append(_t20_match_clause())
    clauses.append("m.team_type = 'international'")
    top_clause1 = event_name_in_clause(BILATERAL_TOP_TEAMS, col="m.team1")
    top_clause2 = event_name_in_clause(BILATERAL_TOP_TEAMS, col="m.team2")
    clauses.append(f"NOT ({top_clause1} AND {top_clause2})")
    where = " AND ".join(clauses)

    rows = await db.q(
        f"""
        WITH p AS (
          SELECT CASE WHEN m.team1 < m.team2 THEN m.team1 ELSE m.team2 END AS a,
                 CASE WHEN m.team1 < m.team2 THEN m.team2 ELSE m.team1 END AS b,
                 m.outcome_winner AS winner,
                 m.outcome_result AS result
          FROM match m
          WHERE {where}
        )
        SELECT a, b, COUNT(*) AS matches,
               SUM(CASE WHEN winner = a THEN 1 ELSE 0 END) AS a_wins,
               SUM(CASE WHEN winner = b THEN 1 ELSE 0 END) AS b_wins,
               SUM(CASE WHEN result = 'tie' THEN 1 ELSE 0 END) AS ties,
               SUM(CASE WHEN result = 'no result' THEN 1 ELSE 0 END) AS nr
        FROM p GROUP BY a, b HAVING COUNT(*) >= 5
        ORDER BY COUNT(*) DESC
        """,
        params,
    )
    return {
        "rivalries": [
            {
                "team1": r["a"], "team2": r["b"],
                "matches": r["matches"],
                "team1_wins": r["a_wins"], "team2_wins": r["b_wins"],
                "ties": r["ties"], "no_result": r["nr"],
            }
            for r in rows
        ],
        "threshold": 5,
    }


@router.get("/rivalries/summary")
async def rivalry_summary(
    team1: str = Query(...),
    team2: str = Query(...),
    filters: FilterParams = Depends(),
):
    """Synthesized bilateral rivalry dossier across all international meetings.

    Unordered — team1 / team2 are normalized alphabetically internally so
    swapping the URL params returns the same payload.

    Honours FilterBar gender / tournament / season_from / season_to.
    Excluded: team_type (always international — rivalries are
    inter-national by definition).

    Reused by polymorphic /head-to-head (enhancement B).
    """
    db = get_db()
    a, b = sorted([team1, team2])

    clauses, params = _build_filter_clauses(filters)
    clauses.append(_t20_match_clause())
    clauses.append("m.team_type = 'international'")
    clauses.append(
        "((m.team1 = :a AND m.team2 = :b) OR (m.team1 = :b AND m.team2 = :a))"
    )
    params["a"] = a
    params["b"] = b
    where = " AND ".join(clauses)

    # Match-level aggregates
    m_rows = await db.q(
        f"""
        SELECT COUNT(*) AS matches,
               SUM(CASE WHEN m.outcome_winner = :a THEN 1 ELSE 0 END) AS a_wins,
               SUM(CASE WHEN m.outcome_winner = :b THEN 1 ELSE 0 END) AS b_wins,
               SUM(CASE WHEN m.outcome_result = 'tie' THEN 1 ELSE 0 END) AS ties,
               SUM(CASE WHEN m.outcome_result = 'no result' THEN 1 ELSE 0 END) AS nr
        FROM match m
        WHERE {where}
        """,
        params,
    )
    mstats = m_rows[0] if m_rows else {}
    matches_n = mstats.get("matches", 0) or 0
    if matches_n == 0:
        return {
            "team1": team1, "team2": team2, "matches": 0,
            "team1_wins": 0, "team2_wins": 0, "ties": 0, "no_result": 0,
            "last_match": None, "by_series_type": {},
            "top_scorer_in_rivalry": None, "top_wicket_taker_in_rivalry": None,
            "highest_individual": None, "largest_partnership": None,
            "closest_match": None, "biggest_win": None,
        }

    # Map a/b back to input team1/team2 order for the response
    t1_wins = mstats["a_wins"] if team1 == a else mstats["b_wins"]
    t2_wins = mstats["b_wins"] if team1 == a else mstats["a_wins"]

    # Last match
    last_rows = await db.q(
        f"""
        SELECT m.id AS match_id,
               m.outcome_winner AS winner,
               m.outcome_result AS result,
               m.outcome_by_runs AS by_runs,
               m.outcome_by_wickets AS by_wickets,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where}
        ORDER BY (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) DESC
        LIMIT 1
        """,
        params,
    )
    last_match = None
    if last_rows:
        r = last_rows[0]
        by_str = None
        if r["by_runs"] is not None:
            by_str = f"{r['by_runs']} runs"
        elif r["by_wickets"] is not None:
            by_str = f"{r['by_wickets']} wickets"
        last_match = {
            "match_id": r["match_id"],
            "date": r["date"],
            "winner": r["winner"],
            "result": r["result"],
            "by": by_str,
        }

    # Split by series type (ICC event / bilateral / other)
    type_rows = await db.q(
        f"""
        SELECT m.event_name AS ev, COUNT(*) AS n
        FROM match m
        WHERE {where}
        GROUP BY m.event_name
        """,
        params,
    )
    by_series_type = {"icc_event": 0, "bilateral_tour": 0, "other": 0}
    for r in type_rows:
        canon = canonicalize(r["ev"])
        if canon is None:
            by_series_type["bilateral_tour"] += r["n"]
        elif canon in ICC_EVENT_NAMES:
            by_series_type["icc_event"] += r["n"]
        elif series_type(canon) == "icc_event":
            by_series_type["icc_event"] += r["n"]
        elif r["ev"] and ("tour of" in r["ev"].lower()):
            by_series_type["bilateral_tour"] += r["n"]
        else:
            by_series_type["other"] += r["n"]

    # Top scorer in rivalry
    ts_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id, p.name,
               SUM(d.runs_batter) AS runs
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE i.super_over = 0 AND {where}
          AND d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id
        ORDER BY runs DESC LIMIT 1
        """,
        params,
    )
    top_scorer = None
    if ts_rows:
        r = ts_rows[0]
        top_scorer = {"person_id": r["person_id"], "name": r["name"], "runs": r["runs"]}

    # Top wicket-taker in rivalry
    tw_rows = await db.q(
        f"""
        SELECT d.bowler_id AS person_id, p.name, COUNT(*) AS wickets
        FROM wicket w
        JOIN delivery d ON d.id = w.delivery_id
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.bowler_id
        WHERE i.super_over = 0 AND {where}
          AND d.bowler_id IS NOT NULL
          AND w.kind NOT IN ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        GROUP BY d.bowler_id
        ORDER BY wickets DESC LIMIT 1
        """,
        params,
    )
    top_wicket = None
    if tw_rows:
        r = tw_rows[0]
        top_wicket = {"person_id": r["person_id"], "name": r["name"], "wickets": r["wickets"]}

    # Highest individual score in rivalry
    hi_rows = await db.q(
        f"""
        SELECT d.batter_id AS person_id, p.name,
               m.id AS match_id,
               SUM(d.runs_batter) AS runs,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM delivery d
        JOIN innings i ON i.id = d.innings_id
        JOIN match m ON m.id = i.match_id
        LEFT JOIN person p ON p.id = d.batter_id
        WHERE i.super_over = 0 AND {where}
          AND d.batter_id IS NOT NULL
          AND d.extras_wides = 0 AND d.extras_noballs = 0
        GROUP BY d.batter_id, m.id
        ORDER BY runs DESC LIMIT 1
        """,
        params,
    )
    highest_individual = None
    if hi_rows:
        r = hi_rows[0]
        highest_individual = {
            "person_id": r["person_id"], "name": r["name"],
            "runs": r["runs"], "match_id": r["match_id"], "date": r["date"],
        }

    # Largest partnership
    lp_rows = await db.q(
        f"""
        SELECT p.partnership_runs AS runs, m.id AS match_id
        FROM partnership p
        JOIN innings i ON i.id = p.innings_id
        JOIN match m ON m.id = i.match_id
        WHERE i.super_over = 0 AND {where}
        ORDER BY p.partnership_runs DESC LIMIT 1
        """,
        params,
    )
    largest_partnership = None
    if lp_rows:
        r = lp_rows[0]
        largest_partnership = {"runs": r["runs"], "match_id": r["match_id"]}

    # Closest match (smallest margin wins)
    cm_rows = await db.q(
        f"""
        SELECT m.outcome_by_runs AS by_runs,
               m.outcome_by_wickets AS by_wickets,
               m.outcome_winner AS winner,
               m.id AS match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where}
          AND (m.outcome_by_runs IS NOT NULL OR m.outcome_by_wickets IS NOT NULL)
        ORDER BY
          CASE WHEN m.outcome_by_runs IS NOT NULL THEN m.outcome_by_runs
               ELSE 1000 END ASC,
          m.outcome_by_wickets ASC
        LIMIT 1
        """,
        params,
    )
    closest_match = None
    if cm_rows:
        r = cm_rows[0]
        margin = f"{r['by_runs']} runs" if r["by_runs"] is not None else f"{r['by_wickets']} wickets"
        closest_match = {
            "margin": margin,
            "winner": r["winner"],
            "match_id": r["match_id"],
            "date": r["date"],
        }

    # Biggest win (by runs)
    bw_rows = await db.q(
        f"""
        SELECT m.outcome_by_runs AS margin,
               m.outcome_winner AS winner,
               m.id AS match_id,
               (SELECT MIN(date) FROM matchdate WHERE match_id = m.id) AS date
        FROM match m
        WHERE {where} AND m.outcome_by_runs IS NOT NULL
        ORDER BY m.outcome_by_runs DESC LIMIT 1
        """,
        params,
    )
    biggest_win = None
    if bw_rows:
        r = bw_rows[0]
        biggest_win = {
            "winner": r["winner"],
            "margin": f"{r['margin']} runs",
            "match_id": r["match_id"],
            "date": r["date"],
        }

    return {
        "team1": team1,
        "team2": team2,
        "matches": matches_n,
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "ties": mstats.get("ties", 0) or 0,
        "no_result": mstats.get("nr", 0) or 0,
        "last_match": last_match,
        "by_series_type": by_series_type,
        "top_scorer_in_rivalry": top_scorer,
        "top_wicket_taker_in_rivalry": top_wicket,
        "highest_individual": highest_individual,
        "largest_partnership": largest_partnership,
        "closest_match": closest_match,
        "biggest_win": biggest_win,
    }
