# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository is for developing Claude Code plugins. Use the `/plugin-dev:create-plugin` skill for guided plugin creation.

**Important**:
- Create each new plugin under `plugins/<domain>/<plugin-name>/`. The domain directory equals the `category` in `marketplace.json` (`backend`, `frontend`, `infra`, `meta`); add a new domain only when none fits
- After creating a new plugin, add it to `marketplace.json` to make it available in the marketplace, and to `cog.toml` `[monorepo.packages]` (key = plugin.json `name`) so it gets versioned. Check with `scripts/release/check-registry.sh`
- Never hand-edit `version` in `plugin.json` or any plugin `CHANGELOG.md`; see [Versioning](#versioning)
- After creating or modifying a plugin, review it with `@agent-plugin-dev:plugin-validator`
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for all git commits (`feat`/`fix`/`refactor`/`perf` for production; `chore`/`test`/`docs` otherwise). Use `fix` only for released issues; use `refactor` for pre-release bugs.
- Plugins may carry their own `CLAUDE.md` for plugin-specific rules (see `plugins/backend/rails/CLAUDE.md`). Parent context auto-loads.

## Plugin Architecture

```
plugins/<domain>/<plugin-name>/
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

## Versioning

Each plugin is versioned independently by cocogitto (`cog.toml`, workflows in `.github/workflows/`). On every push to `main`, `release.yml` runs `cog bump --auto`: for each plugin whose directory changed since its last `<plugin>-<version>` tag it computes the bump from the conventional commits, rewrites `plugin.json` `version`, writes `<plugin>/CHANGELOG.md`, commits, tags and pushes.

- `feat` → minor; `fix`/`perf` → patch; `!` or `BREAKING CHANGE:` → major; `refactor`/`docs`/`chore`/`test` → no bump. Commit scope is cosmetic, bumping follows the touched paths.
- PRs are squash-merged: the PR title is the commit cog reads, and `pr-checks.yml` runs `cog verify` on it.
- Because only `feat`/`fix`/`perf` release, use `refactor` (not `fix`) for pre-release bugs, as above.
- Local dry run: `cog bump --auto --dry-run` (needs cocogitto 7.x; tags come from `git fetch --tags`).
- CI pins `cocogitto-action@v4.2.0` (installs cog 7.0.0) and fails unless `cog --version` is 7.x. Don't use the floating `v4` tag: it installs 6.x, which can't read `[monorepo.packages]`.
- A repo ruleset rejects pushes updating more than 5 refs, so `scripts/release/push-tags.sh` pushes new tags in batches of 5.
- The release workflow pushes to `main` with `GITHUB_TOKEN`; if `main` ever requires PRs, give the Actions bot a ruleset bypass.
- `GITHUB_TOKEN` cannot get the `workflows` permission, so GitHub rejects any new tag whose `.github/workflows/` differs from `main`. `bootstrap-tags.sh` therefore never seeds tags on a commit older than the last workflow change.

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

- `@agent-plugin-dev:plugin-validator` knows the docs at training time only. For new fields (`FileChanged`, monitor `when:`, agent `isolation: "worktree"`), cross-check `code.claude.com/docs/en/plugins-reference.md` via WebFetch — or delegate to `@agent-docs-cross-checker` (in `.claude/agents/`) — before treating its findings as blocking.
- To split a working tree where audit fixes and new features touch the same files (`hooks.json`, `monitors.json`, `CLAUDE.md`), use `git add -p` for per-hunk staging. Avoid snapshotting state to `$TMPDIR` — it is not stable across sandboxed Bash calls.

## Sandbox gotchas

- `cp`, `git checkout`, and direct file writes outside `Edit`/`Write` typically fail with "Operation not permitted" — re-run with `dangerouslyDisableSandbox: true`.
- `$TMPDIR` is not stable across Bash invocations in sandbox mode. Don't snapshot state to a temp file in one call and read it from another.
