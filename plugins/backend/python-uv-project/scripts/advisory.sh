#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_lib.sh"

project_root=$(find_project_root "${CLAUDE_PROJECT_DIR:-.}" || true)
if [[ -z "$project_root" ]]; then
  printf '%s' "No pyproject.toml found. To bootstrap a Python project, run: uv init"
  exit 0
fi

# Accumulate advisory context for Claude (output once at the end via stdout JSON)
advisory=""

# --- Dev-dependency advisory ---
missing_devdeps=()
for tool in pytest ruff pip-audit bandit pyright; do
  if ! uv run "$tool" --version &>/dev/null; then
    missing_devdeps+=("$tool")
  fi
done
# pytest-cov is a pytest plugin, not a CLI — check via python import
if ! uv run python -c "import pytest_cov" &>/dev/null; then
  missing_devdeps+=("pytest-cov")
fi

if [[ ${#missing_devdeps[@]} -gt 0 ]]; then
  advisory+="Some dev tools used by python-dev-environment hooks are not installed: ${missing_devdeps[*]}
Run: uv add --dev ${missing_devdeps[*]}

"
fi

# --- Ruff config bootstrap (#6) ---
if [[ -f "$project_root/pyproject.toml" ]]; then
  if ! grep -q '\[tool\.ruff\]' "$project_root/pyproject.toml"; then
    advisory+='No [tool.ruff] section found in pyproject.toml. Consider adding:

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"

'
  fi
fi

# --- Pyright baseline (#7) ---
if ! grep -q '\[tool\.pyright\]' "$project_root/pyproject.toml" 2>/dev/null \
   && [[ ! -f "$project_root/pyrightconfig.json" ]]; then
  if command -v pyright &>/dev/null; then
    error_count=$(cd "$project_root" && pyright --outputjson 2>/dev/null \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('summary',{}).get('errorCount',0))" 2>/dev/null) || error_count=0

    if [[ "$error_count" -gt 0 ]]; then
      advisory+="Pyright found $error_count existing type errors. Consider adding a pyrightconfig.json with:

{
  \"reportMissingImports\": \"warning\",
  \"reportMissingModuleSource\": \"warning\",
  \"reportOptionalMemberAccess\": \"warning\"
}

This will downgrade common errors to warnings so they don't block your workflow.
"
    fi
  fi
fi

# --- mise.toml tools advisory ---
mise_file=""
for f in "$project_root/mise.toml" "$project_root/.mise.toml"; do
  if [[ -f "$f" ]]; then
    mise_file="$f"
    break
  fi
done

if [[ -n "$mise_file" ]]; then
  missing_mise_tools=()
  for tool in perk direnv uv cocogitto prettier task use; do
    if ! grep -q "$tool" "$mise_file"; then
      missing_mise_tools+=("$tool")
    fi
  done
  if [[ ${#missing_mise_tools[@]} -gt 0 ]]; then
    advisory+="mise.toml is missing tools: ${missing_mise_tools[*]}
Consider adding them to $(basename "$mise_file") for a complete dev environment.

"
  fi
fi

# Output advisory as plain text — SessionStart stdout is added directly as context Claude can see
if [[ -n "$advisory" ]]; then
  printf '%s' "Reminder: At any time launch an Agent to fix the following issues:\n$advisory"
fi
