# monorepo

Orchestration plugin for monorepos that follow this layout:

- `frontend/` — React + TypeScript + Vite + pnpm
- `website/` — React + TypeScript + Vite + pnpm
- `backends/<name>/` — Rails API (one or more)
- `Taskfile.yaml` — central task runner ([go-task](https://taskfile.dev))
- `cog.toml` — [cocogito](https://docs.cocogitto.io) for conventional commits, versioning, and changelog

This plugin handles the **monorepo layer**: cross-package orchestration, versioning, commit hygiene, and Claude memory across the repo. Stack-specific work (React patterns, Rails generators) is left to dedicated frontend / backend plugins.

## Skills

- **monorepo-memory** — manage `CLAUDE.md` files across the repo; decide what lives at root vs per-package; audit for staleness and duplication.
- **monorepo-layout** — canonical structure as ground truth.
- **taskfile-orchestration** — read, run, and extend `Taskfile.yaml`.
- **cog-versioning** — conventional commits, bumping, changelog generation.

## Commands

- `/run-task [name]` — list and run Taskfile tasks.
- `/commit [context]` — draft a conventional-commit message that `cog verify` accepts.
- `/release [auto|patch|minor|major]` — full release flow: bump → changelog → tag → push.
- `/changelog [range]` — regenerate `CHANGELOG.md` without bumping.
- `/scaffold-backend <name>` — wire a new `backends/<name>/` into the monorepo (Taskfile + root config; does not generate Rails).
- `/onboard [role]` — orientation tailored to frontend / backend / fullstack / new contributor.

## Prerequisites

- [`task`](https://taskfile.dev) (go-task)
- [`cog`](https://docs.cocogitto.io) (cocogito)
- `git`, `pnpm`, `bundle` per package as relevant

## Companion plugins

This plugin deliberately does not know React or Rails. Pair it with a frontend plugin and a backend plugin for stack-specific work. The split:

| Concern | Plugin |
|---|---|
| Repo layout, Taskfile, releases, commits, memory | this plugin |
| React patterns, pnpm workflows, Vite config, frontend tests | your frontend plugin |
| Rails generators, RSpec, migrations, API conventions | your backend plugin |

`/scaffold-backend` here only handles the *wiring* (Taskfile entries, root config, stub `CLAUDE.md`). The Rails generation step is the backend plugin's job.
