"""Infer player nationality from the international teams they've played for.

Cricsheet's people registry doesn't carry a nationality field, but the
teams a player appeared for in international matches give an authoritative
answer. Ordered by match count so the "primary" nationality is first.

Used by batting / bowling / fielding / head-to-head summary endpoints
to surface flags next to player names.
"""

from __future__ import annotations


async def player_nationalities(db, person_id: str) -> list[dict]:
    """Return the international teams this player has appeared for,
    ordered by match count desc. Empty list if the player has only
    played club cricket (no inferable nationality → no flag rendered).

    Shape:
        [{"team": "England", "matches": 70},
         {"team": "Ireland", "matches": 21}]
    """
    rows = await db.q(
        """
        SELECT mp.team AS team, COUNT(DISTINCT m.id) AS matches
        FROM matchplayer mp
        JOIN match m ON m.id = mp.match_id
        WHERE mp.person_id = :pid
          AND m.team_type = 'international'
        GROUP BY mp.team
        ORDER BY matches DESC, mp.team
        """,
        {"pid": person_id},
    )
    return [{"team": r["team"], "matches": r["matches"]} for r in rows]
