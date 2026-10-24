---
type: Reference
title: File formats
description: Exact syntax sdd.py parses - Capability and Invariant concepts, acceptance criteria, CapabilityDelta sections and base markers, intent and ADR front matter, task lines and acceptance test citations.
tags: [sdd, reference, formats, capability, invariant, adr, tasks]
sources:
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../skills/change/templates/intent.md
  - resource: ../../skills/change/templates/capability.md.tmpl
  - resource: ../../skills/change/templates/invariant.md.tmpl
  - resource: ../../skills/change/templates/capability-delta.md
  - resource: ../../skills/change/templates/adr.md.tmpl
  - resource: ../../skills/change/templates/plan.md
  - resource: ../../skills/change/templates/tasks.md
  - resource: ../../tools/sdd.py
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# File formats

The `sdd:formats` skill holds the writing rules and is preloaded into spec-author, planner and acceptance-tester. This page states what `sdd.py` actually parses. The Capability, Invariant and ADR formats are the concept templates of the lintel repository (`specs/.templates/`, `adrs/.templates/`), shipped in `skills/change/templates/` and copied into a repo by `sdd init`.

## Ids and citations

A concept id is the file's path below its bundle without `.md`: lowercase snake_case segments, `capabilities/<...>` or `invariants/<...>` under `specs/`. The traceable units are:

| Unit | Citation | Example |
|---|---|---|
| acceptance criterion | `<capability id>#AC-NN` | `capabilities/reports/export_report#AC-02` |
| invariant | `<invariant id>` | `invariants/no_secret_in_logs` |
| ADR | `ADR-NNNN` | `ADR-0003` → `adrs/0003_use_csv.md` |

A citation is matched as a whole: `specs/capabilities/x#AC-01` (preceded by `/`) and `capabilities/x#AC-010` do not cite `capabilities/x#AC-01`. A bare `capabilities/<id>` is not a unit; `check` errors when a task names one.

## Front matter

Parsed as a small YAML subset: `key: value` scalars (plain, `"double"` or `'single'` quoted, also over several lines, and `|` / `>` block scalars with `-`/`+` chomping), flow lists `[a, b]` and mappings `{k: v}` (nested, `null` kept), and one level of indented block (`generated:` with `by`/`at`, `sources:` as `- resource: <path>` entries). Keys sdd does not manage round-trip unchanged. `sources` given as plain strings are read as their `resource`; `bundle --fix` rewrites them as entries.

## Capability

`specs/capabilities/<id>.md`:

```markdown
---
type: Capability
title: "Export report"
description: "A user can download any report as a CSV file."
status: stable          # draft | stable | deprecated
tags: []
generated:
  by: human:jdoe        # OKF_AUTHOR, else human:<git user.name>, else process:sdd
  at: "2026-10-18T10:00:00Z"
sources:
  - resource: src/reports/export.py
---

# Export report

## Intent
## Scope
## Acceptance criteria

### AC-01: CSV download

- **Given** a report with 2 rows
- **When** the user clicks Export
- **Then** a CSV with a header and 2 rows is downloaded

### AC-02: Empty report

- **Retired**: empty reports are no longer exportable

## Invariants
## Decisions
## Verification
```

- Sections are lines `## <name>` outside HTML comments. Intent, Scope and Acceptance criteria are required; Intent and Scope must not be empty.
- A criterion starts at `### AC-NN: <name>` (two or more digits) and runs to the next `###` or `##` heading. Any other `###` heading under Acceptance criteria is an error: sync would not keep what it holds. A live criterion needs lines starting `- **Given**`, `- **When**` and `- **Then**`. A retired one holds `- **Retired**: <reason>` instead and stays forever, so its id is never reused.
- A new criterion (in a new capability, or under ADDED) may end with `- **Baseline**: <where it lives, e.g. src/reports/export.py>`: it writes down behavior the code already has and the change keeps. It needs a `(test)` task and no `(impl)` task, and its acceptance test must pass on the current code. `sync` drops the line, so a living criterion never has one. See [Adopt sdd in an existing repository](../how-to/adopt-an-existing-repo.md).
- Criteria are kept sorted by number; sync and `bundle --fix` reorder them.
- Links in Invariants, Decisions and (for an invariant) Rationale are resolved relative to the living file; one that resolves to nothing, or to a deprecated concept, is a warning. A link there to `adrs/NNNN_<slug>.md` counts as citing `ADR-NNNN`.
- A deprecated capability needs no live criterion.

## Invariant

`specs/invariants/<id>.md`, same front matter with `type: Invariant`, then sections Statement, Scope, Rationale, Enforcement, Examples, Exceptions:

- Statement must not be empty; Enforcement needs a line starting `- Check:`.
- Examples needs `### Holds` and `### Violation`, each with `- **Given**` and `- **Then**` lines. The check must pass on Holds and fail on Violation.
- A missing Rationale or Exceptions is a warning.

## Placeholders

A line that still holds a template placeholder (`<actor>`, `<initial state>`, a link target `(<relative path>.md)`; code spans and comments ignored) is a warning, at most three per file.

## Deltas

Files under `changes/<change>/specs/`, at the path of the living concept. Three kinds:

| File | When | Sync |
|---|---|---|
| `type: Capability` or `Invariant`, no living concept | a new concept | written to `specs/`, status `stable` |
| `type: Invariant` with `base:` in front matter | replaces a living invariant | whole file replaced; `status: deprecated` deprecates it |
| `type: CapabilityDelta` | changes a living capability | merged unit by unit |

A full `Capability` over a living one is an error: change it with a CapabilityDelta.

