#!/usr/bin/env bash
# FileChanged hook: keep src/routeTree.gen.ts in sync after src/routes/**/*.tsx edits.
# Exits 2 with stderr output on failure so the harness surfaces the regen error.
set -euo pipefail

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

if ! out="$(pnpm exec tsr generate 2>&1)"; then
  printf 'route-tree regen failed:\n%s\n' "$out" >&2
  exit 2
fi
exit 0
