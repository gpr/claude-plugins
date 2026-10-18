---
type: Explanation
title: Why the guard works the way it does
description: The reasoning behind an in-process, role-based write guard - role from agentId, rules as pure functions, fail-closed for subagents and open for the lead.
tags: [sdd, explanation, guard, security]
sources:
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
  - resource: ../../CLAUDE.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Why the guard works the way it does

Agent prompts say "never edit the acceptance tests", but a prompt is advice, not enforcement. An implementer under pressure to make a test pass has every incentive to weaken it. The guard turns the workflow's separation of duties into hard limits.

## One role per agent, from the call itself

Each tool call carries the `agentId` of the agent making it, or none for the main conversation. The guard looks up the agent's type (`sdd:implementer`) and maps it to a role. The role isn't something an agent can claim or forget: it comes from how Claude Code spawned the agent. Renaming an agent file therefore renames its role, which is why the role list and the agent tables must change together.

Agents that aren't part of the workflow (`Explore`, `general-purpose`, other plugins) get the role `other`. They are bound by the rules that protect the workflow's artifacts and are otherwise free.

## Artifacts owned by a tool, not by a person

Some files are refused even to the lead: `specs/`, `frozen.json`, `state.json`, archived changes and accepted (stable) or deprecated ADRs. They aren't meant to be edited at all, only produced by `sdd.py` (`sync`, `freeze`, `checkpoint`, ...) or replaced by a superseding ADR. Making that true for everyone means the guarantees in [Why sdd.py exists](determinism.md) hold regardless of who is typing.

The same reasoning covers status lines. A spec-author that could write `status: approved` into its own `intent.md` would approve its own work. Status moves only through `sdd set-status` and `sdd adr-accept`, and the guard refuses those subcommands to every subagent.

## Status-dependent permissions

A spec-author may edit the delta only while the change is `draft`. A planner may edit the plan only while it is `draft` or `approved`. Once you pass Gate 1, the spec is frozen for agents. Once implementation starts, the plan is frozen too. To change them, the lead reopens the change, which sends it back through your review.

## Pure rules, thin I/O

The rules live in `hooks/guard.ts` as pure functions (`checkPath`, `checkBash`, `checkSdd`) that take a path, a role, the config and a status lookup. `hooks/register.tsx` only does I/O: it finds the role, reads the config and front matter, and draws. That split makes every rule unit-testable without a session, and every rule change gets a test case.

## Fail closed for subagents, open for the lead

If the guard throws (an unreadable file, an engine hiccup), it refuses the subagent's call and lets the lead's call through. A subagent that's wrongly refused just reports back. A lead that's wrongly blocked would freeze the whole session, including your ability to fix the guard.

## Bash is a heuristic, hashes are the proof

File-writing tools carry an explicit path, so the guard decides exactly. Bash doesn't: a command can write anywhere in endless ways. The guard looks for write-like commands and checks the paths they mention, which catches mistakes and casual workarounds but can't catch everything. That's why `verify-frozen` exists, and why the verifier treats a hash mismatch as a hard failure whatever the tests say.

## In-process, not a shell hook

The guard runs inside Claude Code as a mod hook, not as an external `PreToolUse` script. It sees the calling agent's id, it can read the plugin's state, and it can show a toast and remember the last refusal for the pane. There is no process spawn on every write either.
