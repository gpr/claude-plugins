---
description: Print a monorepo orientation summary tailored to role
argument-hint: [frontend|backend|fullstack|new]
allowed-tools: Read, Glob, Bash
---

Give the user a monorepo orientation.

Load the `monorepo-layout` skill before starting.

## Steps

1. Read root `CLAUDE.md` (if it exists), `Taskfile.yaml`, and `cog.toml` (if it exists).
2. Enumerate the packages: `frontend/`, `website/`, every entry under `backends/` (use Glob).
3. Run `task --list` and capture the documented tasks.
4. Tailor the summary to $ARGUMENTS:
   - `frontend` → focus on `frontend/` and `website/`, pnpm/Vite tooling, the `frontend:*` and `website:*` tasks.
   - `backend` → focus on `backends/*`, Rails-specific tasks (`<name>:test`, `<name>:migrate`, etc.).
   - `fullstack` → cover all packages at high level.
   - `new` (or empty) → start with the layout, then the three commands they will use most: `task --list`, `/commit`, `/release`. Then pointers to per-package `CLAUDE.md`.

## Output rules

- Keep the summary under 30 lines.
- Lead with the layout, then conventions, then daily commands.
- Link, do not paste. End with: "Read each package's `CLAUDE.md` for stack-specific conventions."
- Do not invent tasks or packages — only mention what `task --list` and `Glob` actually surfaced.
