#!/usr/bin/env bash
# Fail unless plugins/*/*/.claude-plugin/plugin.json, marketplace.json and
# cog.toml [monorepo.packages] agree on name + path for every plugin.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

marketplace=".claude-plugin/marketplace.json"
fail=0
err() { echo "ERROR: $*" >&2; fail=1; }

declare -A cog_path
while read -r name path; do
  cog_path[$name]=$path
done < <(cog_packages)

declare -A market_path
while IFS=$'\t' read -r name source; do
  market_path[$name]=${source#./}
done < <(jq -r '.plugins[] | [.name, .source] | @tsv' "$marketplace")

declare -A seen
for manifest in plugins/*/*/.claude-plugin/plugin.json; do
  path=${manifest%/.claude-plugin/plugin.json}
  name=$(jq -er '.name' "$manifest")
  seen[$name]=1
  [ "${cog_path[$name]-}" = "$path" ] || err "$name ($path): missing or wrong path in cog.toml [monorepo.packages]"
  [ "${market_path[$name]-}" = "$path" ] || err "$name ($path): missing or wrong source in $marketplace"
  jq -e '.version | strings | test("^[0-9]+\\.[0-9]+\\.[0-9]+$")' "$manifest" >/dev/null ||
    err "$name: plugin.json needs a semver \"version\""
done

for name in "${!cog_path[@]}"; do
  [ -n "${seen[$name]-}" ] || err "$name: in cog.toml but no plugins/*/*/.claude-plugin/plugin.json with that name"
done
for name in "${!market_path[@]}"; do
  [ -n "${seen[$name]-}" ] || err "$name: in $marketplace but no plugin.json with that name"
done

[ "$fail" -eq 0 ] && echo "registry OK (${#seen[@]} plugins)"
exit "$fail"
