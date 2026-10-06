---
name: python-project-standards
description: >
  Python project standards using uv, pytest, prek, ruff, and mise.
  Use for GUIDANCE on project init, linting, formatting, and test config.
  Triggers on "new python project", "add ruff", "setup pytest", "python standards".
paths: "pyproject.toml, requirements.txt, setup.py, **/*.py"
---

# Python Project Standards

Apply these standards when working on Python projects.

## Required Tooling

| Concern                   | Tool         | Notes                                |
| ------------------------- | ------------ | ------------------------------------ |
| Python runtime management | `mise`       | Development environment management   |
| Package management        | `uv`         | Fast, reliable dependency resolution |
| Testing                   | `pytest`     | With `pytest-cov` for coverage       |
| Git hooks                 | `prek`       | Git hooks manager (wraps pre-commit) |
| Linting & formatting      | `ruff`       | Single tool for both                 |

### Guidelines

- Use type hints for all function signatures
- Aim for test coverage on critical paths
- Use `pyproject.toml` for project configuration (not `setup.py`)
- Prefer `uv` over `pip` for all dependency operations
- Execute any commands with `uv run <command>` to ensure they run in the correct environment

### Project Setup Commands

When initializing a new Python project:

```bash
# Initialize with uv
uv init

# Add dev dependencies
uv add --dev pytest pytest-cov ruff prek bandit

# Initialize prek
uv run prek install
```

### Configuration Templates

#### pyproject.toml (ruff section)

```toml
[tool.ruff]
line-length = 88
target-version = "py312"  # Adjust to match project's minimum Python version

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.ruff.lint.isort]
force-sort-within-sections = true
known-first-party = ["src"]  # Adjust to match project's package name
```

#### .pre-commit-config.yaml (used by prek)

`prek` manages git hooks using `.pre-commit-config.yaml`. Look up the current stable version of `ruff-pre-commit` before using this template — do not assume the `rev` value below is current.

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <look-up-current-version>
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

## Verification

After applying these standards, confirm:

1. `uv run pytest` runs successfully (even if no tests exist yet, the runner should initialize)
2. `uv run ruff check .` passes with no errors
3. `uv run ruff format --check .` shows no formatting changes needed
4. `uv run prek run --all-files` passes all hooks
5. `pyproject.toml` contains `[tool.ruff]` configuration

## Example

**Scenario**: Existing Python project with `requirements.txt` and no linting.

1. `uv init` (creates `pyproject.toml` if missing)
2. `uv add --dev pytest pytest-cov ruff prek`
3. Add `[tool.ruff]` section to `pyproject.toml`
4. Create `.pre-commit-config.yaml` with ruff hooks
5. `uv runprek install`
6. `uv run ruff check . --fix` to auto-fix existing issues
7. `uv run ruff format .` to format the codebase
8. Commit the configuration files

## Notes

- `target-version` in ruff config should match the project's minimum supported Python version, not the developer's local version
- `ruff` replaces both `black` (formatting) and `flake8`+`isort` (linting) — do not install those separately
- If the project already uses `black` or `flake8`, migrate to `ruff` rather than running both
- For monorepos, place the ruff config in the root `pyproject.toml` and use `extend` in subdirectories if needed
- `prek` hook versions must be pinned — always look up the current stable version rather than using a remembered value
