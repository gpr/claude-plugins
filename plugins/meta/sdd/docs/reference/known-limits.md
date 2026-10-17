---
type: Reference
title: Known limits
description: Current limitations of the sdd plugin and their workarounds.
tags: [sdd, reference, limits]
sources:
  - resource: ../../README.md
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Known limits

| Limit | Workaround |
|---|---|
| `resume` only fast-forwards: a diverged local branch fails with `cannot fast-forward`. | Reconcile the branch by hand in the worktree, then `resume` again. See [Resume a change](../how-to/resume-a-change.md). |
| Merging the base into a change branch (`checkpoint --phase`, `resume`) can conflict. sdd aborts the merge and names the files. | Merge `origin/<base>` by hand in the worktree, resolve, then `checkpoint` again. |
| "Merged" means the dependency's archive directory is on `origin/<base>`. A dependency closed without merging stays blocked. | `sdd requires <id> --clear` (or set the remaining ones). Squash merges are fine. |
| Parallel implementer worktrees (`isolation: "worktree"`) started from inside the change's worktree are untested with nested worktrees. | Run implementers one after another if it fails. |
| Parallel implementers in worktrees need the lead to merge their branches into `sdd/<id>`. | The lead does this; never commit by hand otherwise. |
| The Bash guard is a heuristic on the command text. | `sdd verify-frozen` (verifier, and ideally CI) is the real enforcement. See [Run verify-frozen in CI](../how-to/run-verify-frozen-in-ci.md). |
| The band and panes refresh on workflow events and every 30 s. Edits made outside Claude Code show late. | `/sdd refresh`. |
| Front matter is parsed line by line, not as YAML. | Keep `key: value` lines and inline `[a, b]` lists. |
| Acceptance coverage is a text search for the exact REQ id. | Tag tests with the hyphenated id in a comment or docstring. |
