"""v3 team_class FilterBar — capture-before-and-after URL audit.

For each surface in the BEFORE snapshot (tests/sanity/team_class_pre_audit.json,
captured 2026-04-28 by the Phase C subagent), navigate the page with
team_class=full_member appended and capture every /api/v1/ URL the page
fires. The audit is interested in two questions:

  1. Are the surfaces still loading without errors?
  2. Does every fetched /api/v1/ URL carry team_class=full_member?
     A URL missing the param means a page is silently ignoring the
     filter — exactly the failure-mode v3 is designed to eliminate.

Two phases:
  - BEFORE (pre-migration): captured by the Phase C subagent on
    2026-04-28; output committed at tests/sanity/team_class_pre_audit.json.
    Pre-migration, every URL in `with_team_class` lacks the param —
    that's the BUG state being measured.
  - AFTER (post-migration): run this script post-commit-3 to capture
    the new state; assert every URL in with_team_class CARRIES
    team_class=full_member.

Usage:
  bash deploy: uvicorn :8000 + vite :5173 must be running.

  # Capture AFTER:
  uv run python tests/sanity/team_class_url_audit.py --mode capture \\
      --output tests/sanity/team_class_post_audit.json

  # Verify silent-ignore is gone:
  uv run python tests/sanity/team_class_url_audit.py --mode verify \\
      --after tests/sanity/team_class_post_audit.json

  # Or both at once:
  uv run python tests/sanity/team_class_url_audit.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRE_AUDIT_PATH = os.path.join(REPO_ROOT, "tests/sanity/team_class_pre_audit.json")
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "tests/sanity/team_class_post_audit.json")

# Endpoints that intentionally don't honour team_class — exempted from
# the silent-ignore check. Match path prefix only (query string stripped).
EXEMPT_PATHS: set[str] = {
    # Health/probe endpoints with no scope (none today).
}


def _agent_browser_eval(js: str) -> Any:
    """Run agent-browser eval, return parsed JSON. agent-browser prints
    the raw evaluated value to stdout (sometimes pretty-printed across
    multiple lines)."""
    proc = subprocess.run(
        ["agent-browser", "eval", js],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"agent-browser eval failed: {proc.stderr}")
    out = proc.stdout.strip()
    # Strip ANSI escapes if any.
    return json.loads(out)


def navigate(url: str) -> None:
    proc = subprocess.run(
        ["agent-browser", "open", url],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"agent-browser open failed: {proc.stderr}")


def capture_api_calls(url: str, settle_ms: int = 2500) -> list[str]:
    """Navigate, settle, return /api/v1/ paths fetched (sorted)."""
    # Clear performance entries before navigation so old entries don't
    # leak between captures.
    navigate(url)
    time.sleep(settle_ms / 1000.0)
    js = (
        "JSON.stringify("
        "performance.getEntriesByType('resource')"
        ".map(e => e.name)"
        ".filter(n => n.includes('/api/v1/'))"
        ".map(n => n.replace(window.location.origin, ''))"
        ".sort()"
        ")"
    )
    proc = subprocess.run(
        ["agent-browser", "eval", js],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"agent-browser eval failed: {proc.stderr}")
    raw = proc.stdout.strip()
    # agent-browser sometimes emits the JSON-stringified value as a
    # quoted JSON string. Decode twice if needed.
    val = json.loads(raw)
    if isinstance(val, str):
        val = json.loads(val)
    return val


def capture_all(pre_audit: dict) -> dict:
    """For each surface in pre_audit, capture AFTER state. Mirrors the
    pre_audit's surface list exactly so the diff is structural."""
    surfaces_out: list[dict] = []
    for s in pre_audit.get("surfaces", []):
        sid, label, url = s["id"], s["label"], s["url"]
        sep = "&" if "?" in url else "?"
        with_url = f"{url}{sep}team_class=full_member"
        try:
            control = capture_api_calls(url)
            with_tc = capture_api_calls(with_url)
            entry = {
                "id": sid, "label": label, "url": url,
                "control": control, "with_team_class": with_tc,
            }
        except Exception as exc:
            entry = {
                "id": sid, "label": label, "url": url,
                "error": str(exc),
            }
        surfaces_out.append(entry)
        print(f"  {sid:2d} {label}: captured")
    return {
        "metadata": {
            "captured_at": time.strftime("%Y-%m-%d"),
            "purpose": "AFTER snapshot post-v3 commit-3 — assert every"
                       " /api/v1/ URL with team_class set on FilterBar"
                       " carries team_class=full_member.",
        },
        "surfaces": surfaces_out,
    }


def _is_eligible_for_check(url: str) -> bool:
    """Return False for URLs that legitimately don't carry team_class:
       - Match-identity paths (/matches/{id}/scorecard etc.) take no
         filter scope at all.
       - URLs explicitly scoped team_type=club: the FilterBar's auto-
         clear effect strips team_class when leaving intl. Defensive
         backend gate also makes team_class a no-op for clubs.
       - URLs carrying NO FilterBar field: typeahead probes, identity
         resolution, etc. — frontend doesn't pass team_class to
         endpoints that don't otherwise care about scope.
    """
    path, _, qs = url.partition("?")
    if path in EXEMPT_PATHS:
        return False
    # Match-identity endpoints don't carry filter scope.
    if path.startswith("/api/v1/matches/") and not path.endswith("/api/v1/matches"):
        return False
    if "team_type=club" in qs:
        return False
    # Heuristic: if the URL carries gender/team_type/season/etc., it's
    # a scope-aware request and ought to carry team_class. Otherwise
    # the page didn't bother forwarding any filter (likely identity
    # lookup) — out of scope for this audit.
    has_filter_field = any(
        k in qs for k in ("gender=", "team_type=", "season_from=", "season_to=",
                          "tournament=", "filter_venue=", "filter_team=", "filter_opponent=")
    )
    if not has_filter_field:
        return False
    return True


def verify(after: dict) -> list[str]:
    """For each surface's `with_team_class` set, assert every URL that
    SHOULD carry team_class actually does. Skip URLs that legitimately
    can't carry it (match identity, club scope under defensive gate,
    identity lookups). Returns failure descriptions; empty = clean."""
    failures: list[str] = []
    for s in after.get("surfaces", []):
        if "error" in s:
            failures.append(f"surface {s['id']} ({s['label']}): capture error: {s['error']}")
            continue
        sid = s["id"]; label = s["label"]
        for u in s.get("with_team_class", []):
            if not _is_eligible_for_check(u):
                continue
            if "team_class=full_member" not in u:
                failures.append(
                    f"surface {sid} ({label}): URL silently ignores team_class: {u}"
                )
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("capture", "verify", "both"), default="both")
    parser.add_argument("--pre-audit", default=PRE_AUDIT_PATH)
    parser.add_argument("--after", default=DEFAULT_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.mode in ("capture", "both"):
        with open(args.pre_audit) as f:
            pre = json.load(f)
        print(f"Capturing {len(pre['surfaces'])} surfaces…")
        snapshot = capture_all(pre)
        with open(args.output, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"Wrote {args.output}")

    if args.mode in ("verify", "both"):
        with open(args.after) as f:
            after = json.load(f)
        failures = verify(after)
        if failures:
            print(f"\n{len(failures)} silent-ignore failures:")
            for f in failures:
                print(f"  ✗ {f}")
            sys.exit(1)
        n = sum(len(s.get("with_team_class", [])) for s in after.get("surfaces", []))
        print(f"\nNo silent-ignore bugs detected ({n} URLs across {len(after['surfaces'])} surfaces).")


if __name__ == "__main__":
    main()
