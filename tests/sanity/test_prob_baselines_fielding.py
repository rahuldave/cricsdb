"""Sanity: fielding catches ProbChip cohort baselines.

Hits /fielders/{id}/distribution on the running API and verifies the
PT4.B cohort baseline plumbing on the catches-block ProbRecords:

  1. Shape — every chip (p_zero / p_one / p_geq_2) carries scope_avg /
     delta_pct / direction / sample_size keys.

  2. Direction tags — P(=0) lower_better; P(=1) None (descriptive);
     P(≥2) higher_better. Spec §6.

  3. delta_pct — populated for p_zero + p_geq_2 (directional); null
     for p_one (descriptive — no orientation).

  4. Cohort scope_avg SQL-anchored — equals SUM(matches_with_k) /
     SUM(matches_with_0 + matches_with_1 + matches_with_ge2) across
     the keeper-binary cohort.

  5. sample_size = cohort.n_matches_total (SUM of the three bucket
     totals at the cohort scope).

  6. Form windows inherit the lifetime cohort (window-slice cohorts
     deferred — spec §10).

Subject: V Kohli IPL all-time (outfielder cohort, is_keeper=0).

Spec: internal_docs/spec-prob-baselines.md §3.3 + §6 + §9.

Usage:
  uv run python tests/sanity/test_prob_baselines_fielding.py
  # API server must be running on http://localhost:8000.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "cricket.db")
DEFAULT_HOST = "http://localhost:8000"

EXPECTED_DIRECTIONS: dict[str, str | None] = {
    "p_zero":  "lower_better",
    "p_one":   None,
    "p_geq_2": "higher_better",
}


def check(label: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not ok:
        line += f"\n         {detail}"
    return ok, line


def get(host: str, path: str, **params) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{host}{path}?{qs}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    print(f"Sanity: fielding catches ProbChip cohort baselines ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    KOHLI = "ba607b88"

    resp = get(
        args.host, f"/api/v1/fielders/{KOHLI}/distribution",
        gender="male", team_type="club",
        tournament="Indian Premier League",
        as_of_date="2025-01-01",
    )
    lifetime_ms = resp["lifetime"]["catches"]["milestones"]

    # ─── Test 1: shape ──────────────────────────────────────────────
    print("\n  1. ProbRecord shape extension:")
    for chip in EXPECTED_DIRECTIONS:
        pr = lifetime_ms.get(chip)
        ok = pr is not None and all(
            k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
        )
        _, line = check(f"{chip} carries cohort baseline fields", ok)
        print(line); all_passed &= ok

    # ─── Test 2: direction tags ────────────────────────────────────
    print("\n  2. Direction tags match spec §6:")
    for chip, expected_dir in EXPECTED_DIRECTIONS.items():
        pr = lifetime_ms.get(chip, {})
        ok = pr.get("direction") == expected_dir
        _, line = check(
            f"{chip} direction={expected_dir}",
            ok,
            f"actual={pr.get('direction')}",
        )
        print(line); all_passed &= ok

    # ─── Test 3: delta_pct — p_one is null (descriptive) ───────────
    print("\n  3. delta_pct null for p_one (descriptive):")
    p_one_delta = lifetime_ms["p_one"].get("delta_pct")
    ok = p_one_delta is None
    _, line = check("p_one delta_pct is None (no orientation)",
                    ok, f"actual={p_one_delta}")
    print(line); all_passed &= ok

    for chip in ("p_zero", "p_geq_2"):
        pr = lifetime_ms[chip]
        value = pr["value"]; scope_avg = pr["scope_avg"]; delta_pct = pr["delta_pct"]
        if value is None or not scope_avg:
            continue
        expected = round((value - scope_avg) / scope_avg * 100, 1)
        ok = delta_pct == expected
        _, line = check(f"{chip} delta_pct matches arithmetic", ok,
                        f"expected={expected}, actual={delta_pct}")
        print(line); all_passed &= ok

    # ─── Test 4: scope_avg SQL-anchored ────────────────────────────
    # Kohli's is_keeper=0 (outfielder). Cohort partition: pss.matches_
    # as_keeper = 0 at IPL scope. Sum the three bucket columns,
    # compute prob = bucket / total.
    print("\n  4. Cohort scope_avg SQL-anchored:")
    cohort_row = conn.execute("""
        SELECT SUM(pssfcd.matches_with_0)   AS m0,
               SUM(pssfcd.matches_with_1)   AS m1,
               SUM(pssfcd.matches_with_ge2) AS mge2
        FROM playerscopestatsfieldingcatchdist pssfcd
        JOIN playerscopestats pss
          ON pss.person_id = pssfcd.person_id
         AND pss.scope_key = pssfcd.scope_key
        WHERE pss.matches_as_keeper = 0
          AND pss.tournament = 'Indian Premier League'
    """).fetchone()
    m0, m1, mge2 = cohort_row["m0"], cohort_row["m1"], cohort_row["mge2"]
    total = m0 + m1 + mge2
    expected_probs = {
        "p_zero":  round(m0 / total, 4),
        "p_one":   round(m1 / total, 4),
        "p_geq_2": round(mge2 / total, 4),
    }
    for chip in EXPECTED_DIRECTIONS:
        actual = lifetime_ms[chip]["scope_avg"]
        expected = expected_probs[chip]
        ok = actual == expected
        _, line = check(
            f"{chip} scope_avg matches SUM(bucket) / SUM(total) from cohort",
            ok,
            f"expected={expected}, actual={actual}",
        )
        print(line); all_passed &= ok

    # ─── Test 5: sample_size == cohort matches_total ──────────────
    print("\n  5. ProbRecord.sample_size = cohort.n_matches_total:")
    for chip in EXPECTED_DIRECTIONS:
        ss = lifetime_ms[chip].get("sample_size")
        ok = ss == total
        _, line = check(f"{chip} sample_size == SQL total",
                        ok, f"sample_size={ss}, total={total}")
        print(line); all_passed &= ok

    # ─── Test 6: form windows inherit lifetime cohort ──────────────
    print("\n  6. Form windows inherit lifetime cohort scope_avg:")
    for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        window_doss = resp["form"].get(window_key, {})
        window_ms = window_doss.get("catches", {}).get("milestones", {})
        if not window_ms:
            continue
        ws = window_ms.get("p_zero", {}).get("scope_avg")
        ls = lifetime_ms["p_zero"]["scope_avg"]
        ok = ws == ls
        _, line = check(f"{window_key} p_zero scope_avg matches lifetime",
                        ok, f"window={ws}, lifetime={ls}")
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
