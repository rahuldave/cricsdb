"""Sanity: api.innings_positions.derive_positions correctness.

Pure unit test on synthetic delivery lists — no DB needed.

Spec: internal_docs/spec-player-compare-average.md §4.5 (shared helper
contract). The function was extracted verbatim from
scripts/populate_player_scope_stats.py::_derive_positions in Phase 1.5
of the player-baselines rollout; these tests lock in the position
convention so the three downstream populate scripts (parent table +
batting/fielding child tables) can rely on identical semantics.

Usage:
  uv run python tests/sanity/test_innings_positions.py
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from api.innings_positions import derive_positions


def _d(batter: str | None, non_striker: str | None) -> dict:
    """Minimal delivery dict — only the two fields derive_positions reads."""
    return {"batter_id": batter, "non_striker_id": non_striker}


def check(label: str, expected, actual) -> tuple[bool, str]:
    ok = expected == actual
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if not ok:
        line += f"\n         expected: {expected}\n         actual:   {actual}"
    return ok, line


def main() -> int:
    print("Sanity: api.innings_positions.derive_positions ...")
    all_passed = True

    # 1. Empty deliveries → empty dict.
    ok, line = check("empty list → {}", {}, derive_positions([]))
    print(line); all_passed &= ok

    # 2. Single delivery → striker=1, non_striker=2.
    ok, line = check(
        "single delivery — striker=1, non_striker=2",
        {"A": 1, "B": 2},
        derive_positions([_d("A", "B")]),
    )
    print(line); all_passed &= ok

    # 3. New batter mid-innings gets next position (3).
    ok, line = check(
        "third batter enters → position 3",
        {"A": 1, "B": 2, "C": 3},
        derive_positions([_d("A", "B"), _d("C", "B")]),
    )
    print(line); all_passed &= ok

    # 4. Both new in single delivery — non_striker side first? Actually
    #    the function iterates (batter, non_striker) so batter wins
    #    when both are new on the same delivery. Lock the order.
    ok, line = check(
        "same delivery introduces two — batter gets earlier position",
        {"X": 1, "Y": 2},
        derive_positions([_d("X", "Y")]),
    )
    print(line); all_passed &= ok

    # 5. NULL person_id is skipped (does not consume a position slot).
    ok, line = check(
        "NULL batter_id is skipped, non_striker still gets 1",
        {"B": 1},
        derive_positions([_d(None, "B")]),
    )
    print(line); all_passed &= ok

    # 6. Re-encountering a known person_id does NOT bump position.
    ok, line = check(
        "known person reappears — position unchanged",
        {"A": 1, "B": 2, "C": 3},
        derive_positions([
            _d("A", "B"),       # A=1, B=2
            _d("C", "B"),       # C=3 (B re-seen, no change)
            _d("A", "C"),       # both already known
        ]),
    )
    print(line); all_passed &= ok

    # 7. 11+ distinct batters — extras go into bucket 11.
    twelve = [_d(f"P{i}", f"P{i+1}") for i in range(0, 12)]
    # P0..P11 = 12 distinct batters. P11 lands in bucket 11.
    pos = derive_positions(twelve)
    p0_to_p10_ok = all(pos[f"P{i}"] == i + 1 for i in range(11))
    p11_ok = pos["P11"] == 11
    ok, line = check(
        "12 distinct batters — first 11 take 1..11, 12th lands in bucket 11",
        True,
        p0_to_p10_ok and p11_ok,
    )
    print(line); all_passed &= ok

    # 8. Realistic innings sketch — 6 batters, 4 wickets, positions 1..6.
    realistic = [
        _d("Op1", "Op2"),       # 1, 2
        _d("Op1", "Op2"),
        _d("Op2", "B3"),        # 3
        _d("B3",  "Op2"),
        _d("B3",  "B4"),        # 4
        _d("B4",  "B5"),        # 5
        _d("B5",  "B4"),
        _d("B6",  "B5"),        # 6
    ]
    ok, line = check(
        "realistic 6-batter innings — positions 1..6 by order of appearance",
        {"Op1": 1, "Op2": 2, "B3": 3, "B4": 4, "B5": 5, "B6": 6},
        derive_positions(realistic),
    )
    print(line); all_passed &= ok

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
