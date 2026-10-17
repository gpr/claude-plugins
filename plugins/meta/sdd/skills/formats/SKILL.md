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
Both `specs/` and each `changes/<change>/` are OKF (Open Knowledge Format v0.2) bundles: a
root `index.md` with `okf_version: "0.2"`, concept files with `type`/`sources` front matter.
```
specs/index.md, specs/log.md                         generated: index of capabilities, sync history
specs/<capability>/index.md                          generated: concepts and their REQ ids
specs/<capability>/<concept>.md                      living spec, type: spec, a few REQ blocks
specs/invariants/<category>/<concept>.md             living invariants, type: invariant, a few INV blocks
changes/<change>/index.md                            generated: the change's files and delta ids
changes/<change>/intent.md      why, scope, non-goals, success criteria (front matter: type, status, adrs)
changes/<change>/specs/<capability>/<concept>.md           spec delta (mirrors the living path)
changes/<change>/specs/invariants/<category>/<concept>.md  invariant delta
changes/<change>/plan.md        how: approach, contracts, components
changes/<change>/tasks.md       checklist, the only file edited during implementation
changes/<change>/state.json     phase, branch, base, PR number, requires (written only by `sdd.py`; never edit)
adr/ADR-NNNN-<slug>.md          one decision per file
tests/acceptance/               acceptance tests, tagged with REQ and INV ids
```
- `specs/` and the `index.md` files are written only by `sdd` (sync, `bundle --fix`, delta-new/stub). Never edit them.
- Keep concepts short: at most 5 blocks per file. A capability or category grows by new
  concept files per topic (`auth/tokens.md`, `auth/lockout.md`), not by longer ones.
  To regroup, put a MODIFIED block in the delta file of the new concept: sync moves it.
- Concept front matter: `type`, `title`, `capability` (or `category`), `sources: [code paths]`.
  A delta has `type: spec-delta|invariant-delta`, `target`, `sources` (merged into the concept at sync).
- The spec-author runs `bundle` (the `mcp__sdd__bundle` tool, `target` = change id) before
  handing a change back; it reports layout, front matter and index problems, and
  `fix: true` repairs them.

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

## Invariant block
```
### INV-SEC-001: Secrets are never logged
The system MUST NOT write a password or token to any log.

#### Check: test_no_secret_in_logs greps the captured log of the login flow
```
An invariant is a rule that holds for the whole system at all times, not one feature's
behavior (security, data integrity, performance budgets, compatibility). ID:
`INV-<CATEGORY>-<NNN>`, unique forever. It has a `#### Check:` (how it is verified) instead
of a scenario, and at least one `(test)` task; it needs no `(impl)` task. INV blocks live
only under `specs/invariants/<category>/`, REQ blocks only under `specs/<capability>/`.
Implementers get the titles of all invariants in force with `sdd context`.

## Delta file `changes/<c>/specs/<capability>/<concept>.md`
```
---
type: spec-delta
target: specs/auth/tokens.md
sources: []
---

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
- Create the file with `sdd delta-new <c> <capability>[/<concept>]` or
  `sdd delta-new <c> invariants/<category>[/<concept>]` (the concept defaults to the
  capability or category name; the template lists the three sections and a skeleton in a
  comment); delete the sections you leave empty. The invariant delta has the same sections.
- MODIFIED and REMOVED entries are created with `sdd delta-stub <c> <REQ|INV> [--remove]`,
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
