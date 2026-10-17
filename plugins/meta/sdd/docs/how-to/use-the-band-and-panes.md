---
type: How-to Guide
title: Follow a change from the band and panes
description: See where a change stands, run a check without the model, and find out why the guard refused something.
tags: [sdd, how-to, ui, status]
sources:
  - resource: ../../hooks/register.tsx
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Follow a change from the band and panes

## See the current state

- Glance at the band above the prompt. It shows the active change (the one whose `sdd/<id>` branch is checked out, else the most active), its phase, status, task progress, PR, last check and running agents.
- `/sdd` for detail: every task of the active change, its ADRs, dependencies, the last check's errors. The other open changes sit in folded status groups: press a header, or its digit while the pane has focus, to unfold it.
- `/sdd phase` to see which workflow step the change is in and what happens there.

There's no need to ask the lead for a recap. It's told to point you to the panes.

## Run a check yourself

```
/sdd check add-login
/sdd check add-login --tests
```

Runs `sdd check` directly, without a model turn, and stores the result for the band and pane.

## The band or pane looks stale

```
/sdd refresh
```

Edits made outside Claude Code (your editor, a `git pull`) otherwise appear on the next 30-second refresh.

## Hide the band

Press **Hide** on the band. `/sdd` brings it back.

## Find out why something was refused

The `/sdd` pane ends with `last guard refusal: <role>: <reason>`. Each refusal also shows as a toast. The reasons are listed in [Guard rules](../reference/guard-rules.md).

## The pane is empty but you have a change

The band and panes read `sdd status` from the session's current directory. If the change lives in a worktree the session hasn't entered, ask the lead to resume it (`/sdd:change resume <id>`).
