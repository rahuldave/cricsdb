"""Helpers for Distribution-dossier form-window cutoffs.

Single source of truth for the calendar-window anchor logic.
Imported by the batter / bowler / fielder distribution endpoints
so they all compute their last_60d / last_6mo / last_1yr cutoffs
from the same rule.
"""

from __future__ import annotations

from datetime import date


def scope_anchor(observations: list[dict], today: date) -> date:
    """Anchor date for the calendar form-window cutoffs.

    Returns `min(today, max_obs_date)`. For active subjects in
    unconstrained scopes the anchor IS today (max_obs_date is
    near or past today, so the min picks today). For retired
    subjects (Gayle, AB de Villiers) and tightly-scoped subjects
    (single-season filters) the anchor follows the data — the
    form windows then mean "the last N days OF SCOPE" instead of
    producing empty results when today's calendar window doesn't
    intersect the scope's date range.

    Spec: internal_docs/spec-distribution-stats.md §8.6 (revised
    2026-05-07 from today-direct).

    Empty observations → returns `today` (windows are trivially
    empty in that case anyway, so the anchor is irrelevant).

    `as_of_date` query param semantics preserved: callers pass
    in a pinned `today` for deterministic regression. The
    `min(today, max_obs)` rule still anchors on the pin when the
    scope has data through it; otherwise the data wins.
    """
    obs_dates = [o["date"] for o in observations if o.get("date")]
    if not obs_dates:
        return today
    max_obs_date = date.fromisoformat(max(obs_dates))
    return min(today, max_obs_date)
