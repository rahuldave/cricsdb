"""Per-page social-card meta for the SPA fallback handler.

When someone shares a deep link to T20 & CricsDB on Twitter / Slack /
iMessage / Discord / LinkedIn, the receiving platform's scraper
fetches the URL ONCE and parses the static HTML head. It doesn't run
JavaScript, so client-side `useDocumentTitle` can't reach it. This
module rewrites `<title>`, `og:title`, `og:description`, `og:url`,
`twitter:title`, `twitter:description`, and `<meta name="description">`
per-route so shared cards carry page-specific content.

Card image stays static (`og-card.png`) — per-page image generation
is more work and not asked-for; the wordmark card is a fine fallback.

Covers:
  /teams?team=X[&tab=Y[&compare1=Z[&compare2=W]]]  → Team / Compare
  /series?tournament=X                              → Series dossier
  /venues?venue=X                                   → Venue dossier
  /head-to-head?mode=team&team1=A&team2=B           → Team rivalry
  /head-to-head?mode=player&player=A&compare=B      → Player rivalry
  /players?player=<id>[&compare=<id>[,<id>]]        → Player profile / compare
  /batting?player=<id>                              → Player batting
  /bowling?player=<id>                              → Player bowling
  /fielding?player=<id>                             → Player fielding
  /matches/<match_id>                               → Match scorecard

Player + match routes carry opaque IDs as their identifying param,
so `build_meta` is async and queries the DB to resolve human names.
Param-only routes don't need the DB but stay in the same async
function for uniformity. On lookup failure (id not in DB, transient
DB error) the function falls back to the static site card — never
raises out of the SPA fallback path.

Spec: user feedback 2026-04-29 — "what do we title and twitter card
pages like this?"
"""
from __future__ import annotations

import re
from typing import Any

from .dependencies import get_db

SITE_NAME = "T20 & CricsDB"
SITE_BASE = "https://t20.rahuldave.com"
DEFAULT_DESCRIPTION = (
    "An almanack of Twenty20 cricket — 13,019 matches, 2.95M "
    "deliveries, across international and club competition the world over."
)
DEFAULT_TITLE = f"{SITE_NAME} — An almanack of Twenty20 cricket"


async def _lookup_persons(person_ids: list[str]) -> dict[str, str]:
    """Resolve {person_id: name} for the supplied IDs. Empty input or
    DB failure both return an empty dict — caller falls back to the
    raw ID string in that case (never raises)."""
    person_ids = [p for p in person_ids if p]
    if not person_ids:
        return {}
    try:
        db = get_db()
        # Inline f-string interpolation because deebase bind params
        # don't expand lists for IN-clauses (project convention; see
        # CLAUDE.md "deebase db.q()"). IDs are 8-char hex from
        # cricsheet — sanitise defensively to alphanumeric.
        clean = [pid for pid in person_ids if re.fullmatch(r"[A-Za-z0-9]+", pid)]
        if not clean:
            return {}
        in_list = ",".join(f"'{pid}'" for pid in clean)
        rows = await db.q(
            f"SELECT id, name FROM person WHERE id IN ({in_list})", {},
        )
        return {r["id"]: r["name"] for r in rows}
    except Exception:
        return {}


async def _lookup_match(match_id: str) -> dict[str, Any] | None:
    """Resolve match identity (teams, season, event_name, gender) for
    a given match_id. Returns None on parse failure / missing match."""
    if not match_id:
        return None
    try:
        mid = int(match_id)
    except ValueError:
        return None
    try:
        db = get_db()
        rows = await db.q(
            "SELECT id, team1, team2, season, event_name, gender, "
            "venue, city, outcome_winner FROM match WHERE id = :mid",
            {"mid": mid},
        )
        return rows[0] if rows else None
    except Exception:
        return None


