# python-uv-project plugin

Hook-based Claude Code plugin that provides an opinionated Python development environment for uv-managed projects: auto-formatting (ruff), auto-linting, auto-testing with coverage gating, security scanning (bandit), and Pyright LSP integration.

## Architecture

All automation runs through bash hook scripts orchestrated by `hooks/hooks.json`:

- `scripts/_lib.sh` — shared library sourced by every script; exports `read_hook_input`, `init_tool_runner`, `find_project_root`, `find_workspace_root`, `build_run_cmd`, `find_test_file`, `report_block`, `report_error`
- `scripts/setup.sh` — SessionStart: installs mise/uv, runs `uv sync`
- `scripts/advisory.sh` — SessionStart: reports missing dev tools and config suggestions
- `scripts/ruff-format-lint.sh` — PostToolUse (Write|Edit `.py`): ruff format + check --fix
- `scripts/auto-test.sh` — PostToolUse (Write|Edit `.py`): smart test scoping via `git diff`, coverage gating on changed lines
- `scripts/bandit.sh` — PostToolUse (Write|Edit `.py`): security scanning
- `scripts/prettier-format.sh` — PostToolUse (Write|Edit `.md`/`.json`/`.yaml`): prettier formatting
- `scripts/dep-audit.sh` — PostToolUse (Bash `uv add`/`pip install`): dependency auditing
- `scripts/load-env.sh` — CwdChanged: loads direnv or `.env`

Skills (guidance only, no actions):

- `skills/lsp/SKILL.md` — Pyright LSP-first code navigation decision matrix
- `skills/python-project-standards/SKILL.md` — uv/pytest/ruff project setup standards

## Development Conventions

- Every script must start with `set -euo pipefail` and `source "$(dirname "$0")/_lib.sh"`
- Use `${CLAUDE_PLUGIN_ROOT}` to reference plugin resources (scripts, hooks, skills)
- Use `report_block()` for structured hook feedback (exit 0) and `report_error()` for failures (exit 2)
- Hook scripts receive input on stdin as JSON; use `read_hook_input` to extract `file_path`
- Monorepo-aware: `find_workspace_root()` detects `[tool.uv.workspace]` in ancestor `pyproject.toml`

## Validation

```bash
# Validate plugin manifest
python3 -m json.tool .claude-plugin/plugin.json > /dev/null

# Validate hooks JSON
python3 -m json.tool hooks/hooks.json > /dev/null

# Test a script against a uv project
cd /path/to/uv-project && bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh
```

## Documentation

Fetch Claude Code plugin docs only when modifying hook/skill/plugin structure or when the API is uncertain:

- [Plugins](https://code.claude.com/docs/en/plugins.md)
- [Hooks](https://code.claude.com/docs/en/hooks.md)
- [Skills](https://code.claude.com/docs/en/skills.md)
- [Subagents](https://code.claude.com/docs/en/subagents.md)
