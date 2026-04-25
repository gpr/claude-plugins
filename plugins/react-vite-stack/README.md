# react-vite-stack (Claude Code plugin)

Opinionated Claude Code plugin for: pnpm + Vite + React 19 + TS + TanStack Router/Query/Form + Zod + Zustand + shadcn/ui + Tailwind + Clerk + Vitest/RTL + Playwright.

## Install

Local (per-project, dev):
```
claude --plugin-dir ./react-vite-stack
```

Project scope (committed, team-shared) — copy or symlink this directory into your repo, then run Claude Code from the repo root.

User scope: add to a marketplace and `claude plugin install`.

## Prerequisites
- `typescript-language-server` on `$PATH`: `pnpm add -gD typescript-language-server typescript`
- Claude Code v2.1.105+ (for plugin monitors)
- pnpm 9+

At first run the plugin prompts for `api_base_url` and `clerk_publishable_key` via `userConfig`.

## What's in it

| Component | Count | Purpose |
|---|---|---|
| Skills | 10 | Per-library conventions; auto-invoked by relevance |
| Subagents | 4 | api-client-generator (opus), component-builder (sonnet), test-writer (haiku), reviewer (opus) |
| Hooks | 2 | SessionStart pnpm enforcement; PostToolUse format+lint on changed files |
| Monitors | 2 | tsc --watch, vitest --watch |
| LSP | 1 | typescript-language-server for navigation + diagnostics |

## What it deliberately does not include
- **No project-wide tsc on each edit** — the typecheck-watch monitor streams TS errors continuously instead. Per-edit tsc was 5–20s of dead time
- **No MCP server** — no stateful service worth one for this stack
- **No marketplace metadata** — add when ready to distribute

## Known issues
- **Plugin monitor auto-arm is broken on some Claude Code 2.1.x builds** (anthropics/claude-code#52245). If you don't see TypeScript or Vitest errors streaming after session start, ask Claude to manually arm them: "start the typecheck-watch and test-watch monitors"
- **`@clerk/clerk-react` is in long deprecation** — Clerk now publishes `@clerk/react`. Both still work; the `clerk-rest` skill detects which is in use and won't mix them. New projects should install `@clerk/react`

## Tuning

Disable a noisy monitor: edit `monitors/monitors.json` and remove the entry.

Skip the PostToolUse check temporarily: comment the matcher in `hooks/hooks.json`. Don't keep it disabled.

Bypass pnpm enforcement (polyglot repo): delete the `SessionStart` block from `hooks/hooks.json`.

Add a skill: drop a new `skills/<n>/SKILL.md`. Auto-discovered.
