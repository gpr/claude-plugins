---
type: Reference
title: Things that must change together
description: The sets of files that restate the same fact in the sdd plugin, so a change to one must update the others in the same commit.
tags: [sdd, contributing, maintenance]
sources:
  - resource: ../../CLAUDE.md
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/phase.ts
  - resource: ../../hooks/register.tsx
  - resource: ../../tools/sdd.py
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Things that must change together

| When you change | Also update |
|---|---|
| Phase ids | `PHASES` in `tools/sdd.py` and `hooks/phase.ts` (sdd.py adds `done`), `PHASE_STATUSES` and `PHASE_STEPS` in `sdd.py`, step names in `skills/change/SKILL.md`, `tests/phase.test.ts`, [Phases and states](../reference/phases-and-states.md) |
| A workflow step or a status | `PHASES` / `phaseOf` and their tests, `STATUSES` in `sdd.py`, `skills/change`, [Phases and states](../reference/phases-and-states.md) |
| Which role may run an `sdd` subcommand | `SDD_RULES` in `hooks/guard.ts`, `TOOL_DESCRIPTION` in `hooks/register.tsx`, the README, `tests/guard.test.ts`, [sdd tool roles](../reference/sdd-tool-roles.md) |
| A new `sdd` subcommand (`bundle` included) | `COMMANDS` and the docstring in `sdd.py`, `MUTATING` in `register.tsx` if it writes, `SDD_RULES` if restricted (`checkBundle` for `bundle`), `TOOL_DESCRIPTION` (and `BUNDLE_DESCRIPTION`), `tests/test_sdd.py`, [sdd subcommands](../reference/cli.md) |
| A guard rule | `hooks/guard.ts`, a case in `tests/guard.test.ts`, the README's guard list, [Guard rules](../reference/guard-rules.md) |
| An agent file name | its role in `ROLES` (`guard.ts`), the agent tables in the README and `skills/change`, its memory dir name, [Workflow agents](../reference/agents.md) |
| An agent's tools, model or job | the agent file, [Workflow agents](../reference/agents.md) |
| A file format (Capability, Invariant, CapabilityDelta section, base marker, citation, task line, index or log) | the parser in `sdd.py`, `skills/formats/SKILL.md`, the templates, `tests/test_sdd.py`, [File formats](../reference/file-formats.md) |
| The OKF layout or a bundle check (concept paths, front matter, indexes, `log.md`, the `bundle` fixers, the `bundle` tool roles) | `check_specs` / `check_adrs` / `check_change` / `build_indexes` / `append_log` in `sdd.py`, `checkBundle` in `guard.ts`, `BUNDLE_DESCRIPTION` in `register.tsx`, `skills/formats/SKILL.md`, the templates, `agents/spec-author.md`, the README section "Capabilities, invariants and OKF bundles", `TestBundle` in `tests/test_sdd.py`, [OKF bundles](../reference/bundles.md), [File formats](../reference/file-formats.md), [Repository layout](../reference/repo-layout.md) |
| `state.json` fields or its writers | `sdd.py`, `types/index.d.ts`, the guard's `state.json` message, [Phases and states](../reference/phases-and-states.md#statejson) |
| A config key | `CFG` in `sdd.py`, `Cfg`/`DEFAULT_CFG` in `guard.ts` if the guard needs it, [Configuration](../reference/configuration.md) |
| Band or pane content | `register.tsx`, `tests/mod.test.tsx`, the README, [Slash commands, band and panes](../reference/slash-commands.md) |

## Invariants

- `tools/sdd.py` is the only code that writes specs, ADR statuses, `frozen.json`, `state.json` or the archive. It stays deterministic, with no model calls, and keeps its output terse.
- Agents call `mcp__sdd__sdd`, never `python3 .../sdd.py`.
- The guard identifies the caller from `tool.call`'s `agentId` → `$.agent.list()` type, and maps only the `sdd:` prefix.
- Guard failure policy: refuse for subagents, allow for the lead.
- The lead is a `prompt.compose` section (`LEAD`), not a `settings.json` agent: a plugin agent's prompt would replace Claude Code's whole system prompt. Keep it a short router.
- Every workflow agent keeps its `memory: project` line and its role-specific Memory section. `memoryDirs` is the only `.claude/` exception for subagents.

Source of these rules: the plugin's `CLAUDE.md`.
