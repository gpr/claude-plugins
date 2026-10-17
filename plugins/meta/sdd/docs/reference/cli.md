---
type: Reference
title: sdd subcommands
description: Every subcommand of tools/sdd.py, its arguments, what it writes, and which role may run it through the sdd tool, including the bundle validator.
tags: [sdd, reference, cli, sdd.py]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../hooks/guard.ts
  - resource: ../../hooks/register.tsx
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# sdd subcommands

Agents and the lead call `sdd.py` through the `mcp__sdd__sdd` tool, with the subcommand and its arguments as a list: `sdd check c1` is `{"args": ["check", "c1"]}`. The guard refuses `python3 .../sdd.py` from Bash for every subagent. The lead (and you, outside Claude Code) can still run `python3 <plugin>/tools/sdd.py <subcommand> ...` directly.

**Exit codes:** `0` ok, `1` errors found, `2` usage error (unknown subcommand, bad arguments, unknown change).
**Output:** terse, one fact per line. Problems start with `ERROR` or `WARN`; summaries with `OK` or `FAIL`.
**Working directory:** `sdd.py` resolves the project root from the cwd at start-up; see [Configuration](configuration.md#project-root).

**Role** is who may run the subcommand through the tool ([`SDD_RULES`](sdd-tool-roles.md)). *any* means every role.

## Workspace

| Subcommand | Role | Effect |
|---|---|---|
| `init` | lead | Creates `specs/` (with its `index.md` and `log.md`), `adr/`, `changes/`, `tests/acceptance/` (configured names), writes `.claude/sdd.json` with the defaults if missing, adds `/<worktree_dir>/` to `.gitignore`. Idempotent: prints `created: nothing, already initialised`. |
| `config` | any | Prints the effective configuration as JSON, with `root`. |
| `status [<change>] [--json]` | any | One line per open change: `status`, `tasks=done/total`, `size`, and `phase`, `pr`, `requires` when stored. With a change id, also one line per task. `--json` is what the band and panes read. Also counts archived changes. |

## Change scaffolding and status

| Subcommand | Role | Effect |
|---|---|---|
| `new <change> [--title T]` | lead | Creates `changes/<change>/` with `intent.md`, `plan.md`, `tasks.md` from the templates, the generated `index.md`, and an empty `specs/`. The id must be kebab-case, 2–61 chars (`[a-z0-9][a-z0-9-]{1,60}`). Fails if the directory exists. Normally run by `start`, not by hand. |
| `set-status <change> <status>` | lead | Rewrites `status:` in `intent.md` front matter. Status is one of `draft approved implementing verified archived`. Prints `<change>: <old> -> <new>`. |

## Spec delta and ADRs

| Subcommand | Role | Effect |
|---|---|---|
| `delta-new <change> <capability>[/<concept>]` or `<change> invariants/<category>[/<concept>]` | lead, spec-author | Creates `changes/<change>/specs/<capability>/<concept>.md` (the concept defaults to the capability) from the delta template, or the invariant delta template for `invariants/...`: front matter, `## ADDED`, `## MODIFIED`, `## REMOVED`, guidance in a comment. Every part must be kebab-case. Fails if the file exists. Refreshes the change's `index.md`. |
| `delta-stub <change> <REQ\|INV> [--remove]` | lead, spec-author | Copies the living block into the delta at the mirrored concept path (`changes/<change>/specs/<group>/<concept>.md`), under `## MODIFIED` (or `## REMOVED` with `--remove`, body replaced by `Reason: <why it is removed>`), with a `<!-- base: <hash> -->` line. Creates the delta from the template if needed and refreshes `index.md`. Fails if the id is not in a living spec or already in the delta. |
| `adr-new <title> [--supersedes ADR-NNNN]` | lead, spec-author | Creates `adr/ADR-NNNN-<slug>.md` from the ADR template with the next free number, `status: proposed`, today's date and `supersedes:`. The slug is the title lower-cased, non-alphanumerics folded to `-`, 50 chars max. The superseded ADR must exist. |
| `adr-accept <ADR-NNNN>` | lead | `proposed` → `accepted`. If it supersedes another ADR, that one becomes `superseded` with `superseded_by:`. Accepting an accepted ADR is a no-op; any other status is an error. `sync` does this for the ADRs listed in `intent.md`. |

## Checks and context

| Subcommand | Role | Effect |
|---|---|---|
| `check <change> [--tests]` | any | Traceability, conflict and bundle check, see [the rules](#check-rules). Ends with `OK|FAIL <change>: <n> REQ, <n> tasks, <n> errors, <n> warnings`. Exit 1 on any error. |
| `context <change> <task> [--plan]` | any | Prints the minimal bundle for one task, see [Context bundles](../explanation/context-bundles.md). For an `(impl)` task it also lists `id: title` of every invariant in force (living, plus the change's ADDED/MODIFIED, minus its REMOVED) that the task does not name. |
| `bundle <specs\|change> [--fix]` | any; `--fix` on `specs`: lead; `--fix` on a change: lead, spec-author | Validates an OKF bundle: `specs/` or `changes/<change>/`, see [OKF bundles](bundles.md#bundle-checks). Prints `FIXED`, `WARN`, `ERROR` lines then `OK|FAIL <target>: <n> errors, <n> warnings` (`, <n> fixed` with `--fix`). `--fix` repairs findings marked `[fixable]`, migrates the legacy layout, and is idempotent. Exit 1 on any ERROR. The same check is the `mcp__sdd__bundle` tool ([roles](sdd-tool-roles.md#the-bundle-tool)). |
| `freeze <change>` | lead, acceptance-tester | Writes `changes/<change>/frozen.json`: sha256 of every file under the acceptance dir that mentions one of the change's test REQs. Fails (exit 1) if no file mentions them. Re-running replaces the snapshot. |
| `verify-frozen <change>` | any | Re-hashes the frozen files. `ERROR <file> modified after freeze` or `deleted after freeze`; summary `OK|FAIL <n> frozen file(s), <n> tampered`. Exit 1 if `frozen.json` is missing or anything changed. |

### check rules

Errors (exit 1):
- `intent.md` status not one of the five statuses.
- A REQ appears twice in the change's deltas.
- ADDED REQ already exists in a living spec.
- MODIFIED/REMOVED REQ not in a living spec, or living in another capability's (or category's) spec.
- An INV in the spec tree, or a REQ in the invariant tree.
- MODIFIED/REMOVED without `<!-- base: -->`, or with a base that differs from the living REQ's current hash: `CONFLICT base <a> != current <b>`.
- ADDED/MODIFIED REQ without a `#### Scenario:`; ADDED/MODIFIED INV without a `#### Check:`.
- Task problems: duplicate id, `blocked-by` an unknown task, references an unknown REQ, a `(test)` task on a REMOVED REQ, a `(test)`/`(impl)` task with no REQ or INV.
- A referenced ADR (in `intent.md` `adrs:` or a task) has no file, or is `superseded`/`deprecated`.
- `plan.md` references an unknown REQ or ADR (HTML comments ignored).
- Once `tasks.md` has tasks: an ADDED/MODIFIED REQ with no `(test)` task or no `(impl)` task; an ADDED/MODIFIED INV with no `(test)` task (it needs no `(impl)` task).
- Any bundle ERROR of the change (see [OKF bundles](bundles.md#change)), printed with a `bundle:` prefix.
- No tasks while status is not `draft`.

Warnings:
- No spec delta (unless `size: fix`).
- A base comment on an ADDED REQ (ignored).
- Any bundle WARN of the change, prefixed `bundle:` (a stale `index.md`, a missing `type:`, a legacy flat delta).
- The stored phase does not fit the status (see [Phases and states](phases-and-states.md#phase-and-status)).
- An `(impl)` task not `blocked-by` the `(test)` task(s) covering its REQs.

With `--tests`, also:
- Error: a REQ to be tested (ADDED/MODIFIED, plus existing REQs that a `(test)` task targets, the fix path) is mentioned by no file under the acceptance dir.
- Error: `open tasks: T1,T3` for unticked tasks.
- Warning: a REMOVED REQ still mentioned in an acceptance test.

## Close-out

| Subcommand | Role | Effect |
|---|---|---|
| `sync <change> [--dry-run] [--force]` | lead | Requires status `verified` (`--force` skips that, not the checks), a clean `check`, and no error in `bundle specs` (run `bundle specs --fix`). Applies each delta to its target concept `specs/<group>/<concept>.md`: MODIFIED replaces the whole block, or moves it (printed `MOVED`) when the delta sits in a different concept of the same capability or category; REMOVED drops it, ADDED appends; blocks are then sorted by id. Merges the delta's `sources` into the concept, deletes a concept left without blocks, regenerates the `index.md` files and appends `- <date> <change>: <ops>` to `specs/log.md`. Checks the listed ADRs can be accepted, accepts them, sets `status: archived` and `archived: <date>`, and moves the change to `changes/archive/<YYYY-MM-DD>-<change>/`. `--dry-run` prints the plan and writes nothing. Nothing is written if any check fails. |

## Branch, PR and resume

These need git with a remote named `origin`; the PR steps need an authenticated `gh`.

| Subcommand | Role | Effect |
|---|---|---|
| `start <change> --title T [--pr-title P] [--base B] [--requires a,b]` | lead | Fetches `origin/<base>`, refuses unless `.claude/sdd.json` is committed there. Creates branch `<branch_prefix><change>` and worktree `<worktree_dir>/sdd-<change>` from `origin/<base>`, runs `new`, writes `state.json` (`phase: spec`), commits `chore(sdd): start <change>`, pushes, opens a draft PR with `gh pr create --draft`, records its number. Prints `worktree`, `branch`, `pr` (or `PR missing (...)`) and `next: EnterWorktree path=...`. If anything fails before the push succeeds, it removes the worktree and branch so a retry is clean. Refuses if the branch or worktree already exists. Checks `--requires` for cycles before any side effect and warns about unmerged ones. |
| `checkpoint <change> [--phase P] [-m MSG]` | lead | Must run on the change's branch. With `--phase`, stores it in `state.json`; a phase at or after `plan` first checks `requires` (refuses while any is unmerged, merges `origin/<base>` in if a merged one is missing from the branch). Then `git add -A`, commits (default message `chore(sdd): <change> <phase>`), pushes. Prints `committed|nothing to commit, pushed <branch>, phase <p>`. |
| `set-pr <change> <number> [--url U]` | lead | Records a PR opened by hand in `state.json`, commits, pushes. |
| `requires <change> [<dep>... \| --clear]` | lead | Without deps, prints them (`-` if none). Otherwise stores the list (comma or space separated; no self-reference; cycles refused), commits, pushes and warns for each one not merged yet. |
| `deps <change>` | any | Prints `<state> <dep> <detail>` for every required change, transitively, deepest first. States: `ok`, `missing`, `ready`, `open`, `unknown` (see [Phases and states](phases-and-states.md#dependency-states)). Prints `next: ...` when something blocks. Exit 1 unless all are `ok`. |
| `resume <change> [--pr N]` | lead | Finds the branch (from `state.json`, else `<branch_prefix><change>`, or via `gh pr view N`), fetches it, reuses its worktree or creates one, fast-forwards it (`git pull --ff-only`), prints `worktree`, `branch`, `pr`, `status`, `phase <p>: <step>`. With requires: prints their states, and exits 1 with `blocked` / `next:` if any is unmerged, or merges `origin/<base>` in if one is missing. Ends with `next: EnterWorktree path=...`. |
| `finish <change>` | lead | After `sync`: on the change's branch, sets the archived `state.json` phase to `done`, commits `chore(sdd): sync <change>`, pushes, runs `gh pr ready`. Prints a WARN instead of failing if `gh` cannot mark it ready. Merging stays with you. |

Only `sdd.py` writes `state.json` (`start`, `checkpoint`, `set-pr`, `requires`, `finish`); the guard refuses every other write.

## Related

- [sdd tool roles](sdd-tool-roles.md)
- [File formats](file-formats.md)
- [OKF bundles](bundles.md)
- [Why sdd.py exists](../explanation/determinism.md)
