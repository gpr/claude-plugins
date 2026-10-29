---
type: How-to Guide
title: Test a change to the plugin
description: Run the three sdd test suites, the plugin validator and the workflow evals, and know which suite covers which part.
tags: [sdd, contributing, testing]
sources:
  - resource: ../../tests/test_sdd.py
  - resource: ../../tests/guard.test.ts
  - resource: ../../tests/phase.test.ts
  - resource: ../../tests/mod.test.tsx
  - resource: ../../README.md
  - resource: ../../evals/README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Test a change to the plugin

Run from the repository root.

1. **`sdd.py`**: black-box tests. Each one runs the script as a subprocess in a throwaway git repo, the way the tool calls it. The git cases use a real bare `origin` and a fake `gh`.
   ```
   python3 -m unittest discover -s plugins/meta/sdd/tests -p 'test_*.py'
   ```
   Every behavior change in `sdd.py` gets a case here.

2. **Guard, phase logic and mod**:
   ```
   claude plugin test plugins/meta/sdd
   ```
   - `tests/guard.test.ts`: file-write rules per role, Bash heuristics, status lines, `SDD_RULES`, `roleOf`. Every rule change gets a case.
   - `tests/phase.test.ts`: `phaseOf` per status/size/tasks/agents, fix order, `stepOf`, `byActivity`, `byStatus`, `activeOf`.
   - `tests/mod.test.tsx`: the guard in a session, the lead section in the system prompt, band and pane rendering on terminal and desktop.

3. **Manifest and wiring**:
   ```
   claude plugin validate plugins/meta/sdd
   ```
   Then `@agent-plugin-dev:plugin-validator` and `/plugin-auditor:audit-plugin plugins/meta/sdd`, as the repository's `CLAUDE.md` requires.

4. **Workflow evals**: end-to-end runs of real requests against a fixture repo, graded on the end state (see [`evals/README.md`](../../evals/README.md)):
   ```
   claude plugin eval plugins/meta/sdd --trust-plugin --scaffold --allow-tools Bash Edit Write --no-publish
   ```
   Run them before and after any change to the workflow's shape (which agent does what, what runs in parallel, what the lead loads). The `should-not-fire` tag is a cheap smoke run; the full cases take 30-60 minutes each.

5. **Try it for real**: `claude --plugin-dir ./plugins/meta/sdd` in a scratch repo, and walk through [Your first change](../tutorials/first-change.md).

## Commits

Use Conventional Commits. `feat` → minor, `fix`/`perf` → patch, others → no release (cocogitto computes the version on `main`). Use `refactor`, not `fix`, for a bug that was never released. Never edit `version` in `plugin.json` or `CHANGELOG.md` by hand. If you change something listed in [Things that must change together](keep-in-sync.md), update the docs in the same commit.
