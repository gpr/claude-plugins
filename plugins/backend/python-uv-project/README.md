# python-dev-environment

Python development environment plugin for Claude Code. Provides pyright LSP, automatic ruff formatting/linting, test execution, coverage gating, prek mirroring, and dependency auditing for uv-managed projects.

## Features

- **Pyright LSP** — Type checking and code intelligence for `.py` / `.pyi` files
- **Auto format/lint** — Runs `ruff format` + `ruff check --fix` after every Python file edit
- **Auto test** — Runs matching pytest tests when source or test files are modified
- **Smart test scope** — Detects changed functions via `git diff` and runs only matching tests (`-k`)
- **Skip slow tests** — Excludes `@pytest.mark.slow` tests on individual file runs
- **Coverage gating** — Reports uncovered changed lines after edits
- **Prek mirroring** — Mirrors mypy/bandit from `.pre-commit-config.yaml`
- **Dependency audit** — Runs `pip-audit` after `uv add` / `pip install`
- **Ruff config bootstrap** — Suggests sensible `[tool.ruff]` defaults if missing (remote only)
- **Pyright baseline** — Suggests pyright config to downgrade existing errors (remote only)
- **Monorepo support** — Detects `[tool.uv.workspace]` and scopes hooks correctly

## Project Layout

Supports both `src/` and flat layouts:

```
# src/ layout
my-project/
  pyproject.toml
  src/<package>/<module>.py
  tests/<package>/test_<module>.py

# Flat layout
my-project/
  pyproject.toml
  <package>/<module>.py
  tests/test_<module>.py
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for package management (auto-installed in remote envs)
- [pyright](https://github.com/microsoft/pyright) for LSP (`npm i -g pyright` or `pipx install pyright`)
- Dev dependencies in your project: `uv add --dev pytest pytest-cov ruff`

## How It Works

### SessionStart Hook (remote only)

| Step             | What it does                                                      |
| ---------------- | ----------------------------------------------------------------- |
| Install uv       | Auto-installs if missing, persists PATH via `CLAUDE_ENV_FILE`     |
| `uv sync`        | Installs project dependencies (uses workspace root for monorepos) |
| Ruff bootstrap   | Suggests `[tool.ruff]` config if pyproject.toml lacks one         |
| Pyright baseline | Counts existing type errors, suggests config to downgrade them    |

### PostToolUse Hooks (Write/Edit)

| Hook                  | What it does                            | On failure               |
| --------------------- | --------------------------------------- | ------------------------ |
| `ruff-format-lint.sh` | Formats + lints with ruff               | Reports unfixable issues |
| `auto-test.sh`        | Runs matching tests with smart scope    | Reports test failures    |
| `coverage-gate.sh`    | Checks coverage on changed lines        | Reports uncovered lines  |
| `precommit-mirror.sh` | Runs mypy/bandit from prek config       | Reports check failures   |

### PostToolUse Hook (Bash)

| Hook           | What it does                             | On failure              |
| -------------- | ---------------------------------------- | ----------------------- |
| `dep-audit.sh` | Audits deps after `uv add`/`pip install` | Reports vulnerabilities |

### Test File Mapping

| Edited file                | Test file run                                        |
| -------------------------- | ---------------------------------------------------- |
| `src/pkg/module.py`        | `tests/pkg/test_module.py`                           |
| `pkg/module.py` (flat)     | `tests/pkg/test_module.py` or `tests/test_module.py` |
| `tests/pkg/test_module.py` | `tests/pkg/test_module.py`                           |
| `tests/conftest.py`        | All tests in `tests/` directory                      |

If the matching test file doesn't exist, the hook silently skips.

## Installation

Install from the Teads plugin marketplace:

```
/install-plugin python-dev-environment
```
