#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: auto-run matching pytest tests after Write/Edit on .py files.
# Also checks coverage on changed lines for source files (merged from coverage-gate.sh).
source "$(dirname "$0")/_lib.sh"

read_hook_input  # sets: hook_input, file_path, abs_path

project_root=$(find_project_root "$(dirname "$abs_path")") || exit 0
workspace_root=$(find_workspace_root "$project_root")

rel_path="${abs_path#"$project_root"/}"

# Map source file to test target
test_info=$(find_test_file "$project_root" "$rel_path")
[[ -z "$test_info" ]] && exit 0

test_type="${test_info%%:*}"
test_target="${test_info#*:}"

# Verify target exists
if [[ ! -e "$project_root/$test_target" ]]; then
  exit 0
fi

build_run_cmd "$workspace_root" "$project_root" || exit 0

pytest_args=("$test_target" --tb=short -q)

# Skip slow tests — only for individual files, not directory runs (conftest)
if [[ "$test_type" == "file" ]]; then
  pytest_args+=(-m "not slow")
fi

# Smart test scope — only for source files (not test files, not conftest)
if [[ "$test_type" == "file" && "$rel_path" != tests/* ]]; then
  changed_funcs=$(
    git -C "$project_root" diff HEAD -- "$abs_path" 2>/dev/null \
      | grep -E '^\+\s*(async\s+)?def\s+' \
      | sed -E 's/^\+\s*(async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*).*/\2/' \
      | sort -u \
      | head -10
  ) || true

  if [[ -n "$changed_funcs" ]]; then
    k_expr=""
    while IFS= read -r func; do
      [[ -z "$func" ]] && continue
      if [[ -n "$k_expr" ]]; then
        k_expr+=" or "
      fi
      k_expr+="$func"
    done <<< "$changed_funcs"
    if [[ -n "$k_expr" ]]; then
      pytest_args+=(-k "$k_expr")
    fi
  fi
fi

# Determine if coverage analysis is applicable.
# Only for source files with changed lines — skip tests, __init__, conftest.
want_coverage=false
changed_lines=""
cov_module=""
cov_json=""

if [[ "$test_type" == "file" && "$rel_path" != tests/* ]]; then
  base_name="$(basename "$rel_path" .py)"
  if [[ "$base_name" != "__init__" && "$base_name" != "conftest" ]]; then
    changed_lines=$(git -C "$project_root" diff HEAD -- "$abs_path" 2>/dev/null \
      | grep -E '^@@' \
      | sed -E 's/^@@ -[0-9,]+ \+([0-9]+)(,([0-9]+))? @@.*/\1 \3/' \
      | while read -r start count; do
          count=${count:-1}
          for ((i=start; i<start+count; i++)); do echo "$i"; done
        done
    ) || true

    if [[ -n "$changed_lines" ]]; then
      want_coverage=true
      cov_module="$rel_path"
      cov_module="${cov_module#src/}"
      cov_module="${cov_module%.py}"
      cov_module="${cov_module//\//.}"
      cov_json="${TMPDIR:-/tmp}/pycov-$$.json"
      trap 'rm -f "$cov_json"' EXIT
      pytest_args+=(--cov="$cov_module" --cov-report="json:$cov_json")
    fi
  fi
fi

# Run tests
if ! test_output="$(cd "$project_root" && "${run_cmd[@]}" "${pytest_args[@]}" 2>&1)"; then
  # If failure is from missing pytest-cov, retry without coverage flags
  if [[ "$want_coverage" == true ]] && echo "$test_output" | grep -q "unrecognized arguments"; then
    want_coverage=false
    clean_args=()
    for arg in "${pytest_args[@]}"; do
      case "$arg" in
        --cov=*|--cov-report=*) ;;
        *) clean_args+=("$arg") ;;
      esac
    done
    if ! test_output="$(cd "$project_root" && "${run_cmd[@]}" "${clean_args[@]}" 2>&1)"; then
      report_block "Tests failed for ${test_target}" "${test_output}"$'\nPlease fix the failing tests.'
    fi
  else
    report_block "Tests failed for ${test_target}" "${test_output}"$'\nPlease fix the failing tests.'
  fi
fi

# Coverage analysis — only if tests passed and coverage data was collected
if [[ "$want_coverage" == true && -f "$cov_json" ]]; then
  uncovered=$(COV_JSON="$cov_json" CHANGED_LINES="$changed_lines" REL_PATH="$rel_path" \
    python3 -c "
import json, os, sys
try:
    with open(os.environ['COV_JSON']) as f:
        cov = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    sys.exit(0)
changed = set(int(l) for l in os.environ['CHANGED_LINES'].strip().split('\n') if l.strip())
if not changed:
    sys.exit(0)
rel = os.environ['REL_PATH']
rel_no_src = rel.removeprefix('src/')
for fname, data in cov.get('files', {}).items():
    if fname.endswith(rel) or fname.endswith(rel_no_src):
        missing = set(data.get('missing_lines', []))
        uncovered_changed = sorted(changed & missing)
        if uncovered_changed:
            print(f'Lines {uncovered_changed} are not covered by tests')
        break
" 2>/dev/null) || true

  if [[ -n "$uncovered" ]]; then
    report_block "Coverage gap in ${rel_path}" "${uncovered}. Consider adding tests for the uncovered changed lines."
  fi
fi
