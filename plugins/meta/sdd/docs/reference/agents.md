---
type: Reference
title: Workflow agents
description: The five sdd plugin agents, their job, inputs, outputs, tools, model, effort and memory directory.
tags: [sdd, reference, agents]
sources:
  - resource: ../../agents/spec-author.md
  - resource: ../../agents/planner.md
  - resource: ../../agents/acceptance-tester.md
  - resource: ../../agents/implementer.md
  - resource: ../../agents/verifier.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Workflow agents

The lead (the main conversation) delegates each artifact to one agent. Built-in agents are reused for the rest: `Explore` for codebase facts at triage, `general-purpose` for direct-path work and for running `code-review` after the verifier.

| Agent | Job | Input from the lead | Writes | Model / effort | Preloaded skill |
|---|---|---|---|---|---|
| `sdd:spec-author` | `intent.md`, the spec and invariant deltas (short concepts), proposed ADRs | change id, the request verbatim, Explore findings | intent, delta, ADRs (draft only) | opus / high | `sdd:formats` |
| `sdd:planner` | `plan.md` (Approach, Contracts, Components, Risks) and `tasks.md` | change id (on re-plan: affected REQ ids) | plan, tasks | opus / high | `sdd:formats` |
| `sdd:acceptance-tester` | failing acceptance tests from the scenarios, then `freeze` | `sdd context <id> <Tn>` bundle | `tests/acceptance/`, its task tick | sonnet / medium | `sdd:formats` |
| `sdd:implementer` | one `(impl)` task, inner red-green-refactor TDD | `sdd context <id> <Tn> --plan` bundle | source code and unit tests, its task tick | sonnet / medium | — |
| `sdd:verifier` | close-out check: frozen tests, suites, traceability, diff review | change id | nothing but its memory | opus / high | — |

All five have the tools `Read, Grep, Glob, Bash, mcp__sdd__sdd`. All but the verifier also have `Write` and `Edit`. The spec-author also has `mcp__sdd__bundle`, to check and repair its change's bundle (`fix` is allowed on a change, not on `specs`; see [roles](sdd-tool-roles.md#the-bundle-tool)). All five have `memory: project`.

## Return contracts

| Agent | Returns |
|---|---|
| spec-author | ≤ ~15 lines: REQ and INV ids + titles by ADDED/MODIFIED/REMOVED (and moved concepts), ADR ids + one-line decisions, blocking open questions with options (or "none"), what was left out and why. Never the spec text. |
| planner | ≤ ~10 lines: tasks as `Tn kind REQs files`, one line per contract, any decision or spec problem found. |
| acceptance-tester | ≤ ~8 lines: test files, scenario → test count, failure reason per group, scenarios that could not be tested as written. |
| implementer | ≤ ~8 lines: `DONE` or `BLOCKED: <REQ-id> <reason>`, files changed, unit tests added, acceptance result, out-of-scope notes. |
| verifier | `VERDICT: PASS \| FAIL`, a line `frozen: ok\|tampered   acceptance: n/n   unit: n/n   trace: ok\|errors`, findings as `- [code\|spec\|test] file:line REQ-... reason`. |

## Hard rules per agent

- **spec-author**: never paste spec text back. Keep concepts short (max 5 blocks per file), give every INV a `#### Check:`, run `bundle` with `fix: true` on the change before handing back. Never type a base hash: re-run `delta-stub` after a CONFLICT. If a MODIFIED/REMOVED REQ lives in a required change that is not merged yet, report it as an open question, never re-ADD it.
- **planner**: never change the spec. If a decision meets the ADR bar and has none, stop and report. For a `size: fix`, add lines to `tasks.md` with Edit; never rewrite it or touch T1's line.
- **acceptance-tester**: test only through the public surface in Contracts (or the existing surface, for a fix). Tests must fail for the right reason. An untestable or ambiguous scenario is a spec bug: report it.
- **implementer**: never edit, skip, xfail or weaken an acceptance test, never change spec, plan or ADRs. Stay inside the task's `files:` or name the extra files. No behavior no REQ asks for.
- **verifier**: stop at the first hard failure. A tampered frozen test is a hard FAIL whatever else passes. No style nits. Mark a finding `spec` when the code is reasonable but the REQ is wrong.

## Memory

Each agent keeps notes across changes in `.claude/agent-memory/sdd-<agent>/MEMORY.md` (or `.claude/agent-memory-local/sdd-<agent>/`). Claude Code loads it into the agent's prompt. The guard lets each agent write only its own directory. Memory holds lessons about the repo, never anything about the current change, and never overrides the spec, ADRs, plan or frozen tests. See [Share agent memory](../how-to/share-agent-memory.md).
