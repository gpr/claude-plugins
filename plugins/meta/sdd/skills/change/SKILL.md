---
name: change
description: Lead workflow for any request to change the codebase, and to adopt (write down) an existing area as a spec - triage, capabilities, invariants and ADRs, contract (TypeSpec API, CLI, UI mockup), user gate, plan, test-first implementation, verification, spec sync. Use for every feature, behavior change, or bug fix request, and when the user types /sdd:change.
argument-hint: <what you want changed> | resume <change-id> | adopt <area>
---

# Lead: spec-driven change workflow

You are the lead. You route, gate and close out. You do not write specs, plans, tests or
production code yourself in this workflow (the direct-execution path in step 1 excepted).
Keep your own context thin: pass agents IDs and file paths, read tool output, not whole files.

`sdd <args>` = the `mcp__sdd__sdd` tool with `args` as a list (`sdd check c1` is
`{"args": ["check", "c1"]}`). The guard blocks running the script through Bash.
First use in a repo (no `.claude/sdd.json`): `sdd init --survey` (writes nothing; lists the
ADR dirs, test dirs and build manifests the repo already has, and WARNs about a `specs/` or
`adrs/` sdd did not create). If the repo has code, delegate to `Explore`: how are the tests
run (whole suite, a file list), where would end-to-end tests go. Ask the user (AskUserQuestion)
for `adr_dir` (never an existing ADR folder: sdd keeps its own, old ADRs stay as they are and
are linked as plain references), `acceptance_dir`, `acceptance_cmd`, `unit_cmd`, and, when the
survey lists a TypeSpec or OpenAPI dir or the repo has a public API, CLI or UI, `contracts_dir`
and `contract_cmd` (validates the TypeSpec in the dir `contract-preview` builds, e.g. `npx tsp compile {dir}/api/sdd-main.tsp --no-emit`), then
`sdd init key=value ...` with the answers. Empty repo: `sdd init`, then ask for the two commands.
In a repo with code, `specs/` starts empty: behavior is written down as it is touched
(Baseline criteria, step 2), or up front per area with `adopt`.

The workflow agents are plugin agents: `sdd:spec-author`, `sdd:contract-designer`, `sdd:planner`,
`sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`. Built-ins reused: `Explore`,
`general-purpose`. Below they are named without the `sdd:` prefix.
Request: $ARGUMENTS
If it starts with `resume`, read [resume.md](resume.md) and follow it; with `adopt`,
[adopt.md](adopt.md).

## Paths at a glance
| Path (triage) | Steps | `checkpoint --phase` after `start` |
|---|---|---|
| full change | 2, 3, 4, 5, 6, 7, 8 | contract (skipped for `surface: none`), gate1, plan, gate2, acceptance, implement, verify, sync (finish: done) |
| fix (existing criterion) | 1, 4 with T1, 5, 7, 8 | plan, gate2, implement, verify, sync |
| fix with a criterion | 1, short 3, 4 with T1, 5, 7, 8 | gate1, plan, gate2, implement, verify, sync |
| adopt | Adopt, 2.2-6, 8 without code-review | gate1, plan, gate2, acceptance, verify, sync |

