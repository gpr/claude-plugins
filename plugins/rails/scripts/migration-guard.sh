#!/usr/bin/env bash
# PreToolUse guard for db/migrate/*.rb writes.
# Blocks migrations containing patterns that are unsafe on a large live table.
# Emits a structured JSON decision so the model sees a clear reason.

set -euo pipefail

PAYLOAD="$(cat)"

extract() {
  python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', {}) or {}
fp = ti.get('file_path', '') or ''
content = ti.get('content') or ti.get('new_string') or ''
print(fp)
print('---CONTENT---')
print(content)
" 2>/dev/null <<<"${PAYLOAD}"
}

BLOB="$(extract || true)"
FILE_PATH="$(printf '%s\n' "${BLOB}" | sed -n '1p')"
CONTENT="$(printf '%s\n' "${BLOB}" | sed -n '/^---CONTENT---$/,$p' | tail -n +2)"

# Only guard migration files.
case "${FILE_PATH}" in
  *db/migrate/*.rb) ;;
  *) exit 0 ;;
esac

[ -n "${CONTENT}" ] || exit 0

block() {
  local reason="$1"
  python3 -c "
import json, sys
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'deny',
    'permissionDecisionReason': sys.argv[1]
  }
}))
" "${reason}"
  exit 0
}

# remove_column / drop_table without a safety comment on the same line
if printf '%s' "${CONTENT}" | grep -qE '^\s*(remove_column|drop_table)\b' \
   && ! printf '%s' "${CONTENT}" | grep -qE '(remove_column|drop_table).*#.*safe'; then
  block "Migration contains remove_column/drop_table. Prod-safe pattern: deploy an ignored_columns PR first, then remove in a follow-up. Add '# safe: <reason>' on the line to override."
fi

# add_index without algorithm: :concurrently on a non-empty-table scenario
if printf '%s' "${CONTENT}" | grep -qE '^\s*add_index\b' \
   && ! printf '%s' "${CONTENT}" | grep -qE 'algorithm:\s*:concurrently' \
   && ! printf '%s' "${CONTENT}" | grep -qE '#.*safe'; then
  block "add_index without algorithm: :concurrently will lock writes on a large table. Add 'algorithm: :concurrently' (and 'disable_ddl_transaction!' at the class level), or append '# safe: <reason>'."
fi

# change_column_null :table, :col, false without default backfill
if printf '%s' "${CONTENT}" | grep -qE 'change_column_null\s*:\s*[a-z_]+\s*,\s*:[a-z_]+\s*,\s*false' \
   && ! printf '%s' "${CONTENT}" | grep -qE '#.*safe'; then
  block "change_column_null ..., false on an existing column can fail or lock. Backfill in a prior migration and verify no NULLs remain, or append '# safe: <reason>'."
fi

# Raw SQL with DROP/DELETE
if printf '%s' "${CONTENT}" | grep -qiE 'execute\s*\(.*\b(DROP|DELETE|TRUNCATE)\b'; then
  block "Raw DROP/DELETE/TRUNCATE via execute() is not reversible and skips AR safeguards. Use the typed DSL or confirm with the user first."
fi

exit 0
