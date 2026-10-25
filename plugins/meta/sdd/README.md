# sdd: spec-driven multi-agent workflow for Claude Code

One plugin: a lead workflow, six workflow agents, a deterministic spec tool, and a mod
that makes the main conversation the lead, guards writes per agent and shows the
workflow's state live.

```
request ─► lead (/sdd:change) ─► triage ──direct──► general-purpose / lead
                                  │ fix ──► failing test on the existing AC  ║ plan ─► implement ─► verify
                                  ▼ change: sdd start (branch sdd/<id>, worktree, draft PR)
                          sdd:spec-author (intent, criteria, invariants, ADRs, surface)
                                  ▼ surface api/cli/ui (none: skipped)
                     sdd:contract-designer (TypeSpec, CLI synopsis, UI mockup)
                                  ▼
                          GATE 1 (you: intent, criteria, invariants, contract, ADRs)
                                  ▼
                            sdd:planner ─► GATE 2 (sdd check, automatic)
                                  ▼
                      sdd:acceptance-tester(s) ─► sdd freeze (lead, once)
                                  ▼
                        sdd:implementer, one task at a time  (inner TDD; BLOCKED ─► reopen spec ─► GATE 1)
                                  ▼
                           sdd:verifier ─► PASS ─► code-review (findings ─► implementer / reopen)
                                  ▼
                              sdd sync (merge origin/<base>, concepts → specs/, contracts → contracts/, ADRs accepted, archive)
                                  ▼
                              sdd finish (commit, merge a moved base, push, PR ready)
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
and `adrs/` in every repo, and make every session's main conversation the lead.

Requires Python 3.9+ on PATH (for `tools/sdd.py`, no dependencies).

Local test: `claude --plugin-dir ./plugins/meta/sdd`

In a repo, just describe the change: the main conversation is the lead and runs the
workflow (`/sdd:change <what you want>` does the same explicitly). The first run calls `sdd init`, which
creates `specs/ adrs/ changes/ tests/acceptance/` (`specs/` and `adrs/` as OKF bundles with
`index.md`, `log.md` and their concept templates in `.templates/`), `.claude/sdd.json`
(set `acceptance_cmd` and `unit_cmd` there) and `.gitattributes` lines that merge the two
`log.md` files by union, so concurrent changes don't conflict on them. In a repo initialised
by an older sdd, run `sdd init` again and commit `.gitattributes`.

## Existing repositories
sdd imports nothing. It writes current behavior down as it goes:
- First run: `sdd init --survey` lists the ADR dirs and test dirs the repo already has (found
  by content: numbered or Status/Decision markdown, `test_*.py`, `*.test.ts`, `*_test.go`, ...)
  and its manifests, and writes nothing. The lead asks where things go, then runs
  `sdd init adr_dir=... acceptance_cmd=... unit_cmd=...`. An existing `adrs/` or `specs/` that sdd did not
  create stops init (WARN, nothing written, exit 1); old ADRs stay where they are, as plain references.
- **Baseline criteria.** A change that touches code no capability covers writes the behavior it
  keeps as criteria ending in `- **Baseline**: <path>`: a `(test)` task, no `(impl)` task, and
  the test must pass on the current code (else `MISMATCH`, and you decide whether the code or
  the criterion is wrong). Sync drops the line. `freeze` records the base commit and refuses
  a new Baseline test once production code changed; the verifier re-runs them on that commit
  (`sdd baseline-tree`).
- **A bug no criterion covers** is a `size: fix` that first adds the correct behavior as a
  criterion (ADDED only), reviewed in a short Gate 1, then the usual fix path.
- **`/sdd:change adopt <area>`** writes an area down up front: a `size: baseline` change with
  only Baseline criteria and test tasks, no Implement step, no code change.

See `docs/how-to/adopt-an-existing-repo.md`.

## Capabilities, invariants and OKF bundles
`specs/`, `adrs/` and every `changes/<id>/` are [OKF](https://docs.rs/okf) v0.2 bundles
(`okf_version: "0.2"` in the root `index.md`, a dated `log.md`, `type` front matter on every
concept; synced bundles pass `okf validate`). The concepts follow the lintel templates,
shipped in `skills/change/templates/` and copied into `specs/.templates/` and
`adrs/.templates/` by `sdd init`, where a repo may adapt them:
```
specs/capabilities/<id>.md     type: Capability: Intent, Scope, acceptance criteria AC-NN
                               (Given/When/Then), Invariants, Decisions, Verification
