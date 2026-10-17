---
type: Explanation
title: Context bundles
description: Why each agent receives a computed, minimal slice of the change instead of whole files or the lead's conversation, and what each slice contains.
tags: [sdd, explanation, context, tokens]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/change/SKILL.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Context bundles

`sdd context <change> <task> [--plan]` prints exactly what one agent needs for one task. The lead pastes it into the agent's prompt.

## What each task gets

| Part | test task | impl task | impl task with `--plan` |
|---|---|---|---|
| the task line and the lines of tasks it is blocked by | ✓ | ✓ | ✓ |
| the REQ blocks it cites: the delta's version if the change touches it, else the living one | ✓ | ✓ | ✓ |
| the `## Decision` paragraph of each ADR it cites, with its status | ✓ | ✓ | ✓ |
| the plan's `## Contracts` section | ✓ | | (in the full plan) |
| the paths of the frozen acceptance tests for its REQs | | ✓ | ✓ |
| the whole plan | | | ✓ |

The workflow uses `context <id> <Tn>` for test tasks and `context <id> <Tn> --plan` for impl tasks.

## Why minimal

**Independence.** The acceptance-tester sees the scenario and the public contract, never the planned internals, so its tests check behavior and not implementation. The implementer gets the tests as read-only file paths: it must satisfy them, not redesign them.

**Accuracy.** The REQ text in the bundle is copied by the script from the files, so it is the current text, not the lead's paraphrase of it. For a REQ the change modifies, it is the new version.

**Cost.** An agent that reads the whole spec, every ADR and the lead's conversation spends most of its context on things that don't bear on its task. A bundle is usually a screen or two. The same reasoning drives the other token rules in the workflow: agents are resumed with `SendMessage` instead of re-spawned, and the lead gives you ids and paths, not file contents.

**ADR Decisions must stand alone.** Since implementers receive only the Decision paragraph, an ADR's Decision has to make sense without its Context and Options. An empty one shows as `(Decision section is empty: report this)`.
