---
type: Reference
title: OKF bundles
description: The OKF v0.2 layout of specs/, adrs/ and each change, the index and log formats, the checks of sdd bundle and which ones --fix repairs, and what happens to the old REQ/INV format.
tags: [sdd, reference, okf, bundle, specs, capabilities, invariants, adrs]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# OKF bundles

`specs/`, `adrs/` and each open change `changes/<id>/` are [OKF v0.2](https://docs.rs/okf) bundles: a root `index.md` declaring `okf_version: "0.2"`, a `log.md`, one Markdown file per concept with a `type` in its front matter. `sdd.py` writes the indexes and the logs; nobody edits them. The `bundle` subcommand ([sdd subcommands](cli.md#checks-and-context)) and the `mcp__sdd__bundle` tool ([roles](sdd-tool-roles.md#the-bundle-tool)) validate and repair them. Synced bundles pass `okf validate`.

## Layout

```
specs/index.md                              okf_version "0.2", then the okf index of the directory
specs/log.md                                one `* **Update**:` line per sync, under `## YYYY-MM-DD`
specs/capabilities/<id>.md                  type: Capability
specs/invariants/<id>.md                    type: Invariant
specs/.templates/*.md.tmpl                  concept templates; dot-directories are not part of the bundle
adrs/index.md, adrs/log.md                  log: one line per accepted ADR
adrs/NNNN_<slug>.md                         type: ADR
adrs/.templates/adr.md.tmpl

changes/<id>/index.md                       okf_version "0.2", then the okf index
changes/<id>/intent.md, plan.md, tasks.md   type: intent / plan / tasks
changes/<id>/specs/capabilities/<id>.md     type: Capability (new) or CapabilityDelta
changes/<id>/specs/invariants/<id>.md       type: Invariant (new or replacement)
```

- `index.md` and `log.md` are reserved names, never concepts. Every other `.md` file outside a dot-directory is a concept.
- Concept ids are lowercase snake_case path segments, any depth below `capabilities/` or `invariants/` (`capabilities/reports/export_report`). The tree must match the type.
- Archived changes keep their files as they were; they are not checked.

## Index and log format

Every directory holding a concept at any depth gets an `index.md`, written the way `okf index` writes it: entries grouped under a `# <type>` heading (types sorted, subdirectories under `# Subdirectories`), sorted by title, each `* [<title>](<link>) - <description>`. A subdirectory's description is its single entry's description, else `Contains N entries: <titles>.`. Only the root index has front matter, and only `okf_version`. Unlike `okf index`, dot-directories such as `.templates/` are left out (lintel's `okf-index.sh` strips them the same way).

A log is `# Update Log`, then `## YYYY-MM-DD` groups, newest first, of `* **<Kind>**: <text>` lines. `init` opens it with a `**Creation**` entry: okf rejects a log without a date group.

## Bundle checks

`bundle specs`, `bundle adrs` and `bundle <id>`. With `--fix`, a finding marked `[fixable]` is repaired and printed as `FIXED <message>` instead.

### specs

| Finding | Level | Fixable |
|---|---|---|
| `specs/` missing | ERROR | yes, creates it |
| a concept in the old REQ/INV format | ERROR | no: rewrite it as a Capability or Invariant |
| a concept outside `capabilities/` or `invariants/`, or not snake_case | ERROR | no |
| type does not match the tree | ERROR | no |
| no `title` | ERROR | yes, from the `#` heading |
| no `description` | WARN | no |
| `status` not draft/stable/deprecated | ERROR | no |
| a missing required section, an empty Intent or Scope | ERROR | no |
| no live criterion (capability not deprecated) | ERROR | no |
| a criterion twice, or without Given/When/Then | ERROR | no |
| criteria not sorted by number | ERROR | yes |
| invariant without Statement, `- Check:`, Holds or Violation | ERROR | no |
| no Rationale or Exceptions | WARN | no |
| a link that resolves to nothing or to a deprecated concept | WARN | no |
| a template placeholder left | WARN | no |
| `sources` as plain strings | WARN | yes, as `- resource:` entries |
| a `sources` entry not found | WARN | yes, drops it |
| an `index.md` missing or stale | ERROR | yes, regenerates it |
| an `index.md` of a directory without concepts | WARN | yes, deletes it |
| `log.md` missing, or without a date group | ERROR | yes |
| `log.md` with old sdd lines (`- <date> ...`) | WARN | no |
| empty directory | WARN | yes, removes it |
| a non-`.md` file | WARN | no |

### adrs

| Finding | Level | Fixable |
|---|---|---|
| `adrs/` missing | ERROR | yes |
| a file not named `NNNN_<slug>.md` (the old `ADR-NNNN-<slug>.md` gets the new name in the message) | ERROR | no |
| two files with the same number | ERROR | no |
| type not ADR, status not draft/stable/deprecated, no title | ERROR | no |
| `supersedes` or `superseded_by` naming no ADR | ERROR | no |
| deprecated without `superseded_by` | WARN | no |
| no `## Decision` | ERROR | no |
| no Context or Consequences | WARN | no |
| index or log as for specs | ERROR | yes |

### change

| Finding | Level | Fixable |
|---|---|---|
| `intent.md`, `plan.md` or `tasks.md` lacks its `type:` | WARN | yes |
| a delta in the old format | ERROR | no |
| a delta outside `specs/capabilities/` or `specs/invariants/`, or not snake_case | ERROR | no |
| a delta type that does not fit its tree | ERROR | no |
| CapabilityDelta without the right `target`, or `sources` not as entries | WARN | yes |
| an `index.md` missing or stale | WARN | yes; `checkpoint` and `sync` regenerate them anyway |

The structure of the delta's concepts and units is checked by `sdd check`, not by `bundle`. `--fix` never changes the text of a criterion, section or invariant. It is idempotent: a second run prints `0 fixed`. Output ends with `OK|FAIL <target>: <n> errors, <n> warnings`, plus `, <n> fixed` with `--fix`; exit 1 on any ERROR.

`sdd check <change>` runs `bundle <change>` and prefixes the findings with `bundle:`. `sdd sync` additionally refuses while `bundle specs` has errors.

## The old REQ/INV format

Earlier sdd versions wrote a living spec as a few `### REQ-<CAP>-NNN` blocks per `specs/<capability>/<concept>.md` and invariants were `### INV-<CAT>-NNN` blocks. They are not migrated: one REQ with several scenarios does not map one-to-one onto acceptance criteria, so a conversion would need review anyway. `bundle` reports each such file as an error; [Migrate to Capability and Invariant concepts](../how-to/migrate-to-okf-layout.md) gives the steps.
