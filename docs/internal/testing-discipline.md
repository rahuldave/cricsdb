# Testing discipline

How integration / sanity / regression tests are written in this codebase. CLAUDE.md links here.

## Contents

1. [The three-layer chain](#the-three-layer-chain)
2. [Integration tests must self-anchor against SQL](#integration-tests-must-self-anchor-against-sql)
3. [Tests must cover EVERY call site of a shared abstraction](#tests-must-cover-every-call-site-of-a-shared-abstraction)
4. [Sparkline / per-item chart bar count must match SQL](#sparkline--per-item-chart-bar-count-must-match-sql)
5. [Integration tests anchor against `/summary`'s scope_avg, not re-derived SQL](#integration-tests-anchor-against-summarys-scope_avg-not-re-derived-sql)

---

## The three-layer chain

- **Sanity** (`tests/sanity/test_*.py`): SQL ↔ API.
- **Integration** (`tests/integration/*.sh`): DOM ↔ SQL via the running app (transitively SQL ↔ API ↔ DOM).
- **Regression** (`tests/regression/<feature>/urls.txt`): no-drift across refactors at the API layer.

## Integration tests must self-anchor against SQL

Numeric expected values in `tests/integration/<feature>.sh` (Matches counts, Runs, RR, leaderboard sizes, baseline-avg numerator/denominator) must be **derived from `cricket.db` at test runtime**, not hardcoded.

```bash
expected=$(sqlite3 "$DB" "SELECT COUNT(*) FROM match WHERE …")
actual=$(ab_eval "document.body.textContent.match(/Matches(\\d+)/)?.[1]")
assert_eq "label" "$expected" "$actual"
```

Hardcoding `assert_eq "label" "548" "$actual"` means a bug that drifts the API to 548-by-coincidence silently passes. The DB is source of truth; SQL-derived expecteds self-correct against DB updates AND surface drift the moment either API or DOM departs.

Reference implementation: `tests/integration/team_class_club_per_page_refetch.sh`. `sql()` helper wraps `sqlite3 $DB`; every `assert_eq` reads its expected from `$(sql ...)`. IN-list constants (FM frozenset, PRIMARY/SECONDARY club leagues, ICC events) stay inline at the top of the script, mirroring the Python source — divergence surfaces immediately.

## Tests must cover EVERY call site of a shared abstraction

When you fix a bug in a shared helper (`useFilterDeps`, `FilterParams`, a SQL generator), the integration test must exercise every page that consumes it — not just the page where the bug surfaced. A test hitting 1 of 10 call sites passes through the next refactor that re-breaks 9 of them.

Pattern: `grep -rn 'helperName' src/` enumerates the sites; write one assertion per site. Reference: `tests/integration/inning_per_page_refetch.sh` — 10 mount sites × click-after-mount × 4 toggle states × SQL-anchored DOM assertions. User flagged 2026-05-01 after commit `be4d755` shipped with 83 integration passes while silently breaking the inning toggle on every InningToggle mount site.

## Sparkline / per-item chart bar count must match SQL

Any chart rendering one bar per (innings / spell / match / event) MUST have an integration assertion that the rendered bar count equals the SQL-anchored item count. The "missing matches" bug on 2026-05-06 was 15 wicketless spells rendering at `height=0` — invisible AND unclickable; SQL said 45, the user counted ~30.

```bash
sql_n=$(sql "$INNS_SQL")
dom_n=$(ab_eval "document.querySelectorAll('.wisden-dist-sparkline rect[opacity]').length")
assert_eq "Bar count == SQL n_innings" "$sql_n" "$dom_n"

zero_h=$(ab_eval "Array.from(...).filter(r => parseFloat(r.getAttribute('height')) <= 0).length")
assert_eq "No height=0 bars" "0" "$zero_h"
```

Reference: `tests/integration/bowler_distribution.sh` Test 1, `batter_distribution.sh` Test 8.

## Integration tests anchor against `/summary`'s scope_avg, not re-derived SQL

When testing a UI element that displays a value the API computes via the dual-query envelope (the `team=None` league-side fetch combined with team-side — every `MetricEnvelope.scope_avg`), pull the expected value from `/summary` via `curl` rather than re-deriving it in SQL. Re-deriving league-avg in SQL inside the integration test is brittle (200+ lines of denominator logic) AND tests the wrong layer; `/summary`'s sanity tests cover SQL↔API, the integration test covers API↔DOM plumbing.

```bash
api_summary=$(curl -s "$API_BASE/api/v1/teams/$TEAM_URL/batting/summary?$SCOPE_URL")
expected_scope_avg=$(echo "$api_summary" | python3 -c "
import json, sys
print(f'{json.load(sys.stdin)[\"total_runs\"][\"scope_avg\"]:.1f}')")
dom_legend=$(ab_eval "...legend element innerText...")
assert_contains "legend matches API scope_avg" "league avg $expected_scope_avg" "$dom_legend"
```

Reference: `tests/integration/team_batting_distribution.sh` Test 11 / 12.
