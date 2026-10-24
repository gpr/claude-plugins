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
- Another change editing a *different* criterion or section of the same capability is not a conflict: units merge independently, in sdd and in git (a merge keeps the capability's `generated.at`, and `log.md` merges by union once `sdd init` wrote `.gitattributes`).
- An ADDED criterion whose id another change took first is reported as `ADDED but the id exists ... next free AC-NN`: renumber yours.

## Merge conflict on the branch

A different problem: `checkpoint --phase`, `resume` or `sync` printing `merging origin/main into the change branch failed (<files>)` is a git conflict. Before `sync`, it is in code or tests, never in `specs/` (the change has not touched it yet). Merge by hand in the change's worktree, then checkpoint (and `sync` again). See [Resume a change](resume-a-change.md#if-the-base-merge-conflicts).

## Conflict after sync

`sync` merges `origin/<base>` first, so a change merged before it is caught as a CONFLICT above. But two changes can both sync while both PRs are in review. When the first one is merged, the second one's `finish` merges the base again and stops:

```
ERROR merging origin/main into the change branch failed (specs/capabilities/greeting.md): merge it by hand in .claude/worktrees/sdd-polite-greeting, see `Conflict after sync` in docs/how-to/resolve-sync-conflict.md, then run `finish` again
```

Both changes edited the same unit, and both versions are already in living specs. The merge was aborted; nothing was pushed. You resolve it by hand: the guard keeps every agent, the lead included, out of `specs/`.

1. In the change's worktree, `git merge origin/main`.
2. For each conflicted file under `specs/`, keep the base's version of the unit (the other change, already merged), then re-apply this change's edit on top of it. The text you approved is in the archived delta, `changes/archive/<date>-<id>/specs/<concept>.md`. Other conflicted lines (indexes) take either side; `sdd bundle specs --fix` regenerates them.
3. Show the merged unit to the reviewers (in the workflow, the lead shows it as a Gate 1 for that unit only): what they approved was based on older text.
4. `sdd finish <id>`. It commits the merge, pushes, and marks the PR ready.

If the merged unit means the code must change too, reopen instead: a new change on top of the base.
