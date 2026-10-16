---
name: change
description: Lead workflow for any request to change the codebase - triage, spec delta and ADRs, user gate, plan, test-first implementation, verification, spec sync. Use for every feature, behavior change, or bug fix request, and when the user types /sdd:change.
argument-hint: <what you want changed> | resume <change-id>
---

# Lead: spec-driven change workflow

You are the lead. You route, gate and close out. You do not write specs, plans, tests or
production code yourself in this workflow (the direct-execution path in step 1 excepted).
Keep your own context thin: pass agents IDs and file paths, read tool output, not whole files.

`sdd <args>` = the `mcp__sdd__sdd` tool with `args` as a list (`sdd check c1` is
`{"args": ["check", "c1"]}`). The guard blocks running the script through Bash.
First use in a repo: `sdd init` (creates the folders and `.claude/sdd.json`; ask the user
to set `acceptance_cmd` and `unit_cmd` there).

The workflow agents are plugin agents: `sdd:spec-author`, `sdd:planner`,
`sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`. Built-ins reused: `Explore`,
`general-purpose`. Below they are named without the `sdd:` prefix.
Request: $ARGUMENTS
If it starts with `resume`, see "Resume" below.

## Branch, worktree, PR, checkpoints
Every full change and fix lives on its own branch `sdd/<id>` in its own worktree, with a
draft PR. `sdd start` creates all three; `state.json` stores `phase`, branch, base and PR
number. Direct-path work has no change id and none of this.
- **Checkpoint**: each time an agent (or you) finishes an artifact, run
  `sdd checkpoint <id> [--phase <next>] -m "<conventional message>"`. It stores the phase,
  commits everything and pushes. Phase ids: `spec gate1 plan gate2 acceptance implement
  verify sync done`. Pass `--phase` when the step you just finished moves the change to
  the next phase; omit it for further commits within a phase.
- Never `git commit` or `git push` yourself for a change (merging isolated implementer
  branches is the one exception); never write `state.json`.

## Resume
`resume <id>` continues a change from this or another machine:
1. `sdd resume <id>` (add `--pr <n>` if you only have the PR number). It fetches the PR
   branch, creates or reuses the worktree, fast-forwards it, and prints the stored phase
   and the step to continue at.
2. `EnterWorktree` with `path` = the printed worktree. From here every `sdd` call acts on it.
3. `sdd status <id>`, then continue at the step the phase names (spec -> 2, gate1 -> 3,
   plan -> 4, gate2 -> 5, acceptance -> 6, implement -> 7, verify -> 8, sync -> 8.4,
   done -> nothing left; a fix starts at plan, its test is written alongside). A stored phase can lag a step that was done but not
   checkpointed: trust the files (`sdd check`, task ticks) over the phase when they disagree.
   Resume a partly written spec or plan with the same agent type and the files as context.

## 1. Triage (you, no agent unless context is missing)
If you need codebase facts to decide, delegate to `Explore` (quick or medium) with one
precise question. Do not read the repo yourself.

Apply this rule, in order, and state the result in one line:
- Changes observable behavior or a public contract (API, CLI, schema, event, UI flow)
  -> **full change** (spec delta).
- Makes a decision with lasting consequences (technology, data model, boundary,
  security posture) -> **full change** with ADR, even if behavior is unchanged.
- Code diverges from an existing REQ (bug) -> **fix**: no spec delta, but a failing
  acceptance test first. `sdd start <id> --title ... --pr-title "fix: ..."`, enter the worktree, `sdd checkpoint <id> --phase plan -m "chore(<id>): fix"`, set `size: fix` in intent.md, write one test task
  referencing the existing REQ, then go to step 4 (it runs step 6 alongside).
- Anything else (refactor, rename, dependency bump, docs, config) -> **direct**: delegate
  to `general-purpose` (or do it yourself if trivial), run the unit tests, done.

## 2. Capture intent and spec delta
1. Pick a kebab-case id. `sdd start <id> --title "<title>" --pr-title "<feat|fix>: <title>"`
   (conventional type from triage). Then `EnterWorktree` with `path` = the worktree it
   prints. Do this before any agent writes an artifact. If it prints `PR missing`, create a
   draft PR for the branch (GitHub tools) and run `sdd set-pr <id> <number>`.
2. Delegate to `spec-author` with: change id, the user's request verbatim, and the
   Explore findings (summarized, with file paths). It writes intent.md, the delta and any
   proposed ADRs, then runs `sdd check <id>`. Then
   `sdd checkpoint <id> --phase gate1 -m "docs(<id>): spec delta"`.
3. If it returns open questions, ask the user (AskUserQuestion, max 4) and resume the
   same spec-author with the answers (SendMessage), do not start a new one.

