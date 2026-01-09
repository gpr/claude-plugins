# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository is for developing Claude Code plugins. Use the `/plugin-dev:create-plugin` skill for guided plugin creation.

**Important**:
- Create each new plugin in a category subdirectory (ex: `ai/`, `devex/`, `security/`). Use the plugin description to define the category, use existing one when relevant
- After creating a new plugin, add it to `marketplace.json` to make it available in the marketplace
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for all git commits (e.g., `feat:`, `fix:`, `docs:`, `chore:`). `fix`is only for released issue.

## Plugin Architecture

```
<category>/my-plugin/
├── .claude-plugin/
│   └── plugin.json    # Plugin manifest (only manifest goes here)
├── commands/          # Slash commands (Markdown files)
├── skills/            # Model-invoked skills (directories with SKILL.md)
├── agents/            # Subagents (Markdown files)
├── hooks/
│   └── hooks.json     # Hook definitions
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

## Plugin Components

- **Commands**: Markdown files in `commands/`. Filename becomes `/plugin-name:command-name`
- **Skills**: Directories in `skills/` containing `SKILL.md` with YAML frontmatter. Claude autonomously decides when to invoke them
- **Agents**: Markdown files in `agents/` that define specialized subagents with tool access
- **Hooks**: JSON definitions in `hooks/hooks.json` that run shell commands at lifecycle events (PreToolUse, PostToolUse, Stop, SessionStart, etc.)
- **MCP Servers**: Defined in `.mcp.json` or inline in `plugin.json`. Start automatically when plugin is enabled

## Hook Events

PreToolUse, PostToolUse, PostToolUseFailure, Stop, SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification, PermissionRequest

## Reference

- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
- [Create Plugins](https://code.claude.com/docs/en/plugins)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)
