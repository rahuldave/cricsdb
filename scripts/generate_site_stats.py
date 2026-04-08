#!/usr/bin/env python3
"""
Generate frontend/src/generated/site-stats.json from cricket.db.

The home page reads this file at build time so the totals in the
masthead and the "featured" section update whenever the database
is rebuilt or incrementally updated. Hooked into import_data.py
and update_recent.py so it runs automatically.

To run by hand:
    uv run python scripts/generate_site_stats.py

Featured teams / players / matchups are CURATED — edit the lists
below to change what shows on the home page. The script just
fills in the live counts.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "cricket.db"
OUT_PATH = ROOT / "frontend" / "src" / "generated" / "site-stats.json"


# ─────────────────────────────────────────────────────────────────────
# Curated featured lists. Edit here, not in the frontend.
# ─────────────────────────────────────────────────────────────────────

FEATURED_TEAMS = [
    # name                            blurb
    ("Royal Challengers Bengaluru",   "IPL & WPL"),
    ("Chennai Super Kings",           "IPL"),
    ("India",                         "International"),
    ("Australia",                     "International"),
]

FEATURED_PLAYERS = [
    # id          name           role        gender
    ("ba607b88", "V Kohli",      "batter",   "male"),
    ("462411b3", "JJ Bumrah",    "bowler",   "male"),
    ("5d2eda89", "S Mandhana",   "batter",   "female"),
    ("be150fc8", "EA Perry",     "bowler",   "female"),
]

FEATURED_MATCHUPS = [
    # batter_id      bowler_id      label
    ("740742ef",    "ce820073",    "RG Sharma vs Sandeep Sharma"),
    ("d32cf49a",    "63e3b6b3",    "HK Matthews vs M Kapp"),
]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"cricket.db not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ─── Site totals ───────────────────────────────────────────────
    matches = c.execute("SELECT COUNT(*) FROM match").fetchone()[0]
    deliveries = c.execute("SELECT COUNT(*) FROM delivery").fetchone()[0]
    wickets = c.execute("SELECT COUNT(*) FROM wicket").fetchone()[0]

    # ─── Featured teams: live match counts ─────────────────────────
    teams_out = []
    for name, blurb in FEATURED_TEAMS:
        n = c.execute(
            "SELECT COUNT(*) FROM match WHERE team1 = ? OR team2 = ?",
            (name, name),
        ).fetchone()[0]
        teams_out.append({"name": name, "blurb": blurb, "matches": n})

    # ─── Featured players: live career stats ───────────────────────
    players_out = []
    for pid, name, role, gender in FEATURED_PLAYERS:
        if role == "batter":
            row = c.execute(
                """
                SELECT COALESCE(SUM(runs_batter), 0) as runs
                FROM delivery
                WHERE batter_id = ? AND extras_wides = 0 AND extras_noballs = 0
                """,
                (pid,),
            ).fetchone()
            stat = f"{row['runs']:,} runs"
        else:  # bowler
            row = c.execute(
                """
                SELECT COUNT(*) as wkts
                FROM wicket w
                JOIN delivery d ON d.id = w.delivery_id
                WHERE d.bowler_id = ?
                  AND w.kind NOT IN
                      ('run out','retired hurt','retired out','obstructing the field')
                """,
                (pid,),
            ).fetchone()
            stat = f"{row['wkts']} wkts"
        players_out.append({
            "id": pid,
            "name": name,
            "role": role,
            "gender": gender,
            "stat": stat,
        })

    # ─── Featured matchups: live ball / dismissal counts ───────────
    matchups_out = []
    for bat_id, bowl_id, label in FEATURED_MATCHUPS:
        row = c.execute(
            """
            SELECT
                COUNT(*) as balls,
                COALESCE(SUM(runs_batter), 0) as runs
            FROM delivery
            WHERE batter_id = ? AND bowler_id = ?
              AND extras_wides = 0 AND extras_noballs = 0
            """,
            (bat_id, bowl_id),
        ).fetchone()
        matchups_out.append({
            "batter_id": bat_id,
            "bowler_id": bowl_id,
            "label": label,
            "stat": f"{row['runs']} off {row['balls']}",
        })

    payload = {
        "totals": {
            "matches": matches,
            "deliveries": deliveries,
            "wickets": wickets,
        },
        "featured_teams": teams_out,
        "featured_players": players_out,
        "featured_matchups": matchups_out,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    print(f"  totals:  {matches:,} matches, {deliveries:,} deliveries, {wickets:,} wickets")
    print(f"  teams:   {len(teams_out)}")
    print(f"  players: {len(players_out)}")
    print(f"  H2H:     {len(matchups_out)}")


if __name__ == "__main__":
    main()
