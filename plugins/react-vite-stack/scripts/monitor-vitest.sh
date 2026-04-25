#!/usr/bin/env bash
# Stream Vitest failures.
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

# Match: "FAIL" headers, the literal × glyph vitest prints, and assertion errors.
# The × is bytes E2 9C 95; we put it raw, not as × (grep -E doesn't interpret that).
exec pnpm exec vitest --watch --reporter=verbose 2>&1 \
  | grep -E '^([[:space:]]*FAIL|[[:space:]]*×|AssertionError|Error:|TypeError:)'