specs/invariants/<id>.md       type: Invariant: Statement, Enforcement (Check), Holds and
                               Violation examples, one rule per file
adrs/NNNN_<slug>.md            type: ADR, status draft -> stable -> deprecated
changes/<id>/{index.md,intent.md,plan.md,tasks.md}
changes/<id>/specs/capabilities/<id>.md   a new Capability, or a CapabilityDelta of a living one
changes/<id>/specs/invariants/<id>.md     a new Invariant, or the full replacement of one
```
Tasks and acceptance tests cite `capabilities/<id>#AC-NN` and `invariants/<id>`. A criterion
needs a test task and an impl task (a Baseline criterion a test task only); an invariant a test task only. A CapabilityDelta is
merged one unit at a time: ADDED, MODIFIED and RETIRED criteria (ids are never reused: a
retired one keeps its heading and reason), and SECTIONS that replace Title, Description,
Intent, Scope, Invariants, Decisions or Verification. `sdd sync` sets the concepts `stable`,
merges `sources`, regenerates the indexes the way `okf index` does and adds to `specs/log.md`.

The `bundle` tool (`mcp__sdd__bundle`, or `sdd bundle <specs|adrs|change> [--fix]`) checks
the bundles and repairs what it marks `[fixable]` (indexes, logs, titles, `sources` entries,
criterion order). It is idempotent. The older REQ/INV block format is reported as an error
and not migrated: see `docs/how-to/migrate-to-okf-layout.md`.

## What is in it
| Part | Where | What it does |
|---|---|---|
| Lead workflow | `skills/change` (`/sdd:change`) | triage, gates, routing, close-out, reopen path |
| Discover | `skills/discover` (`/sdd:discover`) | maps an existing repo into areas and decisions, then runs one `adopt` change per area: tested Baseline criteria and draft ADRs |
| Document to changes | `skills/from-doc` (`/sdd:from-doc <file>`) | splits a spec or PRD into changes with triage and `requires`, starts them after approval, runs the first |
| Format rules | `skills/formats` (`sdd:formats`) | Capability/Invariant/CapabilityDelta/ADR/task formats, preloaded into the authoring agents |
| Agents | `agents/` (`sdd:spec-author`, `sdd:contract-designer`, `sdd:planner`, `sdd:acceptance-tester`, `sdd:implementer`, `sdd:verifier`) | one job each, minimal tools, project memory in `.claude/agent-memory/sdd-<agent>/` |
| Spec tool | `tools/sdd.py`, exposed as the `mcp__sdd__sdd` and `mcp__sdd__bundle` tools | check, context bundles, delta-new from the concept templates, delta-stub and contract-stub with base hashes, freeze/verify-frozen, deterministic per-unit sync into the specs bundle, ADR accept/supersede, bundle check/fix |
| Mod | `hooks/register.tsx`, `hooks/guard.ts`, `hooks/phase.ts` | lead role for the main conversation, write guard per agent, the `sdd` tool, status band, `/sdd` and `/sdd phase` panes |

## Branches, PRs and resume
For a full change or a fix the lead runs `sdd start <slug>` before any artifact exists:
- the change id `<NNNN>-<YYMMDD>-<slug>` (e.g. `0007-261025-add-login`): the next number not
  used by a change, an archive or an `sdd/` branch (local, on `origin/<base>` or pushed from
  another machine), today's date and the slug. Every later command takes this id.
- branch `sdd/<id>` from `origin/<base>`, a worktree in `.claude/worktrees/sdd-<id>` (the
  lead moves into it with `EnterWorktree`), the scaffolded change pushed, and a **draft PR**
  opened with `gh`. If `gh` is missing or fails, the lead opens the PR and records it with
  `sdd set-pr <id> <number>`.
