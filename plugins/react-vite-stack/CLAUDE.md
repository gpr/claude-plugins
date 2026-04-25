# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`react-vite-stack` is a Claude Code plugin (v1.1.0) that ships an opinionated React 19 + Vite + TS toolchain — TanStack Router/Query/Form, Zod, Zustand, shadcn/ui, Tailwind v4, Clerk, Vitest/RTL, Playwright — to *end-user React projects*. End users install it; this directory is the payload they receive.

**Critical:** every `*.md`, `*.json`, and `*.sh` file here is source code shipped to users. Edit, lint, and review accordingly. Do not treat skill/agent prose as instructions for *you* — treat it as content you maintain.

## Architecture

Skill-driven agent swarm with parallel monitors:

- **5 agents** (`agents/*.md`) — one task per agent, each declares the skills it relies on:
  - `component-builder` (Sonnet) — scaffolds one route + component using shadcn primitives
  - `api-client-generator` (Opus) — one REST endpoint module: Zod schema + typed fetch + queryOptions/mutationOptions + `useXyz` hook
  - `test-writer` (Haiku) — one test file (Vitest / RTL / Playwright depending on layer)
  - `reviewer` (Opus, read-only) — diffs against stack conventions, emits blockers/must-fix/suggestions; queries Chromatic MCP for visual diffs
  - `migration-pilot` (Opus, worktree isolation) — drives one cross-cutting library migration per invocation
- **10 skills** (`skills/<name>/SKILL.md`) encode per-library conventions: `tanstack-router`, `tanstack-query`, `tanstack-form-zod`, `zustand-slices`, `shadcn-tailwind`, `clerk-rest`, `vitest-rtl-playwright`, `error-and-loading`, `env-vars`, `pnpm-only`. Auto-invoked by relevance.
- **3 hooks** (`hooks/hooks.json`):
  - `SessionStart` → `scripts/enforce-pnpm.sh` (refuses package-lock.json/yarn.lock/bun.lockb and missing `packageManager` field; exit 2 is advisory — SessionStart is non-blocking)
  - `PostToolUse` matcher `Edit|Write|MultiEdit` → `scripts/check-changed.sh` (Prettier + ESLint --fix on the changed file only; **deliberately skips tsc**; exit 2 is advisory)
  - `FileChanged` matcher `src/routes/**/*.tsx` → `scripts/regen-routetree.sh` (regenerates `routeTree.gen.ts` via `tsr generate`)
- **4 monitors** (`monitors/monitors.json`, requires Claude Code ≥ 2.1.105):
  - `typecheck-watch` → `scripts/monitor-tsc.sh` (streams `tsc --watch` errors line by line)
  - `test-watch` → `scripts/monitor-vitest.sh` (streams Vitest FAIL lines)
  - `playwright-trace` → `scripts/monitor-playwright.sh` (lazy: `on-skill-invoke:vitest-rtl-playwright`; streams Playwright failures)
  - `bundle-watch` → `scripts/monitor-bundle.sh` (lazy: `on-skill-invoke:tanstack-query`; emits chunk-growth >10KB or forbidden-import lines; needs `fswatch` or `entr`)
- **MCP** — `.mcp.json` wires the `chromatic` server (visual regression) used by `reviewer`.
- **LSP** — `.lsp.json` wires `typescript-language-server` with inlay hints (`.ts`, `.tsx`, `.js`, `.jsx`).

The architectural bet: **monitors replace per-edit `tsc`** (which cost 5–20s of dead time). The PostToolUse hook does cheap fixes (format/lint); type errors stream from the long-lived monitor instead.

## Plugin layout

```
.claude-plugin/plugin.json    # manifest — userConfig prompts api_base_url + clerk_publishable_key + chromatic_project_token
agents/                       # 5 agent definitions
skills/<name>/SKILL.md        # 10 skills, one dir per skill
hooks/hooks.json              # SessionStart + PostToolUse + FileChanged
monitors/monitors.json        # typecheck-watch + test-watch + playwright-trace + bundle-watch (CC ≥ 2.1.105)
scripts/*.sh                  # 7 bash scripts invoked by hooks/monitors
.mcp.json                     # chromatic MCP server (visual regression)
.lsp.json                     # typescript-language-server config
README.md                     # end-user install / tuning / known issues
```

## Validation when editing this plugin

```bash
jq . .claude-plugin/plugin.json hooks/hooks.json monitors/monitors.json   # JSON syntax
shellcheck scripts/*.sh                                                    # all four bash scripts
```

Then invoke `@agent-plugin-dev:plugin-validator` (from the parent `plugin-dev` plugin) for manifest + component wiring.

Test the plugin against a real React project without installing it:

```bash
claude --plugin-dir /opt/gregory.rome/workspaces/gpr/claude-plugins/plugins/react-vite-stack
```

Hook/monitor scripts must use `${CLAUDE_PLUGIN_ROOT}` for any internal paths — never hardcode. They run in the *user's* React project root, so they detect the repo via `git rev-parse --show-toplevel` patterns inside the script bodies.

## Deliberate non-features (do not "fix")

Per `README.md`:
- **No project-wide `tsc` per edit** — the `typecheck-watch` monitor handles it. Adding tsc to PostToolUse would reintroduce 5–20s blocking.
- **One MCP server (Chromatic)** — wired into the `reviewer` agent for visual regression via `.mcp.json` and the `chromatic_project_token` userConfig entry. Visual regression was the threshold that justified an MCP server; no others are added.
- **No marketplace metadata** — added at distribution time, not now.

## Known end-user issues (mention in README, not fix in plugin)

- Plugin monitor auto-arm is broken on some Claude Code 2.1.x builds (anthropics/claude-code#52245). The README tells users to manually arm monitors when this happens.
- `@clerk/clerk-react` is in long deprecation; the `clerk-rest` skill detects whichever package is in use and won't mix them.

## Conventions (when editing payload)

- Agent frontmatter declares `model`, effort level, max turns, and required skills — keep these in sync with the skill set.
- Skills use auto-invocation by relevance — keep the SKILL.md `description` field specific so it triggers reliably.
- Conventional commits per parent `CLAUDE.md`: `feat`/`fix`/`refactor`/`perf` for production payload changes; `chore`/`docs` for README and tuning notes. Use `refactor` (not `fix`) for pre-release bugs.
- Replace, don't deprecate. If a skill or agent is superseded, delete it and update referencing agents in the same change.
