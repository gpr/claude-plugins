---
type: How-to Guide
title: Migrate to Capability and Invariant concepts
description: Move a project from the old REQ/INV block specs and ADR-NNNN files to Capability, Invariant and ADR concepts, by hand, once, on the base branch.
tags: [sdd, how-to, migration, okf, bundle, capability, invariant, adr]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../skills/formats/SKILL.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Migrate to Capability and Invariant concepts

Use this when `specs/` still holds `### REQ-<CAP>-NNN` or `### INV-<CAT>-NNN` blocks, or `adr/` holds `ADR-NNNN-<slug>.md` files. `bundle specs` reports each old concept as `old sdd format (REQ/INV blocks)`, and `sdd sync` refuses until none is left. There is no automatic migration: a REQ with several scenarios does not map one-to-one onto criteria, and the result needs your review anyway.

The guard refuses writes under `specs/` even to the lead, so do this outside the workflow: in a plain editor or shell on the base branch, in one commit (or disable the plugin for that session).

## 1. Rewrite the specs

`sdd init` copies the templates into `specs/.templates/` and `adrs/.templates/` if they are missing. For each old concept file:

1. Decide the capabilities it holds: one per thing an actor can do. A capability is often one old concept file, sometimes a whole old capability directory.
2. Copy `specs/.templates/capability.md.tmpl` to `specs/capabilities/<id>.md` (snake_case id), fill the front matter (`status: stable`, since it is implemented), Intent and Scope.
3. Turn each REQ into one or more criteria: usually one per `#### Scenario:`, `GIVEN/WHEN/THEN` becoming `- **Given**`, `- **When**`, `- **Then**`. The REQ's MUST sentence goes into the criterion name or into Scope. Number them AC-01, AC-02, ... in the order you want to keep: ids are never renumbered afterwards.
4. Turn each INV block into its own `specs/invariants/<id>.md` from `invariant.md.tmpl`: the MUST sentence is the Statement, `#### Check:` becomes `- Check:` under Enforcement, and add a Holds and a Violation example.
5. Delete the old file.

Keep a mapping `REQ-AUTH-001 -> capabilities/auth/login#AC-01` while you go.

## 2. Re-tag the acceptance tests

Replace every REQ and INV id in `tests/acceptance/` with its new citation from the mapping (`# capabilities/auth/login#AC-01`, `# invariants/no_secret_in_logs`). Fill each capability's Verification section with the test paths.

## 3. Move the ADRs

For each `adr/ADR-NNNN-<slug>.md`: rename it `adrs/NNNN_<slug>.md` (dashes in the slug become underscores), and rewrite its front matter after `adrs/.templates/adr.md.tmpl`: `type: ADR`, `title`, `description`, `status` (`proposed` → `draft`, `accepted` → `stable`, `superseded` or `deprecated` → `deprecated`), `decided` (the old `date`), `supersedes: [<concept id>]` and `superseded_by: <concept id>` (`0003_use_jwt`, not `ADR-0003`). `ADR-NNNN` stays the citation in tasks and intents. A `.claude/sdd.json` written by an older `sdd init` sets `"adr_dir": "adr"`: keep it to stay in `adr/` (the files still need the new names), or move the files to `adrs/` and drop the key. Its `inv_id_pattern` and `concept_max_blocks` keys are no longer read; delete them.

## 4. Regenerate and check

```
python3 <plugin>/tools/sdd.py bundle specs --fix
python3 <plugin>/tools/sdd.py bundle adrs --fix
```

`--fix` regenerates every `index.md` in the okf format, adds a date group to a log that has none, sorts criteria and rewrites plain-string `sources`. Fix by hand what stays an ERROR, until both print `OK`. If `okf` is installed, `okf validate specs` and `okf validate adrs` should pass too. Commit and push.

## 5. Open changes

A change opened before the migration has old-format deltas, which `bundle <id>` reports as errors. Merge the migrated base into its branch (`sdd resume <id>` or `checkpoint --phase ...` do it once the base moved), then resume the spec-author to rewrite the delta as new concepts or CapabilityDeltas with `delta-new` and `delta-stub`, and the planner to update the citations in `tasks.md` and `plan.md`. Then Gate 1 again: the text changed form.

Archived changes are history: leave them as they are.
