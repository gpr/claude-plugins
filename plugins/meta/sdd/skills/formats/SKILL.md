---
name: formats
description: File formats and writing rules for spec deltas, requirements, scenarios, ADRs and tasks in the spec-driven workflow. Preloaded by the workflow subagents; read it before writing any of those files.
user-invocable: false
---

# SDD formats

All paths are relative to the repo root. `sdd <args>` means a call to the `mcp__sdd__sdd` tool
with `args` as a list (`sdd check c1` is `{"args": ["check", "c1"]}`).
The tool is the source of truth for structure: when in doubt, run `sdd check <change>`.

## Layout
```
specs/<capability>/spec.md      living spec: what the system does NOW (never edit by hand)
changes/<change>/intent.md      why, scope, non-goals, success criteria (front matter: status, adrs)
changes/<change>/specs/<capability>.md   delta against the living spec
changes/<change>/plan.md        how: approach, contracts, components
changes/<change>/tasks.md       checklist, the only file edited during implementation
adr/ADR-NNNN-<slug>.md          one decision per file
tests/acceptance/               acceptance tests, tagged with REQ ids
```

## Requirement block
```
### REQ-AUTH-004: Expired tokens are rejected
The API MUST reject a request whose access token is expired with HTTP 401
and error code `token_expired`. It MUST NOT refresh the token implicitly.

#### Scenario: expired token
- GIVEN a token that expired 1 second ago
- WHEN it calls GET /v1/me
- THEN the response is 401 with `{"error": "token_expired"}`
```
Rules:
- ID: `REQ-<CAPABILITY>-<NNN>`, unique forever. Never reuse a removed ID. Pick the next free
  number: `grep -ho "REQ-AUTH-[0-9]*" specs changes -r | sort -u | tail -1`.
- One behavior per REQ. Use MUST / MUST NOT / SHOULD. Observable behavior only, no internals.
- Every ADDED/MODIFIED REQ has at least one `#### Scenario:` with GIVEN/WHEN/THEN.
  Scenarios are the acceptance tests. Concrete values, no "valid input", no "works correctly".
- Cover the unhappy paths that matter (errors, limits, permissions), not only the happy one.

## Delta file `changes/<c>/specs/<capability>.md`
```
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
- Create the file with `sdd delta-new <c> <capability>` (the template lists the three
  sections and a REQ/scenario skeleton in a comment); delete the sections you leave empty.
- MODIFIED and REMOVED entries are created with `sdd delta-stub <c> <REQ> [--remove]`,
  which copies the current text and the base hash. Then edit the copied text. Never type a
  base hash yourself. A wrong or stale base fails `check` with CONFLICT: that is a real
  conflict with another change, report it, do not "fix" the hash.
- MODIFIED holds the complete new requirement. Sync replaces the whole block.

## ADR
Create with `sdd adr-new "<title>" [--supersedes ADR-NNNN]`, then fill the sections.
Write one only if there is a real rejected alternative AND a consequence that outlives this
change. Otherwise it is a line in plan.md. Accepted ADRs are immutable: change a decision by
superseding it. List the change's ADRs in `intent.md` front matter `adrs: [ADR-0007]`.
`## Decision` must be self-contained: it is the only part implementers receive.

## Tasks line
```
- [ ] T2 (impl) Reject expired tokens in middleware — REQ-AUTH-004 ADR-0007 | blocked-by: T1 | files: src/auth/mw.py
```
Kinds: `test`, `impl`, `chore`. Reference IDs, never restate requirement text.

## Acceptance test tagging
Every acceptance test names its REQ id in the test name or a comment on the line above it,
e.g. `def test_REQ_AUTH_004_expired_token_rejected():` is NOT matched (underscores);
use a docstring or comment containing `REQ-AUTH-004` exactly.
