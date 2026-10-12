#!/usr/bin/env bash
# Seed "<plugin>-<version>" tags for plugins cog has never released, so that
# `cog bump --auto` starts from the version declared in plugin.json instead of 0.0.0.
#
# Usage: bootstrap-tags.sh <before-sha>
#   <before-sha>  commit the push started from (github.event.before).
#     - Plugins that already existed there are tagged at that commit, so the pushed
#       commits are still evaluated for a bump.
#     - Anything else (new plugin, all-zero sha) is tagged on a new empty seed commit
#       on top of HEAD. cog counts a commit that is itself tagged as unreleased, so
#       tagging HEAD would bump the plugin on its own introduction.
#   If the push changed .github/workflows, <before-sha> is replaced by the last
#   commit that touched them: GitHub refuses a GITHUB_TOKEN push of a new ref whose
#   workflow files differ from main ("without `workflows` permission"). Plugin
#   commits before that one are then not evaluated for this first bump.
#
# Needs git user.name/user.email configured when a seed commit is required.
set -euo pipefail

before="${1:-}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

if ! git rev-parse -q --verify "${before}^{commit}" >/dev/null 2>&1; then
  before=""
fi

workflows=.github/workflows
if [ -n "$before" ] && ! git diff --quiet "$before" HEAD -- "$workflows"; then
  before="$(git log -1 --format=%H HEAD -- "$workflows")"
  if [ -z "$before" ] || ! git diff --quiet "$before" HEAD -- "$workflows"; then
    before=""
  fi
  echo "bootstrap: push changed $workflows, tagging at ${before:-a seed commit} instead"
fi

seeded=()
while read -r name path; do
  if [ -n "$(git tag -l "${name}-*")" ]; then
    continue
  fi
  manifest="$path/.claude-plugin/plugin.json"
  if [ -n "$before" ] && git cat-file -e "$before:$manifest" 2>/dev/null; then
    version="$(git show "$before:$manifest" | jq -er '.version')"
    echo "bootstrap: $name-$version at $before"
    git tag "$name-$version" "$before"
  else
    seeded+=("$name")
  fi
done < <(cog_packages)

if [ "${#seeded[@]}" -gt 0 ]; then
  git commit -q --allow-empty -m "chore(release): seed first versions of ${seeded[*]}"
  while read -r name path; do
    for s in "${seeded[@]}"; do
      [ "$s" = "$name" ] || continue
      version="$(jq -er '.version' "$path/.claude-plugin/plugin.json")"
      echo "bootstrap: $name-$version at seed commit"
      git tag "$name-$version" HEAD
    done
  done < <(cog_packages)
fi