### CapabilityDelta

```markdown
---
type: CapabilityDelta
title: "Delta: Export report"
target: specs/capabilities/reports/export_report.md
sources: []
---

## ADDED

### AC-04: ...

## MODIFIED

### AC-01: CSV download
<!-- base: 1a2b3c4d -->
(complete new criterion)

## RETIRED

### AC-03: Filename
<!-- base: 9f8e7d6c -->
- **Retired**: <reason>

## SECTIONS

### Scope
<!-- base: 5e6f7a8b -->
(complete new section)
```

- Sections are lines exactly `## ADDED`, `## MODIFIED`, `## RETIRED`, `## SECTIONS` (case included); any other `##` section is an error, and so is a `###` heading under ADDED/MODIFIED/RETIRED that is not a criterion. HTML comments other than base markers are ignored.
- ADDED ids must not exist in the living capability, retired ones included. MODIFIED and RETIRED ids must exist, be live, and carry the base of the living criterion. RETIRED needs a reason.
- SECTIONS entries are `### <name>` with one of Title, Description, Intent, Scope, Invariants, Decisions, Verification; any other `###` line inside an entry is part of it, so a section keeps its own sub-headings. Each name at most once; Title and Description replace the front matter value (Title also the `#` heading). An entry needs the base of the current section when the capability has it.
- Front matter `status: deprecated` plus `base:` (the whole capability's hash) deprecates it; all its live criteria count as retired, and no ADDED or MODIFIED is allowed.
- `sources` are merged (union, sorted by resource) into the capability at sync.

### Base hash

The first 8 hex chars of sha256 over the unit's text with HTML comments removed, trailing spaces stripped and blank lines at both ends dropped. The unit is a criterion block (heading included), a section's content, or a whole concept: its body plus its front matter, `generated` and `base` aside, so a concurrent change to a title, description, tags or sources conflicts too. `delta-stub` writes `<!-- base: <hash> -->` (or `base:` in front matter); never type it. A different current hash is a CONFLICT.

## intent.md

```yaml
---
type: intent
id: add-login
title: Add login
status: draft          # draft | approved | implementing | verified | archived
size: change           # change | fix | baseline
adrs: [ADR-0007]
created: 2026-10-17
archived: 2026-10-20   # added by sync
---
```

`size`: `change` (the default), `fix` (a test on an existing criterion, or on criteria it ADDs; nothing else in its delta, no ADR), `baseline` (an adopt: only Baseline criteria and new invariants, only `(test)` tasks, no code change).

Body sections from the template: Why, Outcome, Scope, Non-goals, Success criteria, Open questions. Open questions must be empty before Gate 1 approval.

## ADR

`adrs/NNNN_<slug>.md`, `<slug>` the title in snake_case:

```yaml
---
type: ADR
title: "Use CSV for exports"
description: "<One sentence: what was decided.>"
status: draft                  # draft (proposed) | stable (accepted) | deprecated (superseded, rejected)
tags: []
decided: 2026-10-18            # set again by adr-accept
deciders: []
supersedes: [0002_use_xlsx]    # concept ids of the ADRs it replaces
superseded_by: null            # set by adr-accept of the successor
generated: {by: ..., at: ...}
sources: []
---
```

Sections: Context, Decision drivers, Options considered, Decision, Consequences, Related. `## Decision` must be self-contained: it is the only part `sdd context` gives to implementers. An empty one shows as `(Decision section is empty: report this)`.

## plan.md

Front matter `type: plan`, `change: <id>`; sections Approach, Contracts, Components, Risks. `sdd context` sends test tasks only `## Contracts`, and sends the whole plan only with `--plan`. `check` validates criterion, invariant and ADR citations outside comments.

## Task line

```
- [ ] T2 (impl) Reject expired tokens — capabilities/auth/tokens#AC-04 ADR-0007 | blocked-by: T1 | files: src/auth/mw.py
```

Parsed with `^- \[( |x|X)\] (T\d+) \((test|impl|chore)\) (.*)$`:

| Part | Meaning |
|---|---|
| `[ ]` / `[x]` | open / done |
| `T<n>` | task id, unique in the file |
| `(test)` | acceptance tests, by acceptance-tester; cites ≥ 1 criterion or invariant, none retired or deprecated |
| `(impl)` | code, by an implementer; cites ≥ 1 criterion; should be `blocked-by` its test task. An invariant needs no `(impl)` task |
| `(chore)` | migrations, config, docs; no citation needed |
| citations, ADR ids | anywhere in the rest of the line |
| `blocked-by: T1, T3` | dependencies |
| `files: a, b` | files the task may change; the implementer stays inside them (impl tasks run one at a time) |

Front matter of `tasks.md` is `type: tasks`, `change: <id>`. Lines inside HTML comments are ignored, so the template's example is never parsed.

## Acceptance test citations

A file under `acceptance_dir` covers a unit when its text contains the exact citation. Put it in a docstring or a comment above the test:

```python
# capabilities/auth/tokens#AC-04
def test_expired_token_rejected(): ...
```

A test name cannot hold `/` or `#`, so the name alone never matches.

## frozen.json

```json
{"version": 2, "base": "<merge-base commit with origin/<base>, or null>", "files": {"<path relative to root>": "<sha256 hex>", ...}}
```

`files` holds every file under `acceptance_dir` at freeze time (tests, helpers, fixtures; ignored files and caches left out). `base` lets `verify-frozen` accept a file a later base merge changed. Written by `freeze` (the lead), checked by `verify-frozen`. A flat `{"<path>": "<sha256>"}` map is the format before v2: still verified, file by file.
