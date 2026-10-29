# sdd eval suite

End-to-end task-completion evals for the workflow, run by `claude plugin eval`. They grade
the end state of a request (change finished, spec synced, archived, verifier PASS, no
workflow on a refactor or a question), not which agents ran. That way the same suite can
compare workflow shapes: a folded agent, a parallel step, a resumed implementer.

Every case starts from `_fixture/make-repo.sh`: a small Python CLI (`tally`) with unit
tests, a bare `origin` next to it, and `sdd init` committed and pushed on `main`. The file
has a planted bug: an empty line between two numbers raises ValueError.

| Case | Path | Checks |
|---|---|---|
| `feature-cli` | full change, `surface: cli` | finished, verifier PASS, capability synced, archived, acceptance tests, CLI contract synced |
| `feature-library` | full change, `surface: none` | same, and no contract files |
| `fix-blank-line` | fix with a criterion | same, and no contract-designer |
| `adopt-cli` | adopt | same, and no Edit/Write on `tally/*.py` |
| `direct-rename` | direct (should not fire) | renamed in place, no `sdd start`, no `sdd:` agent |
| `question` | answered directly (should not fire) | names the crash, no `sdd start`, no `sdd:` agent |

## Run

From the repository root. The write tools have to be granted, and granting Bash needs the
OS sandbox (`bubblewrap` and `socat` on Linux).

```bash
claude plugin eval plugins/meta/sdd --trust-plugin --scaffold --allow-tools Bash Edit Write --no-publish
```

- Cheap smoke run (a few minutes): add `--tag should-not-fire --runs 1`.
- The full cases run the whole workflow, 30-60 minutes each, and cost real money. Each runs
  twice by default (a regression can show in only one run). By default the eval also runs a
  no-plugin baseline arm; `--ablation none` skips it when you only compare two versions of
  sdd.
- To compare two workflow shapes, run the suite on each and diff per case in
  `results/<timestamp>/aggregate-result.json`: score, `costUsd`, `durationSeconds`. Look at
  which cases flipped, not only the mean. `turns` counts only the lead's last stretch after
  background agents return (6 on a full fix), so count spawns and lead↔agent round trips from
  the trace instead (`--keep-temp`, then `out/trace.jsonl`; subagent calls carry
  `parent_tool_use_id`).

## Known limits

- A headless run has no user. The cases append a system prompt that says to approve
  consistent gates and to go on without a GitHub PR (`origin` is a local bare repo).
- An eval session has no `EnterWorktree`, so the fixture sets `"in_place": true`: each change
  is checked out in the run's cwd instead of `.claude/worktrees/sdd-<id>/`. The suite measures
  that path, not the worktree one; the two differ only in where the branch is checked out.
- The `files` graders see the files the run created. Files that existed before the run never
  show up there.
- Subagent tool calls are in the trace, so `tool_used` graders see the implementer's edits too.
- Pilot of `fix-blank-line` (one run): 6/6 graders passed in about 4.5 minutes for $1.61. It
  spawned spec-author (twice), acceptance-tester, planner, implementer and verifier. The
  code-review step was skipped because the skill is not available in an eval session.
