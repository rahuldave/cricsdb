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

from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..dependencies import get_db
from ..filters import FilterParams

router = APIRouter(prefix="/api/v1/venues", tags=["Venues"])


def _strip_venue(filters: FilterParams) -> tuple[str, dict]:
    """Run filters.build() with filter_venue temporarily cleared.

    Both /venues endpoints are self-referential — they return candidate
    venues and shouldn't narrow to the currently-selected venue (that
    would show only one result).
    """
    saved = filters.venue
    filters.venue = None
    try:
        return filters.build(has_innings_join=False)
    finally:
        filters.venue = saved


@router.get("")
async def list_venues(
    filters: FilterParams = Depends(),
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
    where, params = _strip_venue(filters)

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
async def venues_landing(filters: FilterParams = Depends()):
    """Country-grouped venue directory for the /venues landing page.

    Returns:
      {by_country: [{country, matches, venues: [{venue, city, matches}, …]}, …]}

    Countries ordered by total match count DESC; venues within a
    country ordered by match count DESC. `venue_country IS NULL` rows
    (shouldn't exist in a fully canonicalized DB but defensive) are
    bucketed under the `"Unknown"` country key.
    """
    db = get_db()
    where, params = _strip_venue(filters)

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
