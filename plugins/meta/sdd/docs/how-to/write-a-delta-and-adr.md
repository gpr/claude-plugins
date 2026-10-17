---
type: How-to Guide
title: Write a spec delta and an ADR
description: Add, modify and remove requirements in a change's delta, and record or supersede a decision as an ADR.
tags: [sdd, how-to, delta, adr, spec]
sources:
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../tools/sdd.py
  - resource: ../../agents/spec-author.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Write a spec delta and an ADR

The spec-author normally does this. Follow these steps to review its work, or to write a delta yourself as the lead.

## Add a requirement

1. Create the delta for the capability:
   ```
   sdd delta-new add-greeting greeting
   ```
2. Under `## ADDED`, write the block. Find the next free number with
   `grep -ho "REQ-GREET-[0-9]*" specs changes -r | sort -u | tail -1`.

   ```markdown
   ### REQ-GREET-001: Greet a named user
   The CLI MUST print `Hello, <name>!` when run with `--name <name>`.

   #### Scenario: named greeting
   - GIVEN no configuration
   - WHEN the user runs `greet --name Ada`
   - THEN stdout is `Hello, Ada!` and the exit code is 0
   ```

   One behavior per REQ, MUST / MUST NOT / SHOULD, concrete values, and unhappy paths that matter.
3. Delete the sections you left empty.

## Modify or remove a requirement

1. Stub it. Never copy it by hand:
   ```
   sdd delta-stub polite-greeting REQ-GREET-001
   ```
   ```
   MODIFIED REQ-GREET-001 base=f1452e6a -> changes/polite-greeting/specs/greeting.md
   ```
   Add `--remove` for a REMOVED entry, then replace `Reason: <why it is removed>`.
2. Edit the copied text into the **complete** new requirement, scenarios included. Leave the `<!-- base: -->` line alone.

## Check

```
sdd check <id>
```

Fix every ERROR. For the meaning of each one, see [check rules](../reference/cli.md#check-rules).

## Record a decision

Write an ADR only if there is a real rejected alternative **and** a consequence that outlives the change. Otherwise put a line in `plan.md`.

1. ```
   sdd adr-new "Use argparse for the CLI"
   ```
   ```
   ADR-0001 -> adr/ADR-0001-use-argparse-for-the-cli.md
   ```
2. Fill in Context, Options (at least two), Decision and Consequences. Write Decision so it stands alone: implementers receive only that paragraph.
3. List it in `intent.md`: `adrs: [ADR-0001]`.

`sdd sync` accepts it when the change is archived.

## Change an accepted decision

Accepted ADRs are immutable, and the guard refuses edits to them. Supersede instead:

```
sdd adr-new "Use click for the CLI" --supersedes ADR-0001
```

When the new ADR is accepted, the old one becomes `superseded` with `superseded_by: ADR-0002`. `sdd check` then errors on any reference to the old one: reference the successor.