## Branch, worktree, PR, checkpoints
Every full change and fix lives on its own branch `sdd/<id>` in its own worktree, with a
draft PR. `sdd start <slug>` creates all three and generates the change id
`<NNNN>-<YYMMDD>-<slug>` (next free number, today's date): use the `id` line it prints as
`<id>` from then on. `state.json` stores `phase`, branch, base and PR number. Direct-path work
has no change id and none of this.
- **Checkpoint**: each time an agent (or you) finishes an artifact, run
  `sdd checkpoint <id> [--phase <next>] -m "<conventional message>"`. It stores the phase,
  commits everything and pushes. Phase ids: `spec contract gate1 plan gate2 acceptance implement
  verify sync done`. If it refuses because a required change is not merged, handle it as in [resume.md](resume.md) step 1. Pass `--phase` when the step you just finished moves the change to
  the next phase; omit it for further commits within a phase.
- **Requires**: a change may depend on others (`requires` in `state.json`, set with
  `sdd start --requires a,b` or `sdd requires <id> a b`). A dependency counts as done only
  when its PR is merged into the base. `sdd checkpoint --phase plan` (or later) and
  `sdd resume` refuse until then; `sdd deps <id>` shows where each one stands. Spec work
  (steps 2-3) may go ahead meanwhile.
- Never `git commit` or `git push` yourself for a change; never write `state.json`.

## 1. Triage (you, no agent unless context is missing)
If you need codebase facts to decide, delegate to `Explore` (quick or medium) with one
precise question. Do not read the repo yourself.

Apply this rule, in order, and state the result in one line:
- Changes observable behavior or a public contract (API, CLI, schema, event, UI flow)
  -> **full change** (spec delta).
- Makes a decision with lasting consequences (technology, data model, boundary,
  security posture) -> **full change** with ADR, even if behavior is unchanged.
- Code diverges from what users expect, but no living criterion covers it (an existing
  repo) -> **fix with a criterion**. `sdd start <slug> --title ... --pr-title "fix: ..."`, enter the
  worktree, set `size: fix` in intent.md, delegate to `spec-author` (request, Explore
  findings, "a fix: only ADDED criteria"): it writes the correct behavior as a criterion,
  plus Baseline ones for kept behavior nearby. `sdd checkpoint <id> --phase gate1 -m "docs(<id>): fix criterion"`.
  Short Gate 1: show only those criteria (id, name, Given/When/Then in one line each); approve /
  change / stop. The status stays `draft`. On approve, `sdd checkpoint <id> --phase plan -m "chore(<id>): approve fix criterion"`,
  write one test task citing the new criterion, then go to step 4 like any fix. If the spec-author
  needs more than ADDED criteria (a changed criterion, a section, an invariant, an ADR),
  `sdd check` refuses it: re-triage as a full change (step 9).
- Code diverges from an existing acceptance criterion or invariant (bug) -> **fix**: no
  spec delta, but a failing acceptance test first. `sdd start <slug> --title ... --pr-title "fix: ..."`, enter the worktree,
  set `size: fix` in intent.md, then `sdd checkpoint <id> --phase plan -m "chore(<id>): fix"` (so the size is committed
  with the phase), write one test task citing the existing criterion (`capabilities/<id>#AC-NN`) or invariant, then go
  to step 4 (it runs step 6 alongside).
- Anything else (refactor, rename, dependency bump, docs, config) -> **direct**: delegate
  to `general-purpose` (or do it yourself if trivial), run the unit tests, done.

## 2. Capture intent and spec delta
1. Pick a short kebab-case slug (`add-login`), never a number or date: `start` adds them. If the
   request builds on an open change (its PR not merged yet), add `--requires <id>[,<id>]` with
   the full ids. `sdd start <slug> --title "<title>" --pr-title "<feat|fix>: <title>"`
   (conventional type from triage); the change id is its `id` line. Then `EnterWorktree` with `path` = the worktree it
   prints (not when it says `in_place`: `start` already checked the branch out here). Do this before any agent writes an artifact. If it prints `PR missing`, create a
   draft PR for the branch (GitHub tools) and run `sdd set-pr <id> <number>`.
2. Delegate to `spec-author` with: change id, the user's request verbatim, and the
   Explore findings (summarized, with file paths; for code that no capability covers, the
   files that implement the behavior the change touches; when intent.md `## Why` has a
   `Source:` line, that document path and sections). It writes intent.md (with `surface:`), the new or changed
   capabilities and invariants under `changes/<id>/specs/`, and any draft ADRs, then runs `bundle` and `sdd check <id>`. Then
   `sdd checkpoint <id> --phase contract -m "docs(<id>): spec delta"` (`--phase gate1` when
   intent.md says `surface: none`).
3. If it returns open questions, ask the user (AskUserQuestion, max 4) and resume the
   same spec-author with the answers (SendMessage), do not start a new one.
4. Contract (only when `surface:` lists `api`, `cli` or `ui`): delegate to `contract-designer`
   with the change id (it fetches its own `sdd context <id> --contract` bundle). It
   writes `changes/<id>/contracts/` (TypeSpec, CLI synopsis, HTML mockup), runs `contract_cmd`
   on `sdd contract-preview <id>` and `sdd check <id>`. Open questions as in 2.3, resuming the same contract-designer. A spec
   problem it reports goes back to the spec-author (SendMessage), then the contract-designer
   again. Then `sdd checkpoint <id> --phase gate1 -m "docs(<id>): contract"`.

## 3. Gate 1 - user review (deep)
Show the user, compactly: the intent's Why/Outcome/Non-goals and `surface:`; per capability its id, title
and Intent line, then each AC id + name marked added/modified/retired (and any replaced
section); per invariant its id, Statement and Check; each ADR title + decision paragraph;
the contract from `sdd contract-diff <id>`: per TypeSpec operation one line
(`POST /orders -> 201 Order | 409`), the CLI synopsis line, per UI screen its mockup path
(offer to open it in a browser), each marked added/modified/retired, with the diff for a
small modification. Give file paths for the full text.
Ask: approve / change something / stop.
- Change -> resume spec-author with feedback on the spec or `surface:`, contract-designer with
  feedback on the contract (both, spec first, when a criterion changes), then Gate 1 again.
- Approve -> `sdd checkpoint <id> --status approved --phase plan -m "chore(<id>): approve spec"`.
  After a "change" round,
  checkpoint without `--phase`.

## 4. Plan and tasks
Delegate to `planner` with the change id. It writes plan.md and tasks.md.
For a `size: fix`, the contract is the existing code, so the test does not wait for the
plan: in the same message, also delegate T1 to `acceptance-tester` (step 6). Tell the
planner to leave T1's line as is and make its impl tasks `blocked-by: T1`. When T1's
tester returns, run `sdd freeze <id>` yourself (as in step 6).
When the planner returns: `sdd checkpoint <id> --phase gate2 -m "docs(<id>): plan and tasks"`
(a fix also waits for T1 and its freeze, then `--phase gate2` once both are in).

## 5. Gate 2 - automated coherence (light)
Run `sdd check <id>`. If it fails, resume the planner (or spec-author for spec errors)
with the exact ERROR lines. Max 2 rounds, then show the user the remaining errors.
Also confirm plan.md `## Contracts` is filled: the acceptance tests depend on it.
For a fix, wait for both agents instead: T1 ticked and frozen (`sdd verify-frozen <id>`
passes).
Show the user only: task count, contracts summary (one line each), and any WARN lines.
They may still object; otherwise continue:
`sdd checkpoint <id> --status implementing --phase acceptance -m "chore(<id>): start implementation"` (a fix: `--phase implement`,
its tests are already frozen).

## 6. Acceptance tests first (ATDD)
A fix already did this step alongside step 4; skip to step 7.
For each `(test)` task (several: one Agent call each, all in one message, so they run in
parallel): delegate to `acceptance-tester` with the change id and the task id (it fetches its
own `sdd context <id> <Tn>` bundle). It writes the tests, confirms they
fail for the right reason (a Baseline test: that it passes) and ticks its task; testers never
freeze. Settle any untestable criterion or MISMATCH below first. Then, once every test task
of the batch is back, run `sdd freeze <id>` once (one snapshot of the whole acceptance dir,
no half-written test in it) and `sdd checkpoint <id> --phase implement -m "test(<id>): acceptance tests"`
(`--phase verify` for a `size: baseline`). If `freeze` refuses because production code
already changed (Baseline tests), see step 9.
If a tester reports that a criterion is untestable or ambiguous -> step 9 (reopen).
If it reports `MISMATCH: <id>` (a Baseline test fails on the current code), ask the user which
is right: the code (step 9, the criterion is corrected and stays Baseline) or the criterion
(a latent bug: step 9, the spec-author drops its Baseline line, the planner adds an impl task;
in an adopt, see [adopt.md](adopt.md) instead).

## 7. Implementation (inner TDD)
A `size: baseline` change has no impl tasks: go to step 8.
Take the `(impl)` tasks whose blocked-by tasks are done one at a time, each given as the change
id and the task id (the implementer fetches its own `sdd context <id> <Tn> --plan` bundle). Delegate the first to a new
`implementer` and resume that same implementer (SendMessage) for each next task: it keeps
what it learned about the code. Spawn a new one instead after it returned BLOCKED, or when
it has done 4 tasks (its context grows with each). Never run implementers in parallel or with
`isolation: "worktree"`: an isolated worktree starts from the default branch, without this
change's tasks, plan or frozen tests.
If an implementer returns `BLOCKED: <criterion or invariant id> <reason>` -> step 9. Never relax a test.
After each task returns:
`sdd checkpoint <id> -m "feat(<id>): <Tn> <task title>"`; after the last impl task add
`--phase verify`.

## 8. Verify and close out
1. In one message, delegate both (they only read, so they run in parallel):
   - `verifier` with the change id. It runs the frozen-test check, the acceptance and unit
     suites, `sdd check <id> --tests`, and reviews the diff against the spec. It checks
     conformance, not bugs outside its criteria;
   - `general-purpose`: run the built-in `code-review` skill on the change's diff against the
     base branch (uncommitted changes included) and return only the findings list. Never
     pass `--fix`: the implementer fixes code, test first. Skip it for an adopt; when the
     skill is not available, say so to the user in one line.
2. On a verifier FAIL: route each of its findings first (implementer for code, step 9 for
   spec problems), checkpoint after each fix, then go back to 8.1.
3. On PASS, route each code-review finding:
   - a bug inside the behavior of an existing criterion -> implementer, with the finding and the
     id of the task whose files it touches (it fetches that task's bundle); it adds a
     failing unit test first;
   - a defect in a frozen acceptance test, or a fix that needs behavior
     (validation, a new error path) that no criterion describes -> step 9;
   - not worth fixing -> tell the user in one line, then go on.
   After any fix, go back to 8.1. Max 2 review rounds: after that, list the remaining
   findings to the user and let them decide. Once the verifier passes and no finding is
   left to fix, go on.
4. Then `sdd checkpoint <id> --status verified --phase sync -m "chore(<id>): verified"`, then
   `sdd sync <id>` (it checks everything before it writes the specs, so no dry run). Sync merges `origin/<base>` in when the base moved, writes the new
   concepts, merges each CapabilityDelta unit by unit into the specs/ OKF bundle (status
   `stable`, regenerated indexes, `log.md`), accepts the ADRs, copies the change's contract
   files into `contracts_dir` and archives the change. If it refuses (a merge conflict, a
   `specs bundle:` error, a CONFLICT), read [sync-conflicts.md](sync-conflicts.md).
5. `sdd finish <id>`: marks the phase done, commits the synced specs/ADRs/archive, merges
   `origin/<base>` again if it moved since the sync, pushes and marks the PR ready for review
   (merging stays with the user). If that merge conflicts, read
   [sync-conflicts.md](sync-conflicts.md). Report to the user in
   3 lines: what changed, criterion and invariant ids, anything deferred, plus the PR link.

## 9. Reopen (failure path)
A wrong or untestable criterion or invariant goes back to the spec, never into the code or
the tests. When a step sends you here, read [reopen.md](reopen.md) and follow it.

## Status
The plugin shows the active change, its status and task progress above the prompt, and
`/sdd` opens a pane with every open change, its tasks, the last check and running
workflow agents; `/sdd phase` opens a pane with the workflow phase the change is in.
You do not need to recap progress to the user; point them to it.

## Token rules
- Agents get `sdd context` bundles, not whole files and not your conversation: give them the
  change and task ids and let them fetch the bundle; never fetch it to paste it.
- Resume an agent (SendMessage) for follow-ups instead of spawning a new one.
- When the next step needs an agent's result, wait for its completion notice (or run it in
  the foreground); never poll with `sleep` or by reading its files.
- Never paste file contents into your replies to the user; give paths and IDs.
