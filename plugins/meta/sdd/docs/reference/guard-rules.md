---
type: Reference
title: Guard rules
description: Which role may write which path, how the role is identified, the Bash heuristics, and the failure policy of the in-process write guard.
tags: [sdd, reference, guard, permissions]
sources:
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
  - resource: ../../tests/guard.test.ts
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Guard rules

The guard is a `tool.call` hook in the plugin's mod. It checks every `Edit`, `Write`, `MultiEdit`, `NotebookEdit` and `Bash` call before it runs. A refusal comes back to the caller as `[sdd-guard] <reason>`, shows as a toast, and is kept as the "last guard refusal" in the `/sdd` pane.

Paths in the rules use the configured directory names (`specs_dir`, `changes_dir`, `adr_dir`, `acceptance_dir`), written here as their defaults.

## Roles

| Agent type reported by Claude Code | Role |
|---|---|
| none (no `agentId`: the main conversation) | `lead` |
| `sdd:spec-author`, `sdd:planner`, `sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier` | the name without `sdd:` |
| anything else (`Explore`, `general-purpose`, other plugins' agents, an unknown `sdd:` name) | `other` |

The role is looked up from the call's `agentId` with `$.agent.list()` and cached per agent id.

## File writes (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`)

The path is resolved against the session cwd, then the project root (the root `sdd.py` reports). A subagent writing outside both is refused (`<path> is outside the project.`); the lead is not.

### Everyone, the lead included

| Path | Rule |
|---|---|
| `specs/**` | refused: living specs change only through `sdd sync` |
| `changes/archive/**` | refused: archived changes are immutable |
| `changes/**/frozen.json` | refused: written only by `sdd freeze` |
| `changes/**/state.json` | refused: written only by `sdd.py` |
| `adr/*` with `status:` `accepted`, `superseded` or `deprecated` | refused: write a superseding ADR with `sdd adr-new <title> --supersedes ADR-NNNN` |

The lead passes every other write.

### Every subagent

| Path or content | Rule |
|---|---|
| its own memory dirs `.claude/agent-memory/sdd-<role>/`, `.claude/agent-memory-local/sdd-<role>/` | allowed (workflow roles only) |
| any other path under `.claude/` | refused |
| a write to an ADR that puts a `status:` line different from the ADR's current status (`proposed` if none) | refused: ADR status moves only through `sdd adr-accept` |
| a write to `changes/<c>/intent.md` that puts a `status:` line different from the change's current status | refused: status moves only through `sdd set-status` |

### Per role

| Role | May write | While |
|---|---|---|
| `spec-author` | `adr/**`; `changes/<c>/intent.md`; `changes/<c>/specs/**` | intent and delta only while the change is `draft` (or has no status yet) |
| `planner` | `changes/<c>/plan.md`, `changes/<c>/tasks.md` | change is `draft` or `approved` |
| `acceptance-tester` | `tests/acceptance/**`, `changes/<c>/tasks.md` | any status |
| `implementer` | anything except `tests/acceptance/**`, `adr/**` and `changes/**` (but `changes/<c>/tasks.md` is allowed) | any status |
| `verifier` | nothing (its memory dirs aside) | — |
| `other` | anything not covered by the rules above | — |

## Bash

The lead's Bash calls are not checked. For subagents:

1. A command mentioning `tools/sdd.py` is refused: use the `sdd` tool.
2. A command that does not look like a write passes. "Looks like a write" means it contains a redirect (`>`, `>>`), `tee`, `sed -i`, `perl -i`, `mv`, `cp`, `rm`, `truncate`, `dd`, `git checkout|restore|rm|mv|apply`, `patch`, `install`, `write_text`, or `open(..., 'w'|'a')`. Fd duplications (`2>&1`) and `/dev/null` sinks don't count.
3. Otherwise every word containing `/` or ending in `.md` is resolved as a path (relative to the cwd), and:
   - `verifier`: refused.
   - `implementer`: refused if it is under `tests/acceptance/`, or under `changes/` and not a `tasks.md`.
   - any subagent: refused if it is under `specs/`, `adr/`, `.claude/`, `changes/archive/`, or is a `frozen.json` / `state.json` under `changes/`.

This check is a heuristic backstop. `sdd verify-frozen`, run by the verifier and ideally in CI, is the real enforcement for the acceptance tests.

## Failure policy

If the guard itself throws, it refuses the call for a subagent (`the guard failed; refusing for safety.`) and lets the lead's call through.

## Related

- [Why the guard is designed this way](../explanation/guard-design.md)
- [sdd tool roles](sdd-tool-roles.md)