async def build_meta(path: str, query: dict) -> dict:
    """Return {title, description, url} for a given SPA route.

    `path` is the SPA route (e.g. "teams"); `query` is a flat
    {key: value} dict from the URL's query string. Falls back to the
    site-wide title/description when the route doesn't match a known
    pattern (or when the relevant identifying param is missing /
    fails DB lookup). Async so player + match routes can resolve
    human names from opaque IDs.
    """
    p = path.strip("/")

    title = DEFAULT_TITLE
    description = DEFAULT_DESCRIPTION

    # Reconstruct the canonical URL — preserve query params for share
    # parity. Empty query → bare path.
    qs = "&".join(f"{k}={v}" for k, v in query.items() if v)
    url = f"{SITE_BASE}/{p}" if p else f"{SITE_BASE}/"
    if qs:
        url += f"?{qs}"

    team = query.get("team")
    venue = query.get("venue")
    tournament = query.get("tournament")
    tab = query.get("tab") or "Overview"
    compare1 = query.get("compare1")
    compare2 = query.get("compare2")
    mode = query.get("mode")
    team1 = query.get("team1")
    team2 = query.get("team2")
    series_type = query.get("series_type") or query.get("compare1_series_type")
    season_from = query.get("season_from")
    season_to = query.get("season_to")
    team_class = query.get("team_class")

    # Build a short scope tag for the description ("men's IPL 2024",
    # "women's bilateral T20Is", etc.) — best-effort, skipped when no
    # narrowing is set so descriptions don't end with empty bullets.
    scope_bits = []
    if query.get("gender") == "male":
        scope_bits.append("men's")
    elif query.get("gender") == "female":
        scope_bits.append("women's")
    if tournament:
        scope_bits.append(tournament)
    elif series_type in ("bilateral", "bilateral_only"):
        scope_bits.append("bilateral T20Is")
    elif series_type in ("icc", "tournament_only"):
        scope_bits.append("ICC events")
    if season_from and season_to:
        scope_bits.append(season_from if season_from == season_to else f"{season_from}–{season_to}")
    elif season_from:
        scope_bits.append(f"{season_from}+")
    elif season_to:
        scope_bits.append(f"–{season_to}")
    if team_class == "full_member":
        scope_bits.append("full-member only")
    scope_tag = " · ".join(scope_bits)

    if p == "teams" and team:
        if tab == "Compare":
            others = [c for c in (compare1, compare2) if c and c != "__avg__"]
            avg_present = (compare1 == "__avg__") or (compare2 == "__avg__")
            entities = [team] + others
            if avg_present:
                entities.append("avg team")
            title = f"{' vs '.join(entities)} — Compare · {SITE_NAME}"
            desc = f"Side-by-side T20 stats: {', '.join(entities)}"
            if scope_tag:
                desc += f" · {scope_tag}"
            description = desc + "."
        else:
            title = f"{team} — {tab} · {SITE_NAME}"
            description = f"T20 {tab.lower()} for {team}"
            if scope_tag:
                description += f" — {scope_tag}"
            description += "."

    elif p == "venues" and venue:
        title = f"{venue} — Venue · {SITE_NAME}"
        description = f"T20 matches and stats at {venue}"
        if scope_tag:
            description += f" — {scope_tag}"
        description += "."

    elif p == "series" and tournament:
        title = f"{tournament} — Series · {SITE_NAME}"
        # Drop tournament from scope_tag — it's already in the title +
        # the description's primary subject. Keep the rest (gender,
        # season, team_class).
        scope_no_tournament = " · ".join(b for b in scope_bits if b != tournament)
        description = f"T20 series dossier: {tournament}"
        if scope_no_tournament:
            description += f" — {scope_no_tournament}"
        description += "."

    elif p == "head-to-head" and mode == "team" and team1 and team2:
        title = f"{team1} v {team2} — Head to Head · {SITE_NAME}"
        description = f"T20 head-to-head: {team1} v {team2}"
        if scope_tag:
            description += f" — {scope_tag}"
        description += "."

    # ─── Player routes (opaque IDs → DB lookup) ──────────────────────
    # /players?player=X[&compare=Y[,Z]]    /batting?player=X
    # /bowling?player=X    /fielding?player=X    /head-to-head?mode=player
    elif p in ("players", "batting", "bowling", "fielding") or (p == "head-to-head" and mode == "player"):
        player_id = query.get("player")
        compare_csv = query.get("compare") or ""
        compare_ids = [c.strip() for c in compare_csv.split(",") if c.strip()]
        if player_id:
            names = await _lookup_persons([player_id] + compare_ids)
            primary_name = names.get(player_id, player_id)
            others = [names.get(cid, cid) for cid in compare_ids]
            page_label = {
                "players":     "Player",
                "batting":     "Batting",
                "bowling":     "Bowling",
                "fielding":    "Fielding",
                "head-to-head": "Head to Head",
            }[p]
            if others:
                title = f"{primary_name} vs {' vs '.join(others)} — {page_label} · {SITE_NAME}"
                description = f"T20 {page_label.lower()}: {primary_name} vs {', '.join(others)}"
            else:
                title = f"{primary_name} — {page_label} · {SITE_NAME}"
                description = f"T20 {page_label.lower()} stats for {primary_name}"
            if scope_tag:
                description += f" — {scope_tag}"
            description += "."

    # ─── Match scorecard ─────────────────────────────────────────────
    # /matches/<id>      (the non-list match URL — list page /matches
    # has no identifying ID and falls through to default.)
    elif p.startswith("matches/"):
        match_id = p[len("matches/"):]
        m = await _lookup_match(match_id)
        if m:
            t1, t2 = m.get("team1") or "?", m.get("team2") or "?"
            season = m.get("season") or ""
            event = m.get("event_name") or ""
            venue = m.get("venue") or ""
            winner = m.get("outcome_winner") or ""
            title = f"{t1} v {t2} — Scorecard · {SITE_NAME}"
            desc_bits = []
            if event: desc_bits.append(event)
            if season: desc_bits.append(season)
            if venue: desc_bits.append(f"@ {venue}")
            if winner: desc_bits.append(f"{winner} won")
            description = f"T20 scorecard: {t1} v {t2}"
            if desc_bits:
                description += f" — {' · '.join(desc_bits)}"
            description += "."

    return {"title": title, "description": description, "url": url}


