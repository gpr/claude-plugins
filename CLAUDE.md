# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository is for developing Claude Code plugins. Use the `/plugin-dev:create-plugin` skill for guided plugin creation.

**Important**:
- Create each new plugin under `plugins/<plugin-name>/`. Set `category` in `marketplace.json` (e.g. `ai`, `devex`, `security`) for classification; reuse an existing category when relevant
- After creating a new plugin, add it to `marketplace.json` to make it available in the marketplace
- After creating or modifying a plugin, review it with `@agent-plugin-dev:plugin-validator`
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for all git commits (`feat`/`fix`/`refactor`/`perf` for production; `chore`/`test`/`docs` otherwise). Use `fix` only for released issues; use `refactor` for pre-release bugs.
- Plugins may carry their own `CLAUDE.md` for plugin-specific rules (see `plugins/rails/CLAUDE.md`). Parent context auto-loads.

## Plugin Architecture

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json    # Plugin manifest (only manifest goes here)
├── commands/          # Slash commands (Markdown files)
├── skills/            # Model-invoked skills (directories with SKILL.md)
├── agents/            # Subagents (Markdown files)
├── hooks/
│   └── hooks.json     # Hook definitions
├── scripts/           # Shell scripts invoked by hooks (optional)
├── monitors/
│   └── monitors.json  # Background monitors (optional, ≥ v2.1.105)
└── .mcp.json          # MCP server configuration (optional)
```

## Plugin Manifest (plugin.json)

```json
{
  "name": "plugin-name",
  "description": "What this plugin does",
  "version": "1.0.0",
  "author": { "name": "Your Name" }
}
```

## Development Commands

```bash
# Test plugin during development (loads directly without installation)
claude --plugin-dir /path/to/my-plugin

# Install from marketplace
claude /install marketplace-name@plugin-name

# Enable/disable plugins via settings or /plugins command
```

## Validation

After any plugin change, run:

1. `jq . .claude-plugin/plugin.json hooks/hooks.json monitors/monitors.json .mcp.json 2>/dev/null` — JSON syntax (skip files that don't exist)
2. `shellcheck scripts/*.sh` — shell scripts (if any)
3. `@agent-plugin-dev:plugin-validator` — manifest + component wiring
4. `/plugin-auditor:audit-plugin <plugin-path>` — prompt-engineering and doc-alignment audit

Use `${CLAUDE_PLUGIN_ROOT}` for all script paths in hooks/MCP config. Never hardcode absolute paths.

## Plugin Components

- **Commands**: Markdown files in `commands/`. Filename becomes `/plugin-name:command-name`
- **Skills**: Directories in `skills/` containing `SKILL.md` with YAML frontmatter. Claude autonomously decides when to invoke them
- **Agents**: Markdown files in `agents/` that define specialized subagents with tool access
- **Hooks**: JSON definitions in `hooks/hooks.json` that run shell commands at lifecycle events (PreToolUse, PostToolUse, Stop, SessionStart, etc.)
- **MCP Servers**: Defined in `.mcp.json` or inline in `plugin.json`. Start automatically when plugin is enabled

## Hook Events

PreToolUse, PostToolUse, PostToolUseFailure, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification, PermissionRequest, FileChanged, WorktreeCreate, WorktreeRemove

## Reference

- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference.md)
- [Create Plugins](https://code.claude.com/docs/en/plugins.md)
- [Hooks Documentation](https://code.claude.com/docs/en/hooks.md)
- [Skill Documentation](https://code.claude.com/docs/en/skills.md)
- [Sub-Agents Documentation](https://code.claude.com/docs/en/sub-agents.md)

## Critical: source code vs. instructions

Every `*.md`, `hooks.json`, `monitors.json`, and `*.sh` file in `plugins/` is **payload shipped to end users**. Treat them as source code to edit, lint, and review.

## Tips

- `@agent-plugin-dev:plugin-validator` knows the docs at training time only. For new fields (`FileChanged`, monitor `when:`, agent `isolation: "worktree"`), cross-check `code.claude.com/docs/en/plugins-reference.md` via WebFetch before treating its findings as blocking.
- To split a working tree where audit fixes and new features touch the same files (`hooks.json`, `monitors.json`, `CLAUDE.md`), prefer `git add -p` over snapshot/revert dance — picks lines, no scratch files needed.

## Sandbox gotchas

- `cp`, `git checkout`, and direct file writes outside `Edit`/`Write` typically fail with "Operation not permitted" — re-run with `dangerouslyDisableSandbox: true`.
- `$TMPDIR` is not stable across Bash invocations in sandbox mode. Don't snapshot state to a temp file in one call and read it from another.
