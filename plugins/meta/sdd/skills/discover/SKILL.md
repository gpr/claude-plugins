---
name: discover
description: Generate the living specs and ADRs of an existing codebase from its source code - maps the repo into areas, finds the decisions the code embodies, then writes each area down as tested Baseline criteria through one adopt change per area. Use when the user asks to document what the code does, reverse-engineer specs or ADRs, or bootstrap sdd on a repo with code, and when the user types /sdd:discover.
argument-hint: [all | <area> ...]
---

# Lead: discover specs and ADRs from code

You are the lead. This skill maps an existing repo and drives one `adopt` change per area
(`sdd:change adopt <area>`, its `adopt.md`). It changes no production code. Every criterion it produces is a
Baseline criterion with a passing acceptance test; every ADR is a draft that `sync` accepts.
`sdd <args>` = the `mcp__sdd__sdd` tool, as in `sdd:change`.
Request: $ARGUMENTS (`all`, empty, or the areas to document)

## 1. Precondition
No `.claude/sdd.json`: run the first-use procedure of `sdd:change` (`sdd init --survey`, ask the
user for the config, `sdd init key=value ...`) and commit it before going on.

## 2. Map the repo
Delegate to `Explore` (very thorough; one precise question). Give it `specs/index.md` so it
skips areas already covered. It returns one row per area:
- `id` (kebab-case), one-line purpose;
- public surface (API routes, CLI commands, UI flows, events, exported functions);
- implementing files and existing tests (path, how they run);
- decision candidates: a technology, data model, boundary or security posture the code
  commits to, each with its file evidence (manifest, config, a module layout).
An area is one thing an actor can do, not a directory. No area is made of code nobody calls.

## 3. Choose
If the user named areas, keep those. Otherwise show the table compactly (id, surface, files,
tests yes/no, ADR candidates) in a suggested order: most used surface first; areas without
tests last (their Baseline tests are all new). Ask (AskUserQuestion): which areas now, in
which order; which decision candidates to record. Candidates the user drops are not written.

## 4. One adopt per area
For each chosen area, one at a time, invoke `sdd:change` with `adopt <area>` and follow its `adopt.md`, with the Explore findings of
this area already in hand (skip its own Explore) and the chosen decision candidates passed to
the spec-author as "record after the fact". One adopt = one change = one PR; never batch areas.
After `sdd finish`, report in one line and ask whether to continue. When the user stops, list
the remaining areas as `/sdd:change adopt <area>` lines.

## Rules
- Describe what the code does now. A wish for other behavior is not recorded: it becomes a
  separate `/sdd:change` request.
- A MISMATCH is handled as in `sdd:change`'s `adopt.md`: drop the criterion from the adopt, offer a fix change.
- An invariant is written only where the code enforces the rule (a test, a lint rule, a
  type, a gate). An unenforced habit is not an invariant.
- An ADR needs a real alternative the code shows (a replaced library, a removed path, a
  comment, a commit message). Without one the decision is a line in the capability's Scope.
- Existing ADRs in other folders stay as they are and are linked as plain references.
