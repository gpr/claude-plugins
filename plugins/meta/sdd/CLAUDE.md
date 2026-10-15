# sdd

- `tools/sdd.py` is the only code that writes specs, ADR statuses, `frozen.json` or the
  archive. Keep it deterministic (no model calls) and its output terse: agents read it.
- `hooks/guard.ts` holds the write rules as pure functions; `hooks/register.tsx` only does
  I/O (`$.fs`, `$.process`, `$.agent.list`) and drawing. Every rule change gets a case in
  `tests/guard.test.ts` (`claude plugin test plugins/meta/sdd`).
- The guard identifies the caller from `tool.call`'s `agentId` → `$.agent.list()` type.
  Plugin agents report `sdd:<name>`; `roleOf` maps only that prefix. Renaming an agent
  file renames its role: update `ROLES` and the agent tables in README and `skills/change`.
- The main conversation is the lead because `register.tsx`'s `prompt.compose` hook appends
  the `sdd:lead` section (`LEAD`). Keep it a short router: the workflow lives in
  `skills/change`. Not an agent with `settings.json` `agent`: a plugin agent's prompt
  would replace Claude Code's whole system prompt.
- Guard failure policy: refuse for subagents, allow for the lead (`.catch` in register.tsx).
- The `sdd` tool's per-subcommand roles live in `SDD_RULES` (guard.ts) and are restated in
  the tool description and README. Change all three together.
- Agents call `mcp__sdd__sdd`, never `python3 .../sdd.py`; the guard refuses the latter
  for subagents.
- File formats (REQ blocks, delta sections, `<!-- base: -->`, task lines) are parsed by
  `sdd.py` and described in `skills/formats/SKILL.md`. Change both together.
