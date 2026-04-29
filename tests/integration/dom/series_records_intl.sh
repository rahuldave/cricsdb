#!/bin/bash
# Series Records (intl anchor) — DOM-grounded "Highest team totals"
# table assertions.
#
# Closed window: T20 World Cup Men 2024. The Records tab renders 5+
# DataTables (highest team totals, lowest all-out, biggest wins by
# runs, biggest wins by wkts, largest partnerships, best individual
# batting, best bowling figures). extract_data_table grabs the FIRST
# (highest team totals). Asserts top + last of the 5-row list — the
# spec's "first and last row" rule for tabular surfaces.
#
# Numbers verified by independent SQL — see audit/series_records_intl.sql.

source "$(dirname "$0")/_lib.sh"

navigate "$BASE/series?tournament=ICC+Men%27s+T20+World+Cup&gender=male&team_type=international&season_from=2024&season_to=2024&tab=Records" \
  "Anchor — T20 WC Men 2024 Records (highest team totals)"
# Records tab fans out to 5+ DataTable endpoints; the default 3s soak
# in navigate() isn't enough. Extra sleep here bridges the gap.
sleep 4

JSON=$(extract_data_table 2>/dev/null)

# Columns: 0:Runs  1:Team  2:vs  3:Edition (season)  4:Date
EXPECTED=$(cat <<'PYEXPECT'
{
    "expected_total_rows": 10,    # dossier requests limit=10
    "row_assertions": [
        # Top: India 205 vs Australia (2024)
        (0, [(0, "205"), (1, "India"), (2, "Australia"), (4, "2024-06-24")]),
        # Last: Australia 181 vs India (2024)
        (9, [(0, "181"), (1, "Australia"), (2, "India"), (4, "2024-06-24")]),
    ],
}
PYEXPECT
)

run_data_table_assertions "T20 WC Men 2024 Records (highest team totals)" "$JSON" "$EXPECTED"; record_result $?

print_summary
