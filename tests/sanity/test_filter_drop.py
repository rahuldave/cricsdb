"""Sanity: FilterBarParams.build(drop=...) masks named axes correctly.

Pure unit test on the SQL clause / params output of FilterBarParams —
no DB needed.

Verifies:
  1. For each recognised axis name, drop={axis} produces output
     identical to constructing FilterBarParams without that axis set.
  2. Multiple axes can be dropped simultaneously.
  3. `season` is a single name masking both season_from and season_to.
  4. Unknown axis names raise ValueError.

Spec: internal_docs/spec-player-compare-average.md §4.6.

Usage:
  uv run python tests/sanity/test_filter_drop.py
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from api.filters import FilterBarParams, _DROP_AXES


# Sample value per axis — chosen so the clause is non-trivial. The
# value doesn't have to be valid against the DB; we only inspect the
# SQL/params output.
ALL_SET = dict(
    gender="men",
    team_type="club",
    tournament="Indian Premier League",
    season_from="2015",
    season_to="2020",
    filter_team="Mumbai Indians",
    filter_opponent="Chennai Super Kings",
    filter_venue="Wankhede Stadium",
    team_class="primary_club",
    series_type="club",
)

# Axis → constructor kwargs that the axis controls. `season` is the
# odd one — single drop name maps to both season_from + season_to.
AXIS_TO_KWARGS = {
    "gender":          ["gender"],
    "team_type":       ["team_type"],
    "tournament":      ["tournament"],
    "season":          ["season_from", "season_to"],
    "filter_venue":    ["filter_venue"],
    "filter_team":     ["filter_team"],
    "filter_opponent": ["filter_opponent"],
    "team_class":      ["team_class"],
    "series_type":     ["series_type"],
}


def _build_with_all() -> FilterBarParams:
    return FilterBarParams(**ALL_SET)


def _build_without(*axes: str) -> FilterBarParams:
    kwargs = dict(ALL_SET)
    for axis in axes:
        for k in AXIS_TO_KWARGS[axis]:
            kwargs[k] = None
    return FilterBarParams(**kwargs)


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def main() -> int:
    print("Sanity: FilterBarParams.build(drop=...) ...")
    all_passed = True

    # 1. Per-axis: drop={axis} equivalent to constructing without it.
    print("\n  1. Per-axis drop equivalence:")
    for axis in sorted(_DROP_AXES):
        dropped_where, dropped_params = _build_with_all().build(drop={axis})
        omitted_where, omitted_params = _build_without(axis).build()
        ok = dropped_where == omitted_where and dropped_params == omitted_params
        passed, line = check(
            f"drop={{{axis!r}}} == omit({axis})",
            ok,
            detail=(
                f"\n         dropped where: {dropped_where}"
                f"\n         omitted where: {omitted_where}"
                f"\n         dropped params: {dropped_params}"
                f"\n         omitted params: {omitted_params}"
            ),
        )
        print(line)
        all_passed &= passed

    # 2. Multi-axis: drop two at once equivalent to omitting both.
    print("\n  2. Multi-axis drop equivalence:")
    multi = {"filter_team", "filter_opponent"}
    dropped_where, dropped_params = _build_with_all().build(drop=multi)
    omitted_where, omitted_params = _build_without(*multi).build()
    ok = dropped_where == omitted_where and dropped_params == omitted_params
    passed, line = check(
        f"drop={multi} == omit(filter_team, filter_opponent)",
        ok,
        detail=(
            f"\n         dropped where: {dropped_where}"
            f"\n         omitted where: {omitted_where}"
        ),
    )
    print(line)
    all_passed &= passed

    # 3. `season` masks both season_from and season_to.
    print("\n  3. `season` masks both season_from and season_to:")
    dropped_where, dropped_params = _build_with_all().build(drop={"season"})
    ok = "season_from" not in dropped_params and "season_to" not in dropped_params
    passed, line = check(
        "drop={'season'} removes both season_from and season_to",
        ok,
        detail=f"params: {dropped_params}",
    )
    print(line)
    all_passed &= passed

    # 4. Unknown axis raises ValueError.
    print("\n  4. Unknown axis name raises ValueError:")
    raised = False
    msg = ""
    try:
        _build_with_all().build(drop={"not_a_real_axis"})
    except ValueError as e:
        raised = True
        msg = str(e)
    ok = raised and "not_a_real_axis" in msg
    passed, line = check(
        "drop={'not_a_real_axis'} → ValueError",
        ok,
        detail=f"raised={raised}, msg={msg!r}",
    )
    print(line)
    all_passed &= passed

    # 5. drop=None and drop=set() are no-ops (full clause output).
    print("\n  5. drop=None and drop=set() are no-ops:")
    baseline_where, baseline_params = _build_with_all().build()
    for variant in (None, set()):
        dwhere, dparams = _build_with_all().build(drop=variant)
        ok = dwhere == baseline_where and dparams == baseline_params
        passed, line = check(
            f"drop={variant!r} preserves all clauses",
            ok,
            detail=f"\n         baseline: {baseline_where}\n         got:      {dwhere}",
        )
        print(line)
        all_passed &= passed

    print()
    if all_passed:
        print("ALL PASS")
        return 0
    else:
        print("SOME FAILURES — see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
