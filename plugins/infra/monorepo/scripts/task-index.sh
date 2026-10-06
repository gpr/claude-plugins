#!/usr/bin/env bash
# Prefetch the Taskfile task list so Claude doesn't re-run `task --list-all`
# every command. Runs on SessionStart (full) and UserPromptSubmit (--short).
# Exit 0 always — this is advisory context, not a gate.
set -euo pipefail

short=0
if [ "${1:-}" = "--short" ]; then
  short=1
fi

repo_root=""
if repo_root=$(git rev-parse --show-toplevel 2>/dev/null); then
  :
else
  repo_root="$PWD"
fi

if [ ! -f "$repo_root/Taskfile.yaml" ] && [ ! -f "$repo_root/Taskfile.yml" ]; then
  exit 0
fi

if ! command -v task >/dev/null 2>&1; then
  # shellcheck disable=SC2016  # backticks are Markdown formatting for human output
  printf 'monorepo: Taskfile present but `task` CLI not on PATH — install go-task to enable orchestration.\n' >&2
  exit 0
fi

if [ "$short" -eq 1 ]; then
  task --list 2>/dev/null | sed -n '1,40p' || true
else
  printf 'monorepo: available tasks (from Taskfile.yaml)\n'
  task --list-all 2>/dev/null || true
fi
exit 0
