---
type: How-to Guide
title: Make a change depend on another
description: Declare, inspect and clear the changes a change requires, and unblock it once they merge.
tags: [sdd, how-to, dependencies, requires]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/change/SKILL.md
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Make a change depend on another

Use this when a new change builds on one whose PR isn't merged yet.

## Declare it

When starting: tell the lead the new change builds on the open one. It runs:

```
sdd start add-sso --title "Add SSO" --requires add-login
```

On an existing change:

```
sdd requires add-sso add-login add-audit
```

For a change planned on the base (its `changes/<id>/intent.md` committed ahead of time), put `requires: [add-login]` in the intent's front matter instead; `sdd start add-sso` reads it, and refuses a `--requires` that differs.

Ids can be comma- or space-separated. A change can't require itself, and cycles (including transitive ones) are refused.

## Check where they stand

```
sdd deps add-sso
```

```
ready add-login finished pr #42, awaits merge into main
open add-audit phase implement pr #43
next: merge the PR of add-login (#42)
```

States: `ok`, `missing`, `ready`, `open`, `planned`, `unknown`; see [dependency states](../reference/phases-and-states.md#dependency-states). Exit code 1 means not all are in.

## What waits

- Spec work and Gate 1 go ahead.
- `sdd checkpoint --phase plan` (or any later phase) and `sdd resume` refuse while a required change isn't merged into the base.

## Unblock

1. Get each required change to `done` (the lead resumes it depth-first if it is `open`).
2. Merge its PR.
3. Resume or checkpoint the dependent change. sdd merges `origin/<base>` into its branch so the dependency's specs and code arrive, then continues.

## Drop a dependency

If a required change was abandoned or closed without merging:

```
sdd requires add-sso --clear
```

Or list only the ones that remain.

## A criterion that exists only in a dependency

If the spec-author needs to modify a criterion or invariant that only exists in an unmerged dependency, `delta-stub` fails because it isn't in the living specs yet. It reports that as an open question rather than adding it again. The fix is to wait for the dependency to merge.
