#!/usr/bin/env bash
# Runs after Claude Writes or Edits a file. Targets Ruby files only.
# - Always: rubocop --autocorrect on the changed file (if rubocop is available)
# - Optional: run the matching RSpec file if run_tests_on_edit=true

set -euo pipefail

# Hook payload arrives on stdin as JSON. We pull the affected path via jq
# if available; otherwise fall back to a grep — hooks shouldn't hard-require jq.
PAYLOAD="$(cat)"

extract_path() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "${PAYLOAD}" | jq -r '.tool_input.file_path // empty' 2>/dev/null
  else
    printf '%s' "${PAYLOAD}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''),end='')" 2>/dev/null
  fi
}

FILE_PATH="$(extract_path)"
[ -z "${FILE_PATH}" ] && exit 0

# Only act on Ruby sources inside the project.
case "${FILE_PATH}" in
  *.rb|*.rake) ;;
  *) exit 0 ;;
esac

# Skip if the file no longer exists (e.g. deleted in the same turn).
[ -f "${FILE_PATH}" ] || exit 0

# --- Rubocop -----------------------------------------------------------------
if command -v bundle >/dev/null 2>&1 && [ -f "Gemfile" ] && bundle show rubocop >/dev/null 2>&1; then
  bundle exec rubocop --autocorrect --force-exclusion "${FILE_PATH}" 2>&1 || true
elif command -v rubocop >/dev/null 2>&1; then
  rubocop --autocorrect --force-exclusion "${FILE_PATH}" 2>&1 || true
fi

# --- Matching spec -----------------------------------------------------------
RUN_TESTS="${CLAUDE_PLUGIN_OPTION_RUN_TESTS_ON_EDIT:-false}"
if [ "${RUN_TESTS}" != "true" ]; then
  exit 0
fi

# Map app/models/user.rb -> spec/models/user_spec.rb, and spec files to themselves.
case "${FILE_PATH}" in
  spec/*_spec.rb)
    SPEC_PATH="${FILE_PATH}"
    ;;
  app/*.rb)
    SPEC_PATH="spec/${FILE_PATH#app/}"
    SPEC_PATH="${SPEC_PATH%.rb}_spec.rb"
    ;;
  lib/*.rb)
    SPEC_PATH="spec/lib/${FILE_PATH#lib/}"
    SPEC_PATH="${SPEC_PATH%.rb}_spec.rb"
    ;;
  *)
    exit 0
    ;;
esac

if [ ! -f "${SPEC_PATH}" ]; then
  echo "[rails-api-backend] No matching spec at ${SPEC_PATH}, skipping."
  exit 0
fi

if [ -f "Gemfile" ] && command -v bundle >/dev/null 2>&1 && bundle show rspec-core >/dev/null 2>&1; then
  bundle exec rspec "${SPEC_PATH}" --no-color 2>&1 || true
elif command -v rspec >/dev/null 2>&1; then
  rspec "${SPEC_PATH}" --no-color 2>&1 || true
fi
