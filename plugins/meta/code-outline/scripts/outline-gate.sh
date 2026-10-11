#!/usr/bin/env bash
# PreToolUse hook on Read: for a full (non-partial) read of a large source file,
# deny the Read and return a cached outline instead. Fails open on any error.
set -uo pipefail

[[ "${CODE_OUTLINE_DISABLE:-0}" == "1" || "${CODE_OUTLINE_INNER:-0}" == "1" ]] && exit 0
command -v jq &>/dev/null && command -v uv &>/dev/null || exit 0

plugin_root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
min_lines="${CODE_OUTLINE_MIN_LINES:-200}"

input="$(cat)"
file_path="$(jq -r '.tool_input.file_path // empty' <<<"$input")"
partial="$(jq -r '[.tool_input.offset, .tool_input.limit, .tool_input.pages] | map(select(. != null and . != "")) | length' <<<"$input")"
cwd="$(jq -r '.cwd // empty' <<<"$input")"

[[ -n "$file_path" && "$partial" == "0" && -f "$file_path" ]] || exit 0

project_root="${CLAUDE_PROJECT_DIR:-${cwd:-$PWD}}"
project_root="$(cd "$project_root" 2>/dev/null && pwd)" || exit 0
abs_path="$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)/$(basename "$file_path")"

case "$abs_path" in
  "$project_root"/.kb/*) exit 0 ;;
  "$project_root"/*) ;;
  *) exit 0 ;;
esac

case "${abs_path##*.}" in
  py|rb|ts|tsx|js|jsx|mjs|cjs|go|rs|java|sh|bash|php|c|h|cpp|hpp|cs|kt|swift) ;;
  *) exit 0 ;;
esac

lines="$(wc -l <"$abs_path")"
(( lines >= min_lines )) || exit 0

rel_path="${abs_path#"$project_root"/}"
kb_file="$project_root/.kb/files/$rel_path.md"
src_sha="$(sha256sum "$abs_path" | cut -d' ' -f1)"

cached_sha=""
[[ -f "$kb_file" ]] && cached_sha="$(grep -m1 '^source_sha256: ' "$kb_file" | cut -d' ' -f2)"

if [[ "$cached_sha" != "$src_sha" ]]; then
  mkdir -p "$(dirname "$kb_file")" || exit 0
  tmp="$kb_file.tmp.$$"
  if ! uv run --quiet --script "$plugin_root/scripts/outline.py" "$abs_path" "$rel_path" "$src_sha" >"$tmp" 2>/dev/null || [[ ! -s "$tmp" ]]; then
    rm -f "$tmp"
    exit 0
  fi
  mv "$tmp" "$kb_file"
  nohup bash "$plugin_root/scripts/enrich.sh" "$abs_path" "$kb_file" "$src_sha" >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi

body="$(cat "$kb_file")"
reason="Full read blocked by code-outline: $rel_path has $lines lines. Outline below (cached at .kb/files/$rel_path.md). Read only the sections you need with offset/limit. To read the whole file anyway, pass offset=1 and limit=$lines.

$body"

jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
