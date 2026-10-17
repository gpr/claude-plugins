# sdd: spec-driven multi-agent workflow for Claude Code

One plugin: a lead workflow, five workflow agents, a deterministic spec tool, and a mod
that makes the main conversation the lead, guards writes per agent and shows the
workflow's state live.

```
request ─► lead (/sdd:change) ─► triage ──direct──► general-purpose / lead
                                  │ fix ──► failing test on the existing REQ ║ plan ─► implement ─► verify
                                  ▼ change: sdd start (branch sdd/<id>, worktree, draft PR)
                          sdd:spec-author ─► GATE 1 (you: intent, REQs, ADRs)
                                  ▼
                            sdd:planner ─► GATE 2 (sdd check, automatic)
                                  ▼
                      sdd:acceptance-tester ─► sdd freeze
                                  ▼
                        sdd:implementer(s)  (inner TDD; BLOCKED ─► reopen spec ─► GATE 1)
                                  ▼
                           sdd:verifier ─► PASS ─► code-review (findings ─► implementer / reopen)
                                  ▼
                              sdd sync (delta → specs/, ADRs accepted, archive)
                                  ▼
                              sdd finish (commit, push, PR ready)
```
Each artifact is committed and pushed with `sdd checkpoint`, which also stores the phase.

Full documentation (tutorials, how-to guides, reference, explanation): [docs/index.md](docs/index.md).

## Install

```
/plugin marketplace add gpr/claude-plugins
/plugin install sdd@gpr-plugins
```

Install it at **project** scope in the repos that use the workflow: the guard applies
wherever the plugin is enabled, and at user scope it would block hand edits to `specs/`
and `adr/` in every repo, and make every session's main conversation the lead.

Requires Python 3.9+ on PATH (for `tools/sdd.py`, no dependencies).

Local test: `claude --plugin-dir ./plugins/meta/sdd`

In a repo, just describe the change: the main conversation is the lead and runs the
workflow (`/sdd:change <what you want>` does the same explicitly). The first run calls `sdd init`, which
creates `specs/ adr/ changes/ tests/acceptance/` (`specs/` as an OKF bundle with `index.md`
and `log.md`) and `.claude/sdd.json`: set `acceptance_cmd` and `unit_cmd` there.

