---
name: change
description: Lead workflow for any request to change the codebase, and to adopt (write down) an existing area as a spec - triage, capabilities, invariants and ADRs, user gate, plan, test-first implementation, verification, spec sync. Use for every feature, behavior change, or bug fix request, and when the user types /sdd:change.
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
are linked as plain references), `acceptance_dir`, `acceptance_cmd`, `unit_cmd`, then
`sdd init key=value ...` with the answers. Empty repo: `sdd init`, then ask for the two commands.
In a repo with code, `specs/` starts empty: behavior is written down as it is touched
(Baseline criteria, step 2), or up front per area with `adopt`.

The workflow agents are plugin agents: `sdd:spec-author`, `sdd:planner`,
`sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`. Built-ins reused: `Explore`,
`general-purpose`. Below they are named without the `sdd:` prefix.
Request: $ARGUMENTS
If it starts with `resume`, see "Resume" below; with `adopt`, see "Adopt" below.

## Paths at a glance
| Path (triage) | Steps | `checkpoint --phase` after `start` |
|---|---|---|
| full change | 2, 3, 4, 5, 6, 7, 8 | gate1, plan, gate2, acceptance, implement, verify, sync (finish: done) |
| fix (existing criterion) | 1, 4 with T1, 5, 7, 8 | plan, gate2, implement, verify, sync |
| fix with a criterion | 1, short 3, 4 with T1, 5, 7, 8 | gate1, plan, gate2, implement, verify, sync |
| adopt | Adopt, 2.2-6, 8 without code-review | gate1, plan, gate2, acceptance, verify, sync |

## Branch, worktree, PR, checkpoints
Every full change and fix lives on its own branch `sdd/<id>` in its own worktree, with a
draft PR. `sdd start` creates all three; `state.json` stores `phase`, branch, base and PR
number. Direct-path work has no change id and none of this.
- **Checkpoint**: each time an agent (or you) finishes an artifact, run
  `sdd checkpoint <id> [--phase <next>] -m "<conventional message>"`. It stores the phase,
  commits everything and pushes. Phase ids: `spec gate1 plan gate2 acceptance implement
  verify sync done`. If it refuses because a required change is not merged, handle it as in Resume. Pass `--phase` when the step you just finished moves the change to
  the next phase; omit it for further commits within a phase.
- **Requires**: a change may depend on others (`requires` in `state.json`, set with
  `sdd start --requires a,b` or `sdd requires <id> a b`). A dependency counts as done only
  when its PR is merged into the base. `sdd checkpoint --phase plan` (or later) and
  `sdd resume` refuse until then; `sdd deps <id>` shows where each one stands. Spec work
  (steps 2-3) may go ahead meanwhile.
- Never `git commit` or `git push` yourself for a change; never write `state.json`.

