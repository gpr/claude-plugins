---
name: monorepo-memory
description: Manages CLAUDE.md memory files across a monorepo with frontend/, website/, and backends/<name>/ packages. Covers updating memory, adding context to CLAUDE.md, deciding root-vs-package placement, and auditing memory files for staleness or duplication. Trigger phrases include "update CLAUDE.md", "add this to memory", "document for Claude", "Claude memory", "CLAUDE.md hygiene", "where should I put this in memory".
---

# Monorepo memory

Memory is split across the monorepo. Each package owns its own `CLAUDE.md`; the repo root has one too. Place context at the right level and keep each file lean.

## File locations

- `CLAUDE.md` (repo root) — cross-cutting context: monorepo layout, Taskfile entry points, cocogito version policy, branch model, package ownership, links to per-package memory.
- `frontend/CLAUDE.md` — frontend-only context.
- `website/CLAUDE.md` — website-only context.
- `backends/<name>/CLAUDE.md` — that backend's context.

If a package's `CLAUDE.md` does not exist when it should, create it before adding content. Do not invent a different location.

## Placement decision

When deciding where new context belongs, ask in order:

1. Does it apply to more than one package? → root.
2. Does it describe how packages interact (API contracts, shared envs)? → root.
3. Is it a release / version / commit / Taskfile convention? → root.
4. Is it stack-specific (React patterns, Rails generators, RSpec setup, Vite config quirks)? → that package.
5. Is it about a single endpoint, model, or component? → that package.

When in doubt, prefer the package-level file. Root is for things every contributor needs regardless of which package they touch.

## Content rules

- **Lead with the rule, not the rationale.** Future-Claude needs the rule; rationale is optional context, not the headline.
- **Imperative voice.** "Use pnpm, never npm" — not "We tend to use pnpm."
- **No history.** Memory is the current state, not a changelog. If a convention changes, replace the line, do not append.
- **Link, don't copy.** If a doc already exists in the repo (`docs/`, ADRs), link to it from `CLAUDE.md` — do not paste its content.
- **Lean files.** Target under 300 lines per `CLAUDE.md`. Past that, split into a `docs/` reference and link.

## Suggested root CLAUDE.md skeleton

```markdown
# Monorepo

## Layout
- frontend/ — React app (see frontend/CLAUDE.md)
- website/ — marketing site (see website/CLAUDE.md)
- backends/<name>/ — Rails APIs (see each backends/<name>/CLAUDE.md)

## Tooling
- Task runner: go-task. All cross-package commands go through Taskfile.yaml.
- Versioning: cocogito (cog). Single repo-wide version.
- Commits: conventional commits, enforced by `cog verify`.

## Daily commands
- `task --list-all` — see all tasks
- `cog verify "<msg>"` — check a commit message
- `cog bump` — release

## Branches
- <branch model goes here>

## Ownership
- <who owns what>
```

Per-package files should be even leaner — only what is unique to that package.

## Audit checklist

When asked to review memory files:

1. Read each `CLAUDE.md` in the monorepo (root + every package).
2. Flag duplication — anything stated in two files belongs in only one (usually the root).
3. Flag staleness — references to packages, scripts, or tasks that no longer exist.
4. Flag misplacement — stack-specific content in root, cross-cutting content in a package file.
5. Flag bloat — files over ~300 lines.
6. Report findings as a punch list before making edits. Do not silently rewrite.

## Sync with the layout skill

Before deciding where a file should live, load the `monorepo-layout` skill if it is not already in context. Placement decisions depend on knowing the canonical layout.
