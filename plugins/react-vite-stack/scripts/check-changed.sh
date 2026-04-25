#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit): check only the file that changed.
# Reads hook payload from stdin; extracts file_path; runs scoped checks.
set -u

payload="$(cat)"
file="$(printf '%s' "$payload" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"

[ -z "$file" ] && exit 0
[ ! -f "$file" ] && exit 0

case "$file" in
  *.ts|*.tsx|*.js|*.jsx) ;;
  *) exit 0 ;;
esac

cd_to_root() {
  local d
  d="$(dirname "$1")"
  while [ "$d" != "/" ]; do
    [ -f "$d/package.json" ] && { echo "$d"; return; }
    d="$(dirname "$d")"
  done
  return 1
}

root="$(cd_to_root "$file")" || exit 0
cd "$root" || exit 0

errors=""

# Format (silent on success)
pnpm exec prettier --write "$file" >/dev/null 2>&1 || errors+="prettier failed on $file\n"

# Lint (auto-fix what's safe; report what isn't)
lint_out="$(pnpm exec eslint --fix "$file" 2>&1)" || errors+="eslint:\n$lint_out\n"

# NOTE: tsc is deliberately NOT run here. The typecheck-watch monitor streams
# diagnostics continuously; running tsc per-edit is 5-20s and blocks the agent.

if [ -n "$errors" ]; then
  printf 'CHECKS FAILED on %s\n%b' "$file" "$errors" >&2
  exit 2
fi
exit 0