# Patterns match the static index.html. Whitespace tolerant inside the
# tag so future hand-edits to index.html don't silently break injection.
_TITLE_RE   = re.compile(r"<title>[^<]*</title>", re.IGNORECASE)
_OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="[^"]*"\s*/?>', re.IGNORECASE)
_OG_DESC_RE  = re.compile(r'<meta\s+property="og:description"\s+content="[^"]*"\s*/?>', re.IGNORECASE)
_OG_URL_RE   = re.compile(r'<meta\s+property="og:url"\s+content="[^"]*"\s*/?>', re.IGNORECASE)
_TW_TITLE_RE = re.compile(r'<meta\s+name="twitter:title"\s+content="[^"]*"\s*/?>', re.IGNORECASE)
_TW_DESC_RE  = re.compile(r'<meta\s+name="twitter:description"\s+content="[^"]*"\s*/?>', re.IGNORECASE)
_DESC_RE     = re.compile(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>', re.IGNORECASE)


def _esc(s: str) -> str:
    """HTML-attribute-safe escape. Replace order matters — `&` first
    so subsequent `&amp;` substitutions aren't double-escaped."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def inject_meta(html: str, meta: dict) -> str:
    """Substitute the head's <title> + OG/Twitter meta with route-
    specific content. Tags absent from index.html are silently
    ignored (regex .sub on no-match returns the input unchanged)."""
    t = _esc(meta["title"])
    d = _esc(meta["description"])
    u = _esc(meta["url"])
    html = _TITLE_RE.sub(f"<title>{t}</title>", html, count=1)
    html = _DESC_RE.sub(f'<meta name="description" content="{d}" />', html, count=1)
    html = _OG_TITLE_RE.sub(f'<meta property="og:title" content="{t}" />', html, count=1)
    html = _OG_DESC_RE.sub(f'<meta property="og:description" content="{d}" />', html, count=1)
    html = _OG_URL_RE.sub(f'<meta property="og:url" content="{u}" />', html, count=1)
    html = _TW_TITLE_RE.sub(f'<meta name="twitter:title" content="{t}" />', html, count=1)
    html = _TW_DESC_RE.sub(f'<meta name="twitter:description" content="{d}" />', html, count=1)
    return html
