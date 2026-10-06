#!/usr/bin/env bash
# Audit every CLAUDE.md against current monorepo state.
# Emits one finding per line; nothing means clean.
set -euo pipefail

repo_root=""
if repo_root=$(git rev-parse --show-toplevel 2>/dev/null); then
  :
else
  repo_root="$PWD"
fi
cd "$repo_root"

taskfile=""
if [ -f Taskfile.yaml ]; then
  taskfile="Taskfile.yaml"
elif [ -f Taskfile.yml ]; then
  taskfile="Taskfile.yml"
fi

# Collect known task names (best-effort: parse `<name>:` keys at column 0–2)
known_tasks=""
if [ -n "$taskfile" ]; then
  known_tasks=$(awk '/^  [A-Za-z][A-Za-z0-9:_-]*:/ {gsub(/^ +| *:.*$/, ""); print}' "$taskfile" || true)
fi

# Collect backends present on disk
present_backends=""
if [ -d backends ]; then
  present_backends=$(find backends -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null || true)
fi

# Find every CLAUDE.md
mapfile -t files < <(find . -name CLAUDE.md -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null || true)

for f in "${files[@]}"; do
  [ -z "$f" ] && continue
  lines=$(wc -l <"$f" | tr -d ' ')
  if [ "$lines" -gt 300 ]; then
    printf '%s: %s lines (>300, consider splitting)\n' "$f" "$lines"
  fi

  # Stale task references
  if [ -n "$known_tasks" ]; then
    grep -oE 'task [A-Za-z][A-Za-z0-9:_-]+' "$f" 2>/dev/null | awk '{print $2}' | sort -u | while read -r ref; do
      [ -z "$ref" ] && continue
      if ! printf '%s\n' "$known_tasks" | grep -Fxq "$ref"; then
        # shellcheck disable=SC2016  # backticks are Markdown formatting for human output
        printf '%s: references task `%s` not present in %s\n' "$f" "$ref" "$taskfile"
      fi
    done
  fi
done

# Stale backend references in root CLAUDE.md
if [ -f CLAUDE.md ] && [ -n "$present_backends" ]; then
  grep -oE 'backends/[A-Za-z0-9_-]+' CLAUDE.md 2>/dev/null | sed 's|backends/||' | sort -u | while read -r b; do
    [ -z "$b" ] && continue
    if ! printf '%s\n' "$present_backends" | grep -Fxq "$b"; then
      # shellcheck disable=SC2016  # backticks are Markdown formatting for human output
      printf 'CLAUDE.md: references backend `%s` not present under backends/\n' "$b"
    fi
  done
fi

exit 0
