---
name: pnpm-only
description: Use when installing, removing, or running packages. Enforces pnpm in a project that explicitly forbids npm/yarn/bun.
---

# pnpm only

Use `pnpm` exclusively. Never run `npm`, `yarn`, or `bun` — they corrupt the lockfile and break the workspace.

## Commands
- Install: `pnpm add <pkg>` (runtime), `pnpm add -D <pkg>` (dev), `pnpm add -w <pkg>` (workspace root)
- Remove: `pnpm remove <pkg>`
- Run: `pnpm <script>` (no `run`), or `pnpm exec <bin>` for binaries
- Sync: `pnpm install --frozen-lockfile` in CI; plain `pnpm install` locally

## Rules
- Never edit `pnpm-lock.yaml` by hand
- If `package-lock.json`, `yarn.lock`, or `bun.lockb` appears, delete it before continuing
- Add `"packageManager": "pnpm@<version>"` to `package.json` if missing — without it, Corepack won't pin
- Use `pnpm dlx` (not `npx`) for one-off binaries
