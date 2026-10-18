---
type: How-to Guide
title: Write a spec delta and an ADR
description: Add a capability or an invariant, add, modify or retire acceptance criteria of an existing capability, replace a section, deprecate a concept, and record or supersede a decision as an ADR.
tags: [sdd, how-to, delta, capability, invariant, adr, spec]
sources:
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../tools/sdd.py
  - resource: ../../agents/spec-author.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Write a spec delta and an ADR

The spec-author normally does this. Follow these steps to review its work, or to write a delta yourself as the lead. Formats: [File formats](../reference/file-formats.md).

## Add a capability

1. Create it from the Capability template (the repo's `specs/.templates/capability.md.tmpl` if it has one):
   ```
   sdd delta-new add-greeting capabilities/greeting --title "Greeting"
   ```
   ```
   created changes/add-greeting/specs/capabilities/greeting.md (new Capability)
   ```
2. Fill every `<placeholder>`: description, Intent (`As a <actor>, I can <action>, so that <outcome>.`), Scope, and the criteria:

   ```markdown
   ### AC-01: Greet a named user

   - **Given** no configuration
   - **When** the user runs `greet --name Ada`
   - **Then** stdout is `Hello, Ada!` and the exit code is 0
   ```

   One observable behavior per criterion, concrete values, and the unhappy paths that matter. Number from AC-01.
3. Link the invariants it must preserve and its ADRs under Invariants and Decisions, relative to `specs/capabilities/`. Fill Verification once the tests exist, or leave the planned path.

Leave `status: draft`: `sync` sets `stable` when the change is verified.

## Change an existing capability

1. Start a CapabilityDelta. It prints the next free criterion id:
   ```
   sdd delta-new polite-greeting capabilities/greeting
   ```
   ```
   created changes/polite-greeting/specs/capabilities/greeting.md (CapabilityDelta; next free AC-02)
   ```
2. New criteria go under `## ADDED`, numbered from that id. Never reuse an id, even a retired one.
3. Stub every unit you change. Never copy it by hand:
   ```
   sdd delta-stub polite-greeting capabilities/greeting#AC-01
   ```
   ```
   MODIFIED capabilities/greeting#AC-01 base=f1452e6a -> changes/polite-greeting/specs/capabilities/greeting.md
   ```
   Edit the copy into the **complete** new criterion. Leave the `<!-- base: -->` line alone.
   - Retire a criterion: `delta-stub ... capabilities/greeting#AC-01 --retire`, then replace `<why it is retired>`. The living file keeps `### AC-01: <name>` with the reason, so the id stays taken.
   - Replace a section (Title, Description, Intent, Scope, Invariants, Decisions, Verification): `delta-stub ... capabilities/greeting --section Scope`, then edit the whole section.
   - Deprecate the capability: `delta-stub ... capabilities/greeting --deprecate`. All its criteria retire; remove their tests in the same change.
4. Delete the sections of the delta you left empty.

Two changes conflict only when they touch the same unit: a criterion, a section, or the whole capability for a deprecation.

## Add, change or deprecate an invariant

An invariant is a rule that holds for the whole system at all times (security, data integrity, performance budgets), not one feature's behavior. One rule per file.

1. ```
   sdd delta-new add-redaction invariants/tokens_redacted --title "Tokens are redacted"
   ```
2. Fill Statement (`<Subject> must always / must never <condition>.`), Scope, Rationale, Enforcement (`- Check:` the test, lint rule or gate, and where it runs) and both Examples: the check must pass on Holds and fail on Violation.
3. Change an existing one by replacing it whole:
   ```
   sdd delta-stub redact invariants/no_secret_in_logs
   ```
   ```
   REPLACE invariants/no_secret_in_logs base=1f01a9f3 -> changes/redact/specs/invariants/no_secret_in_logs.md
   ```
   Add `--deprecate` to drop it (record why in an ADR). `check` then warns for every capability that still lists it: replace their Invariants section.
4. The change needs a `(test)` task citing `invariants/<id>`, and no `(impl)` task. `sdd context` shows implementers the title and statement of every invariant in force.

## Check

Repair what can be repaired, then check the traceability:

```
bundle  {"target": "<id>", "fix": true}
sdd check <id>
```

The `bundle` tool (`mcp__sdd__bundle`) fixes front matter and the generated indexes, never the text of a criterion or invariant; see [OKF bundles](../reference/bundles.md). `sdd check` reports the structure of every new concept and delta, placeholders left, and any remaining bundle problem prefixed `bundle:`.

Fix every ERROR and every placeholder WARN. For the meaning of each one, see [check rules](../reference/cli.md#check-rules).

## Record a decision

Write an ADR only if there is a real rejected alternative **and** a consequence that outlives the change. Otherwise put a line in `plan.md`.

1. ```
   sdd adr-new "Use argparse for the CLI"
   ```
   ```
   ADR-0001 -> adrs/0001_use_argparse_for_the_cli.md
   ```
2. Fill in Context, Decision drivers, Options considered (at least two), Decision, Consequences and Related. Write Decision so it stands alone: implementers receive only that section.
3. List it in `intent.md`: `adrs: [ADR-0001]`, and link it from the capability's Decisions section (`- [Use argparse for the CLI](../../adrs/0001_use_argparse_for_the_cli.md)`).

`sdd sync` accepts it (`status: stable`) when the change is archived.

## Change an accepted decision

Accepted ADRs are immutable, and the guard refuses edits to them. Supersede instead:

```
sdd adr-new "Use click for the CLI" --supersedes ADR-0001
```

When the new ADR is accepted, the old one becomes `deprecated` with `superseded_by: 0002_use_click_for_the_cli`. `sdd check` then errors on any reference to the old one: reference the successor.
