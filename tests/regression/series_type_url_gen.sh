#!/bin/bash
# series_type FilterBar — regression URL generator.
#
# Mechanically generates ~125 REG URLs by appending
# &series_type=bilateral_only to each existing intl REG URL.
#
# Tag is REG (NOT NEW) because the FilterBar promotion is inert by
# design: the backend SQL output for `?series_type=bilateral_only`
# is byte-identical pre- and post-promotion (the param simply binds
# to FilterBarParams now instead of AuxParams; same series_type_clause
# fires either way). NEW URLs would fail the runner's "NEW changed"
# assertion. REG URLs pin backwards-compat: a future refactor that
# accidentally drops series_type from FilterBarParams (or renames it)
# would break every one of these.
#
# Filter rule: only URLs that include team_type=international qualify.
# bilateral_only is a hard team_type='international' clause; a club URL
# with bilateral_only would zero out (no regression signal).
#
# Output: series_type.txt per affected suite, ready to append to
# urls.txt.
#
# Usage:
#   bash tests/regression/series_type_url_gen.sh
#   for s in teams scope-averages batting bowling fielding \
#            players head_to_head matches venues filterbar_refs; do
#     cat tests/regression/$s/series_type.txt >> tests/regression/$s/urls.txt
#   done
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SUITES=(teams scope-averages batting bowling fielding players head_to_head matches venues filterbar_refs)

for suite in "${SUITES[@]}"; do
  src="$REPO_ROOT/tests/regression/$suite/urls.txt"
  out="$REPO_ROOT/tests/regression/$suite/series_type.txt"
  [ -f "$src" ] || { echo "SKIP $suite (no urls.txt)"; continue; }

  : > "$out"
  echo "# series_type FilterBar — generated REG URLs (one-shot)" >> "$out"
  echo "# Source: each row mirrors an intl REG row in urls.txt with &series_type=bilateral_only appended." >> "$out"
  echo "# Tag REG (not NEW): promotion is inert by design — backend output is byte-identical pre/post." >> "$out"
  echo "# Filter: only intl-context REG entries qualify (bilateral_only requires team_type=international)." >> "$out"
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

    # Build the NEW URL: append series_type param.
    case "$url" in
      *\?*) new_url="${url}&series_type=bilateral_only" ;;
      *)    new_url="${url}?series_type=bilateral_only" ;;
    esac

    new_label="${label}_bilat"
    printf "REG %-50s %s\n" "$new_label" "$new_url" >> "$out"
    count=$((count + 1))
  done < "$src"

  echo "  $suite: $count REG URLs → $out"
done

echo
echo "Generated series_type.txt per suite. Review, then concatenate into each urls.txt:"
echo "  for s in ${SUITES[*]}; do cat tests/regression/\$s/series_type.txt >> tests/regression/\$s/urls.txt; done"
