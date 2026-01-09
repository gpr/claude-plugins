# Claude Code Plugins

A collection of plugins for [Claude Code](https://claude.ai/code), Anthropic's official CLI for Claude.

## Overview

This repository serves as a marketplace for Claude Code plugins. Plugins extend Claude Code's capabilities with custom commands, skills, agents, hooks, and MCP server integrations.

## Installation

Install plugins directly from this marketplace using Claude Code:

```bash
claude /install gpr/claude-plugins@plugin-name
```

Manage installed plugins:

```bash
# List and manage plugins
claude /plugins
```

## Plugin Structure

Each plugin follows this structure:

```text
<category>/plugin-name/
├── .claude-plugin/
│   └── plugin.json    # Plugin manifest
├── commands/          # Slash commands (Markdown)
├── skills/            # Auto-invoked skills (SKILL.md)
├── agents/            # Subagents (Markdown)
├── hooks/
│   └── hooks.json     # Lifecycle hooks
└── .mcp.json          # MCP server config (optional)
```

## Development

### Testing a Plugin

Load a plugin directly during development:

```bash
claude --plugin-dir /path/to/my-plugin
```

### Creating a Plugin

Use the guided plugin creation workflow:

```bash
claude /plugin-dev:create-plugin
```

## Documentation

- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
- [Create Plugins](https://code.claude.com/docs/en/plugins)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting plugins and contributing to this repository.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
