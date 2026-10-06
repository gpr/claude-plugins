---
description: List Taskfile tasks and run one
argument-hint: [task-name]
allowed-tools: Bash, Read, Grep
---

Help the user run a task from the monorepo's `Taskfile.yaml`.

Load the `taskfile-orchestration` skill if it is not already in context.

## If $ARGUMENTS is provided

1. Run `task --summary $ARGUMENTS` first to confirm the task exists and show what it will do.
2. If the task does not exist, run `task --list-all`, identify the closest match, and ask before running anything.
3. Otherwise, run `task $ARGUMENTS` and stream output back.

## If $ARGUMENTS is empty

1. Run `task --list-all`.
2. Group results by namespace (`frontend:`, `website:`, each `<backend>:`, `release:`, top-level).
3. Present the grouped list and ask which task to run.

## Pre-flight for state-changing tasks

Before running anything matching `release:*`, `*:migrate`, `*:reset`, `*:deploy`, `*:rollback`, or anything containing `db:`:

1. Confirm the working tree state with `git status --short`.
2. Tell the user what the task will do (from `task --summary`).
3. Ask for explicit confirmation before invoking.

Do not bypass `cog verify` or other pre-task hooks defined in `Taskfile.yaml`.
