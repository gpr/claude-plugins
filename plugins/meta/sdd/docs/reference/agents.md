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
  at: 2026-10-18T00:00:00Z
---

# Workflow agents

The lead (the main conversation) delegates each artifact to one agent. Built-in agents are reused for the rest: `Explore` for codebase facts at triage, `general-purpose` for direct-path work and for running `code-review` alongside the verifier (both only read, so the lead starts them in one message).

| Agent | Job | Input from the lead | Writes | Model / effort | Preloaded skill |
|---|---|---|---|---|---|
| `sdd:spec-author` | `intent.md`, new Capability and Invariant concepts or CapabilityDeltas, draft ADRs | change id, the request verbatim, Explore findings | intent, delta, ADRs (draft only) | opus / high | `sdd:formats` |
| `sdd:contract-designer` | contract files: API in TypeSpec, CLI synopsis, UI as a static HTML mockup; only when intent.md `surface` lists a kind | change id; fetches its `sdd context <id> --contract` bundle | `changes/<id>/contracts/` (draft only) | sonnet / medium | `sdd:formats` |
| `sdd:planner` | `plan.md` (Approach, Contracts, Components, Risks) and `tasks.md` | change id (on re-plan: affected criterion and invariant ids) | plan, tasks | opus / high | `sdd:formats` |
| `sdd:acceptance-tester` | failing acceptance tests from the criteria and invariant checks (the lead freezes them) | change and task ids; fetches its `sdd context <id> <Tn>` bundle | `tests/acceptance/`, its task tick | sonnet / medium | `sdd:formats` |
| `sdd:implementer` | one `(impl)` task at a time, inner red-green-refactor TDD; resumed for the next task | change and task ids per task; fetches its `sdd context <id> <Tn> --plan` bundle | source code and unit tests, its task tick | sonnet / medium | — |
| `sdd:verifier` | close-out check: frozen tests, suites, traceability, diff review | change id | nothing but its memory | opus / high | — |

The spec-author, planner, acceptance-tester, implementer and verifier have the tools `Read, Grep, Glob, Bash, mcp__sdd__sdd`; all but the verifier also have `Write` and `Edit`. The contract-designer has `Read, Write, Edit, Bash, mcp__sdd__sdd` and no `Grep`/`Glob`: it works from its bundle, not by exploring the repo, and uses Bash only for `contract_cmd` on `contract-preview`'s dir. The spec-author also has `mcp__sdd__bundle`, to check and repair its change's bundle (`fix` is allowed on a change, not on `specs`; see [roles](sdd-tool-roles.md#the-bundle-tool)). All six have `memory: project`.

### Cost of the contract step

The contract-designer runs only for a full change whose `surface` lists `api`, `cli` or `ui`; `surface: none` (internal behavior, a library call) skips it, as do fixes and adopts. It runs on sonnet with a bundle of the touched criteria and the contract files they cite, starts from `contract-stub` copies so a small change is a small edit, and is resumed (SendMessage) for Gate 1 feedback rather than spawned again. In return the planner no longer designs the surface.

## Return contracts

| Agent | Returns |
|---|---|
| spec-author | ≤ ~15 lines: capability and invariant ids + titles, per capability the AC ids added/modified/retired and the sections replaced, ADR ids + one-line decisions, blocking open questions with options (or "none"), what was left out and why. Never the spec text. |
| contract-designer | ≤ ~10 lines: per file `ADDED\|MODIFIED\|RETIRED <path>` with its criteria ids, one line per operation, command or screen, the `contract_cmd` result, any spec problem or open question. Never the contract text: the lead runs `contract-diff`. |
| planner | ≤ ~10 lines: tasks as `Tn kind ids files`, one line per contract, any decision or spec problem found. |
| acceptance-tester | ≤ ~8 lines: test files (helpers and fixtures included), criterion → test count, failure reason per group (Baseline: passed), any `MISMATCH: <id> <observed behavior>`, criteria that could not be tested as written. |
| implementer | ≤ ~8 lines: `DONE` or `BLOCKED: <id> <reason>`, files changed, unit tests added, acceptance result, out-of-scope notes. |
| verifier | `VERDICT: PASS \| FAIL`, a line `frozen: ok\|tampered   acceptance: n/n   unit: n/n   baseline: n/n\|not run\|-   trace: ok\|errors`, findings as `- [code\|spec\|test] file:line <id> reason`. |

## Hard rules per agent

An agent's return ends its run. The spec-author, contract-designer, planner and verifier return only when their steps are done or something blocks them (a missing fact, a decision without an ADR, a hard failure), never to report progress, announce a next step or offer to continue.

- **spec-author**: never paste spec text back. Fill every template placeholder, give every criterion Given/When/Then and every invariant a Check with Holds and Violation examples, change existing concepts only through `delta-stub`, run `bundle` with `fix: true` on the change before handing back. Never type a base hash: re-run `delta-stub` after a CONFLICT. If a criterion to change lives in a required change that is not merged yet, report it as an open question, never add it again.
- **contract-designer**: work from the bundle, do not explore the repo. Start every file with `contract-stub`; never copy a living file by hand or touch a base line. Cite the criteria each element serves. A criterion the surface cannot express as written is a spec problem, a lasting naming or shape choice without an ADR is an open question: report both, never invent.
- **planner**: never change the spec or a contract file; with contract files, `## Contracts` lists them and adds only what they do not cover. If a decision meets the ADR bar and has none, stop and report. For a `size: fix`, add lines to `tasks.md` with Edit; never rewrite it or touch T1's line.
- **acceptance-tester**: test only through the public surface in the contract files and Contracts (or the existing surface, for a fix). Tests must fail for the right reason (a Baseline test must pass; if not, `MISMATCH`). An untestable or ambiguous criterion is a spec bug: report it. Tick the task with Edit, never Write; never freeze.
- **implementer**: never edit, skip, xfail or weaken an acceptance test, never change spec, contract files, plan or ADRs. Stay inside the task's `files:` or name the extra files. No behavior no criterion asks for. Implementers run one at a time, never in an isolated worktree. The lead resumes the same implementer (SendMessage) for each next task, so it keeps what it learned about the code; it spawns a new one after a BLOCKED or after 4 tasks.
- **verifier**: stop at the first hard failure. A tampered frozen test is a hard FAIL whatever else passes. No style nits. Mark a finding `spec` when the code is reasonable but the criterion is wrong.

## Memory

Each agent keeps notes across changes in `.claude/agent-memory/sdd-<agent>/MEMORY.md` (or `.claude/agent-memory-local/sdd-<agent>/`). Claude Code loads it into the agent's prompt. The guard lets each agent write only its own directory. Memory holds lessons about the repo, never anything about the current change, and never overrides the spec, ADRs, plan or frozen tests. See [Share agent memory](../how-to/share-agent-memory.md).
