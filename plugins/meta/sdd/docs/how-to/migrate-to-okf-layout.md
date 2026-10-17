---
type: How-to Guide
title: Migrate to the OKF layout
description: Move a project from one long specs/<capability>/spec.md and flat change deltas to concept files and OKF bundles with sdd bundle --fix.
tags: [sdd, how-to, migration, okf, bundle]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Migrate to the OKF layout

Use this when `specs/` still holds `specs/<capability>/spec.md` files and open changes hold flat deltas `changes/<id>/specs/<capability>.md`. The layout it migrates to is in [OKF bundles](../reference/bundles.md).

Until you migrate, `sdd sync` refuses (it requires a clean `bundle specs`), and `sdd check` reports the open changes' legacy files as `bundle:` warnings.

## 1. Migrate the living specs

On the base branch, as the lead (only the lead may fix `specs`). Look first:

```
bundle  {"target": "specs"}
```

```
ERROR specs/auth/spec.md: legacy layout, expected specs/auth/auth.md [fixable]
ERROR specs/auth/spec.md: front matter incomplete (type, title, capability, sources) [fixable]
ERROR specs/auth/index.md: missing [fixable]
ERROR specs/index.md: missing [fixable]
ERROR specs/log.md: missing [fixable]
FAIL specs: 5 errors, 0 warnings
```

Then repair:

```
bundle  {"target": "specs", "fix": true}
```

```
FIXED specs/auth/spec.md: legacy layout, expected specs/auth/auth.md
FIXED specs/auth/auth.md: front matter incomplete (type, title, capability, sources)
FIXED specs/auth/index.md: missing
FIXED specs/index.md: missing
FIXED specs/log.md: missing
OK specs: 0 errors, 0 warnings, 5 fixed
```

Outside Claude Code the same is `python3 <plugin>/tools/sdd.py bundle specs --fix`. Running it again prints `0 fixed`.

Each `spec.md` becomes one concept named after its capability (`specs/auth/auth.md`). Requirement text is untouched. A concept above 5 blocks gets a warning, which is fine until you next touch it: split it then, see [Group requirements into concepts](write-a-delta-and-adr.md#group-requirements-into-concepts).

Commit and push to the base branch.

## 2. Migrate each open change

In the change's worktree, after merging the migrated base branch into the change branch. The lead or the spec-author runs, per change:

```
bundle  {"target": "add-login", "fix": true}
```

```
FIXED changes/add-login/intent.md: front matter lacks 'type: intent'
FIXED changes/add-login/plan.md: front matter lacks 'type: plan'
FIXED changes/add-login/tasks.md: front matter lacks 'type: tasks'
FIXED changes/add-login/specs/auth.md: legacy layout, expected changes/add-login/specs/auth/auth.md
FIXED changes/add-login/specs/auth/auth.md: front matter incomplete (type, target, sources)
FIXED changes/add-login/index.md: missing
OK add-login: 0 errors, 0 warnings, 6 fixed
```

The flat delta moves to `specs/<capability>/<capability>.md`, which targets the migrated concept, so its base hashes still match. Run `sdd check <id>`, then checkpoint.

## If a fix is refused or reports an ERROR

- `legacy file, ... already exists`: both `spec.md` and `<cap>.md` exist. Merge them by hand into the concept, delete `spec.md`, rerun.
- `no requirement blocks but it holds prose`: move or delete the prose by hand; `--fix` only deletes concept files with nothing but headings.
- `bundle specs --fix` is run by the lead only: ask the lead. A spec-author may fix a change, not `specs`.

Rules for the findings and which are fixable: [OKF bundles](../reference/bundles.md#bundle-checks).
