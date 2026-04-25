---
name: audit-plugin
description: Audits a Claude Code plugin's skills, agents, hooks, and monitors for prompt-engineering quality and doc alignment. Returns a prioritised plan of proposed changes; never modifies plugin files. Invoke when the user says "audit plugin", "review plugin quality", "check plugin components", "plan plugin improvements", "improve my plugin", or runs `/plugin-auditor:audit-plugin <path>`. Takes a path to a plugin directory (one of `plugins/<name>/` in this repo, or any directory containing `.claude-plugin/plugin.json`).
argument-hint: <plugin-path>
allowed-tools: Read, Glob, Bash, Task, Write
---

Fan out five focused auditor/ideator agents in parallel, aggregate their findings, and return a ranked plan of proposed changes. **No plugin files are modified** — the user decides what to apply.

## Scope boundary

This skill owns **content quality** (instruction concision, trigger phrase strength, doc alignment) and **feature ideation** (what the plugin should add). It does **not** re-validate manifest wiring or file naming — tell the user to run `@agent-plugin-dev:plugin-validator` for that.

## Procedure

### 0. Verify and disclose harness capabilities

Before doing anything else, confirm the two tools this skill depends on:

- **`Task`** — required for the §3 parallel fan-out. Without it, the five auditors cannot run independently.
- **`WebFetch`** — required so each auditor can re-read its assigned doc URL on every run. Without it, the doc-drift safeguard (the main failure mode this plugin exists to prevent) is bypassed.

Decide harness state and record it as one of:

- `full` — both `Task` and `WebFetch` are available. Proceed normally.
- `degraded:no-task` — `Task` unavailable. **Do not silently inline the audit.** Tell the user the skill cannot fan out and ask whether to (a) abort, or (b) proceed inline against the rubrics with the limitation flagged in the report header. Default to (a) unless the user picks (b).
- `degraded:no-webfetch` — `WebFetch` unavailable. Same prompt: abort or proceed against cached rubrics only, with the limitation flagged.
- `degraded:none` — neither available. Almost always abort; only continue if the user explicitly accepts a rubric-only review.

The harness state must appear verbatim as the first line of the §5 report and the §6 summary. A degraded run that doesn't disclose its mode is a contract violation.

### 1. Resolve the target

- Treat the first argument as `<plugin-path>`. If absent, stop and ask the user for one.
- Verify `<plugin-path>/.claude-plugin/plugin.json` exists with `Read`. If not, stop — the path is not a plugin root.
- Inventory components with `Glob`:
  - `<plugin-path>/skills/*/SKILL.md`
  - `<plugin-path>/agents/*.md`
  - `<plugin-path>/hooks/hooks.json`
  - `<plugin-path>/monitors/monitors.json`
  - `<plugin-path>/scripts/*.sh`
  - `<plugin-path>/CLAUDE.md` (optional context)

Record which component types exist. A missing type is not a failure — `plugin-ideator` will still run to propose additions.

### 2. Load rubrics

Read all five rubric files from this skill's own `references/` subdirectory (use `${CLAUDE_SKILL_DIR}/references/` to resolve the path from inside this skill):

- `rubric-skills.md`
- `rubric-agents.md`
- `rubric-hooks.md`
- `rubric-monitors.md`
- `rubric-ideation.md`

