#!/bin/bash
# Series Records (club anchor) — DOM-grounded "Highest team totals".
# Closed window: IPL 2025.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=Indian+Premier+League&gender=male&team_type=club&season_from=2025&season_to=2025&tab=Records" \
  "Anchor — IPL 2025 Records (highest team totals)"
sleep 4   # Records tab fans out to 5+ DataTables.

JSON=$(extract_data_table 2>/dev/null)

EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,
    "row_assertions": [
        # Top: SRH 286 vs RR (the famous 286 — biggest IPL total ever)
        (0, [(0, "286"), (1, "Sunrisers Hyderabad"), (2, "Rajasthan Royals"), (4, "2025-03-23")]),
        # Last: KKR 234 vs LSG
        (9, [(0, "234"), (1, "Kolkata Knight Riders"), (2, "Lucknow Super Giants"), (4, "2025-04-08")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "IPL 2025 Records (highest team totals)" "$JSON" "$EXPECTED"; record_result $?

print_summary