## Specs, invariants and OKF bundles
`specs/` and every `changes/<id>/` are [OKF](https://github.com/gpr/claude-plugins/tree/main/plugins/meta/documentalist-agent)
bundles (`okf_version: "0.2"` in the root `index.md`, `type`/`sources` front matter on
every concept). Concept files are short (at most `concept_max_blocks`, default 5, REQ/INV
blocks) and grouped:
```
specs/index.md  specs/log.md
specs/<capability>/{index.md,<concept>.md}                living requirements (REQ-<CAP>-NNN)
specs/invariants/<category>/{index.md,<concept>.md}       living invariants (INV-<CAT>-NNN)
changes/<id>/{index.md,intent.md,plan.md,tasks.md}
changes/<id>/specs/<capability>/<concept>.md              spec delta, mirrors the living path
changes/<id>/specs/invariants/<category>/<concept>.md     invariant delta
```
An invariant is a system-wide rule with a `#### Check:` instead of a scenario; it needs a
test task but no impl task. `sdd sync` applies both deltas (ADDED, MODIFIED, REMOVED, and
MOVED when a MODIFIED block sits in another concept of the same capability), merges the
delta `sources`, regenerates the indexes and appends to `specs/log.md`.

The `bundle` tool (`mcp__sdd__bundle`, or `sdd bundle <specs|change> [--fix]`) checks both
kinds of bundle and repairs what it marks `[fixable]` (indexes, front matter, block order,
missing sources, empty concepts). `--fix` also migrates the old layout: `specs/<cap>/spec.md`
becomes `specs/<cap>/<cap>.md` and flat `changes/<id>/specs/<cap>.md` deltas move below
`specs/<cap>/`. It is idempotent. Splitting an over-long concept stays a warning: a
spec-author decides the topics. After upgrading, run `bundle specs --fix` once (sync refuses
a specs bundle with errors), then `bundle <id> --fix` for each open change.

## What is in it
| Part | Where | What it does |
|---|---|---|
| Lead workflow | `skills/change` (`/sdd:change`) | triage, gates, routing, close-out, reopen path |
| Format rules | `skills/formats` (`sdd:formats`) | REQ/scenario/delta/ADR/task formats, preloaded into the authoring agents |
| Agents | `agents/` (`sdd:spec-author`, `sdd:planner`, `sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`) | one job each, minimal tools, project memory in `.claude/agent-memory/sdd-<agent>/` |
| Spec tool | `tools/sdd.py`, exposed as the `mcp__sdd__sdd` and `mcp__sdd__bundle` tools | check, context bundles, delta-new from the delta templates, delta-stub with base hashes, freeze/verify-frozen, deterministic sync into the specs bundle, ADR accept/supersede, bundle check/fix |
| Mod | `hooks/register.tsx`, `hooks/guard.ts`, `hooks/phase.ts` | lead role for the main conversation, write guard per agent, the `sdd` tool, status band, `/sdd` and `/sdd phase` panes |

## Branches, PRs and resume
For a full change or a fix the lead runs `sdd start <id>` before any artifact exists:
- branch `sdd/<id>` from `origin/<base>`, a worktree in `.claude/worktrees/sdd-<id>` (the
  lead moves into it with `EnterWorktree`), the scaffolded change pushed, and a **draft PR**
  opened with `gh`. If `gh` is missing or fails, the lead opens the PR and records it with
  `sdd set-pr <id> <number>`.
- `changes/<id>/state.json` stores `phase`, `branch`, `base`, `pr`, `pr_url`, `requires`. Only `sdd.py`
  writes it; the guard refuses every other write. Phases: `spec gate1 plan gate2 acceptance
  implement verify sync done`. The band and `/sdd phase` show the stored phase (older
  changes without it keep the derived one) and `sdd check` warns when phase and status
  disagree.
- After every artifact outcome (spec, plan, each test task, each impl task, each fix) the
  lead runs `sdd checkpoint <id> [--phase P] -m "<message>"`: store the phase, commit all,
  push. It refuses to run off the change's branch.
- **Dependencies**: `sdd start <id> --requires a,b` (or `sdd requires <id> a b`, `--clear`)
  stores the changes this one needs in `state.json`. A required change is done when its
  archive is on `origin/<base>`, i.e. its PR is **merged**. `sdd deps <id>` lists each one
  (`ok`, `missing` = merged but not in this branch yet, `ready` = finished, PR unmerged,
  `open`, `unknown`), transitively; cycles are refused. Spec work can start anyway, but
  `checkpoint --phase plan` (or later) and `resume` refuse until all are merged. Once they
  are, `resume` / `checkpoint` merge `origin/<base>` into the branch, so the dependency's
  specs and code are there. The lead handles a blocked resume by resuming the unfinished
  required change first (depth-first) and finishing it, then asking you to merge its PR.
- **Continue a change**: `/sdd:change resume <id>` runs `sdd resume <id>` (or `--pr <n>`):
  `git fetch` the PR branch, create or reuse the worktree, fast-forward it, print the stored
  phase and the step to continue at. The lead enters the worktree and carries on.
- `sdd finish <id>` after `sync`: phase `done`, commit, push, `gh pr ready`. Merging stays
  with you. The worktree is kept.

Needs a git remote named `origin` with `.claude/sdd.json` committed on the base branch;
`gh` (authenticated) only for the PR steps. Config keys: `base_branch` (default: the
remote's default branch), `branch_prefix` (`sdd/`), `worktree_dir` (`.claude/worktrees`).

## The mod
- **Lead role.** A `prompt.compose` hook appends an `sdd:lead` section to the main
  conversation's system prompt: change requests go through `sdd:change`, questions are
  answered directly. Claude Code's default system prompt stays as it is.
- **Guard, in-process.** Every Edit/Write/MultiEdit/NotebookEdit/Bash call is checked
  against the calling agent, identified by the call's `agentId`:
  - Nobody edits `specs/` by hand: it changes only through `sdd sync`.
  - Nobody edits accepted ADRs, `frozen.json`, `state.json` or archived changes.
  - `spec-author` writes only the intent, the delta and proposed ADRs, and only while
    the change is `draft`.
  - `planner` writes only `plan.md` and `tasks.md`, while the change is `draft` or
    `approved`.
  - `acceptance-tester` writes only the acceptance tests and `tasks.md`.
  - `implementer` can never touch the acceptance tests, the spec or the ADRs.
  - `verifier` writes nothing but its memory.
  - No subagent edits `.claude/` outside its own memory directory, or changes a `status:` line in `intent.md` or an ADR
    (that is `sdd set-status` / `sdd adr-accept`, lead only).

  If the guard itself fails, it refuses subagents' calls and lets the lead's through.
- **`sdd` tool.** Agents call `mcp__sdd__sdd` with `args` instead of a script path, and
  the tool applies role rules per subcommand:
  - lead only: `sync`, `set-status`, `new`, `init`, `adr-accept`, `start`, `checkpoint`, `set-pr`, `requires`, `resume`, `finish`
  - read-only, any role: `deps`
  - lead and acceptance-tester: `freeze`
  - lead and spec-author: `delta-new`, `delta-stub`, `adr-new`
- **`bundle` tool.** `mcp__sdd__bundle` takes `target` (`specs` or a change id) and `fix`.
  Checking is open to every role; `fix` on `specs` is lead-only, `fix` on a change is
  lead or spec-author.
- **Band above the prompt.** Shows the most active open change, its phase, its status, task
  progress, the last check result, which workflow agents are running, and how many other
  changes are open. It hides itself when nothing is open.
- **`/sdd` pane.** The most active change in full (phase and hint, progress bar, its next
  five open tasks, ADRs, requires, the last check with its ERROR lines), then the other open
  changes one line each, grouped by phase, most advanced first (requires, check result and a
  failed check's ERROR lines), then running agents and the last guard refusal.
  `/sdd check <change> [--tests]` runs a check without the model; `/sdd refresh` re-reads the state.
- **`/sdd phase` pane.** The workflow's phases for the most active change (Spec, Gate 1,
  Plan, Gate 2, Acceptance tests, Implement, Verify, Sync; a `size: fix` change skips
  Spec and Gate 1 and writes its tests alongside the plan, before Gate 2): done ones
  ticked, the current one marked with what happens in it, plus the phase of every other
  open change. The phase is derived from the change's
  status, its open test/impl tasks and which workflow agent is running.

## Agent memory
Each workflow agent has `memory: project`: Claude Code loads
`.claude/agent-memory/sdd-<agent>/MEMORY.md` into its prompt and lets it keep notes there
across changes (repo layout, test setup, recurring findings). Commit the directory to share
it with the team, or ignore it in git to keep it per clone. The guard lets each agent write
only its own directory (and the `agent-memory-local` one). Memory never overrides the spec,
the ADRs or the frozen tests. With auto memory turned off (`autoMemoryEnabled: false`)
the agents run without it.

## Determinism (why sdd.py exists)
- **Sync** merges by REQ id; MODIFIED replaces the whole block, nothing is paraphrased.
- **Conflicts.** Each MODIFIED or REMOVED entry carries the hash of the REQ it was based
  on, so if another change edited that REQ first you get a CONFLICT, not a silent
  overwrite.
- **Traceability.** `check` fails when a REQ has no scenario, no test task or no impl
  task, or when anything references a REQ, ADR or task that doesn't exist.
  `check --tests` also fails when a REQ has no acceptance test or a task is still open.
- **Freeze.** Records hashes of the acceptance tests; `verify-frozen` catches any edit
  that slipped past the guard.
- **Context bundles.** `context <change> <task>` gives each agent only its own slice:
  - every task: the REQ blocks it cites and the ADR Decision paragraphs
  - test tasks: the plan's Contracts section, nothing else from the plan
  - impl tasks: the frozen test paths, plus the full plan with `--plan`

## Development
```
claude plugin validate plugins/meta/sdd
claude plugin test plugins/meta/sdd   # guard rules + band/pane rendering on terminal and desktop
python3 -m unittest discover -s plugins/meta/sdd/tests -p 'test_*.py'   # sdd.py, black-box in a temp repo
```

## Known limits
- `resume` fast-forwards only: a diverged local branch needs a manual fix.
- Bringing the base into a change's branch can conflict; sdd aborts the merge and names
  the files, you resolve it by hand and checkpoint.
- "Merged" means the dependency's archive directory is on `origin/<base>`: squash merges
  are fine, a dependency that is closed without merging stays blocked until `requires --clear`.
- Parallel implementer worktrees (`isolation: "worktree"`) started from inside the change's
  worktree are untested with nested worktrees; run implementers sequentially if it fails.
- The Bash check is heuristic. `verify-frozen`, run by the verifier and ideally in CI,
  is the real enforcement for tests.
- Parallel implementers in worktrees still need the lead to merge their branches.
- The band and pane refresh on workflow events and every 30 s; edits made outside
  Claude Code show on the next refresh or with `/sdd refresh`.
