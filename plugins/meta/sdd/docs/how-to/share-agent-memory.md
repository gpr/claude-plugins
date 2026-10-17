---
type: How-to Guide
title: Share or isolate agent memory
description: Decide whether the workflow agents' project memory is shared with the team through git or kept per clone, and how to turn it off.
tags: [sdd, how-to, memory, agents]
sources:
  - resource: ../../README.md
  - resource: ../../hooks/guard.ts
  - resource: ../../agents/planner.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Share or isolate agent memory

Each workflow agent keeps lessons about your repository (layout, test setup, recurring findings) in `.claude/agent-memory/sdd-<agent>/MEMORY.md`, loaded into its prompt on every run.

## Share it with the team

Commit the directory:

```
git add .claude/agent-memory/
```

Every clone's agents then start with what earlier changes taught them. Review memory diffs in PRs like any other file.

## Keep it per clone

Ignore it:

```
# .gitignore
/.claude/agent-memory/
```

Claude Code's local memory scope uses `.claude/agent-memory-local/sdd-<agent>/`. The guard allows that directory as well.

## Turn it off

Set `autoMemoryEnabled: false` in Claude Code settings. The agents run without memory.

## What memory can't do

- An agent can write only its own directories. The guard refuses everything else under `.claude/`.
- Memory holds nothing about the current change (that's in `changes/<id>/`) and never overrides the spec, ADRs, plan or frozen tests: each agent's prompt says so.

## Clean up bad lessons

Edit or delete `MEMORY.md` by hand. You are the lead, and the guard doesn't restrict you there.
