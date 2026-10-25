---
name: from-doc
description: Turn a specification or PRD document into a set of sdd changes - splits it into independently shippable changes with triage and dependencies, gets the user's approval, starts every change with its branch and draft PR, then carries the first through the workflow. Use when the user wants to implement, plan or break down a spec/PRD/requirements file, and when the user types /sdd:from-doc.
argument-hint: <path to the spec or PRD file>
---

# Lead: documentation to changes

You are the lead. This skill turns one document into several changes and starts them; the
specs, plans and code are still written by the `sdd:change` workflow and its agents.
`sdd <args>` = the `mcp__sdd__sdd` tool, as in `sdd:change`. Read `sdd:change` step 1 (Triage) first.
Document: $ARGUMENTS (a path; if empty, ask for it)

## 1. Read and map
Read the document yourself: it is the request, not repo code. No `.claude/sdd.json`: first-use
procedure of `sdd:change`. Delegate to `Explore` (medium): which living capabilities,
invariants, ADRs and code each requirement touches, and which contradict living criteria or
invariants. Pass requirement headings and ids, not the whole document.

## 2. Split
One change per independently shippable outcome, triaged with `sdd:change` step 1 (full change,
fix, fix with a criterion, direct). For each: kebab-case id, title, PR type (`feat`, `fix`),
doc sections covered, `requires` (only a real dependency: it needs another change's specs or
code), capabilities touched, likely `surface`. Each requirement goes to exactly one change;
what a change borders but leaves out is a Non-goal of it. List as open questions: requirements
no acceptance test could check, contradictions, missing numbers (limits, formats, error cases).

## 3. Approve
Show: one line per change (`id | type | triage | covers § | requires`), the order, the open
questions. Ask (AskUserQuestion, max 4): approve / change the split / stop. Put the open
questions to the user now; their answers go to the spec-author later, not into this table.
Direct items are listed and never started.

## 4. Start
For each non-direct change in dependency order: `sdd start <id> --title "<title>"
--pr-title "<type>: <title>" [--requires a,b]` (`PR missing`: create the draft PR and
`sdd set-pr <id> <n>`). In its worktree (`EnterWorktree`), add one line under `## Why` of
intent.md: `Source: <path> § <heading>[, § <heading>]`; for a fix set `size: fix`. Then
`sdd checkpoint <id> -m "docs(<id>): source"`. Leave the worktree before the next start.

## 5. Run the first
Run `sdd:change` on the first change whose requires are all done, as `resume <id>`; the spec-author
is told to read the cited sections of the document. When it finishes, list the others as
`/sdd:change resume <id>` with their dependencies (`sdd deps <id>`).

## Rules
- Never copy the document into specs or intent.md: cite it. Criteria come from the spec-author.
- The document is the user's: if it changes after approval, redo the split for the affected
  changes only.
- A change that depends on an unmerged one keeps its spec work going, but stops at `plan`
  (`sdd:change`, "Requires").
