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
  at: 2026-10-18T00:00:00Z
---

# sdd subcommands

Agents and the lead call `sdd.py` through the `mcp__sdd__sdd` tool, with the subcommand and its arguments as a list: `sdd check c1` is `{"args": ["check", "c1"]}`. The guard refuses `python3 .../sdd.py` from Bash for every subagent. The lead (and you, outside Claude Code) can still run `python3 <plugin>/tools/sdd.py <subcommand> ...` directly.

**Exit codes:** `0` ok, `1` errors found, `2` usage error (unknown subcommand, bad arguments, unknown change).
**Output:** terse, one fact per line. Problems start with `ERROR` or `WARN`; summaries with `OK` or `FAIL`.
**Working directory:** `sdd.py` resolves the project root from the cwd at start-up; see [Configuration](configuration.md#project-root).

**Role** is who may run the subcommand through the tool ([`SDD_RULES`](sdd-tool-roles.md)). *any* means every role.

**Change ids:** every subcommand that takes a `<change>` accepts only an id (`[a-z0-9][a-z0-9-]{1,60}`, not `specs`, `adrs` or `archive`), never a path such as `archive/<date>-x` or `../x`. A flag given without its value (`--title` at the end) is a usage error (exit 2). An invalid `.claude/sdd.json` (bad JSON, not an object) makes every subcommand print `ERROR .claude/sdd.json: ...` and exit 2.

## Workspace

| Subcommand | Role | Effect |
|---|---|---|
| `init [--survey] [key=value ...]` | lead | Creates `specs/` and `adrs/` (each with its `index.md`, `log.md` and `.templates/` concept templates), `changes/`, `tests/acceptance/` (configured names), writes `.claude/sdd.json` with the defaults if missing, adds `/<worktree_dir>/` to `.gitignore` and `/<specs_dir>/log.md merge=union`, `/<adr_dir>/log.md merge=union` to `.gitattributes` (run it again in a repo initialised by an older sdd to add them). Idempotent: prints `created: nothing, already initialised`. First prints `found:` with what the repo already has, from a walk up to 4 levels deep that skips hidden, vendored and build dirs: ADR-like dirs (the usual names, or 2+ `.md` files mostly numbered `NNNN-` or with Status and Decision headings; not an sdd bundle), test dirs (the topmost dir holding `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.js`, `*_spec.rb`, `*Test.java` and similar files, or a test-named dir with them below), build manifests; at most 10 per kind. A `specs_dir` or `adr_dir` that holds `.md` files but none of `index.md`, `log.md`, `.templates/` (sdd's own, whose lost `index.md` init recreates) gets `WARN ... sdd did not create` and exit 1: without `.claude/sdd.json` nothing is written, with one that folder is left alone and the rest is created. `key=value` (any key of [the config](configuration.md)) writes a new `.claude/sdd.json` with those values and initialises with it, once the checks pass; it refuses once the file exists, and a `*_dir` value must be a relative path inside the repo (not empty, `.`, absolute or with `..`). `--survey` prints `found:` and the WARNs and writes nothing (it takes no `key=value`). See [Adopt sdd in an existing repository](../how-to/adopt-an-existing-repo.md). |
| `config` | any | Prints the effective configuration as JSON, with `root`. |
| `status [<change>] [--json]` | any | One line per open change: `status`, `tasks=done/total`, `size`, and `phase`, `pr`, `requires` when stored. With a change id, also one line per task. `--json` is what the band and panes read. Also counts archived changes. |

## Change scaffolding and status

| Subcommand | Role | Effect |
|---|---|---|
| `new <change> [--title T]` | lead | Creates `changes/<change>/` with `intent.md`, `plan.md`, `tasks.md` from the templates, the generated `index.md`, and an empty `specs/`. The id must be kebab-case, 2–61 chars (`[a-z0-9][a-z0-9-]{1,60}`), and not `specs`, `adrs` or `archive`. Fails if the directory exists. Normally run by `start`, which passes the id it generated; `new` takes the id as given. |
| `set-status <change> <status>` | lead | Rewrites `status:` in `intent.md` front matter. Status is one of `draft approved implementing verified archived`. Prints `<change>: <old> -> <new>`. |

## Concepts, deltas and ADRs

| Subcommand | Role | Effect |
|---|---|---|
| `delta-new <change> <concept id> [--title T]` | lead, spec-author | `capabilities/<id>` or `invariants/<id>` (snake_case). If no living concept has that id: writes `changes/<change>/specs/<id>.md` from the Capability or Invariant template (the repo's `specs/.templates/` copy if present), filling title, heading, `generated.by`/`at`; `--title` defaults to the last segment, capitalised. If a living capability has it: writes a CapabilityDelta and prints the next free AC id. A living invariant: error, use `delta-stub`. Fails if the file exists. Refreshes the change's indexes. |
| `delta-stub <change> <capability>#AC-NN [--retire]` | lead, spec-author | Copies the living criterion into the change's CapabilityDelta (created if needed) under `## MODIFIED`, or under `## RETIRED` with `- **Retired**: <why it is retired>`, with its `<!-- base: <hash> -->`. Fails for an unknown, retired or already copied criterion. |
| `delta-stub <change> <capability> --section <Name>` | lead, spec-author | Copies one of Title, Description, Intent, Scope, Invariants, Decisions, Verification under `## SECTIONS` as `### <Name>` with its base. |
| `delta-stub <change> <capability> --deprecate` | lead, spec-author | Sets `status: deprecated` and `base:` (the capability's hash) in the CapabilityDelta. |
| `delta-stub <change> <invariant> [--deprecate]` | lead, spec-author | Copies the living invariant to the change with `base:` in its front matter (and `status: deprecated`). |
| `contract-stub <change> <kind>/<name>.<ext>` | lead, contract-designer | `api/<name>.tsp`, `cli/<name>.md` or `ui/<name>.html` (a leading `contracts_dir/` is dropped). Copies the living contract file to `changes/<change>/contracts/` with a base line (`// base: <hash>` or `<!-- base: <hash> -->`), or, when there is none, writes a new file from the kind's template. Fails if the change's file exists. |
| `contract-stub <change> <path> --retire` | lead, contract-designer | Records `<path>@<hash>` in intent.md `retire_contracts`; `sync` deletes the living file. Fails when the living file does not exist or the change has its own copy. |
| `contract-preview <change> [--remove]` | lead, contract-designer | Rebuilds `<worktree_dir>/sdd-<change>-contracts/`: the living contract files (only `api/*.tsp`, `cli/*.md`, `ui/*.html`; generated output and configs stay out) minus the retired ones, with the change's files (base lines dropped) over them, and `api/sdd-main.tsp` importing every TypeSpec file. Prints `dir`, the file count and `run: <contract_cmd with {dir}>`; sdd.py never runs it. `--remove` deletes the dir. |
| `contract-diff <change>` | everyone | Per contract file `ADDED` (the file, up to 60 lines), `MODIFIED` (a unified diff against the living file, base line left out), `UNCHANGED`, and `RETIRED`. What the lead shows at Gate 1. |
| `adr-new <title> [--supersedes ADR-NNNN]` | lead, spec-author | Creates `adrs/NNNN_<slug>.md` from the ADR template (the repo's `adrs/.templates/` copy if present) with the next free number, `status: draft`, `decided:` today, and `supersedes: [<concept id>]`. The slug is the title lower-cased, non-alphanumerics folded to `_`, 50 chars max. The superseded ADR must exist. Refreshes `adrs/index.md`. |
| `adr-accept <ADR-NNNN>` | lead | `draft` → `stable`, `decided:` today. Each ADR it supersedes becomes `deprecated` with `superseded_by:`. Appends to `adrs/log.md` and refreshes the index. Accepting a stable ADR is a no-op; any other status is an error. `sync` does this for the ADRs listed in `intent.md`. |

## Checks and context

| Subcommand | Role | Effect |
|---|---|---|
| `check <change> [--tests]` | any | Traceability, conflict and bundle check, see [the rules](#check-rules). Ends with `OK|FAIL <change>: <n> unit(s), <n> tasks, <n> errors, <n> warnings`. Exit 1 on any error. |
| `context <change> <task> [--plan]` | any | Prints the minimal bundle for one task, see [Context bundles](../explanation/context-bundles.md). For an `(impl)` task it also lists `id: title — statement` of every invariant in force (living and not deprecated, plus the change's new or replaced ones, minus those it deprecates) that the task does not name. A `(test)` or `(impl)` task also gets `## Contract files`: the contract files citing its criteria in full (the change's copy, else the living file) and the paths of the others. |
| `context <change> --contract` | any | The contract-designer's bundle: `surface`, `contracts_dir` and `contract_cmd`; the criteria the change adds or modifies; the contract files citing them or the touched capabilities' other criteria, in full, and the paths of the others; the retired ones. |
| `bundle <specs\|adrs\|change> [--fix]` | any; `--fix` on `specs` or `adrs`: lead; `--fix` on a change: lead, spec-author | Validates an OKF bundle: `specs/`, `adrs/` or `changes/<change>/`, see [OKF bundles](bundles.md#bundle-checks). Prints `FIXED`, `WARN`, `ERROR` lines then `OK|FAIL <target>: <n> errors, <n> warnings` (`, <n> fixed` with `--fix`). `--fix` repairs findings marked `[fixable]` and is idempotent. Exit 1 on any ERROR. The same check is the `mcp__sdd__bundle` tool ([roles](sdd-tool-roles.md#the-bundle-tool)). |
| `freeze <change> [--after-code]` | lead | Writes `changes/<change>/frozen.json` ([format](file-formats.md#frozenjson)): sha256 of every file under the acceptance dir, tests, helpers and fixtures alike (git's view: ignored files, dot-dirs, `__pycache__`, `node_modules` and `*.pyc` are left out), and the merge-base with `origin/<base>`. Fails (exit 1) if no file there cites one of the change's test units. Re-running replaces the snapshot. The lead runs it once after each batch of test tasks. When the change has Baseline criteria and their test files are new or changed, it records `baseline: {commit, files}` in `state.json`, where `commit` is the merge-base with `origin/<base>`. It refuses (exit 1, nothing written) once files outside `changes/`, the acceptance dir, `specs/`, `adrs/`, `.claude/` and `.gitignore` differ from that commit; `--after-code` (the lead, on a reopen) freezes anyway with a WARN. Without git or an origin base: `WARN no git base`, nothing recorded. A Baseline test file that also cites a non-Baseline unit gets a WARN: the base run runs whole files. |
| `baseline-tree <change> [--remove] [--link PATH ...]` | lead, verifier | Needs the `baseline` record. Creates a detached worktree `<worktree_dir>/sdd-<change>-baseline` at the recorded commit, copies the current acceptance dir into it, symlinks `node_modules`, `.venv`, `venv` and each `--link` path (inside the repo) from the change's tree, and prints `worktree`, `commit`, `files`, `linked` and `run: <acceptance_cmd with the Baseline files>`. sdd.py never runs it. `--remove` deletes the worktree. |
| `verify-frozen <change>` | any | Re-hashes the acceptance dir. `ERROR <file> modified after freeze`, `deleted after freeze` or `added after freeze`. Files a test run writes (`.pyc`, `.log`, `.tmp`, `junit*.xml`, `coverage*`, caches, dot-paths) and git-ignored files are not part of the set. A difference is accepted, with `WARN  <file> <what> by origin/<base> after freeze (accepted)`, only when the file is exactly as the local `origin/<base>` has it and the base changed it since the recorded commit (a base merge brought it in). Summary `OK|FAIL <n> frozen file(s), <n> tampered`. Exit 1 if `frozen.json` is missing or anything was tampered. A pre-v2 `frozen.json` (a flat map) is checked file by file, without the added-file check. |

### check rules

Errors (exit 1):
- `intent.md` status not one of the five statuses, or `size` not one of `change fix baseline`.
- A unit (criterion or invariant) appears twice in the change.
- A new concept's structure: see [File formats](file-formats.md#capability) (type, title, status, required sections, Given/When/Then, Statement, `- Check:`, Holds and Violation).
- A full Capability over a living one; a CapabilityDelta for a capability that does not exist or is deprecated; a base on a new concept.
- CapabilityDelta: a `##` section other than ADDED/MODIFIED/RETIRED/SECTIONS, or a non-criterion `###` heading under the first three; a SECTIONS name given twice; an ADDED id that exists (retired ones included; the message names the next free id); a MODIFIED or RETIRED id that is not live; a missing base, or one that differs from the current hash: `CONFLICT base <a> != current <b>`; RETIRED without a reason; a SECTIONS entry that is not editable, empty, or whose base differs; a deprecation without base or with ADDED/MODIFIED criteria.
- An invariant replacement without base, or with a stale one (CONFLICT).
- Task problems: duplicate id, `blocked-by` an unknown task; a citation of an unknown unit, of a bare capability, of a criterion on an invariant, of a retired criterion or deprecated invariant; a `(test)` task on a unit this change retires or deprecates; a `(test)`/`(impl)` task citing nothing.
- A referenced ADR (in `intent.md` `adrs:` or a task) has no file, or is `deprecated`.
- `plan.md` cites an unknown unit or ADR (HTML comments ignored).
- Once `tasks.md` has tasks: an added or modified criterion with no `(test)` task or no `(impl)` task (a Baseline criterion needs no `(impl)` task); an added or modified invariant with no `(test)` task.
- A `- **Baseline**` line on a MODIFIED or RETIRED criterion, or one without a location.
- `size: fix`: a touched unit that is not an ADDED criterion (MODIFIED, RETIRED, deprecated, an invariant), a SECTIONS entry, or ADRs in `intent.md`.
- `size: baseline`: a criterion that is not Baseline, any MODIFIED, RETIRED or deprecated unit, a SECTIONS entry, any `(impl)` task.
- Any bundle ERROR of the change (see [OKF bundles](bundles.md#change)), printed with a `bundle:` prefix.
- No tasks while status is not `draft`.
- Contract files ([format](file-formats.md#contract-files)): a file outside `api/*.tsp`, `cli/*.md`, `ui/*.html`; a kind `surface` does not list; no criterion cited, or a citation that does not resolve; a CLI file missing one of its four sections; a file replacing a living one without a base line; `CONFLICT` when the living file changed since `contract-stub` (or is gone); a `retire_contracts` entry that is not a contract path, also has a copy in the change, names no living file, or whose base differs (`CONFLICT retire`); an unknown `surface` kind; after the `contract` phase, a declared kind with no file.
- `size: change` without `surface:` while status `draft` and stored phase `contract` or `gate1`.

Warnings:
- No spec delta (unless `size: fix`), or a CapabilityDelta that changes nothing.
- A missing description, a placeholder left, a link that does not resolve or points to a deprecated concept.
- A living capability that still lists an invariant this change deprecates.
- A draft ADR linked from a concept (Decisions, Rationale) but not listed in `intent.md` `adrs:` (sync would not accept it).
- Any bundle WARN of the change, prefixed `bundle:` (a stale `index.md`, a missing `type:`).
- The stored phase does not fit the status (see [Phases and states](phases-and-states.md#phase-and-status)).
- An `(impl)` task not `blocked-by` the `(test)` task(s) covering its criteria.
- An `(impl)` task that cites only Baseline criteria.
- `size: change` without `surface:` (outside the case above); contract files, `retire_contracts` or a `surface` in a `size: fix` or `baseline` change.

With `--tests`, also:
- Error: a unit to be tested (added or modified, plus existing units that a `(test)` task targets, the fix path) is cited by no file under the acceptance dir.
- Error: `open tasks: T1,T3` for unticked tasks.
- Warning: a retired criterion or deprecated invariant still cited in an acceptance test.

## Close-out

| Subcommand | Role | Effect |
|---|---|---|
| `sync <change> [--dry-run] [--force]` | lead | For a change made by `start` (its `state.json` names a branch): must run on that branch; fetches `origin/<base>` and, if it has commits the branch lacks, merges it in first (`merged origin/<base> into the branch (the living specs are current)`, pushed; a git conflict aborts the merge and names the files), so the checks below see the living spec as it is on the base. `--dry-run` does not fetch: it judges the `origin/<base>` it has and only warns `WARN origin/<base> has commits this branch lacks`. When the fetch fails, sync warns `could not fetch origin/<base>` and judges the ref as last fetched. Requires status `verified` (`--force` skips that, not the checks), a clean `check`, and no error in `bundle specs`. Writes each new concept to `specs/` and replaces each invariant replacement, with template comments, `base:` and `- **Baseline**` lines dropped and `status: stable` (or `deprecated`). Merges each CapabilityDelta unit by unit: MODIFIED replaces the criterion, RETIRED leaves its heading and the reason, ADDED inserts, criteria are sorted, SECTIONS replace whole sections, `sources` are merged. Sets `generated.at` to now on every new or replaced concept; a CapabilityDelta merge keeps the capability's `generated` (so two changes merging different criteria don't conflict on it in git). Prints one line per unit (`ADDED`, `MODIFIED`, `RETIRED`, `SECTION`, `DEPRECATED`). Copies each contract file of the change to `contracts_dir` without its base line and deletes the `retire_contracts` files (`CONTRACT ADD`, `CONTRACT REPLACE`, `CONTRACT RETIRE` lines). Regenerates the indexes, appends `* **Update**: <change>: <units>` to `specs/log.md`, accepts the listed ADRs, sets `status: archived` and `archived: <date>`, and moves the change to `changes/archive/<YYYY-MM-DD>-<change>/`. `--dry-run` prints the plan and writes nothing. Nothing is written if any check fails. |

## Branch, PR and resume

These need git with a remote named `origin`; the PR steps need an authenticated `gh`.

| Subcommand | Role | Effect |
|---|---|---|
| `start <slug> --title T [--pr-title P] [--base B] [--requires a,b]` | lead | Fetches `origin/<base>` and generates the change id `<change>` = `<NNNN>-<YYMMDD>-<slug>`: one more than the highest number of a generated id among `changes/` and `changes/archive/` (here and on `origin/<base>`) and the `<branch_prefix>` branches (local and on origin, from `git ls-remote`), zero-padded to 4 digits, then today's date. Ids that do not start with a number and a date (made before) are ignored. The slug is kebab-case, 1–49 chars, and must not already carry the prefix (exit 2). Refuses unless `.claude/sdd.json` is committed there, and warns when its `.gitattributes` lacks the `merge=union` lines for the logs. Creates branch `<branch_prefix><change>` and worktree `<worktree_dir>/sdd-<change>` from `origin/<base>`, runs `new`, writes `state.json` (`phase: spec`), commits `chore(sdd): start <change>`, pushes, opens a draft PR with `gh pr create --draft`, records its number. Prints `id <change>`, `worktree`, `branch`, `pr` (or `PR missing (...)`) and `next: EnterWorktree path=...`. If anything fails before the push succeeds, it removes the worktree and branch so a retry is clean. With `in_place`, it refuses (exit 1) while `git status --porcelain` lists anything, checks the branch out in this checkout instead of adding a worktree, prints `worktree <root> (in_place)` and `next: continue in this checkout (in_place)`, and on failure switches back and deletes the branch. Refuses if the branch or worktree already exists. Two starts on different machines in the same moment can draw the same number; the slug and the date still keep their ids apart in most cases. Checks `--requires` (full ids) for cycles before any side effect and warns about unmerged ones. |
| `checkpoint <change> [--status S] [--phase P] [-m MSG]` | lead | Must run on the change's branch. With `--status`, sets intent.md's status like `set-status`, after the status, phase and `requires` checks pass, so a checkpoint they refuse writes nothing (a secrets refusal at commit time leaves the new status uncommitted). With `--phase`, stores it in `state.json`; a phase at or after `plan` first checks `requires` (refuses while any is unmerged, merges `origin/<base>` in if a merged one is missing from the branch). Then regenerates the change's indexes, `git add -A`, commits (default message `chore(sdd): <change> <phase>`), pushes. Prints `added <n> new file(s): ...` and `committed|nothing to commit, pushed <branch>, phase <p>`. Like every sdd commit (`start`, `set-pr`, `requires`, `finish`), it refuses (exit 1, the files unstaged, nothing committed) new files that look like secrets: `.env*` (not `.example`, `.sample`, `.template`), `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa`/`id_ed25519` and similar, `credentials` and `credentials.json`/`.yaml`/`.ini`/... |
| `set-pr <change> <number> [--url U]` | lead | Records a PR opened by hand in `state.json`, commits, pushes. |
| `requires <change> [<dep>... \| --clear]` | lead | Without deps, prints them (`-` if none). Otherwise stores the list (comma or space separated; no self-reference; cycles refused), commits, pushes and warns for each one not merged yet. |
| `deps <change>` | any | Prints `<state> <dep> <detail>` for every required change, transitively, deepest first. States: `ok`, `missing`, `ready`, `open`, `unknown` (see [Phases and states](phases-and-states.md#dependency-states)). Prints `next: ...` when something blocks. Exit 1 unless all are `ok`. |
| `resume <change> [--pr N]` | lead | Finds the branch (from `state.json`, else `<branch_prefix><change>`, or via `gh pr view N`), fetches it, reuses its worktree or creates one, fast-forwards it (`git pull --ff-only`), prints `worktree`, `branch`, `pr`, `status`, `phase <p>: <step>`. With requires: prints their states, and exits 1 with `blocked` / `next:` if any is unmerged, or merges `origin/<base>` in if one is missing. Ends with `next: EnterWorktree path=...`. With `in_place`, it checks the branch out in this checkout (refusing while it is dirty, unless already on the branch) and ends with `next: continue in this checkout (in_place)`. |
| `finish <change>` | lead | After `sync`: on the change's branch, sets the archived `state.json` phase to `done`, commits `chore(sdd): sync <change>`, fetches `origin/<base>` and merges it in if it moved since the sync (a git conflict aborts the merge and points to [Conflict after sync](../how-to/resolve-sync-conflict.md#conflict-after-sync)), pushes, runs `gh pr ready`. Prints a WARN instead of failing if `gh` cannot mark it ready. Merging stays with you. |

Only `sdd.py` writes `state.json` (`start`, `checkpoint`, `set-pr`, `requires`, `finish`, and `freeze` for the Baseline record); the guard refuses every other write.

## Related

- [sdd tool roles](sdd-tool-roles.md)
- [File formats](file-formats.md)
- [OKF bundles](bundles.md)
- [Why sdd.py exists](../explanation/determinism.md)
