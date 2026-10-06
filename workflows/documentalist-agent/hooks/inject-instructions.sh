#!/usr/bin/env bash
# SessionStart(compact) and SubagentStart hook: tell agents to ask the documentalist about the codebase.
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "documentalist-agent: 'jq' is required by hooks/inject-instructions.sh. Install jq." >&2
  exit 1
fi

input=$(cat)
agent_type=$(jq -r '.agent_type // empty' <<<"$input")
event=$(jq -r '.hook_event_name // empty' <<<"$input")

case "$agent_type" in
  documentalist | *:documentalist)
    exit 0
    ;;
esac

case "$event" in
  SubagentStart)
    msg='For codebase questions, ask the `documentalist` agent with `SendMessage({to: "documentalist", message: "<question>"})` before you explore files. Call ListAgents to check it is running. If it is not running, explore the files yourself; do not start it.'
    ;;
  SessionStart)
    msg='Context was compacted. For codebase questions, ask the `documentalist` agent with `SendMessage({to: "documentalist", message: "<question>"})` before you explore files. Call ListAgents to check it is running; if not, start it with /documentalist-agent:start.'
    ;;
  *)
    echo "documentalist-agent: unexpected hook_event_name '$event' in hooks/inject-instructions.sh." >&2
    exit 1
    ;;
esac

jq -n --arg event "$event" --arg ctx "$msg" '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}'