## Resume
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
2. `EnterWorktree` with `path` = the printed worktree. From here every `sdd` call acts on it.
3. `sdd status <id>`, then continue at the step the phase names (spec -> 2, gate1 -> 3,
   plan -> 4, gate2 -> 5, acceptance -> 6, implement -> 7, verify -> 8, sync -> 8.4,
   done -> nothing left; "Paths at a glance" gives each path's order). A stored phase can lag a step that was done but not
   checkpointed: trust the files (`sdd check`, task ticks) over the phase when they disagree.
   Resume a partly written spec or plan with the same agent type and the files as context.
   Run the `bundle` tool on the change first. A change written in the old REQ/INV format
   cannot be fixed by `bundle`: resume spec-author to rewrite its delta as concepts.

## Adopt
`adopt <area>` writes down what an existing area of the code does, as Baseline criteria
(sdd:formats), with passing acceptance tests, and changes no code.
Delegate to `Explore` (medium): the area's public surface, the files that implement it, and
existing tests for it. `sdd start <id> --title "Baseline: <area>" --pr-title "docs(<id>): baseline spec"`,
enter the worktree, set `size: baseline` in intent.md, then steps 2.2-6 as usual (spec-author
with the Explore findings, told the change is an adopt; Gate 1 asks "is this what the code
does, and what it should keep doing?"). Step 6 ends with `--phase verify`; skip step 7 and the
code-review in step 8.3. A MISMATCH (step 6) in an adopt is either a wrong criterion
(spec-author) or a bug: drop that criterion from the adopt and offer a fix as its own change.

## 1. Triage (you, no agent unless context is missing)
If you need codebase facts to decide, delegate to `Explore` (quick or medium) with one
precise question. Do not read the repo yourself.

Apply this rule, in order, and state the result in one line:
- Changes observable behavior or a public contract (API, CLI, schema, event, UI flow)
  -> **full change** (spec delta).
- Makes a decision with lasting consequences (technology, data model, boundary,
  security posture) -> **full change** with ADR, even if behavior is unchanged.
- Code diverges from what users expect, but no living criterion covers it (an existing
  repo) -> **fix with a criterion**. `sdd start <id> --title ... --pr-title "fix: ..."`, enter the
  worktree, set `size: fix` in intent.md, delegate to `spec-author` (request, Explore
  findings, "a fix: only ADDED criteria"): it writes the correct behavior as a criterion,
  plus Baseline ones for kept behavior nearby. `sdd checkpoint <id> --phase gate1 -m "docs(<id>): fix criterion"`.
  Short Gate 1: show only those criteria (id, name, Given/When/Then in one line each); approve /
  change / stop. The status stays `draft`. On approve, `sdd checkpoint <id> --phase plan -m "chore(<id>): approve fix criterion"`,
  write one test task citing the new criterion, then go to step 4 like any fix. If the spec-author
  needs more than ADDED criteria (a changed criterion, a section, an invariant, an ADR),
  `sdd check` refuses it: re-triage as a full change (step 9).
- Code diverges from an existing acceptance criterion or invariant (bug) -> **fix**: no
  spec delta, but a failing acceptance test first. `sdd start <id> --title ... --pr-title "fix: ..."`, enter the worktree,
  set `size: fix` in intent.md, then `sdd checkpoint <id> --phase plan -m "chore(<id>): fix"` (so the size is committed
  with the phase), write one test task citing the existing criterion (`capabilities/<id>#AC-NN`) or invariant, then go
  to step 4 (it runs step 6 alongside).
- Anything else (refactor, rename, dependency bump, docs, config) -> **direct**: delegate
  to `general-purpose` (or do it yourself if trivial), run the unit tests, done.

## 2. Capture intent and spec delta
1. Pick a kebab-case id. If the request builds on an open change (its PR not merged yet),
   add `--requires <id>[,<id>]`. `sdd start <id> --title "<title>" --pr-title "<feat|fix>: <title>"`
   (conventional type from triage). Then `EnterWorktree` with `path` = the worktree it
   prints. Do this before any agent writes an artifact. If it prints `PR missing`, create a
   draft PR for the branch (GitHub tools) and run `sdd set-pr <id> <number>`.
2. Delegate to `spec-author` with: change id, the user's request verbatim, and the
   Explore findings (summarized, with file paths; for code that no capability covers, the
   files that implement the behavior the change touches). It writes intent.md, the new or changed
   capabilities and invariants under `changes/<id>/specs/`, and any draft ADRs, then runs `bundle` and `sdd check <id>`. Then
   `sdd checkpoint <id> --phase gate1 -m "docs(<id>): spec delta"`.
3. If it returns open questions, ask the user (AskUserQuestion, max 4) and resume the
   same spec-author with the answers (SendMessage), do not start a new one.

## 3. Gate 1 - user review (deep)
Show the user, compactly: the intent's Why/Outcome/Non-goals; per capability its id, title
and Intent line, then each AC id + name marked added/modified/retired (and any replaced
section); per invariant its id, Statement and Check; each ADR title + decision paragraph. Give file paths for the full text.
Ask: approve / change something / stop.
- Change -> resume spec-author with the feedback, then Gate 1 again.
- Approve -> `sdd set-status <id> approved`, then
  `sdd checkpoint <id> --phase plan -m "chore(<id>): approve spec"`. After a "change" round,
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
They may still object; otherwise continue. `sdd set-status <id> implementing`, then
`sdd checkpoint <id> --phase acceptance -m "chore(<id>): start implementation"` (a fix: `--phase implement`,
its tests are already frozen).

## 6. Acceptance tests first (ATDD)
A fix already did this step alongside step 4; skip to step 7.
For each `(test)` task (several: one Agent call each, all in one message, so they run in
parallel): delegate to `acceptance-tester` with
the `sdd context <id> <Tn>` output pasted in the prompt. It writes the tests, confirms they
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
in an adopt, see "Adopt" instead).

## 7. Implementation (inner TDD)
A `size: baseline` change has no impl tasks: go to step 8.
For each `(impl)` task whose blocked-by tasks are done, one at a time, delegate to
`implementer` with the `sdd context <id> <Tn> --plan` output pasted in the prompt. Never run
implementers in parallel or with `isolation: "worktree"`: an isolated worktree starts from
the default branch, without this change's tasks, plan or frozen tests.
If an implementer returns `BLOCKED: <criterion or invariant id> <reason>` -> step 9. Never relax a test.
After each implementer returns:
`sdd checkpoint <id> -m "feat(<id>): <Tn> <task title>"`; after the last impl task add
`--phase verify`.

## 8. Verify and close out
1. Delegate to `verifier` with the change id. It runs the frozen-test check, the
   acceptance and unit suites, `sdd check <id> --tests`, and reviews the diff.
2. On FAIL: route each finding (implementer for code, step 9 for spec problems);
   checkpoint after each fix.
3. On PASS, review before syncing: the verifier checks conformance to the spec, not bugs
   outside its criteria. Delegate to `general-purpose`: run the built-in `code-review`
   skill on the change's diff against the base branch (uncommitted changes included) and
   return only the findings list (skip this step if the skill is not available). Never
   pass `--fix`: the implementer fixes code, test first. Route each finding:
   - a bug inside the behavior of an existing criterion -> implementer, with the finding and the
     `sdd context <id> <Tn> --plan` bundle of the task whose files it touches; it adds a
     failing unit test first;
   - a defect in a frozen acceptance test, or a fix that needs behavior
     (validation, a new error path) that no criterion describes -> step 9;
   - not worth fixing -> tell the user in one line, then go on.
   After any fix, go back to 8.1. Max 2 review rounds: after that, list the remaining
   findings to the user and let them decide.
4. Then `sdd set-status <id> verified`, `sdd checkpoint <id> --phase sync -m "chore(<id>): verified"`,
   then `sdd sync <id> --dry-run`, then
   `sdd sync <id>`. Sync first merges `origin/<base>` into the branch when the base moved (a
   dry run only warns), so its checks see the living spec as it is now; if that merge
   conflicts, resolve it in the worktree, checkpoint, and sync again. It then writes the new
   concepts and merges each CapabilityDelta unit by
   unit into the specs/ OKF bundle (status `stable`, regenerated indexes, `log.md`), accepts
   the ADRs (status `stable`) and archives the change. If sync refuses with a `specs bundle:`
   error, run the `bundle` tool on `specs` (with `fix: true` for what it marks fixable) and
   commit that first; old REQ/INV concepts must be rewritten by hand. If sync reports
   CONFLICT, another change modified the same criterion, section or invariant first: resume
   spec-author to rebase that unit (`delta-stub` again), back to Gate 1 for it only.
5. `sdd finish <id>`: marks the phase done, commits the synced specs/ADRs/archive, merges
   `origin/<base>` again if it moved since the sync, pushes and marks the PR ready for review
   (merging stays with the user). If that merge conflicts, another change edited the same
   unit after this sync: tell the user which files, then follow "Conflict after sync" in the
   plugin's how-to/resolve-sync-conflict (keep the base's text, re-apply this change's unit
   from its archived delta, show that unit at Gate 1, commit, `finish` again). Report to the user in
   3 lines: what changed, criterion and invariant ids, anything deferred, plus the PR link.

