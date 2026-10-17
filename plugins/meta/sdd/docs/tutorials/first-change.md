---
type: Tutorial
title: Your first spec-driven change
description: Take a tiny CLI from request to merged spec with the sdd workflow - set up a sandbox repo, approve a spec at Gate 1, watch the agents test and implement, and finish the PR.
tags: [sdd, tutorial, getting-started]
sources:
  - resource: ../../skills/change/SKILL.md
  - resource: ../../tools/sdd.py
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Your first spec-driven change

In this tutorial we add a `--name` option to a one-file Python CLI. Along the way you will see every step of the workflow once: triage, the spec delta, Gate 1, the plan, Gate 2, acceptance tests, implementation, verification and sync.

It takes about 20 minutes. Everything stays on your machine: a local bare repository plays `origin`, so you need neither GitHub nor `gh`.

You need Claude Code, git, Python 3.9+ and `pytest` (`pip install pytest`).

## 1. Make a sandbox project

```
mkdir -p ~/sdd-tutorial && cd ~/sdd-tutorial
git init -q --bare origin.git
git clone -q origin.git greet && cd greet
git checkout -q -b main
mkdir -p tests/unit
cat > greet.py <<'EOF'
import sys

def main(argv):
    print("Hello!")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF
cat > tests/unit/test_greet.py <<'EOF'
from greet import main

def test_default(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out == "Hello!\n"
EOF
touch tests/__init__.py tests/unit/__init__.py
git add . && git commit -qm "initial" && git push -q -u origin main
```

## 2. Enable the plugin for this project

Start Claude Code in `~/sdd-tutorial/greet` and install the plugin at **project** scope:

```
/plugin marketplace add gpr/claude-plugins
/plugin install sdd@gpr-plugins
```

You'll notice nothing yet: the band above the prompt appears only once a change is open.

## 3. Initialise the workflow

Type:

> Set up sdd in this repo.

The lead runs `sdd init`:

```
created: specs/, adr/, changes/, tests/acceptance/, .claude/sdd.json (edit acceptance_cmd / unit_cmd), specs/index.md, specs/log.md, .gitignore (/.claude/worktrees/)
```

The defaults (`pytest -q {files}` and `pytest -q tests/unit`) suit this project, so leave `.claude/sdd.json` as it is. Commit and push it with the empty `specs/` bundle (`specs/index.md`, `specs/log.md`), since each change will start from `origin/main`:

```
git add .claude/sdd.json .gitignore specs && git commit -qm "chore: set up sdd" && git push -q
```

## 4. Ask for the change

> Add a `--name NAME` option: `python greet.py --name Ada` prints `Hello, Ada!`. Without it, keep printing `Hello!`.

Notice what the lead does first. It **triages** in one line: this changes observable CLI behavior, so it's a *full change*. Then it starts the change:

```
worktree /home/you/sdd-tutorial/greet/.claude/worktrees/sdd-greet-by-name
branch sdd/greet-by-name (base main)
PR missing (...): create a draft PR for sdd/greet-by-name, then run `set-pr greet-by-name <number>`
next: EnterWorktree path=...
```

`PR missing` is expected here: there's no GitHub. If the lead offers to open a PR some other way, tell it to continue without one. The band above the prompt now shows the change in phase **Spec**.

## 5. Gate 1: review the spec

The spec-author writes `changes/greet-by-name/intent.md` and a delta in `changes/greet-by-name/specs/greet/greeting.md` (one short concept file for the `greet` capability), like:

```markdown
## ADDED

### REQ-GREET-001: Greet a named user
The CLI MUST print `Hello, <name>!` when run with `--name <name>`.

#### Scenario: named greeting
- GIVEN no configuration
- WHEN the user runs `greet --name Ada`
- THEN stdout is `Hello, Ada!` and the exit code is 0
```

Your wording will differ. The spec-author also runs `bundle` with `fix` on the change, which regenerates the change's `index.md`. The lead then shows you a compact summary (why, outcome, non-goals, each REQ and scenario name) and asks you to approve, change something, or stop.

This is the one review that needs your full attention. Check that there is a REQ for the default behavior too (`Hello!` without `--name`). If there isn't, answer:

> Change: add a scenario that `greet` without options still prints `Hello!`.

The lead sends that to the same spec-author and shows you Gate 1 again. When it's right, answer **approve**. The lead sets the status to `approved`.

## 6. Plan and Gate 2

The planner writes `plan.md` (with a **Contracts** section: the `--name` flag and its output) and `tasks.md`:

```
- [ ] T1 (test) Named and default greeting — REQ-GREET-001, REQ-GREET-002
- [ ] T2 (impl) Parse --name in greet.py — REQ-GREET-001 REQ-GREET-002 | blocked-by: T1 | files: greet.py
```

Gate 2 is automatic. You'll see something like:

```
OK greet-by-name: 2 REQ, 2 tasks, 0 errors, 0 warnings
```

followed by the task count and contracts. There's nothing to do unless you object.

## 7. Tests first, then code

Run `/sdd phase` and keep the pane open while you watch:

1. The **acceptance-tester** writes `tests/acceptance/test_greet_name.py`, with `REQ-GREET-001` in a comment above each test. It runs the tests, confirms they fail because `--name` doesn't exist yet, ticks T1 and runs `sdd freeze`:
   ```
   froze 1 file(s) -> changes/greet-by-name/frozen.json
   ```
2. The **implementer** changes `greet.py`, writing a unit test first, until the frozen acceptance tests and the unit suite pass, then ticks T2.

Each step ends with a checkpoint: a commit and a push of the branch to your local `origin`.

## 8. Verify, review, sync

The **verifier** reports something like:

```
VERDICT: PASS
frozen: ok   acceptance: 2/2   unit: 3/3   trace: ok
findings:
```

A `code-review` pass follows. Then the lead syncs:

```
ADDED    REQ-GREET-001
ADDED    REQ-GREET-002
synced 2 change(s); ADRs accepted: -; archived -> changes/archive/2026-10-17-greet-by-name
```

Open `specs/greet/greeting.md` in the worktree. It now holds your two requirements, word for word as you approved them. `specs/greet/index.md` lists them, and `specs/log.md` has a new line: `- 2026-10-17 greet-by-name: ADDED REQ-GREET-001; ADDED REQ-GREET-002`.

Finally `sdd finish` marks the phase `done` and pushes. With GitHub it would mark the PR ready for review. Here it says to do that by hand.

## 9. Merge

Merge the branch as you would a PR:

```
cd ~/sdd-tutorial/greet
git merge --no-ff -q origin/sdd/greet-by-name && git push -q
python greet.py --name Ada
```

```
Hello, Ada!
```

## What you've done

You turned a one-sentence request into an approved requirement, a frozen acceptance test that encodes it, code that passes it, and a living spec that records it. Along the way you reviewed only once: at Gate 1.

Next:
- [Your first fix](first-fix.md): the shorter path when code breaks an existing REQ.
- [How the workflow fits together](../explanation/workflow-overview.md): why each step is there.
