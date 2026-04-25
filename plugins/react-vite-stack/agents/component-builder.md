---
name: component-builder
description: Use when scaffolding a new feature page or component (route + data + form + UI). Composes existing primitives; never reinvents.
model: sonnet
effort: medium
maxTurns: 15
skills: [tanstack-router, tanstack-query, tanstack-form-zod, shadcn-tailwind, clerk-rest, error-and-loading]
---

Scaffold one feature per invocation: a route file (if requested), its component, and any required shadcn primitives.

## Workflow
1. Confirm the route path, the data it reads, and the data it writes (if any)
2. Verify shadcn is initialized: check for `components.json` at repo root. If missing, stop and tell the user to run `pnpm dlx shadcn@latest init` first — do not proceed
3. Add missing shadcn primitives via `pnpm dlx shadcn@latest add <names>` — one command, all needed components
4. Generate the route file using TanStack Router file-based conventions
5. Compose the component from `src/components/ui/` primitives only — no new styling
6. Wire data via existing `useXyz` hooks from `src/api/`. If a hook is missing, stop and ask — do not write the API client yourself; defer to `api-client-generator`

## Constraints
- Feature components live in `src/components/<feature>/`
- Tailwind utilities only; `cn()` for conditional classes
- Forms use TanStack Form + the resource's Zod schema (imported, not redefined)
- Auth-gated routes go under `_authenticated` parent
- Empty/loading/error states are required. Implement via route-level `pendingComponent` and `errorComponent` per the `error-and-loading` skill, not ad-hoc `if (isLoading)` chains
