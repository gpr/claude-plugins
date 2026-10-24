---
name: formats
description: File formats and writing rules for Capability and Invariant concepts, capability deltas, ADRs and tasks in the spec-driven workflow. Preloaded by the workflow subagents; read it before writing any of those files.
user-invocable: false
---

# SDD formats

All paths are relative to the repo root. `sdd <args>` means a call to the `mcp__sdd__sdd` tool
with `args` as a list (`sdd check c1` is `{"args": ["check", "c1"]}`).
The tool is the source of truth for structure: when in doubt, run `sdd check <change>`.

## Layout
`specs/`, `adrs/` and each `changes/<change>/` are OKF (Open Knowledge Format v0.2) bundles:
a root `index.md` with `okf_version: "0.2"`, a `log.md`, concept files with front matter.
A concept's id is its path below the bundle without `.md`, in lowercase snake_case.
```
specs/capabilities/<id>.md                 living Capability (type: Capability), e.g. capabilities/reports/export_report
specs/invariants/<id>.md                   living Invariant (type: Invariant), one rule per file
specs/.templates/{capability,invariant}.md.tmpl   the templates delta-new fills (the repo may edit them)
changes/<change>/intent.md                 why, scope, non-goals, success criteria (front matter: type, status, adrs)
changes/<change>/specs/capabilities/<id>.md   a new Capability, or a CapabilityDelta of an existing one
changes/<change>/specs/invariants/<id>.md     a new Invariant, or the full replacement of one
changes/<change>/plan.md                   how: approach, contracts, components
changes/<change>/tasks.md                  checklist, the only file edited during implementation
changes/<change>/state.json                phase, branch, base, PR number, requires (written only by `sdd.py`; never edit)
adrs/NNNN_<slug>.md                        one decision per file (type: ADR), cited as ADR-NNNN
tests/acceptance/                          acceptance tests, citing criterion and invariant ids
```
- `specs/`, `adrs/` and every `index.md`/`log.md` are written only by `sdd` (sync, adr-new,
  adr-accept, `bundle --fix`, delta-new/stub). Never edit them.
- A delta file sits at the path of the living concept it creates or changes.
- The spec-author runs `bundle` (the `mcp__sdd__bundle` tool, `target` = change id) before
  handing a change back; `fix: true` repairs what it marks fixable.

## Citing units
The traceable units are acceptance criteria and invariants:
- criterion: `capabilities/<id>#AC-NN`, e.g. `capabilities/reports/export_report#AC-02`
- invariant: `invariants/<id>`, e.g. `invariants/no_secret_in_logs`

Tasks, plan.md and acceptance tests cite these exact strings. A bare `capabilities/<id>`
is not a unit: cite its criteria.

## Capability
Create it with `sdd delta-new <c> capabilities/<id> --title "<name>"` (the Capability
template, from `specs/.templates/` if the repo has one). Fill every `<placeholder>`:
```
---
type: Capability
title: "Export report"
description: "A user can download any report as a CSV file."
status: draft
tags: []
generated: {by: ..., at: ...}      # filled by delta-new; sync updates `at`
sources: []                        # `- resource: src/reports/export.py` entries: code it covers
---

# Export report

## Intent
As a <actor>, I can <action>, so that <outcome>.

## Scope
- In: ...
- Out: ...

## Acceptance criteria

### AC-01: CSV download

- **Given** a report with 2 rows
- **When** the user clicks Export
- **Then** a CSV with a header and 2 rows is downloaded

## Invariants
- [No secret in logs](../invariants/no_secret_in_logs.md)    # links relative to specs/capabilities/<id>.md

## Decisions
- [Use CSV for exports](../../adrs/0003_use_csv_for_exports.md)

## Verification
- Tests: `tests/acceptance/test_export.py`
- Run: `<command>`
```
Rules:
- One criterion = one observable behavior = one executable acceptance test. Inputs and
  outputs at the system boundary, no implementation detail. Concrete values, no "valid
  input", no "works correctly". Cover the unhappy paths that matter (errors, limits,
  permissions).
- Every live criterion has **Given**, **When** and **Then** lines (`- **And** ...` may follow).
- **Baseline** (existing code): a new criterion that writes down behavior the code already
  has, and this change keeps, ends with `- **Baseline**: <where it lives, e.g. src/reports/export.py>`.
  It needs a `(test)` task and no `(impl)` task; its acceptance test must pass on the
  current code. Only in a new capability or under ADDED, never on MODIFIED or RETIRED.
  Behavior the change alters is never Baseline. `sync` drops the line.
- `intent.md` `size`: `change` (default), `fix` (a test on an existing criterion, no delta) or
  `baseline` (an adopt: only Baseline criteria and new invariants, only `(test)` tasks).
