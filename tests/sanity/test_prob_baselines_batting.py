"""Sanity: batting ProbChip cohort baselines on /batters/{id}/distribution.

Hits the running API (default http://localhost:8000) and verifies the
PT1.B cohort baseline plumbing on each chip's ProbRecord:

  1. **Shape**: every milestone ProbRecord (p_failure_10, p_30_plus,
     p_50_plus, p_100_plus, p_50_given_30, p_70_given_50) carries
     `scope_avg`, `delta_pct`, `direction`, `sample_size` keys.

  2. **Direction-tag table**: P(≤10) is lower_better; the remaining
     five chips are higher_better. Matches spec §6.

  3. **delta_pct sign**: when value > scope_avg AND direction is
     higher_better, delta_pct > 0. When value > scope_avg AND
     direction is lower_better, delta_pct > 0 (math: still
     `(value − scope_avg) / scope_avg × 100`; chip-side renders
     polarity via the direction tag). Spec §4.1 + §6.

  4. **Convex combination — simples**: cohort.scope_avg for
     `p_50_plus` matches Σ mix[b] × (fifties + hundreds) / innings at
     bucket b, computed from playerscopestatsposition directly.

  5. **Convex combination — conditionals**: cohort.scope_avg for
     `p_50_given_30` matches Σ mix[b] × P(≥50│≥30)_bucket — the
     per-bucket ratio convex-combined, NOT the ratio of two convex-
     combines (spec §4.3 — `cv(P_50│30) ≠ cv(P_50) / cv(P_30)`).

  6. **Cliff propagation**: tail-batter Bumrah's distribution at IPL
     2024 (small sample, weight on thin buckets) — cohort scope_avg
     fields are null when below_support fires.

  7. **Sample size**: ProbRecord.sample_size equals
     cohort.n_innings_total at the same scope (the cohort tooltip
     denominator).

Spec: internal_docs/spec-prob-baselines.md §9.

Usage:
  uv run python tests/sanity/test_prob_baselines_batting.py
  # API server must be running on http://localhost:8000 (or --host).
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

# spec §6 direction tags. P(=1) is fielding-only so it doesn't appear
# here; p_25_plus is computed but not chip-rendered so it carries no
# direction (skipped by the enrichment).
EXPECTED_DIRECTIONS: dict[str, str] = {
    "p_failure_10":  "lower_better",
    "p_30_plus":     "higher_better",
    "p_50_plus":     "higher_better",
    "p_100_plus":    "higher_better",
    "p_50_given_30": "higher_better",
    "p_70_given_50": "higher_better",
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

    print(f"Sanity: ProbChip cohort baselines — /batters/.../distribution ({args.host})")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    all_passed = True

    # Kohli IPL all-time — the spec §9 acceptance subject.
    KOHLI = "ba607b88"
    BUMRAH = "462411b3"

    resp = get(
        args.host, f"/api/v1/batters/{KOHLI}/distribution",
        tournament="Indian Premier League",
        as_of_date="2025-01-01",
    )
    lifetime_ms = resp["lifetime"]["milestones"]

    # ─── Test 1: shape ──────────────────────────────────────────────
    print("\n  1. ProbRecord shape extension (lifetime milestones):")
    for chip in EXPECTED_DIRECTIONS:
        pr = lifetime_ms.get(chip)
        ok = pr is not None and all(
            k in pr for k in ("scope_avg", "delta_pct", "direction", "sample_size")
        )
        _, line = check(
            f"{chip} carries scope_avg / delta_pct / direction / sample_size",
            ok,
            f"keys={sorted(pr.keys()) if pr else 'missing'}",
        )
        print(line); all_passed &= ok

    # ─── Test 2: direction-tag table ───────────────────────────────
    print("\n  2. Direction tags match spec §6:")
    for chip, expected_dir in EXPECTED_DIRECTIONS.items():
        pr = lifetime_ms.get(chip, {})
        actual_dir = pr.get("direction")
        ok = actual_dir == expected_dir
        _, line = check(
            f"{chip} direction={expected_dir}",
            ok,
            f"actual={actual_dir}",
        )
        print(line); all_passed &= ok

    # ─── Test 3: delta_pct sign ────────────────────────────────────
    print("\n  3. delta_pct = (value − scope_avg) / scope_avg × 100:")
    for chip in EXPECTED_DIRECTIONS:
        pr = lifetime_ms.get(chip, {})
        value = pr.get("value")
        scope_avg = pr.get("scope_avg")
        delta_pct = pr.get("delta_pct")
        if value is None or not scope_avg:
            continue
        expected = round((value - scope_avg) / scope_avg * 100, 1)
        ok = delta_pct == expected
        _, line = check(
            f"{chip} delta_pct matches (value − scope_avg)/scope_avg × 100",
            ok,
            f"expected={expected}, actual={delta_pct}",
        )
        print(line); all_passed &= ok

    # ─── Test 4: convex combination for simple — p_50_plus ─────────
    # SUM(fifties + hundreds) / SUM(innings) AT bucket b, then weighted
    # by the player's mix. Mix is what the endpoint internally computed
    # — derive it from the SQL totals.
    print("\n  4. Cohort p_50_plus matches manual convex combination (Kohli IPL):")
    pos_rows = conn.execute("""
        SELECT pssp.position_bucket AS b,
               SUM(pssp.innings) AS inn
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
         AND pss.person_id = pssp.person_id
        WHERE pss.person_id = ?
          AND pss.tournament = 'Indian Premier League'
        GROUP BY pssp.position_bucket
    """, (KOHLI,)).fetchall()
    kohli_innings_total = sum(r["inn"] for r in pos_rows)
    kohli_mix = {r["b"]: (r["inn"] or 0) / kohli_innings_total for r in pos_rows}

    cohort_rows = conn.execute("""
        SELECT pssp.position_bucket AS b,
               SUM(pssp.innings) AS innings,
               SUM(pssp.fifties) AS fifties,
               SUM(pssp.hundreds) AS hundreds
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
        WHERE pss.tournament = 'Indian Premier League'
        GROUP BY pssp.position_bucket
    """).fetchall()
    cohort_p50 = {
        r["b"]: ((r["fifties"] + r["hundreds"]) / r["innings"]) if r["innings"] else None
        for r in cohort_rows
    }
    expected_p50 = sum(
        kohli_mix.get(b, 0) * cohort_p50[b]
        for b in cohort_p50
        if cohort_p50[b] is not None and kohli_mix.get(b, 0) > 0
    )
    actual_p50 = lifetime_ms["p_50_plus"]["scope_avg"]
    ok = actual_p50 is not None and abs(actual_p50 - round(expected_p50, 4)) < 1e-3
    _, line = check(
        "p_50_plus scope_avg matches manual cv from playerscopestatsposition",
        ok,
        f"expected≈{expected_p50:.4f}, actual={actual_p50}",
    )
    print(line); all_passed &= ok

    # ─── Test 5: convex combination for conditional — p_50_given_30 ──
    # Per-bucket (fifties + hundreds) / (thirties + fifties + hundreds),
    # then convex-combine. NOT the ratio of two convex-combines
    # (spec §4.3).
    print("\n  5. Cohort p_50_given_30 uses bucket-grain ratio (spec §4.3):")
    cond_rows = conn.execute("""
        SELECT pssp.position_bucket AS b,
               SUM(pssp.thirties) AS thirties,
               SUM(pssp.fifties) AS fifties,
               SUM(pssp.hundreds) AS hundreds
        FROM playerscopestatsposition pssp
        JOIN playerscopestats pss
          ON pss.scope_key = pssp.scope_key
        WHERE pss.tournament = 'Indian Premier League'
        GROUP BY pssp.position_bucket
    """).fetchall()
    cohort_p50g30 = {}
    for r in cond_rows:
        denom = r["thirties"] + r["fifties"] + r["hundreds"]
        cohort_p50g30[r["b"]] = (
            (r["fifties"] + r["hundreds"]) / denom if denom else None
        )
    expected_cond = sum(
        kohli_mix.get(b, 0) * cohort_p50g30[b]
        for b in cohort_p50g30
        if cohort_p50g30[b] is not None and kohli_mix.get(b, 0) > 0
    )
    actual_cond = lifetime_ms["p_50_given_30"]["scope_avg"]
    ok = actual_cond is not None and abs(actual_cond - round(expected_cond, 4)) < 1e-3
    _, line = check(
        "p_50_given_30 scope_avg matches bucket-grain cv",
        ok,
        f"expected≈{expected_cond:.4f}, actual={actual_cond}",
    )
    print(line); all_passed &= ok

    # Anti-equality: the cv-of-ratios shortcut should DIFFER from the
    # bucket-grain ratio (otherwise the test is vacuous).
    wrong_cond = (
        lifetime_ms["p_50_plus"]["scope_avg"]
        / lifetime_ms["p_30_plus"]["scope_avg"]
    )
    ok = abs(wrong_cond - actual_cond) > 1e-4
    _, line = check(
        "cv(P_50│30) ≠ cv(P_50) / cv(P_30) — the bucket-grain ratio differs",
        ok,
        f"bucket_grain={actual_cond}, cv_of_ratios={wrong_cond:.4f}",
    )
    print(line); all_passed &= ok

    # ─── Test 6: cliff propagation ─────────────────────────────────
    print("\n  6. Cliff propagation (Bumrah IPL — tail batter, thin sample):")
    bumrah_resp = get(
        args.host, f"/api/v1/batters/{BUMRAH}/distribution",
        tournament="Indian Premier League",
        season_from="2024", season_to="2024",
        as_of_date="2025-01-01",
    )
    bumrah_ms = bumrah_resp["lifetime"]["milestones"]
    # Bumrah's tail-batter cohort at IPL 2024 produces zero scope_avg
    # for p_100_plus (no tail batter has hit 100 — bucket cohort
    # prob is 0). delta_pct must null out when scope_avg = 0 because
    # the division is undefined (matches wrap_metric semantics).
    if bumrah_resp["lifetime"]["n_innings"] > 0:
        p100 = bumrah_ms["p_100_plus"]
        scope_avg = p100["scope_avg"]
        delta_pct = p100["delta_pct"]
        # Either (a) below-cliff → scope_avg is None and delta is None,
        # OR (b) above-cliff with cohort prob == 0 → scope_avg = 0 and
        # delta is None (zero-baseline division blocks the percentage).
        ok = (
            (scope_avg is None and delta_pct is None)
            or (scope_avg == 0 and delta_pct is None)
            or (scope_avg not in (None, 0))
        )
        _, line = check(
            "Bumrah p_100_plus: delta_pct null when scope_avg null or 0",
            ok,
            f"scope_avg={scope_avg}, delta_pct={delta_pct}",
        )
        print(line); all_passed &= ok

    # ─── Test 7: sample_size matches cohort.n_innings_total ───────
    print("\n  7. ProbRecord.sample_size = cohort.n_innings_total:")
    # The endpoint uses an IN-subquery on scope_key (DISTINCT) — match
    # that exact form here. A JOIN-on-scope_key would multiply by the
    # number of player rows in each scope, inflating the count ~180x.
    sql_innings = conn.execute("""
        SELECT SUM(pssp.innings) AS s
        FROM playerscopestatsposition pssp
        WHERE pssp.scope_key IN (
          SELECT scope_key FROM playerscopestats pss
          WHERE pss.tournament = 'Indian Premier League'
        )
    """).fetchone()["s"]
    for chip in EXPECTED_DIRECTIONS:
        ss = lifetime_ms[chip].get("sample_size")
        ok = ss == sql_innings
        _, line = check(
            f"{chip} sample_size == SQL SUM(innings) at IPL scope",
            ok,
            f"sample_size={ss}, sql={sql_innings}",
        )
        print(line); all_passed &= ok

    # ─── Test 8: form window inherits the SAME cohort ─────────────
    # All windows reuse the lifetime cohort (per spec §10 deferral —
    # window-slice cohorts are out of scope this spec).
    print("\n  8. Form windows inherit lifetime cohort scope_avg:")
    for window_key in ("last_10", "last_60d", "last_6mo", "last_1yr"):
        window_doss = resp["form"].get(window_key, {})
        window_ms = window_doss.get("milestones", {})
        if not window_ms:
            continue
        p50_window = window_ms.get("p_50_plus", {})
        p50_lifetime = lifetime_ms["p_50_plus"]
        ok = p50_window.get("scope_avg") == p50_lifetime["scope_avg"]
        _, line = check(
            f"{window_key} p_50_plus scope_avg matches lifetime",
            ok,
            f"window={p50_window.get('scope_avg')}, lifetime={p50_lifetime['scope_avg']}",
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
