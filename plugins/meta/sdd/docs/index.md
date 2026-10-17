---
okf_version: "0.2"
---

# sdd documentation

Documentation for the `sdd` Claude Code plugin, a spec-driven multi-agent workflow. It is organised by [Diátaxis](https://diataxis.fr/) and packaged as an [OKF v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundle: every page carries YAML front matter with `type`, `sources` and `generated`.

## Tutorials

* [Your first spec-driven change](tutorials/first-change.md) - add an option to a tiny CLI, from request to merged spec, in a local sandbox.
* [Your first fix](tutorials/first-fix.md) - repair a broken requirement test-first, without a new spec.

## How-to guides

* [Install and configure sdd](how-to/install-and-configure.md) - project-scope install, `sdd init`, test commands, publish the config.
* [Write a spec delta and an ADR](how-to/write-a-delta-and-adr.md) - add, modify and remove REQs; record or supersede a decision.
* [Resume a change](how-to/resume-a-change.md) - continue by id or PR number; blocked, diverged and conflicting resumes.
* [Make a change depend on another](how-to/manage-dependencies.md) - `--requires`, `deps`, unblocking, clearing.
* [Reopen a spec](how-to/reopen-a-spec.md) - when an agent reports BLOCKED or a scenario is untestable.
* [Resolve a REQ conflict](how-to/resolve-sync-conflict.md) - a CONFLICT from `check` or `sync`.
* [Run verify-frozen and check in CI](how-to/run-verify-frozen-in-ci.md) - fail PRs that tamper with frozen tests.
* [Follow a change from the band and panes](how-to/use-the-band-and-panes.md) - status, checks without the model, guard refusals.
* [Share or isolate agent memory](how-to/share-agent-memory.md) - commit, ignore or turn off.

## Reference

* [sdd subcommands](reference/cli.md) - every `sdd.py` subcommand, its effect and its role, plus the `check` rules.
* [sdd tool and its role rules](reference/sdd-tool-roles.md) - `mcp__sdd__sdd` input, output and `SDD_RULES`.
* [Guard rules](reference/guard-rules.md) - who may write what, Bash heuristics, failure policy.
* [Workflow agents](reference/agents.md) - the five agents: job, input, output, tools, model, memory.
* [Phases, statuses and state.json](reference/phases-and-states.md) - phase ids, statuses, fix order, derived phase, dependency states.
* [File formats](reference/file-formats.md) - REQ blocks, deltas, base markers, intent, ADR, plan, task lines, test tagging.
* [Repository layout](reference/repo-layout.md) - the files sdd creates and who writes each.
* [Configuration](reference/configuration.md) - `.claude/sdd.json` keys, project root, requirements.
* [Slash commands, band and panes](reference/slash-commands.md) - `/sdd:change`, `/sdd`, the band and both panes.
* [Known limits](reference/known-limits.md) - current limitations and their workarounds.

## Explanation

* [How the workflow fits together](explanation/workflow-overview.md) - triage, two gates, tests outside and TDD inside, sync.
* [Why sdd.py exists](explanation/determinism.md) - exact sync, base-hash conflicts, traceability, freezing.
* [Why the guard works the way it does](explanation/guard-design.md) - roles from agentId, status-bound permissions, fail-closed.
* [Why the main conversation is the lead](explanation/lead-as-main-conversation.md) - an appended prompt section, not an agent.
* [Context bundles](explanation/context-bundles.md) - what each agent receives, and why so little.
* [Branches, PRs and checkpoints](explanation/branches-prs-checkpoints.md) - one branch per change, checkpoints, "merged" as done.

## Contributing

* [Plugin architecture](contributing/architecture.md) - the layers and what each must not do.
* [Things that must change together](contributing/keep-in-sync.md) - facts stated in several files, docs included.
* [Test a change to the plugin](contributing/testing.md) - the three suites, the validators, commit rules.
