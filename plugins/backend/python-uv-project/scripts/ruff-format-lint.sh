#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: auto-format and lint Python files with ruff after Write/Edit
source "$(dirname "$0")/_lib.sh"
export UV_NO_PROGRESS=1

read_hook_input  # sets: hook_input, file_path, abs_path
init_tool_runner  # sets: tool_runner_prefix

errors=""

# Run ruff format
if ! format_output="$("${tool_runner_prefix[@]}" ruff format "$abs_path" 2>&1)"; then
  errors+=$'ruff format failed:\n'"${format_output}"$'\n\n'
fi

# Run ruff check with auto-fix
if ! check_output="$("${tool_runner_prefix[@]}" ruff check --fix "$abs_path" 2>&1)"; then
  # ruff check exits non-zero when unfixable issues remain
  errors+=$'ruff check found issues:\n'"${check_output}"$'\n\n'
fi

if [[ -n "$errors" ]]; then
  report_block \
    "ruff found unfixable issues in ${file_path}" \
    "${errors}Please fix the remaining issues."
fi
