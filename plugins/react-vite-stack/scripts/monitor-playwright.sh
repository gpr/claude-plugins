#!/usr/bin/env bash
# Stream Playwright failures. Lazy-armed via on-skill-invoke:vitest-rtl-playwright.
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

exec pnpm exec playwright test --reporter=line --watch 2>&1 \
  | grep -E '^([[:space:]]*✘|Error:|TimeoutError:|locator\(.*\) (resolved to|expected))'
