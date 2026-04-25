#!/usr/bin/env bash
# Stream TS errors. One line per diagnostic; suppresses "Found N errors" summaries.
set -u

# Find repo root (where pnpm-lock.yaml lives) and cd there.
d="$PWD"
while [ "$d" != "/" ]; do
  [ -f "$d/pnpm-lock.yaml" ] && break
  d="$(dirname "$d")"
done
[ "$d" = "/" ] && exit 0
cd "$d" || exit 0

exec pnpm exec tsc --noEmit --watch --pretty false --preserveWatchOutput 2>&1 \
  | grep -E '^[^[:space:]].*\.tsx?\([0-9]+,[0-9]+\): error TS[0-9]+:'
