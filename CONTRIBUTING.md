# Contributing

Thank you for your interest in contributing to the Claude Code Plugins repository.

## Getting Started

1. Fork this repository
2. Create a new branch for your contribution
3. Make your changes following the guidelines below
4. Submit a pull request

## Creating a Plugin

### Directory Structure

Create your plugin under `plugins/`:

```text
plugins/your-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/
├── skills/
├── agents/
├── hooks/
│   └── hooks.json
└── .mcp.json (optional)
```

**Categories**: Classification lives in `marketplace.json` via the `category` field. Reuse an existing category (`ai`, `devex`, `security`, `devops`, etc.) when relevant, or introduce a new one if needed.

### Plugin Manifest

Every plugin requires a `plugin.json`:

```json
{
  "name": "your-plugin",
  "description": "Clear description of what your plugin does",
  "version": "1.0.0",
  "author": { "name": "Your Name" }
}
```

### Adding to Marketplace

After creating your plugin, add an entry to `marketplace.json` to make it discoverable.

## Commit Guidelines

This project follows [Conventional Commits](https://www.conventionalcommits.org/).

### Format

```text
<type>: <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature or plugin |
| `fix` | Bug fix (for released issues only) |
| `docs` | Documentation changes |
| `chore` | Maintenance tasks |
| `refactor` | Code changes that neither fix bugs nor add features |
| `test` | Adding or updating tests |

### Examples

```text
feat: add code-review plugin

docs: update README with installation instructions

fix: resolve hook execution order in linter plugin

chore: update marketplace.json schema
```

## Code Standards

- Keep plugins focused and single-purpose
- Include clear descriptions in your `plugin.json`
- Document commands and skills with helpful examples
- Test your plugin locally before submitting

## Pull Request Process

1. Ensure your plugin follows the directory structure
2. Verify your plugin works with `claude --plugin-dir /path/to/plugin`
3. Update `marketplace.json` if adding a new plugin
4. Use a descriptive PR title following conventional commits
5. Provide a clear description of what your plugin does

## Questions

If you have questions, open an issue or reach out through the project's communication channels.
