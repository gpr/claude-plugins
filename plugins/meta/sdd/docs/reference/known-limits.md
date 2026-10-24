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
  at: 2026-10-18T00:00:00Z
---

# Known limits

| Limit | Workaround |
|---|---|
| `resume` only fast-forwards: a diverged local branch fails with `cannot fast-forward`. | Reconcile the branch by hand in the worktree, then `resume` again. See [Resume a change](../how-to/resume-a-change.md). |
| Merging the base into a change branch (`checkpoint --phase`, `resume`, `sync`) can conflict. sdd aborts the merge and names the files. | Merge `origin/<base>` by hand in the worktree, resolve, then `checkpoint` again. |
| Two changes that both sync while both PRs are in review, and edit the same unit: the second one's `finish` stops on a git conflict in `specs/`. | Resolve it by hand, keeping the base's unit and re-applying yours: [Conflict after sync](../how-to/resolve-sync-conflict.md#conflict-after-sync). |
| "Merged" means the dependency's archive directory is on `origin/<base>`. A dependency closed without merging stays blocked. | `sdd requires <id> --clear` (or set the remaining ones). Squash merges are fine. |
| Implementers run one at a time. Claude Code's isolated subagent worktrees branch from the default branch, without the change's tasks, plan and frozen tests. | None needed; `files:` keeps each task small. |
| The Bash guard is a heuristic on the command text: it follows `cd`, redirects and file-writing commands, but not a path built at run time (`python -c "...write_text(...)"`). | `sdd verify-frozen` (verifier, and ideally CI) is the real enforcement: it hashes the whole acceptance dir. See [Run verify-frozen in CI](../how-to/run-verify-frozen-in-ci.md). |
| The band and panes refresh on workflow events and every 30 s. Edits made outside Claude Code show late. | `/sdd refresh`. |
| The Baseline re-run on the base commit (`baseline-tree`) links only `node_modules`, `.venv`, `venv` and the `--link` paths; anything else the tests need (a build step, a database) is missing there. | Pass `--link <path>`, or the verifier reports `baseline: not run (<why>)` and you run the tests on the base yourself. |
| The `init` survey is a heuristic: names, file patterns and Status/Decision headings, 4 levels deep. | The lead still asks Explore how the tests run; set the `*_dir` keys yourself if nothing is found. |
| Front matter is parsed line by line, not as YAML. | Keep `key: value` lines and inline `[a, b]` lists. |
| Acceptance coverage is a text search for the exact citation (`capabilities/<id>#AC-NN`, `invariants/<id>`). | Cite it in a comment or docstring; a test name cannot hold `/` or `#`. |