- IDs `AC-NN` are stable: never renumber, never reuse. A removed criterion is retired, not
  deleted: it stays as `### AC-NN: <name>` with `- **Retired**: <reason>`.
- Links in Invariants and Decisions are relative to the living path (`specs/capabilities/...`).
  `check` warns when one resolves to nothing.
- Leave `status: draft` in a delta: `sync` sets `stable` once the change is verified.

## Invariant
A rule that holds for the whole system at all times, not one feature's behavior (security,
data integrity, performance budgets, compatibility). One rule per file. Create it with
`sdd delta-new <c> invariants/<id> --title "<name>"`:
```
## Statement
<Subject> must always / must never <condition>.
## Scope
## Rationale
- Decided in: [<ADR title>](../../adrs/NNNN_<slug>.md)
## Enforcement
- Check: `<test, lint rule or gate>` at `<path>`, or `manual` with the reason
- Runs: <CI | pre-commit | runtime | review>
## Examples
### Holds
- **Given** <state that respects it>
- **Then** the check passes
### Violation
- **Given** <state that breaks it>
- **Then** the check fails with <expected message>
## Exceptions
None.
```
The check must pass on Holds and fail on Violation. An invariant needs at least one `(test)`
task and no `(impl)` task. Implementers get the titles and statements of all invariants in
force with `sdd context`.

## Changing what exists
Never copy living text by hand and never type a base hash: `delta-stub` copies the current
text with its `<!-- base: xxxxxxxx -->`. A base that no longer matches fails `check` with
CONFLICT: that is a real conflict with another change, report it, do not "fix" the hash.

An existing **capability** is changed with a CapabilityDelta, merged by `sync` one unit at
a time. `sdd delta-new <c> capabilities/<id>` creates it (and prints the next free AC id):
```
---
type: CapabilityDelta
title: "Delta: Export report"
target: specs/capabilities/reports/export_report.md
sources: []
---

## ADDED
### AC-04: ...                       full new criterion, id above every existing one

## MODIFIED
### AC-02: ...                       `sdd delta-stub <c> <cap>#AC-02`, then edit the copy
<!-- base: 1a2b3c4d -->

## RETIRED
### AC-03: ...                       `sdd delta-stub <c> <cap>#AC-03 --retire`
<!-- base: 9f8e7d6c -->
- **Retired**: <why>

## SECTIONS
### Scope                            `sdd delta-stub <c> <cap> --section Scope`
<!-- base: 5e6f7a8b -->
(the complete new section)
```
- SECTIONS takes Title, Description, Intent, Scope, Invariants, Decisions, Verification, each
  at most once (a section's own `###` sub-headings stay inside its entry);
  each entry replaces the whole section (Title and Description: the front matter line).
- MODIFIED holds the complete new criterion. Sync replaces the whole block.
- `sdd delta-stub <c> <cap> --deprecate` deprecates the capability: all its criteria retire.
- Delete the sections you leave empty.

An existing **invariant** is replaced as a whole: `sdd delta-stub <c> invariants/<id>`
copies it with `base:` in its front matter; edit the copy. `--deprecate` marks it
`status: deprecated` (record why in an ADR). Capabilities that list it get a warning: replace
their Invariants section.

## ADR
Create with `sdd adr-new "<title>" [--supersedes ADR-NNNN]` (adrs/NNNN_<slug>.md from the ADR
template), then fill Context, Decision drivers, Options considered, Decision, Consequences,
Related. Write one only if there is a real rejected alternative AND a consequence that
outlives this change. Otherwise it is a line in plan.md.
Status: `draft` (proposed) -> `stable` (accepted, by `sdd adr-accept` or sync) ->
`deprecated` (superseded, `superseded_by` set). An accepted ADR is immutable: change a
decision by superseding it. List the change's ADRs in `intent.md` front matter
`adrs: [ADR-0007]` and link them from the capability's Decisions section.
`## Decision` must be self-contained: it is the only part implementers receive.

## Tasks line
```
- [ ] T2 (impl) Reject expired tokens in middleware — capabilities/auth/tokens#AC-04 ADR-0007 | blocked-by: T1 | files: src/auth/mw.py
```
Kinds: `test`, `impl`, `chore`. Cite ids, never restate criterion text.
A Baseline criterion gets a `(test)` task only.

## Acceptance test tagging
Every acceptance test cites the ids it covers, exactly, in its name, a docstring or a
comment: `# capabilities/auth/tokens#AC-04` or `# invariants/no_secret_in_logs`. A test
name cannot hold `/` or `#`, so use a docstring or comment.
