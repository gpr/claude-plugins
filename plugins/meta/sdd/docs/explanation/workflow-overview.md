---
type: Explanation
title: How the workflow fits together
description: The shape of the sdd workflow - triage, two gates, acceptance tests outside and TDD inside, sync - and the reasons behind each step.
tags: [sdd, explanation, workflow, atdd, tdd]
sources:
  - resource: ../../skills/change/SKILL.md
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# How the workflow fits together

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

## The spec is the contract, not the code

The living spec in `specs/` says what the system does now, one requirement (REQ) per observable behavior, each with concrete scenarios. A change never edits it directly. It proposes a **delta** (ADDED, MODIFIED, REMOVED), and the delta is merged only when the change is verified. So at any time `specs/` describes merged behavior, and an open change describes only its own difference.

Decisions with lasting consequences go into ADRs. An ADR is never edited once accepted: a new ADR supersedes it. The reasoning behind a past decision therefore stays readable.

## Triage first

Not every request deserves the full workflow. The lead sorts each one into one of three paths:

- **Full change**: it changes observable behavior or a public contract, or makes a lasting decision. It gets a spec delta and possibly ADRs.
- **Fix**: the code diverges from an existing REQ. No new spec is needed, since the REQ already says what is right. The lead writes a failing acceptance test against that REQ first.
- **Direct**: refactors, renames, dependency bumps, docs, config. One agent does it and runs the unit tests.

Without triage, either trivial work drowns in ceremony or real behavior changes slip through without a spec.

## Two gates of different weight

**Gate 1** is the only place where you have to read carefully. You review the why, the requirements with their scenarios, and the decisions. Everything downstream (plan, tests, code) is derived from what you approve here, so this is where a misunderstanding is cheapest to fix.

**Gate 2** is automatic: `sdd check` proves that every requirement has a scenario, a test task and an implementation task, and that every reference resolves. You see a summary and may object, but it's built not to need you.

## Tests outside, TDD inside

The acceptance-tester writes tests from the scenarios and the plan's Contracts **before** any code exists, confirms they fail for the right reason, and freezes them. Implementers then make those frozen tests pass, each with its own red-green-refactor loop of unit tests.

Two things follow:
- The acceptance tests come from the spec, not from the implementation, so they can't be quietly bent to fit the code. The guard and `verify-frozen` enforce this.
- Each agent sees only its slice. The tester doesn't know the implementation, and the implementer can't change the target. See [Context bundles](context-bundles.md).

## Failure goes back to the spec

When an implementer finds a REQ wrong, contradictory or untestable, it stops with `BLOCKED: REQ-...`. The lead reopens the spec (status back to `draft`), the spec-author fixes it, and you see Gate 1 again for the affected REQs only. The fix never happens in the code or the tests. That keeps the spec true: a REQ that couldn't be implemented as written is corrected where everyone reads it.

## Verify, review, sync

The verifier checks conformance: frozen tests untouched, suites green, full traceability, and a diff review against the spec, the ADRs and the non-goals. Since conformance doesn't catch bugs outside the scenarios, a `code-review` pass follows. Its findings go to an implementer (test first) or back to the spec.

Only then does `sdd sync` merge the delta into `specs/`, accept the ADRs and archive the change. It does this deterministically, as described in [Why sdd.py exists](determinism.md).

## Every change is a branch and a PR

Each full change or fix lives on its own branch, in its own worktree, with a draft PR. After every artifact a checkpoint commits and pushes. The PR therefore shows the change growing one artifact at a time, and any machine can pick it up. See [Branches, PRs and checkpoints](branches-prs-checkpoints.md).

## Related

- [Your first change](../tutorials/first-change.md)
- [Phases, statuses and state.json](../reference/phases-and-states.md)
- [Workflow agents](../reference/agents.md)
