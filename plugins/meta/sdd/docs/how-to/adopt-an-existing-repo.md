---
type: How-to Guide
title: Adopt sdd in an existing repository
description: Start the sdd workflow in a repository that already has code, tests and ADRs - survey, point the config at what exists, write current behavior down as Baseline criteria, as you touch it or per area with adopt.
tags: [sdd, how-to, brownfield, baseline, adopt, init]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../skills/change/SKILL.md
  - resource: ../../skills/formats/SKILL.md
generated:
  by: claude-code
  at: 2026-10-24T00:00:00Z
---

# Adopt sdd in an existing repository

In an existing repository `specs/` starts empty while the code already does a lot. sdd never imports or converts anything. Current behavior is written down as **Baseline** criteria: it is tested, and nobody has to implement it. You can do this as changes touch the code, or up front for one area at a time.

**Before you start:** the plugin is installed at project scope ([Install and configure sdd](install-and-configure.md), step 1).

## 1. Survey and configure

Ask Claude for the first change. The lead runs the survey, finds out how your tests run, and asks you where things go. To do it yourself:

```
python3 <plugin>/tools/sdd.py init --survey
```

```
found: docs/adr/ (1 .md, ADR-like), tests/ (tests), pyproject.toml
survey only, nothing written; then: init [key=value ...] (specs_dir, changes_dir, adr_dir, acceptance_dir, acceptance_cmd, unit_cmd, worktree_dir)
```

Then initialise with the values for your repository:

```
python3 <plugin>/tools/sdd.py init adr_dir=docs/sdd-adrs "acceptance_cmd=pytest -q {files}" "unit_cmd=pytest -q tests"
```

```
created: specs/, docs/sdd-adrs/, changes/, tests/acceptance/, specs/index.md, specs/log.md, docs/sdd-adrs/index.md, docs/sdd-adrs/log.md, specs/.templates/capability.md.tmpl, specs/.templates/invariant.md.tmpl, docs/sdd-adrs/.templates/adr.md.tmpl, .gitignore (/.claude/worktrees/)
```

- **ADRs.** Give sdd its own `adr_dir`. Your existing ADRs stay where they are, in their own format, and a capability or a new ADR links to them as plain references. If `adrs/` (or `specs/`) already holds files sdd did not create, `init` writes nothing, prints `WARN adrs/ has N .md file(s) sdd did not create` and exits 1. Run it again with `adr_dir=<another dir>`.
- **Tests.** `acceptance_dir` holds only the tests that cite criteria. Your existing suite stays where it is and keeps running through `unit_cmd`.
- `key=value` only works before `.claude/sdd.json` exists. After that, edit the file.

Commit `.claude/sdd.json` and the new folders on the base branch, as in [Install and configure sdd](install-and-configure.md).

## 2. Write behavior down as you touch it

You don't need to do anything special. When a change touches code that no capability covers, the spec-author writes two kinds of criteria:

- a **Baseline** criterion for each behavior in the touched slice that the change keeps. It ends with the place in the code that does it now:

  ```
  ### AC-01: Header first

  - **Given** rows `a` and `b`
  - **When** export runs
  - **Then** the output is `h`, `a`, `b` on three lines
  - **Baseline**: src/export.py
  ```

- a normal criterion for what the change adds or alters.

A Baseline criterion gets a `(test)` task and no `(impl)` task. Its acceptance test must **pass** on the current code: it pins down the behavior so the change can't break it. At Gate 1 you confirm both "this is what the code does" and "this is what it should do". `sync` drops the Baseline line, so the living spec reads like any other.

A **bug** in code that no criterion covers is not a `fix` (a `fix` needs an existing criterion). The lead runs it as a full change titled `fix: ...`. Its criterion states the correct behavior, so its test fails first.

## 3. Or adopt an area up front

```
/sdd:change adopt report export
```

The lead starts a `size: baseline` change titled `Baseline: <area>`, with the PR title `docs(<id>): baseline spec`. It follows the usual steps up to the acceptance tests, then goes straight to verify, with no implementation and no code review. `sdd check` enforces the rules: only Baseline criteria and new invariants, and only `(test)` tasks. The verifier fails the change if anything outside the change folder and the acceptance tests moved. Since it is a `docs` change, merging it releases nothing.

## When a Baseline test fails

The acceptance-tester reports `MISMATCH: <id> <observed behavior>` and does not freeze that test. The lead asks you which side is right:

- **The code is right:** the criterion is reopened and corrected, and stays Baseline.
- **The criterion is right (a latent bug):** the criterion loses its Baseline line and the planner adds an `(impl)` task. In an adopt, the criterion leaves the adopt instead, and the fix becomes its own change.

## Related

- [File formats: Capability](../reference/file-formats.md#capability)
- [Phases and states: order for a baseline](../reference/phases-and-states.md#order-for-a-baseline)
- [sdd subcommands: init](../reference/cli.md#workspace)
