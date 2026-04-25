#!/usr/bin/env bash
# Stream TS errors. One line per diagnostic; suppresses "Found N errors" summaries.
set -euo pipefail

# Find repo root (where pnpm-lock.yaml lives) and cd there.
d="$PWD"
while [ "$d" != "/" ]; do
  if [ -f "$d/pnpm-lock.yaml" ]; then
    break
  fi
  d="$(dirname "$d")"
done
if [ "$d" = "/" ]; then
  exit 0
fi
cd "$d" || exit 0

exec pnpm exec tsc --noEmit --watch --pretty false --preserveWatchOutput 2>&1 \
  | grep -E '^[^[:space:]].*\.tsx?\([0-9]+,[0-9]+\): error TS[0-9]+:'
