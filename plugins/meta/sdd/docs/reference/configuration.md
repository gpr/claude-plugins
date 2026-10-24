---
type: Reference
title: Configuration
description: Keys of .claude/sdd.json with defaults, how sdd.py finds the project root, and the plugin's runtime requirements.
tags: [sdd, reference, configuration]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Configuration

## .claude/sdd.json

Created by `sdd init` with every key below except `req_id_pattern`; `sdd init key=value ...` sets the first values (in an existing repo, before the folders exist). Keys you omit take the default. `sdd config` prints the effective values.

| Key | Default | Used for |
|---|---|---|
| `specs_dir` | `specs` | the living specs OKF bundle ([layout](bundles.md)) |
| `changes_dir` | `changes` | open and archived changes |
| `adr_dir` | `adrs` | ADRs (an OKF bundle) |
| `acceptance_dir` | `tests/acceptance` | acceptance tests: coverage, freeze, guard |
| `acceptance_cmd` | `pytest -q {files}` | how agents run acceptance tests; `{files}` is the file list |
| `unit_cmd` | `pytest -q tests/unit` | how agents run the unit suite |
| `base_branch` | `""` | base for new changes; empty means the remote's default branch (`origin/HEAD`), else `main` |
| `branch_prefix` | `sdd/` | change branch name prefix |
| `worktree_dir` | `.claude/worktrees` | where change worktrees go |

`acceptance_cmd` and `unit_cmd` are read by the agents through `sdd config`; `sdd.py` itself never runs them. Set them for your stack, for example `"acceptance_cmd": "npx vitest run {files}"`.

The guard reads the four `*_dir` keys (trimmed, `./` and trailing `/` removed). An unreadable or invalid file falls back to the defaults.

## Project root

`sdd.py` looks from the cwd up to the enclosing git root, and takes the nearest directory that has:

1. `.claude/sdd.json`, else
2. a `changes/` or `specs/` directory, else
3. the git root (else the cwd).

Nothing above the git root counts. Inside a change worktree, the root is the worktree, so every `sdd` call acts on the change's branch.

## Requirements

| Need | For |
|---|---|
| Python 3.9+ as `python3` on PATH, no dependencies | everything |
| git, remote `origin`, `.claude/sdd.json` committed on the base branch | `start`, `checkpoint`, `resume`, `requires`, `deps`, `finish` |
| `gh`, authenticated | opening the draft PR (`start`), `resume --pr`, marking it ready (`finish`) |

## Plugin scope

Install the plugin at **project** scope. At user scope the guard would block hand edits to `specs/` and `adrs/` in every repo, and every session's main conversation would become the lead.
