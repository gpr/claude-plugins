---
type: Reference
title: Slash commands, band and panes
description: The /sdd:change skill, the /sdd command and its arguments, and what the band above the prompt and the two panes show.
tags: [sdd, reference, ui, commands]
sources:
  - resource: ../../hooks/register.tsx
  - resource: ../../hooks/phase.ts
  - resource: ../../skills/change/SKILL.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Slash commands, band and panes

## /sdd:change

`/sdd:change <what you want changed>` or `/sdd:change resume <change-id>`

Runs the lead workflow (`skills/change`). You don't have to type it: with the plugin enabled, the main conversation routes every change request to it.

## /sdd

| Command | Effect |
|---|---|
| `/sdd` | Opens the status pane (and shows the band again if it was hidden). |
| `/sdd phase` | Opens the phase pane. |
| `/sdd refresh` | Re-reads `sdd status --json`. |
| `/sdd check <change> [--tests]` | Runs `sdd check` without the model and prints its output. The result is stored for the pane. |

Each `/sdd` call refreshes the change list first.

## Band above the prompt

Shown when at least one change is open, unless hidden:

```
sdd  add-login  Implement · implementing · 2/5 tasks · PR #42 · check ok · implementer running · +1 open   [Open] [Hide]
```

The fields are: the active change, its phase label, status, tasks done/total, PR, the last check result, which workflow agents are running, and how many other changes are open. **Open** opens the status pane. **Hide** hides the band until the next `/sdd`.

The active change is the one whose branch (`sdd/<id>`, made by `sdd start`) is checked out in the session's directory. Without one, it is the most active open change: ordered by status (`implementing`, `verified`, `approved`, `draft`), then by how far the change is in its own workflow, then by the number of tasks.

## Status pane (`/sdd`)

- Header: open count, running agents, archived count.
- The active change in full: id, status, PR, branch; its title; its phase label and hint; a 12-cell progress bar; every task, done ones dimmed, with all its REQs (`[ ] T3 impl REQ-AUTH-004 REQ-AUTH-005`); its ADRs; `requires`; the last check, with its ERROR/WARN lines (up to 12).
- The other open changes in status groups (`implementing`, `verified`, `approved`, `draft`, then any other status), folded at first. A folded group is one line: `▸ approved (3) add-login, add-sso, fix-typo · 1 check failed`. Press the header, or its digit (`1` for the first group) while the pane has focus, to unfold it (`▾`). An unfolded group lists its changes one line each: phase, tasks, PR, requires, check result, plus the ERROR lines of a failed check. Groups stay unfolded for the session.
- Running workflow agents with their description.
- The last guard refusal.

With no open change it says how to start one.

## Phase pane (`/sdd phase`)

The steps of the active change's workflow (a fix has its own order, see [Phases](phases-and-states.md#order-for-a-fix)): `✓` done, `▶` current with its hint, `·` to come. Then the phase of every other open change.

## Refresh

The change list refreshes at session start, after a mutating `sdd` call or a `check`, after a write under `changes/`, on `/sdd`, and every 30 s. Running agents refresh every 4 s, on agent spawn and at turn end.
