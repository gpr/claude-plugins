---
type: Reference
title: sdd tool and its role rules
description: The mcp__sdd__sdd tool's input, output, and which role may run each subcommand (SDD_RULES).
tags: [sdd, reference, tool, roles, guard]
sources:
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# sdd tool and its role rules

The mod registers one tool, `sdd` (seen by agents as `mcp__sdd__sdd`), at session start.

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

| Subcommand | lead | spec-author | planner | acceptance-tester | implementer | verifier | other |
|---|---|---|---|---|---|---|---|
| `init`, `new`, `set-status`, `sync`, `adr-accept` | ✓ | | | | | | |
| `start`, `checkpoint`, `set-pr`, `requires`, `resume`, `finish` | ✓ | | | | | | |
| `freeze` | ✓ | | | ✓ | | | |
| `delta-new`, `delta-stub`, `adr-new` | ✓ | ✓ | | | | | |
| `config`, `status`, `check`, `context`, `verify-frozen`, `deps` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

A refusal reads ``[sdd] `sdd <sub>` is run by <roles> only, not <role>.``

If the tool's handler throws, the call is refused with `[sdd] the sdd tool failed unexpectedly; retry once, then tell the lead.`

These rules are stated in three places that must agree: `SDD_RULES` in `hooks/guard.ts`, `TOOL_DESCRIPTION` in `hooks/register.tsx`, and the README. See [Keep in sync](../contributing/keep-in-sync.md).
