---
type: Tutorial
title: Your first fix
description: Break an existing requirement on purpose and repair it through the fix path - a failing acceptance test against the existing REQ, no new spec, no Gate 1.
tags: [sdd, tutorial, fix]
sources:
  - resource: ../../skills/change/SKILL.md
  - resource: ../../hooks/phase.ts
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Your first fix

This tutorial continues from [Your first spec-driven change](first-change.md). You have `specs/greet/spec.md` with `REQ-GREET-001` (`--name Ada` prints `Hello, Ada!`) merged on `main`.

We'll introduce a bug, report it, and watch the workflow fix it test-first, without writing any new spec.

## 1. Break it

In `~/sdd-tutorial/greet`, open `greet.py` in your editor and delete the `!` from the named greeting (the line the implementer wrote for `--name`). Then:

```
python greet.py --name Ada
```

```
Hello, Ada
```

Commit and push it to `main`, so the bug is "released":

```
git commit -qam "tweak output" && git push -q
```

## 2. Report it

In Claude Code:

> `greet --name Ada` prints `Hello, Ada` without the `!`.

Notice the triage line: the code diverges from an existing REQ, so it's a **fix**, not a change. No spec delta, no Gate 1.

The lead starts the change, sets `size: fix` in its `intent.md`, and writes one test task against the existing REQ:

```
- [ ] T1 (test) Named greeting keeps its exclamation mark — REQ-GREET-001
```

## 3. Test and plan side by side

Open `/sdd phase`. A fix has its own order, with no Spec and no Gate 1:

```
▶ 1. Plan — planner writes plan.md and tasks.md
· 2. Acceptance tests
· 3. Gate 2
· 4. Implement
· 5. Verify
· 6. Sync
```

The contract is the existing CLI, so the test doesn't need to wait for a plan. The acceptance-tester and the planner run **at the same time**. The tester writes a test tagged `REQ-GREET-001`, sees it fail on `Hello, Ada`, and freezes it. The planner adds an impl task `blocked-by: T1`.

## 4. Gate 2, implement, verify

Gate 2 waits for both, checks that T1 is ticked and frozen, and moves straight to **Implement**. The implementer restores the `!`. The verifier confirms the frozen test passes and is untouched.

## 5. Sync without a delta

Sync has no requirement to merge, so `specs/` doesn't change. It archives the change, and the new acceptance test stays in `tests/acceptance/` as a regression guard for `REQ-GREET-001`.

Merge the branch as before, and `python greet.py --name Ada` prints `Hello, Ada!` again.

## What you've learned

- A fix starts from a REQ that already exists. It costs one failing test, not a spec review.
- If the test can't be written against an existing REQ (the "fix" needs behavior no REQ describes), the lead re-triages it as a full change. See [Reopen a spec](../how-to/reopen-a-spec.md#fix-size-fix).
