#!/bin/bash
# v3 team_class FilterBar — regression URL generator.
#
# Mechanically generates the ~125 NEW URLs required by spec §8.2.
# Each NEW URL is derived from an existing REG URL by appending
# &team_class=full_member to its query string.
#
# Filter rule: only URLs that already include team_type=international
# (or team_type=female intl) get FM siblings. URLs with team_type=club
# would produce zero-result siblings (defensive backend gate makes
# them no-ops, so REG vs NEW would be identical → no regression value).
#
# Output: a "team_class.txt" file per affected suite, with NEW-tagged
# URLs ready to append to that suite's urls.txt.
#
# Usage:
#   bash tests/regression/team_class_url_gen.sh
#
# Run before commit 4 of v3 rollout. Review the output, append to
# each suite's urls.txt, commit.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SUITES=(teams scope-averages batting bowling fielding players head_to_head matches venues filterbar_refs)

for suite in "${SUITES[@]}"; do
  src="$REPO_ROOT/tests/regression/$suite/urls.txt"
  out="$REPO_ROOT/tests/regression/$suite/team_class.txt"
  [ -f "$src" ] || { echo "SKIP $suite (no urls.txt)"; continue; }

  : > "$out"
  echo "# v3 team_class FilterBar — generated NEW URLs (one-shot)" >> "$out"
  echo "# Source: each row mirrors a REG row in urls.txt with &team_class=full_member appended." >> "$out"
  echo "# Filter: only intl-context REG entries qualify." >> "$out"
  echo >> "$out"

  count=0
  while IFS= read -r line; do
    case "$line" in \#*|"") continue ;; esac
    kind=$(echo "$line" | awk '{print $1}')
    label=$(echo "$line" | awk '{print $2}')
    url=$(echo "$line" | awk '{print $3}')

    [ "$kind" = "REG" ] || continue
    [ -n "$url" ] || continue
    case "$url" in
      *team_type=international*) ;;  # qualifies
      *) continue ;;  # skip non-intl
    esac

    # Build the NEW URL: append team_class param.
    case "$url" in
      *\?*) new_url="${url}&team_class=full_member" ;;
      *)    new_url="${url}?team_class=full_member" ;;
    esac

    new_label="${label}_fm"
    printf "NEW %-50s %s\n" "$new_label" "$new_url" >> "$out"
    count=$((count + 1))
  done < "$src"

  echo "  $suite: $count NEW URLs → $out"
done

echo
echo "Generated team_class.txt per suite. Review, then concatenate into each urls.txt:"
echo "  for s in ${SUITES[*]}; do cat tests/regression/\$s/team_class.txt >> tests/regression/\$s/urls.txt; done"
