---
type: How-to Guide
title: Resolve a spec conflict
description: Handle a CONFLICT reported by sdd check or sdd sync when another change modified the same criterion, section or invariant first.
tags: [sdd, how-to, conflict, sync, delta]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/formats/SKILL.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Resolve a spec conflict

**Symptom** (from `sdd check` or `sdd sync`):

```
ERROR changes/polite-greeting/specs/capabilities/greeting.md capabilities/greeting#AC-01: CONFLICT base f1452e6a != current 59e67d47 (living spec changed since this delta was written)
FAIL polite-greeting: 1 unit(s), 0 tasks, 1 errors, 0 warnings
```

Another change synced a new version of that unit after your delta copied it. The unit is a criterion (`#AC-NN`), a capability section (`... capabilities/greeting Scope: CONFLICT ...`), a whole capability you deprecate, or an invariant you replace. Nothing has been written.

1. **Don't edit the base hash.** That would silently overwrite the other change's version.
2. Read what changed: compare the living unit in `specs/capabilities/greeting.md` with your delta's copy.
3. Re-stub it. `delta-stub` refuses a unit already in the delta, so first delete your copy:
   - a criterion: its block, from `### AC-NN` to the next heading, under MODIFIED or RETIRED;
   - a section: its `### <Name>` block under SECTIONS;
   - an invariant: the whole file `changes/<id>/specs/invariants/<id>.md`;
   - a deprecation: the `status: deprecated` and `base:` lines of the CapabilityDelta.

   Then run the same `delta-stub` again, e.g.:

   ```
   sdd delta-stub <id> capabilities/greeting#AC-01
   ```

   This copies the current text with the new base.
4. Re-apply your intended edit on top of the new text.
5. `sdd check <id>`: the conflict is gone.
6. Show that unit at Gate 1 again, and only that one: what you approved earlier was based on older text.

In the workflow, the lead resumes the spec-author for steps 2–5 and runs step 6.

## Not a conflict

- Trailing whitespace and comments in the living file don't change the hash. A pure reformat never triggers this.
- Another change editing a *different* criterion or section of the same capability is not a conflict: units merge independently.
- An ADDED criterion whose id another change took first is reported as `ADDED but the id exists ... next free AC-NN`: renumber yours.

## Merge conflict on the branch

A different problem: `checkpoint --phase` or `resume` printing `merging origin/main into the change branch failed (<files>)` is a git conflict. Merge by hand in the change's worktree, then checkpoint. See [Resume a change](resume-a-change.md#if-the-base-merge-conflicts).
