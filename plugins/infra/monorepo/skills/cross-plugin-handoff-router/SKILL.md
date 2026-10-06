---
name: cross-plugin-handoff-router
description: Routes stack-specific work in this monorepo to the dedicated companion plugins (`react-vite-stack` for frontend/website, `rails` for backends/<name>) instead of answering inside the orchestration plugin. Trigger phrases include "scaffold a route", "add a Rails controller", "generate a migration", "new component", "Vite config", "RSpec test", "shadcn", "TanStack", "ActiveRecord", "Sidekiq".
---

This plugin owns orchestration only — Taskfile, cocogito, memory layout. Stack-specific work belongs to companion plugins. When a request crosses that boundary, name the right destination and stop.

## Routing table

| Request shape | Hand off to |
|---|---|
| React route, component, hook, form, store, shadcn/Tailwind, TanStack Router/Query/Form, Vitest, Playwright, Vite config | `@agent-react-vite-stack:component-builder`, `@agent-react-vite-stack:api-client-generator`, `@agent-react-vite-stack:test-writer`, `@agent-react-vite-stack:reviewer`, or relevant `react-vite-stack` skill |
| Marketing site (`website/`) — same React stack | same as above; `react-vite-stack` covers both `frontend/` and `website/` |
| Rails controller, model, migration, route, RSpec, Sidekiq, ActiveRecord, deployment to Render | `@agent-rails:rails-backend`, `/rails:rails-console`, or relevant `rails` skill (`rails-api-conventions`, `rails-migrations`, `rails-routes`, `rails-test-impact`, `rails-render-deploy`) |
| Cross-package release, version bump, conventional commit policy | stay here — load `cog-versioning` or invoke `release-orchestrator` |
| Taskfile authoring, new task, wiring a backend into `task test` | stay here — load `taskfile-orchestration` |
| CLAUDE.md placement, memory hygiene | stay here — load `monorepo-memory` |
| Where a file should go in the repo | stay here — load `monorepo-layout` |

## How to hand off

1. Identify the package (`frontend/`, `website/`, `backends/<name>/`).
2. Name the companion plugin component explicitly (e.g. "use `@agent-react-vite-stack:component-builder` to scaffold this route").
3. Provide the working directory the companion will need (e.g. "run from `backends/auth/`").
4. Do not duplicate stack-specific knowledge here. If the user pushes for an answer this plugin should not give, redirect once more and stop.

## Hard rules

- Never embed React, Rails, or Vite specifics in this plugin's skills, agents, or commands.
- Never invent a companion-plugin component name. If the listed agents/skills do not match the request, say so and let the user pick.
- If neither companion plugin is installed, surface that — do not silently absorb the request.
