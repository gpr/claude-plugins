#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: audit dependencies after uv add / pip install
source "$(dirname "$0")/_lib.sh"

hook_input="$(cat)"
command="$(echo "$hook_input" | jq -r '.tool_input.command // empty')"

# Only trigger on dependency-adding commands
if [[ ! "$command" =~ (uv\ add|pip\ install|uv\ pip\ install) ]]; then
  exit 0
fi

project_root=$(find_project_root "${CLAUDE_PROJECT_DIR:-.}") || exit 0

# Require uv
command -v uv &>/dev/null || exit 0

# Check pip-audit is available in the project
if ! uv run pip-audit --version &>/dev/null 2>&1; then
  report_error "pip-audit is not installed. Run: uv add --dev pip-audit"
  exit 0
fi

if ! audit_output=$(cd "$project_root" && uv run pip-audit 2>&1); then
  report_error "pip-audit found vulnerabilities after dependency change:"$'\n'"$audit_output"$'\nConsider updating or removing vulnerable packages.'
fi
