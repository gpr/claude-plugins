#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: auto-format Markdown files with prettier after Write/Edit
source "$(dirname "$0")/_lib.sh"

hook_input="$(cat)"
file_path="$(echo "$hook_input" | jq -r '.tool_input.file_path // empty')"
if [[ -z "$file_path" || "$file_path" != *.md ]]; then
  exit 0
fi
if [[ ! -f "$file_path" ]]; then
  exit 0
fi
abs_path="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"

if ! command -v prettier &>/dev/null; then
  exit 0
fi

if ! format_output="$(prettier --write "$abs_path" 2>&1)"; then
  report_block \
    "prettier failed to format ${file_path}" \
    "${format_output}"
fi
