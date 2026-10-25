---
type: Reference
title: sdd tool and its role rules
description: The mcp__sdd__sdd and mcp__sdd__bundle tools' input, output, and which role may run each subcommand (SDD_RULES and checkBundle).
tags: [sdd, reference, tool, roles, guard, bundle]
sources:
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# sdd tool and its role rules

The mod registers two tools at session start: `sdd` (seen by agents as `mcp__sdd__sdd`) and `bundle` (`mcp__sdd__bundle`, [below](#the-bundle-tool)).

## Input

```json
{ "args": ["context", "add-login", "T2", "--plan"] }
```

`args` (required): the subcommand, then its arguments, as strings. A call with no subcommand is refused.

## Output

`sdd.py`'s stdout, trimmed. If stderr is not empty, a `stderr: ...` line follows. `(no output)` if both are empty. A non-zero exit appends `(exit N)`.

The tool runs `python3 <plugin root>/tools/sdd.py <args>` in the session's current directory, with a 120 s timeout. After `EnterWorktree` that is the change's worktree. If `python3` cannot be started, the call is refused with `Python 3.9+ must be on PATH`.

After a mutating subcommand or `check`, the band and panes refresh. Every `check` result is stored and shown in the `/sdd` pane.

## Role rules

The caller's role comes from the tool call's `agentId` (see [Guard rules](guard-rules.md#roles)). Subcommands absent from `SDD_RULES` are open to every role.

| Subcommand | lead | spec-author | contract-designer | planner | acceptance-tester | implementer | verifier | other |
|---|---|---|---|---|---|---|---|---|
| `init`, `new`, `set-status`, `sync`, `adr-accept` | ✓ | | | | | | | |
| `start`, `checkpoint`, `set-pr`, `requires`, `resume`, `finish` | ✓ | | | | | | | |
| `freeze` (once per batch of test tasks, so no half-written test is snapshotted) | ✓ | | | | | | | |
| `baseline-tree` | ✓ | | | | | | ✓ | |
| `delta-new`, `delta-stub`, `adr-new` | ✓ | ✓ | | | | | | |
| `contract-stub`, `contract-preview` | ✓ | | ✓ | | | | | |
| `config`, `status`, `check`, `context`, `contract-diff`, `verify-frozen`, `deps` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `bundle <target>` (check only) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `bundle specs --fix`, `bundle adrs --fix` | ✓ | | | | | | | |
| `bundle <change> --fix` | ✓ | ✓ | | | | | | |

A refusal reads ``[sdd] `sdd <sub>` is run by <roles> only, not <role>.`` `bundle` is not in `SDD_RULES`: `checkBundle` decides it, from the target and the `--fix` flag (`--fix` may sit anywhere in `args`). Refusals: ``[sdd] `bundle specs --fix` is run by the lead only, not <role>.`` (`adrs` alike), ``[sdd] `bundle <id> --fix` is run by lead or spec-author only, not <role>.``, `bundle` with other than one target is `usage: bundle <specs|adrs|change> [--fix]`.

If the tool's handler throws, the call is refused with `[sdd] the sdd tool failed unexpectedly; retry once, then tell the lead.`

## The bundle tool

`mcp__sdd__bundle` runs `sdd.py bundle <target> [--fix]` ([what it checks](bundles.md#bundle-checks)). Same working directory, Python requirement and output format as the `sdd` tool.

```json
{ "target": "add-login", "fix": true }
```

`target` (required): `specs`, `adrs` or a change id. `fix` (optional, default false): repair what is marked `[fixable]`. The role rule is the one in the table above: checking is open to all, `--fix` on `specs` or `adrs` is lead-only (only the lead may write them), `--fix` on a change is lead or spec-author (it touches front matter and the generated indexes, never the text of a criterion or invariant). A call without `target` is refused: `give the target: "specs", "adrs" or a change id.` A throwing handler is refused with `[sdd] the bundle tool failed unexpectedly; retry once, then tell the lead.` After a `fix`, the band and panes refresh.

The spec-author has this tool; it runs it on its change before handing back.

These rules are stated in three places that must agree: `SDD_RULES` and `checkBundle` in `hooks/guard.ts`, `TOOL_DESCRIPTION` and `BUNDLE_DESCRIPTION` in `hooks/register.tsx`, and the README. See [Keep in sync](../contributing/keep-in-sync.md).
