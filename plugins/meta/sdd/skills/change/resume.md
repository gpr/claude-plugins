# Resume a change

Part of the `sdd:change` lead workflow: read when the request starts with `resume`.
Step numbers refer to SKILL.md.

`resume <id>` continues a change from this or another machine:
1. `sdd resume <id>` (add `--pr <n>` if you only have the PR number). It fetches the PR
   branch, creates or reuses the worktree, fast-forwards it, and prints the stored phase
   and the step to continue at.
   If it ends with `blocked` / `next: ...`, a required change is not merged yet: do not
   enter the worktree or continue this change. Follow `next:`. For `resume <dep>`, run this
   whole Resume procedure for the dep (its own worktree, its own `requires` first), carry it
   through to `sdd finish`, then come back. For `merge the PR of <dep>`, tell the user which
   PR to merge and stop; once they say it is merged, `sdd resume <id>` again (it merges the
   base into the branch, so the dependency's specs and code arrive).
2. `EnterWorktree` with `path` = the printed worktree (skip it when the output says `in_place`:
   the branch is then checked out in this checkout). From here every `sdd` call acts on it.
3. `sdd status <id>`, then continue at the step the phase names (spec -> 2, contract -> 2.4, gate1 -> 3,
   plan -> 4, gate2 -> 5, acceptance -> 6, implement -> 7, verify -> 8, sync -> 8.4,
   done -> nothing left; "Paths at a glance" in SKILL.md gives each path's order). A stored phase can lag a step that was done but not
   checkpointed: trust the files (`sdd check`, task ticks) over the phase when they disagree.
   Resume a partly written spec or plan with the same agent type and the files as context.
   Run the `bundle` tool on the change first. A change written in the old REQ/INV format
   cannot be fixed by `bundle`: resume spec-author to rewrite its delta as concepts.
