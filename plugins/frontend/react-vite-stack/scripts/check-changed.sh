#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit): check only the file that changed.
# Reads hook payload JSON from stdin; extracts file_path; runs scoped checks.
# NOTE: PostToolUse exit 2 is non-blocking per docs; checks here are advisory.
set -euo pipefail

file="$(jq -r '.tool_input.file_path // .tool_input.new_path // empty')"

if [ -z "$file" ]; then
  exit 0
fi
if [ ! -f "$file" ]; then
  exit 0
fi

case "$file" in
  *.ts|*.tsx|*.js|*.jsx) ;;
  *) exit 0 ;;
esac

cd_to_root() {
  local d
  d="$(dirname "$1")"
  while [ "$d" != "/" ]; do
    if [ -f "$d/package.json" ]; then
      echo "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}

if ! root="$(cd_to_root "$file")"; then
  exit 0
fi
cd "$root" || exit 0

errors=""

# Format (silent on success)
pnpm exec prettier --write "$file" >/dev/null 2>&1 || errors+="prettier failed on $file\n"

# Lint (auto-fix what's safe; report what isn't)
if ! lint_out="$(pnpm exec eslint --fix "$file" 2>&1)"; then
  errors+="eslint:\n$lint_out\n"
fi

# NOTE: tsc is deliberately NOT run here. The typecheck-watch monitor streams
# diagnostics continuously; running tsc per-edit is 5-20s and blocks the agent.

if [ -n "$errors" ]; then
  printf 'CHECKS FAILED on %s\n%b' "$file" "$errors" >&2
  exit 2
fi
exit 0
