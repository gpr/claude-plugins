---
description: Wire a new backends/<name>/ entry into the monorepo (Taskfile + root config). Does not generate Rails code — that belongs to the dedicated backend plugin.
argument-hint: <backend-name>
allowed-tools: Read, Write, Edit, Bash, Glob
---

Wire a new backend at `backends/$ARGUMENTS/` into the monorepo.

Load the `monorepo-layout` and `taskfile-orchestration` skills before starting.

## Validate

1. If $ARGUMENTS is empty, ask for the backend name. Require kebab-case, descriptive, no spaces or special characters.
2. List existing entries in `backends/`. If the name conflicts with an existing directory, stop and ask.
3. Confirm the working tree is clean: `git status --porcelain`. Recommend committing pending work first so the scaffolding diff is isolated.

## Wiring (this plugin's job)

4. Create the `backends/<name>/` directory if it does not exist.
5. Create `backends/<name>/CLAUDE.md` with this stub:

   ```markdown
   # <name>

   Rails API backend.

   ## Conventions

   <fill in as the backend takes shape — endpoints, auth model, persistence, tests>

   ## Useful commands

   - `task <name>:install` — install gems
   - `task <name>:migrate` — run migrations
   - `task <name>:test` — run RSpec
   - `task <name>:console` — Rails console
   - `task <name>:server` — Rails server
   ```

6. Read `Taskfile.yaml`. Add the namespaced tasks listed in the `taskfile-orchestration` skill: `<name>:install`, `<name>:migrate`, `<name>:test`, `<name>:console`, `<name>:server`. Match the existing style (`dir:`, `desc:`, etc.).
7. Add `<name>:test` to the top-level `test:` task's `deps:` (create the top-level `test:` task if it doesn't exist yet).
8. Add `<name>:install` to the top-level `setup:` task's `deps:` (same).
9. Update root `CLAUDE.md` to mention the new backend in its layout section.
10. Show the user the full diff (`git diff`) before they commit anything. Recommend `/commit` with a `feat(<name>): scaffold backend wiring` message.

## Out of scope — explicit

This command does **not**:

- Run `rails new` or generate any Rails code.
- Add gems, configure databases, or touch Ruby version files.
- Create routes, controllers, or specs.

That is the dedicated backend plugin's job. After wiring is in place, hand off to it. If the user expected Rails generation here, point them to the backend plugin and explain the split.
