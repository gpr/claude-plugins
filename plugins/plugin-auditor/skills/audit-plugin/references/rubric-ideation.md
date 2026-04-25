# Ideation rubric — think big

Whole-plugin ideation: read every file in the plugin, then propose what's missing across the **full** component spectrum.

## Component types to range across

- **Missing skills** — user workflows the plugin currently forces Claude to improvise.
- **Missing agents** — specialised tasks that would benefit from an isolated context and focused system prompt.
- **Missing hooks** — automation opportunities (pre-commit checks, post-edit validation, permission gates).
- **Missing monitors** — background signals worth surfacing (log tails, build watchers, deployment status).
- **MCP integrations** — external services the plugin's domain clearly touches but doesn't expose (databases, APIs, cloud consoles, dashboards).
- **Cross-plugin synergies** — overlap with another plugin in the same `marketplace.json`. Propose concrete handoffs.
- **Novel workflows** — beyond the obvious. What would a 10x user of this plugin wish existed?

## Proposal format

Each proposal must include:

- **Name** and component type.
- **Problem** — what user pain it addresses (1–2 lines), tied to specific evidence in the plugin.
- **Concrete file path** where it would live.
- **Trigger/activation sketch** — description frontmatter for skills/agents, event+matcher for hooks, interval+command for monitors, server config for MCP.
- **Effort estimate** — S / M / L.
- **Dependencies** — external tools, env vars, MCP servers required.

Aim for **3–6 proposals**. Fewer means you haven't stretched; more means you're padding. At least one must be cross-cutting (another marketplace plugin or external MCP ecosystem). Prioritise by user value, not ease of implementation.

## Bar

- **Bold, not safe.** "Add a validation hook" is too generic. Name the exact validation, matcher, and failure mode.
- **Grounded.** Reference specific evidence: a skill that improvises, a domain touched but not exposed, a workflow implied by `description`.
- **No overlap with auditors.** Your scope is *additions*, not corrections to existing files.

## Leave alone

- Do not create files. Proposals go in the report only — the user decides what to build.
- Do not audit existing components — that's the four sibling auditors' job.
