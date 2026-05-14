"""Pure-unit invariants for populate helpers.

Currently covers `_missing_cols(have, want)` — the column-diff core
of `_add_columns_if_missing`. Extracted in commit TBD so that:

  - the DB-touching ALTER TABLE wrapper stays a thin shell;
  - the diff logic (which columns are missing) is unit-testable
    without a sqlite handle.

Reference: scripts/populate_bucket_baseline.py Phase D part 1.

Usage:
  uv run python tests/sanity/test_populate_helpers.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.populate_bucket_baseline import _missing_cols


def main():
    cases = [
        # (description, have, want, expected_missing)
        ("all-missing — want exists in want, none in have",
         set(),
         {"a": "INTEGER DEFAULT 0", "b": "TEXT"},
         {"a": "INTEGER DEFAULT 0", "b": "TEXT"}),
        ("all-present — every want already in have",
         {"a", "b", "c"},
         {"a": "INTEGER", "b": "TEXT"},
         {}),
        ("partial — some present, some missing, preserves decls of missing",
         {"a", "x"},
         {"a": "INTEGER", "b": "TEXT", "c": "REAL"},
         {"b": "TEXT", "c": "REAL"}),
        ("empty want → empty result",
         {"a", "b"},
         {},
         {}),
        ("empty have → returns entire want",
         set(),
         {"x": "INTEGER"},
         {"x": "INTEGER"}),
        ("decls aren't compared, only names",
         {"a"},
         {"a": "DIFFERENT_DECL_IGNORED"},
         {}),
        ("name match case-sensitive — 'A' in have does NOT match 'a' in want",
         {"A"},
         {"a": "INTEGER"},
         {"a": "INTEGER"}),
    ]

    failures = []
    for desc, have, want, expected in cases:
        got = _missing_cols(have, want)
        if got != expected:
            failures.append(f"FAIL: {desc}\n  expected={expected}\n  got     ={got}")
        else:
            print(f"PASS: {desc}")

    print()
    if failures:
        for f in failures:
            print(f)
        print(f"FAILED: {len(failures)}/{len(cases)}")
        sys.exit(1)
    print("ALL PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
