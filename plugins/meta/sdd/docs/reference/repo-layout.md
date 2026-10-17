---
type: Reference
title: Repository layout
description: The files and directories the sdd workflow creates and owns in a project repository, and who writes each.
tags: [sdd, reference, layout]
sources:
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Repository layout

Default directory names; each is configurable (see [Configuration](configuration.md)). `specs/` and each change are OKF bundles: see [OKF bundles](bundles.md).

```
specs/index.md, specs/log.md             generated: index of the bundle, one line per sync
specs/<capability>/index.md              generated: the capability's concepts and REQ ids
specs/<capability>/<concept>.md          living spec: what the system does now, a few REQs
specs/invariants/<category>/<concept>.md living invariants: rules that always hold, a few INVs
adr/ADR-NNNN-<slug>.md                   one decision per file
changes/<id>/index.md                    generated: the change's files and delta ids
changes/<id>/intent.md                   why, scope, non-goals; front matter status/size/adrs
changes/<id>/specs/<capability>/<concept>.md             spec delta, mirrors the living path
changes/<id>/specs/invariants/<category>/<concept>.md    invariant delta
changes/<id>/plan.md                     approach, contracts, components, risks
changes/<id>/tasks.md                    task checklist
changes/<id>/frozen.json                 hashes of the frozen acceptance tests
changes/<id>/state.json                  phase, branch, base, PR, requires
changes/archive/<YYYY-MM-DD>-<id>/       a synced change, immutable
tests/acceptance/                        acceptance tests tagged with REQ ids
.claude/sdd.json                         project configuration
.claude/worktrees/sdd-<id>/              one worktree per change (git-ignored)
.claude/agent-memory/sdd-<agent>/        per-agent project memory
.claude/agent-memory-local/sdd-<agent>/  per-agent memory kept out of git
```

How a change's files move at `sdd sync`:

```mermaid
flowchart LR
    subgraph open ["changes/&lt;id&gt;/ (open)"]
        I[intent.md]
        DL["specs/&lt;cap&gt;/&lt;concept&gt;.md<br/>delta"]
        PT[plan.md, tasks.md]
        FJ[frozen.json, state.json]
    end
    DL -- "ADDED / MODIFIED / REMOVED / MOVED<br/>by REQ or INV id" --> LS["specs/&lt;cap&gt;/&lt;concept&gt;.md<br/>+ index.md, log.md"]
    I -- "adrs: [...]" --> ADR["adr/ADR-NNNN: proposed → accepted"]
    open -- "moved whole" --> AR["changes/archive/&lt;date&gt;-&lt;id&gt;/"]
```

Acceptance tests stay where they are in `tests/acceptance/` and become part of the regression suite.

## Who writes what

| Path | Written by |
|---|---|
| `specs/**` | `sdd sync`; `sdd bundle specs --fix` (lead) for layout, front matter and indexes |
| `adr/*` (proposed) | spec-author, via `sdd adr-new` then Edit |
| ADR `status:` | `sdd adr-accept` / `sdd sync` |
| `intent.md` body, delta | spec-author, while `draft` |
| `changes/<id>/index.md` | `sdd new`, `delta-new`, `delta-stub`, `bundle <id> --fix` |
| `intent.md` `status:` | `sdd set-status` / `sdd sync` |
| `plan.md`, `tasks.md` | planner, while `draft` or `approved` |
| task ticks in `tasks.md` | acceptance-tester and implementer, each its own task |
| `tests/acceptance/**` | acceptance-tester |
| `frozen.json` | `sdd freeze` |
| `state.json` | `sdd start`, `checkpoint`, `set-pr`, `requires`, `finish` |
| `changes/archive/**` | `sdd sync` (move), `sdd finish` (`state.json` phase) |
| source code, unit tests | implementer (or `general-purpose` on the direct path) |
| `.claude/sdd.json` | `sdd init`, then you |

Enforcement: [Guard rules](guard-rules.md).

## What to commit

Commit everything above except `.claude/worktrees/` (`sdd init` adds it to `.gitignore`). `.claude/sdd.json` must be committed and pushed to the base branch before `sdd start`. Committing `.claude/agent-memory/` is optional: see [Share agent memory](../how-to/share-agent-memory.md).
