"""DB-grounded numeric assertions for the v3 team_class FilterBar
migration. Pinned to closed historical windows so expected values
stay stable across DB rebuilds:
  - Men's T20I 2024-2025 / 2024-2026 (intl, full calendar window)
  - Women's T20I 2024-2025 (intl, FM symmetry sanity)
  - IPL 2025 (club, completed — defensive gate proof)

Two axes per anchor:
  AXIS A — match-count anchors: SQL count vs API count
  AXIS B — top-N batter/bowler lists: SQL ordering vs API leaders
  AXIS C — chip baselines + run rate: SQL value vs API field value

For the FM-mode anchors, the FilterBar's `team_class=full_member`
must narrow team-side data correctly. For club anchors, the
defensive backend gate must make team_class a no-op.

Ground truth derived by a DB-only subagent (no api/ source reads) on
2026-04-28 — see internal_docs/team-class-anchor-numbers.md.

Usage:
  uv run python tests/sanity/test_team_class_baseline_numbers.py
  uv run python tests/sanity/test_team_class_baseline_numbers.py --db /tmp/cricket-prod-test.db

Set CRICSDB_TEST_BASE_URL to point at a different uvicorn instance
(default http://localhost:8000).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# TODO(commit-1): import from filters AFTER team_class moves to FilterBarParams.
# Until commit 1 lands, AuxParams still has team_class — these imports work either way.
from deebase import Database
from api import dependencies as deps
from api.filters import FilterBarParams, AuxParams


EPS = 0.15  # decimal-rounding tolerance


def near(a, b) -> bool:
    if a is None and b is None: return True
    if a is None or b is None:  return False
    return abs(float(a) - float(b)) <= EPS


def make_filters(**kwargs) -> FilterBarParams:
    """After commit 1, this signature gains team_class.
    Until then, callers that pass team_class will need make_aux."""
    keys = ("gender", "team_type", "tournament", "season_from", "season_to",
            "filter_team", "filter_opponent", "filter_venue")
    # TODO(commit-1): add 'team_class' to keys after field move.
    return FilterBarParams(**{k: kwargs.get(k) for k in keys})


# ─── Closed-window scope definitions ──────────────────────────────────
#
# CRITICAL: scope window is season IN ('2024','2024/25','2025') —
# NOT '2025/26' (Phase B subagent confirmed empirically; spec §7
# updated 2026-04-28). Using FilterBarParams' season_from/to as
# string bounds works because '2025' < '2025/26' lexically.

INTL_24_25_M = dict(gender="male", team_type="international",
                    season_from="2024", season_to="2025")
INTL_24_25_W = dict(gender="female", team_type="international",
                    season_from="2024", season_to="2025")
IPL_2025 = dict(gender="male", team_type="club",
                tournament="Indian Premier League",
                season_from="2025", season_to="2025")


# ─── Ground truth (pinned 2026-04-28) ─────────────────────────────────
# Source: internal_docs/team-class-anchor-numbers.md (28 anchors)
# DB-direct, no api/ source read by the deriving subagent.

GROUND_TRUTH: dict[str, Any] = {
    # A — Intl narrowing (men_intl 2024-25, season IN ('2024','2024/25','2025'))
    "A1_total_intl_unbounded": 870,
    "A2_total_intl_fm": 140,
    "A3_aus_unbounded": 22,
    "A4_aus_fm": 16,
    "A5_ind_unbounded": 34,
    "A6_ind_fm": 31,
    "A7_scotland_unbounded": 17,
    "A8_scotland_fm": 0,
    "A13_t20wc_men_unbounded": 44,    # canonical event_name only; qualifiers excluded
    "A14_t20wc_men_fm": 16,

    # B — Rivalries + venue
    "A15a_ind_aus_unbounded": 1,      # 2024 T20 WC Super-8 only meeting
    "A15b_ind_aus_fm": 1,             # both FM, no-op
    "A16a_ind_scotland_unbounded": 0, # didn't play in scope
    "A16b_ind_scotland_fm": 0,        # FM ≤ unbounded; both 0 satisfies
    "A17_wankhede_unbounded": 1,      # single Ind-Eng match 2025-02-02
    "A18_wankhede_fm": 1,             # both FM

    # C — Chip baselines (run rates, 4dp precision per anchor file)
    "C1_aus_rr_unbounded": 9.9150,
    "C2_aus_rr_fm": 9.8232,
    "C3_league_rr_unbounded": 7.5172,
    "C4_league_rr_fm": 8.4974,

    # D — Women's intl symmetry (women_intl 2024-25)
    "D1_women_intl_unbounded": 596,
    "D2_women_intl_fm": 97,

    # B-prime — Club no-op (RCB / SRH / All IPL 2025)
    "Bp1_rcb_ipl_2025": 15,
    # CRITICAL: B2 = 0 if FM clause is naively applied to a club URL.
    # Sanity test must assert API returns 15 (== Bp1), NOT 0 — proving
    # the defensive backend gate fires and makes team_class a no-op
    # when team_type='club'.
    "Bp2_rcb_ipl_2025_fm_via_API_must_equal_Bp1": 15,
    "Bp3_srh_ipl_2025": 14,
    "Bp4_all_ipl_2025": 74,

    # A9 — Top-10 batters by total_runs, men_intl 2024-25 unbounded
    # Note: 9/10 are associate-team batters — exactly the leaderboard
    # distortion the FM filter is designed to remove.
    "A9_top10_batters_unbounded": [
        ("6a97c7a4", "Karanbir Singh", 1420),
        ("6f02fe2a", "Waseem Muhammad", 1173),
        ("df1f2f29", "Fiaz Ahmed", 1060),
        ("33b67317", "Bilal Zalmai", 997),
        ("552b228c", "Anshuman Rath", 990),
        ("06cad4f0", "A Sharafu", 977),
        ("074acfb4", "Asif Khan", 975),
        ("8ee36b18", "P Nissanka", 974),
        ("987187b9", "Zeeshan Ali", 914),
        ("e3eb9e46", "Nizakat Khan", 910),
    ],
    # A10 — Top-10 batters, FM-only — completely different leaderboard
    "A10_top10_batters_fm": [
        ("8ee36b18", "P Nissanka", 906),
        ("99b75528", "JC Buttler", 802),
        ("f29185a1", "Abhishek Sharma", 781),
        ("3d284ca3", "PD Salt", 765),
        ("b0482a1d", "Tilak Varma", 597),
        ("b8cc58c9", "RR Hendricks", 594),
        ("1fc6ef83", "SD Hope", 594),
        ("33609a8c", "Saim Ayub", 574),
        ("9e52a414", "Towhid Hridoy", 567),
        ("a4cc73aa", "SV Samson", 563),
    ],
    # A11 — Top-10 bowlers by wickets, unbounded (same associate-heavy pattern)
    "A11_top10_bowlers_unbounded": [
        ("e741ed8f", "Rizwan Butt", 68),
        ("596982e6", "Ali Dawood", 59),
        ("d3851cd8", "Ehsan Khan", 47),
        ("c9d05f1a", "Yasim Murtaza", 46),
        ("5935d694", "Rishad Hossain", 45),
        ("3c8faed4", "F Banunaek", 44),
        ("ef18b66e", "Taskin Ahmed", 43),
        ("84dc72db", "Junaid Siddique", 43),
        ("a9a18e3e", "Imran Anwar", 42),
        ("a62f55ba", "DJ Hawoe", 42),
    ],
    # A12 — Top-10 bowlers, FM-only
    "A12_top10_bowlers_fm": [
        ("5b7ab5a9", "CV Varun", 37),
        ("45a7e761", "Shaheen Shah Afridi", 37),
        ("24bb1c2f", "Haris Rauf", 34),
        ("5935d694", "Rishad Hossain", 33),
        ("2cec2a92", "Abbas Afridi", 33),
        ("ef18b66e", "Taskin Ahmed", 32),
        ("a97c8ec2", "PWH de Silva", 32),
        ("244048f6", "Arshdeep Singh", 31),
        ("dadbdb68", "JA Duffy", 28),
        ("249d60c9", "AU Rashid", 28),
    ],
}


# ─── Test runner ──────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cricket.db",
    ))
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: {args.db} not found", file=sys.stderr)
        sys.exit(1)

    deps.init_db(args.db)
    failures: list[str] = []

    # ── AXIS A — match counts ──────────────────────────────────────
    # TODO(commit-5): for each anchor, hit /api/v1/teams/{team}/summary
    # (or /matches?... or /scope/averages/* — pick the endpoint each
    # anchor exercises) and assert response count == GROUND_TRUTH[key].
    print("=== AXIS A: match counts ===")
    # TODO: assert A3 (Australia unbounded — should be 22)
    # TODO: assert A4 (Australia FM — should be 16; requires team_class on FilterBar)
    # TODO: assert A5/A6, A7/A8, A13/A14, A15, A16

    # ── AXIS B — top-N lists ───────────────────────────────────────
    # TODO(commit-5): for each leader-list anchor, hit
    # /api/v1/batters/leaders?... and assert top-10 ordering matches
    # GROUND_TRUTH list (by person_id, in order).
    print("=== AXIS B: top-N batter/bowler lists ===")
    # TODO: A9 unbounded vs A10 FM (should differ)
    # TODO: A11/A12 same

    # ── AXIS C — chip baselines + run rates ────────────────────────
    # TODO(commit-5): for each scope, exercise
    # /api/v1/teams/Australia/batting/summary (team data) AND
    # /api/v1/scope/averages/batting/summary (avg col) and assert
    # numeric agreement against GROUND_TRUTH.
    print("=== AXIS C: chip baselines (run rates) ===")
    # TODO: C1 (Aus RR unbounded), C2 (Aus RR FM)
    # TODO: C3 (league RR unbounded), C4 (league RR FM)

    # ── AXIS D — women's symmetry ──────────────────────────────────
    print("=== AXIS D: women's intl symmetry ===")
    # TODO: D1 (women_intl unbounded), D2 (women_intl FM)

    # ── B-prime — Club no-op ───────────────────────────────────────
    # CRITICAL: with team_class=full_member on a club URL, the response
    # MUST equal the response without team_class. This proves the
    # defensive backend gate is firing.
    print("=== B-prime: club no-op (defensive gate) ===")
    # TODO: Bp1 vs Bp2 (RCB IPL 2025 with/without team_class — MUST equal)
    # TODO: Bp3 (SRH IPL 2025 control)

    # ── Summary ────────────────────────────────────────────────────
    if failures:
        print(f"\n{len(failures)} FAILURES")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
