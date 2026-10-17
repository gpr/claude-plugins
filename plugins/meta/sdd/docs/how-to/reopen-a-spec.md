---
type: How-to Guide
title: Reopen a spec when implementation is blocked
description: Send a change back to the spec when an implementer, the acceptance-tester or the verifier finds a requirement wrong, untestable or missing.
tags: [sdd, how-to, reopen, blocked]
sources:
  - resource: ../../skills/change/SKILL.md
  - resource: ../../agents/implementer.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Reopen a spec when implementation is blocked

**When:** an implementer returns `BLOCKED: REQ-... <reason>`, the acceptance-tester reports a scenario untestable or ambiguous, the verifier marks a finding `spec`, or a code-review finding needs behavior no REQ describes.

The lead does this. You see it as a new Gate 1 for the affected REQs.

## Full change

1. Back to draft:
   ```
   sdd set-status <id> draft
   sdd checkpoint <id> --phase spec -m "chore(<id>): reopen spec"
   ```
2. The spec-author is resumed with the report and fixes the affected REQs or scenarios.
3. **Gate 1** for the affected REQs only. You approve, then `set-status approved`.
4. The planner re-plans the affected tasks, `sdd check` passes (Gate 2).
5. The acceptance-tester rewrites the affected tests and runs `sdd freeze` again.
6. Implementation resumes.

Never relax a test or patch the code around the spec instead. The guard blocks the first, and the verifier catches the second.

## Fix (`size: fix`)

A fix has no spec-author to resume. If it turns out to need behavior no REQ describes, it isn't a fix any more:

1. Set `size: change` in `intent.md`.
2. ```
   sdd set-status <id> draft
   sdd checkpoint <id> --phase spec -m "chore(<id>): re-triage as change"
   ```
3. Start the spec-author with the finding, then Gate 1.
