#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: run bandit security scan on Python files after Write/Edit
source "$(dirname "$0")/_lib.sh"

read_hook_input  # sets: hook_input, file_path, abs_path
init_tool_runner  # sets: tool_runner_prefix

# Run bandit in quiet mode (only show issues)
if ! output="$("${tool_runner_prefix[@]}" bandit -q "$abs_path" 2>&1)"; then
  report_block \
    "bandit found security issues in ${file_path}" \
    "${output}"$'\n'"Please fix the security issues."
fi
