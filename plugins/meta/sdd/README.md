# sdd: spec-driven multi-agent workflow for Claude Code

One plugin: a lead workflow, five workflow agents, a deterministic spec tool, and a mod
that makes the main conversation the lead, guards writes per agent and shows the
workflow's state live.

```
request ─► lead (/sdd:change) ─► triage ──direct──► general-purpose / lead
                                  │ fix ──► failing test on the existing REQ ─► implement ─► verify
                                  ▼ change
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
```

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
creates `specs/ adr/ changes/ tests/acceptance/` and `.claude/sdd.json`: set
`acceptance_cmd` and `unit_cmd` there.

## What is in it
| Part | Where | What it does |
|---|---|---|
| Lead workflow | `skills/change` (`/sdd:change`) | triage, gates, routing, close-out, reopen path |
| Format rules | `skills/formats` (`sdd:formats`) | REQ/scenario/delta/ADR/task formats, preloaded into the authoring agents |
| Agents | `agents/` (`sdd:spec-author`, `sdd:planner`, `sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`) | one job each, minimal tools |
| Spec tool | `tools/sdd.py`, exposed as the `mcp__sdd__sdd` tool | check, context bundles, delta-new from the delta template, delta-stub with base hashes, freeze/verify-frozen, deterministic sync, ADR accept/supersede |
| Mod | `hooks/register.tsx`, `hooks/guard.ts`, `hooks/phase.ts` | lead role for the main conversation, write guard per agent, the `sdd` tool, status band, `/sdd` and `/sdd phase` panes |

## The mod
- **Lead role.** A `prompt.compose` hook appends an `sdd:lead` section to the main
  conversation's system prompt: change requests go through `sdd:change`, questions are
  answered directly. Claude Code's default system prompt stays as it is.
- **Guard, in-process.** Every Edit/Write/MultiEdit/NotebookEdit/Bash call is checked
  against the calling agent, identified by the call's `agentId`:
  - Nobody edits `specs/` by hand: it changes only through `sdd sync`.
  - Nobody edits accepted ADRs, `frozen.json` or archived changes.
  - `spec-author` writes only the intent, the delta and proposed ADRs, and only while
    the change is `draft`.
  - `planner` writes only `plan.md` and `tasks.md`, while the change is `draft` or
    `approved`.
  - `acceptance-tester` writes only the acceptance tests and `tasks.md`.
  - `implementer` can never touch the acceptance tests, the spec or the ADRs.
  - `verifier` writes nothing.
  - No subagent edits `.claude/`, or changes a `status:` line in `intent.md` or an ADR
    (that is `sdd set-status` / `sdd adr-accept`, lead only).

  If the guard itself fails, it refuses subagents' calls and lets the lead's through.
- **`sdd` tool.** Agents call `mcp__sdd__sdd` with `args` instead of a script path, and
  the tool applies role rules per subcommand:
  - lead only: `sync`, `set-status`, `new`, `init`, `adr-accept`
  - lead and acceptance-tester: `freeze`
  - lead and spec-author: `delta-new`, `delta-stub`, `adr-new`
- **Band above the prompt.** Shows the most active open change, its phase, its status, task
  progress, the last check result, which workflow agents are running, and how many other
  changes are open. It hides itself when nothing is open.
- **`/sdd` pane.** Lists every open change with its next step and tasks, the last check
  with its ERROR lines, Check and Check + tests buttons, running agents, and the last
  guard refusal. `/sdd refresh` re-reads the state.
- **`/sdd phase` pane.** The workflow's phases for the most active change (Spec, Gate 1,
  Plan, Gate 2, Acceptance tests, Implement, Verify, Sync; a `size: fix` change skips
  Spec and Gate 1): done ones ticked, the current one marked with what happens in it,
  plus the phase of every other open change. The phase is derived from the change's
  status, its open test/impl tasks and which workflow agent is running.

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
- The Bash check is heuristic. `verify-frozen`, run by the verifier and ideally in CI,
  is the real enforcement for tests.
- Parallel implementers in worktrees still need the lead to merge their branches.
- The band and pane refresh on workflow events and every 30 s; edits made outside
  Claude Code show on the next refresh or with `/sdd refresh`.
