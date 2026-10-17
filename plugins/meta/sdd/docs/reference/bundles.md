---
type: Reference
title: OKF bundles
description: The OKF v0.2 layout of specs/ and of each change, the front matter of every concept type, the checks of sdd bundle and which ones --fix repairs, and how to migrate the legacy layout.
tags: [sdd, reference, okf, bundle, specs, invariants]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../skills/change/templates/delta.md
  - resource: ../../skills/change/templates/invariant-delta.md
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# OKF bundles

`specs/` and each open change `changes/<id>/` are [OKF v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundles: a root `index.md`, one short Markdown file per concept, YAML front matter with a `type`. `sdd.py` writes the indexes and the log; nobody edits them. The `bundle` subcommand ([sdd subcommands](cli.md#checks-and-context)) and the `mcp__sdd__bundle` tool ([roles](sdd-tool-roles.md#the-bundle-tool)) validate and repair them.

## Layout

```
specs/index.md                                   okf_version "0.2"; lists the capabilities and invariants/
specs/log.md                                     one line per sync
specs/<capability>/index.md                      concepts of the capability, with their REQ ids
specs/<capability>/<concept>.md                  type: spec, a few REQ blocks
specs/invariants/<category>/index.md             concepts of the category, with their INV ids
specs/invariants/<category>/<concept>.md         type: invariant, a few INV blocks

changes/<id>/index.md                            type: change, generated: files and delta ids
changes/<id>/intent.md                           type: intent
changes/<id>/plan.md                             type: plan
changes/<id>/tasks.md                            type: tasks
changes/<id>/specs/<capability>/<concept>.md     type: spec-delta, mirrors the living path
changes/<id>/specs/invariants/<category>/<concept>.md   type: invariant-delta
```

- `index.md` and `log.md` are reserved names, never concepts. Every other `.md` under `specs/` is a concept; names are kebab-case.
- REQ blocks live only under `specs/<capability>/`, INV blocks only under `specs/invariants/<category>/`. `invariants` is therefore not a usable capability name.
- A concept is short: at most `concept_max_blocks` blocks (default 5, see [Configuration](configuration.md)). Over the limit is a warning: split the topic into another concept file. A concept's file name is free; the REQ/INV id decides what a block is, the path only groups it.
- A delta's path mirrors the concept it targets. A MODIFIED block placed in a different concept of the same capability or category **moves** the requirement at sync (the log line says `MOVED`). It cannot move to another capability or category.
- Archived changes keep their files as they were; they are not checked.

## Front matter per type

Front matter is parsed line by line as `key: value`; `[a, b]` is a list (nested YAML is not supported, see [File formats](file-formats.md#intentmd)). Keys not listed are kept.

| File | Keys |
|---|---|
| `specs/index.md` | `okf_version: "0.2"`, `type: index`, `title: Specs` |
| `specs/<dir>/index.md` | `type: index`, `title: <dir path under specs/>` |
| `specs/log.md` | `type: log`, `title: Specs log` |
| spec concept | `type: spec`, `title`, `capability`, `sources: [code paths]` |
| invariant concept | `type: invariant`, `title`, `category`, `sources: [code paths]` |
| `changes/<id>/index.md` | `okf_version: "0.2"`, `type: change`, `title` |
| `intent.md` | `type: intent`, then `id`, `title`, `status`, `size`, `adrs`, `created` |
| `plan.md`, `tasks.md` | `type: plan` / `type: tasks`, `change: <id>` |
| spec delta | `type: spec-delta`, `target: specs/<capability>/<concept>.md`, `sources` |
| invariant delta | `type: invariant-delta`, `target: specs/invariants/<category>/<concept>.md`, `sources` |

- `title` of a concept defaults to its first `# ` heading, else the file name with dashes as spaces.
- `sources` lists repository paths the concept covers; an entry may end in `:12` or `:12-30`. A path that does not exist is reported and dropped by `--fix`.
- At sync, the delta's `sources` are merged (union, sorted) into the target concept's.

## Invariant block

```markdown
### INV-SEC-001: Secrets are never logged
The system MUST NOT write a password or token to any log.

#### Check: test_no_secret_in_logs greps the captured log of the login flow
```

An INV id matches `inv_id_pattern` (default `INV-[A-Z0-9]+-[0-9]{3}`). It has a `#### Check:` line instead of a `#### Scenario:`. In a change, an ADDED or MODIFIED INV needs a `(test)` task and no `(impl)` task. `sdd context` for an `(impl)` task lists the id and title of every invariant in force that the task does not name. Everything else (base hash, MODIFIED/REMOVED, `delta-stub`) works as for a REQ.

## Bundle checks

`bundle specs` checks the living specs; `bundle <id>` checks the change. With `--fix`, a finding marked `[fixable]` is repaired and printed as `FIXED <message>` instead.

### specs

| Finding | Level | Fixable |
|---|---|---|
| `specs/` missing | ERROR | yes, creates it |
| `<cap>/spec.md` legacy layout | ERROR | yes, renames to `<cap>/<cap>.md` (not if that file exists) |
| concept at the wrong depth (not `specs/<cap>/x.md` or `specs/invariants/<cat>/x.md`) | ERROR | no |
| name not kebab-case | ERROR | no |
| front matter incomplete (`type`, `title`, `capability`/`category`, `sources`) | ERROR | yes |
| `sources` entry not found | WARN | yes, drops it |
| INV in the spec tree, or REQ in the invariant tree | ERROR | no |
| an id defined in two files | ERROR | no |
| REQ without `#### Scenario:`, INV without `#### Check:` | WARN | no |
| concept without blocks | ERROR | yes, deletes the file, unless it holds prose |
| blocks not sorted by id | ERROR | yes |
| more than `concept_max_blocks` blocks | WARN | no, split by hand |
| an `index.md` missing, stale, or the root without `okf_version` | ERROR | yes, regenerates it |
| an `index.md` of a directory without concepts | WARN | yes, deletes it |
| `log.md` missing | ERROR | yes |
| empty directory | WARN | yes, removes it |
| a non-`.md` file under `specs/` | WARN | no |

### change

| Finding | Level | Fixable |
|---|---|---|
| `intent.md`, `plan.md` or `tasks.md` lacks its `type:` | WARN | yes |
| flat delta `specs/<cap>.md` (legacy) | WARN | yes, moves to `specs/<cap>/<cap>.md` (not if that file exists) |
| delta at the wrong depth | ERROR | no |
| delta name not kebab-case | ERROR | no |
| delta front matter incomplete (`type`, `target`, `sources`) | WARN | yes |
| `index.md` missing or stale | WARN | yes, regenerates it |

`--fix` never changes the text of a requirement. It is idempotent: a second run prints `0 fixed`. Output ends with `OK|FAIL <target>: <n> errors, <n> warnings`, plus `, <n> fixed` with `--fix`; exit 1 on any ERROR.

`sdd check <change>` runs `bundle <change>` and prefixes the findings with `bundle:`. `sdd sync` additionally refuses while `bundle specs` has errors.

## Migrate the legacy layout

The older layout had one long `specs/<capability>/spec.md` and flat deltas `changes/<id>/specs/<capability>.md`. Both are read and repaired by `--fix`:

1. `bundle specs --fix` once, on the base branch (lead).
2. `bundle <id> --fix` for every open change (lead or spec-author).

A migrated spec keeps all its blocks in a single concept named after the capability. If it has more than `concept_max_blocks` blocks, `bundle specs` warns; regroup it by topic through a change (see [Write a delta](../how-to/write-a-delta-and-adr.md#group-requirements-into-concepts)). Steps and output: [Migrate to the OKF layout](../how-to/migrate-to-okf-layout.md).