## 9. Reopen (failure path)
A wrong or untestable criterion or invariant goes back to the spec, never into the code or the tests.
`sdd set-status <id> draft`, `sdd checkpoint <id> --phase spec -m "chore(<id>): reopen spec"`,
resume spec-author with the BLOCKED report, then Gate 1 for
the affected units only, then re-plan the affected tasks, re-run their test tasks
(then `sdd freeze <id>` again), then implementation. A Baseline test rewritten after code has changed is
refused by `freeze`: you then run `sdd freeze <id> --after-code` yourself (the verifier's
run on the base commit is then its only proof).
A `size: fix` change adds at most new criteria: when it needs more (a changed criterion,
a section, an invariant, an ADR), re-triage it as a full change. Set `size: change` in intent.md,
`sdd set-status <id> draft`, `sdd checkpoint <id> --phase spec -m "chore(<id>): re-triage as change"`,
start spec-author with the finding, then step 3.

## Status
The plugin shows the active change, its status and task progress above the prompt, and
`/sdd` opens a pane with every open change, its tasks, the last check and running
workflow agents; `/sdd phase` opens a pane with the workflow phase the change is in.
You do not need to recap progress to the user; point them to it.

## Token rules
- Agents get `sdd context` bundles, not whole files and not your conversation.
- Resume an agent (SendMessage) for follow-ups instead of spawning a new one.
- Never paste file contents into your replies to the user; give paths and IDs.
