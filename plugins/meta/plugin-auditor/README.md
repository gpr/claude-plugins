# plugin-auditor

Audits a Claude Code plugin's content quality and surfaces ambitious new component ideas. Complements (does not replace) `@agent-plugin-dev:plugin-validator`, which owns structural validation.

## What it does

One user-invoked skill (`/plugin-auditor:audit-plugin <plugin-path>`) fans out to five focused subagents **in parallel**:

| Agent | Audits | Doc source |
|-------|--------|------------|
| `skills-auditor` | `skills/*/SKILL.md` | skills.md |
| `agents-auditor` | `agents/*.md` | sub-agents.md |
| `hooks-auditor` | `hooks/hooks.json` + `scripts/*.sh` | hooks.md |
| `monitors-auditor` | `monitors/monitors.json` | plugins-reference.md |
| `plugin-ideator` | whole plugin + `marketplace.json` for synergies | plugins-reference.md |

Each agent:

1. Fetches the current Claude Code doc for its area (no stale cache).
2. Scores its files against a rubric (see `skills/audit-plugin/references/`).
3. Emits **proposals** for clear-cut defects (file:line + before/after + severity + rationale). **No files are modified.**
4. Flags judgement calls as recommendations.

The orchestrator aggregates the four reports into `<plugin-path>/.claude/reviews/<timestamp>-plan.md`, prepends a prioritised action plan sorted by severity, and prints a short summary. The user decides what to apply.

`plugin-ideator` proposes 3–6 bold new components (skills, agents, hooks, monitors, MCP integrations, cross-plugin synergies) grounded in the target plugin's domain.

## Usage

```
/plugin-auditor:audit-plugin plugins/my-plugin
```

The target can be any directory containing `.claude-plugin/plugin.json`.

## Scope

**In scope:** prompt-engineering quality, trigger-phrase strength, concision, doc alignment, shellcheck, security defaults, feature ideation.

**Out of scope:** manifest wiring, file naming, marketplace registration. Run `@agent-plugin-dev:plugin-validator` for those.

## Safety

- Read-only: auditor agents do not have `Edit` or `Write` and cannot mutate plugin files.
- The only file the orchestrator writes is the plan report under `<plugin-path>/.claude/reviews/`.
- Proposals cover structural and prompt-engineering concerns listed in the rubrics — domain content is out of scope.
