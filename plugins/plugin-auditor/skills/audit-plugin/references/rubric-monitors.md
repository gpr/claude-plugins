# Monitors & ideation rubric

Dual purpose: audit `monitors/monitors.json` and propose bold additions across the whole plugin.

## Monitors audit

- `monitors.json` parses as JSON (`jq .`). Syntax errors are a defect.
- Each monitor entry has `name`, `command`, and `trigger` (interval or event). Missing fields are a defect.
- `command` uses `${CLAUDE_PLUGIN_ROOT}` — no hardcoded paths.
- Interactive-only caveat stated in README when a monitor is present (monitors do not run in headless/SDK mode).
- Interval choices are justified — a 5-second poll on a log file is typically wasteful; prefer event-driven `tail -F` patterns.

## Ideation — think big

Read every file in the plugin (`plugin.json` description, `CLAUDE.md` if any, every skill, every agent, every script). Then propose additions the plugin **should** have to fulfil its stated domain. Range over all component types:

- **Missing skills** — user workflows the plugin currently forces Claude to improvise.
- **Missing agents** — specialised tasks that would benefit from an isolated context and focused system prompt.
- **Missing hooks** — automation opportunities (pre-commit checks, post-edit validation, permission gates).
- **Missing monitors** — background signals worth surfacing (log tails, build watchers, deployment status).
- **MCP integrations** — external services the plugin's domain clearly touches but doesn't expose (databases, APIs, cloud consoles, dashboards).
- **Cross-plugin synergies** — does this plugin's domain overlap with another in the same marketplace? Propose concrete handoffs.
- **Novel workflows** — think beyond the obvious. What would a 10x user of this plugin wish existed?

## Proposal format

For each proposal, include:

- **Name** and component type.
- **Problem** — what user pain it addresses (1–2 lines).
- **Concrete file path** where it would live.
- **Trigger/activation sketch** — description frontmatter for skills/agents, event+matcher for hooks, interval+command for monitors.
- **Effort estimate** — S / M / L.
- **Dependencies** — external tools, env vars, MCP servers required.

Aim for 3–6 proposals. Fewer means you haven't stretched; more means you're padding. Prioritise by user value, not ease of implementation.

## Proposals you may emit

- Fix `monitors.json` schema errors.
- Replace hardcoded paths with `${CLAUDE_PLUGIN_ROOT}`.

## Leave alone

- Do not create the proposed new components as files. Proposals go in the report only — the user decides what to build.
