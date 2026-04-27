#!/usr/bin/env bash
# PreToolUse(Bash) gate: enforce monorepo package-manager conventions.
#   - frontend/, website/      → pnpm only (no npm/yarn/bun)
#   - cross-package install    → prefer `task <pkg>:install`
# Reads the Bash tool's `command` field from PreToolUse JSON on stdin.
# Exit 2 with stderr message blocks the call; exit 0 lets it through.
set -euo pipefail

input=""
if [ ! -t 0 ]; then
  input=$(cat)
fi

# Tolerate non-JSON or jq-less environments — never block when we can't parse.
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
if [ -z "$cmd" ]; then
  exit 0
fi

block() {
  printf 'monorepo pm-guard: %s\n' "$1" >&2
  exit 2
}

# Forbid npm / yarn / bun install in frontend/website packages
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:];&|])(npm|yarn|bun)[[:space:]]+(install|add|i)\b'; then
  block "use pnpm in frontend/ and website/. Run \`task <package>:install\` or \`pnpm install\` from the package directory."
fi

# Suggest the task wrapper for cross-package installs at repo root
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:];&|])pnpm[[:space:]]+install\b' && [ -f "Taskfile.yaml" ] && [ ! -f "package.json" ]; then
  block "running \`pnpm install\` at repo root has no package.json. Did you mean \`task <package>:install\`? See \`task --list\`."
fi

exit 0
