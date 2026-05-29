"""Sanity: update_recent.pick_window only ever returns a cricsheet bundle
that is actually published.

Cricsheet publishes "recently_added_<N>_json.zip" bulk bundles for a
shifting set of windows. As of 2026-05-29 it serves 2 / 7 / 30 but NOT
14 (the 14-day URL 404s). The bug this guards: AVAILABLE_WINDOWS listed
14, so pick_window(d) for d in 8..14 rounded UP to 14 and the download
crashed with HTTP 404. The fix drops 14, so that range rounds to 30.

No network — pick_window is a pure function over AVAILABLE_WINDOWS.

Usage:
  uv run python tests/sanity/test_pick_window.py
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from update_recent import AVAILABLE_WINDOWS, pick_window


def test_no_unpublished_14day_bundle():
    # cricsheet no longer serves the 14-day bundle.
    assert 14 not in AVAILABLE_WINDOWS, (
        f"14 is in AVAILABLE_WINDOWS={AVAILABLE_WINDOWS} but cricsheet "
        f"404s recently_added_14_json.zip"
    )


def test_8_to_14_day_range_rounds_to_live_bundle():
    # The gap left by dropping 14: days 8..14 must round up to 30 (the
    # next live bundle), never to a window that 404s.
    for d in range(8, 15):
        w = pick_window(d)
        assert w in AVAILABLE_WINDOWS, f"pick_window({d})={w} not available"
        assert w == 30, f"pick_window({d})={w}, expected 30"


def test_small_windows_unchanged():
    assert pick_window(1) == 2
    assert pick_window(2) == 2
    assert pick_window(5) == 7
    assert pick_window(7) == 7
    assert pick_window(30) == 30
    assert pick_window(100) == 30  # beyond largest → clamp to largest


if __name__ == "__main__":
    test_no_unpublished_14day_bundle()
    test_8_to_14_day_range_rounds_to_live_bundle()
    test_small_windows_unchanged()
    print("PASS: pick_window only returns published cricsheet bundles")