Each agent receives its rubric embedded in its prompt — do not ask the agent to read the file (keeps the agent's context self-contained and avoids a race with parallel runs).

### 3. Fan out — single message, five Task calls

Launch all five agents in **one** assistant message with five parallel `Task` tool calls (`subagent_type` set to the agent name in each). Sequential spawning is forbidden; it defeats the purpose of this skill.

Each agent prompt must be self-contained and include:

- Target `<plugin-path>` (absolute).
- The explicit list of files it owns (derived from step 1).
- The full rubric text for its area.
- **Authority (read-only)**: "**Do not call Edit, Write, or any tool that modifies files in `<plugin-path>`. Read-only run.** For each defect, emit a proposal with: `file:line`, a 3-line before snippet, the exact proposed replacement, severity (`blocker` / `high` / `medium` / `low`), and a one-sentence rationale. The user will decide whether to apply."
- The doc URL it must `WebFetch` at the start of its run.
- Return format (markdown section — see §5).
- A reminder: do not touch files outside `<plugin-path>`, and do not touch files inside it either.

Agent assignments:

| Agent | Files | Doc URL |
|-------|-------|---------|
| `skills-auditor` | every `skills/*/SKILL.md` and `skills/*/references/*.md` | https://code.claude.com/docs/en/skills.md |
| `agents-auditor` | every `agents/*.md` | https://code.claude.com/docs/en/sub-agents.md |
| `hooks-auditor` | `hooks/hooks.json` + every `scripts/*.sh` | https://code.claude.com/docs/en/hooks.md |
| `monitors-auditor` | `monitors/monitors.json` | https://code.claude.com/docs/en/plugins-reference.md |
| `plugin-ideator` | full plugin tree (all components) + repo `marketplace.json` for synergies | https://code.claude.com/docs/en/plugins-reference.md |

If a file list is empty for an auditor, still launch it — produces a "nothing to review" note. `plugin-ideator` always runs regardless of which components are present; the whole point is proposing what's missing.

### 4. Wait for all five

Do not do any audit work yourself while the agents run. Wait until all five have returned before writing the report — a partial report produces a partial plan.

### 5. Aggregate

Compose one markdown report:

```
# Plugin audit plan: <plugin-name> — <ISO-8601 timestamp> (no files modified)

> Harness: <full | degraded:no-task | degraded:no-webfetch | degraded:none>. <one-sentence consequence — e.g. "Live doc fetch skipped; rubric snapshots used.">

## Summary
- Skills reviewed: N (M proposals: B blocker / H high / Me medium / L low)
- Agents reviewed: N (M proposals: ...)
- Hooks reviewed: N (M proposals: ...)
- Monitors reviewed: N (M proposals: ...)
- Ideation proposals: N

## Prioritised action plan
1. [blocker] <file:line> — <one-line change> (area: skills)
2. [high]    <file:line> — <one-line change> (area: hooks)
...

## Skills
<skills-auditor report>

## Agents
<agents-auditor report>

## Hooks
<hooks-auditor report>

## Monitors
<monitors-auditor report>

## Ideation
<plugin-ideator report>
```

Sort the prioritised list by severity, then by area. Each entry should reference the detailed proposal in the per-area section below.

Write the report to `<plugin-path>/.claude/reviews/<ISO-8601-compact>-plan.md` using `Write`. Create the parent directory with `Bash("mkdir -p <plugin-path>/.claude/reviews")` first. The report file is the **only** file this skill writes.

### 6. Summarise to the user

Print at most six lines:

- Banner: `plan only — no files modified` (append `· harness: degraded:<mode>` if not `full`).
- One-line per area (skills, agents, hooks, monitors, ideation): component/proposal count by severity.
- Path to the full report.
- One line: "Hand-pick items and ask me to apply them, or run `@agent-plugin-dev:plugin-validator` for structural checks."

Do not restate the report's content inline. The user can open the file.

## Hard rules

- **Never edit or write files in `<plugin-path>`** — yours or the agents'. The only allowed write is the report under `<plugin-path>/.claude/reviews/`.
- Never run the agents sequentially.
- Never skip the `WebFetch` step in an agent prompt — doc drift is the main failure mode this plugin exists to prevent.
- Never touch files outside `<plugin-path>`.
- Never run a degraded audit silently — if §0 finds `Task` or `WebFetch` missing, ask the user before proceeding and disclose the mode in the report header and user summary.
- If any agent returns evidence of an `Edit` or `Write` call against plugin content, flag it at the top of the report as a contract violation and continue with the rest of the findings.
