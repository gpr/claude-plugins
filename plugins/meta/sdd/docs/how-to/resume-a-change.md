---
type: How-to Guide
title: Resume a change
description: Continue an open change in a new session or on another machine, by change id or PR number, and handle a blocked or diverged resume.
tags: [sdd, how-to, resume, worktree]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/change/SKILL.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Resume a change

1. Ask the lead:

   ```
   /sdd:change resume add-login
   ```

   If you only know the PR number, say so ("resume the change in PR 42"). The lead runs `sdd resume --pr 42`, which asks `gh` for the branch.

2. The lead runs `sdd resume <id>`. It fetches the branch, reuses or creates the worktree `.claude/worktrees/sdd-<id>`, fast-forwards it, and prints:

   ```
   worktree /repo/.claude/worktrees/sdd-add-login
   branch sdd/add-login
   pr 42 https://github.com/o/r/pull/42
   status approved
   phase plan: step 4: planner writes plan.md and tasks.md
   next: EnterWorktree path=/repo/.claude/worktrees/sdd-add-login
   ```

3. The lead enters the worktree, runs `sdd status <id>`, and continues at the step the phase names. If the files say more was done than the phase (a step finished without a checkpoint), the files win.

## If it says `blocked`

```
open other-change phase implement pr #40
blocked: required changes are not merged into main
next: resume other-change, then `resume add-login` again
```

A required change isn't merged yet. The lead resumes and finishes that one first. If the output says `next: merge the PR of <dep> (#40)`, merge that PR yourself, then tell the lead to resume again. The base is merged into the branch at that point. See [Manage dependencies](manage-dependencies.md).

## If it says `cannot fast-forward`

Your local branch and `origin` diverged (commits made on both sides). sdd won't guess. In the worktree:

```
cd .claude/worktrees/sdd-add-login
git fetch origin
git rebase origin/sdd/add-login     # or: git merge origin/sdd/add-login
git push
```

Then resume again.

## If the base merge conflicts

`resume` or `checkpoint` may print `merging origin/main into the change branch failed (<files>)`. Merge by hand in the worktree, resolve, commit, then ask the lead to checkpoint.
