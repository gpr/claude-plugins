---
type: How-to Guide
title: Resolve a REQ conflict
description: Handle a CONFLICT reported by sdd check or sdd sync when another change modified the same requirement first.
tags: [sdd, how-to, conflict, sync, delta]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/formats/SKILL.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Resolve a REQ conflict

**Symptom** (from `sdd check` or `sdd sync`):

```
ERROR specs/greeting.md REQ-GREET-001: CONFLICT base f1452e6a != current 52566f36 (living spec changed since this delta was written)
FAIL polite-greeting: 1 REQ, 0 tasks, 1 errors, 0 warnings
```

Another change synced a new version of `REQ-GREET-001` after your delta copied it. Nothing has been written.

1. **Don't edit the base hash.** That would silently overwrite the other change's version.
2. Read what changed: compare the living block in `specs/greeting/spec.md` with your delta's MODIFIED block.
3. Re-stub the REQ. `delta-stub` refuses a REQ already in the delta, so delete your block (heading through the end of its scenarios) from `changes/<id>/specs/<capability>.md` first, then:

   ```
   sdd delta-stub <id> REQ-GREET-001
   ```

   This copies the current text with the new base. With `--remove`, it makes a REMOVED entry.
4. Re-apply your intended edit on top of the new text.
5. `sdd check <id>`: the conflict is gone.
6. Show the REQ at Gate 1 again, for that REQ only: what you approved earlier was based on older text.

In the workflow, the lead resumes the spec-author for steps 2–5 and runs step 6.

## Not a conflict

Trailing whitespace changes in the living spec don't change the hash. A pure reformat never triggers this.

## Merge conflict on the branch

A different problem: `checkpoint --phase` or `resume` printing `merging origin/main into the change branch failed (<files>)` is a git conflict. Merge by hand in the change's worktree, then checkpoint. See [Resume a change](resume-a-change.md#if-the-base-merge-conflicts).
