---
type: Reference
title: File formats
description: Exact syntax sdd.py parses - REQ blocks, scenarios, delta sections and base markers, intent and ADR front matter, task lines and acceptance test tagging.
tags: [sdd, reference, formats, spec, adr, tasks]
sources:
  - resource: ../../skills/formats/SKILL.md
  - resource: ../../skills/change/templates/intent.md
  - resource: ../../skills/change/templates/delta.md
  - resource: ../../skills/change/templates/adr.md
  - resource: ../../skills/change/templates/plan.md
  - resource: ../../skills/change/templates/tasks.md
  - resource: ../../tools/sdd.py
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# File formats

The `sdd:formats` skill holds the writing rules and is preloaded into spec-author, planner and acceptance-tester. This page states what `sdd.py` actually parses.

## Requirement block

```markdown
### REQ-AUTH-004: Expired tokens are rejected
The API MUST reject a request whose access token is expired with HTTP 401
and error code `token_expired`. It MUST NOT refresh the token implicitly.

#### Scenario: expired token
- GIVEN a token that expired 1 second ago
- WHEN it calls GET /v1/me
- THEN the response is 401 with `{"error": "token_expired"}`
```

- A block starts at a line `### <REQ id>: <title>` and runs to the next such line. Text before the first block is kept as the spec's preamble.
- REQ ids match `req_id_pattern` (default `REQ-[A-Z0-9]+-[0-9]{3}`). An id is unique forever; never reuse a removed one.
- A block has a scenario when one of its lines starts with `#### Scenario:`. ADDED and MODIFIED blocks need one.
- **Block hash**: the first 8 hex chars of sha256 over the block's lines, trailing spaces stripped, leading and trailing blank lines dropped, base marker excluded. Whitespace at line ends does not change it.

## Living spec

`specs/<capability>/spec.md`: a preamble (`# <capability>`) and REQ blocks. `sync` rewrites it with blocks sorted by REQ id. Never edited by hand.

## Delta

`changes/<change>/specs/<capability>.md`, one per capability:

```markdown
# Delta: auth

## ADDED

### REQ-AUTH-004: ...

## MODIFIED

### REQ-AUTH-001: ...
<!-- base: 1a2b3c4d -->
(full new text of the requirement, not a diff)

## REMOVED

### REQ-AUTH-002: ...
<!-- base: 9f8e7d6c -->
Reason: ...
```

- Sections are lines exactly `## ADDED`, `## MODIFIED`, `## REMOVED`. Blocks outside a section are ignored.
- `<!-- base: <8 hex> -->` on its own line inside a block records the hash of the living REQ the entry was based on. `delta-stub` writes it; never type it.
- MODIFIED holds the complete new block: sync replaces the whole block.
- Other HTML comments (template guidance) are ignored.

## intent.md

```yaml
---
id: add-login
title: Add login
status: draft          # draft | approved | implementing | verified | archived
size: change           # change | fix
adrs: [ADR-0007]       # inline list only
created: 2026-10-17
archived: 2026-10-20   # added by sync
---
```

Body sections from the template: Why, Outcome, Scope, Non-goals, Success criteria, Open questions. Open questions must be empty before Gate 1 approval.

Front matter is parsed line by line as `key: value`; `[a, b]` is a list. Nested YAML is not supported.

## ADR

`adr/ADR-NNNN-<slug>.md`:

```yaml
---
status: proposed       # proposed | accepted | superseded | deprecated
date: 2026-10-17
supersedes: ADR-0003   # or empty
superseded_by:         # filled by adr-accept of the successor
---

# ADR-0008: <title>

## Context
## Options
## Decision
## Consequences
```

The ADR number is the first 8 characters of the file name. `## Decision` must be self-contained: it is the only part `sdd context` gives to implementers. An empty Decision shows as `(Decision section is empty: report this)`.

## plan.md

Front matter `change: <id>`; sections Approach, Contracts, Components, Risks. `sdd context` sends test tasks only `## Contracts`, and sends the whole plan only with `--plan`. `check` validates REQ and ADR ids mentioned outside comments.

## Task line

```
- [ ] T2 (impl) Reject expired tokens in middleware — REQ-AUTH-004 ADR-0007 | blocked-by: T1 | files: src/auth/mw.py
```

Parsed with `^- \[( |x|X)\] (T\d+) \((test|impl|chore)\) (.*)$`:

| Part | Meaning |
|---|---|
| `[ ]` / `[x]` | open / done |
| `T<n>` | task id, unique in the file |
| `(test)` | acceptance tests, by acceptance-tester; needs ≥ 1 REQ |
| `(impl)` | code, by an implementer; needs ≥ 1 REQ; should be `blocked-by` its test task |
| `(chore)` | migrations, config, docs; no REQ needed |
| REQ / ADR ids | anywhere in the rest of the line |
| `blocked-by: T1, T3` | dependencies |
| `files: a, b` | files the task touches; the lead runs impl tasks in parallel when these sets are disjoint |

Lines inside HTML comments are ignored, so the template's example is never parsed.

## Acceptance test tagging

A file under `acceptance_dir` covers a REQ when its text contains the exact REQ id. Put it in a docstring or a comment above the test:

```python
# REQ-AUTH-004
def test_expired_token_rejected(): ...
```

`def test_REQ_AUTH_004_...` does **not** match: underscores are not hyphens.

## frozen.json

`{"<path relative to root>": "<sha256 hex>", ...}` for every acceptance file that mentions one of the change's test REQs. Written by `freeze`, checked by `verify-frozen`.
