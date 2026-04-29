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

Currently covers param-derivable routes (no DB lookup needed):
  /teams?team=X[&tab=Y[&compare1=Z[&compare2=W]]]  → Team / Compare
  /series?tournament=X                              → Series dossier
  /venues?venue=X                                   → Venue dossier
  /head-to-head?mode=team&team1=A&team2=B           → Rivalry
  /head-to-head?player=A&compare=B                  → Player rivalry

Routes whose subject is encoded as an opaque ID (player/match) need
a DB lookup to resolve the human name; deferred until the per-page
title work expands to those.

Spec: user feedback 2026-04-29 — "what do we title and twitter card
pages like this?"
"""
from __future__ import annotations

import re

SITE_NAME = "T20 & CricsDB"
SITE_BASE = "https://t20.rahuldave.com"
DEFAULT_DESCRIPTION = (
    "An almanack of Twenty20 cricket — 13,019 matches, 2.95M "
    "deliveries, across international and club competition the world over."
)
DEFAULT_TITLE = f"{SITE_NAME} — An almanack of Twenty20 cricket"


def build_meta(path: str, query: dict) -> dict:
    """Return {title, description, url} for a given SPA route.

    `path` is the SPA route (e.g. "teams"); `query` is a flat
    {key: value} dict from the URL's query string. Falls back to the
    site-wide title/description when the route doesn't match a known
    pattern (or when the relevant identifying param is missing).
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