- `changes/<id>/state.json` stores `phase`, `branch`, `base`, `pr`, `pr_url`, `requires`. Only `sdd.py`
  writes it; the guard refuses every other write. Phases: `spec contract gate1 plan gate2 acceptance
  implement verify sync done`. The band and `/sdd phase` show the stored phase (older
  changes without it keep the derived one) and `sdd check` warns when phase and status
  disagree.
- After every artifact outcome (spec, plan, each test task, each impl task, each fix) the
  lead runs `sdd checkpoint <id> [--phase P] -m "<message>"`: store the phase, commit all,
  push. It refuses to run off the change's branch.
- **Dependencies**: `sdd start <slug> --requires a,b` (or `sdd requires <id> a b`, `--clear`)
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
- `sdd sync <id>` first merges `origin/<base>` into the branch when the base moved, so the
  delta's base hashes are checked against the living spec as it is now.
- `sdd finish <id>` after `sync`: phase `done`, commit, merge `origin/<base>` again if it
  moved since the sync, push, `gh pr ready`. Merging stays with you. The worktree is kept.
- Every commit sdd makes lists the new files; one that looks like a secret (`.env`, `*.pem`,
  `*.key`, `id_rsa`, `credentials.json`, ...) is unstaged and the commit refused.

Needs a git remote named `origin` with `.claude/sdd.json` committed on the base branch;
`gh` (authenticated) only for the PR steps. Config keys: `base_branch` (default: the
remote's default branch), `branch_prefix` (`sdd/`), `worktree_dir` (`.claude/worktrees`).

## The mod
- **Lead role.** A `prompt.compose` hook appends an `sdd:lead` section to the main
  conversation's system prompt: change requests go through `sdd:change`, questions are
  answered directly. Claude Code's default system prompt stays as it is.
- **Guard, in-process.** Every Edit/Write/MultiEdit/NotebookEdit/Bash call is checked
  against the calling agent, identified by the call's `agentId`:
  - Nobody edits `specs/` or the living contract files (`contracts/api|cli|ui/`) by hand:
    they change only through `sdd sync`.
  - Nobody edits accepted (stable) or deprecated ADRs, `frozen.json`, `state.json` or archived changes.
  - Only the lead edits the concept templates (`specs/.templates/`, `adrs/.templates/`) and
    the ADR bundle's `index.md` and `log.md`.
  - `spec-author` writes only the intent, the delta and draft ADRs, and only while
    the change is `draft`.
  - `contract-designer` writes only the change's `contracts/`, while the change is `draft`.
  - `planner` writes only `plan.md` and `tasks.md`, while the change is `draft` or
    `approved`.
  - `acceptance-tester` writes only the acceptance tests and `tasks.md`.
  - `implementer` can never touch the acceptance tests, the spec, the contract files or the ADRs.
  - `verifier` writes nothing but its memory.
  - No subagent edits `.claude/` outside its own memory directory, or changes the `status:` of `intent.md` or an ADR
    (that is `sdd set-status` / `sdd adr-accept`, lead only). The guard compares the file's
    front matter before and after the write, so a status spliced in by an Edit counts.

  If the guard itself fails, or a call comes from an agent the session does not list, it
  refuses subagents' calls and lets the lead's through.
- **`sdd` tool.** Agents call `mcp__sdd__sdd` with `args` instead of a script path, and
  the tool applies role rules per subcommand:
  - lead only: `sync`, `set-status`, `new`, `init`, `adr-accept`, `start`, `checkpoint`, `set-pr`, `requires`, `resume`, `finish`, `freeze`
  - read-only, any role: `deps`
  - lead and verifier: `baseline-tree`
  - lead and spec-author: `delta-new`, `delta-stub`, `adr-new`
  - lead and contract-designer: `contract-stub`, `contract-preview`
- **`bundle` tool.** `mcp__sdd__bundle` takes `target` (`specs`, `adrs` or a change id) and
  `fix`. Checking is open to every role; `fix` on `specs` or `adrs` is lead-only, `fix` on a
  change is lead or spec-author.
- **Band above the prompt.** Shows the active change (as in the `/sdd` pane), its phase, its status, task
  progress, the last check result, which workflow agents are running, and how many other
  changes are open. It hides itself when nothing is open.
- **`/sdd` pane.** The active change in full: the one whose branch (`sdd/<id>`) is checked
  out in the session's directory, else the most active. It shows its title, phase and hint,
  a progress bar, every task with its citations, ADRs, requires, and the last check with its
  ERROR lines. The other open changes sit in status groups (implementing, verified,
  approved, draft), folded to one line each (`▸ approved (6) a, b, …`, plus how many checks
  failed). Press a header, or its digit while the pane has focus, to unfold it: one line per
  change with its phase, tasks, PR, requires, check result and a failed check's ERROR lines.
  Then running agents and the last guard refusal. `/sdd check <change> [--tests]` runs a
  check without the model; `/sdd refresh` re-reads the state.
- **`/sdd phase` pane.** The workflow's phases for the active change (Spec, Contract, Gate 1,
  Plan, Gate 2, Acceptance tests, Implement, Verify, Sync; `surface: none` skips Contract, a
  `size: fix` change skips Spec, Contract and Gate 1 and writes its tests alongside the plan,
  before Gate 2): done ones
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
- **Sync** merges by unit (criterion, section, invariant); MODIFIED replaces the whole unit,
  nothing is paraphrased.