## 3. Gate 1 - user review (deep)
Show the user, compactly: the intent's Why/Outcome/Non-goals, each REQ id + title +
scenario names, each ADR title + decision paragraph. Give file paths for the full text.
Ask: approve / change something / stop.
- Change -> resume spec-author with the feedback, then Gate 1 again.
- Approve -> `sdd set-status <id> approved`, then
  `sdd checkpoint <id> --phase plan -m "chore(<id>): approve spec"`. After a "change" round,
  checkpoint without `--phase`.

## 4. Plan and tasks
Delegate to `planner` with the change id. It writes plan.md and tasks.md.
For a `size: fix`, the contract is the existing code, so the test does not wait for the
plan: in the same message, also delegate T1 to `acceptance-tester` (step 6). Tell the
planner to leave T1's line as is and make its impl tasks `blocked-by: T1`.
When the planner returns: `sdd checkpoint <id> --phase gate2 -m "docs(<id>): plan and tasks"`
(a fix also waits for T1, then `--phase gate2` once both are in).

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
For each `(test)` task (parallel if several): delegate to `acceptance-tester` with
the `sdd context <id> <Tn>` output pasted in the prompt. It writes the tests, confirms they
fail for the right reason, ticks its task and runs `sdd freeze <id>`. After each one:
`sdd checkpoint <id> -m "test(<id>): <Tn> acceptance tests"`; after the last add
`--phase implement`.
If it reports that a scenario is untestable or ambiguous -> step 9 (reopen).

## 7. Implementation (inner TDD)
For each `(impl)` task whose blocked-by tasks are done, delegate to `implementer` with
the `sdd context <id> <Tn> --plan` output pasted in the prompt.
Parallelism: run impl tasks concurrently only when their `files:` sets are disjoint;
pass `isolation: "worktree"` on each Agent call when you do, and merge the branches
yourself into `sdd/<id>` after each returns (they never touch the same files by
construction), then checkpoint.
If an implementer returns `BLOCKED: REQ-... <reason>` -> step 9. Never relax a test.
After each implementer returns (and its branch is merged, if isolated):
`sdd checkpoint <id> -m "feat(<id>): <Tn> <task title>"`; after the last impl task add
`--phase verify`.

## 8. Verify and close out
1. Delegate to `verifier` with the change id. It runs the frozen-test check, the
   acceptance and unit suites, `sdd check <id> --tests`, and reviews the diff.
2. On FAIL: route each finding (implementer for code, step 9 for spec problems);
   checkpoint after each fix.
3. On PASS, review before syncing: the verifier checks conformance to the spec, not bugs
   outside its scenarios. Delegate to `general-purpose`: run the built-in `code-review`
   skill on the change's diff against the base branch (uncommitted changes included) and
   return only the findings list (skip this step if the skill is not available). Never
   pass `--fix`: the implementer fixes code, test first. Route each finding:
   - a bug inside the behavior of an existing REQ -> implementer, with the finding and the
     `sdd context <id> <Tn> --plan` bundle of the task whose files it touches; it adds a
     failing unit test first;
   - a defect in a frozen acceptance test, or a fix that needs behavior no REQ describes
     (validation, a new error path) -> step 9;
   - not worth fixing -> tell the user in one line, then go on.
   After any fix, go back to 8.1. Max 2 review rounds: after that, list the remaining
   findings to the user and let them decide.
4. Then `sdd set-status <id> verified`, `sdd checkpoint <id> --phase sync -m "chore(<id>): verified"`,
   then `sdd sync <id> --dry-run`, then
   `sdd sync <id>`. Sync merges the delta into specs/, accepts the ADRs and archives the
   change. If sync reports CONFLICT, another change modified the same REQ first: resume
   spec-author to rebase the delta (`delta-stub` again), back to Gate 1 for that REQ only.
5. `sdd finish <id>`: marks the phase done, commits the synced specs/ADRs/archive, pushes
   and marks the PR ready for review (merging stays with the user). Report to the user in
   3 lines: what changed, REQ ids, anything deferred, plus the PR link.

## 9. Reopen (failure path)
A wrong or untestable REQ goes back to the spec, never into the code or the tests.
`sdd set-status <id> draft`, `sdd checkpoint <id> --phase spec -m "chore(<id>): reopen spec"`,
resume spec-author with the BLOCKED report, then Gate 1 for
the affected REQs only, then re-plan the affected tasks, re-run their test tasks
(re-freeze), then implementation.
A `size: fix` change has no spec-author to resume: when it needs behavior no REQ
describes, re-triage it as a full change. Set `size: change` in intent.md,
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
