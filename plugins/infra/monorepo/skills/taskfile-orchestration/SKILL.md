---
name: taskfile-orchestration
description: Covers reading and using the central Taskfile.yaml (go-task) that orchestrates this monorepo. Handles listing available tasks, running tasks, adding tasks, understanding what a task does, and wiring new packages into the task runner. Trigger phrases include "task", "Taskfile", "run task", "task list", "go-task", "what tasks are available", "add a task".
---

The repo uses [go-task](https://taskfile.dev) (`task` CLI). The single source of truth is `Taskfile.yaml` at the repo root.

## Listing and running

- List all tasks: `task --list-all`
- List documented tasks only: `task --list`
- Run a task: `task <name>`
- Show a task's commands without running: `task --summary <name>`
- Dry run: `task --dry <name>`

Always read `Taskfile.yaml` before claiming a task does or does not exist. Do not invent task names.

## Namespacing

Tasks follow a `<package>:<verb>` pattern:

- `frontend:dev`, `frontend:build`, `frontend:test`, `frontend:lint`, `frontend:typecheck`
- `website:dev`, `website:build`, `website:lint`
- `<backend>:test`, `<backend>:migrate`, `<backend>:console`, `<backend>:server`, `<backend>:install`
- `release:bump`, `release:changelog`, `release:tag`
- `commit:verify` (runs `cog verify`)

Top-level convenience tasks (no namespace) are reserved for cross-cutting workflows: `setup`, `test` (runs all package tests), `lint` (runs all linters), `release`.

## Adding a task

1. Read `Taskfile.yaml` to confirm the namespace pattern in use.
2. Add the task under the matching namespace, with a one-line `desc:` so it shows up in `--list`.
3. Prefer composing existing tasks (`deps:`) over inlining shell.
4. Use `dir:` to scope a task to a package directory rather than `cd`-ing in `cmds:`.

Example shape:

```yaml
auth:test:
  desc: Run RSpec for the auth backend
  dir: backends/auth
  cmds:
    - bundle exec rspec
```

## Wiring a new backend

When a new `backends/<name>/` is added, register at minimum:

- `<name>:install` — `bundle install`
- `<name>:migrate` — `bundle exec rails db:migrate`
- `<name>:test` — `bundle exec rspec`
- `<name>:console` — `bundle exec rails console`
- `<name>:server` — `bundle exec rails s`

Then add `<name>:test` to the top-level `test:` task's `deps:` so `task test` covers it. Do the same for `<name>:install` under `setup:`.

## Common patterns

- **Variables:** prefer `vars:` blocks at the top of `Taskfile.yaml` for shared values (e.g. node version, ruby version).
- **Environment:** put `.env` loading via `dotenv:` at task level, not global, so secrets don't leak across packages.
- **Sources / generates:** use `sources:` and `generates:` for build tasks so go-task can skip when inputs haven't changed.
- **Silent:** add `silent: true` to noisy tasks; let `cmds:` produce the signal.
