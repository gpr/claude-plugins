---
type: How-to Guide
title: Write a spec delta and an ADR
description: Add, modify, remove and regroup requirements and invariants in a change's delta files, and record or supersede a decision as an ADR.
tags: [sdd, how-to, delta, invariant, adr, spec]
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

1. Create the delta file for a concept of the capability (`<capability>/<concept>`; the concept defaults to the capability name):
   ```
   sdd delta-new add-greeting greeting/named
   ```
   ```
   created changes/add-greeting/specs/greeting/named.md
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
4. Keep the file short: at most 5 blocks (`concept_max_blocks`). See [Group requirements into concepts](#group-requirements-into-concepts).

## Modify or remove a requirement

1. Stub it. Never copy it by hand:
   ```
   sdd delta-stub polite-greeting REQ-GREET-001
   ```
   ```
   MODIFIED REQ-GREET-001 base=f1452e6a -> changes/polite-greeting/specs/greet/greeting.md
   ```
   The entry lands in the delta file that mirrors the living concept, created from the template if needed.
   Add `--remove` for a REMOVED entry, then replace `Reason: <why it is removed>`.
2. Edit the copied text into the **complete** new requirement, scenarios included. Leave the `<!-- base: -->` line alone.

## Group requirements into concepts

A capability is a directory of short concept files, one per topic: `specs/auth/tokens.md`, `specs/auth/lockout.md`. A delta file targets one of them, by path: `changes/<id>/specs/auth/tokens.md`.

- New topic: `sdd delta-new <id> auth/lockout` and ADD the REQs there.
- Too many blocks in a concept (`bundle` warns above 5): split the topic. To move an existing REQ to another concept of the same capability, `delta-stub` it, then cut the MODIFIED entry from its delta file and paste it into the delta file of the target concept (create it with `delta-new`). At `sdd sync` it prints `MOVED REQ-AUTH-001`. A REQ cannot move to another capability.

## Add an invariant

An invariant is a rule that holds for the whole system at all times (security, data integrity, performance budgets), not one feature's behavior. It lives under `invariants/<category>`:

1. ```
   sdd delta-new add-redaction invariants/security/redaction
   ```
2. Under `## ADDED`, write it with a `#### Check:` instead of a scenario:
   ```markdown
   ### INV-SEC-002: Tokens are redacted in error reports
   The system MUST replace a token with `***` in every error report.

   #### Check: test_error_report_redacts_token
   ```
3. Modify or remove one with `sdd delta-stub <id> INV-SEC-001 [--remove]`, as for a REQ:
   ```
   MODIFIED INV-SEC-001 base=1f01a9f3 -> changes/redact/specs/invariants/security/logging.md
   ```
4. The change needs a `(test)` task naming the INV, and no `(impl)` task. `sdd context` shows implementers the title of every invariant in force.

## Check

Repair the layout first, then check the traceability:

```
bundle  {"target": "<id>", "fix": true}
sdd check <id>
```

The `bundle` tool (`mcp__sdd__bundle`) fixes front matter, delta locations and the generated `index.md`, never a requirement's text; see [OKF bundles](../reference/bundles.md). `sdd check` also reports any remaining bundle problem, prefixed `bundle:`.

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
