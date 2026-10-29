# Sync and finish conflicts

Part of the `sdd:change` lead workflow: read when `sdd sync` or `sdd finish` (step 8.4, 8.5)
refuses. Step numbers refer to SKILL.md.

- **The base merge conflicts** (sync merges `origin/<base>` in first when the base moved; a
  dry run only warns): resolve it in the change's checkout, checkpoint, and sync again.
- **`specs bundle:` error**: run the `bundle` tool on `specs` (with `fix: true` for what it
  marks fixable) and commit that first; old REQ/INV concepts must be rewritten by hand.
- **CONFLICT on a criterion, section or invariant**: another change modified the same unit
  first. Resume spec-author to rebase that unit (`delta-stub` again), then Gate 1 for it only.
- **CONFLICT on a contract file**: resume contract-designer to stub it again and redo the
  edit, then Gate 1 for that file only.
- **`finish` merge conflicts**: another change edited the same unit after this sync. Tell the
  user which files and that they resolve it by hand (the guard keeps you out of `specs/`), as
  "Conflict after sync" in the plugin's how-to/resolve-sync-conflict says; show the merged
  unit as a Gate 1 for it only, then `finish` again.
