#!/usr/bin/env bash
# SessionStart: refuse to proceed if non-pnpm artifacts exist.
# To bypass for a polyglot context: rename or delete this script.
# NOTE: SessionStart exit 2 is non-blocking per docs; output is advisory only.
set -euo pipefail

problems=""
if [ -f package-lock.json ]; then
  problems+="- package-lock.json present (delete: pnpm import && rm package-lock.json)\n"
fi
if [ -f yarn.lock ]; then
  problems+="- yarn.lock present (delete: pnpm import && rm yarn.lock)\n"
fi
if [ -f bun.lockb ]; then
  problems+="- bun.lockb present (delete it; this project uses pnpm)\n"
fi

if [ -f package.json ] && ! grep -q '"packageManager"[[:space:]]*:[[:space:]]*"pnpm@' package.json; then
  problems+="- package.json missing \"packageManager\": \"pnpm@<version>\" (run: corepack use pnpm@latest)\n"
fi

if [ -n "$problems" ]; then
  printf 'PNPM ENFORCEMENT — fix before continuing:\n%b\nTo skip this check, rename hooks/hooks.json in the plugin.\n' "$problems" >&2
  exit 2
fi
exit 0