- **Conflicts.** Each MODIFIED or RETIRED criterion, replaced section, replaced invariant and
  deprecation carries the hash of the living text it was based on, so if another change
  edited that unit first you get a CONFLICT, not a silent overwrite. Since each change lives
  on its own branch, `sync` first merges `origin/<base>` in, so "first" means "merged into
  the base". Changes to different criteria of one capability merge independently, in sdd and
  in git (a merge keeps the capability's `generated.at`; the logs merge by union). A change
  merged into the base *after* this one synced, and that edited the same unit, shows up as a
  git conflict at `finish`: see `docs/how-to/resolve-sync-conflict.md`.
- **Contracts.** A full change declares its public `surface` (`api`, `cli`, `ui`, or `none`)
  in intent.md. For each kind the contract-designer writes typed files under
  `changes/<id>/contracts/` (TypeSpec, CLI synopsis, static HTML mockup), each citing the
  criteria it serves; you review them at Gate 1. `contract-stub` copies a living file with a
  base hash (a moved living file is a CONFLICT), `contract-diff` shows the change, and `sync`
  copies whole files into `contracts/` (`contracts_dir`). `contract-preview` builds the contracts as
  the change leaves them in a git-ignored dir for `contract_cmd` (e.g.
  `npx tsp compile {dir}/api/sdd-main.tsp --no-emit`), which the agent runs, never sdd.py.
- **Traceability.** `check` fails when a criterion has no Given/When/Then, no test task or
  no impl task, an invariant no check or test task, or when anything cites a criterion,
  invariant, ADR or task that doesn't exist (or is retired or deprecated).
  `check --tests` also fails when a unit has no acceptance test or a task is still open.
- **Freeze.** The lead runs it once per batch of test tasks. It records hashes of every file
  in the acceptance dir (tests, helpers, fixtures) and the base commit; `verify-frozen`
  catches any edit, deletion or new file that slipped past the guard, and accepts only what
  a merge of the base brought in.
- **Context bundles.** `context <change> <task>` gives each agent only its own slice:
  - every task: the criteria it cites (with their capability's Intent), the invariants it
    cites in full, and the ADR Decision sections
  - test tasks: the plan's Contracts section, nothing else from the plan
  - test and impl tasks: the contract files citing their criteria
  - `context <change> --contract`: the contract-designer's bundle (touched criteria, the
    contract files they cite)
  - impl tasks: the statements of the invariants in force, the frozen test paths, plus the
    full plan with `--plan`

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
- Implementers run one at a time. Claude Code's isolated worktrees start from the default
  branch, without the change's tasks, plan and frozen tests, so the workflow does not use them.
- The Bash check is heuristic: it follows `cd` and redirects, but code that builds a path at
  run time (a `python -c` one-liner) gets past it. `verify-frozen`, run by the verifier and
  ideally in CI, is the real enforcement for the acceptance dir.
- Two changes in review at the same time that both edit one unit: the second one's `finish`
  stops on a git conflict, resolved by hand (`docs/how-to/resolve-sync-conflict.md`).
- The band and pane refresh on workflow events and every 30 s; edits made outside
  Claude Code show on the next refresh or with `/sdd refresh`.
