#!/usr/bin/env bash
# Push local tags the remote lacks, at most 5 per push: a repository ruleset rejects
# any push that updates more than 5 branches or tags, and the first release seeds
# one tag per plugin.
#
# Usage: push-tags.sh [remote]   (default: origin)
set -euo pipefail

remote="${1:-origin}"
batch=5

mapfile -t missing < <(
  LC_ALL=C comm -23 \
    <(git tag -l | LC_ALL=C sort) \
    <(git ls-remote --tags --refs "$remote" | sed 's#.*refs/tags/##' | LC_ALL=C sort)
)

if [ "${#missing[@]}" -eq 0 ]; then
  echo "tags: nothing to push"
  exit 0
fi

refs=("${missing[@]/#/refs/tags/}")
for ((i = 0; i < ${#refs[@]}; i += batch)); do
  git push "$remote" "${refs[@]:i:batch}"
done
