# Contributing

Thank you for your interest in contributing to the Claude Code Plugins repository.

## Getting Started

1. Fork this repository
2. Create a new branch for your contribution
3. Make your changes following the guidelines below
4. Submit a pull request

## Creating a Plugin

### Directory Structure

Create your plugin under `plugins/<domain>/` (`backend`, `frontend`, `infra`, `meta`):

```text
plugins/<domain>/your-plugin/
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

After creating your plugin, add an entry to `marketplace.json` to make it discoverable, and register it in `cog.toml` under `[monorepo.packages]` (key = the `name` in `plugin.json`) so it gets versioned. The `version` in `plugin.json` is the plugin's first release.

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

### Versioning

Plugin versions and changelogs are automatic ([cocogitto](https://docs.cocogitto.io/)); never edit `version` in `plugin.json` or a plugin's `CHANGELOG.md` by hand. When a PR is squash-merged into `main`, a GitHub Action bumps every plugin whose directory the commit touched, commits the new `plugin.json` version and `CHANGELOG.md`, and tags `<plugin>-<version>`.

- `feat` bumps minor, `fix` and `perf` bump patch, `!` or a `BREAKING CHANGE:` footer bumps major.
- Other types (`refactor`, `docs`, `chore`, `test`, ...) do not bump.
- The PR title becomes the commit message, so it must be a valid conventional commit (checked by CI).
- A commit touching several plugins bumps each of them; split the PR if that is not what you want.
- Changes outside `plugins/` (root docs, workflows) never bump anything.

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
