"""Batter-position derivation for one innings.

Shared helper used by:
  - scripts/populate_player_scope_stats.py (parent table — fills
    `avg_batting_position` and `innings_by_position_json`).
  - scripts/populate_playerscopestats_position.py (batting per-
    position child table — Phase 2a of spec-player-compare-average.md).
  - scripts/populate_playerscopestats_fielding_position.py (fielding
    dismissed-batter position child table — Phase 2c).

The populate scripts batch-fetch deliveries for many innings at once
and group them by innings_id; this helper takes one innings's
pre-sorted delivery list and returns the position vector for that
innings. Computing once per innings and sharing across the three
populate scripts is the contract — do not call this once per child
table per innings; that would re-derive the same positions three
times.

Position convention: per innings, position 1 = striker on the first
delivery; position 2 = non_striker on the first delivery; each
subsequent newcomer in delivery order takes the next position number.
The 11-batter convention caps things — anything beyond the 11th
distinct batter (very rare 12th-man / concussion-sub edge cases) is
bucketed into position 11.
"""

from __future__ import annotations


def derive_positions(deliveries: list[dict]) -> dict[str, int]:
    """Return {person_id: position} for one innings, by delivery order.

    Args:
        deliveries: list of delivery row dicts for ONE innings, pre-
            sorted ascending by (over_number, delivery_index, id).
            Each dict must carry at minimum ``batter_id`` and
            ``non_striker_id`` keys.

    Returns:
        dict mapping each batter's person_id to a position 1..11.

    The first delivery contributes positions 1 and 2 (striker +
    non_striker). Subsequent deliveries contribute position 3, 4, …
    each time a new person_id appears. NULL person_ids are skipped.

    The 11-batter convention is enforced: anything beyond 11 distinct
    batters is bucketed into position 11 (rare 12th-man / concussion-
    sub edge cases that the populate aggregations also fold into the
    last bucket).
    """
    positions: dict[str, int] = {}
    next_pos = 1
    for d in deliveries:
        for pid in (d["batter_id"], d["non_striker_id"]):
            if pid is None:
                continue
            if pid not in positions:
                if next_pos > 11:
                    positions[pid] = 11
                else:
                    positions[pid] = next_pos
                    next_pos += 1
    return positions
