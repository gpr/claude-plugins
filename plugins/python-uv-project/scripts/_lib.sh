# Shared utilities for python-dev-environment hooks — source this, don't execute directly.

# Read PostToolUse hook stdin and extract file_path.
# Sets globals: hook_input, file_path, abs_path, project_root
# Exits 0 (skip) if not a .py file, file doesn't exist, or no project found.
read_hook_input() {
  hook_input="$(cat)"
  file_path="$(echo "$hook_input" | jq -r '.tool_input.file_path // empty')"
  if [[ -z "$file_path" || "$file_path" != *.py ]]; then
    exit 0
  fi
  if [[ ! -f "$file_path" ]]; then
    exit 0
  fi
  abs_path="$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")"
}

# Build a command prefix for running Python dev tools (ruff, bandit, etc.).
# Prefers `uv run` to resolve from the project venv, falls back to direct invocation.
# Usage: run_tool=($(tool_runner)); "${run_tool[@]}" ruff check file.py
# Sets global: tool_runner_prefix=()
init_tool_runner() {
  if command -v uv &>/dev/null; then
    tool_runner_prefix=(uv run --quiet --no-progress)
  else
    tool_runner_prefix=()
  fi
}

# Find the nearest pyproject.toml walking up from a given directory.
# Usage: project_root=$(find_project_root "/some/path") || exit 0
find_project_root() {
  local dir="$1"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/pyproject.toml" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Find workspace root (pyproject.toml containing [tool.uv.workspace]).
# Walks up from project_root. Returns project_root if no workspace found.
find_workspace_root() {
  local project_root="$1"
  local dir="$(dirname "$project_root")"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/pyproject.toml" ]] && grep -q '\[tool\.uv\.workspace\]' "$dir/pyproject.toml"; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  echo "$project_root"
}

# Build pytest runner command array.
# Sets global: run_cmd=()
# Returns 1 if no pytest runner is available.
build_run_cmd() {
  local workspace_root="${1:-}"
  if command -v uv &>/dev/null; then
    if [[ -n "$workspace_root" && "$workspace_root" != "${2:-}" ]]; then
      run_cmd=(uv run --project "$workspace_root" pytest)
    else
      run_cmd=(uv run pytest)
    fi
  elif command -v pytest &>/dev/null; then
    run_cmd=(pytest)
  else
    return 1
  fi
}

# Map a source file to its test counterpart.
# Usage: result=$(find_test_file "$project_root" "$rel_path")
# Returns: "file:<relative_test_path>" or "dir:<relative_dir_path>" or "" (no match)
find_test_file() {
  local project_root="$1" rel_path="$2"
  local module_name dir_part without_src

  module_name="$(basename "$rel_path" .py)"

  # conftest.py -> run all tests in that directory
  if [[ "$module_name" == "conftest" ]]; then
    local conftest_dir
    conftest_dir="$(dirname "$rel_path")"
    if [[ -d "$project_root/$conftest_dir" ]]; then
      echo "dir:$conftest_dir"
    fi
    return
  fi

  # Already a test file -> run it directly
  if [[ "$rel_path" == tests/* ]]; then
    echo "file:$rel_path"
    return
  fi

  # Skip __init__.py
  [[ "$module_name" == "__init__" ]] && return

  # src/ layout: src/<pkg>/module.py -> tests/<pkg>/test_module.py
  if [[ "$rel_path" == src/* ]]; then
    without_src="${rel_path#src/}"
    dir_part="$(dirname "$without_src")"
    module_name="$(basename "$without_src" .py)"
    local candidate="tests/${dir_part}/test_${module_name}.py"
    if [[ -f "$project_root/$candidate" ]]; then
      echo "file:$candidate"
    fi
    return
  fi

  # Flat layout: <pkg>/module.py -> tests/<pkg>/test_module.py or tests/test_module.py
  if [[ -d "$project_root/tests" ]]; then
    dir_part="$(dirname "$rel_path")"
    if [[ "$dir_part" != "." ]]; then
      local c1="tests/${dir_part}/test_${module_name}.py"
      local c2="tests/test_${module_name}.py"
      if [[ -f "$project_root/$c1" ]]; then
        echo "file:$c1"
        return
      fi
      if [[ -f "$project_root/$c2" ]]; then
        echo "file:$c2"
        return
      fi
    else
      # Top-level file: module.py -> tests/test_module.py
      local c="tests/test_${module_name}.py"
      if [[ -f "$project_root/$c" ]]; then
        echo "file:$c"
      fi
    fi
  fi
}

# Report error to Claude via plain text on stderr, then exit 2.
# Per hooks docs: exit 2 feeds stderr to Claude as an error message (raw text, not parsed as JSON).
# Use for environment problems (missing tools, broken setup).
report_error() {
  local msg="$1"
  echo "$msg" >&2
  exit 2
}

# Structured blocking feedback to Claude via JSON stdout (exit 0).
# Per hooks docs: exit 0 with {"decision":"block"} provides rich structured feedback.
# Use for actionable code issues (lint errors, test failures, security findings).
report_block() {
  local reason="$1"
  local context="${2:-}"
  if command -v jq &>/dev/null; then
    jq -nc --arg r "$reason" --arg c "$context" \
      '{"decision":"block","reason":$r,"additionalContext":$c}'
  else
    python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1],'additionalContext':sys.argv[2]}))" "$reason" "$context"
  fi
  exit 0
}
