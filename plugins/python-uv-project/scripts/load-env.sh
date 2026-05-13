#!/usr/bin/env bash
set -euo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-.}"

if command -v direnv &>/dev/null; then
  direnv export bash >> "$CLAUDE_ENV_FILE"
elif [[ -f "$project_dir/.env" ]]; then
  # Load .env manually — skip comments and blank lines
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    echo "$line" >> "$CLAUDE_ENV_FILE"
  done < "$project_dir/.env"
fi
