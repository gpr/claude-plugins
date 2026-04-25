#!/usr/bin/env bash
# Stream Vitest failures.
set -u

d="$PWD"
while [ "$d" != "/" ]; do
  [ -f "$d/pnpm-lock.yaml" ] && break
  d="$(dirname "$d")"
done
[ "$d" = "/" ] && exit 0
cd "$d" || exit 0

# Match: "FAIL" headers, the literal × glyph vitest prints, and assertion errors.
# The × is bytes E2 9C 95; we put it raw, not as \u00d7 (grep -E doesn't interpret that).
exec pnpm exec vitest --watch --reporter=verbose 2>&1 \
  | grep -E '^([[:space:]]*FAIL|[[:space:]]*×|AssertionError|Error:|TypeError:)'
