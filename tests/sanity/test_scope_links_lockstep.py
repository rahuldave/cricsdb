"""Lockstep test for `api.scope_links.suggested_splits` against the
canonical fixture in `tests/sanity/scope_splits_fixtures.json`.

The TypeScript implementation in
`frontend/src/components/scopeLinks.ts::suggestedSplits` is required
to produce identical output for the same fixture inputs (enforced by
code review until a Vitest harness exists).

Usage:
  uv run python tests/sanity/test_scope_links_lockstep.py

Exits 0 on all-pass, 1 on any divergence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.scope_links import suggested_splits  # noqa: E402

FIXTURE = ROOT / "tests" / "sanity" / "scope_splits_fixtures.json"


def main() -> int:
    fixtures = json.loads(FIXTURE.read_text())
    failures = 0
    for fx in fixtures:
        name = fx["name"]
        scope = fx["scope"]
        expected = fx["expected"]
        actual = suggested_splits(scope)
        if actual == expected:
            print(f"PASS · {name}")
        else:
            failures += 1
            print(f"FAIL · {name}")
            print(f"  expected: {json.dumps(expected, indent=2)}")
            print(f"  actual:   {json.dumps(actual, indent=2)}")
    print()
    print(f"{len(fixtures) - failures}/{len(fixtures)} pass · {failures} fail")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
