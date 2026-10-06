# documentalist-agent

Claude Code plugin. Runs a `documentalist` agent in the background. Other agents ask it questions about the codebase instead of exploring it themselves. It keeps an OKF v0.2 knowledge bundle in `.kb/`.

## Install

```
/plugin marketplace add <path-or-repo>
/plugin install documentalist-agent@gpr-plugins
```

Local test: `claude --plugin-dir ./plugins/meta/documentalist-agent`

## Use

1. Start it: `/documentalist-agent:start`
2. Ask it: `SendMessage({to: "documentalist", message: "Where is auth handled?"})`

Two hooks in `hooks/hooks.json` run `hooks/inject-instructions.sh`. Requires `jq`.

- `SessionStart` (matcher `compact`): replays the instructions to the main session after context compaction.
- `SubagentStart`: tells every subagent (built-in and custom, except the documentalist) to ask the documentalist before exploring files. Subagents do not start it; they explore themselves if it is not running.

Limits:

- A subagent can act on the hint only if its tool list includes `SendMessage` and `ListAgents`. Custom agents with a restricted `tools:` list must add them.
- Subagents spawned before `/documentalist-agent:start` find no documentalist and explore themselves.

It answers with `path:line` evidence and updates `.kb/` (`index.md`, `catalog.md`, `log.md`, concepts). It never edits source code.

## Suggested CLAUDE.md snippet

```
For questions about the codebase, send them to the `documentalist` agent with SendMessage before exploring files yourself. Start it with /documentalist-agent:start if it is not running.
```
