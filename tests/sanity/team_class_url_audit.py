"""v3 team_class FilterBar — capture-before-and-after URL audit.

For each surface in spec §8.3 matrix, navigate via agent-browser and
capture every /api/v1/ URL the page fires. Two phases:
  - BEFORE (pre-migration): captured by the Phase C subagent on
    2026-04-28; output committed at tests/sanity/team_class_pre_audit.json.
  - AFTER (post-migration): run this script post-commit-5 to capture
    the new state; diff against pre_audit.json.

The diff catches two failure modes:
  1. AFTER URL doesn't carry team_class=full_member when the page URL
     does → backend endpoint not respecting the filter, OR frontend
     dropping the param before fetch.
  2. AFTER set differs from BEFORE in path shape (URLs added/removed)
     → page-level conditional fetch path that depends on team_class.
     Investigate.

Skeleton — implementation deferred to commit 5.

Usage:
  uv run python tests/sanity/team_class_url_audit.py --mode capture
      --output tests/sanity/team_class_post_audit.json

  uv run python tests/sanity/team_class_url_audit.py --mode diff
      --before tests/sanity/team_class_pre_audit.json
      --after  tests/sanity/team_class_post_audit.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any


# Same surface list the Phase C subagent used. Keep in sync.
SURFACES: list[dict[str, str]] = [
    # TODO(commit-5): copy the surface list from the Phase C subagent's
    # output (tests/sanity/team_class_pre_audit.json metadata) so the
    # AFTER capture exercises the identical surfaces.
]


def capture_via_agent_browser(url: str) -> list[str]:
    """Navigate to URL via agent-browser, return /api/v1/ paths fired.

    Pattern (from existing integration scripts):
      agent-browser open "$URL"
      agent-browser wait --load networkidle
      agent-browser eval "<JS>"
    """
    # TODO(commit-5): shell out to agent-browser; collect performance.getEntries.
    raise NotImplementedError


def capture_all() -> dict[str, Any]:
    """Capture all surfaces, return AFTER snapshot dict in same shape
    as BEFORE."""
    raise NotImplementedError


def diff(before: dict, after: dict) -> list[str]:
    """Return list of failure descriptions:
       - URL in after_with_team_class missing &team_class=full_member
       - Path in after but absent in before (or vice versa)
       - Surfaces that loaded fine in BEFORE but errored in AFTER

    Empty list = no silent-ignore bugs.
    """
    failures: list[str] = []
    # TODO(commit-5): per-surface diff.
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("capture", "diff"), required=True)
    parser.add_argument("--output")
    parser.add_argument("--before")
    parser.add_argument("--after")
    args = parser.parse_args()

    if args.mode == "capture":
        snapshot = capture_all()
        with open(args.output, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"Captured {len(snapshot.get('surfaces', []))} surfaces → {args.output}")
        return

    if args.mode == "diff":
        with open(args.before) as f:
            before = json.load(f)
        with open(args.after) as f:
            after = json.load(f)
        failures = diff(before, after)
        if failures:
            print(f"\n{len(failures)} silent-ignore failures:")
            for f in failures:
                print(f"  - {f}")
            sys.exit(1)
        print("\nNo silent-ignore bugs detected.")


if __name__ == "__main__":
    main()
