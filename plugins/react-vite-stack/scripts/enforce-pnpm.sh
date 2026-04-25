#!/usr/bin/env bash
# SessionStart: refuse to proceed if non-pnpm artifacts exist.
# To bypass for a polyglot context: rename or delete this script.
set -u

problems=""
[ -f package-lock.json ] && problems+="- package-lock.json present (delete: pnpm import && rm package-lock.json)\n"
[ -f yarn.lock ] && problems+="- yarn.lock present (delete: pnpm import && rm yarn.lock)\n"
[ -f bun.lockb ] && problems+="- bun.lockb present (delete it; this project uses pnpm)\n"

if [ -f package.json ] && ! grep -q '"packageManager"[[:space:]]*:[[:space:]]*"pnpm@' package.json; then
  problems+="- package.json missing \"packageManager\": \"pnpm@<version>\" (run: corepack use pnpm@latest)\n"
fi

if [ -n "$problems" ]; then
  printf 'PNPM ENFORCEMENT — fix before continuing:\n%b\nTo skip this check, rename hooks/hooks.json in the plugin.\n' "$problems" >&2
  exit 2
fi
exit 0
